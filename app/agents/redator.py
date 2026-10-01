"""Redator do relatório comparativo — tarefa C.4.

Recebe a `Comparacao` do motor (frente C) e as apólices extraídas (frente B) e
devolve o relatório em prosa: o que distingue as apólices e por que importa.

O motor decide *o que* difere sem LLM. Para quase tudo isso basta: campo ausente
numa apólice, valor diferente, lacuna nas duas — o texto sai do `porque_importa`
do especialista, sem modelo nenhum. O LLM entra num único ponto, o
`redacao_divergente`: duas seguradoras escrevem a mesma cláusula com palavras
diferentes, e só a leitura diz se o *conteúdo* difere.

**O redator não pode inventar diferenças.** Mesma regra da frente B — o modelo
propõe, o texto da apólice decide:

* o modelo lê os **trechos literais** das cláusulas, não os resumos da extração;
* para afirmar que duas cláusulas diferem, ele tem de **citar as expressões** de
  cada apólice que provam a diferença. A citação é conferida no trecho, e tem de
  haver prova de pelo menos duas apólices; sem isso, a análise vira
  "inconclusivo", nunca "diferente";
* o trecho é um recorte da cláusula: o que aparece numa apólice e não na outra
  não conta como diferença. No primeiro teste real, sem esta regra, o modelo
  declarou 7 de 8 cláusulas "diferentes" comparando pontos distintos de cada uma;
* número na explicação que não está nos trechos derruba a explicação — o
  guardrail do Desafio 5, de novo;
* se o LLM cair, o relatório sai do mesmo jeito, só sem a leitura das redações.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..domain.comparacao import Comparacao, DiferencaCampo, Veredito
from ..schemas import ApoliceExtraida, CampoExtraido
from .llm import LLMIndisponivel, RespostaLLM, gerar_texto
from .validacao import MINIMO_PALAVRAS_TRECHO, _chave_busca, numeros_sem_apoio

log = logging.getLogger(__name__)


class Leitura(str, Enum):
    """O que a leitura das duas cláusulas concluiu."""

    EQUIVALENTE = "equivalente"            # palavras diferentes, mesmo efeito
    DIFERENTE = "diferente_no_conteudo"    # o efeito para o segurado muda
    INCONCLUSIVO = "inconclusivo"          # os trechos não bastam para afirmar


@dataclass(frozen=True)
class Evidencia:
    """Uma expressão de uma apólice que sustenta a leitura — conferida no trecho."""

    apolice: str
    citacao: str


@dataclass(frozen=True)
class AnaliseCampo:
    """Um campo do relatório: o veredito do motor e, se houve, a leitura do LLM."""

    diferenca: DiferencaCampo
    #: {nome da apólice: campo extraído} — de onde saem trecho e página
    extraidos: dict[str, CampoExtraido | None]
    leitura: Leitura | None = None
    explicacao: str | None = None
    evidencias: tuple[Evidencia, ...] = ()
    #: o que a validação recusou na resposta do modelo, para auditoria
    ressalvas: tuple[str, ...] = ()

    @property
    def campo_id(self) -> str:
        return self.diferenca.campo.id

    @property
    def rotulo(self) -> str:
        return self.diferenca.campo.rotulo


@dataclass(frozen=True)
class RelatorioComparativo:
    apolices: tuple[str, ...]
    analises: tuple[AnaliseCampo, ...]
    modelo_usado: str | None = None
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    #: por que a leitura das redações não aconteceu, quando não aconteceu
    aviso: str | None = None
    resposta_llm: str | None = field(default=None, repr=False)

    def analise(self, campo_id: str) -> AnaliseCampo | None:
        return next((a for a in self.analises if a.campo_id == campo_id), None)

    def com_veredito(self, veredito: Veredito) -> list[AnaliseCampo]:
        return [a for a in self.analises if a.diferenca.veredito is veredito]

    def com_leitura(self, leitura: Leitura) -> list[AnaliseCampo]:
        return [a for a in self.com_veredito(Veredito.REDACAO_DIVERGENTE) if a.leitura is leitura]

    def markdown(self) -> str:
        return _renderizar(self)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_INSTRUCOES = """\
