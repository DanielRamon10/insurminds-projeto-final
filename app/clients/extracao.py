"""Extração de texto de PDF e de imagem — tarefas A.2 e A.3.

Duas rotas, escolhidas por página e não por documento:

* **PDF nativo** (`pypdf`) quando a página traz texto embutido. É exato e
  instantâneo — as condições gerais que o corretor do grupo reuniu são todas assim.
* **OCR** (`pytesseract`) quando a página não traz texto, o que acontece em
  documento escaneado e em imagem solta. É lento e sujeito a erro de leitura, então
  só entra quando não há alternativa.

A escolha é por página porque documento misto existe: um PDF nativo com uma página
escaneada no meio (um anexo assinado, por exemplo) perderia justamente essa página
se a decisão fosse tomada uma vez para o arquivo inteiro.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ..config import DPI_OCR, IDIOMA_OCR, MINIMO_CARACTERES_PAGINA, caminho_tesseract
from ..schemas import OrigemTexto, PaginaExtraida

log = logging.getLogger(__name__)


class ErroExtracao(Exception):
    """O documento não pôde ser lido de forma nenhuma."""


class OCRIndisponivel(ErroExtracao):
    """O OCR seria necessário, mas o Tesseract não está instalado.

    Mensagem separada porque a solução é do operador, não do código.
    """


# ---------------------------------------------------------------------------
# PDF com texto embutido
# ---------------------------------------------------------------------------


def _texto_das_paginas(caminho: Path) -> list[str]:
    """Texto de cada página do PDF, na ordem. String vazia onde não houver."""
    try:
        leitor = PdfReader(caminho)
    except (PdfReadError, OSError, ValueError) as exc:
        raise ErroExtracao(f"nao foi possivel abrir {caminho.name}: {exc}") from exc

    if leitor.is_encrypted:
        try:
            leitor.decrypt("")  # PDFs protegidos só contra edição abrem com senha vazia
        except Exception as exc:
            raise ErroExtracao(
                f"{caminho.name} esta protegido por senha e nao pode ser lido"
            ) from exc

    textos: list[str] = []
    for i, pagina in enumerate(leitor.pages, start=1):
        try:
            textos.append(pagina.extract_text() or "")
        except Exception as exc:
            # uma página defeituosa não pode custar o documento inteiro (A.4)
            log.warning("falha ao extrair a pagina %d de %s: %s", i, caminho.name, exc)
            textos.append("")
    return textos


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------


def ocr_disponivel() -> bool:
    """Se dá para rodar OCR neste computador."""
    if caminho_tesseract() is None:
        return False
    try:
        import pytesseract  # noqa: F401
        import pypdfium2  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True


def _exigir_ocr() -> None:
    if caminho_tesseract() is None:
        raise OCRIndisponivel(
            "Tesseract nao encontrado. Instale-o para ler documentos escaneados:\n"
            "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  Linux  : sudo apt install tesseract-ocr tesseract-ocr-por\n"
            "  macOS  : brew install tesseract tesseract-lang\n"
            "Se ja estiver instalado fora do PATH, aponte com TESSERACT_CMD no .env."
        )
    try:
        import pytesseract  # noqa: F401
        import pypdfium2  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise OCRIndisponivel(
            f"pacote de OCR faltando ({exc.name}). Instale com: "
            f"pip install pytesseract pypdfium2 pillow"
        ) from exc


def _ler_por_ocr(imagem) -> str:
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = caminho_tesseract()
    try:
        return pytesseract.image_to_string(imagem, lang=IDIOMA_OCR).strip()
    except Exception as exc:
        log.warning("OCR falhou numa pagina: %s", exc)
        return ""


def _ocr_de_pagina_pdf(caminho: Path, numero: int) -> str:
    """Renderiza uma página do PDF como imagem e passa pelo OCR.

    `pypdfium2` renderiza sem depender de nada instalado no sistema — ao contrário
    do `pdf2image`, que exige o poppler à parte.
    """
    _exigir_ocr()
    import pypdfium2 as pdfium

    documento = pdfium.PdfDocument(caminho)
    try:
        pagina = documento[numero - 1]
        # escala em relação a 72 dpi, que é a unidade do PDF
        imagem = pagina.render(scale=DPI_OCR / 72).to_pil()
        return _ler_por_ocr(imagem)
    finally:
        documento.close()


def extrair_de_imagem(caminho: Path) -> str:
    """Texto de um arquivo de imagem solto (PNG, JPG, TIFF...)."""
    _exigir_ocr()
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(caminho) as imagem:
            return _ler_por_ocr(imagem)
    except (UnidentifiedImageError, OSError) as exc:
        raise ErroExtracao(f"nao foi possivel abrir a imagem {caminho.name}: {exc}") from exc


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def extrair_pdf(caminho: Path, permitir_ocr: bool = True) -> list[PaginaExtraida]:
    """Lê um PDF página a página, usando OCR só onde o texto embutido falta.

    Com `permitir_ocr=False` as páginas sem texto voltam vazias em vez de
    levantar erro — é o modo usado quando não se quer esperar pelo OCR.
    """
    textos = _texto_das_paginas(caminho)
    if not textos:
        raise ErroExtracao(f"{caminho.name} nao tem nenhuma pagina")

    paginas: list[PaginaExtraida] = []
    for numero, texto in enumerate(textos, start=1):
        origem = OrigemTexto.PDF_NATIVO

        if len(texto.strip()) < MINIMO_CARACTERES_PAGINA and permitir_ocr:
            if ocr_disponivel():
                log.info("pagina %d de %s sem texto: tentando OCR", numero, caminho.name)
                if reconhecido := _ocr_de_pagina_pdf(caminho, numero):
                    texto, origem = reconhecido, OrigemTexto.OCR
            else:
                log.warning(
                    "pagina %d de %s sem texto embutido e OCR indisponivel",
                    numero, caminho.name,
                )

        paginas.append(PaginaExtraida(numero=numero, texto=texto, origem=origem))

    if all(p.vazia for p in paginas):
        raise ErroExtracao(
            f"{caminho.name}: nenhuma pagina rendeu texto. "
            f"Se for um documento escaneado, o OCR precisa estar disponivel."
        )
    return paginas
