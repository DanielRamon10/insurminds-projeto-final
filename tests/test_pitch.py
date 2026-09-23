"""Testes do gerador do pitch deck (E.3).

O deck é entregável avaliado e o nome do arquivo é literal, então há dois tipos
de teste aqui:

* **o arquivo** — gera de verdade num diretório temporário e confere que o
  `.pptx` abre, tem os slides, o formato 16:9 e nenhum slide vazio;
* **o conteúdo** — confere que os números escritos no deck batem com o que o
  código produz hoje. Sem isso, o corretor acrescenta um campo ao dicionário e o
  deck continua dizendo "15 campos" na frente da banca.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from pptx import Presentation  # noqa: E402

from app.domain.campos import carregar_campos  # noqa: E402
from app.domain.comparacao import Veredito, comparar  # noqa: E402
from app.domain.exemplos import carregar_exemplos  # noqa: E402
from app.interface.apresentacao import linhas_rastreabilidade  # noqa: E402
from scripts.gerar_pitch import CONTEUDO, DESTINO, montar  # noqa: E402


@pytest.fixture(scope="module")
def deck(tmp_path_factory):
    """O deck gerado uma vez, num diretório temporário."""
    caminho = tmp_path_factory.mktemp("pitch") / "InsurMinds_Projeto_Final.pptx"
    return montar(caminho)


def texto_do_deck(caminho: Path) -> str:
    apresentacao = Presentation(str(caminho))
    return "\n".join(
        forma.text_frame.text
        for slide in apresentacao.slides
        for forma in slide.shapes
        if forma.has_text_frame
    )


def slide_por_tipo(tipo: str) -> dict:
    return next(s for s in CONTEUDO if s["tipo"] == tipo)


# ---------------------------------------------------------------------------
# O arquivo
# ---------------------------------------------------------------------------


def test_nome_do_arquivo_e_o_exigido_pelo_enunciado():
    assert DESTINO.name == "InsurMinds_Projeto_Final.pptx"
    assert DESTINO.parent.name == "Projeto_Final_Artefatos"


def test_gera_um_pptx_valido_com_todos_os_slides(deck):
    apresentacao = Presentation(str(deck))
    assert len(apresentacao.slides) == len(CONTEUDO)
    assert len(apresentacao.slides) >= 12


def test_formato_de_apresentacao_e_16_9(deck):
    apresentacao = Presentation(str(deck))
    assert round(apresentacao.slide_width / apresentacao.slide_height, 2) == 1.78


def test_nenhum_slide_saiu_vazio(deck):
    """Um slide em branco no meio do deck só se descobre na hora de apresentar."""
    apresentacao = Presentation(str(deck))
    for numero, slide in enumerate(apresentacao.slides, start=1):
        textos = [f.text_frame.text for f in slide.shapes if f.has_text_frame]
        assert any(texto.strip() for texto in textos), f"slide {numero} saiu sem texto"


# ---------------------------------------------------------------------------
# O conteúdo
# ---------------------------------------------------------------------------


def test_o_deck_nomeia_todos_os_integrantes(deck):
    texto = texto_do_deck(deck)
    for nome in (
        "Daniel Ramon",
        "Paulo Henrique",
        "Nicole Paes",
        "Paulo Roberto",
        "Juliana Catarina",
    ):
        assert nome in texto, f"{nome} nao aparece no deck"


def test_a_capa_declara_a_entrega(deck):
    capa = Presentation(str(deck)).slides[0]
    texto = "\n".join(f.text_frame.text for f in capa.shapes if f.has_text_frame)
    assert "06/10/2026" in texto
    assert "Insurminds" in texto


def test_o_deck_declara_que_a_extracao_ainda_esta_em_desenvolvimento(deck):
    """O deck não pode vender como pronto o que não está."""
    assert "desenvolvimento" in texto_do_deck(deck)


def test_o_numero_de_campos_do_deck_bate_com_o_dicionario():
    dicionario = carregar_campos()
    slide = next(s for s in CONTEUDO if s.get("titulo", "").startswith("O que comparar"))
    valores = [numero[0] for numero in slide["numeros"]]
    assert str(len(dicionario)) in valores, (
        f"o deck diz {valores} e o dicionario tem {len(dicionario)} campos"
    )


def test_os_numeros_do_slide_de_resultados_batem_com_o_motor():
    """O slide de resultados não pode envelhecer em relação ao código."""
    apolices = carregar_exemplos()
    dicionario = carregar_campos()
    resultado = comparar(apolices, dicionario)
    linhas = linhas_rastreabilidade(resultado, apolices)

    slide = next(s for s in CONTEUDO if s.get("titulo") == "O resultado, campo a campo")
    valores = [numero[0] for numero in slide["numeros"]]

    for veredito in (
        Veredito.AUSENTE_EM_ALGUMA,
        Veredito.DIFERENTE,
        Veredito.REDACAO_DIVERGENTE,
    ):
        assert str(resultado.resumo[veredito.value]) in valores, (
            f"o deck nao cita o total de '{veredito.value}'"
        )
    assert str(len(linhas)) in valores


def test_todo_slide_de_conteudo_tem_titulo_e_kicker():
    for dados in CONTEUDO:
        if dados["tipo"] == "capa":
            continue
        assert dados["kicker"].strip()
        assert dados["titulo"].strip()


def test_o_slide_de_arquitetura_cobre_as_quatro_frentes():
    slide = slide_por_tipo("fluxo")
    siglas = [etapa[0] for etapa in slide["etapas"]]
    assert siglas == ["A", "B", "C", "D"]


def test_o_slide_de_limites_avisa_do_risco_do_projeto():
    """A limitação mais perigosa é a extração inventar valor."""
    slide = next(s for s in CONTEUDO if s.get("kicker") == "limitações conhecidas")
    texto = " ".join(titulo + corpo for _, titulo, corpo in slide["topicos"])
    assert "LLM" in texto or "modelo" in texto