Você é um especialista em seguros D&O ajudando um corretor a comparar apólices
de seguradoras diferentes: {apolices}.

Abaixo estão cláusulas que tratam do mesmo assunto em cada apólice, mas escritas
de formas diferentes. Cada "trecho" é uma cópia literal da apólice. Para cada
campo, decida:

- "equivalente": as redações diferem, mas o efeito para o segurado é o mesmo.
- "diferente_no_conteudo": o efeito muda — cobre mais ou menos, impõe condição
  que a outra não impõe, exclui algo que a outra não exclui.
- "inconclusivo": os trechos não bastam para afirmar nem uma coisa nem outra.

REGRAS — seguir todas:

1. Use SOMENTE os trechos abaixo. Não complete com conhecimento geral de seguros
   nem com o que "costuma" constar em apólices.
2. Cada trecho é um RECORTE da cláusula, não a cláusula inteira. Algo que aparece
   no trecho de uma apólice e não aparece no da outra NÃO é diferença: a outra
   pode tratar disso fora do recorte. Só é "diferente_no_conteudo" quando os
   trechos das duas apólices dizem coisas INCOMPATÍVEIS sobre o MESMO ponto
   (ex.: um diz que a defesa consome o limite, o outro que é paga além dele).
   Se os trechos falam de pontos diferentes da cláusula, é "inconclusivo".
3. Para "diferente_no_conteudo", preencha "evidencias" com uma expressão de CADA
   apólice sobre esse mesmo ponto, copiada LITERALMENTE do trecho daquela apólice
   (4 a 25 palavras cada). Elas serão conferidas; diferença sem evidência
   conferível das duas apólices é descartada.
4. Na dúvida, "inconclusivo". Afirmar uma diferença que não existe é pior que
   não afirmar nada: o corretor vai repetir isso ao cliente.
5. "explicacao": até 3 frases, em português simples, dizendo o que muda (ou por
   que é equivalente, ou por que os trechos não bastam) para quem contrata. Não
   cite número que não esteja nos trechos, nem número de cláusula ou de página.

CAMPOS:

{campos}

Responda APENAS com um objeto JSON, sem texto antes ou depois, neste formato:

