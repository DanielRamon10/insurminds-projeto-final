"""Testes dos contratos de dados entre as frentes.

O foco é a rastreabilidade: se `pagina_de` errar, a frente B não tem como provar
de onde veio um campo, e a tarefa B.3 perde o sentido.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    DocumentoExtraido,
    OrigemTexto,
    PaginaExtraida,
    TipoArquivo,
    separar_por_marcador,
)


def pagina(numero: int, texto: str, origem=OrigemTexto.PDF_NATIVO) -> PaginaExtraida:
    return PaginaExtraida(numero=numero, texto=texto, origem=origem)


def documento(*paginas: PaginaExtraida) -> DocumentoExtraido:
    return DocumentoExtraido(
        nome_arquivo="apolice.pdf", tipo=TipoArquivo.PDF, paginas=list(paginas)
    )


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------


def test_pagina_comeca_em_um():
    """Numeração como o leitor conta, não como o índice do array."""
    with pytest.raises(ValidationError):
        PaginaExtraida(numero=0, texto="x", origem=OrigemTexto.PDF_NATIVO)


def test_pagina_quase_vazia_e_considerada_vazia():
    assert pagina(1, "   \n  ").vazia
    assert pagina(1, "logotipo").vazia


def test_pagina_de_rosto_curta_nao_e_descartada():
    """Uma capa legítima tem poucas palavras — perdê-la custaria o número da apólice."""
    assert not pagina(1, "Apolice numero 15414.900832/2017-90 — Condicoes Gerais").vazia


# ---------------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------------


def test_paginas_fora_de_ordem_sao_recusadas():
    with pytest.raises(ValidationError, match="ordem crescente"):
        documento(pagina(2, "segunda"), pagina(1, "primeira"))


def test_pagina_repetida_e_recusada():
    with pytest.raises(ValidationError, match="repetido"):
        documento(pagina(1, "a"), pagina(1, "b"))


def test_contagens_do_documento():
    d = documento(
        pagina(1, "texto da primeira pagina, com conteudo suficiente"),
        pagina(2, "  ", origem=OrigemTexto.OCR),
        pagina(3, "reconhecido por ocr nesta pagina aqui", origem=OrigemTexto.OCR),
    )
    assert d.total_paginas == 3
    assert d.paginas_por_ocr == 2
    assert d.paginas_vazias == 1


def test_pagina_por_numero():
    d = documento(pagina(1, "primeira"), pagina(2, "segunda"))
    assert d.pagina(2).texto == "segunda"
    assert d.pagina(9) is None


# ---------------------------------------------------------------------------
# Rastreabilidade — o que sustenta a tarefa B.3
# ---------------------------------------------------------------------------


def test_encontra_a_pagina_de_um_trecho():
    d = documento(
        pagina(1, "Das definicoes gerais desta apolice"),
        pagina(2, "A franquia sera de R$ 50.000,00 por reclamacao"),
    )
    assert d.pagina_de("franquia sera de R$ 50.000,00") == 2


def test_citacao_reescrita_pelo_modelo_ainda_casa():
    """O modelo devolve o trecho com outra caixa e outro espaçamento; a página
    tem de ser encontrada do mesmo jeito."""
    d = documento(pagina(7, "O Limite Máximo de Indenização é de R$ 10.000.000,00"))
    assert d.pagina_de("limite  maximo   de\n indenizacao") == 7
    assert d.pagina_de("LIMITE MÁXIMO DE INDENIZAÇÃO") == 7


def test_trecho_inventado_nao_casa_com_pagina_nenhuma():
    """A contraprova do guardrail: se o modelo inventar a citação, isto denuncia."""
    d = documento(pagina(1, "texto real da apolice"))
    assert d.pagina_de("clausula que nao existe no documento") is None


def test_trecho_vazio_nao_casa():
    d = documento(pagina(1, "qualquer texto"))
    assert d.pagina_de("   ") is None


# ---------------------------------------------------------------------------
# Texto entregue ao modelo
# ---------------------------------------------------------------------------


def test_texto_com_marcadores_anuncia_cada_pagina():
    d = documento(pagina(1, "primeira"), pagina(2, "segunda"))
    texto = d.texto_com_marcadores
    assert "=== PÁGINA 1 ===" in texto
    assert "=== PÁGINA 2 ===" in texto
    assert texto.index("primeira") < texto.index("=== PÁGINA 2 ===")


def test_marcadores_podem_ser_desfeitos():
    """Ida e volta sem perda: quem recebe o texto pronto consegue voltar à página."""
    d = documento(pagina(1, "conteudo da primeira"), pagina(2, "conteudo da segunda"))
    voltou = separar_por_marcador(d.texto_com_marcadores)
    assert voltou == {1: "conteudo da primeira", 2: "conteudo da segunda"}


def test_texto_completo_nao_tem_marcador():
    """Para contar tokens e buscar, sem o ruído dos marcadores."""
    d = documento(pagina(1, "abc"), pagina(2, "def"))
    assert "PÁGINA" not in d.texto_completo
    assert d.texto_completo == "abc\n\ndef"


# ---------------------------------------------------------------------------
# Trecho repetido — o caso que só apareceu com documento real
# ---------------------------------------------------------------------------


def test_cabecalho_repetido_nao_vira_localizacao():
    """Apólice repete cabeçalho em toda página. Responder a primeira ocorrência
    daria uma resposta certa e inútil — pior, faria a frente B registrar a página
    errada como origem de um campo."""
    cabecalho = "Processo SUSEP 15414.900832/2017-90"
    d = documento(*[
        pagina(n, f"{cabecalho}\nconteudo especifico da pagina {n}") for n in range(1, 9)
    ])
    assert d.trecho_repetido(cabecalho)
    assert d.pagina_de(cabecalho) is None
    assert len(d.paginas_de(cabecalho)) == 8


def test_trecho_em_poucas_paginas_ainda_localiza():
    """O limite é três: até aí ainda é uma localização utilizável."""
    d = documento(
        pagina(1, "a clausula de franquia aparece aqui"),
        pagina(2, "e tambem a clausula de franquia aqui"),
        pagina(3, "texto sem relacao nenhuma"),
    )
    assert d.pagina_de("clausula de franquia") == 1
    assert d.paginas_de("clausula de franquia") == [1, 2]
    assert not d.trecho_repetido("clausula de franquia")
