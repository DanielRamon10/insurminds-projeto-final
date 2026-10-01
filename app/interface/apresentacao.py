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
verdadeiro e o texto exibido é explícito, no mesmo espírito da tarefa B.4. E
quando a cláusula existe mas o valor não está no documento — o caso das condições
gerais de D&O, que remetem o número à Especificação da Apólice —, a tela mostra a
ressalva do extrator em vez de afirmar que a apólice não trata do assunto.
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

#: Quando a cláusula existe mas o número não está no documento comparado.
#:
#: Não é ausência: as condições gerais de D&O definem franquia, LMI, vigência e
#: retroatividade como "o valor indicado na Especificação da Apólice" — e é a
#: especificação, não as condições gerais, que traz o número. Escrever "não trata
#: do assunto" ali seria afirmar o contrário do que o documento diz.
TEXTO_SEM_VALOR = "— valor não está neste documento —"

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


# ---------------------------------------------------------------------------
# Identidade visual: ícone de cada campo e cor de cada seguradora
# ---------------------------------------------------------------------------


#: Um ícone por campo do dicionário, com o nome que a fonte "Material Symbols
#: Rounded" usa como ligadura. A fonte não é baixada por nós: o próprio
#: Streamlit já a carrega para desenhar os ícones dele (`theme.iconFont`), e o
#: nome é o texto que ela converte em desenho. Usar a mesma fonte evita mais um
#: pedido de rede e mantém o traço igual ao dos componentes nativos.
#:
#: A armadilha, que já custou uma correção nesta frente: se alguma regra de
#: `font-family` alcançar o span do ícone, a ligadura não acontece e o navegador
#: pinta o NOME por extenso — foi o "De expand_more" que a tela mostrava. O
#: teste `test_a_fonte_do_texto_nao_alcanca_os_icones` protege isso.
ICONE_DO_CAMPO: dict[str, str] = {
    "limite_maximo_indenizacao": "payments",
    "franquia": "receipt_long",
    "vigencia": "event_available",
    "retroatividade": "history",
    "prazo_complementar": "hourglass_bottom",
    "ambito_geografico": "public",
    "definicao_segurado": "badge",
    "custos_defesa": "gavel",
    "multas_administrativas": "request_quote",
    "exclusao_atos_dolosos": "block",
    "exclusao_ambiental": "eco",
    "clausula_rescisao": "cancel_schedule_send",
    "definicao_reclamacao": "campaign",
    "sublimites": "stacked_bar_chart",
    "cobertura_investigacoes": "search",
}

#: Ícone de quem não está no mapa — um campo novo no dicionário não deve
#: derrubar a tela nem sair sem ícone.
ICONE_DE_CAMPO_DESCONHECIDO = "description"


def icone_do_campo(campo_id: str) -> str:
    """O nome do ícone do campo, ou o genérico se o campo for novo."""
    return ICONE_DO_CAMPO.get(campo_id, ICONE_DE_CAMPO_DESCONHECIDO)


#: Cor de acento por seguradora. Não é a cor da marca — é uma cor de leitura,
#: para o olho achar a coluna sem ler o rótulo. As marcas conhecidas ficam
#: fixas para não mudarem de cor entre execuções; o resto cai num tom estável
#: derivado do próprio nome, que é o que garante que a mesma apólice apareça
#: sempre com a mesma cor.
CORES_DE_SEGURADORA: dict[str, str] = {
    "aig": "#185FA5",
    "chubb": "#2C2C2A",
    "tokio": "#0F6E56",
    "allianz": "#185FA5",
    "zurich": "#185FA5",
    "axa": "#7C3AED",
    "porto": "#993C1D",
    "sulamerica": "#185FA5",
    "liberty": "#993556",
    "mapfre": "#993C1D",
    "hdi": "#0F6E56",
}

