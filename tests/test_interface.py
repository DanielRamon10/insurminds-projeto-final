"""Testes da interface (frente D).

O que se testa aqui não é pixel, é o que a tela afirma: o rótulo de cada
veredito, o texto do campo ausente, a ordem das diferenças, a página de origem
que acompanha cada valor e a ponte com a extração da frente B.

Nenhum teste depende de o Streamlit estar rodando, exceto o último — que sobe a
aplicação de verdade com o `AppTest` e falha se o script levantar exceção. É
barato e pega o erro que mais dói: a tela que só quebra quando alguém abre.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domain.campos import carregar_campos
from app.domain.comparacao import Veredito, comparar
from app.domain.exemplos import FONTE_EXEMPLO, carregar_exemplos
from app.interface import apresentacao
from app.interface.apresentacao import (
    ESTILOS,
    TEXTO_AUSENTE,
    TEXTO_SEM_PAGINA,
    ValorNaTela,
    carregar_modulo_extracao,
    encontrar_extrator,
    estilo,
    exportar_csv,
    formatar_pagina,
    legenda,
    linhas_rastreabilidade,
    matriz_comparativa,
    montar_cartoes,
    montar_kpis,
    nome_arquivo_csv,
    resumir_apolice,
    usando_exemplos,
)
from app.schemas import ApoliceExtraida, CampoExtraido

DICIONARIO = carregar_campos()
APOLICES = carregar_exemplos()
COMPARACAO = comparar(APOLICES, DICIONARIO)

RAIZ = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Vocabulário da tela
# ---------------------------------------------------------------------------


def test_todo_veredito_do_motor_tem_rotulo_na_tela():
    """Se o motor ganhar um veredito novo, a tela não pode ficar muda.

    É o tipo de buraco que só aparece na hora da apresentação, com uma célula em
    branco no lugar da situação.
    """
    for veredito in Veredito:
        assert veredito in ESTILOS, f"{veredito} nao tem rotulo na interface"


def test_rotulo_e_traducao_e_nao_o_nome_do_enum():
    """"Ausente em uma delas" é para o usuário; `ausente_em_alguma` é do código."""
    for veredito, est in ESTILOS.items():
        assert est.rotulo != veredito.value
        assert "_" not in est.rotulo
        assert est.explicacao.strip()


def test_a_legenda_vem_na_ordem_de_importancia():
    """O que mais pesa numa decisão vem primeiro: ausência, diferença, redação."""
    ordem = [est.rotulo for est in legenda()]
    assert ordem[0] == ESTILOS[Veredito.AUSENTE_EM_ALGUMA].rotulo
    assert ordem[1] == ESTILOS[Veredito.DIFERENTE].rotulo
    assert ordem.index(ESTILOS[Veredito.IGUAL].rotulo) > ordem.index(
        ESTILOS[Veredito.REDACAO_DIVERGENTE].rotulo
    )


def test_estilo_de_veredito_desconhecido_nao_quebra():
    """A tela precisa sobreviver a um veredito que esta versão não conhece."""

    class Futuro:
        pass

    assert estilo(Futuro()).rotulo == apresentacao.TEXTO_VEREDITO_DESCONHECIDO


def test_apresentacao_nao_importa_streamlit():
    """É o que permite testar a apresentação sem subir a aplicação."""
    fonte = Path(apresentacao.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+streamlit", fonte, re.MULTILINE)


# ---------------------------------------------------------------------------
# Campo ausente e citação de origem
# ---------------------------------------------------------------------------


def test_campo_ausente_nao_vira_texto_vazio():
    valor = ValorNaTela(apolice="AIG", campo=None)
    assert valor.ausente
    assert valor.texto == TEXTO_AUSENTE
    assert valor.ancoragem == TEXTO_SEM_PAGINA


def test_valor_em_branco_conta_como_ausente():
    """Regra da tarefa B.4: `None` e string vazia não podem virar um valor mudo."""
    valor = ValorNaTela(
        apolice="AIG", campo=CampoExtraido(campo_id="franquia", valor="   ")
    )
    assert valor.ausente
    assert valor.texto == TEXTO_AUSENTE


def test_valor_encontrado_e_rastreavel_cita_a_pagina_e_o_trecho():
    campo = CampoExtraido(
        campo_id="franquia",
        valor="R$ 50.000,00",
        trecho_origem="a franquia sera de R$ 50.000,00 por reclamacao",
        pagina=12,
    )
    valor = ValorNaTela(apolice="Chubb", campo=campo)
    assert not valor.ausente
    assert valor.texto == "R$ 50.000,00"
    assert valor.rastreavel
    assert valor.trecho == campo.trecho_origem
    assert valor.ancoragem == "página 12"


def test_pagina_de_origem_nao_e_inventada_quando_falta():
    campo = CampoExtraido(campo_id="vigencia", valor="12 meses")
    valor = ValorNaTela(apolice="Chubb", campo=campo)
    assert not valor.ausente
    assert not valor.rastreavel
    assert valor.ancoragem == TEXTO_SEM_PAGINA


def test_pagina_que_se_repete_no_documento_e_dita_como_aviso():
    """Cláusula padrão aparece em vários lugares; fingir precisão seria mentir."""
    assert formatar_pagina(12, [12, 45]) == "página 12 (o trecho se repete em 45)"
    assert formatar_pagina(None, [7, 30]) == "páginas 7, 30"
    assert formatar_pagina(4) == "página 4"


# ---------------------------------------------------------------------------
# Cartões da comparação (D.2 e D.3)
# ---------------------------------------------------------------------------


def test_cartoes_trazem_so_o_que_distingue_as_apolices():
    cartoes = montar_cartoes(COMPARACAO, APOLICES, apenas_relevantes=True)
    assert cartoes
    assert all(c.relevante for c in cartoes)
    assert {c.veredito for c in cartoes} == {
        Veredito.AUSENTE_EM_ALGUMA,
        Veredito.DIFERENTE,
        Veredito.REDACAO_DIVERGENTE,
    }


def test_cartoes_completos_incluem_o_que_e_igual():
    """O caso em que R$ 10.000.000,00 e R$ 10 milhões são o mesmo valor."""
    cartoes = montar_cartoes(COMPARACAO, APOLICES, apenas_relevantes=False)
    iguais = [c for c in cartoes if c.veredito is Veredito.IGUAL]
    assert iguais
    assert any(c.campo_id == "limite_maximo_indenizacao" for c in iguais)


def test_cartao_traz_o_trecho_de_origem_de_cada_apolice():
    """É este encontro entre motor e apólice que sustenta o D.3."""
    cartoes = montar_cartoes(COMPARACAO, APOLICES)
    for cartao in cartoes:
        for valor in cartao.valores:
            if valor.ausente:
                continue
            apolice = next(a for a in APOLICES if a.nome == valor.apolice)
            original = apolice.campo(cartao.campo_id)
            assert valor.trecho == original.trecho_origem
            assert valor.pagina == original.pagina


def test_ordem_das_colunas_e_a_ordem_das_apolices():
    cartoes = montar_cartoes(COMPARACAO, APOLICES)
    esperado = tuple(a.nome for a in APOLICES)
    assert all(tuple(v.apolice for v in c.valores) == esperado for c in cartoes)


def test_cartao_aponta_quem_nao_trata_do_assunto():
    cartoes = montar_cartoes(COMPARACAO, APOLICES)
    sublimites = next(c for c in cartoes if c.campo_id == "sublimites")
    assert sublimites.ausentes == ("AIG",)


def test_cartao_com_apolice_nao_carregada_nao_derruba_a_tela():
    cartoes = montar_cartoes(COMPARACAO, apolices=[], apenas_relevantes=False)
    assert cartoes
    assert all(v.ausente for c in cartoes for v in c.valores)


# ---------------------------------------------------------------------------
# Números, tabela e CSV
# ---------------------------------------------------------------------------


def test_kpis_batem_com_a_contagem_do_motor():
    por_rotulo = {k.rotulo: k.valor for k in montar_kpis(COMPARACAO)}
    assert por_rotulo["Campos comparados"] == len(COMPARACAO.diferencas)
    assert por_rotulo["Valores diferentes"] == COMPARACAO.resumo[Veredito.DIFERENTE.value]
    assert por_rotulo["Iguais nas duas"] == COMPARACAO.resumo[Veredito.IGUAL.value]


def test_matriz_tem_uma_coluna_por_apolice_e_a_situacao_traduzida():
    colunas, linhas = matriz_comparativa(COMPARACAO)
    assert colunas == ("Campo", "Chubb", "AIG", "Situação")
    assert len(linhas) == len(COMPARACAO.diferencas)

    situacoes = {linha["Situação"] for linha in linhas}
    assert "Ausente em uma delas" in situacoes
    assert not any("_" in situacao for situacao in situacoes)


def test_matriz_escreve_a_ausencia_em_vez_de_deixar_em_branco():
    _, linhas = matriz_comparativa(COMPARACAO)
    sublimites = next(l for l in linhas if l["Campo"].startswith("Sublimites"))
    assert sublimites["AIG"] == TEXTO_AUSENTE


def test_csv_abre_acentuado_no_excel():
    """Separador `;` e BOM: o arquivo que o grupo abre no Windows em português."""
    texto = exportar_csv(COMPARACAO)
    assert texto.startswith("\ufeff")
    cabecalho = texto.lstrip("\ufeff").splitlines()[0]
    assert cabecalho == "Campo;Chubb;AIG;Situação"
    assert TEXTO_AUSENTE in texto


def test_nome_do_csv_nao_tem_acento_nem_espaco():
    assert nome_arquivo_csv(COMPARACAO) == "comparacao_chubb-x-aig.csv"


# ---------------------------------------------------------------------------
# Rastreabilidade (D.3)
# ---------------------------------------------------------------------------


def test_rastreabilidade_so_lista_o_que_foi_encontrado():
    linhas = linhas_rastreabilidade(COMPARACAO, APOLICES)
    assert linhas
    assert all(linha["Valor"] != TEXTO_AUSENTE for linha in linhas)
    assert all(linha["Trecho de origem"] for linha in linhas)


def test_rastreabilidade_marca_quem_tem_e_quem_nao_tem_origem():
    linhas = linhas_rastreabilidade(COMPARACAO, APOLICES, apenas_encontrados=False)
    assert any(linha["Confere"] == "sim" for linha in linhas)
    assert all(linha["Confere"] in {"sim", "não"} for linha in linhas)


def test_rastreabilidade_traz_a_pagina_que_o_motor_encontrou():
    """As páginas vêm do `d.paginas` do motor — a tela não recalcula nada."""
    linhas = linhas_rastreabilidade(COMPARACAO, APOLICES)
    for diferenca in COMPARACAO.diferencas:
        for nome, pagina in diferenca.paginas.items():
            if pagina is None:
                continue
            casadas = [
                linha
                for linha in linhas
                if linha["Campo"] == diferenca.campo.rotulo and linha["Apólice"] == nome
            ]
            assert casadas and casadas[0]["Página"] == pagina


# ---------------------------------------------------------------------------
# Cartão da apólice
# ---------------------------------------------------------------------------


def test_resumo_conta_os_campos_do_dicionario_e_nao_so_os_encontrados():
    """"9 de 15" — uma extração incompleta não pode parecer completa."""
    resumo = resumir_apolice(APOLICES[1], DICIONARIO)  # a AIG não traz 3 campos
    assert resumo.total == len(DICIONARIO)
    assert resumo.encontrados < resumo.total
    assert 0 < resumo.fracao_encontrada < 1


def test_resumo_de_exemplo_declara_que_nao_veio_do_sistema():
    resumo = resumir_apolice(APOLICES[0], DICIONARIO)
    assert resumo.veio_de_exemplo
    assert "exemplo" in resumo.fonte
    assert resumo.modelo_usado == FONTE_EXEMPLO


def test_fonte_de_extracao_real_cita_o_modelo():
    real = ApoliceExtraida(
        documento="x.pdf",
        seguradora="X",
        modelo_usado="gemini-3.6-flash",
        campos=[CampoExtraido(campo_id="franquia", valor="R$ 50.000,00", pagina=7)],
    )
    resumo = resumir_apolice(real, DICIONARIO)
    assert not resumo.veio_de_exemplo
    assert resumo.fonte == "extraída por gemini-3.6-flash"


def test_aviso_de_exemplos_aparece_quando_ha_exemplo_na_comparacao():
    assert usando_exemplos(APOLICES)
    assert not usando_exemplos(
        [
            ApoliceExtraida(
                documento="x.pdf", modelo_usado="gemini-3.6-flash", campos=[]
            )
        ]
    )


# ---------------------------------------------------------------------------
# Ponte com a frente B
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nome", ["extrair_apolice", "extrair_apolices", "extrair", "extrair_campos"]
)
def test_ponte_acha_qualquer_nome_combinado_com_a_frente_b(nome):
    def extrair(documento):
        return documento

    modulo = SimpleNamespace(**{nome: extrair})
    assert encontrar_extrator(modulo) is extrair


def test_ponte_devolve_none_quando_a_extracao_nao_existe():
    """O estado de hoje: `app.agents` está vazio e a tela tem de dizer isso."""
    assert encontrar_extrator(SimpleNamespace()) is None
    assert encontrar_extrator(None) is None
    assert carregar_modulo_extracao("modulo.que.nao.existe") is None


def test_ponte_ignora_atributo_que_nao_e_funcao():
    assert encontrar_extrator(SimpleNamespace(extrair="texto")) is None


def test_aviso_da_extracao_pendente_diz_o_que_falta_e_o_que_ja_funciona():
    aviso = apresentacao.aviso_sem_extracao()
    assert "frente B" in aviso
    assert "ingestão" in aviso


# ---------------------------------------------------------------------------
# A aplicação inteira, executada de verdade
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tela():
    """A aplicação executada uma vez, para os testes de conteúdo reusarem."""
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    from app.interface import app as interface

    at = streamlit_testing.AppTest.from_file(
        str(Path(interface.__file__)), default_timeout=90
    )
    at.run()
    return at


def test_app_streamlit_sobe_sem_excecao(tela):
    """Sobe o script da interface no runtime simulado do Streamlit.

    É o teste que pega o erro que só apareceria com a tela aberta na frente de
    quem avalia — o `AppTest` executa o arquivo de verdade, com barra lateral,
    abas, tabelas e cartões.
    """
    assert not tela.exception, [e.value for e in tela.exception]


def test_a_tela_abre_com_a_comparacao_montada(tela):
    """Não basta não quebrar: a comparação precisa estar na tela."""
    assert len(tela.tabs) == 4
    assert len(tela.metric) >= 5

    texto = "\n".join(m.value for m in tela.markdown)
    assert "Comparador de apólices D&amp;O" in texto
    assert "Limite Máximo de Indenização (LMI)" in texto
    assert "Por que importa:" in texto


def test_a_tela_declara_que_a_comparacao_usa_exemplos(tela):
    """Dado fabricado nunca pode aparecer como saída do sistema."""
    avisos = "\n".join(w.value for w in tela.warning)
    assert "extrações de exemplo" in avisos
