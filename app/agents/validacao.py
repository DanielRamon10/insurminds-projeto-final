"""Validação da extração — tarefas B.3 (rastreabilidade) e B.4 (null explícito).

O modelo propõe; o documento decide. Nada do que o LLM responde é aceito sem ser
conferido contra o texto da apólice:

* **a citação tem de existir.** Se o trecho que o modelo diz ter lido não está em
  página nenhuma, a citação foi inventada — e um valor apoiado numa citação
  inventada é descartado, não "aproveitado com ressalva";
* **a página é nossa, não do modelo.** Ela vem de onde o trecho foi encontrado; a
  página que o modelo informou só desempata quando o trecho aparece em mais de uma;
* **cabeçalho não é origem.** Trecho que se repete em mais de três páginas é
  cabeçalho ou rodapé: o valor fica, mas o campo deixa de contar como rastreável;
* **número do valor tem de estar no trecho.** É o guardrail do Desafio 5 — lá o
  modelo não podia citar número que a previsão não tinha; aqui não pode apresentar
  um limite de indenização que a cláusula citada não traz;
* **campo ausente é `null`**, com o motivo na observação. Nunca um valor genérico.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from ..domain.campos import Campo, DicionarioCampos
from ..schemas import CampoExtraido, DocumentoExtraido

log = logging.getLogger(__name__)

#: Acima disto o trecho é boilerplate. Mesmo limiar de `DocumentoExtraido.pagina_de`.
MAXIMO_PAGINAS_ORIGEM = 3

#: Trechos mais curtos que isto acham-se em qualquer lugar e não provam nada.
MINIMO_PALAVRAS_TRECHO = 4

#: Respostas que alguns modelos dão em vez de `null`.
_VAZIOS = {
    "", "null", "none", "n/a", "na", "-", "nao encontrado", "nao consta",
    "nao informado", "nao se aplica", "nao ha",
}

_RE_RETICENCIAS = re.compile(r"\[?(?:\.\.\.|…)\]?")
_RE_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")

_ESCALAS = {
    "mil": 1e3,
    "milhao": 1e6, "milhoes": 1e6, "mi": 1e6,
    "bilhao": 1e9, "bilhoes": 1e9, "bi": 1e9,
}

#: Cláusula jurídica escreve prazo por extenso — "30 (trinta) dias", às vezes só
#: "trinta dias". Sem isto, "30 dias" no valor seria tomado por número inventado.
_EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
    "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40, "quarenta e cinco": 45,
    "sessenta": 60, "noventa": 90, "cento e vinte": 120, "cento e oitenta": 180,
    "trezentos e sessenta e cinco": 365,
}


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _chave_busca(texto: str) -> str:
    """Forma do texto usada para achar uma citação.

    Mais tolerante que `schemas._normalizar`: além de acento, caixa e espaço,
    ignora pontuação e junta a palavra hifenizada na quebra de linha ("inde-
    nização"), porque o modelo cita a palavra inteira e o PDF guarda a partida.
    """
    t = _sem_acento(texto).lower()
    t = re.sub(r"-\s+", "", t)
    t = re.sub(r"[^\w]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _limpar(valor) -> str | None:
    """Texto útil, ou `None` para as várias formas de "não achei"."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if _chave_busca(texto) in _VAZIOS:
        return None
    return texto


def _pagina_informada(valor) -> int | None:
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return numero if numero >= 1 else None


# ---------------------------------------------------------------------------
# B.3 — onde está o trecho
# ---------------------------------------------------------------------------


def _molde_linha(linha: str) -> str:
    """A linha sem os números: "Página 9 de 70" e "Página 10 de 70" são o mesmo rodapé."""
    return re.sub(r"\d+", "#", _chave_busca(linha))


def _linhas_repetidas(documento: DocumentoExtraido) -> set[str]:
    """Moldes de linha presentes em mais de `MAXIMO_PAGINAS_ORIGEM` páginas."""
    contagem: dict[str, int] = {}
    for p in documento.paginas:
        for molde in {_molde_linha(l) for l in p.texto.splitlines()}:
            if molde:
                contagem[molde] = contagem.get(molde, 0) + 1
    return {m for m, n in contagem.items() if n > MAXIMO_PAGINAS_ORIGEM}


class Localizador:
    """Acha em que páginas do documento um trecho citado aparece.

    Normaliza cada página uma vez só: são 15 campos contra 70 páginas por apólice.
    """

    def __init__(self, documento: DocumentoExtraido) -> None:
        self.documento = documento
        self._paginas = [(p.numero, _chave_busca(p.texto)) for p in documento.paginas]

        # Cláusula que começa no pé de uma página e termina no topo da seguinte:
        # o modelo cita por cima da quebra — pulando o rodapé "Página 10 de 70"
        # que fica no meio —, e página nenhuma contém o trecho inteiro. Foi o que
        # aconteceu com a definição de Segurado da Chubb. Na junção, as linhas
        # repetidas (cabeçalho e rodapé) saem.
        repetidas = _linhas_repetidas(documento)
        limpas = [
            _chave_busca("\n".join(
                linha for linha in p.texto.splitlines()
                if _molde_linha(linha) not in repetidas
            ))
            for p in documento.paginas
        ]
        self._viradas = [
            (p.numero, f"{t1} {t2}")
            for p, t1, t2 in zip(documento.paginas, limpas, limpas[1:])
        ]

    def _onde(self, trecho: str) -> set[int]:
        alvo = _chave_busca(trecho)
        if not alvo:
            return set()
        achadas = {numero for numero, texto in self._paginas if alvo in texto}
        if achadas:
            return achadas
        # a origem é a página onde o trecho começa
        return {numero for numero, texto in self._viradas if alvo in texto}

    def paginas(self, trecho: str) -> list[int]:
        """Páginas onde o trecho aparece, em ordem. Vazia se não aparecer.

        O modelo às vezes encurta a citação com reticências mesmo sendo pedido que
        não o faça. Nesse caso cada pedaço tem de estar no documento, e todos na
        mesma página — pedaços espalhados não formam uma citação.
        """
        pedacos = [p for p in _RE_RETICENCIAS.split(trecho) if p.strip()]
        if len(pedacos) > 1:
            pedacos = [p for p in pedacos if len(p.split()) >= MINIMO_PALAVRAS_TRECHO]
            if not pedacos:
                return []
            comuns = set.intersection(*(self._onde(p) for p in pedacos))
            return sorted(comuns)
        return sorted(self._onde(trecho))

    def contem(self, texto: str) -> bool:
        """Se o texto aparece em alguma página — para validar o nome da seguradora."""
        return bool(self._onde(texto))


# ---------------------------------------------------------------------------
# Guardrail numérico
# ---------------------------------------------------------------------------


def _ocorrencias(texto: str) -> list[tuple[str, set[float]]]:
    """Cada número escrito no texto, com as leituras possíveis dele.

    `10 milhões` rende {10, 10.000.000}: a grandeza, para bater com
    `R$ 10.000.000,00`, e o número cru, para bater com "10 (dez) milhões".
    """
    limpo = _sem_acento(texto).lower()
    resultado = []
    for m in _RE_NUMERO.finditer(limpo):
        bruto = m.group()
        if "," in bruto:  # pt-BR: ponto separa milhar, vírgula separa decimal
            convertido = bruto.replace(".", "").replace(",", ".")
        else:
            convertido = bruto.replace(".", "")
        try:
            numero = float(convertido)
        except ValueError:
            continue

        leituras = {numero}
        depois = limpo[m.end():m.end() + 12]
        for palavra, fator in _ESCALAS.items():
            if re.match(rf"\s*{palavra}\b", depois):
                leituras.add(numero * fator)
                break
        resultado.append((bruto, leituras))
    return resultado


def numeros(texto: str) -> set[float]:
    """Todos os números que um texto afirma, em algarismo ou por extenso."""
    limpo = _sem_acento(texto).lower()
    achados = set().union(*(leituras for _, leituras in _ocorrencias(texto)))
    for palavra, numero in _EXTENSO.items():
        if re.search(rf"\b{palavra}\b", limpo):
            achados.add(float(numero))
    return achados


def numeros_sem_apoio(valor: str, trecho: str) -> list[str]:
    """Números do valor que o trecho citado não traz — cada um, uma alucinação."""
    no_trecho = numeros(trecho)
    return [bruto for bruto, leituras in _ocorrencias(valor) if not leituras & no_trecho]


# ---------------------------------------------------------------------------
# Validação de um campo
# ---------------------------------------------------------------------------


_RE_REMISSAO = re.compile(
    r"\b(especificacao|frontispicio|proposta de seguro|conforme (a )?apolice)\b"
)


def _so_remete(valor: str) -> bool:
    """Se o "valor" só diz que o valor está em outro documento.

    Condições gerais deixam limite, franquia e datas para a especificação da
    apólice. O prompt pede `null` nesse caso, mas o modelo nem sempre obedece.
    Valor curto, sem número e que cita a especificação é remissão, não conteúdo.
    """
    chave = _chave_busca(valor)
    return (
        bool(_RE_REMISSAO.search(chave))
        and not _RE_NUMERO.search(chave)
        and len(chave.split()) <= 12
    )


def _resumo(trecho: str, palavras: int = 12) -> str:
    partes = trecho.split()
    return " ".join(partes[:palavras]) + (" ..." if len(partes) > palavras else "")


def validar_campo(
    campo: Campo, bruto: dict | None, localizador: Localizador
) -> CampoExtraido:
    """Transforma a resposta do modelo para um campo num `CampoExtraido` conferido."""
    if not isinstance(bruto, dict):
        return CampoExtraido(
            campo_id=campo.id, observacao="o modelo nao devolveu este campo"
        )

    valor = _limpar(bruto.get("valor"))
    trecho = _limpar(bruto.get("trecho") or bruto.get("trecho_origem"))
    pagina_modelo = _pagina_informada(bruto.get("pagina"))
    notas = [n for n in [_limpar(bruto.get("observacao"))] if n]

    def resultado(**kw) -> CampoExtraido:
        return CampoExtraido(
            campo_id=campo.id, observacao="; ".join(notas) or None, **kw
        )

    # B.4: sem citação não há como provar o valor
    if trecho is None:
        if valor is not None:
            notas.append("valor sem citacao do documento: descartado")
            log.info("%s: valor sem trecho descartado (%r)", campo.id, valor)
        return resultado()

    if len(trecho.split()) < MINIMO_PALAVRAS_TRECHO:
        notas.append(f"citacao curta demais para provar origem ({trecho!r})")
        return resultado()

    # B.3: a página vem do documento, não do modelo
    paginas = localizador.paginas(trecho)
    if not paginas:
        notas.append(
            f'citacao nao encontrada no documento ("{_resumo(trecho)}")'
            + (": valor descartado" if valor else "")
        )
        log.info("%s: citacao nao localizada, valor %r descartado", campo.id, valor)
        return resultado()

    if len(paginas) > MAXIMO_PAGINAS_ORIGEM:
        pagina = None
        notas.append(
            f"trecho repetido em {len(paginas)} paginas (cabecalho/rodape): "
            "nao serve como prova de origem"
        )
    elif pagina_modelo in paginas:
        pagina = pagina_modelo
    else:
        pagina = paginas[0]
        if pagina_modelo is not None:
            notas.append(f"pagina informada pelo modelo ({pagina_modelo}) corrigida para {pagina}")

    # "Definido na especificação" não é valor: comparado com a mesma frase da outra
    # apólice, faria a frente C declarar iguais dois campos que nem têm número.
    if valor is not None and _so_remete(valor):
        notas.append("valor definido na especificacao da apolice, fora deste documento")
        valor = None

    # guardrail numérico: todo número do valor tem de estar na citação
    if valor is not None:
        faltando = numeros_sem_apoio(valor, trecho)
        if faltando:
            notas.append(
                f"numero(s) {', '.join(faltando)} do valor nao aparecem no trecho citado: "
                "valor descartado"
            )
            log.info("%s: numeros sem apoio %s, valor %r descartado", campo.id, faltando, valor)
            valor = None

    return resultado(
        valor=valor, trecho_origem=trecho, pagina=pagina, paginas_possiveis=paginas
    )


def validar_campos(
    brutos: dict, dicionario: DicionarioCampos, documento: DocumentoExtraido
) -> list[CampoExtraido]:
    """Um `CampoExtraido` para cada campo do dicionário, na ordem do dicionário.

    Campo que o modelo esqueceu vira `null` explícito; campo que ele inventou fora
    do dicionário é ignorado — quem decide o que se procura é o especialista.
    """
    localizador = Localizador(documento)
    extras = set(brutos) - set(dicionario.ids)
    if extras:
        log.info("campos fora do dicionario ignorados: %s", ", ".join(sorted(extras)))
    return [validar_campo(c, brutos.get(c.id), localizador) for c in dicionario]
