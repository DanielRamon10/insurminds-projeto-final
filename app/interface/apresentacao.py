"""Regras de apresentação da interface — frente D.

Aqui mora *o que* a tela mostra: como cada veredito do motor é chamado, em que
ordem as diferenças aparecem, o que dizer quando um campo não foi encontrado e
como apontar a página de origem de cada valor. *Como* isso é desenhado é
assunto de `app/interface/app.py`, com Streamlit.

A separação não é preciosismo. Um Streamlit só existe durante a execução dele,
o que tornaria intestável justamente a parte que não pode mudar entre a
demonstração e a entrega: se o rótulo de um veredito mudar, o vídeo e o
relatório mentem sobre a mesma tela. Por isso este módulo **não importa
Streamlit** — e é ele que os testes exercitam.

Nada aqui inventa dado: quando o campo não existe, `ValorNaTela.ausente` é
verdadeiro e o texto exibido é explícito, no mesmo espírito da tarefa B.4.
"""

from __future__ import annotations

import csv
import io
import importlib
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

from ..domain.campos import DicionarioCampos, carregar_campos
from ..domain.comparacao import Comparacao, DiferencaCampo, Veredito
from ..domain.exemplos import FONTE_EXEMPLO
from ..schemas import ApoliceExtraida, CampoExtraido

#: O que aparece no lugar de um valor que a apólice não traz. O motor distingue
#: "não trata do assunto" de "campo vazio", e a tela precisa fazer o mesmo —
#: senão a diferença mais relevante da comparação vira um espaço em branco.
TEXTO_AUSENTE = "— não trata do assunto —"

#: Quando o extrator achou o valor mas não conseguiu localizá-lo no documento.
TEXTO_SEM_PAGINA = "página de origem não identificada"

#: Aviso de que o selo "desconhecido" existe: o motor nunca devolve isto, mas a
#: tela não pode quebrar se um veredito novo for acrescentado ao motor.
TEXTO_VEREDITO_DESCONHECIDO = "situação não classificada"


@dataclass(frozen=True)
class EstiloVeredito:
    """Como um veredito do motor aparece para quem lê a tela."""

    rotulo: str
    """Nome curto, do jeito que um corretor falaria."""

    explicacao: str
    """Uma frase dizendo o que aquilo significa — é a legenda da tela."""

    simbolo: str
    """Marca de uma letra, para onde não há cor: CSV, console, relatório."""

    icone: str
    """Ícone do selo."""

    cor: str
    """Cor aceita pelo `st.badge`: blue, green, orange, red, violet, yellow, gray."""

    ordem: int
    """Ordem de leitura: o que mais pesa numa decisão vem primeiro."""


#: Tradução do vocabulário do motor para o vocabulário de quem contrata seguro.
#: Escrever "ausente_em_alguma" na tela seria jogar o nome do enum na cara do
#: usuário; escrever "diferente" para tudo perderia a diferença que mais importa.
ESTILOS: dict[Veredito, EstiloVeredito] = {
    Veredito.AUSENTE_EM_ALGUMA: EstiloVeredito(
        rotulo="Ausente em uma delas",
        explicacao=(
            "Uma apólice trata do assunto e a outra não. Costuma ser a diferença "
            "que mais pesa: não é um valor diferente, é uma proteção que não existe "
            "de um dos lados."
        ),
        simbolo="∅",
        icone="🚫",
        cor="orange",
        ordem=0,
    ),
    Veredito.DIFERENTE: EstiloVeredito(
        rotulo="Valores diferentes",
        explicacao=(
            "As duas apólices tratam do assunto, com valores distintos — limite, "
            "franquia ou prazo que não batem."
        ),
        simbolo="≠",
        icone="⚠️",
        cor="red",
        ordem=1,
    ),
    Veredito.REDACAO_DIVERGENTE: EstiloVeredito(
        rotulo="Redação divergente",
        explicacao=(
            "As duas tratam do assunto, escrito de formas diferentes. O motor não "
            "afirma se o conteúdo é equivalente — isso exige leitura, e é o que o "
            "relatório (C.4) faz."
        ),
        simbolo="≈",
        icone="🔎",
        cor="violet",
        ordem=2,
    ),
    Veredito.IGUAL: EstiloVeredito(
        rotulo="Igual nas duas",
        explicacao=(
            "Mesmo valor nas duas apólices, ainda que escrito de outro jeito — "
            "`R$ 10.000.000,00` e `R$ 10 milhões` não são uma diferença."
        ),
        simbolo="=",
        icone="✅",
        cor="green",
        ordem=3,
    ),
    Veredito.AUSENTE_EM_TODAS: EstiloVeredito(
        rotulo="Fora das duas",
        explicacao=(
            "Nenhuma das apólices trata do assunto. Não é diferença entre elas, é "
            "lacuna das duas — e some se o campo ausente for tratado como vazio."
        ),
        simbolo="—",
        icone="➖",
        cor="gray",
        ordem=4,
    ),
}


