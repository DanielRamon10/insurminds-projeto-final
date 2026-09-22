"""Testes do motor de comparação (C.2 e C.3).

Nenhum toca a rede: o motor é determinístico de propósito, e é isso que permite
testá-lo inteiro sem cota de LLM.
"""

from __future__ import annotations

import pytest

from app.domain.campos import TipoCampo, carregar_campos
from app.domain.comparacao import (
    Veredito,
    comparar,
    equivalentes,
    prazo_em_dias,
    valor_monetario,
)
from app.schemas import ApoliceExtraida, CampoExtraido

DICIONARIO = carregar_campos()


def apolice(nome: str, **campos: str | None) -> ApoliceExtraida:
    """Apólice com os campos informados; o resto fica ausente."""
    return ApoliceExtraida(
        documento=f"{nome}.pdf",
        seguradora=nome,
        campos=[
            CampoExtraido(campo_id=cid, valor=valor, trecho_origem="trecho", pagina=1)
            for cid, valor in campos.items()
        ],
    )


# ---------------------------------------------------------------------------
# Leitura de valores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("R$ 10.000.000,00", 10_000_000.0),
        ("R$ 10 milhões", 10_000_000.0),
        ("10 milhoes de reais", 10_000_000.0),
        ("R$ 500 mil", 500_000.0),
        ("R$ 50.000,00", 50_000.0),
        ("R$ 1,5 milhão", 1_500_000.0),
        ("sem valor nenhum", None),
    ],
)
def test_le_valor_monetario(texto, esperado):
    assert valor_monetario(texto) == esperado


def test_mesmo_valor_escrito_de_dois_jeitos_nao_e_diferenca():
    """O falso positivo mais grosseiro que o motor poderia cometer."""
    assert equivalentes("R$ 10.000.000,00", "R$ 10 milhões", TipoCampo.VALOR_MONETARIO)


@pytest.mark.parametrize(
    "texto, dias",
    [("90 dias", 90), ("3 meses", 90), ("1 ano", 365), ("2 anos", 730), ("nada", None)],
)
def test_le_prazo(texto, dias):
    assert prazo_em_dias(texto) == dias


def test_prazo_equivalente_em_unidades_diferentes():
    assert equivalentes("90 dias", "3 meses", TipoCampo.PRAZO)
    assert not equivalentes("90 dias", "180 dias", TipoCampo.PRAZO)


def test_texto_identico_e_seguro_dizer_igual():
    assert equivalentes("Exclui danos ambientais", "exclui  DANOS ambientais", TipoCampo.TEXTO)


def test_texto_diferente_nao_e_julgado_pelo_motor():
    """O motor não afirma o que não verificou: duas redações distintas podem dizer
    a mesma coisa, e decidir isso é do redator (C.4)."""
    a = "Estão excluídos os danos decorrentes de poluição"
    b = "Não haverá cobertura para contaminação do meio ambiente"
    assert equivalentes(a, b, TipoCampo.TEXTO) is None


# ---------------------------------------------------------------------------
# Vereditos
# ---------------------------------------------------------------------------


def test_valores_diferentes_sao_diferenca():
    c = comparar([
        apolice("Chubb", limite_maximo_indenizacao="R$ 10.000.000,00"),
        apolice("AIG", limite_maximo_indenizacao="R$ 5.000.000,00"),
    ], DICIONARIO)
    d = next(d for d in c.diferencas if d.campo.id == "limite_maximo_indenizacao")
    assert d.veredito is Veredito.DIFERENTE
    assert d.relevante


def test_mesmo_valor_em_formatos_diferentes_nao_aparece_como_diferenca():
    c = comparar([
        apolice("Chubb", limite_maximo_indenizacao="R$ 10.000.000,00"),
        apolice("AIG", limite_maximo_indenizacao="R$ 10 milhões"),
    ], DICIONARIO)
    d = next(d for d in c.diferencas if d.campo.id == "limite_maximo_indenizacao")
    assert d.veredito is Veredito.IGUAL
    assert not d.relevante


def test_campo_ausente_numa_apolice_e_destacado():
    """Costuma ser a diferença que mais importa, e sumiria se ausente fosse
    tratado como 'vazio igual a vazio'."""
    c = comparar([
        apolice("Chubb", cobertura_investigacoes="Cobre custos de investigação"),
        apolice("AIG", limite_maximo_indenizacao="R$ 5.000.000,00"),
    ], DICIONARIO)
    d = next(d for d in c.diferencas if d.campo.id == "cobertura_investigacoes")
    assert d.veredito is Veredito.AUSENTE_EM_ALGUMA
    assert d.ausentes() == ["AIG"]