#: Paleta de reserva, toda de tons escuros o bastante para carregar texto
#: branco por cima. A ordem é fixa: o mesmo nome sempre cai no mesmo tom.
PALETA_DE_RESERVA: tuple[str, ...] = (
    "#185FA5", "#0F6E56", "#7C3AED", "#993C1D",
    "#993556", "#854F0B", "#2C2C2A", "#3B6D11",
)


def cor_da_seguradora(nome: str) -> str:
    """Uma cor estável para a seguradora, para distinguir as colunas na tela.

    A marca conhecida tem cor fixa; qualquer outra cai num tom derivado do
    nome. É determinístico de propósito: se a cor mudasse entre execuções, a
    coluna da AIG mudaria de cor no meio de uma apresentação.
    """
    chave = nome.strip().lower()
    for marca, cor in CORES_DE_SEGURADORA.items():
        if marca in chave:
            return cor
    # `hash()` do Python varia a cada processo (PYTHONHASHSEED), então não
    # serve aqui. A soma dos caracteres é estável entre execuções.
    soma = sum(ord(c) for c in chave) if chave else 0
    return PALETA_DE_RESERVA[soma % len(PALETA_DE_RESERVA)]


#: Palavras que aparecem no nome registrado e não identificam a marca. Sem
#: descartá-las, "AIG Seguros Brasil S.A." viraria o chip "ASB" — as iniciais do
#: nome da empresa, não da seguradora que o corretor reconhece.
PALAVRAS_QUE_NAO_SAO_A_MARCA: frozenset[str] = frozenset({
    "sa", "ltda", "cia", "companhia", "seguros", "seguradora", "brasil",
    "do", "da", "de", "e", "group", "grupo", "holding", "gerais", "minas",
})


def iniciais_da_seguradora(nome: str) -> str:
    """As iniciais para o chip: "AIG Seguros Brasil S.A." vira "AIG".

    Duas regras, porque os dois formatos que aparecem no projeto são diferentes:
    a razão social longa ("AIG Seguros Brasil S.A.") pede que se descarte o
    juridiquês e fique com a marca; o nome curto ("Chubb") já é a marca, e
    cortá-lo em três letras daria um chip que não se lê.
    """
    # O ponto vira espaço antes do split, e o "S.A." se desfaz em duas letras
    # soltas — que não são palavras e por isso saem junto com o juridiquês.
    palavras = [p for p in nome.replace(".", " ").split() if p[:1].isalpha() and len(p) > 1]
    marca = [p for p in palavras if p.lower() not in PALAVRAS_QUE_NAO_SAO_A_MARCA]
    if not marca:
        marca = palavras
    if not marca:
        return "??"

    if len(marca) == 1:
        unica = marca[0]
        # Sigla já vem pronta ("AIG", "AXA"); nome comum vira duas letras.
        if unica.isupper() and len(unica) <= 4:
            return unica
        return unica[:2].upper()

    return "".join(p[0] for p in marca[:3]).upper()


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
    def sem_valor_no_documento(self) -> bool:
        """A cláusula existe, mas o valor não está neste documento.

        Reconhecido pela prova que o extrator deixou: a ressalva escrita ("o valor
        é definido na Especificação da Apólice") ou o trecho de origem. Sem
        nenhuma das duas não há como distinguir isto de ausência de verdade, e a
        tela não deve inventar a distinção — daí o teste pelas duas.
        """
        if self.campo is None or self.campo.encontrado:
            return False
        return bool(self.campo.observacao or self.campo.trecho_origem)

    @property
    def ausente(self) -> bool:
        """Se esta apólice não trata do assunto.

        Faltar o valor não basta. Quando o extrator achou a cláusula e registrou
        por que não há número, o documento **trata** do assunto — e era o
        contrário disso que a tela dizia, descartando junto a página e o trecho
        que a extração tinha registrado.
        """
        if self.campo is not None and self.campo.encontrado:
            return False
        return not self.sem_valor_no_documento

    @property
    def texto(self) -> str:
        """O valor como aparece na tela, ou o texto explícito de ausência.

        São três casos, e não dois: valor encontrado; campo que a apólice não
        trata; e cláusula presente cujo número está em outro documento — neste
        último, o que se mostra é a ressalva do extrator.
        """
        if self.campo is None:
            return TEXTO_AUSENTE
        if self.campo.encontrado:
            return self.campo.valor.strip()
        if self.sem_valor_no_documento:
            return (self.campo.observacao or "").strip() or TEXTO_SEM_VALOR
        return TEXTO_AUSENTE

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


