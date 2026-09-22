"""Teste de integração contra as condições gerais reais em `data/apolices/`.

Os outros testes simulam a extração; este roda de ponta a ponta sobre os PDFs que
o corretor do grupo reuniu. É o que garante que a frente A funciona com o documento
de verdade, e não só com o caso construído para passar.

Se as apólices não estiverem presentes, os testes são pulados em vez de falhar —
quem clonar o repositório sem os documentos ainda consegue rodar a suíte.
"""

from __future__ import annotations

import pytest

from app.config import APOLICES_DIR
from app.domain.ingestao import receber
from app.schemas import OrigemTexto, separar_por_marcador

APOLICES = sorted(APOLICES_DIR.glob("*.pdf")) if APOLICES_DIR.is_dir() else []

pytestmark = pytest.mark.skipif(
    not APOLICES, reason="nenhuma apolice em data/apolices/"
)


@pytest.fixture(scope="module", params=[p.name for p in APOLICES])
def documento(request):
    caminho = APOLICES_DIR / request.param
    return receber(caminho)


def test_apolice_rende_texto_em_todas_as_paginas(documento):
    """Condições gerais são PDF nativo: nenhuma página deveria sair vazia."""
    assert documento.total_paginas > 20, "apolice curta demais para ser condicoes gerais"
    assert documento.paginas_vazias == 0


def test_apolice_nao_precisa_de_ocr(documento):
    """Se isto falhar, os documentos mudaram e a frente A ficou mais cara."""
    assert documento.paginas_por_ocr == 0
    assert all(p.origem is OrigemTexto.PDF_NATIVO for p in documento.paginas)


def test_numeracao_e_continua(documento):
    numeros = [p.numero for p in documento.paginas]
    assert numeros == list(range(1, documento.total_paginas + 1))


def test_todo_trecho_real_e_localizavel(documento):
    """A promessa da rastreabilidade, contra o documento inteiro: um trecho tirado
    do miolo de qualquer página tem de ser encontrado naquela página.

    O trecho vem do meio e não do começo porque o começo é cabeçalho — veja o teste
    seguinte.
    """
    for pagina in documento.paginas[::10]:
        palavras = pagina.texto.split()
        if len(palavras) < 60:
            continue
        meio = len(palavras) // 2
        trecho = " ".join(palavras[meio:meio + 12])
        assert pagina.numero in documento.paginas_de(trecho)


def test_cabecalho_repetido_nao_passa_por_localizacao(documento):
    """O achado que só apareceu com documento real: o cabeçalho das condições
    gerais se repete em todas as páginas.

    Se `pagina_de` respondesse a primeira ocorrência, uma citação de cabeçalho
    pareceria uma localização precisa — e a frente B registraria a página errada
    como origem de um campo.
    """
    primeira = " ".join(documento.paginas[0].texto.split()[:8])
    if len(documento.paginas_de(primeira)) <= 3:
        pytest.skip("este documento nao repete o cabecalho")

    assert documento.trecho_repetido(primeira)
    assert documento.pagina_de(primeira) is None


def test_marcadores_sobrevivem_a_ida_e_volta(documento):
    voltou = separar_por_marcador(documento.texto_com_marcadores)
    assert len(voltou) == documento.total_paginas
    for pagina in documento.paginas:
        if pagina.texto.strip():
            assert voltou[pagina.numero].strip() == pagina.texto.strip()


def test_tamanho_cabe_numa_passagem_do_modelo(documento):
    """A decisão de não fragmentar o documento depende disto continuar verdade.

    Se uma apólice passar de ~200 mil tokens, a frente B precisa repensar a
    estratégia — o limite prático de contexto deixa de ser confortável.
    """
    tokens = len(documento.texto_com_marcadores.split()) / 0.75
    assert tokens < 200_000, f"apolice com ~{int(tokens)} tokens: rever a estrategia de B.2"


def test_campos_do_especialista_ocorrem_no_documento():
    """A lista do Paulo Henrique tem de valer para os documentos reais, não só no papel."""
    import yaml

    from app.config import DATA_DIR

    campos = yaml.safe_load((DATA_DIR / "campos_do.yaml").read_text(encoding="utf-8"))
    textos = [receber(c).texto_completo.lower() for c in APOLICES]

    ausentes = []
    for campo in campos["campos"]:
        termos = [campo["rotulo"], *campo["sinonimos"]]
        # basta o campo aparecer, sob qualquer um dos seus nomes, em algum documento
        achou = any(
            t.lower() in texto for texto in textos for t in termos
        )
        if not achou:
            ausentes.append(campo["id"])

    assert not ausentes, f"campos que nao ocorrem em nenhuma apolice: {ausentes}"
