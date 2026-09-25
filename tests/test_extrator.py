"""Testes da frente B: extrator (B.2), rastreabilidade (B.3) e null explícito (B.4).

Nenhum teste chama o modelo de verdade: a resposta do LLM é montada à mão, o que
permite simular exatamente os erros que um modelo comete — citação inventada,
página errada, cabeçalho como origem, número que não está no trecho.
"""

from __future__ import annotations

import json

import pytest

from app.agents.extrator import (
    RespostaInvalida,
    extrair,
    interpretar_resposta,
    montar_prompt,
)
from app.agents.llm import RespostaLLM
from app.agents.validacao import numeros_sem_apoio
from app.domain.campos import carregar_campos
from app.schemas import DocumentoExtraido, OrigemTexto, PaginaExtraida, TipoArquivo

CABECALHO = "Processo SUSEP nº 15414.900000/2020-00 Seguro de Responsabilidade Civil D&O"

CORPO = {
    1: "Seguradora Exemplo S.A. apresenta as condições gerais deste seguro.",
    2: ("CLÁUSULA 4 - LIMITE MÁXIMO DE GARANTIA. O Limite Máximo de Garantia desta "
        "apólice é de R$ 10.000.000,00 por reclamação e no agregado anual."),
    3: ("CLÁUSULA 7 - ABRANGÊNCIA TERRITORIAL. Este seguro cobre reclamações "
        "apresentadas em qualquer parte do mundo, exceto Estados Unidos e Canadá."),
    4: ("CLÁUSULA 9 - PRAZO COMPLEMENTAR. Findo o contrato, o segurado terá 30 (trinta) "
        "dias para apresentar reclamações relativas a atos anteriores."),
    5: ("CLÁUSULA 12 - FRANQUIA. A participação obrigatória do segurado será a indicada "
        "na especificação da apólice, aplicada a cada reclamação."),
}


@pytest.fixture
def documento() -> DocumentoExtraido:
    return DocumentoExtraido(
        nome_arquivo="exemplo.pdf",
        tipo=TipoArquivo.PDF,
        paginas=[
            PaginaExtraida(numero=n, texto=f"{CABECALHO}\n{texto}", origem=OrigemTexto.PDF_NATIVO)
            for n, texto in CORPO.items()
        ],
    )


@pytest.fixture(scope="module")
def dicionario():
    return carregar_campos()


def modelo_que_responde(campos: dict, seguradora: str | None = "Seguradora Exemplo S.A."):
    """Um `gerar` falso que devolve este JSON e registra o prompt recebido."""
    chamadas = []

    def gerar(prompt: str, json: bool = False) -> RespostaLLM:
        chamadas.append({"prompt": prompt, "json": json})
        return RespostaLLM(
            texto=_json({"seguradora": seguradora, "campos": campos}),
            provedor="teste", modelo="falso", tokens_entrada=1000, tokens_saida=100,
        )

    gerar.chamadas = chamadas
    return gerar


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def rodar(documento, dicionario, campos: dict, **kw):
    return extrair(documento, dicionario, gerar=modelo_que_responde(campos, **kw)).apolice


LMI_CERTO = {
    "valor": "R$ 10.000.000,00",
    "trecho": "O Limite Máximo de Garantia desta apólice é de R$ 10.000.000,00 por reclamação",
    "pagina": 2,
    "observacao": None,
}


# ---------------------------------------------------------------------------
# B.2 — prompt e formato da resposta
# ---------------------------------------------------------------------------


def test_prompt_leva_documento_com_marcadores_e_sinonimos(documento, dicionario):
    prompt = montar_prompt(documento, dicionario)

    assert "=== PÁGINA 3 ===" in prompt
    # o sinônimo é o que leva o modelo à cláusula que não usa o rótulo oficial
    assert "Abrangência Territorial" in prompt
    for campo_id in dicionario.ids:
        assert f'"{campo_id}"' in prompt