def estilo(veredito: Veredito) -> EstiloVeredito:
    """O estilo do veredito, ou um estilo neutro se o motor ganhar um novo."""
    return ESTILOS.get(
        veredito,
        EstiloVeredito(
            rotulo=TEXTO_VEREDITO_DESCONHECIDO,
            explicacao="Situação que esta versão da interface ainda não conhece.",
            simbolo="?",
            icone="❔",
            cor="gray",
            ordem=99,
        ),
    )


def legenda() -> tuple[EstiloVeredito, ...]:
    """Os estilos em ordem de leitura, para a legenda da tela."""
    return tuple(ESTILOS[v] for v in sorted(ESTILOS, key=lambda v: ESTILOS[v].ordem))


#: As situações que o filtro da barra lateral oferece — só o que distingue as
#: apólices. O que é igual nas duas e o que está fora das duas entra pelo botão
#: "incluir o que é igual", nunca pelo filtro: duas alavancas sobre a mesma
#: coisa brigavam entre si (a auditoria da frente D pegou o caso, com o botão
#: ligado mostrando os mesmos 11 cartões).
SITUACOES_NO_FILTRO: tuple[Veredito, ...] = (
    Veredito.AUSENTE_EM_ALGUMA,
    Veredito.DIFERENTE,
    Veredito.REDACAO_DIVERGENTE,
)


def sigla(veredito: Veredito) -> str:
    """O símbolo do veredito em uma letra — usado no CSV e na demonstração."""
    return estilo(veredito).simbolo


def formatar_pagina(
    pagina: int | None, paginas_possiveis: Iterable[int] = ()
) -> str:
    """Como a origem é citada na tela: `página 12`, e as ocorrências repetidas.

    O motor já avisa quando o mesmo trecho aparece em várias páginas — sinal de
    cláusula padrão repetida no documento. Esconder isso do leitor daria à
    citação uma precisão que ela não tem.
    """
    outras = [p for p in paginas_possiveis if p != pagina]

    if pagina is None:
        if not outras:
            return TEXTO_SEM_PAGINA
        return "páginas " + ", ".join(str(p) for p in outras)

    texto = f"página {pagina}"
    if outras:
        texto += " (o trecho se repete em " + ", ".join(str(p) for p in outras) + ")"
    return texto


# ---------------------------------------------------------------------------
# O que a tela mostra de cada campo em cada apólice
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValorNaTela:
    """O valor de um campo numa apólice, já pronto para ser exibido.

    Guarda o `CampoExtraido` inteiro, e não só a string, porque a rastreabilidade
    (D.3) precisa da página, do trecho e da ressalva do extrator — perder isso na
    hora de montar a tela esvaziaria a tarefa B.3 na última etapa do caminho.
    """

    apolice: str
    campo: CampoExtraido | None

    @property
    def ausente(self) -> bool:
        """Se esta apólice não trata do assunto."""
        return self.campo is None or not self.campo.encontrado

    @property
    def texto(self) -> str:
        """O valor como aparece na tela, ou o texto explícito de ausência."""
        if self.campo is None or self.campo.valor is None:
            return TEXTO_AUSENTE
        return self.campo.valor.strip() or TEXTO_AUSENTE

    @property
    def pagina(self) -> int | None:
        return self.campo.pagina if self.campo else None

    @property
    def paginas_possiveis(self) -> tuple[int, ...]:
        return tuple(self.campo.paginas_possiveis) if self.campo else ()

    @property
    def trecho(self) -> str | None:
        return self.campo.trecho_origem if self.campo else None

    @property
    def observacao(self) -> str | None:
        """Ressalva escrita pelo extrator, quando houver."""
        return self.campo.observacao if self.campo else None

    @property
    def rastreavel(self) -> bool:
        """Se dá para apontar a página e o trecho de onde o valor saiu."""
        return bool(self.campo and self.campo.rastreavel)

    @property
    def ancoragem(self) -> str:
        """A citação de origem, do jeito que aparece abaixo do valor."""
        return formatar_pagina(self.pagina, self.paginas_possiveis)