def test_campo_ausente_nas_duas_nao_e_diferenca_entre_elas():
    c = comparar([apolice("Chubb"), apolice("AIG")], DICIONARIO)
    d = next(d for d in c.diferencas if d.campo.id == "sublimites")
    assert d.veredito is Veredito.AUSENTE_EM_TODAS
    assert not d.relevante


def test_redacao_divergente_fica_para_o_redator():
    c = comparar([
        apolice("Chubb", exclusao_ambiental="Estão excluídos danos por poluição"),
        apolice("AIG", exclusao_ambiental="Sem cobertura para contaminação ambiental"),
    ], DICIONARIO)
    d = next(d for d in c.diferencas if d.campo.id == "exclusao_ambiental")
    assert d.veredito is Veredito.REDACAO_DIVERGENTE
    assert d.relevante


# ---------------------------------------------------------------------------
# Resultado completo
# ---------------------------------------------------------------------------


def test_compara_todo_o_dicionario_e_nao_so_o_que_veio():
    """Percorrer o dicionário é o que faz a ausência aparecer."""
    c = comparar([
        apolice("Chubb", limite_maximo_indenizacao="R$ 10.000.000,00"),
        apolice("AIG", limite_maximo_indenizacao="R$ 5.000.000,00"),
    ], DICIONARIO)
    assert len(c.diferencas) == len(DICIONARIO)


def test_relevantes_vem_com_ausencia_primeiro():
    c = comparar([
        apolice("Chubb",
                limite_maximo_indenizacao="R$ 10.000.000,00",
                sublimites="Sublimite de R$ 1 milhão para custos de defesa"),
        apolice("AIG", limite_maximo_indenizacao="R$ 5.000.000,00"),
    ], DICIONARIO)
    vereditos = [d.veredito for d in c.relevantes]
    assert vereditos[0] is Veredito.AUSENTE_EM_ALGUMA
    assert Veredito.DIFERENTE in vereditos


def test_a_justificativa_do_especialista_acompanha_a_diferenca():
    """É o texto que o relatório mostra para explicar o peso da diferença."""
    c = comparar([
        apolice("Chubb", sublimites="Sublimite de R$ 1 milhão"),
        apolice("AIG", sublimites="Sublimite de R$ 3 milhões"),
    ], DICIONARIO)
    d = next(d for d in c.diferencas if d.campo.id == "sublimites")
    assert "mesmo LMI" in d.porque_importa


def test_paginas_de_origem_acompanham_a_comparacao():
    """Sem isto a interface não consegue mostrar de onde cada valor veio (D.3)."""
    a = ApoliceExtraida(documento="a.pdf", seguradora="Chubb", campos=[
        CampoExtraido(campo_id="franquia", valor="R$ 50.000,00",
                      trecho_origem="a franquia sera de", pagina=12),
    ])
    b = ApoliceExtraida(documento="b.pdf", seguradora="AIG", campos=[
        CampoExtraido(campo_id="franquia", valor="R$ 80.000,00",
                      trecho_origem="retencao de", pagina=7),
    ])
    d = next(d for d in comparar([a, b], DICIONARIO).diferencas if d.campo.id == "franquia")
    assert d.paginas == {"Chubb": 12, "AIG": 7}


def test_comparar_exige_duas_apolices():
    with pytest.raises(ValueError, match="pelo menos duas"):
        comparar([apolice("Chubb")], DICIONARIO)


def test_recusa_apolices_com_o_mesmo_nome():
    """Senão uma sobrescreveria a outra no dicionário de valores, em silêncio."""
    with pytest.raises(ValueError, match="mesmo nome"):
        comparar([apolice("Chubb"), apolice("Chubb")], DICIONARIO)


def test_compara_mais_de_duas():
    c = comparar([
        apolice("Chubb", franquia="R$ 50.000,00"),
        apolice("AIG", franquia="R$ 50.000,00"),
        apolice("Allianz", franquia="R$ 90.000,00"),
    ], DICIONARIO)
    d = next(d for d in c.diferencas if d.campo.id == "franquia")
    assert d.veredito is Veredito.DIFERENTE
    assert len(d.valores) == 3
