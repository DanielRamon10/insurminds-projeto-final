"""Testes do redator do relatório comparativo (C.4).

A regra que estes testes defendem: **o redator não inventa diferenças.** A resposta
do modelo é montada à mão, simulando o que um modelo faz de errado — diferença sem
prova, citação que não está no trecho, número inventado na explicação.
"""

from __future__ import annotations

import json

import pytest

from app.agents.llm import LLMIndisponivel, RespostaLLM
from app.agents.redator import Leitura, montar_prompt, redigir
from app.domain.comparacao import Veredito, comparar
from app.domain.exemplos import carregar_exemplos

#: Nos exemplos, a Chubb diz que os custos de defesa "integram" o limite e a AIG
#: que são pagos "em acrescimo" a ele — uma diferença real de conteúdo.
DEFESA_DIFERENTE = {
    "leitura": "diferente_no_conteudo",
    "explicacao": "Na Chubb a defesa consome o limite; na AIG ela é paga por fora.",
    "evidencias": [
        {"apolice": "Chubb", "citacao": "os custos de defesa integram o Limite Maximo"},
        {"apolice": "AIG", "citacao": "serao pagas em acrescimo ao Limite de Garantia"},
    ],
}


@pytest.fixture
def apolices():
    return carregar_exemplos()


@pytest.fixture
def comparacao(apolices):
    return comparar(apolices)


def modelo_que_responde(analises: dict | str):
    chamadas = []

    def gerar(prompt: str, json: bool = False) -> RespostaLLM:
        chamadas.append(prompt)
        texto = analises if isinstance(analises, str) else _json({"analises": analises})
        return RespostaLLM(texto=texto, provedor="teste", modelo="falso",
                           tokens_entrada=3000, tokens_saida=500)

    gerar.chamadas = chamadas
    return gerar


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def redigir_com(comparacao, apolices, analises):
    return redigir(comparacao, apolices, gerar=modelo_que_responde(analises))


# ---------------------------------------------------------------------------
# O que vai ao modelo
# ---------------------------------------------------------------------------


def test_so_redacao_divergente_vai_ao_modelo(comparacao, apolices):
    divergentes = [d.campo for d in comparacao.por_veredito(Veredito.REDACAO_DIVERGENTE)]
    analises = [a for a in redigir(comparacao, apolices, usar_llm=False).analises
                if a.diferenca.veredito is Veredito.REDACAO_DIVERGENTE]
    prompt = montar_prompt(analises, comparacao.apolices)

    for campo in divergentes:
        assert f'"{campo.id}"' in prompt
    # franquia é DIFERENTE (valor): o motor já resolveu, não gasta token
    assert '"franquia"' not in prompt


def test_modelo_le_o_trecho_literal_nao_so_o_resumo(comparacao, apolices):
    gerar = modelo_que_responde({})
    redigir(comparacao, apolices, gerar=gerar)
    assert "as despesas de defesa serao pagas em acrescimo ao Limite de Garantia" in gerar.chamadas[0]


def test_sem_redacao_divergente_nao_chama_o_modelo(apolices):
    iguais = [a.model_copy(deep=True) for a in apolices]
    for campo in iguais[1].campos:
        campo.valor = iguais[0].campo(campo.campo_id).valor
    gerar = modelo_que_responde({})
    redigir(comparar(iguais), iguais, gerar=gerar)
    assert gerar.chamadas == []


def test_sem_llm_nao_chama_o_modelo(comparacao, apolices):
    gerar = modelo_que_responde({})
    r = redigir(comparacao, apolices, gerar=gerar, usar_llm=False)
    assert gerar.chamadas == []
    assert r.aviso


# ---------------------------------------------------------------------------
# Não inventar diferenças
# ---------------------------------------------------------------------------


def test_diferenca_com_evidencia_conferida_e_aceita(comparacao, apolices):
    r = redigir_com(comparacao, apolices, {"custos_defesa": DEFESA_DIFERENTE})
    a = r.analise("custos_defesa")

    assert a.leitura is Leitura.DIFERENTE
    assert len(a.evidencias) == 2
    assert a.ressalvas == ()
    assert r.modelo_usado == "teste/falso"


def test_diferenca_sem_evidencia_vira_inconclusivo(comparacao, apolices):
    sem_prova = {**DEFESA_DIFERENTE, "evidencias": []}
    a = redigir_com(comparacao, apolices, {"custos_defesa": sem_prova}).analise("custos_defesa")

    assert a.leitura is Leitura.INCONCLUSIVO
    assert a.explicacao is None, "a explicacao de uma diferenca nao provada nao pode aparecer"
    assert "sem evidencia" in a.ressalvas[-1]


def test_diferenca_com_prova_de_uma_apolice_so_vira_inconclusivo(comparacao, apolices):
    """Achado do teste real: o modelo citava um ponto de uma apólice que o recorte
    da outra não cobria, e chamava isso de diferença. Sem contraste, não é."""
    um_lado = {**DEFESA_DIFERENTE, "evidencias": DEFESA_DIFERENTE["evidencias"][:1]}
    a = redigir_com(comparacao, apolices, {"custos_defesa": um_lado}).analise("custos_defesa")

    assert a.leitura is Leitura.INCONCLUSIVO
    assert a.explicacao is None
    assert "duas apolices" in a.ressalvas[-1]


