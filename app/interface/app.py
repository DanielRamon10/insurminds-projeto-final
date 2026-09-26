"""Interface da plataforma de análise de apólices D&O — frente D (D.1 a D.3).

    streamlit run app/interface/app.py

O que esta tela faz, tarefa por tarefa:

* **D.1** — recebe apólice em PDF ou imagem e entrega o arquivo à ingestão da
  frente A, mostrando o que voltou: páginas, páginas por OCR, tamanho do texto.
* **D.2** — mostra as diferenças entre as apólices lado a lado, na ordem em que
  o motor as considera relevantes, com a explicação do especialista junto.
* **D.3** — cada valor encontrado abre a página e o trecho de onde saiu, e
  mostra a página do PDF renderizada para conferência.

Duas decisões que valem explicação:

**A tela não extrai nada.** Quem decide o que difere é o motor da frente C;
quem lê o documento é a frente A. Aqui só se apresenta o que eles devolvem —
era o erro que custou um PR de consolidação no Desafio 5 misturar as camadas.

**A tela não finge.** A extração das cláusulas (frente B) ainda não existe, e a
comparação da demonstração roda sobre as extrações de exemplo de
`app/domain/exemplos.py`. Isso é dito em toda tela onde os dados aparecem, no
rodapé e no cartão de cada apólice. Dado fabricado apresentado como saída do
sistema destruiria o projeto na primeira pergunta da banca.

`apresentacao.py` monta o que aparece; este arquivo desenha.
"""

from __future__ import annotations

import html
import sys
import tempfile
from pathlib import Path

# A raiz do projeto precisa estar no caminho de import: o Streamlit executa
# este arquivo como script solto, e `from app...` só resolve a partir daqui.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.clients.extracao import ocr_disponivel  # noqa: E402
from app.config import APOLICES_DIR, EXTENSOES_IMAGEM, EXTENSOES_PDF  # noqa: E402
from app.config import provedores_disponiveis  # noqa: E402
from app.domain.armazenamento import Banco  # noqa: E402
from app.domain.campos import DicionarioCampos, carregar_campos  # noqa: E402
from app.domain.comparacao import Veredito, comparar  # noqa: E402
from app.domain.exemplos import FONTE_EXEMPLO, carregar_exemplos  # noqa: E402
from app.domain.ingestao import receber_varios  # noqa: E402
from app.interface.apresentacao import (  # noqa: E402
    TEXTO_AUSENTE,
    TEXTO_SEM_PAGINA,
    CartaoDiferenca,
    ValorNaTela,
    aviso_sem_extracao,
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
    SITUACOES_NO_FILTRO,
    usando_exemplos,
)
from app.schemas import ApoliceExtraida, DocumentoExtraido  # noqa: E402

CSS = (Path(__file__).resolve().parent / "estilo.css").read_text(encoding="utf-8")

#: Fundo das células da tabela, por cor de selo. O `st.badge` recebe nome de
#: cor ("orange"), o pandas precisa de hexadecimal — esta é a única tradução.
FUNDO = {
    "red": "#FEE2E2",
    "orange": "#FFEDD5",
    "yellow": "#FEF9C3",
    "violet": "#EDE9FE",
    "green": "#DCFCE7",
    "blue": "#DBEAFE",
    "gray": "#F1F5F9",
}

FORMATOS_ACEITOS = sorted(EXTENSOES_PDF | EXTENSOES_IMAGEM)

#: Fundo de cada situação na tabela, pelo rótulo que aparece na tela. O
#: `st.badge` recebe nome de cor ("orange"); o pandas quer hexadecimal — esta é
#: a única tradução entre os dois vocabulários, e ela vive em um lugar só.
FUNDO_SITUACAO = {
    estilo(v).rotulo: FUNDO.get(estilo(v).cor, "#F1F5F9") for v in Veredito
}


# ---------------------------------------------------------------------------
# Estado e carga
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def banco_do_projeto() -> Banco:
    """O banco de apólices processadas (C.1).

    `cache_resource` porque o banco é recurso compartilhado e não dado de
    entrada: a cada clique o Streamlit reexecuta este arquivo inteiro, e no modo
    em memória reabrir a conexão a cada rerun apagaria tudo.
    """
    return Banco()