def test_documento_vem_antes_das_instrucoes(documento, dicionario):
    prompt = montar_prompt(documento, dicionario)
    assert prompt.index("=== PÁGINA 1 ===") < prompt.index("REGRAS")


def test_extracao_pede_json_ao_modelo(documento, dicionario):
    gerar = modelo_que_responde({})
    extrair(documento, dicionario, gerar=gerar)
    assert gerar.chamadas[0]["json"] is True


def test_resposta_com_cerca_markdown_e_aceita():
    texto = 'Claro! Segue:\n```json\n{"seguradora": null, "campos": {}}\n```'
    assert interpretar_resposta(texto) == {"seguradora": None, "campos": {}}


def test_campos_em_lista_viram_dicionario():
    texto = _json({"campos": [{"campo_id": "franquia", "valor": None}]})
    assert "franquia" in interpretar_resposta(texto)["campos"]


@pytest.mark.parametrize("texto", ["nao sei", "{quebrado", '{"outra": 1}'])
def test_resposta_fora_do_formato_levanta_erro(texto):
    with pytest.raises(RespostaInvalida):
        interpretar_resposta(texto)


def test_modelo_usado_fica_registrado(documento, dicionario):
    apolice = rodar(documento, dicionario, {})
    assert apolice.modelo_usado == "teste/falso"


# ---------------------------------------------------------------------------
# B.3 — rastreabilidade
# ---------------------------------------------------------------------------


def test_campo_certo_e_rastreavel(documento, dicionario):
    apolice = rodar(documento, dicionario, {"limite_maximo_indenizacao": LMI_CERTO})
    lmi = apolice.campo("limite_maximo_indenizacao")

    assert lmi.valor == "R$ 10.000.000,00"
    assert lmi.pagina == 2
    assert lmi.paginas_possiveis == [2]
    assert lmi.rastreavel


def test_pagina_vem_do_documento_nao_do_modelo(documento, dicionario):
    """O modelo errou a página; a validação corrige e registra."""
    errado = {**LMI_CERTO, "pagina": 40}
    lmi = rodar(documento, dicionario, {"limite_maximo_indenizacao": errado}).campo(
        "limite_maximo_indenizacao"
    )
    assert lmi.pagina == 2
    assert "corrigida" in lmi.observacao


def test_citacao_inventada_descarta_o_valor(documento, dicionario):
    """O risco central do projeto: um limite plausível com citação que não existe."""
    inventado = {
        "valor": "R$ 20.000.000,00",
        "trecho": "O limite de indenização desta apólice é de R$ 20.000.000,00 por ano",
        "pagina": 2,
    }
    lmi = rodar(documento, dicionario, {"limite_maximo_indenizacao": inventado}).campo(
        "limite_maximo_indenizacao"
    )
    assert lmi.valor is None
    assert lmi.trecho_origem is None
    assert "nao encontrada" in lmi.observacao


def test_citacao_de_cabecalho_nao_prova_origem(documento, dicionario):
    """Cabeçalho repetido em todas as páginas: o valor fica, a localização não."""
    cabecalho = {
        "valor": "Responsabilidade Civil D&O",
        "trecho": "Processo SUSEP nº 15414.900000/2020-00 Seguro de Responsabilidade Civil",
        "pagina": 1,
    }
    campo = rodar(documento, dicionario, {"definicao_segurado": cabecalho}).campo(
        "definicao_segurado"
    )
    assert campo.pagina is None
    assert len(campo.paginas_possiveis) == 5
    assert not campo.rastreavel
    assert "cabecalho" in campo.observacao


def test_citacao_com_espacamento_e_caixa_diferentes_e_achada(documento, dicionario):
    """O modelo reescreve espaços, acentos e pontuação ao citar."""
    reescrito = {
        "valor": "Mundial, exceto Estados Unidos e Canadá",
        "trecho": "este seguro cobre reclamacoes apresentadas em QUALQUER parte do mundo exceto",
        "pagina": 3,
    }
    campo = rodar(documento, dicionario, {"ambito_geografico": reescrito}).campo(
        "ambito_geografico"
    )
    assert campo.pagina == 3