@dataclass(frozen=True)
class FatiaDaComposicao:
    """Um pedaço da barra que mostra a situação de cada campo."""

    rotulo: str
    """Como a fatia é nomeada na legenda."""

    quantidade: int
    """Quantos campos caíram nesta situação."""

    cor: str
    """Cor sólida da fatia, no mesmo tom do selo do cartão."""

    simbolo: str
    """A marca de uma letra, para quem não vê a cor."""


#: A cor de cada fatia, no mesmo tom que o selo usa. Manter aqui — e não no CSS
#: — é o que permite a fatia e o selo nunca discordarem: os dois saem do mesmo
#: mapa, e o teste confere que todo veredito do motor tem entrada.
CORES_DA_COMPOSICAO: dict[Veredito, str] = {
    Veredito.AUSENTE_EM_ALGUMA: "#F59E0B",
    Veredito.DIFERENTE: "#DC2626",
    Veredito.REDACAO_DIVERGENTE: "#7C3AED",
    Veredito.IGUAL: "#16A34A",
    Veredito.AUSENTE_EM_TODAS: "#CBD5E1",
}


def fatias_da_composicao(comparacao: Comparacao) -> tuple[FatiaDaComposicao, ...]:
    """A comparação inteira como uma barra só, em ordem de peso na decisão.

    Cinco números separados não dizem nada sobre proporção: "8, 1, 0, 1, 5" só
    vira informação quando alguém soma. A barra mostra de relance que cinco dos
    quinze campos não são tratados por nenhuma das apólices — que é o argumento
    do projeto, e o que a ausência-como-ausência existe para deixar visível.

    Vem de `Comparacao.resumo`, como os KPIs: a interface não reconta nada.
    """
    resumo = comparacao.resumo
    ordem = sorted(ESTILOS, key=lambda v: ESTILOS[v].ordem)
    if Veredito.AUSENTE_EM_TODAS not in ordem:
        ordem.append(Veredito.AUSENTE_EM_TODAS)

    fatias: list[FatiaDaComposicao] = []
    for veredito in ordem:
        quantidade = resumo.get(veredito.value, 0)
        if veredito is Veredito.AUSENTE_EM_TODAS:
            rotulo, simbolo = "Fora das duas", "∅∅"
        else:
            est = estilo(veredito)
            rotulo, simbolo = est.rotulo, est.simbolo
        fatias.append(
            FatiaDaComposicao(
                rotulo=rotulo,
                quantidade=quantidade,
                cor=CORES_DA_COMPOSICAO.get(veredito, "#CBD5E1"),
                simbolo=simbolo,
            )
        )
    return tuple(fatias)


#: Fundo do selo de veredito, no tom claro da cor da fatia. O texto usa a cor
#: cheia (`CORES_DA_COMPOSICAO`), então a mesma situação tem o mesmo significado
#: cromático na barra, no selo e na célula da tabela.
CORES_DO_SELO: dict[Veredito, str] = {
    Veredito.AUSENTE_EM_ALGUMA: "#FEF4E4",
    Veredito.DIFERENTE: "#FCEBEB",
    Veredito.REDACAO_DIVERGENTE: "#F0EDFE",
    Veredito.IGUAL: "#E7F6ED",
    Veredito.AUSENTE_EM_TODAS: "#F1F5F9",
}