@st.cache_data(show_spinner=False)
def dicionario_do_especialista() -> DicionarioCampos:
    """O dicionário de campos (B.1). É o arquivo do corretor, só lido aqui."""
    return carregar_campos()


@st.cache_data(show_spinner="Renderizando a página do PDF...", max_entries=40)
def pagina_em_imagem(caminho: str, numero: int, escala: float = 1.7):
    """Renderiza uma página do PDF, para a conferência visual do D.3.

    Sem OCR: aqui o PDF já é nativo, e o que se quer é ver a página como ela é.
    Devolve `None` quando não dá para renderizar — uma página ilegível não pode
    derrubar a comparação inteira.

    O limite de 40 páginas em cache é deliberado: cada render em 300 dpi ocupa
    alguns megabytes, e sem teto a memória cresceria a cada campo aberto durante
    uma apresentação longa.
    """
    import pypdfium2 as pdfium

    try:
        documento = pdfium.PdfDocument(caminho)
    except Exception:  # arquivo errado ou protegido: a tela segue sem a imagem
        return None

    try:
        if not 1 <= numero <= len(documento):
            return None
        return documento[numero - 1].render(scale=escala).to_pil()
    except Exception:
        return None
    finally:
        documento.close()


def caminho_do_documento(documento: str) -> Path | None:
    """O arquivo original desta apólice, se ainda estiver na máquina.

    Serve à prova de origem: sem o arquivo não há página para mostrar, e a tela
    diz isso em vez de exibir um espaço vazio.
    """
    caminho = Path(st.session_state.setdefault("enviados", {}).get(documento, ""))
    if documento in st.session_state["enviados"] and caminho.is_file():
        return caminho

    candidato = APOLICES_DIR / documento
    return candidato if candidato.is_file() else None


def documentos_por_apolice(apolices: list[ApoliceExtraida]) -> dict[str, Path | None]:
    """De {nome da apólice} para {arquivo de onde ela saiu}."""
    return {a.nome: caminho_do_documento(a.documento) for a in apolices}


def semear_exemplos(banco: Banco, forcar: bool = False) -> tuple[int, int]:
    """Coloca as extrações de exemplo no banco.

    Devolve `(gravadas, preservadas)`. `preservadas` conta as apólices que já
    estavam no banco com extração de verdade — a demonstração **nunca** passa por
    cima de dado real, nem quando alguém manda recarregar os exemplos. Sem essa
    trava, o primeiro clique depois de a frente B entrar apagaria a extração real
    e a comparação voltaria a mostrar dado fabricado, em silêncio.
    """
    gravadas = 0
    preservadas = 0

    for apolice in carregar_exemplos():
        existente = banco.carregar(apolice.documento)

        if existente is None:
            banco.salvar(apolice)
            gravadas += 1
            continue

        if (existente.modelo_usado or "") != FONTE_EXEMPLO:
            preservadas += 1
            continue

        if forcar:
            banco.salvar(apolice)
            gravadas += 1

    return gravadas, preservadas


def aviso_de_preservadas(preservadas: int) -> str:
    """O que dizer quando a demonstração deixou uma extração real em paz."""
    return (
        f"{preservadas} apólice(s) **não** foram sobrescritas: no banco há extração "
        "de verdade e a demonstração não passa por cima dela."
    )


# ---------------------------------------------------------------------------
# Desenho: o que o Streamlit não tem pronto
# ---------------------------------------------------------------------------


