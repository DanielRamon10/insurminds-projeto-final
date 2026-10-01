"""Testes da interface (frente D).

O que se testa aqui não é pixel, é o que a tela afirma: o rótulo de cada
veredito, o texto do campo ausente, a ordem das diferenças, a página de origem
que acompanha cada valor e a ponte com a extração da frente B.

Nenhum teste depende de o Streamlit estar rodando, exceto o último — que sobe a
aplicação de verdade com o `AppTest` e falha se o script levantar exceção. É
barato e pega o erro que mais dói: a tela que só quebra quando alguém abre.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.llm import RespostaLLM
from app.domain.armazenamento import Banco
from app.domain.campos import carregar_campos
from app.domain.comparacao import Veredito, comparar
from app.domain.exemplos import FONTE_EXEMPLO, carregar_exemplos
from app.interface import apresentacao
from app.interface.apresentacao import (
    ESTILOS,
    ICONE_DE_CAMPO_DESCONHECIDO,
    ICONE_DO_CAMPO,
    PALETA_DE_RESERVA,
    SITUACOES_NO_FILTRO,
    TEXTO_AUSENTE,
    TEXTO_SEM_PAGINA,
    ValorNaTela,
    carregar_modulo_extracao,
    cor_da_seguradora,
    cores_do_selo,
    encontrar_extrator,
    estilo,
    exportar_csv,
    formatar_pagina,
    icone_do_campo,
    iniciais_da_seguradora,
    legenda,
    linhas_rastreabilidade,
    matriz_comparativa,
    montar_cartoes,
    montar_kpis,
    nome_arquivo_csv,
    resumir_apolice,
    usando_exemplos,
)
from app.schemas import (
    ApoliceExtraida,
    CampoExtraido,
    DocumentoExtraido,
    OrigemTexto,
    PaginaExtraida,
    TipoArquivo,
)

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


def test_todo_campo_do_dicionario_tem_icone():
    """O ícone do cartão sai do dicionário, não de uma lista paralela.

    Se a frente de negócio acrescentar um campo, este teste falha em vez de a
    tela cair no ícone genérico sem ninguém notar.
    """
    faltando = [
        campo.id for campo in carregar_campos().campos if campo.id not in ICONE_DO_CAMPO
    ]
    assert not faltando, f"campos sem ícone: {faltando}"


def test_nao_ha_icone_orfao():
    """O outro lado: ícone para campo que não existe mais é lixo que confunde."""
    ids = {campo.id for campo in carregar_campos().campos}
    orfaos = sorted(chave for chave in ICONE_DO_CAMPO if chave not in ids)
    assert not orfaos, f"ícones para campos inexistentes: {orfaos}"


def test_campo_desconhecido_cai_no_icone_generico():
    """Campo novo, extração antiga: a tela mostra algo, não um buraco."""
    assert icone_do_campo("campo_que_ainda_nao_existe") == ICONE_DE_CAMPO_DESCONHECIDO


def test_a_cor_da_seguradora_e_estavel_entre_execucoes():
    """Cor por seguradora não pode depender do `hash()` da sessão.

    O `hash()` de `str` no Python é aleatorizado por processo (`PYTHONHASHSEED`).
    Uma cor derivada dele mudaria a cada reinício do Streamlit — e o mesmo
    cartão apareceria de cor diferente na máquina de quem apresenta.
    """
    nomes = ["AIG Seguros Brasil S.A.", "Chubb", "Tokio Marine", "Mapfre"]
    primeira = [cor_da_seguradora(n) for n in nomes]
    segunda = [cor_da_seguradora(n) for n in nomes]
    assert primeira == segunda
    assert all(cor.startswith("#") and len(cor) == 7 for cor in primeira)


def test_seguradora_desconhecida_ainda_recebe_cor_da_paleta():
    """Sem marca reconhecida, a cor sai da paleta — nunca de um valor solto."""
    cor = cor_da_seguradora("Seguradora Que Ninguém Conhece Ltda")
    assert cor in PALETA_DE_RESERVA


def test_as_iniciais_nao_sao_juridiques():
    """"AIG Seguros Brasil S.A." tem de virar "AIG", não "ASB"."""
    assert iniciais_da_seguradora("AIG Seguros Brasil S.A.") == "AIG"
    assert iniciais_da_seguradora("Chubb") == "CH"
    for nome in ["Tokio Marine", "Mapfre", "Zurich"]:
        iniciais = iniciais_da_seguradora(nome)
        assert 1 < len(iniciais) <= 3
        assert iniciais.isupper()


def test_o_selo_de_veredito_tem_fundo_e_tinta():
    """Cada veredito tem par de cores; sem ele o selo sairia transparente."""
    for veredito in Veredito:
        fundo, tinta = cores_do_selo(veredito)
        assert fundo.startswith("#") and tinta.startswith("#")
        assert fundo != tinta


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


# ---------------------------------------------------------------------------
# A cláusula existe e o número está em outro documento
#
# É o caso real das condições gerais de D&O: franquia, LMI, vigência,
# retroatividade e sublimites são definidos ali como "o valor indicado na
# Especificação da Apólice", e é a especificação — não as condições gerais — que
# traz o número. O extrator acha a cláusula, registra a página e a ressalva, e
# devolve `valor=None` corretamente. A tela escrevia "não trata do assunto" nesses
# cinco campos, afirmando o contrário do que o documento diz, e ainda descartava
# a página e o trecho junto.
# ---------------------------------------------------------------------------


def _apolices_reais() -> list[ApoliceExtraida]:
    """As extrações de verdade gravadas em `data/extracoes/`, se existirem."""
    pasta = RAIZ / "data" / "extracoes"
    arquivos = sorted(
        p for p in pasta.glob("*.json") if not p.name.endswith(".resposta_llm.json")
    )
    if not arquivos:
        pytest.skip("sem extração real gravada: rode python -m scripts.demo_extracao")
    return [
        ApoliceExtraida.model_validate_json(p.read_text(encoding="utf-8"))
        for p in arquivos
    ]


def test_clausula_que_remete_o_valor_a_outro_documento_nao_e_ausencia():
    """A correção: o documento trata do assunto — ele diz onde o valor está."""
    campo = CampoExtraido(
        campo_id="franquia",
        valor=None,
        trecho_origem="A importância definida na Especificação da Apólice, representada…",
        pagina=8,
        observacao="O valor é definido na Especificação da Apólice.",
    )
    valor = ValorNaTela(apolice="AIG", campo=campo)

    assert valor.sem_valor_no_documento
    assert not valor.ausente, "a apólice trata do assunto: a cláusula diz onde o valor está"
    assert valor.texto == campo.observacao
    assert valor.pagina == 8
    assert valor.trecho == campo.trecho_origem, (
        "a prova existe e não pode ser descartada — é o D.3, a tarefa que este "
        "caminho estava esvaziando"
    )


def test_ressalva_sem_trecho_ainda_marca_valor_em_outro_documento():
    """O caso da Chubb: a citação não foi localizada, mas a ressalva existe."""
    campo = CampoExtraido(
        campo_id="limite_maximo_indenizacao",
        valor=None,
        observacao="O valor específico é definido na Especificação da Apólice.",
    )
    valor = ValorNaTela(apolice="Chubb", campo=campo)
    assert valor.sem_valor_no_documento
    assert not valor.ausente
    assert valor.texto == campo.observacao


def test_campo_vazio_sem_prova_nenhuma_continua_sendo_ausencia():
    """O outro lado: sem cláusula e sem ressalva, distinguir seria inventar.

    É o caso das extrações de exemplo, e é o que impede esta correção de virar
    uma desculpa universal para campo faltando.
    """
    valor = ValorNaTela(apolice="AIG", campo=CampoExtraido(campo_id="sublimites"))
    assert valor.ausente
    assert not valor.sem_valor_no_documento
    assert valor.texto == TEXTO_AUSENTE


def test_a_extracao_real_nao_e_lida_como_ausencia():
    """O teste que teria pego o erro antes de ele chegar ao vídeo.

    Percorre os campos das extrações reais que a apólice remete a outro documento
    e exige que nenhum deles seja apresentado como "não trata do assunto".
    """
    remetem = [
        campo
        for apolice in _apolices_reais()
        for campo in apolice.campos
        if campo.valor is None and campo.observacao
    ]
    assert remetem, (
        "esperava ao menos um campo remetido a outro documento; se a extração "
        "mudou, este teste deixou de cobrir o caso para o qual existe"
    )
    for campo in remetem:
        valor = ValorNaTela(apolice="?", campo=campo)
        assert not valor.ausente, (
            f"{campo.campo_id} saiu como ausência, mas a cláusula diz: {campo.observacao}"
        )
        assert valor.texto == campo.observacao


def test_a_tabela_tambem_distingue_o_valor_que_esta_em_outro_documento():
    """A tabela e o CSV usavam o mesmo texto errado do cartão."""
    apolices = _apolices_reais()
    comparacao = comparar(apolices, DICIONARIO)
    _, linhas = matriz_comparativa(comparacao, apolices=apolices)

    for rotulo in ("Limite Máximo de Indenização", "Franquia"):
        linha = next(l for l in linhas if l["Campo"].startswith(rotulo))
        for nome in comparacao.apolices:
            assert linha[nome] != TEXTO_AUSENTE, (
                f"{rotulo} / {nome} saiu como 'não trata do assunto', mas a apólice "
                "remete o valor à Especificação da Apólice"
            )


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


def test_cartoes_saem_na_ordem_em_que_a_tela_os_mostra():
    """Importância do veredito primeiro, rótulo do campo depois — na tela e no console."""
    cartoes = montar_cartoes(COMPARACAO, APOLICES)
    chaves = [(estilo(c.veredito).ordem, c.rotulo) for c in cartoes]
    assert chaves == sorted(chaves)


def test_completos_trazem_todos_os_campos_do_dicionario_na_mesma_ordem():
    cartoes = montar_cartoes(COMPARACAO, APOLICES, apenas_relevantes=False)
    chaves = [(estilo(c.veredito).ordem, c.rotulo) for c in cartoes]
    assert chaves == sorted(chaves)
    assert len(cartoes) == len(DICIONARIO)


def test_filtro_da_barra_oferece_so_o_que_distingue_as_apolices():
    """Duas alavancas sobre a mesma coisa brigavam: o filtro pedia igual, o botão
    cortava de volta. O que entra por uma não pode sair pela outra."""
    assert set(SITUACOES_NO_FILTRO) == {
        Veredito.AUSENTE_EM_ALGUMA,
        Veredito.DIFERENTE,
        Veredito.REDACAO_DIVERGENTE,
    }


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
    """O caminho de exceção: sem função publicada, a tela tem de dizer isso.

    `app.agents` publica `extrair_apolice` hoje, então este não é o estado do
    repositório — é o estado de um ambiente onde a importação falhou. O que se
    testa é que a ponte devolve `None` em vez de estourar, porque é isso que
    permite à tela dizer "não está publicada" em vez de mostrar campo vazio.
    """
    assert encontrar_extrator(SimpleNamespace()) is None
    assert encontrar_extrator(None) is None
    assert carregar_modulo_extracao("modulo.que.nao.existe") is None


def test_ponte_ignora_atributo_que_nao_e_funcao():
    assert encontrar_extrator(SimpleNamespace(extrair="texto")) is None


def test_aviso_da_extracao_pendente_diz_o_que_falta_e_o_que_ja_funciona():
    aviso = apresentacao.aviso_sem_extracao()
    assert "frente B" in aviso
    assert "ingestão" in aviso


def test_ponte_encontra_a_extracao_real_publicada_pela_frente_b():
    """O contrato entre as frentes é exercido, não só descrito.

    A ponte foi combinada para a tela não precisar mudar quando a extração
    entrasse — mas convênio no papel não impede `app.agents` de ficar vazio
    depois do merge, que é exatamente o que aconteceu: a extração estava
    entregue e a tela continuava anunciando que não existia. Aqui a ponte é
    exercitada contra o módulo de verdade, sem rede, e a ausência quebra o
    teste em vez de quebrar só quem abre a tela.
    """
    extrator = encontrar_extrator(carregar_modulo_extracao())
    assert extrator is not None, "a frente B precisa publicar a extração em app.agents"


def test_extrator_publicado_cumpre_o_contrato_da_interface():
    """A interface usa só o que a extração devolve — e o tipo está no centro.

    `apolice = extrator(documento)` seguido de `apolice.documento` e
    `banco.salvar(apolice)`: se a função devolver o invólucro `Extracao` em vez
    da `ApoliceExtraida`, isso quebra com `AttributeError` — tarde demais, e só
    no momento em que alguém envia um arquivo.
    """
    extrator = encontrar_extrator(carregar_modulo_extracao())
    documento = DocumentoExtraido(
        nome_arquivo="exemplo.pdf",
        tipo=TipoArquivo.PDF,
        paginas=[PaginaExtraida(
            numero=1,
            texto="Contrato de seguro D&O.",
            origem=OrigemTexto.PDF_NATIVO,
        )],
    )
    apolice = extrator(
        documento,
        gerar=lambda prompt, json=False: RespostaLLM(
            texto='{"seguradora": null, "campos": {}}',
            provedor="teste", modelo="falso",
        ),
    )

    assert isinstance(apolice, ApoliceExtraida)
    assert apolice.documento == "exemplo.pdf"


def test_rastreabilidade_nao_deixa_celula_vazia():
    """Célula em branco na tabela de origem vira "não sei"; ausente é resposta."""
    linhas = linhas_rastreabilidade(COMPARACAO, APOLICES, apenas_encontrados=False)
    linha = next(
        l for l in linhas
        if l["Campo"].startswith("Sublimites") and l["Apólice"] == "AIG"
    )
    assert linha["Valor"] == TEXTO_AUSENTE
    assert linha["Confere"] == "não"
    assert linha["Trecho de origem"] == ""


# ---------------------------------------------------------------------------
# Demonstração e banco — a trava que protege dado real
# ---------------------------------------------------------------------------


def test_demonstracao_nunca_sobrescreve_extracao_real():
    """Trava contra o pior acidente possível: apagar a extração de verdade.

    Depois que a frente B entrar, os botões de exemplo continuam na tela. Sem
    esta trava, um clique apagaria a extração real e a comparação voltaria a
    mostrar dado fabricado — sem avisar ninguém.
    """
    from app.domain.armazenamento import Banco
    from app.interface.app import semear_exemplos

    banco = Banco(":memory:")
    try:
        banco.salvar(ApoliceExtraida(
            documento="chubb_do_capital_fechado.pdf",
            seguradora="Chubb",
            modelo_usado="gemini-3.6-flash",
            campos=[CampoExtraido(
                campo_id="franquia", valor="R$ 42.000,00",
                trecho_origem="franquia real extraida do documento", pagina=3,
            )],
        ))

        gravadas, preservadas = semear_exemplos(banco, forcar=True)

        assert preservadas == 1, "a extração real foi sobrescrita pelo exemplo"
        assert gravadas == 1  # a outra apólice, que não estava no banco, entrou

        apolice = banco.carregar("chubb_do_capital_fechado.pdf")
        assert apolice.campo("franquia").valor == "R$ 42.000,00"
        assert apolice.modelo_usado == "gemini-3.6-flash"
    finally:
        banco.fechar()


def test_recarregar_exemplos_regrava_apenas_apolice_de_exemplo():
    """Recarregar é para consertar a demonstração, não para mexer em dado real."""
    from app.domain.armazenamento import Banco
    from app.interface.app import semear_exemplos

    banco = Banco(":memory:")
    try:
        assert semear_exemplos(banco) == (2, 0)  # banco vazio: entra tudo
        assert semear_exemplos(banco, forcar=True) == (2, 0)  # só exemplo: regrava
        assert len(banco.listar()) == 2
    finally:
        banco.fechar()


# ---------------------------------------------------------------------------
# O visual — a folha de estilo não pode roubar a fonte dos ícones
# ---------------------------------------------------------------------------

#: Os spans com que o Streamlit desenha um ícone na tela.
#:
#: Medido no Chrome, com o Streamlit 1.64: o componente `DynamicIcon` é um
#: `styled("span")` do emotion, então o elemento chega ao DOM com a classe
#: `st-emotion-cache-<hash>` e o texto dentro dele é o *nome* do ícone
#: (`expand_more`, `keyboard_arrow_right`). O desenho não vem do texto: vem da
#: fonte "Material Symbols Rounded", que converte esse nome em glifo por
#: **ligadura** (`font-feature-settings: liga`). Emoji é span irmão, com outra
#: fonte, e nenhum dos dois é texto para a folha de estilo formatar.
ICONES = (
    {
        "tag": "span",
        "class": "st-emotion-cache-1dkvzay e1vmumty0",
        "data-testid": "stIconMaterial",
    },
    {"tag": "span", "class": "st-emotion-cache-1a2b3c", "data-testid": "stIconEmoji"},
)

#: As formas de seletor que esta folha escreve para definir fonte.
_PARTES = re.compile(
    r"""
      (?P<tag>^[a-zA-Z][\w-]*)
    | \.(?P<classe>[\w-]+)
    | \[(?P<atributo>[\w-]+)(?P<operador>[~|^$*]?=)\s*"(?P<valor>[^"]*)"\]
    | :not\(\[(?P<negado>[\w-]+)\s*=\s*"(?P<negado_valor>[^"]*)"\]\)
    """,
    re.VERBOSE,
)


def _folha_de_estilo() -> str:
    return (RAIZ / "app" / "interface" / "estilo.css").read_text(encoding="utf-8")


def _regras(css: str) -> list[tuple[str, str]]:
    """Cada `(seletor, corpo)` da folha, com comentários e `@import` fora.

    O `@import` precisa sair antes: ele não tem chaves, então o parser colaria a
    primeira regra da folha no mesmo pedaço de texto e descartaria as duas —
    foi assim que este teste quase nasceu cego, deixando de examinar justamente
    a regra que impõe a fonte do texto.

    O corte é por linha, e não por `;`: a URL do Google Fonts tem ponto e vírgula
    dentro da própria consulta (`wght@400;500;600;700;800`), então um
    `[^;]+;` parava no primeiro deles e deixava o resto da linha colado no
    seletor seguinte — de novo o mesmo cegamento, por outro caminho.
    """
    limpo = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    limpo = re.sub(r"@import[^\n]*", "", limpo)
    return [
        (seletor.strip(), corpo)
        for seletor, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", limpo)
        if not seletor.strip().startswith("@")
    ]


def _casa(seletor: str, elemento: dict[str, str]) -> bool | None:
    """Se o seletor alcança o elemento — `None` quando este teste não sabe dizer.

    Entende o que a folha escreve para definir fonte: tag, `.classe`,
    `[atributo operador "valor"]` e `:not([atributo="valor"])`. Seletor com
    combinador (`.hero h1`) devolve `None` de propósito: nenhuma regra de fonte
    da folha é escrita assim, e fingir que sei ler isso seria pior do que
    admitir que não sei — o teste reprova o que ele entende e não opina sobre o
    resto, em vez de passar por omissão.
    """
    if any(caractere in seletor for caractere in " >+~"):
        return None

    casou = False
    posicao = 0
    for parte in _PARTES.finditer(seletor):
        if seletor[posicao:parte.start()].strip():
            return None
        posicao = parte.end()

        if parte.group("tag"):
            casou = elemento.get("tag") == parte.group("tag")
        elif parte.group("classe"):
            casou = parte.group("classe") in elemento.get("class", "").split()
        elif parte.group("atributo"):
            valor = elemento.get(parte.group("atributo"), "")
            alvo = parte.group("valor")
            casou = {
                "=": valor == alvo,
                "*=": alvo in valor,
                "^=": valor.startswith(alvo),
                "$=": valor.endswith(alvo),
                "~=": alvo in valor.split(),
            }[parte.group("operador")]
        else:
            casou = elemento.get(parte.group("negado")) != parte.group("negado_valor")

        if not casou:
            return False

    if seletor[posicao:].strip():
        return None
    return casou


def test_a_fonte_do_texto_nao_alcanca_os_icones():
    """Regressão do "De expand_more": a ligadura do ícone depende da fonte.

    O `font-family` da folha era dirigido a `[class*="st-"]`, que alcança todo
    elemento do Streamlit — inclusive o span do ícone, cuja classe é
    `st-emotion-cache-*`. Com a fonte trocada por Inter, a ligadura não
    acontece e o navegador escreve o nome do ícone por extenso, transbordando
    sobre o rótulo do botão, porque a largura do span é fixa (16px). Medido no
    Chrome antes da correção: 21 ícones na página, todos com `font-family:
    Inter` em vez de "Material Symbols Rounded".
    """
    regras = _regras(_folha_de_estilo())

    for icone in ICONES:
        culpadas = [
            seletor
            for seletor, corpo in regras
            if "font-family" in corpo
            and "Material Symbols Rounded" not in corpo
            and any(_casa(s.strip(), icone) for s in seletor.split(","))
        ]
        assert not culpadas, (
            f"a regra de fonte do texto alcança o ícone {icone['data-testid']} "
            f"e apaga a ligadura: {'; '.join(culpadas)}"
        )


def test_a_fonte_do_icone_material_e_restaurada():
    """O cinto de segurança: existe regra devolvendo a fonte ao ícone.

    Se outra regra da folha (ou uma versão futura do Streamlit) alcançar o
    span, esta é quem devolve o desenho — e é o que este teste guarda.
    """
    resgates = [
        seletor
        for seletor, corpo in _regras(_folha_de_estilo())
        if "Material Symbols Rounded" in corpo
        and any(_casa(s.strip(), ICONES[0]) for s in seletor.split(","))
    ]
    assert resgates, "nada devolve 'Material Symbols Rounded' ao span do ícone"


# ---------------------------------------------------------------------------
# O visual — o cartão precisa de âncora estável para o CSS alcançá-lo
# ---------------------------------------------------------------------------

#: O container de cartão como o Streamlit 1.64 o entrega ao DOM.
#:
#: Medido no Chrome: `st.container(border=True, key="cartao-x")` rende um
#: `div[data-testid="stVerticalBlock"]` que carrega, junto das classes de
#: layout, a classe `st-key-cartao-x`. É por essa classe que a folha alcança o
#: cartão. O `data-testid` que a folha usava antes
#: (`stVerticalBlockBorderWrapper`) não existe mais no DOM do 1.64 — medido:
#: zero elementos na página. A regra ficou morta e os cartões saíram com
#: `background: rgba(0,0,0,0)`, `border-radius: 8px`, `box-shadow: none`.
CONTAINER_CARTAO = {
    "tag": "div",
    "class": "stVerticalBlock st-key-cartao-redacao-divergente st-emotion-cache-1s3lgy2",
    "data-testid": "stVerticalBlock",
}


def _containers_com_borda() -> list[ast.Call]:
    """Todo `st.container(border=True, ...)` de `app.py`, como nó da AST.

    A AST, e não uma expressão regular, porque o argumento pode ser uma
    f-string (`key=f"cartao-{cartao.campo_id}"`) — e é justamente a parte
    literal dessa f-string que este teste precisa ler.
    """
    codigo = (RAIZ / "app" / "interface" / "app.py").read_text(encoding="utf-8")
    achados: list[ast.Call] = []
    for no in ast.walk(ast.parse(codigo)):
        if not isinstance(no, ast.Call):
            continue
        if not (isinstance(no.func, ast.Attribute) and no.func.attr == "container"):
            continue
        if any(
            kw.arg == "border"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in no.keywords
        ):
            achados.append(no)
    return achados


def _chave_do_container(no: ast.Call) -> str | None:
    """O `key=` do container; numa f-string, a parte literal que não varia."""
    for kw in no.keywords:
        if kw.arg != "key":
            continue
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
        if isinstance(kw.value, ast.JoinedStr) and kw.value.values:
            cabeca = kw.value.values[0]
            if isinstance(cabeca, ast.Constant) and isinstance(cabeca.value, str):
                return cabeca.value
    return None


def _chave_da_classe(chave: str) -> str:
    """A classe que o Streamlit gera para um `key=` de container.

    É o sanitizador do próprio Streamlit (`"st-key-" + key`, com todo caractere
    fora de `[A-Za-z0-9_-]` trocado por hífen). Reimplementado aqui para provar
    que a chave escrita em `app.py` produz exatamente a classe que a folha
    procura — sem isso, os dois lados do contrato passariam no teste separados
    e falhariam juntos na tela.
    """
    return "st-key-" + re.sub(r"[^a-zA-Z0-9_-]", "-", chave.strip())


def test_todo_cartao_tem_ancora_estavel():
    """Sem `key=`, o cartão volta a sair sem fundo — e o CSS não avisa.

    O container com borda é o único lugar do app onde a folha desenha
    superfície (fundo, raio, sombra). A âncora tem de vir do `key=`, porque o
    `data-testid` do Streamlit muda de versão para versão — foi exatamente o que
    aconteceu entre a versão em que a folha foi escrita e a 1.64.
    """
    containers = _containers_com_borda()
    assert len(containers) >= 3, (
        "esperava ao menos os cartões de campo, de apólice e de aba; se algum "
        "saiu do app, este teste deixou de cobrir o que devia"
    )

    sem_ancora = [
        no.lineno
        for no in containers
        if not (chave := _chave_do_container(no)) or not chave.startswith("cartao")
    ]
    assert not sem_ancora, (
        "container(border=True) sem `key=` começando por 'cartao', nas linhas "
        f"{sem_ancora}: o CSS não alcança o cartão e ele sai sem fundo, sem raio "
        "e sem sombra"
    )


def test_a_regra_do_cartao_alcanca_o_container_de_verdade():
    """Regressão do cartão transparente: a regra tem de casar com o DOM real.

    A regra antiga era `div[data-testid="stVerticalBlockBorderWrapper"]`. No
    Streamlit 1.64 esse `data-testid` não existe, então a regra casava zero
    elementos e o cartão que a frente D desenhou sumia da tela. Aqui a regra é
    casada contra o container como ele é — e contra a classe que cada `key=`
    escrito em `app.py` de fato produz.
    """
    desenham = [
        seletor
        for seletor, corpo in _regras(_folha_de_estilo())
        if "border-radius: 18px" in corpo and "box-shadow" in corpo
    ]
    assert desenham, "a folha não tem mais a regra que desenha o cartão"

    alcancam = [
        seletor
        for seletor in desenham
        for parte in seletor.split(",")
        if _casa(parte.strip(), CONTAINER_CARTAO)
    ]
    assert alcancam, (
        "nenhuma regra de cartão alcança o container real "
        f"(classe {CONTAINER_CARTAO['class']!r}); o cartão volta a sair sem fundo"
    )

    for chave in filter(None, (_chave_do_container(no) for no in _containers_com_borda())):
        elemento = {
            "tag": "div",
            "class": f"stVerticalBlock {_chave_da_classe(chave)} st-emotion-cache-1s3lgy2",
            "data-testid": "stVerticalBlock",
        }
        assert any(
            _casa(parte.strip(), elemento)
            for seletor in desenham
            for parte in seletor.split(",")
        ), (
            f"o `key=\"{chave}\"` produz a classe {_chave_da_classe(chave)!r}, "
            "que nenhuma regra de cartão alcança — a âncora e o seletor "
            "divergiram"
        )



# ---------------------------------------------------------------------------
# A aplicação inteira, executada de verdade
# ---------------------------------------------------------------------------


def _banco_temporario(apolices, diretorio) -> Path:
    """Grava as apólices num `.db` descartável e devolve o caminho.

    Sem isto, os testes de tela dependeriam do `data/apolices.db` de quem está
    rodando — arquivo que está no `.gitignore` e cujo conteúdo depende de a
    pessoa ter rodado a extração real ou não. A suíte precisa dar o mesmo
    resultado em qualquer máquina, e a entrega aborta quando ela falha.
    """
    caminho = Path(diretorio) / "apolices_teste.db"
    banco = Banco(caminho)
    for apolice in apolices:
        banco.salvar(apolice)
    return caminho


def _abrir_tela():
    """Sobe a aplicação de verdade, no banco apontado por `INSURMINDS_DB`.

    A variável precisa estar valendo **durante toda a vida do teste**, não só na
    primeira execução: cada `.run()` reexecuta o script do Streamlit, que volta
    a perguntar o caminho do banco. Se ela sumisse no meio do caminho, a tela
    passaria a ler o `data/apolices.db` da máquina — exatamente a dependência de
    estado local que estes testes existem para eliminar.
    """
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    from app.interface import app as interface

    at = streamlit_testing.AppTest.from_file(
        str(Path(interface.__file__)), default_timeout=90
    )
    at.run()
    return at


@pytest.fixture
def tela_de_exemplos(tmp_path, monkeypatch):
    """A aplicação aberta contra um banco só com as extrações de exemplo."""
    caminho = _banco_temporario(carregar_exemplos(), tmp_path)
    monkeypatch.setenv("INSURMINDS_DB", str(caminho))
    return _abrir_tela()


@pytest.fixture(scope="module")
def tela(tmp_path_factory, request):
    """A aplicação com dado de exemplo, executada uma vez para os testes reusarem."""
    caminho = _banco_temporario(carregar_exemplos(), tmp_path_factory.mktemp("tela"))
    os.environ["INSURMINDS_DB"] = str(caminho)
    request.addfinalizer(lambda: os.environ.pop("INSURMINDS_DB", None))
    return _abrir_tela()


def test_app_streamlit_sobe_sem_excecao(tela):
    """Sobe o script da interface no runtime simulado do Streamlit.

    É o teste que pega o erro que só apareceria com a tela aberta na frente de
    quem avalia — o `AppTest` executa o arquivo de verdade, com barra lateral,
    abas, tabelas e cartões.
    """
    assert not tela.exception, [e.value for e in tela.exception]


def _composicao_na_tela(tela) -> str | None:
    """O HTML da barra de composição, como o Streamlit o entregou ao DOM."""
    for bloco in tela.markdown:
        if 'class="composicao"' in bloco.value:
            return bloco.value
    return None


def test_a_tela_abre_com_a_comparacao_montada(tela):
    """Não basta não quebrar: a comparação precisa estar na tela."""
    assert len(tela.tabs) == 4

    # A linha de KPIs em `st.metric` deu lugar à barra de composição: em vez de
    # cinco números soltos, uma barra proporcional com a mesma contagem. O
    # contrato que este teste guarda continua o mesmo — o resumo da comparação
    # tem de estar renderizado, e com os números do motor.
    assert _composicao_na_tela(tela), "a barra de composição não foi renderizada"

    texto = "\n".join(m.value for m in tela.markdown)
    assert "Comparador de apólices D&amp;O" in texto
    assert "Limite Máximo de Indenização (LMI)" in texto
    assert "Por que importa:" in texto


def test_a_barra_de_composicao_usa_as_contagens_do_motor(tela):
    """Cada fatia da barra vale exatamente o que o motor contou.

    O erro que este teste pega é o mais fácil de cometer num gráfico: a barra
    fica bonita e some com um veredito, ou o total da legenda deixa de ser a
    soma das fatias. Se uma fatia sumir, a comparação passa a mentir sobre si
    mesma — que é o defeito que a frente D existe para não ter.
    """
    html = _composicao_na_tela(tela)
    assert html

    larguras = [int(n) for n in re.findall(r'class="composicao-seg[^"]*" style="flex:(\d+)', html)]
    rotulos = re.findall(r"</span>([^<]+) <b>(\d+)</b></span>", html)
    contagens = [int(n) for _, n in rotulos]

    # O dicionário inteiro: toda comparação cobre os 15 campos, então as fatias
    # têm de fechar no total, sem sobra nem falta.
    assert sum(larguras) == len(carregar_campos().campos)
    assert sum(contagens) == len(carregar_campos().campos)
    assert larguras == contagens, "a barra e a legenda contam histórias diferentes"

    # A fatia vazia não pode ocupar espaço: `flex:0` e a classe que a colapsa.
    zeradas = re.findall(r'class="(composicao-seg composicao-seg-vazia)" style="flex:0', html)
    assert len(zeradas) == contagens.count(0)


def test_a_barra_de_composicao_rotula_cada_veredito_do_motor(tela):
    """Nenhum veredito some da legenda — inclusive o que hoje dá zero."""
    html = _composicao_na_tela(tela)
    assert html

    esperados = {
        apresentacao.estilo(v).rotulo for v in Veredito if v is not Veredito.AUSENTE_EM_TODAS
    }
    esperados.add("Fora das duas")  # o rótulo próprio de AUSENTE_EM_TODAS na barra

    rotulos = {r for r, _ in re.findall(r"</span>([^<]+) <b>(\d+)</b></span>", html)}
    assert rotulos == esperados


# ---------------------------------------------------------------------------
# O cabeçalho — as duas armadilhas do markdown do Streamlit
# ---------------------------------------------------------------------------


def test_o_html_do_cabecalho_comeca_na_coluna_zero_e_sem_linha_em_branco():
    """Recuo na primeira linha vira bloco de código, e o HTML aparece na tela.

    Aconteceu de verdade: com o HTML do cabeçalho recuado dentro da função, as
    tags `</div>` de fechamento saíram **escritas** no cabeçalho, dentro de um
    retângulo branco, logo abaixo dos selos.

    A regra do markdown é esta: quem decide se o bloco é HTML ou código é a
    **primeira linha** — se ela começa com quatro espaços ou mais, o bloco
    inteiro é código. E uma linha em branco **encerra** o bloco de HTML, de modo
    que o que vier depois volta a ser markdown, com o recuo valendo outra vez.
    Por isso o molde fica na coluna zero: o recuo de dentro (`<div>` aninhado)
    não é problema, o de fora é.
    """
    from app.interface import app as interface

    for nome, molde in [
        ("_MOLDE_DO_CABECALHO", interface._MOLDE_DO_CABECALHO),
        ("ARTE_DO_CABECALHO", interface.ARTE_DO_CABECALHO),
    ]:
        # A primeira linha com conteúdo tem de começar na coluna zero.
        primeira = next(linha for linha in molde.splitlines() if linha.strip())
        assert not primeira.startswith((" ", "\t")), (
            f"{nome} começa recuado ({primeira[:40]!r}): o markdown leria o bloco "
            f"inteiro como código"
        )

        # Nenhuma linha em branco no meio: ela fecharia o bloco de HTML.
        corpo = molde.strip()
        assert "\n\n" not in corpo, (
            f"{nome} tem linha em branco no meio — o bloco de HTML termina ali e "
            f"o que vem depois é lido como markdown"
        )


def test_a_arte_do_cabecalho_vem_embrulhada_em_div():
    """`<svg>` solto é embrulhado num `<p>` e deixa de ser filho do flex.

    O markdown do Streamlit reconhece `<div>` como bloco, mas não reconhece
    `<svg>`: o que não conhece, ele embrulha num parágrafo. Com o `<p>` no meio,
    o `flex` do `.hero-topo` deixa de valer para a arte e ela cai para baixo do
    texto. A div em volta é o que mantém a arte ao lado do título.
    """
    from app.interface import app as interface

    arte = interface.ARTE_DO_CABECALHO.strip()
    assert arte.startswith('<div class="hero-arte">'), arte[:60]
    assert arte.endswith("</div>")
    assert "<svg" in arte

    # E o molde coloca essa div como filha direta do `.hero-topo`.
    molde = interface._MOLDE_DO_CABECALHO
    assert "{arte}" in molde
    dentro = molde.split('<div class="hero-topo">')[1].split("</div>\n  </div>")[0]
    assert "{arte}" in dentro, "a arte não está dentro do .hero-topo"


def test_o_cabecalho_monta_o_html_com_a_arte_e_o_contexto():
    """O `format` precisa achar os dois campos — um `KeyError` aqui é tela branca."""
    from app.interface import app as interface

    sem_escolha = interface._MOLDE_DO_CABECALHO.format(
        contexto="Selecione duas apólices na barra lateral para começar",
        arte=interface.ARTE_DO_CABECALHO,
    )
    assert "hero-topo" in sem_escolha
    assert "hero-arte" in sem_escolha
    assert "Comparador de apólices D&amp;O" in sem_escolha
    assert "{" not in sem_escolha.split("<style")[0], "sobrou chave sem substituir"


def test_a_tela_declara_que_a_comparacao_usa_exemplos(tela):
    """Dado fabricado nunca pode aparecer como saída do sistema."""
    avisos = "\n".join(w.value for w in tela.warning)
    assert "extrações de exemplo" in avisos


def test_a_tela_nao_declara_exemplo_quando_o_banco_tem_extracao_real(
    tmp_path, monkeypatch
):
    """O outro lado do mesmo compromisso: dado real não carrega o aviso de exemplo.

    O teste anterior prova que o exemplo é declarado. Este prova que a extração
    de verdade não é tratada como se fosse exemplo — que é o que aconteceu
    depois que a frente B entrou: com `extrair_apolice` publicado em
    `app.agents`, o dado real passou a poder chegar ao banco, e o aviso de
    "dado de exemplo" sobre a apólice errada seria o mesmo tipo de mentira que
    o aviso evita.
    """
    pasta = Path(__file__).resolve().parent.parent / "data" / "extracoes"
    arquivos = sorted(
        p for p in pasta.glob("*.json") if not p.name.endswith(".resposta_llm.json")
    )
    if not arquivos:
        pytest.skip("sem extração real gravada: rode python -m scripts.demo_extracao")

    apolices = [
        ApoliceExtraida.model_validate_json(p.read_text(encoding="utf-8"))
        for p in arquivos
    ]
    caminho = _banco_temporario(apolices, tmp_path)
    monkeypatch.setenv("INSURMINDS_DB", str(caminho))

    at = _abrir_tela()
    assert not at.exception, [e.value for e in at.exception]
    avisos = "\n".join(w.value for w in at.warning)
    assert "extrações de exemplo" not in avisos


def _nova_tela(tela_pronta):
    """Uma execução já aberta, para os testes que clicam em controles."""
    assert not tela_pronta.exception, [e.value for e in tela_pronta.exception]
    return tela_pronta


def test_toggle_incluir_iguais_acrescenta_os_campos_identicos(tela_de_exemplos):
    """Regressão da auditoria da frente D: o botão ligava e nada mudava.

    O filtro de situações pedia os iguais e o próprio botão cortava de volta —
    duas alavancas brigando pela mesma coisa. Agora o botão é o único caminho
    para os iguais, e ligar ele tem de somar os 4 campos à lista.
    """
    at = _nova_tela(tela_de_exemplos)
    antes = sum("Por que importa:" in m.value for m in at.markdown)

    at.toggle[0].set_value(True).run()
    assert not at.exception, [e.value for e in at.exception]

    depois = sum("Por que importa:" in m.value for m in at.markdown)
    assert antes == 11
    assert depois == 15, "ligar 'incluir iguais' não acrescentou os 4 campos iguais"

    texto = "\n".join(m.value for m in at.markdown)
    assert "Igual nas duas" in texto


def test_filtro_vazio_esvazia_a_comparacao_e_volta(tela_de_exemplos):
    """Desligar todas as situações não pode quebrar a tela — nem deixá-la muda."""
    at = _nova_tela(tela_de_exemplos)
    filtros = at.sidebar.multiselect[1]
    assert filtros.value, "o filtro deveria abrir com as 3 situações ligadas"

    filtros.set_value([]).run()
    assert not at.exception, [e.value for e in at.exception]
    assert sum("Por que importa:" in m.value for m in at.markdown) == 0

    filtros.set_value(list(filtros.options)).run()
    assert sum("Por que importa:" in m.value for m in at.markdown) == 11


def test_uma_apolice_mostra_o_estado_inicial(tela_de_exemplos):
    """Uma apólice só não é erro: é o estado antes de escolher a segunda."""
    at = _nova_tela(tela_de_exemplos)
    seletor = at.sidebar.multiselect[0]
    seletor.set_value([seletor.options[0]]).run()
    assert not at.exception, [e.value for e in at.exception]

    infos = " | ".join(i.value for i in at.info)
    assert "duas apólices" in infos
