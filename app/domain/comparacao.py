"""Motor de comparação entre apólices — tarefas C.2 e C.3.

**Este módulo não usa modelo de linguagem, e isso é deliberado.** Ele decide *o
que* difere: determinístico, testável, sempre igual para a mesma entrada. Explicar
*por que a diferença importa* é trabalho do redator (C.4), que usa LLM.

Manter a fronteira é o que permite testar a comparação sem rede e sem cota — e foi
misturar as duas coisas que custou um PR de consolidação no Desafio 5.

Como cada tipo é comparado:

* **Valor monetário** — extrai o número e compara grandeza. `R$ 10.000.000,00` e
  `R$ 10 milhões` são o mesmo valor escrito de dois jeitos, e dizer que diferem
  seria um falso positivo grosseiro na cara do usuário.
* **Prazo** — extrai a quantidade de dias, meses ou anos e normaliza para dias.
* **Data e período** — comparação textual normalizada; formatos variam pouco.
* **Texto** — aqui a comparação literal não serve: duas seguradoras escrevem a
  mesma exclusão com palavras diferentes. O motor reporta que ambas tratam do
  assunto com redações distintas e deixa a leitura para o redator, em vez de
  fingir que sabe se o conteúdo é equivalente.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from ..schemas import ApoliceExtraida, CampoExtraido
from .campos import Campo, DicionarioCampos, TipoCampo, carregar_campos


class Veredito(str, Enum):
    """O que se pode dizer de um campo ao longo de várias apólices."""

    IGUAL = "igual"
    DIFERENTE = "diferente"
    #: Todas tratam do assunto, mas em texto corrido que não dá para igualar
    #: mecanicamente. É o redator que diz se o conteúdo diverge.
    REDACAO_DIVERGENTE = "redacao_divergente"
    #: Uma apólice trata do assunto e outra não — costuma ser a diferença que mais
    #: importa, e some se o campo ausente for tratado como "vazio igual a vazio".
    AUSENTE_EM_ALGUMA = "ausente_em_alguma"
    AUSENTE_EM_TODAS = "ausente_em_todas"


#: Multiplicadores para "10 milhões", "500 mil".
_ESCALAS = {
    "mil": 1_000,
    "milhao": 1_000_000,
    "milhoes": 1_000_000,
    "bilhao": 1_000_000_000,
    "bilhoes": 1_000_000_000,
}

#: Para normalizar prazo em dias.
_UNIDADES_PRAZO = {"dia": 1, "dias": 1, "mes": 30, "meses": 30, "ano": 365, "anos": 365}


@dataclass(frozen=True)
class DiferencaCampo:
    """O que se encontrou de um campo, comparando as apólices."""

    campo: Campo
    veredito: Veredito
    #: {nome da apólice: valor encontrado, ou None}
    valores: dict[str, str | None]
    #: {nome da apólice: página de origem, ou None}
    paginas: dict[str, int | None] = field(default_factory=dict)

    @property
    def relevante(self) -> bool:
        """Se vale aparecer no topo do relatório.

        Campo igual em todas não é notícia; ausente em todas é lacuna das duas
        apólices, não diferença entre elas.
        """
        return self.veredito in {
            Veredito.DIFERENTE,
            Veredito.AUSENTE_EM_ALGUMA,
            Veredito.REDACAO_DIVERGENTE,
        }

    @property
    def porque_importa(self) -> str:
        """A explicação escrita pelo especialista para este campo."""
        return self.campo.porque_importa

    def ausentes(self) -> list[str]:
        """Quais apólices não tratam deste campo."""
        return [nome for nome, valor in self.valores.items() if not valor]


@dataclass(frozen=True)
class Comparacao:
    """O resultado completo: todas as apólices, todos os campos."""

    apolices: tuple[str, ...]
    diferencas: tuple[DiferencaCampo, ...]

    @property
    def relevantes(self) -> tuple[DiferencaCampo, ...]:
        """Só o que distingue uma apólice da outra, em ordem de leitura."""
        ordem = {
            Veredito.AUSENTE_EM_ALGUMA: 0,
            Veredito.DIFERENTE: 1,
            Veredito.REDACAO_DIVERGENTE: 2,
        }
        return tuple(
            sorted(
                (d for d in self.diferencas if d.relevante),
                key=lambda d: (ordem[d.veredito], d.campo.rotulo),
            )
        )

    def por_veredito(self, veredito: Veredito) -> tuple[DiferencaCampo, ...]:
        return tuple(d for d in self.diferencas if d.veredito is veredito)

    @property
    def resumo(self) -> dict[str, int]:
        return {v.value: len(self.por_veredito(v)) for v in Veredito}


# ---------------------------------------------------------------------------
# Normalização por tipo
# ---------------------------------------------------------------------------


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def valor_monetario(texto: str) -> float | None:
    """Extrai a grandeza de um valor em reais, ou `None` se não houver número.

    Entende tanto `R$ 10.000.000,00` quanto `R$ 10 milhões`, que é como as
    condições gerais alternam entre o quadro de apólice e o texto corrido.
    """
    limpo = _sem_acento(texto.lower())
    m = re.search(r"(\d[\d.\s]*(?:,\d+)?)", limpo)
    if not m:
        return None

    bruto = m.group(1).replace(" ", "")
    # pt-BR: ponto separa milhar, vírgula separa decimal
    numero = float(bruto.replace(".", "").replace(",", "."))

    depois = limpo[m.end():m.end() + 24]
    for palavra, fator in _ESCALAS.items():
        if re.search(rf"\b{palavra}\b", depois):
            return numero * fator
    return numero


def prazo_em_dias(texto: str) -> int | None:
    """Converte `90 dias`, `3 meses`, `1 ano` para dias."""
    limpo = _sem_acento(texto.lower())
    m = re.search(r"(\d+)\s*(dias?|meses|mes|anos?)", limpo)
    if not m:
        return None
    return int(m.group(1)) * _UNIDADES_PRAZO[m.group(2)]


def _texto_comparavel(texto: str) -> str:
    return re.sub(r"[^\w\s]", " ", re.sub(r"\s+", " ", _sem_acento(texto.lower()))).strip()


def equivalentes(a: str, b: str, tipo: TipoCampo) -> bool | None:
    """Se dois valores dizem a mesma coisa.

    Devolve `None` quando a comparação mecânica não é confiável — o caso do texto
    corrido, em que só a leitura resolve. Retornar `False` ali seria afirmar uma
    diferença que não foi verificada.
    """
    if tipo is TipoCampo.VALOR_MONETARIO:
        va, vb = valor_monetario(a), valor_monetario(b)
        if va is not None and vb is not None:
            return va == vb
        return _texto_comparavel(a) == _texto_comparavel(b)

    if tipo is TipoCampo.PRAZO:
        pa, pb = prazo_em_dias(a), prazo_em_dias(b)
        if pa is not None and pb is not None:
            return pa == pb
        return _texto_comparavel(a) == _texto_comparavel(b)

    if tipo in {TipoCampo.DATA, TipoCampo.PERIODO}:
        return _texto_comparavel(a) == _texto_comparavel(b)

    # TEXTO: idênticos é resposta segura; diferentes exige leitura
    if _texto_comparavel(a) == _texto_comparavel(b):
        return True
    return None


# ---------------------------------------------------------------------------
# Comparação
# ---------------------------------------------------------------------------


def _avaliar(campo: Campo, extraidos: dict[str, CampoExtraido | None]) -> Veredito:
    presentes = {
        nome: c.valor for nome, c in extraidos.items() if c is not None and c.encontrado
    }

    if not presentes:
        return Veredito.AUSENTE_EM_TODAS
    if len(presentes) < len(extraidos):
        return Veredito.AUSENTE_EM_ALGUMA

    valores = list(presentes.values())
    referencia = valores[0]
    incerto = False
    for outro in valores[1:]:
        resultado = equivalentes(referencia, outro, campo.tipo)
        if resultado is False:
            return Veredito.DIFERENTE
        if resultado is None:
            incerto = True

    return Veredito.REDACAO_DIVERGENTE if incerto else Veredito.IGUAL


def comparar(
    apolices: list[ApoliceExtraida], dicionario: DicionarioCampos | None = None
) -> Comparacao:
    """Compara duas ou mais apólices, campo a campo.

    Percorre o dicionário do especialista, e não os campos que cada apólice trouxe:
    é assim que um campo ausente numa delas aparece como ausência, em vez de
    simplesmente não ser mencionado.
    """
    if len(apolices) < 2:
        raise ValueError("a comparacao precisa de pelo menos duas apolices")

    nomes = [a.nome for a in apolices]
    if len(set(nomes)) != len(nomes):
        raise ValueError(f"duas apolices com o mesmo nome: {nomes}")

    dicionario = dicionario or carregar_campos()

    diferencas: list[DiferencaCampo] = []
    for campo in dicionario:
        extraidos = {a.nome: a.campo(campo.id) for a in apolices}
        diferencas.append(
            DiferencaCampo(
                campo=campo,
                veredito=_avaliar(campo, extraidos),
                valores={
                    nome: (c.valor if c and c.encontrado else None)
                    for nome, c in extraidos.items()
                },
                paginas={
                    nome: (c.pagina if c else None) for nome, c in extraidos.items()
                },
            )
        )

    return Comparacao(apolices=tuple(nomes), diferencas=tuple(diferencas))