def cores_do_selo(veredito: Veredito) -> tuple[str, str]:
    """(fundo, texto) do selo de um veredito, com um par neutro de reserva."""
    return (
        CORES_DO_SELO.get(veredito, "#F1F5F9"),
        CORES_DA_COMPOSICAO.get(veredito, "#475569"),
    )


# ---------------------------------------------------------------------------
# Tabelas: a visão completa e a prova de origem
# ---------------------------------------------------------------------------


def matriz_comparativa(
    comparacao: Comparacao,
    apenas_relevantes: bool = False,
    apolices: Sequence[ApoliceExtraida] | None = None,
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    """A comparação inteira em formato de tabela, para o `st.dataframe`.

    Devolve `(colunas, linhas)` em vez de um DataFrame para não arrastar pandas
    para dentro do módulo que os testes exercitam.

    `apolices` é opcional porque a matriz funciona só com a comparação — mas,
    quando vem, é o que permite distinguir "a apólice não trata do assunto" de "a
    cláusula existe e o número está em outro documento". A diferença mora no
    `CampoExtraido`, e o motor devolve só o texto do valor.
    """
    colunas = ("Campo", *comparacao.apolices, "Situação")
    diferencas = comparacao.relevantes if apenas_relevantes else comparacao.diferencas
    por_nome = {a.nome: a for a in (apolices or ())}

    linhas: list[dict[str, Any]] = []
    for d in diferencas:
        linha: dict[str, Any] = {"Campo": d.campo.rotulo}
        for nome in comparacao.apolices:
            if por_nome:
                campo = _campo_de(por_nome.get(nome), d)
                linha[nome] = ValorNaTela(apolice=nome, campo=campo).texto
            else:
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


def exportar_csv(
    comparacao: Comparacao,
    apenas_relevantes: bool = False,
    apolices: Sequence[ApoliceExtraida] | None = None,
) -> str:
    """A comparação em CSV, pronta para o `st.download_button`.

    Separador `;` e BOM porque quem recebe isto abre no Excel em português — e
    um CSV de cláusulas com acento quebrado é pior que nenhum CSV. `apolices`
    passa adiante para `matriz_comparativa`: ver a nota lá.
    """
    colunas, linhas = matriz_comparativa(comparacao, apenas_relevantes, apolices)
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
    que recebe um `DocumentoExtraido` e devolve uma `ApoliceExtraida` — hoje é
    `extrair_apolice`. Quando nenhuma é encontrada, a tela diz que a extração não
    está publicada, em vez de mostrar campo vazio como se a apólice não tratasse
    do assunto, que seria a mentira mais cara possível neste projeto.
    """
    if modulo is None:
        return None
    for nome in NOMES_EXTRATOR:
        funcao = getattr(modulo, nome, None)
        if callable(funcao):
            return funcao
    return None


def carregar_modulo_extracao(nome: str = MODULO_EXTRACAO) -> object | None:
    """Importa o módulo da frente B, ou devolve `None` se não der para importar."""
    try:
        return importlib.import_module(nome)
    except ImportError:
        return None


def aviso_sem_extracao() -> str:
    """A frase que explica, na tela, por que os campos não saem do LLM.

    É o caminho de exceção: `app.agents` publica `extrair_apolice`, então este
    texto só aparece quando a importação falha ou a função some. Por isso ele
    fala do que falta **neste ambiente**, e não de uma frente inacabada — dizer
    "ainda não está pronta" com a extração publicada seria falso.
    """
    return (
        "**A extração das cláusulas não está publicada neste ambiente.**\n\n"
        "A ingestão é real: o documento foi lido, página a página, e o que aparece acima "
        "saiu dele. O que falta aqui é a etapa que transforma esse texto nos campos "
        "estruturados — a frente B a publica como `extrair_apolice`, em `app.agents`, e "
        "este aviso quer dizer que ela não foi encontrada. Enquanto isso, a comparação "
        "da aba *Comparação* roda sobre as extrações de exemplo de "
        "`app/domain/exemplos.py`, identificadas como tal em cada tela."
    )
