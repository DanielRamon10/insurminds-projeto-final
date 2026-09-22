"""Recepção dos documentos — tarefas A.1 e A.4.

É a porta de entrada da plataforma: decide se o arquivo pode ser lido, escolhe a
rota de extração e devolve o `DocumentoExtraido` que a frente B consome.

A recusa é tão importante quanto a aceitação. Um `.docx` que entrasse por engano
produziria texto vazio lá na frente, e a mensagem de erro apareceria no meio da
extração — longe da causa. Barrar aqui, dizendo o que se aceita, poupa a
investigação.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..clients.extracao import ErroExtracao, extrair_de_imagem, extrair_pdf
from ..config import EXTENSOES_IMAGEM, EXTENSOES_PDF
from ..schemas import DocumentoExtraido, OrigemTexto, PaginaExtraida, TipoArquivo

log = logging.getLogger(__name__)


class ArquivoRecusado(Exception):
    """O arquivo não pode ser processado, e o motivo cabe numa frase."""


def identificar(caminho: Path) -> TipoArquivo:
    """Que tipo de arquivo é este, ou recusa dizendo o que é aceito."""
    if not caminho.exists():
        raise ArquivoRecusado(f"arquivo nao encontrado: {caminho}")
    if not caminho.is_file():
        raise ArquivoRecusado(f"{caminho.name} nao e um arquivo")
    if caminho.stat().st_size == 0:
        raise ArquivoRecusado(f"{caminho.name} esta vazio")

    sufixo = caminho.suffix.lower()
    if sufixo in EXTENSOES_PDF:
        return TipoArquivo.PDF
    if sufixo in EXTENSOES_IMAGEM:
        return TipoArquivo.IMAGEM

    aceitos = ", ".join(sorted(EXTENSOES_PDF | EXTENSOES_IMAGEM))
    raise ArquivoRecusado(
        f"{caminho.name}: formato '{sufixo or 'sem extensao'}' nao e aceito. "
        f"A plataforma le apolices em PDF ou imagem ({aceitos})."
    )


def receber(caminho: Path | str, permitir_ocr: bool = True) -> DocumentoExtraido:
    """Lê um documento e devolve o texto página a página.

    Levanta `ArquivoRecusado` quando o arquivo não serve, e `ErroExtracao` quando
    serve mas não pôde ser lido — a distinção importa para a interface saber se
    pede outro arquivo ou reporta uma falha.
    """
    caminho = Path(caminho)
    tipo = identificar(caminho)

    if tipo is TipoArquivo.PDF:
        paginas = extrair_pdf(caminho, permitir_ocr=permitir_ocr)
    else:
        texto = extrair_de_imagem(caminho)
        if not texto.strip():
            raise ErroExtracao(
                f"{caminho.name}: o OCR nao reconheceu texto nenhum na imagem."
            )
        paginas = [PaginaExtraida(numero=1, texto=texto, origem=OrigemTexto.OCR)]

    documento = DocumentoExtraido(
        nome_arquivo=caminho.name, tipo=tipo, paginas=paginas
    )
    log.info(
        "%s: %d paginas (%d por OCR, %d vazias)",
        documento.nome_arquivo, documento.total_paginas,
        documento.paginas_por_ocr, documento.paginas_vazias,
    )
    return documento


def receber_varios(
    caminhos: list[Path | str], permitir_ocr: bool = True
) -> tuple[list[DocumentoExtraido], list[tuple[str, str]]]:
    """Processa vários documentos sem deixar um problema derrubar os demais (A.4).

    Devolve os documentos lidos e a lista de `(arquivo, motivo)` dos que falharam.
    Numa apresentação, um PDF corrompido no meio do lote não pode impedir a
    comparação dos outros dois.
    """
    lidos: list[DocumentoExtraido] = []
    falhas: list[tuple[str, str]] = []

    for caminho in caminhos:
        nome = Path(caminho).name
        try:
            lidos.append(receber(caminho, permitir_ocr=permitir_ocr))
        except (ArquivoRecusado, ErroExtracao) as exc:
            falhas.append((nome, str(exc)))
            log.error("%s ficou de fora: %s", nome, exc)

    return lidos, falhas