def cabecalho(comparacao_em_uso: str | None = None) -> None:
    """O cabeçalho da página."""
    contexto = (
        f"Comparando <b>{html.escape(comparacao_em_uso)}</b>"
        if comparacao_em_uso
        else "Selecione duas apólices na barra lateral para começar"
    )
    st.markdown(
        f"""
        <div class="hero">
          <h1>🛡️ Comparador de apólices D&amp;O</h1>
          <p>Leitura, extração e comparação de condições gerais de seguro para
          <i>Directors &amp; Officers</i>. {contexto}.</p>
          <div class="linha-selos">
            <span class="selo">IA generativa sobre documento jurídico</span>
            <span class="selo">cada valor aponta a página de origem</span>
            <span class="selo">protótipo InsurMinds · I2A2</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def rodape() -> None:
    st.markdown(
        '<div class="rodape">Protótipo acadêmico do grupo Insurminds · I2A2. As apólices '
        "são condições gerais públicas, com registro na SUSEP — nenhum dado de cliente "
        "entra nesta plataforma.</div>",
        unsafe_allow_html=True,
    )


def _valor(valor: ValorNaTela, documentos: dict[str, Path | None]) -> None:
    """Um valor, com a citação de origem e a prova documental quando pedida."""
    st.markdown(
        f'<div class="valor-nome">{html.escape(valor.apolice)}</div>',
        unsafe_allow_html=True,
    )

    if valor.ausente:
        st.markdown(
            f'<div class="valor-ausente">{TEXTO_AUSENTE}</div>', unsafe_allow_html=True
        )
        return

    st.markdown(f'<div class="valor">{html.escape(valor.texto)}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="pagina">📄 {html.escape(valor.ancoragem)}</div>',
        unsafe_allow_html=True,
    )

    if not valor.rastreavel:
        st.caption("⚠️ valor localizado, mas sem trecho de origem registrado")

    if valor.trecho:
        with st.popover("De onde veio", icon="🔎", width="stretch"):
            _prova_de_origem(valor, documentos.get(valor.apolice))


def _prova_de_origem(valor: ValorNaTela, caminho: Path | None) -> None:
    """O trecho citado e, quando o arquivo está à mão, a página renderizada."""
    st.markdown("**Trecho de origem**")
    st.markdown(
        f'<div class="trecho">{html.escape(valor.trecho or "")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="pagina">📄 {html.escape(valor.ancoragem)}</div>',
        unsafe_allow_html=True,
    )

    if valor.observacao:
        st.warning(valor.observacao)

    if caminho is None:
        st.caption("O arquivo original não está nesta máquina, então não há página para exibir.")
        return

    if caminho.suffix.lower() != ".pdf":
        st.caption(f"{caminho.name} é imagem: a conferência é o próprio arquivo enviado.")
        return

    if not valor.pagina:
        return

    imagem = pagina_em_imagem(str(caminho), valor.pagina)
    if imagem is None:
        st.caption("Não foi possível renderizar esta página do PDF.")
        return
    st.image(imagem, caption=f"página {valor.pagina} de {caminho.name}", width="stretch")


def _cartao(cartao: CartaoDiferenca, documentos: dict[str, Path | None]) -> None:
    """Um campo, com o valor de cada apólice lado a lado (D.2 e D.3)."""
    with st.container(border=True):
        titulo, selo = st.columns([4.2, 1.6], vertical_alignment="top")
        with titulo:
            st.markdown(
                f'<div class="campo-titulo">{html.escape(cartao.rotulo)}</div>'
                f'<div class="campo-significado">{html.escape(cartao.significado)}</div>',
                unsafe_allow_html=True,
            )
        with selo:
            est = cartao.estilo
            st.badge(est.rotulo, icon=est.icone, color=est.cor)

        colunas = st.columns(len(cartao.valores), gap="medium")
        for coluna, valor in zip(colunas, cartao.valores):
            with coluna:
                _valor(valor, documentos)

        st.markdown(
            f'<div class="porque"><b>Por que importa:</b> '
            f"{html.escape(cartao.porque_importa)}</div>",
            unsafe_allow_html=True,
        )


def _secao(titulo: str, contagem: int | None = None) -> None:
    sufixo = (
        f' <span class="contagem">— {contagem} campo{"s" if contagem != 1 else ""}</span>'
        if contagem is not None
        else ""
    )
    st.markdown(f'<div class="secao">{titulo}{sufixo}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------


def barra_lateral(
    banco: Banco, itens: list[dict], dic: DicionarioCampos
) -> tuple[list[str], bool, set[Veredito]]:
    """Escolha das apólices, filtros e o estado do ambiente.

    Devolve `(documentos selecionados, incluir iguais, situações escolhidas)`.
    """
    por_rotulo = {estilo(v).rotulo: v for v in SITUACOES_NO_FILTRO}

    with st.sidebar:
        st.markdown("### 🛡️ Comparador D&O")
        st.caption("Grupo Insurminds · I2A2 · Projeto Final")

        opcoes = [i["documento"] for i in itens]
        rotulos = {
            i["documento"]: (
                f"{i['seguradora'] or i['documento']} — "
                f"{i['encontrados']}/{i['total_campos']} campos"
            )
            for i in itens
        }

        # A seleção vive no `session_state` para sobreviver aos reruns, e a
        # limpeza a cada execução evita que um documento apagado do banco
        # continue selecionado — o que faria a tela comparar duas apólices e
        # mostrar uma só.
        atuais = [d for d in st.session_state.get("selecao", []) if d in opcoes]
        st.session_state["selecao"] = atuais or opcoes[:2]

        st.markdown("#### Apólices para comparar")
        selecionados = st.multiselect(
            "Apólices",
            options=opcoes,
            format_func=lambda d: rotulos.get(d, d),
            key="selecao",
            label_visibility="collapsed",
        )

        st.markdown("#### Filtros")
        incluir_iguais = st.toggle(
            "Incluir o que é igual nas duas",
            value=False,
            help="Por padrão a tela mostra só o que distingue as apólices: ausente "
                 "em uma delas, valores diferentes e redação divergente. Ligar "
                 "esta opção acrescenta também o que é igual nas duas e o que está "
                 "fora das duas.",
        )
        escolhidos = st.multiselect(
            "Situações a exibir",
            options=list(por_rotulo),
            default=list(por_rotulo),
            format_func=lambda r: f"{estilo(por_rotulo[r]).icone} {r}",
            help="Os rótulos são a tradução dos vereditos do motor de comparação "
                 "para a linguagem de quem contrata o seguro. O que é igual nas duas "
                 "entra pelo botão acima, nunca por este filtro.",
        )
        situacoes = {por_rotulo[r] for r in escolhidos}

        st.divider()
        if st.button("Recarregar as extrações de exemplo", icon="🧪", width="stretch"):
            gravadas, preservadas = semear_exemplos(banco, forcar=True)
            st.toast(f"{gravadas} apólice(s) de exemplo regravadas no banco")
            if preservadas:
                st.warning(aviso_de_preservadas(preservadas), icon="🔒")

        st.caption(
            f"{len(itens)} apólice(s) no banco · dicionário de {len(dic)} campos, "
            f"definido por {dic.definido_por}."
        )
        provedores = provedores_disponiveis()
        if provedores:
            st.caption("Modelos configurados no `.env`: " + ", ".join(provedores) + ".")
        else:
            st.caption(
                "Nenhuma chave de LLM no `.env`: a extração por modelo não roda nesta "
                "máquina. A comparação não depende dela."
            )

    return selecionados, incluir_iguais, situacoes


# ---------------------------------------------------------------------------
# Estado inicial
# ---------------------------------------------------------------------------


def estado_inicial() -> None:
    """O que a tela mostra quando ainda não há duas apólices escolhidas."""
    st.info(
        "Escolha ao menos **duas apólices** na barra lateral para ver a comparação.",
        icon="👈",
    )

    cartoes = [
        (
            "D.1 · Enviar",
            "Aceita PDF e imagem. A leitura acontece na ingestão da frente A, que "
            "preserva a página de cada trecho.",
            "📤",
        ),
        (
            "D.2 · Comparar",
            "As diferenças aparecem lado a lado, na ordem em que o motor as "
            "considera relevantes, com a explicação do especialista.",
            "⚖️",
        ),
        (
            "D.3 · Conferir",
            "Cada valor abre o trecho de origem e a página do PDF de onde saiu. "
            "Nenhum número aparece sem prova.",
            "🧭",
        ),
    ]
    for coluna, (titulo, texto, icone) in zip(st.columns(3, gap="medium"), cartoes):
        with coluna:
            with st.container(border=True):
                st.markdown(f"#### {icone} {titulo}")
                st.caption(texto)

    if st.button("Carregar as duas apólices de exemplo", type="primary", icon="🧪"):
        banco = banco_do_projeto()
        _, preservadas = semear_exemplos(banco, forcar=True)
        if preservadas:
            st.warning(aviso_de_preservadas(preservadas), icon="🔒")
        st.session_state["selecao"] = [i["documento"] for i in banco.listar()][:2]
        st.toast("Apólices de exemplo carregadas")
        st.rerun()


# ---------------------------------------------------------------------------
# Aba 1 — a comparação (D.2 e D.3)
# ---------------------------------------------------------------------------


def aba_comparacao(
    comparacao,
    apolices: list[ApoliceExtraida],
    documentos: dict[str, Path | None],
    incluir_iguais: bool,
    situacoes: set[Veredito],
) -> None:
    """Os números do topo e os cartões, agrupados por situação."""
    for coluna, kpi in zip(st.columns(len(montar_kpis(comparacao)), gap="small"), montar_kpis(comparacao)):
        with coluna:
            st.metric(kpi.rotulo, kpi.valor, help=kpi.ajuda, icon=kpi.icone, border=True)

    fora_das_duas = comparacao.resumo[Veredito.AUSENTE_EM_TODAS.value]
    st.caption(
        "Todos os campos do dicionário do especialista foram percorridos — é assim que "
        f"a ausência aparece como ausência. {fora_das_duas} campo(s) não são tratados "
        "por nenhuma das apólices."
    )

    cartoes = montar_cartoes(comparacao, apolices, apenas_relevantes=not incluir_iguais)
    if incluir_iguais:
        permitidos = set(situacoes) | {Veredito.IGUAL, Veredito.AUSENTE_EM_TODAS}
        cartoes = tuple(c for c in cartoes if c.veredito in permitidos)
    else:
        cartoes = tuple(c for c in cartoes if c.veredito in situacoes)

    with st.expander("Como ler os rótulos"):
        for est in legenda():
            st.markdown(f"{est.icone} **{est.rotulo}** — {est.explicacao}")

    if not cartoes:
        st.info(
            "Nenhum campo com as situações escolhidas. Os filtros da barra lateral "
            "decidem o que aparece aqui.",
            icon="🎯",
        )
        return

    grupos: dict[Veredito, list[CartaoDiferenca]] = {}
    for cartao in cartoes:
        grupos.setdefault(cartao.veredito, []).append(cartao)

    for veredito in sorted(grupos, key=lambda v: estilo(v).ordem):
        est = estilo(veredito)
        _secao(f"{est.icone} {est.rotulo}", len(grupos[veredito]))
        st.caption(est.explicacao)
        for cartao in grupos[veredito]:
            _cartao(cartao, documentos)

    st.caption(
        "O motor de comparação (frente C) decide o que difere e não usa modelo de "
        "linguagem: a mesma entrada devolve sempre a mesma saída. Explicar o peso de "
        "cada diferença é a tarefa do redator (C.4)."
    )


# ---------------------------------------------------------------------------
# Aba 2 — a tabela completa
# ---------------------------------------------------------------------------


def aba_tabela(comparacao) -> None:
    """A comparação inteira numa tabela, com o CSV para levar embora."""
    _secao("📋 A comparação inteira, campo a campo")
    st.caption(
        "É o mesmo veredito do motor, sem releitura: a interface não reinterpreta "
        "ninguém. Baixe em CSV para levar a comparação embora."
    )

    colunas, linhas = matriz_comparativa(comparacao)
    tabela = pd.DataFrame(linhas, columns=list(colunas))
    st.dataframe(_pintar(tabela), hide_index=True, width="stretch")

    esquerda, direita = st.columns([1.4, 2.6], vertical_alignment="center")
    with esquerda:
        st.download_button(
            "Baixar a comparação em CSV",
            data=exportar_csv(comparacao),
            file_name=nome_arquivo_csv(comparacao),
            mime="text/csv",
            icon="⬇️",
            width="stretch",
        )
    with direita:
        st.caption(
            "CSV com separador `;` e acentuação preservada — abre direto no Excel em "
            "português. A planilha é uma saída do protótipo; a decisão continua sendo "
            "de quem lê a apólice."
        )


def _cor_da_situacao(rotulo: str) -> str:
    """Pinta a célula da situação com a mesma cor do selo do cartão."""
    cor = FUNDO_SITUACAO.get(rotulo)
    return f"background-color: {cor}; font-weight: 600; color: #0F172A;" if cor else ""


def _pintar(tabela: pd.DataFrame):
    """Colore a coluna de situação sem depender da versão do pandas."""
    estilizador = tabela.style
    pintar = getattr(estilizador, "map", None) or estilizador.applymap
    return pintar(_cor_da_situacao, subset=["Situação"])


# ---------------------------------------------------------------------------
# Aba 3 — rastreabilidade (D.3)
# ---------------------------------------------------------------------------


def aba_rastreabilidade(comparacao, apolices: list[ApoliceExtraida]) -> None:
    """De onde veio cada valor: a página, o trecho e a página renderizada."""
    _secao("🧭 De onde veio cada valor")
    st.caption(
        "Um limite de indenização inventado passaria despercebido numa demonstração e "
        "destruiria a credibilidade numa pergunta. Por isso todo valor encontrado "
        "carrega a página e o trecho de origem — é o que separa este sistema de um "
        "chute bem formatado."
    )

    linhas = linhas_rastreabilidade(comparacao, apolices)
    if not linhas:
        st.info("Ainda não há valores encontrados para rastrear.", icon="🧭")
        return

    rastreaveis = sum(1 for linha in linhas if linha["Confere"] == "sim")
    for coluna, (rotulo, valor, ajuda, icone) in zip(
        st.columns(3, gap="small"),
        [
            ("Valores encontrados", len(linhas), "O que as apólices responderam.", "🔢"),
            ("Com origem registrada", rastreaveis, "Página e trecho apontados.", "📍"),
            (
                "Sem origem",
                len(linhas) - rastreaveis,
                "Valor localizado, mas sem registro de onde saiu — vale menos.",
                "⚠️",
            ),
        ],
    ):
        with coluna:
            st.metric(rotulo, valor, help=ajuda, icon=icone, border=True)

    tabela = pd.DataFrame(
        [
            {**linha, "Página": str(linha["Página"]) if linha["Página"] else TEXTO_SEM_PAGINA}
            for linha in linhas
        ]
    )
    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        column_config={
            "Campo": st.column_config.TextColumn(width="medium"),
            "Apólice": st.column_config.TextColumn(width="small"),
            "Valor": st.column_config.TextColumn(width="medium"),
            "Página": st.column_config.TextColumn(width="small"),
            "Trecho de origem": st.column_config.TextColumn(width="large"),
            "Confere": st.column_config.TextColumn(
                width="small", help="Se página e trecho foram registrados para este valor."
            ),
        },
    )

    rotulos = {d.campo.id: d.campo.rotulo for d in comparacao.diferencas}
    with st.expander("Ver os trechos de origem, um por um"):
        for apolice in apolices:
            st.markdown(f"#### {apolice.nome}")
            st.caption(
                f"{apolice.documento} · {apolice.rastreaveis} de {apolice.encontrados} "
                "valores com origem registrada"
            )
            for campo in apolice.campos:
                if not campo.encontrado:
                    continue
                rotulo = rotulos.get(campo.campo_id, campo.campo_id)
                st.markdown(
                    f"**{html.escape(rotulo)}** — "
                    f"{html.escape(formatar_pagina(campo.pagina, campo.paginas_possiveis))}"
                )
                st.markdown(
                    f'<div class="trecho">{html.escape(campo.trecho_origem or "")}</div>',
                    unsafe_allow_html=True,
                )
            st.divider()

    st.caption(
        "No cartão de cada campo, o botão **De onde veio** abre o mesmo trecho e a "
        "página do PDF renderizada — para conferir sem sair da tela."
    )


# ---------------------------------------------------------------------------
# Aba 4 — apólices guardadas e envio de documento (D.1)
# ---------------------------------------------------------------------------


def aba_apolices(
    apolices: list[ApoliceExtraida],
    dic: DicionarioCampos,
    banco: Banco,
    documentos: dict[str, Path | None],
) -> None:
    """O que está guardado e a porta de entrada de documento novo."""
    _secao("📄 Apólices em comparação")
    st.caption(
        "Este é o banco de apólices processadas (SQLite, frente C). Reprocessar uma "
        "apólice custa cota de modelo; reler do banco não custa nada — e a "
        "rastreabilidade sobrevive à gravação."
    )

    resumos = [resumir_apolice(a, dic) for a in apolices]
    for inicio in range(0, len(resumos), 2):
        for coluna, resumo in zip(st.columns(2, gap="medium"), resumos[inicio:inicio + 2]):
            with coluna:
                _cartao_apolice(resumo, documentos.get(resumo.nome))

    st.divider()
    _envio(banco)


def _cartao_apolice(resumo, caminho: Path | None) -> None:
    """O cartão de uma apólice: procedência, cobertura de campos e origem."""
    with st.container(border=True):
        st.markdown(
            f'<div class="apolice-nome">{html.escape(resumo.nome)}</div>'
            f'<div class="apolice-arquivo">{html.escape(resumo.documento)}</div>'
            f'<div class="apolice-fonte">{html.escape(resumo.fonte)}</div>',
            unsafe_allow_html=True,
        )
        st.progress(
            resumo.fracao_encontrada,
            text=f"{resumo.encontrados} de {resumo.total} campos do dicionário",
        )
        st.caption(
            f"{resumo.rastreaveis} valores com página e trecho de origem · "
            + (
                "arquivo original disponível para conferência"
                if caminho
                else "arquivo original não está nesta máquina"
            )
        )
        if resumo.veio_de_exemplo:
            st.badge("extração de exemplo — não é saída do sistema", icon="🧪", color="yellow")
        elif resumo.todas_rastreaveis:
            st.badge("todos os valores são rastreáveis", icon="📍", color="green")


def _envio(banco: Banco) -> None:
    """A porta de entrada: recebe o arquivo e o entrega à ingestão (D.1)."""
    _secao("📤 Enviar uma apólice")
    st.caption(
        "PDF ou imagem. Quem lê o documento é a ingestão da frente A — `pypdf` quando "
        "a página traz texto embutido, OCR quando não traz."
    )
    if not ocr_disponivel():
        st.caption(
            "⚠️ Tesseract não encontrado nesta máquina: PDF escaneado e imagem ficam de "
            "fora. PDF nativo é lido normalmente."
        )

    extrator = encontrar_extrator(carregar_modulo_extracao())
    if extrator is None:
        st.info(aviso_sem_extracao(), icon="🧩")
    else:
        st.success(
            "A extração das cláusulas está disponível: "
            f"`{extrator.__name__}`, publicada pela frente B em `app.agents`. "
            "O documento enviado já sai daqui com os campos estruturados.",
            icon="✅",
        )

    arquivos = st.file_uploader(
        "Envie a apólice",
        type=[extensao.lstrip(".") for extensao in FORMATOS_ACEITOS],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if arquivos and st.button("Processar documento(s)", type="primary", icon="📥"):
        _processar(arquivos, extrator, banco)


def _diagnostico(documento: DocumentoExtraido) -> None:
    """Os números medidos neste arquivo — nada aqui é estimado pela interface."""
    tokens = int(len(documento.texto_com_marcadores.split()) / 0.75)
    st.markdown(f"**{documento.nome_arquivo}** · {documento.tipo.value}, lido página a página")
    for coluna, (rotulo, valor, icone) in zip(
        st.columns(4, gap="small"),
        [
            ("Páginas", documento.total_paginas, "📄"),
            ("Por OCR", documento.paginas_por_ocr, "🔍"),
            ("Páginas vazias", documento.paginas_vazias, "⬜"),
            ("Tokens aprox.", f"{tokens:,}".replace(",", "."), "🧮"),
        ],
    ):
        with coluna:
            st.metric(rotulo, valor, icon=icone, border=True)

    with st.expander("Ver o começo do texto que o modelo vai receber"):
        st.markdown(
            f'<div class="trecho">{html.escape(documento.texto_com_marcadores[:1200])}</div>',
            unsafe_allow_html=True,
        )


def _processar(arquivos: list, extrator, banco: Banco) -> None:
    """Lê os arquivos enviados e diz, com honestidade, até onde dá para ir.

    A ingestão roda sempre. A extração só roda se a frente B já tiver publicado
    a função — e, quando não tiver, a tela explica em vez de mostrar campo vazio.
    """
    destino = Path(tempfile.mkdtemp(prefix="apolices_"))
    caminhos: list[Path] = []
    for arquivo in arquivos:
        caminho = destino / Path(arquivo.name).name
        caminho.write_bytes(arquivo.getvalue())
        caminhos.append(caminho)
        # guardar o caminho é o que permite, depois, mostrar a página de origem
        st.session_state.setdefault("enviados", {})[caminho.name] = str(caminho)

    with st.status("Lendo os documentos...", expanded=True) as estado:
        documentos, falhas = receber_varios(caminhos)
        for documento in documentos:
            _diagnostico(documento)
        for nome, motivo in falhas:
            st.error(f"**{nome}**: {motivo}")

        if not documentos:
            estado.update(label="Nenhum documento pôde ser lido", state="error")
            return

        if extrator is None:
            estado.update(
                label="Documento lido — falta a extração das cláusulas (frente B)",
                state="complete",
            )
            return

        guardadas = 0
        for documento in documentos:
            try:
                apolice = extrator(documento)
                ja_existia = banco.tem(apolice.documento)
                banco.salvar(apolice)
                guardadas += 1
                if ja_existia:
                    st.warning(
                        f"**{documento.nome_arquivo}**: substituiu a extração que já "
                        "estava no banco. O banco guarda uma versão por documento — a "
                        "última extração é a que vale."
                    )
                else:
                    st.success(
                        f"**{documento.nome_arquivo}**: {apolice.encontrados} campos "
                        "extraídos e guardados no banco."
                    )
            except Exception as exc:  # noqa: BLE001 — uma falha não derruba o lote (A.4)
                st.error(f"**{documento.nome_arquivo}**: a extração falhou — {exc}")

        estado.update(label=f"{guardadas} documento(s) extraídos e guardados", state="complete")
        st.info(
            "A apólice guardada entra na comparação: escolha-a na barra lateral.",
            icon="👈",
        )


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="Comparador de apólices D&O",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

    banco = banco_do_projeto()
    dic = dicionario_do_especialista()
    semear_exemplos(banco)
    itens = banco.listar()

    selecionados, incluir_iguais, situacoes = barra_lateral(banco, itens, dic)
    apolices = banco.carregar_varias(selecionados)

    if len(apolices) < 2:
        cabecalho()
        estado_inicial()
        rodape()
        return

    cabecalho(" × ".join(a.nome for a in apolices))

    if usando_exemplos(apolices):
        st.warning(
            "**Demonstração sobre extrações de exemplo.** A frente B (extração das "
            "cláusulas com IA generativa) ainda está sendo escrita. Os campos "
            "comparados aqui foram escritos à mão em `app/domain/exemplos.py`, "
            "imitando as condições gerais reais, para a interface não ficar parada. "
            "Eles **não são resultado do sistema** e não podem ser apresentados como "
            "tal — a ingestão e o motor de comparação, esses sim, são reais.",
            icon="🧪",
        )

    comparacao = comparar(apolices, dic)
    documentos = documentos_por_apolice(apolices)

    abas = st.tabs(
        ["🔍 Comparação", "📋 Tabela completa", "🧭 Rastreabilidade", "📄 Apólices e envio"]
    )
    with abas[0]:
        aba_comparacao(comparacao, apolices, documentos, incluir_iguais, situacoes)
    with abas[1]:
        aba_tabela(comparacao)
    with abas[2]:
        aba_rastreabilidade(comparacao, apolices)
    with abas[3]:
        aba_apolices(apolices, dic, banco, documentos)

    rodape()


if __name__ == "__main__":
    main()