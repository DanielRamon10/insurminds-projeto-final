"""Testes do armazenamento (C.1).

O que mais importa aqui é a rastreabilidade sobreviver à ida e volta do banco:
guardar só o valor e perder a página de origem esvaziaria a tarefa B.3.
"""

from __future__ import annotations

import pytest

from app.domain.armazenamento import Banco
from app.schemas import ApoliceExtraida, CampoExtraido


@pytest.fixture
def banco(tmp_path):
    return Banco(tmp_path / "teste.db")


def apolice(documento="chubb.pdf", seguradora="Chubb", **campos) -> ApoliceExtraida:
    return ApoliceExtraida(
        documento=documento,
        seguradora=seguradora,
        modelo_usado="gemini-3.6-flash",
        campos=[
            CampoExtraido(
                campo_id=cid, valor=valor,
                trecho_origem=f"trecho de {cid}", pagina=10,
                paginas_possiveis=[10],
            )
            for cid, valor in campos.items()
        ],
    )


def test_salva_e_carrega_de_volta(banco):
    banco.salvar(apolice(limite_maximo_indenizacao="R$ 10.000.000,00"))
    lida = banco.carregar("chubb.pdf")

    assert lida.seguradora == "Chubb"
    assert lida.modelo_usado == "gemini-3.6-flash"
    assert lida.campo("limite_maximo_indenizacao").valor == "R$ 10.000.000,00"


def test_rastreabilidade_sobrevive_ao_banco(banco):
    """Se isto falhar, guardar a apólice custa exatamente a prova de origem."""
    banco.salvar(ApoliceExtraida(
        documento="aig.pdf", seguradora="AIG",
        campos=[CampoExtraido(
            campo_id="franquia", valor="R$ 50.000,00",
            trecho_origem="a franquia sera de R$ 50.000,00 por reclamacao",
            pagina=12, paginas_possiveis=[12, 45],
            observacao="valor aparece tambem no quadro de apolice",
        )],
    ))
    campo = banco.carregar("aig.pdf").campo("franquia")

    assert campo.pagina == 12
    assert campo.paginas_possiveis == [12, 45]
    assert "franquia sera de" in campo.trecho_origem
    assert campo.observacao == "valor aparece tambem no quadro de apolice"
    assert campo.rastreavel


def test_campo_nao_encontrado_continua_nulo(banco):
    """`None` significa "a apólice não trata do assunto" e não pode virar string
    vazia no banco — a comparação distingue os dois casos."""
    banco.salvar(ApoliceExtraida(
        documento="x.pdf",
        campos=[CampoExtraido(campo_id="sublimites", valor=None)],
    ))
    campo = banco.carregar("x.pdf").campo("sublimites")
    assert campo.valor is None
    assert not campo.encontrado


def test_regravar_substitui_em_vez_de_duplicar(banco):
    """Reprocessar depois de melhorar o prompt é rotina; acumular versões faria a
    comparação escolher uma ao acaso."""
    banco.salvar(apolice(franquia="R$ 50.000,00"))
    banco.salvar(apolice(franquia="R$ 80.000,00", vigencia="12 meses"))

    assert len(banco.listar()) == 1
    lida = banco.carregar("chubb.pdf")
    assert lida.campo("franquia").valor == "R$ 80.000,00"
    assert lida.campo("vigencia") is not None


def test_regravar_apaga_campo_que_sumiu(banco):
    """A segunda extração é a verdade: um campo que ela não achou não pode
    continuar no banco vindo da anterior."""
    banco.salvar(apolice(franquia="R$ 50.000,00", sublimites="R$ 1 milhao"))
    banco.salvar(apolice(franquia="R$ 50.000,00"))

    assert banco.carregar("chubb.pdf").campo("sublimites") is None


def test_carregar_o_que_nao_existe_devolve_none(banco):
    assert banco.carregar("inexistente.pdf") is None
    assert not banco.tem("inexistente.pdf")


def test_listar_resume_o_que_esta_guardado(banco):
    banco.salvar(apolice("chubb.pdf", "Chubb", franquia="R$ 50.000,00"))
    banco.salvar(ApoliceExtraida(
        documento="aig.pdf", seguradora="AIG",
        campos=[
            CampoExtraido(campo_id="franquia", valor="R$ 80.000,00"),
            CampoExtraido(campo_id="sublimites", valor=None),
        ],
    ))

    por_documento = {l["documento"]: l for l in banco.listar()}
    assert por_documento["aig.pdf"]["total_campos"] == 2
    assert por_documento["aig.pdf"]["encontrados"] == 1
    assert por_documento["chubb.pdf"]["seguradora"] == "Chubb"


def test_carregar_varias_ignora_as_que_faltam(banco):
    banco.salvar(apolice("chubb.pdf", "Chubb", franquia="R$ 50.000,00"))
    lidas = banco.carregar_varias(["chubb.pdf", "nao_existe.pdf"])
    assert [a.nome for a in lidas] == ["Chubb"]


def test_apagar_leva_os_campos_junto(banco):
    banco.salvar(apolice(franquia="R$ 50.000,00"))
    assert banco.apagar("chubb.pdf")
    assert banco.carregar("chubb.pdf") is None
    assert banco.listar() == []


def test_apagar_o_que_nao_existe_nao_quebra(banco):
    assert not banco.apagar("fantasma.pdf")


def test_banco_novo_comeca_vazio(banco):
    assert banco.listar() == []


def test_reabrir_o_mesmo_arquivo_mantem_os_dados(tmp_path):
    caminho = tmp_path / "persistente.db"
    Banco(caminho).salvar(apolice(franquia="R$ 50.000,00"))

    outro = Banco(caminho)  # como se fosse outra execução do programa
    assert outro.carregar("chubb.pdf").campo("franquia").valor == "R$ 50.000,00"


def test_comparacao_funciona_com_apolices_vindas_do_banco(banco):
    """A integração que importa: o que sai do banco alimenta o motor de comparação."""
    from app.domain.campos import carregar_campos
    from app.domain.comparacao import Veredito, comparar

    banco.salvar(apolice("chubb.pdf", "Chubb", limite_maximo_indenizacao="R$ 10 milhões"))
    banco.salvar(apolice("aig.pdf", "AIG", limite_maximo_indenizacao="R$ 5.000.000,00"))

    resultado = comparar(banco.carregar_varias(["chubb.pdf", "aig.pdf"]), carregar_campos())
    d = next(d for d in resultado.diferencas if d.campo.id == "limite_maximo_indenizacao")

    assert d.veredito is Veredito.DIFERENTE
    assert d.valores == {"Chubb": "R$ 10 milhões", "AIG": "R$ 5.000.000,00"}
    assert d.paginas == {"Chubb": 10, "AIG": 10}


# ---------------------------------------------------------------------------
# Banco em memória — o modo usado por demonstrações e testes rápidos
# ---------------------------------------------------------------------------


def test_banco_em_memoria_mantem_os_dados_entre_operacoes():
    """Regressão: um banco em memória vive enquanto a conexão viver. Abrir e
    fechar a cada operação, como se faz com arquivo, apagava o esquema junto."""
    banco = Banco(":memory:")
    banco.salvar(apolice(franquia="R$ 50.000,00"))

    assert banco.carregar("chubb.pdf").campo("franquia").valor == "R$ 50.000,00"
    assert len(banco.listar()) == 1
    banco.fechar()


def test_bancos_em_memoria_sao_independentes():
    um, outro = Banco(":memory:"), Banco(":memory:")
    um.salvar(apolice(franquia="R$ 50.000,00"))
    assert outro.listar() == []
    um.fechar()
    outro.fechar()