{{
  "analises": {{
{exemplo}
  }}
}}
"""


def _descrever(analise: AnaliseCampo) -> str:
    campo = analise.diferenca.campo
    linhas = [
        f'### "{campo.id}" — {campo.rotulo}',
        f"Significado: {campo.significado}",
        f"Por que importa: {campo.porque_importa}",
    ]
    for nome, extraido in analise.extraidos.items():
        trecho = extraido.trecho_origem if extraido else None
        valor = extraido.valor if extraido else None
        linhas.append(f"- {nome}:")
        linhas.append(f"  resumo: {valor or '(sem resumo)'}")
        linhas.append(f'  trecho: "{trecho or "(sem trecho)"}"')
    return "\n".join(linhas)


def montar_prompt(analises: list[AnaliseCampo], apolices: tuple[str, ...]) -> str:
    exemplo = ",\n".join(
        f'    "{a.campo_id}": {{"leitura": ..., "explicacao": ..., '
        f'"evidencias": [{{"apolice": ..., "citacao": ...}}]}}'
        for a in analises
    )
    return _INSTRUCOES.format(
        apolices=", ".join(apolices),
        campos="\n\n".join(_descrever(a) for a in analises),
        exemplo=exemplo,
    )


def interpretar_resposta(texto: str) -> dict:
    """O objeto `analises` da resposta, tolerando cerca markdown e texto em volta."""
    sem_cerca = re.sub(r"```(?:json)?", "", texto)
    inicio, fim = sem_cerca.find("{"), sem_cerca.rfind("}")
    if inicio == -1 or fim <= inicio:
        raise ValueError("a resposta nao contem JSON")
    dados = json.loads(sem_cerca[inicio:fim + 1])
    analises = dados.get("analises") if isinstance(dados, dict) else None
    if not isinstance(analises, dict):
        raise ValueError("a resposta nao tem o objeto 'analises'")
    return analises


# ---------------------------------------------------------------------------
# Validação da leitura
# ---------------------------------------------------------------------------


def _conferir_evidencias(
    brutas, extraidos: dict[str, CampoExtraido | None]
) -> tuple[list[Evidencia], list[str]]:
    """Evidências cuja citação está, de fato, no trecho da apólice indicada."""
    validas: list[Evidencia] = []
    recusadas: list[str] = []
    for bruta in brutas if isinstance(brutas, list) else []:
        if not isinstance(bruta, dict):
            continue
        nome = str(bruta.get("apolice") or "").strip()
        citacao = str(bruta.get("citacao") or "").strip()
        extraido = extraidos.get(nome)
        if extraido is None or not extraido.trecho_origem:
            recusadas.append(f'evidencia atribuida a apolice desconhecida "{nome}"')
            continue
        if len(citacao.split()) < MINIMO_PALAVRAS_TRECHO:
            recusadas.append(f'evidencia curta demais de {nome} ("{citacao}")')
            continue
        if _chave_busca(citacao) not in _chave_busca(extraido.trecho_origem):
            recusadas.append(f'evidencia de {nome} nao esta no trecho ("{citacao[:80]}")')
            continue
        validas.append(Evidencia(apolice=nome, citacao=citacao))
    return validas, recusadas


def validar_leitura(analise: AnaliseCampo, bruta: dict | None) -> AnaliseCampo:
    """Aplica as regras do redator à resposta do modelo para um campo."""
    if not isinstance(bruta, dict):
        return _com(analise, Leitura.INCONCLUSIVO, None, [], ["o modelo nao analisou este campo"])

    try:
        leitura = Leitura(str(bruta.get("leitura") or "").strip())
    except ValueError:
        return _com(analise, Leitura.INCONCLUSIVO, None, [],
                    [f"leitura desconhecida: {bruta.get('leitura')!r}"])

    explicacao = str(bruta.get("explicacao") or "").strip() or None
    evidencias, ressalvas = _conferir_evidencias(bruta.get("evidencias"), analise.extraidos)

    # guardrail numérico: a explicação não traz número que os trechos não tenham
    if explicacao:
        contexto = " ".join(
            f"{c.trecho_origem or ''} {c.valor or ''}"
            for c in analise.extraidos.values() if c
        )
        sem_apoio = numeros_sem_apoio(explicacao, contexto)
        if sem_apoio:
            ressalvas.append(
                f"explicacao citava numero(s) ausente(s) dos trechos ({', '.join(sem_apoio)})"
            )
            return _com(analise, Leitura.INCONCLUSIVO, None, evidencias, ressalvas)

    # diferença só com prova — e prova dos dois lados: uma frase de uma apólice
    # sozinha não mostra contraste, porque o trecho da outra é só um recorte
    if leitura is Leitura.DIFERENTE and len({e.apolice for e in evidencias}) < 2:
        ressalvas.append(
            "diferenca alegada sem evidencia conferivel de pelo menos duas apolices"
        )
        return _com(analise, Leitura.INCONCLUSIVO, None, evidencias, ressalvas)

    return _com(analise, leitura, explicacao, evidencias, ressalvas)


def _com(analise, leitura, explicacao, evidencias, ressalvas) -> AnaliseCampo:
    return AnaliseCampo(
        diferenca=analise.diferenca,
        extraidos=analise.extraidos,
        leitura=leitura,
        explicacao=explicacao,
        evidencias=tuple(evidencias),
        ressalvas=tuple(ressalvas),
    )


# ---------------------------------------------------------------------------
# Redação
# ---------------------------------------------------------------------------


def redigir(
    comparacao: Comparacao,
    apolices: list[ApoliceExtraida],
    gerar: Callable[..., RespostaLLM] = gerar_texto,
    usar_llm: bool = True,
) -> RelatorioComparativo:
    """O relatório comparativo, com a leitura das redações conferida.

    `apolices` são as mesmas passadas a `comparar()`: é delas que vêm os trechos
    literais que o modelo lê. `usar_llm=False` gera o relatório sem a leitura —
    para a demo sem rede e para quando a cota acabou.
    """
    por_nome = {a.nome: a for a in apolices}
    faltando = set(comparacao.apolices) - set(por_nome)
    if faltando:
        raise ValueError(f"apolices da comparacao sem a extracao correspondente: {sorted(faltando)}")

    analises = [
        AnaliseCampo(
            diferenca=d,
            extraidos={nome: por_nome[nome].campo(d.campo.id) for nome in comparacao.apolices},
        )
        for d in comparacao.diferencas
    ]
    a_ler = [a for a in analises if a.diferenca.veredito is Veredito.REDACAO_DIVERGENTE]

    def relatorio(**kw) -> RelatorioComparativo:
        return RelatorioComparativo(apolices=comparacao.apolices, analises=tuple(analises), **kw)

    if not a_ler:
        return relatorio()
    if not usar_llm:
        return relatorio(aviso="leitura das redacoes desligada (sem LLM)")

    try:
        resposta = gerar(montar_prompt(a_ler, comparacao.apolices), json=True)
    except LLMIndisponivel as exc:
        log.warning("redator sem LLM: %s", exc)
        return relatorio(aviso=f"modelo de linguagem indisponivel: {str(exc).splitlines()[0]}")
    try:
        brutas = interpretar_resposta(resposta.texto)
    except ValueError as exc:  # inclui json.JSONDecodeError
        log.warning("resposta do redator fora do formato: %s", exc)
        return relatorio(
            aviso=f"resposta do modelo fora do formato: {exc}",
            resposta_llm=resposta.texto,
        )

    lidas = {a.campo_id: validar_leitura(a, brutas.get(a.campo_id)) for a in a_ler}
    analises = [lidas.get(a.campo_id, a) for a in analises]

    return relatorio(
        modelo_usado=resposta.identificacao,
        tokens_entrada=resposta.tokens_entrada,
        tokens_saida=resposta.tokens_saida,
        resposta_llm=resposta.texto,
    )


# ---------------------------------------------------------------------------
# Texto final
# ---------------------------------------------------------------------------


def _onde(c: CampoExtraido | None) -> str:
    return f" (p. {c.pagina})" if c and c.pagina else ""


def _remete(c: CampoExtraido | None) -> bool:
    """A cláusula existe no documento, mas o valor ficou para a especificação."""
    return bool(c and not c.encontrado and c.pagina and c.trecho_origem)


def _situacao(nome: str, c: CampoExtraido | None) -> str:
    if c and c.encontrado:
        return f"**{nome}**: {c.valor}{_onde(c)}"
    if _remete(c):
        return (f"**{nome}**: a cláusula existe{_onde(c)}, mas o valor fica na "
                f"especificação da apólice, fora deste documento")
    return f"**{nome}**: não trata do assunto"


def _bloco_campo(a: AnaliseCampo) -> list[str]:
    linhas = [f"#### {a.rotulo}", ""]
    linhas += [f"- {_situacao(n, c)}" for n, c in a.extraidos.items()]
    linhas.append("")
    if a.explicacao:
        linhas += [a.explicacao, ""]
    for e in a.evidencias:
        linhas.append(f'> {e.apolice}: "{e.citacao}"')
    if a.evidencias:
        linhas.append("")
    linhas += [f"*Por que importa:* {a.diferenca.porque_importa}", ""]
    return linhas


def _resumo(r: RelatorioComparativo) -> str:
    so_uma = r.com_veredito(Veredito.AUSENTE_EM_ALGUMA)
    valores = r.com_veredito(Veredito.DIFERENTE)
    conteudo = r.com_leitura(Leitura.DIFERENTE)
    equivalentes = r.com_leitura(Leitura.EQUIVALENTE)
    iguais = r.com_veredito(Veredito.IGUAL)

    partes = []
    if so_uma:
        partes.append(f"{len(so_uma)} campo(s) aparecem só em uma das apólices "
                      f"({', '.join(a.rotulo for a in so_uma)})")
    if valores:
        partes.append(f"{len(valores)} com valores diferentes "
                      f"({', '.join(a.rotulo for a in valores)})")
    if conteudo:
        partes.append(f"{len(conteudo)} cláusula(s) com efeito diferente para o segurado "
                      f"({', '.join(a.rotulo for a in conteudo)})")
    if not partes:
        frase = "Não foi encontrada diferença comprovada entre as apólices nos campos analisados."
    else:
        frase = "As apólices se distinguem em: " + "; ".join(partes) + "."
    equivalentes_total = len(equivalentes) + len(iguais)
    if equivalentes_total:
        frase += f" Em {equivalentes_total} campo(s) as apólices são equivalentes."
    inconclusivos = r.com_leitura(Leitura.INCONCLUSIVO)
    if inconclusivos:
        frase += (f" Em {len(inconclusivos)} a leitura não permitiu afirmar se há "
                  "diferença — vale ler as duas cláusulas.")
    nao_lidas = [a for a in r.com_veredito(Veredito.REDACAO_DIVERGENTE) if a.leitura is None]
    if nao_lidas:
        frase += (f" {len(nao_lidas)} cláusula(s) estão escritas de formas diferentes e "
                  "não foram lidas por um modelo nesta versão: podem esconder diferenças.")
    return frase


def _renderizar(r: RelatorioComparativo) -> str:
    linhas = [f"# Comparação: {' × '.join(r.apolices)}", "", _resumo(r), ""]
    if r.aviso:
        linhas += [f"> **Atenção:** {r.aviso}. As cláusulas de redação divergente "
                   "aparecem sem a leitura do conteúdo.", ""]

    secoes = [
        ("O que só uma das apólices traz", r.com_veredito(Veredito.AUSENTE_EM_ALGUMA)),
        ("Valores diferentes", r.com_veredito(Veredito.DIFERENTE)),
        ("Cláusulas com efeito diferente", r.com_leitura(Leitura.DIFERENTE)),
        ("Escritas de outro jeito, mesmo efeito", r.com_leitura(Leitura.EQUIVALENTE)),
        ("Não foi possível afirmar — vale ler as duas cláusulas",
         r.com_leitura(Leitura.INCONCLUSIVO)
         + [a for a in r.com_veredito(Veredito.REDACAO_DIVERGENTE) if a.leitura is None]),
    ]
    for titulo, analises in secoes:
        if not analises:
            continue
        linhas += [f"## {titulo}", ""]
        for a in analises:
            linhas += _bloco_campo(a)

    iguais = r.com_veredito(Veredito.IGUAL)
    if iguais:
        linhas += ["## Iguais nas apólices", ""]
        for a in iguais:
            valor = next((c.valor for c in a.extraidos.values() if c and c.encontrado), "")
            linhas.append(f"- **{a.rotulo}**: {valor}")
        linhas.append("")

    lacunas = r.com_veredito(Veredito.AUSENTE_EM_TODAS)
    if lacunas:
        linhas += ["## Sem valor em nenhuma das apólices", ""]
        for a in lacunas:
            remetem = [n for n, c in a.extraidos.items() if _remete(c)]
            if len(remetem) == len(a.extraidos):
                situacao = "todas remetem o valor à especificação da apólice"
            elif not remetem:
                situacao = "nenhuma das apólices trata do assunto"
            else:
                outras = [n for n in a.extraidos if n not in remetem]
                situacao = (f"{', '.join(remetem)} remete o valor à especificação; "
                            f"{', '.join(outras)} não traz cláusula localizável")
            linhas.append(f"- **{a.rotulo}**: {situacao}")
        linhas.append("")

    rodape = ("*Diferenças de valor e ausências vêm do motor de comparação, sem modelo de "
              "linguagem. A leitura das redações")
    if r.modelo_usado:
        rodape += (f" foi feita por {r.modelo_usado}, e toda diferença afirmada cita o "
                   "texto das apólices.*")
    else:
        rodape += " não foi feita nesta versão do relatório.*"
    linhas += ["---", rodape, ""]
    return "\n".join(linhas)
