"""Testes das extrações de exemplo.

Elas sustentam a interface antes de a extração real existir, então precisam estar
no formato final e cobrir todos os vereditos do motor — senão quem constrói a tela
descobre um caso só na integração.
"""

from __future__ import annotations

from app.domain.campos import carregar_campos
from app.domain.comparacao import Veredito, comparar
from app.domain.exemplos import APOLICES, carregar_exemplos

DICIONARIO = carregar_campos()


def test_exemplos_cobrem_o_dicionario_inteiro():
    """Cada apólice precisa responder por todos os campos — mesmo que a resposta
    seja "não trata do assunto"."""
    for apolice in APOLICES:
        ids = {c.campo_id for c in apolice.campos}
        assert ids == set(DICIONARIO.ids), f"{apolice.nome}: faltam {set(DICIONARIO.ids) - ids}"


def test_todo_campo_encontrado_e_rastreavel():
    """O exemplo tem de respeitar a regra que o sistema real segue: valor sem
    origem não deveria existir."""
    for apolice in APOLICES:
        for campo in apolice.campos:
            if campo.encontrado:
                assert campo.rastreavel, f"{apolice.nome}/{campo.campo_id} sem origem"


def test_exemplos_exercitam_todos_os_vereditos():
    """Se um veredito não aparece aqui, a interface não tem como exibi-lo antes da
    integração — e o caso só surge na véspera."""
    resultado = comparar(carregar_exemplos(), DICIONARIO)
    presentes = {d.veredito for d in resultado.diferencas}
    esperados = {
        Veredito.IGUAL,
        Veredito.DIFERENTE,
        Veredito.REDACAO_DIVERGENTE,
        Veredito.AUSENTE_EM_ALGUMA,
    }
    assert esperados <= presentes, f"faltam: {esperados - presentes}"


def test_mesmo_limite_em_formatos_diferentes_sai_como_igual():
    """O caso que motivou comparar por tipo: R$ 10.000.000,00 e R$ 10 milhões."""
    resultado = comparar(carregar_exemplos(), DICIONARIO)
    d = next(d for d in resultado.diferencas if d.campo.id == "limite_maximo_indenizacao")
    assert d.veredito is Veredito.IGUAL


def test_exemplos_declaram_que_nao_vieram_de_um_modelo():
    """Para não entrarem no relatório como resultado do sistema."""
    for apolice in APOLICES:
        assert "sem LLM" in (apolice.modelo_usado or "")


def test_carregar_exemplos_devolve_copia():
    """Quem mexer nos dados da demonstração não pode contaminar os outros testes."""
    copia = carregar_exemplos()
    copia[0].campos[0].valor = "alterado"
    assert APOLICES[0].campos[0].valor != "alterado"
