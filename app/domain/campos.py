"""Leitura do dicionário de campos — `data/campos_do.yaml`.

O arquivo é do especialista de seguros do grupo: define o que a plataforma procura
e por que cada diferença importa. Tudo é validado na carga, porque um `id`
repetido ou um tipo desconhecido viraria comportamento errado silencioso lá na
comparação, longe da causa.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from ..config import DATA_DIR


class ErroCampos(Exception):
    """Dicionário de campos inconsistente."""


class TipoCampo(str, Enum):
    """Como o valor deste campo deve ser comparado.

    A distinção existe porque comparar dinheiro e comparar cláusula são coisas
    diferentes: `R$ 10.000.000,00` e `R$ 10 milhões` são o mesmo valor escrito de
    dois jeitos, enquanto duas redações de exclusão de poluição podem dizer coisas
    distintas usando palavras parecidas.
    """

    VALOR_MONETARIO = "valor_monetario"
    DATA = "data"
    PERIODO = "periodo"
    PRAZO = "prazo"
    TEXTO = "texto"


@dataclass(frozen=True)
class Campo:
    """Um campo que a plataforma procura em toda apólice."""

    id: str
    rotulo: str
    significado: str
    sinonimos: tuple[str, ...]
    tipo: TipoCampo
    porque_importa: str

    @property
    def nomes(self) -> tuple[str, ...]:
        """Todos os nomes sob os quais este campo pode aparecer no documento."""
        return (self.rotulo, *self.sinonimos)


@dataclass(frozen=True)
class DicionarioCampos:
    """O conjunto de campos definido pelo especialista."""

    versao: int
    definido_por: str
    campos: tuple[Campo, ...]

    def __iter__(self):
        return iter(self.campos)

    def __len__(self) -> int:
        return len(self.campos)

    def por_id(self, campo_id: str) -> Campo | None:
        return next((c for c in self.campos if c.id == campo_id), None)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.campos)


def carregar_campos(caminho: Path | None = None) -> DicionarioCampos:
    """Lê e valida `data/campos_do.yaml`."""
    caminho = caminho or DATA_DIR / "campos_do.yaml"
    if not caminho.is_file():
        raise ErroCampos(f"dicionario de campos nao encontrado: {caminho}")

    try:
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ErroCampos(f"YAML invalido em {caminho.name}: {exc}") from exc

    if not isinstance(bruto, dict) or not bruto.get("campos"):
        raise ErroCampos(f"{caminho.name} nao tem a secao 'campos'")

    campos: list[Campo] = []
    vistos: set[str] = set()

    for dados in bruto["campos"]:
        campo_id = str(dados.get("id", "")).strip()
        if not campo_id:
            raise ErroCampos(f"campo sem 'id': {dados}")
        if campo_id in vistos:
            raise ErroCampos(f"id de campo repetido: '{campo_id}'")
        vistos.add(campo_id)

        try:
            tipo = TipoCampo(dados.get("tipo", "texto"))
        except ValueError as exc:
            raise ErroCampos(
                f"campo '{campo_id}': tipo '{dados.get('tipo')}' desconhecido "
                f"(validos: {', '.join(t.value for t in TipoCampo)})"
            ) from exc

        porque = (dados.get("porque_importa") or "").strip()
        if not porque:
            raise ErroCampos(
                f"campo '{campo_id}' sem 'porque_importa' — e o texto que explica "
                f"ao usuario o peso da diferenca, e sem ele o relatorio fica mudo"
            )

        campos.append(
            Campo(
                id=campo_id,
                rotulo=str(dados.get("rotulo", campo_id)),
                significado=str(dados.get("significado", "")).strip(),
                sinonimos=tuple(dados.get("sinonimos") or ()),
                tipo=tipo,
                porque_importa=porque,
            )
        )

    return DicionarioCampos(
        versao=int(bruto.get("versao", 1)),
        definido_por=str(bruto.get("definido_por", "(nao informado)")),
        campos=tuple(campos),
    )
