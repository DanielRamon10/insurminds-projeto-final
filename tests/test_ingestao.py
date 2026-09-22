"""Testes da recepção de documentos (A.1) e da tolerância a falha (A.4).

Os casos de recusa usam arquivos temporários de verdade, porque é o comportamento
do sistema de arquivos que está sendo testado. A extração em si é simulada, para
os testes não dependerem de um PDF de 70 páginas.
"""

from __future__ import annotations

import pytest

from app.clients import extracao
from app.clients.extracao import ErroExtracao
from app.domain import ingestao
from app.domain.ingestao import ArquivoRecusado, identificar, receber, receber_varios
from app.schemas import OrigemTexto, PaginaExtraida, TipoArquivo


@pytest.fixture
def pdf_falso(tmp_path):
    """Um arquivo com extensão .pdf e conteúdo qualquer; a extração é simulada."""
    caminho = tmp_path / "apolice.pdf"
    caminho.write_bytes(b"%PDF-1.7 conteudo simulado")
    return caminho


def simular_extracao(monkeypatch, paginas: list[PaginaExtraida]):
    monkeypatch.setattr(
        ingestao, "extrair_pdf", lambda caminho, permitir_ocr=True: paginas
    )


# ---------------------------------------------------------------------------
# A.1 — o que entra e o que é recusado
# ---------------------------------------------------------------------------


def test_aceita_pdf(pdf_falso):
    assert identificar(pdf_falso) is TipoArquivo.PDF


@pytest.mark.parametrize("extensao", [".png", ".jpg", ".jpeg", ".tiff", ".webp"])
def test_aceita_imagem(tmp_path, extensao):
    caminho = tmp_path / f"apolice{extensao}"
    caminho.write_bytes(b"conteudo")
    assert identificar(caminho) is TipoArquivo.IMAGEM


def test_recusa_formato_desconhecido_dizendo_o_que_aceita(tmp_path):
    """A mensagem tem de resolver a dúvida de quem errou o arquivo."""
    caminho = tmp_path / "apolice.docx"
    caminho.write_bytes(b"conteudo")
    with pytest.raises(ArquivoRecusado) as erro:
        identificar(caminho)
    assert ".docx" in str(erro.value)
    assert ".pdf" in str(erro.value)


def test_recusa_arquivo_vazio(tmp_path):
    caminho = tmp_path / "vazio.pdf"
    caminho.write_bytes(b"")
    with pytest.raises(ArquivoRecusado, match="vazio"):
        identificar(caminho)


def test_recusa_arquivo_inexistente(tmp_path):
    with pytest.raises(ArquivoRecusado, match="nao encontrado"):
        identificar(tmp_path / "nao_existe.pdf")


def test_recusa_diretorio(tmp_path):
    pasta = tmp_path / "pasta.pdf"
    pasta.mkdir()
    with pytest.raises(ArquivoRecusado, match="nao e um arquivo"):
        identificar(pasta)


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def test_documento_lido_preserva_numero_de_pagina(pdf_falso, monkeypatch):
    simular_extracao(monkeypatch, [
        PaginaExtraida(numero=1, texto="primeira pagina da apolice", origem=OrigemTexto.PDF_NATIVO),
        PaginaExtraida(numero=2, texto="segunda pagina da apolice", origem=OrigemTexto.PDF_NATIVO),
    ])
    d = receber(pdf_falso)
    assert d.total_paginas == 2
    assert d.nome_arquivo == "apolice.pdf"
    assert d.pagina_de("segunda pagina") == 2


def test_imagem_vira_documento_de_uma_pagina(tmp_path, monkeypatch):
    caminho = tmp_path / "pagina.png"
    caminho.write_bytes(b"imagem")
    monkeypatch.setattr(
        ingestao, "extrair_de_imagem", lambda c: "texto reconhecido pelo ocr na imagem"
    )
    d = receber(caminho)
    assert d.total_paginas == 1
    assert d.paginas[0].origem is OrigemTexto.OCR
    assert d.tipo is TipoArquivo.IMAGEM


def test_imagem_sem_texto_reconhecido_falha_claro(tmp_path, monkeypatch):
    caminho = tmp_path / "pagina.png"
    caminho.write_bytes(b"imagem")
    monkeypatch.setattr(ingestao, "extrair_de_imagem", lambda c: "   ")
    with pytest.raises(ErroExtracao, match="nao reconheceu texto"):
        receber(caminho)


# ---------------------------------------------------------------------------
# A.4 — uma falha não derruba o lote
# ---------------------------------------------------------------------------


def test_lote_continua_apesar_de_um_arquivo_ruim(tmp_path, monkeypatch):
    """Numa apresentação, um PDF corrompido não pode impedir a comparação dos outros."""
    bom1 = tmp_path / "boa1.pdf"
    bom2 = tmp_path / "boa2.pdf"
    ruim = tmp_path / "ruim.docx"
    for c in (bom1, bom2, ruim):
        c.write_bytes(b"conteudo")

    simular_extracao(monkeypatch, [
        PaginaExtraida(numero=1, texto="conteudo da apolice", origem=OrigemTexto.PDF_NATIVO)
    ])

    lidos, falhas = receber_varios([bom1, ruim, bom2])
    assert [d.nome_arquivo for d in lidos] == ["boa1.pdf", "boa2.pdf"]
    assert [nome for nome, _ in falhas] == ["ruim.docx"]


def test_falha_de_extracao_tambem_e_isolada(tmp_path, monkeypatch):
    bom = tmp_path / "boa.pdf"
    quebrado = tmp_path / "quebrado.pdf"
    for c in (bom, quebrado):
        c.write_bytes(b"conteudo")

    def extrair(caminho, permitir_ocr=True):
        if caminho.name == "quebrado.pdf":
            raise ErroExtracao("stream terminou inesperadamente")
        return [PaginaExtraida(numero=1, texto="conteudo bom", origem=OrigemTexto.PDF_NATIVO)]

    monkeypatch.setattr(ingestao, "extrair_pdf", extrair)

    lidos, falhas = receber_varios([bom, quebrado])
    assert len(lidos) == 1
    assert "stream terminou" in falhas[0][1]


def test_lote_vazio_nao_quebra():
    assert receber_varios([]) == ([], [])


# ---------------------------------------------------------------------------
# A.3 — OCR ausente é problema do operador, e a mensagem tem de dizer isso
# ---------------------------------------------------------------------------


def test_mensagem_de_ocr_ausente_explica_como_instalar(monkeypatch):
    monkeypatch.setattr(extracao, "caminho_tesseract", lambda: None)
    with pytest.raises(extracao.OCRIndisponivel) as erro:
        extracao._exigir_ocr()
    mensagem = str(erro.value)
    assert "Tesseract nao encontrado" in mensagem
    assert "TESSERACT_CMD" in mensagem  # a saída para quem já tem, fora do PATH
