"""Demonstração da frente A: o que a ingestão entrega para a frente B.

Roda sobre as apólices em `data/apolices/` e mostra o contrato que a extração de
cláusulas vai consumir — inclusive o texto com marcadores de página, que é a
matéria-prima da rastreabilidade (B.3).

    python -m scripts.demo_ingestao
    python -m scripts.demo_ingestao caminho/para/outra.pdf
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# O console do Windows abre em cp1252 e engasga com acento vindo do PDF. Todo o
# grupo trabalha em Windows, então a saída é forçada para UTF-8 antes de imprimir.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.extracao import ErroExtracao, ocr_disponivel  # noqa: E402
from app.config import APOLICES_DIR  # noqa: E402
from app.domain.ingestao import ArquivoRecusado, receber_varios  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        alvos = [Path(a) for a in sys.argv[1:]]
    else:
        alvos = sorted(APOLICES_DIR.glob("*.pdf"))
        if not alvos:
            print(f"nenhuma apolice em {APOLICES_DIR}")
            return 1

    print(f"OCR disponivel: {'sim' if ocr_disponivel() else 'nao'}\n")

    inicio = time.time()
    documentos, falhas = receber_varios(alvos)
    duracao = time.time() - inicio

    for d in documentos:
        tokens = int(len(d.texto_com_marcadores.split()) / 0.75)
        print(f"{d.nome_arquivo}")
        print(f"  {d.total_paginas} paginas | {len(d.texto_completo):,} caracteres "
              f"| ~{tokens:,} tokens".replace(",", "."))
        print(f"  por OCR: {d.paginas_por_ocr} | vazias: {d.paginas_vazias}")

        # amostra do que o modelo recebe
        amostra = d.texto_com_marcadores[:180].replace("\n", " | ")
        print(f"  entrega ao modelo: {amostra}...")

        # prova de rastreabilidade num trecho do miolo
        meio = d.paginas[d.total_paginas // 2]
        palavras = meio.texto.split()
        if len(palavras) > 30:
            trecho = " ".join(palavras[len(palavras) // 2:][:10])
            paginas = d.paginas_de(trecho)
            print(f"  rastreabilidade: trecho da pagina {meio.numero} localizado em {paginas}")
        print()

    if falhas:
        print("Nao foram lidos:")
        for nome, motivo in falhas:
            print(f"  {nome}: {motivo}")
        print()

    print(f"{len(documentos)} documento(s) em {duracao:.1f}s")
    return 0 if documentos else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ArquivoRecusado, ErroExtracao) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        sys.exit(1)