def test_prompt_avisa_que_o_trecho_e_um_recorte(comparacao, apolices):
    gerar = modelo_que_responde({})
    redigir(comparacao, apolices, gerar=gerar)
    assert "RECORTE" in gerar.chamadas[0]


def test_evidencia_que_nao_esta_no_trecho_e_recusada(comparacao, apolices):
    inventada = {
        **DEFESA_DIFERENTE,
        "evidencias": [{"apolice": "AIG", "citacao": "a defesa tem limite proprio de R$ 2 milhoes"}],
    }
    a = redigir_com(comparacao, apolices, {"custos_defesa": inventada}).analise("custos_defesa")

    assert a.leitura is Leitura.INCONCLUSIVO
    assert any("nao esta no trecho" in r for r in a.ressalvas)


def test_evidencia_atribuida_a_apolice_errada_e_recusada(comparacao, apolices):
    """A frase existe, mas na outra apólice: trocar a origem é inventar a diferença."""
    trocada = {
        **DEFESA_DIFERENTE,
        "evidencias": [{"apolice": "AIG", "citacao": "os custos de defesa integram o Limite Maximo"}],
    }
    a = redigir_com(comparacao, apolices, {"custos_defesa": trocada}).analise("custos_defesa")
    assert a.leitura is Leitura.INCONCLUSIVO


def test_numero_inventado_na_explicacao_derruba_a_analise(comparacao, apolices):
    com_numero = {**DEFESA_DIFERENTE,
                  "explicacao": "Na AIG a defesa tem limite extra de R$ 2.000.000,00."}
    a = redigir_com(comparacao, apolices, {"custos_defesa": com_numero}).analise("custos_defesa")

    assert a.leitura is Leitura.INCONCLUSIVO
    assert a.explicacao is None
    assert "2.000.000,00" in a.ressalvas[-1]


def test_equivalente_e_aceito(comparacao, apolices):
    equivalente = {
        "leitura": "equivalente",
        "explicacao": "As duas excluem danos de poluição ao meio ambiente.",
        "evidencias": [],
    }
    a = redigir_com(comparacao, apolices, {"exclusao_ambiental": equivalente}).analise(
        "exclusao_ambiental"
    )
    assert a.leitura is Leitura.EQUIVALENTE
    assert a.explicacao


@pytest.mark.parametrize("bruta", [None, {"leitura": "talvez"}, "texto solto"])
def test_resposta_ausente_ou_estranha_vira_inconclusivo(comparacao, apolices, bruta):
    analises = {} if bruta is None else {"custos_defesa": bruta}
    a = redigir_com(comparacao, apolices, analises).analise("custos_defesa")
    assert a.leitura is Leitura.INCONCLUSIVO


def test_campo_fora_da_redacao_divergente_nao_e_reclassificado(comparacao, apolices):
    """O modelo não pode reabrir o que o motor decidiu sem LLM."""
    r = redigir_com(comparacao, apolices, {"franquia": DEFESA_DIFERENTE})
    assert r.analise("franquia").leitura is None
    assert r.analise("franquia").diferenca.veredito is Veredito.DIFERENTE


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def test_llm_indisponivel_ainda_gera_relatorio(comparacao, apolices):
    def gerar(prompt, json=False):
        raise LLMIndisponivel("todos os provedores falharam:\n  google: 429")

    r = redigir(comparacao, apolices, gerar=gerar)
    texto = r.markdown()

    assert "indisponivel" in r.aviso
    assert "Atenção" in texto
    assert "Franquia" in texto  # o que o motor decidiu continua no relatório
    assert all(a.leitura is None for a in r.analises)


def test_resposta_fora_do_formato_ainda_gera_relatorio(comparacao, apolices):
    r = redigir_com(comparacao, apolices, "desculpe, nao consegui")
    assert "fora do formato" in r.aviso
    assert r.resposta_llm == "desculpe, nao consegui"


def test_comparacao_sem_a_extracao_correspondente_e_recusada(comparacao, apolices):
    with pytest.raises(ValueError, match="sem a extracao"):
        redigir(comparacao, apolices[:1], usar_llm=False)


# ---------------------------------------------------------------------------
# Texto final
# ---------------------------------------------------------------------------


def test_relatorio_traz_evidencias_paginas_e_porque_importa(comparacao, apolices):
    texto = redigir_com(comparacao, apolices, {"custos_defesa": DEFESA_DIFERENTE}).markdown()

    assert "## Cláusulas com efeito diferente" in texto
    assert '> AIG: "serao pagas em acrescimo ao Limite de Garantia"' in texto
    assert "(p. 13)" in texto
    assert "*Por que importa:*" in texto
    assert "teste/falso" in texto


def test_resumo_aponta_as_diferencas_comprovadas(comparacao, apolices):
    texto = redigir_com(comparacao, apolices, {"custos_defesa": DEFESA_DIFERENTE}).markdown()
    resumo = texto.split("\n")[2]
    assert "Custos de Defesa" in resumo
    assert "Franquia" in resumo


def test_resumo_avisa_quando_ha_clausulas_nao_lidas(comparacao, apolices):
    texto = redigir(comparacao, apolices, usar_llm=False).markdown()
    assert "não foram lidas" in texto.split("\n")[2]
