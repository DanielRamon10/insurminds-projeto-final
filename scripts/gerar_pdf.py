"""Converte um documento Markdown de `docs/` em PDF, para circular pelo grupo.

Nem todo mundo no grupo abre Markdown ou navega no GitHub; o PDF chega por
WhatsApp e abre no celular. A conversão é Markdown -> HTML -> PDF pelo Chrome
em modo headless, sem depender de LaTeX nem de pacote externo.

    python -m scripts.gerar_pdf docs/ROTEIRO_PROJETO_FINAL.md
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

CHROMES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
]

ESTILO = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Segoe UI", Calibri, sans-serif; font-size: 10.5pt;
       line-height: 1.55; color: #1a1a1a; }
h1 { font-size: 19pt; color: #1F4E79; border-bottom: 2px solid #1F4E79;
     padding-bottom: 6px; margin-bottom: 4px; }
h2 { font-size: 14pt; color: #1F4E79; margin-top: 26px;
     border-bottom: 1px solid #c9d6e4; padding-bottom: 3px; }
h3 { font-size: 11.5pt; color: #2a5d8f; margin-top: 18px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 9.5pt; }
th { background: #1F4E79; color: #fff; text-align: left; padding: 7px 9px; }
td { border-bottom: 1px solid #dde4ec; padding: 6px 9px; vertical-align: top; }
tr:nth-child(even) td { background: #f6f9fc; }
code { background: #eef2f7; padding: 1px 5px; border-radius: 3px;
       font-family: Consolas, monospace; font-size: 9.5pt; }
blockquote { border-left: 4px solid #1F4E79; background: #f6f9fc;
             margin: 12px 0; padding: 9px 14px; }
blockquote p { margin: 4px 0; }
hr { border: none; border-top: 1px solid #d6dee8; margin: 22px 0; }
strong { color: #10375c; }
h2, h3, table, blockquote { page-break-inside: avoid; }
h2, h3 { page-break-after: avoid; }
"""


def inline(texto: str) -> str:
    """Aplica negrito, itálico e código dentro de uma linha já escapada."""
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", texto)
    return texto


def converter(markdown: str) -> str:
    """Markdown -> HTML. Cobre só o que os documentos do projeto usam."""
    saida: list[str] = []
    linhas = markdown.split("\n")
    i = 0

    while i < len(linhas):
        linha = linhas[i].rstrip()

        if not linha.strip():
            i += 1
            continue

        if re.match(r"^---+$", linha.strip()):
            saida.append("<hr>")
            i += 1
            continue

        if m := re.match(r"^(#{1,4})\s+(.*)", linha):
            nivel = len(m.group(1))
            saida.append(f"<h{nivel}>{inline(html.escape(m.group(2)))}</h{nivel}>")
            i += 1
            continue

        # tabela: linha de cabeçalho seguida da linha de separação
        if linha.startswith("|") and i + 1 < len(linhas) and re.match(r"^\|[\s:\-|]+\|$", linhas[i + 1].strip()):
            def celulas(l: str) -> list[str]:
                return [c.strip() for c in l.strip().strip("|").split("|")]

            cabecalho = celulas(linha)
            i += 2
            corpo = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                corpo.append(celulas(linhas[i]))
                i += 1
            th = "".join(f"<th>{inline(html.escape(c))}</th>" for c in cabecalho)
            trs = "".join(
                "<tr>" + "".join(f"<td>{inline(html.escape(c))}</td>" for c in linha_corpo) + "</tr>"
                for linha_corpo in corpo
            )
            saida.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
            continue

        if linha.startswith(">"):
            bloco = []
            while i < len(linhas) and linhas[i].startswith(">"):
                bloco.append(linhas[i].lstrip("> ").rstrip())
                i += 1
            texto = " ".join(bloco)
            saida.append(f"<blockquote><p>{inline(html.escape(texto))}</p></blockquote>")
            continue

        if re.match(r"^\s*[-*]\s+", linha):
            itens = []
            while i < len(linhas) and re.match(r"^\s*[-*]\s+", linhas[i]):
                itens.append(re.sub(r"^\s*[-*]\s+", "", linhas[i]).rstrip())
                i += 1
            li = "".join(f"<li>{inline(html.escape(t))}</li>" for t in itens)
            saida.append(f"<ul>{li}</ul>")
            continue

        if re.match(r"^\s*\d+\.\s+", linha):
            itens = []
            while i < len(linhas) and re.match(r"^\s*\d+\.\s+", linhas[i]):
                itens.append(re.sub(r"^\s*\d+\.\s+", "", linhas[i]).rstrip())
                i += 1
            li = "".join(f"<li>{inline(html.escape(t))}</li>" for t in itens)
            saida.append(f"<ol>{li}</ol>")
            continue

        paragrafo = [linha]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not re.match(
            r"^(#{1,4}\s|>|\||\s*[-*]\s|\s*\d+\.\s|---+$)", linhas[i]
        ):
            paragrafo.append(linhas[i].rstrip())
            i += 1
        saida.append(f"<p>{inline(html.escape(' '.join(paragrafo)))}</p>")

    return "\n".join(saida)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    origem = Path(sys.argv[1])
    if not origem.is_absolute():
        origem = RAIZ / origem
    if not origem.is_file():
        print(f"arquivo nao encontrado: {origem}")
        return 1

    chrome = next((c for c in CHROMES if c.is_file()), None)
    if chrome is None:
        print("Chrome nao encontrado — necessario para gerar o PDF.")
        return 1

    corpo = converter(origem.read_text(encoding="utf-8"))
    html_completo = (
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{html.escape(origem.stem)}</title><style>{ESTILO}</style></head>"
        f"<body>{corpo}</body></html>"
    )

    caminho_html = origem.with_suffix(".html")
    caminho_pdf = origem.with_suffix(".pdf")
    caminho_html.write_text(html_completo, encoding="utf-8")

    r = subprocess.run(
        [
            str(chrome), "--headless", "--disable-gpu", "--no-pdf-header-footer",
            f"--print-to-pdf={caminho_pdf}", caminho_html.as_uri(),
        ],
        capture_output=True, text=True, timeout=300,
    )
    if not caminho_pdf.is_file():
        print(f"falha ao gerar o PDF: {r.stderr[:300]}")
        return 1

    print(f"PDF gerado: {caminho_pdf.relative_to(RAIZ)} "
          f"({caminho_pdf.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