@dataclass(frozen=True)
class CartaoDiferenca:
    """Uma diferença como a tela a apresenta: o campo e o valor em cada apólice."""

    diferenca: DiferencaCampo
    valores: tuple[ValorNaTela, ...]

    @property
    def campo_id(self) -> str:
        return self.diferenca.campo.id

    @property
    def rotulo(self) -> str:
        return self.diferenca.campo.rotulo

    @property
    def significado(self) -> str:
        """O que o especialista diz que este campo é."""
        return self.diferenca.campo.significado

    @property
    def porque_importa(self) -> str:
        """Por que esta diferença interessa a quem vai contratar."""
        return self.diferenca.porque_importa

    @property
    def veredito(self) -> Veredito:
        return self.diferenca.veredito

    @property
    def estilo(self) -> EstiloVeredito:
        return estilo(self.diferenca.veredito)

    @property
    def relevante(self) -> bool:
        return self.diferenca.relevante

    @property
    def ausentes(self) -> tuple[str, ...]:
        """Quais apólices não tratam deste assunto."""
        return tuple(v.apolice for v in self.valores if v.ausente)


def montar_cartoes(
    comparacao: Comparacao,
    apolices: Sequence[ApoliceExtraida],
    apenas_relevantes: bool = True,
) -> tuple[CartaoDiferenca, ...]:
    """Junta o que o motor decidiu com o que cada apólice guardou de origem.

    O `DiferencaCampo` traz valores e páginas, mas não o trecho de origem: isso
    mora na apólice. É aqui que os dois se encontram, e é o que permite o D.3 —
    `d.paginas` para chegar à página, `apolice.campo(id)` para chegar ao trecho.

    Os cartões saem ordenados como a tela os mostra: a importância do veredito
    primeiro, o rótulo do campo depois. É o que garante que a tela e a
    demonstração por linha de comando listem na mesma ordem.
    """
    por_nome = {a.nome: a for a in apolices}
    diferencas = sorted(
        comparacao.relevantes if apenas_relevantes else comparacao.diferencas,
        key=lambda d: (estilo(d.veredito).ordem, d.campo.rotulo),
    )

    return tuple(
        CartaoDiferenca(
            diferenca=d,
            valores=tuple(
                ValorNaTela(apolice=nome, campo=_campo_de(por_nome.get(nome), d))
                for nome in comparacao.apolices
            ),
        )
        for d in diferencas
    )


def _campo_de(
    apolice: ApoliceExtraida | None, diferenca: DiferencaCampo
) -> CampoExtraido | None:
    """O campo desta apólice, ou `None` se a apólice não foi carregada."""
    return apolice.campo(diferenca.campo.id) if apolice else None


# ---------------------------------------------------------------------------
# Números do topo da tela
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Kpi:
    """Um número grande do topo, com a frase que explica o que ele conta."""

    rotulo: str
    valor: int
    ajuda: str
    icone: str
    cor: str


