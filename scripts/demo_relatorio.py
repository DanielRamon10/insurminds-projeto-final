"""Demonstração da C.4: o relatório comparativo em prosa.

Carrega as extrações de `data/extracoes/`, compara (frente C, sem LLM) e pede ao
redator a leitura das cláusulas de redação divergente. O relatório é impresso e
salvo em `data/relatorios/`, junto com a resposta crua do modelo.

    python -m scripts.demo_relatorio              # com a leitura do LLM
    python -m scripts.demo_relatorio --sem-llm    # só o motor, sem rede e sem cota
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.redator import redigir  # noqa: E402
from app.config import DATA_DIR  # noqa: E402
from app.domain.comparacao import comparar  # noqa: E402
from app.schemas import ApoliceExtraida  # noqa: E402

EXTRACOES_DIR = DATA_DIR / "extracoes"
SAIDA_DIR = DATA_DIR / "relatorios"


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
    usar_llm = "--sem-llm" not in sys.argv[1:]

    arquivos = sorted(
        p for p in EXTRACOES_DIR.glob("*.json") if not p.name.endswith(".resposta_llm.json")
    )
    apolices = [
        ApoliceExtraida.model_validate_json(p.read_text(encoding="utf-8")) for p in arquivos
    ]
    if len(apolices) < 2:
        print(f"preciso de pelo menos duas extracoes em {EXTRACOES_DIR} "
              "(rode python -m scripts.demo_extracao antes)")
        return 1

    relatorio = redigir(comparar(apolices), apolices, usar_llm=usar_llm)
    texto = relatorio.markdown()
    print(texto)

    SAIDA_DIR.mkdir(exist_ok=True)
    nome = "_x_".join(Path(a.documento).stem for a in apolices)
    destino = SAIDA_DIR / f"{nome}.md"
    destino.write_text(texto, encoding="utf-8")
    if relatorio.resposta_llm:
        (SAIDA_DIR / f"{nome}.resposta_llm.json").write_text(
            relatorio.resposta_llm, encoding="utf-8"
        )

    print(f"\nsalvo em {destino.relative_to(DATA_DIR.parent)}", file=sys.stderr)
    if relatorio.modelo_usado:
        print(f"modelo: {relatorio.modelo_usado} | tokens: {relatorio.tokens_entrada} entrada "
              f"+ {relatorio.tokens_saida} saida", file=sys.stderr)
    for a in relatorio.analises:
        for r in a.ressalvas:
            print(f"ressalva em {a.campo_id}: {r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