def test_citacao_com_reticencias_exige_pedacos_na_mesma_pagina(documento, dicionario):
    ok = {
        "valor": "Mundial, exceto Estados Unidos e Canadá",
        "trecho": "Este seguro cobre reclamações ... exceto Estados Unidos e Canadá",
        "pagina": 3,
    }
    espalhado = {
        "valor": "R$ 10.000.000,00",
        "trecho": "O Limite Máximo de Garantia desta ... para apresentar reclamações relativas",
        "pagina": 2,
    }
    apolice = rodar(
        documento, dicionario,
        {"ambito_geografico": ok, "limite_maximo_indenizacao": espalhado},
    )
    assert apolice.campo("ambito_geografico").pagina == 3
    assert apolice.campo("limite_maximo_indenizacao").valor is None


def test_citacao_que_atravessa_a_quebra_de_pagina_e_achada(documento, dicionario):
    """Achado com a apólice real da Chubb: a definição de Segurado começa no pé
    da página 9 e continua na 10, e o modelo cita pulando o cabeçalho que fica no
    meio. A origem é a página onde o trecho começa."""
    atravessa = {
        "valor": "Mundial, exceto Estados Unidos e Canadá",
        # sem o CABECALHO que abre a página 4 — o modelo não o repete
        "trecho": ("em qualquer parte do mundo, exceto Estados Unidos e Canadá. "
                   "CLÁUSULA 9 - PRAZO COMPLEMENTAR. Findo o contrato"),
        "pagina": 3,
    }
    campo = rodar(documento, dicionario, {"ambito_geografico": atravessa}).campo(
        "ambito_geografico"
    )
    assert campo.pagina == 3
    assert campo.rastreavel


# ---------------------------------------------------------------------------
# Guardrail numérico
# ---------------------------------------------------------------------------


def test_numero_que_nao_esta_no_trecho_descarta_o_valor(documento, dicionario):
    """Citação real, número inventado: o guardrail do Desafio 5 aplicado à apólice."""
    trocado = {**LMI_CERTO, "valor": "R$ 15.000.000,00"}
    lmi = rodar(documento, dicionario, {"limite_maximo_indenizacao": trocado}).campo(
        "limite_maximo_indenizacao"
    )
    assert lmi.valor is None
    assert lmi.pagina == 2  # a citação era real e continua registrada
    assert "15.000.000,00" in lmi.observacao


@pytest.mark.parametrize("valor, trecho", [
    ("R$ 10 milhões", "limite de R$ 10.000.000,00 por reclamação"),
    ("R$ 10.000.000,00", "limite de R$ 10 milhões por reclamação"),
    ("30 dias", "o segurado terá 30 (trinta) dias para apresentar"),
    ("30 dias", "o segurado terá trinta dias para apresentar"),
    ("01/01/2020", "atos praticados a partir de 01/01/2020"),
])
def test_mesmo_numero_escrito_de_outro_jeito_passa(valor, trecho):
    assert numeros_sem_apoio(valor, trecho) == []


@pytest.mark.parametrize("valor, trecho", [
    ("R$ 5.000.000,00", "limite de R$ 10.000.000,00"),
    ("90 dias", "o segurado terá 30 (trinta) dias"),
    ("01/01/2018", "a partir de 01/01/2020"),
])
def test_numero_diferente_e_barrado(valor, trecho):
    assert numeros_sem_apoio(valor, trecho)


def test_prazo_por_extenso_no_documento_e_aceito(documento, dicionario):
    prazo = {
        "valor": "30 dias",
        "trecho": "o segurado terá 30 (trinta) dias para apresentar reclamações",
        "pagina": 4,
    }
    campo = rodar(documento, dicionario, {"prazo_complementar": prazo}).campo(
        "prazo_complementar"
    )
    assert campo.valor == "30 dias"
    assert campo.rastreavel