def montar_kpis(comparacao: Comparacao) -> tuple[Kpi, ...]:
    """Os cinco números que resumem a comparação.

    São derivados do `Comparacao.resumo` do motor — a interface não recalcula
    nada por conta própria. Se a contagem aparecesse diferente na tela e no
    relatório, o problema seria de quem contou duas vezes.
    """
    resumo = comparacao.resumo
    return (
        Kpi(
            rotulo="Campos comparados",
            valor=len(comparacao.diferencas),
            ajuda="Todos os campos do dicionário do especialista, apólice por apólice.",
            icone="📋",
            cor="blue",
        ),
        Kpi(
            rotulo="Ausentes em uma delas",
            valor=resumo[Veredito.AUSENTE_EM_ALGUMA.value],
            ajuda="Proteção que existe numa apólice e não aparece na outra.",
            icone="🚫",
            cor="orange",
        ),
        Kpi(
            rotulo="Valores diferentes",
            valor=resumo[Veredito.DIFERENTE.value],
            ajuda="Limite, franquia ou prazo que não batem entre as apólices.",
            icone="⚠️",
            cor="red",
        ),
        Kpi(
            rotulo="Redação divergente",
            valor=resumo[Veredito.REDACAO_DIVERGENTE.value],
            ajuda="As duas tratam do assunto com palavras diferentes: exige leitura.",
            icone="🔎",
            cor="violet",
        ),
        Kpi(
            rotulo="Iguais nas duas",
            valor=resumo[Veredito.IGUAL.value],
            ajuda="Mesmo valor nas duas, mesmo escrito de outro jeito.",
            icone="✅",
            cor="green",
        ),
    )


# ---------------------------------------------------------------------------
# Tabelas: a visão completa e a prova de origem
# ---------------------------------------------------------------------------


