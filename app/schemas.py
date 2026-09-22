"""Contratos de dados entre as frentes.

Estes modelos são a fronteira: a frente A produz `DocumentoExtraido`, a frente B
consome e devolve os campos, a frente C compara. Nenhuma frente precisa saber como
a outra funciona por dentro — só precisa respeitar o que está escrito aqui.

A decisão que mais afeta o resto: **o texto extraído nunca perde o número da
página**. A tarefa B.3 exige que todo campo extraído aponte de onde veio, e não dá
para reconstruir essa informação depois de concatenar tudo numa string só.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum

from pydantic import BaseModel, Field, field_validator

#: Abre cada página no texto entregue ao modelo. O formato é explícito de
#: propósito: o modelo consegue citar "página 12" e nós conseguimos conferir.
MARCADOR_PAGINA = "=== PÁGINA {numero} ==="

_RE_MARCADOR = re.compile(r"^=== PÁGINA (\d+) ===$", re.MULTILINE)


class OrigemTexto(str, Enum):
    """De onde o texto de uma página veio."""

    PDF_NATIVO = "pdf-nativo"  # texto embutido no PDF, extração exata
    OCR = "ocr"                # reconhecido de imagem, sujeito a erro de leitura


class TipoArquivo(str, Enum):
    """Formatos que a plataforma aceita (tarefa A.1)."""

    PDF = "pdf"
    IMAGEM = "imagem"


class PaginaExtraida(BaseModel):
    """Uma página de um documento, com o texto que foi possível extrair dela."""

    numero: int = Field(ge=1, description="1 para a primeira página, como o leitor conta")
    texto: str
    origem: OrigemTexto

    @property
    def vazia(self) -> bool:
        """Página sem conteúdo aproveitável.

        O limiar é baixo de propósito: uma página de rosto legítima pode ter
        poucas palavras, e descartá-la perderia o número da apólice.
        """
        return len(self.texto.strip()) < 20


class DocumentoExtraido(BaseModel):
    """Documento inteiro convertido em texto, página a página.

    É o que a frente A entrega e a frente B consome.
    """

    nome_arquivo: str
    tipo: TipoArquivo
    paginas: list[PaginaExtraida]

    @field_validator("paginas")
    @classmethod
    def _paginas_em_ordem(cls, v: list[PaginaExtraida]) -> list[PaginaExtraida]:
        numeros = [p.numero for p in v]
        if numeros != sorted(numeros):
            raise ValueError("as paginas devem vir em ordem crescente")
        if len(numeros) != len(set(numeros)):
            raise ValueError("ha numero de pagina repetido")
        return v

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    @property
    def total_paginas(self) -> int:
        return len(self.paginas)

    @property
    def paginas_por_ocr(self) -> int:
        """Quantas páginas precisaram de OCR — o relatório cita este número."""
        return sum(1 for p in self.paginas if p.origem is OrigemTexto.OCR)

    @property
    def paginas_vazias(self) -> int:
        return sum(1 for p in self.paginas if p.vazia)

    @property
    def texto_completo(self) -> str:
        """Só o texto, sem marcadores. Para contagem e busca."""
        return "\n\n".join(p.texto for p in self.paginas)

    @property
    def texto_com_marcadores(self) -> str:
        """O texto como vai para o modelo, com a página anunciada antes de cada bloco.

        É isto que permite ao extrator responder "isto está na página 12" em vez de
        devolver um trecho solto — a matéria-prima da rastreabilidade (B.3).
        """
        partes = []
        for p in self.paginas:
            partes.append(MARCADOR_PAGINA.format(numero=p.numero))
            partes.append(p.texto)
        return "\n".join(partes)

    def pagina(self, numero: int) -> PaginaExtraida | None:
        return next((p for p in self.paginas if p.numero == numero), None)

    def paginas_de(self, trecho: str) -> list[int]:
        """Todas as páginas onde este trecho aparece.

        Devolve lista porque apólice tem cabeçalho e rodapé repetidos em todas as
        páginas — o número do processo SUSEP da Chubb, por exemplo, ocorre nas 70.
        Responder só a primeira ocorrência daria uma resposta tecnicamente certa e
        praticamente inútil, e pior: faria uma citação de cabeçalho parecer uma
        localização precisa.

        A comparação ignora acento, caixa e quebras de linha, porque o modelo
        reescreve o espaçamento ao citar.
        """
        alvo = _normalizar(trecho)
        if not alvo:
            return []
        return [p.numero for p in self.paginas if alvo in _normalizar(p.texto)]

    def pagina_de(self, trecho: str) -> int | None:
        """A página deste trecho, ou `None` se não estiver em nenhuma — e também
        `None` se estiver em muitas.

        Um trecho que aparece em mais de três páginas é cabeçalho, rodapé ou
        fórmula repetida, não uma localização. Quem precisa do detalhe usa
        `paginas_de`; quem só quer a origem de um campo recebe `None` e sabe que
        aquela citação não serve como prova de lugar.
        """
        encontradas = self.paginas_de(trecho)
        if not encontradas or len(encontradas) > 3:
            return None
        return encontradas[0]

    def trecho_repetido(self, trecho: str) -> bool:
        """Se este trecho é boilerplate — aparece em mais de três páginas."""
        return len(self.paginas_de(trecho)) > 3


# ---------------------------------------------------------------------------
# Fronteira entre a extração (frente B) e a comparação (frente C)
#
# A frente B lê o documento e devolve `ApoliceExtraida`. A frente C recebe duas ou
# mais e aponta as diferenças. Nenhuma das duas precisa saber como a outra
# funciona, mas as duas precisam concordar com o que está escrito abaixo.
# ---------------------------------------------------------------------------


class CampoExtraido(BaseModel):
    """O que a plataforma achou de um campo do dicionário, numa apólice.

    Os três atributos de origem (`trecho_origem`, `pagina`, `paginas_possiveis`)
    são o que torna a extração auditável. Sem eles não há como distinguir um valor
    lido de um valor inventado, que é justamente o risco de usar um modelo de
    linguagem sobre documento jurídico.
    """

    campo_id: str = Field(description="o mesmo `id` usado em data/campos_do.yaml")
    valor: str | None = Field(
        default=None,
        description="o que foi encontrado; None quando a apólice não trata do assunto",
    )
    trecho_origem: str | None = Field(
        default=None, description="o texto da apólice de onde o valor saiu"
    )
    pagina: int | None = Field(
        default=None, description="página do trecho, quando é possível localizá-lo"
    )
    paginas_possiveis: list[int] = Field(
        default_factory=list,
        description="todas as páginas onde o trecho ocorre; mais de três indica boilerplate",
    )
    observacao: str | None = Field(
        default=None, description="ressalva do extrator, quando houver"
    )

    @property
    def encontrado(self) -> bool:
        return self.valor is not None and self.valor.strip() != ""

    @property
    def rastreavel(self) -> bool:
        """Se dá para apontar de onde este valor veio.

        Um campo encontrado mas não rastreável não é erro — pode ser um resumo de
        cláusula longa —, mas vale menos, e o relatório distingue os dois.
        """
        return self.encontrado and self.pagina is not None and bool(self.trecho_origem)


class ApoliceExtraida(BaseModel):
    """Uma apólice depois de lida e estruturada. É o que a frente B entrega."""

    documento: str = Field(description="nome do arquivo de origem")
    seguradora: str | None = None
    campos: list[CampoExtraido]
    modelo_usado: str | None = Field(
        default=None, description="qual LLM gerou esta extração, para o relatório"
    )

    @field_validator("campos")
    @classmethod
    def _sem_campo_repetido(cls, v: list[CampoExtraido]) -> list[CampoExtraido]:
        ids = [c.campo_id for c in v]
        if len(ids) != len(set(ids)):
            repetidos = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"campo extraido mais de uma vez: {', '.join(repetidos)}")
        return v

    @property
    def nome(self) -> str:
        """Como esta apólice aparece no relatório."""
        return self.seguradora or self.documento

    def campo(self, campo_id: str) -> CampoExtraido | None:
        return next((c for c in self.campos if c.campo_id == campo_id), None)

    @property
    def encontrados(self) -> int:
        return sum(1 for c in self.campos if c.encontrado)

    @property
    def rastreaveis(self) -> int:
        return sum(1 for c in self.campos if c.rastreavel)


def _normalizar(texto: str) -> str:
    """Tira acento, caixa e espaço repetido — para comparar citação com original."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def separar_por_marcador(texto: str) -> dict[int, str]:
    """Desfaz `texto_com_marcadores`, devolvendo {número da página: texto}.

    Útil para quem recebe o texto pronto e precisa voltar à página de origem.
    """
    resultado: dict[int, str] = {}
    marcas = list(_RE_MARCADOR.finditer(texto))
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        resultado[int(m.group(1))] = texto[m.end():fim].strip()
    return resultado