# ---------------------------------------------------------------------------
# B.4 — null explícito, nunca inventado
# ---------------------------------------------------------------------------


def test_todo_campo_do_dicionario_sai_mesmo_se_o_modelo_esquecer(documento, dicionario):
    apolice = rodar(documento, dicionario, {"limite_maximo_indenizacao": LMI_CERTO})

    assert [c.campo_id for c in apolice.campos] == list(dicionario.ids)
    esquecido = apolice.campo("franquia")
    assert esquecido.valor is None
    assert "nao devolveu" in esquecido.observacao


def test_campo_fora_do_dicionario_e_ignorado(documento, dicionario):
    apolice = rodar(documento, dicionario, {"campo_inventado": LMI_CERTO})
    assert apolice.campo("campo_inventado") is None


def test_valor_sem_citacao_e_descartado(documento, dicionario):
    sem_trecho = {"valor": "R$ 10.000.000,00", "trecho": None, "pagina": 2}
    lmi = rodar(documento, dicionario, {"limite_maximo_indenizacao": sem_trecho}).campo(
        "limite_maximo_indenizacao"
    )
    assert lmi.valor is None
    assert "sem citacao" in lmi.observacao


@pytest.mark.parametrize("vazio", ["", "null", "N/A", "Não encontrado", "não consta"])
def test_formas_de_nao_achei_viram_null(documento, dicionario, vazio):
    campo = rodar(
        documento, dicionario,
        {"franquia": {"valor": vazio, "trecho": vazio, "pagina": None}},
    ).campo("franquia")
    assert campo.valor is None
    assert not campo.encontrado


def test_valor_remetido_a_especificacao_fica_null_com_origem(documento, dicionario):
    """Condição geral que manda o valor para a especificação: não há número a
    extrair, mas a cláusula existe e fica registrada — null honesto e rastreado."""
    remete = {
        "valor": None,
        "trecho": "A participação obrigatória do segurado será a indicada na especificação",
        "pagina": 5,
        "observacao": "valor definido na especificação da apólice",
    }
    campo = rodar(documento, dicionario, {"franquia": remete}).campo("franquia")
    assert campo.valor is None
    assert campo.pagina == 5
    assert campo.observacao == "valor definido na especificação da apólice"


@pytest.mark.parametrize("remissao", [
    "Definidos na Especificação da Apólice",
    "Conforme especificação",
    "O valor indicado no frontispício",
])
def test_valor_que_so_remete_a_especificacao_vira_null(documento, dicionario, remissao):
    """O modelo desobedeceu o prompt com a Chubb e respondeu a remissão como valor.
    Duas apólices com a mesma frase seriam declaradas iguais sem número nenhum."""
    remete = {
        "valor": remissao,
        "trecho": "A participação obrigatória do segurado será a indicada na especificação",
        "pagina": 5,
    }
    campo = rodar(documento, dicionario, {"franquia": remete}).campo("franquia")
    assert campo.valor is None
    assert campo.pagina == 5
    assert "especificacao" in campo.observacao


def test_texto_que_menciona_especificacao_mas_diz_algo_continua(documento, dicionario):
    """Só a remissão pura é descartada: valor com número ou conteúdo próprio fica."""
    com_numero = {**LMI_CERTO, "valor": "R$ 10.000.000,00, salvo outro valor na especificação"}
    lmi = rodar(documento, dicionario, {"limite_maximo_indenizacao": com_numero}).campo(
        "limite_maximo_indenizacao"
    )
    assert lmi.encontrado


def test_seguradora_so_e_aceita_se_estiver_no_documento(documento, dicionario):
    assert rodar(documento, dicionario, {}).seguradora == "Seguradora Exemplo S.A."
    assert rodar(documento, dicionario, {}, seguradora="Allianz").seguradora is None