def matriz_comparativa(
    comparacao: Comparacao, apenas_relevantes: bool = False
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    """A comparação inteira em formato de tabela, para o `st.dataframe`.

    Devolve `(colunas, linhas)` em vez de um DataFrame para não arrastar pandas
    para dentro do módulo que os testes exercitam.
    """
    colunas = ("Campo", *comparacao.apolices, "Situação")
    diferencas = comparacao.relevantes if apenas_relevantes else comparacao.diferencas

    linhas: list[dict[str, Any]] = []
    for d in diferencas:
        linha: dict[str, Any] = {"Campo": d.campo.rotulo}
        for nome in comparacao.apolices:
            valor = d.valores.get(nome)
            linha[nome] = valor.strip() if valor else TEXTO_AUSENTE
        linha["Situação"] = estilo(d.veredito).rotulo
        linhas.append(linha)

    return colunas, tuple(linhas)


def linhas_rastreabilidade(
    comparacao: Comparacao,
    apolices: Sequence[ApoliceExtraida],
    apenas_encontrados: bool = True,
) -> tuple[dict[str, Any], ...]:
    """Uma linha por (campo, apólice) mostrando de onde o valor saiu — o D.3.

    `apenas_encontrados=False` inclui também o que não foi encontrado, o que é
    útil para conferir se a ausência é real ou se o extrator não deu conta.
    """
    por_nome = {a.nome: a for a in apolices}

    linhas: list[dict[str, Any]] = []
    for d in comparacao.diferencas:
        for nome in comparacao.apolices:
            campo = _campo_de(por_nome.get(nome), d)
            encontrado = bool(campo and campo.encontrado)
            if apenas_encontrados and not encontrado:
                continue
            linhas.append(
                {
                    "Campo": d.campo.rotulo,
                    "Apólice": nome,
                    "Valor": (
                        campo.valor.strip()
                        if campo and campo.encontrado and campo.valor
                        else TEXTO_AUSENTE
                    ),
                    "Página": campo.pagina if campo else None,
                    "Trecho de origem": (campo.trecho_origem or "") if campo else "",
                    "Confere": "sim" if (campo and campo.rastreavel) else "não",
                }
            )
    return tuple(linhas)


def exportar_csv(comparacao: Comparacao, apenas_relevantes: bool = False) -> str:
    """A comparação em CSV, pronta para o `st.download_button`.

    Separador `;` e BOM porque quem recebe isto abre no Excel em português — e
    um CSV de cláusulas com acento quebrado é pior que nenhum CSV.
    """
    colunas, linhas = matriz_comparativa(comparacao, apenas_relevantes)
    buffer = io.StringIO()
    escritor = csv.DictWriter(
        buffer, fieldnames=list(colunas), delimiter=";", lineterminator="\n"
    )
    escritor.writeheader()
    escritor.writerows(linhas)
    return "\ufeff" + buffer.getvalue()


def nome_arquivo_csv(comparacao: Comparacao) -> str:
    """Nome de arquivo sem acento nem espaço, com as apólices comparadas."""
    partes = "-x-".join(_slug(n) for n in comparacao.apolices)
    return f"comparacao_{partes}.csv"


def _slug(texto: str) -> str:
    """Versão simples de um nome para caber em nome de arquivo."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return "".join(c if c.isalnum() else "_" for c in sem_acento.lower()).strip("_")


# ---------------------------------------------------------------------------
# Cartões das apólices carregadas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResumoApolice:
    """O que a tela mostra de uma apólice guardada."""

    nome: str
    documento: str
    modelo_usado: str
    encontrados: int
    total: int
    rastreaveis: int

    @property
    def fracao_encontrada(self) -> float:
        """Fração do dicionário que esta apólice responde — para a barra de progresso."""
        return self.encontrados / self.total if self.total else 0.0

    @property
    def veio_de_exemplo(self) -> bool:
        """Se estes campos foram escritos à mão em vez de extraídos pelo modelo."""
        return self.modelo_usado == FONTE_EXEMPLO

    @property
    def fonte(self) -> str:
        """Como a origem da extração é declarada na tela e no relatório."""
        if self.veio_de_exemplo:
            return "extração de exemplo (sem LLM)"
        return f"extraída por {self.modelo_usado or 'modelo não informado'}"

    @property
    def todas_rastreaveis(self) -> bool:
        return self.encontrados > 0 and self.rastreaveis == self.encontrados


def resumir_apolice(
    apolice: ApoliceExtraida, dicionario: DicionarioCampos | None = None
) -> ResumoApolice:
    """Resume uma apólice para o cartão da aba "Apólices".

    `total` vem do dicionário, e não da quantidade de campos que a extração
    trouxe: é o que permite dizer "9 de 15" em vez de "9 de 9", que faria uma
    extração incompleta parecer completa.
    """
    dicionario = dicionario or carregar_campos()
    return ResumoApolice(
        nome=apolice.nome,
        documento=apolice.documento,
        modelo_usado=apolice.modelo_usado or "",
        encontrados=apolice.encontrados,
        total=len(dicionario),
        rastreaveis=apolice.rastreaveis,
    )


def usando_exemplos(apolices: Sequence[ApoliceExtraida]) -> bool:
    """Se alguma das apólices comparadas veio das extrações de exemplo."""
    return any((a.modelo_usado or "") == FONTE_EXEMPLO for a in apolices)


# ---------------------------------------------------------------------------
# Ponte para a frente B
# ---------------------------------------------------------------------------

#: Nomes aceitos para a função de extração da frente B. A interface procura por
#: todos, nesta ordem, e passa a usar o primeiro que aparecer em `app.agents`.
NOMES_EXTRATOR = ("extrair_apolice", "extrair_apolices", "extrair", "extrair_campos")

MODULO_EXTRACAO = "app.agents"


def encontrar_extrator(modulo: object | None) -> Callable[..., Any] | None:
    """Acha, num módulo, a função que transforma texto em campos.

    O contrato combinado com a frente B: ela publica em `app.agents` uma função
    que recebe um `DocumentoExtraido` e devolve uma `ApoliceExtraida`. Enquanto
    não houver nenhuma, a tela diz que a extração está em desenvolvimento — em
    vez de mostrar campo vazio como se a apólice não tratasse do assunto, que
    seria a mentira mais cara possível neste projeto.
    """
    if modulo is None:
        return None
    for nome in NOMES_EXTRATOR:
        funcao = getattr(modulo, nome, None)
        if callable(funcao):
            return funcao
    return None


def carregar_modulo_extracao(nome: str = MODULO_EXTRACAO) -> object | None:
    """Importa o módulo da frente B, ou devolve `None` se ele ainda não existe."""
    try:
        return importlib.import_module(nome)
    except ImportError:
        return None


def aviso_sem_extracao() -> str:
    """A frase que explica, na tela, por que os campos ainda não saem do LLM."""
    return (
        "**A extração das cláusulas ainda não está pronta (frente B, tarefas B.2 a B.4).**\n\n"
        "A ingestão é real: o documento foi lido, página a página, e o que aparece acima "
        "saiu dele. O que falta é a etapa que transforma esse texto nos campos "
        "estruturados — e é ela que vai publicar a função de extração em `app.agents`. "
        "Enquanto isso, a comparação da aba *Comparação* roda sobre as extrações de "
        "exemplo de `app/domain/exemplos.py`, identificadas como tal em cada tela."
    )
