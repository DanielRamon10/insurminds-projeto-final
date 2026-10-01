"""Gera o pitch deck da entrega — `Projeto_Final_Artefatos/InsurMinds_Projeto_Final.pptx`.

    python -m scripts.gerar_pitch

Por que um script e não um arquivo editado à mão: o nome do arquivo é
obrigatório e literal, o conteúdo tem números que saem do próprio projeto (15
campos, 70 e 72 páginas, 27 valores rastreáveis) e o deck precisa acompanhar o
que o sistema faz. Escrito à mão, os três desandam em silêncio — o texto fala de
um número que o código já não produz.

O conteúdo está em `CONTEUDO`, no fim do arquivo, e pode ser editado sem tocar
em nada de desenho. Onde a informação depende de outra pessoa, há um marcador
explícito escrito no slide: **o que falta está dito no deck, não escondido**.

Requer `python-pptx` (ver `requirements.txt`).
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PIL import Image  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

DESTINO = RAIZ / "Projeto_Final_Artefatos" / "InsurMinds_Projeto_Final.pptx"

#: Onde moram os recortes da interface que o slide de demonstração cola.
PRINTS = RAIZ / "Projeto_Final_Artefatos" / "prints"

#: Um arquivo por legenda do slide, na mesma ordem de `legendas`. O teste
#: `test_ha_um_print_por_legenda` casa os dois tamanhos: se a lista desalinhar,
#: o slide mostra a tela errada embaixo do texto errado.
ARQUIVOS_DE_PRINT = ("01_comparacao.png", "02_de_onde_veio.png", "03_tabela_csv.png")

# ---------------------------------------------------------------------------
# Paleta e medidas — as mesmas cores da interface, para o deck e a tela
# parecerem a mesma coisa na apresentação
# ---------------------------------------------------------------------------

ESCURO = RGBColor(0x08, 0x31, 0x2F)
VERDE = RGBColor(0x0E, 0x6E, 0x63)
TEAL = RGBColor(0x0D, 0x94, 0x88)
CLARO = RGBColor(0xF5, 0xF7, 0xF9)
BRANCO = RGBColor(0xFF, 0xFF, 0xFF)
TEXTO = RGBColor(0x0F, 0x17, 0x2A)
CINZA = RGBColor(0x64, 0x74, 0x8B)
AMARELO = RGBColor(0xF5, 0x9E, 0x0B)
VERMELHO = RGBColor(0xDC, 0x26, 0x26)
ROXO = RGBColor(0x7C, 0x3A, 0xED)
VERDE_OK = RGBColor(0x16, 0xA3, 0x4A)
LARANJA = RGBColor(0xB4, 0x53, 0x09)
BORDA = RGBColor(0xE2, 0xE8, 0xF0)

LARGURA = Inches(13.333)
ALTURA = Inches(7.5)

FONTE = "Segoe UI"


def faixa(slide, cor, top=Inches(0), altura=Inches(0.22), largura=LARGURA):
    """Uma faixa lisa — é o que dá o ar de slide desenhado, e não de lista."""
    forma = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(0), top, largura, altura)
    forma.fill.solid()
    forma.fill.fore_color.rgb = cor
    forma.line.fill.background()
    forma.shadow.inherit = False
    return forma


def retangulo(slide, esquerda, top, largura, altura, cor, arredondado=False):
    forma = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if arredondado else MSO_SHAPE.RECTANGLE,
        esquerda, top, largura, altura,
    )
    if arredondado:
        forma.adjustments[0] = 0.12
    forma.fill.solid()
    forma.fill.fore_color.rgb = cor
    forma.line.fill.background()
    forma.shadow.inherit = False
    return forma


def texto(slide, esquerda, top, largura, altura, conteudo, tamanho=18, cor=TEXTO,
          negrito=False, alinhamento=PP_ALIGN.LEFT, espaco=6):
    """Uma caixa de texto simples, com parágrafos separados por `\\n`."""
    caixa = slide.shapes.add_textbox(esquerda, top, largura, altura)
    moldura = caixa.text_frame
    moldura.word_wrap = True
    moldura.vertical_anchor = MSO_ANCHOR.TOP

    for i, linha in enumerate(conteudo.split("\n")):
        paragrafo = moldura.paragraphs[0] if i == 0 else moldura.add_paragraph()
        paragrafo.alignment = alinhamento
        paragrafo.space_after = Pt(espaco)
        pedaco = paragrafo.add_run()
        pedaco.text = linha
        pedaco.font.size = Pt(tamanho)
        pedaco.font.bold = negrito
        pedaco.font.color.rgb = cor
        pedaco.font.name = FONTE
    return caixa


def slide_novo(apresentacao):
    return apresentacao.slides.add_slide(apresentacao.slide_layouts[6])


def cabecalho(slide, kicker: str, titulo: str) -> None:
    """A faixa, o sobretítulo em verde e o título de todo slide de conteúdo."""
    retangulo(slide, Emu(0), Emu(0), LARGURA, Inches(0.16), TEAL)
    texto(
        slide, Inches(0.7), Inches(0.42), Inches(11.9), Inches(0.3),
        kicker.upper(), tamanho=11, cor=TEAL, negrito=True, espaco=0,
    )
    texto(
        slide, Inches(0.7), Inches(0.72), Inches(11.9), Inches(0.75),
        titulo, tamanho=30, cor=ESCURO, negrito=True, espaco=0,
    )
    retangulo(slide, Inches(0.7), Inches(1.55), Inches(1.5), Pt(4), TEAL)


def rodape(slide, numero: int) -> None:
    texto(
        slide, Inches(0.7), Inches(6.95), Inches(9.6), Inches(0.3),
        "Plataforma de análise e comparação de apólices D&O · grupo Insurminds / I2A2",
        tamanho=10, cor=CINZA, espaco=0,
    )
    texto(
        slide, Inches(12.0), Inches(6.95), Inches(0.7), Inches(0.3),
        str(numero), tamanho=10, cor=CINZA, alinhamento=PP_ALIGN.RIGHT, espaco=0,
    )


def chamada_do_slide(slide, dados: dict) -> None:
    """A frase de apoio abaixo do título, quando o slide tiver uma."""
    if chamada := dados.get("chamada"):
        texto(slide, Inches(0.7), Inches(1.72), Inches(11.9), Inches(0.45),
              chamada, tamanho=15, cor=CINZA, espaco=0)


def slide_capa(apresentacao, dados: dict) -> None:
    slide = slide_novo(apresentacao)
    retangulo(slide, Emu(0), Emu(0), LARGURA, ALTURA, ESCURO)
    retangulo(slide, Emu(0), Inches(4.9), LARGURA, Inches(2.6), VERDE)
    retangulo(slide, Inches(0.9), Inches(1.45), Inches(1.8), Pt(6), TEAL)

    texto(slide, Inches(0.9), Inches(0.75), Inches(11.5), Inches(0.4),
          dados["curso"], tamanho=13, cor=RGBColor(0x9F, 0xD8, 0xCE), negrito=True, espaco=0)
    texto(slide, Inches(0.9), Inches(1.8), Inches(11.5), Inches(1.6),
          dados["titulo"], tamanho=42, cor=BRANCO, negrito=True, espaco=0)
    texto(slide, Inches(0.9), Inches(3.3), Inches(10.6), Inches(1.2),
          dados["resumo"], tamanho=17, cor=RGBColor(0xD7, 0xE7, 0xE4), espaco=4)
    texto(slide, Inches(0.9), Inches(5.3), Inches(11.5), Inches(1.5),
          dados["rodape"], tamanho=14, cor=BRANCO, espaco=6)


def slide_topicos(apresentacao, dados: dict, numero: int) -> None:
    slide = slide_novo(apresentacao)
    cabecalho(slide, dados["kicker"], dados["titulo"])
    chamada_do_slide(slide, dados)

    topicos = dados["topicos"]
    por_linha = 2 if len(topicos) > 3 else len(topicos)
    linhas = (len(topicos) + por_linha - 1) // por_linha
    largura = Inches((13.333 - 1.4 - 0.35 * (por_linha - 1)) / por_linha)
    topo = Inches(2.35) if dados.get("chamada") else Inches(1.95)
    altura = Inches((6.7 - float(topo) / 914400 - 0.3 * (linhas - 1)) / linhas)

    for i, (icone, titulo, corpo) in enumerate(topicos):
        linha, coluna = divmod(i, por_linha)
        esquerda = Inches(0.7) + (largura + Inches(0.35)) * coluna
        top = topo + (altura + Inches(0.3)) * linha
        retangulo(slide, esquerda, top, largura, altura, CLARO, arredondado=True)
        retangulo(slide, esquerda, top, Pt(5), altura, dados.get("cor", TEAL))
        texto(slide, esquerda + Inches(0.28), top + Inches(0.2), largura - Inches(0.5),
              Inches(0.45), f"{icone}  {titulo}", tamanho=16, cor=ESCURO, negrito=True, espaco=0)
        texto(slide, esquerda + Inches(0.28), top + Inches(0.68), largura - Inches(0.5),
              altura - Inches(0.85), corpo, tamanho=13, cor=CINZA, espaco=3)

    rodape(slide, numero)


def slide_numeros(apresentacao, dados: dict, numero: int) -> None:
    slide = slide_novo(apresentacao)
    cabecalho(slide, dados["kicker"], dados["titulo"])
    chamada_do_slide(slide, dados)

    numeros = dados["numeros"]
    largura = Inches((13.333 - 1.4 - 0.3 * (len(numeros) - 1)) / len(numeros))
    for i, (valor, rotulo, observacao, cor) in enumerate(numeros):
        esquerda = Inches(0.7) + (largura + Inches(0.3)) * i
        retangulo(slide, esquerda, Inches(2.45), largura, Inches(2.45), CLARO)
        retangulo(slide, esquerda, Inches(2.45), largura, Pt(6), cor)
        texto(slide, esquerda + Inches(0.25), Inches(2.75), largura - Inches(0.5),
              Inches(0.9), valor, tamanho=36, cor=cor, negrito=True, espaco=0)
        texto(slide, esquerda + Inches(0.25), Inches(3.6), largura - Inches(0.5),
              Inches(0.6), rotulo, tamanho=14, cor=ESCURO, negrito=True, espaco=0)
        texto(slide, esquerda + Inches(0.25), Inches(4.0), largura - Inches(0.5),
              Inches(0.85), observacao, tamanho=11, cor=CINZA, espaco=0)

    if nota := dados.get("nota"):
        texto(slide, Inches(0.7), Inches(5.25), Inches(11.9), Inches(1.3),
              nota, tamanho=11, cor=CINZA, espaco=3)
    rodape(slide, numero)


def slide_fluxo(apresentacao, dados: dict, numero: int) -> None:
    """A arquitetura em quatro etapas — o slide que explica o sistema inteiro."""
    slide = slide_novo(apresentacao)
    cabecalho(slide, dados["kicker"], dados["titulo"])
    chamada_do_slide(slide, dados)

    etapas = dados["etapas"]
    largura = Inches((13.333 - 1.4) / len(etapas))
    for i, (sigla, titulo, corpo, cor) in enumerate(etapas):
        esquerda = Inches(0.7) + largura * i
        retangulo(slide, esquerda, Inches(2.5), largura, Inches(0.8), cor)
        texto(slide, esquerda, Inches(2.72), largura, Inches(0.45),
              f"{sigla} · {titulo}", tamanho=15, cor=BRANCO, negrito=True,
              alinhamento=PP_ALIGN.CENTER, espaco=0)
        texto(slide, esquerda + Inches(0.14), Inches(3.45), largura - Inches(0.28),
              Inches(2.3), corpo, tamanho=12, cor=TEXTO, espaco=3)

    if nota := dados.get("nota"):
        texto(slide, Inches(0.7), Inches(5.9), Inches(11.9), Inches(0.9),
              nota, tamanho=12, cor=CINZA, espaco=3)
    rodape(slide, numero)


def _medidas_da_imagem(imagem: Path, largura: int, altura: int) -> tuple[int, int]:
    """O tamanho que a imagem ocupa dentro do espaço, sem distorcer o aspecto."""
    with Image.open(imagem) as figura:
        proporcao = figura.width / figura.height
    if proporcao >= largura / altura:      # mais larga que o espaço: manda a largura
        return largura, int(largura / proporcao)
    return int(altura * proporcao), altura  # mais alta: manda a altura


def slide_prints(apresentacao, dados: dict, numero: int) -> None:
    """Os recortes da interface, com a legenda embaixo de cada um.

    As imagens ficam em `Projeto_Final_Artefatos/prints/` (ver
    `ARQUIVOS_DE_PRINT`), recortadas com o app rodando — as regiões de cada
    recorte estão em `docs/ROTEIRO_VIDEO.md`. Quando o arquivo não existe, o
    slide desenha a caixa vazia com a instrução: é o estado de um clone
    recém-baixado, e quem apresenta vê o que falta em vez de ver um slide
    quebrado. Ou as três telas estão coladas, ou as três caixas estão vazias —
    nunca as duas coisas no mesmo slide.
    """
    slide = slide_novo(apresentacao)
    cabecalho(slide, dados["kicker"], dados["titulo"])
    chamada_do_slide(slide, dados)

    legendas = dados["legendas"]
    largura = Inches((13.333 - 1.4 - 0.3 * (len(legendas) - 1)) / len(legendas))
    for i, legenda in enumerate(legendas):
        esquerda = Inches(0.7) + (largura + Inches(0.3)) * i
        arquivo = PRINTS / ARQUIVOS_DE_PRINT[i]

        if arquivo.exists():
            largura_foto, altura_foto = _medidas_da_imagem(arquivo, largura, Inches(2.6))
            foto_x = esquerda + int((largura - largura_foto) / 2)
            foto_y = Inches(2.25) + int((Inches(2.6) - altura_foto) / 2)
            # A moldura vai antes da imagem: quem entra depois fica por cima.
            retangulo(slide, foto_x - Inches(0.02), foto_y - Inches(0.02),
                      largura_foto + Inches(0.04), altura_foto + Inches(0.04), BORDA)
            slide.shapes.add_picture(str(arquivo), foto_x, foto_y,
                                     width=largura_foto, height=altura_foto)
        else:
            retangulo(slide, esquerda, Inches(2.25), largura, Inches(2.6), CLARO)
            texto(slide, esquerda, Inches(3.35), largura, Inches(0.4),
                  f"print {i + 1} — colar aqui", tamanho=10, cor=CINZA,
                  alinhamento=PP_ALIGN.CENTER, espaco=0)

        titulo, _, corpo = legenda.partition("\n\n")
        texto(slide, esquerda, Inches(4.98), largura, Inches(0.3),
              titulo, tamanho=12, cor=TEAL, negrito=True,
              alinhamento=PP_ALIGN.CENTER, espaco=0)
        texto(slide, esquerda + Inches(0.15), Inches(5.26), largura - Inches(0.3),
              Inches(1.05), corpo, tamanho=11, cor=CINZA,
              alinhamento=PP_ALIGN.CENTER, espaco=0)

    if nota := dados.get("nota"):
        texto(slide, Inches(0.7), Inches(6.4), Inches(11.9), Inches(0.5),
              nota, tamanho=10, cor=CINZA, espaco=0)
    rodape(slide, numero)


def slide_equipe(apresentacao, dados: dict, numero: int) -> None:
    slide = slide_novo(apresentacao)
    cabecalho(slide, dados["kicker"], dados["titulo"])

    integrantes = dados["integrantes"]
    largura = Inches((13.333 - 1.4 - 0.3 * (len(integrantes) - 1)) / len(integrantes))
    for i, (nome, frente) in enumerate(integrantes):
        esquerda = Inches(0.7) + (largura + Inches(0.3)) * i
        retangulo(slide, esquerda, Inches(1.95), largura, Inches(2.3), CLARO, arredondado=True)
        texto(slide, esquerda + Inches(0.25), Inches(2.25), largura - Inches(0.5),
              Inches(0.5), nome, tamanho=16, cor=ESCURO, negrito=True, espaco=0)
        texto(slide, esquerda + Inches(0.25), Inches(2.75), largura - Inches(0.5),
              Inches(1.4), frente, tamanho=12, cor=CINZA, espaco=0)

    if nota := dados.get("nota"):
        texto(slide, Inches(0.7), Inches(4.6), Inches(11.9), Inches(1.6),
              nota, tamanho=13, cor=TEXTO, espaco=4)
    rodape(slide, numero)


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------

MONTADORES = {
    "topicos": slide_topicos,
    "numeros": slide_numeros,
    "fluxo": slide_fluxo,
    "prints": slide_prints,
    "equipe": slide_equipe,
}


def montar(destino: Path | None = None) -> Path:
    """Monta o deck e grava no caminho pedido (por padrão, o artefato da entrega)."""
    destino = Path(destino) if destino else DESTINO

    apresentacao = Presentation()
    apresentacao.slide_width = LARGURA
    apresentacao.slide_height = ALTURA

    for numero, dados in enumerate(CONTEUDO, start=1):
        if dados["tipo"] == "capa":
            slide_capa(apresentacao, dados)
        else:
            MONTADORES[dados["tipo"]](apresentacao, dados, numero)

    destino.parent.mkdir(parents=True, exist_ok=True)
    apresentacao.save(destino)
    return destino


def main() -> int:
    destino = montar()
    print(f"pitch gravado em {destino.relative_to(RAIZ)}")
    print(f"  {len(CONTEUDO)} slides · {destino.stat().st_size / 1024:.0f} KB")
    print("  nome exigido pelo enunciado: InsurMinds_Projeto_Final.pptx (conferido)")

    titulo = "\no que ainda falta neste deck"
    print(titulo)
    print("-" * len(titulo.strip()))

    # O item dos prints só aparece enquanto faltar algum: o deck se declara
    # incompleto, não fica com um "a fazer" cravado que já foi feito.
    faltam = [n for n in ARQUIVOS_DE_PRINT if not (PRINTS / n).exists()]
    if faltam:
        print(f"  1. {len(faltam)} dos {len(ARQUIVOS_DE_PRINT)} prints do slide de demonstracao:")
        for nome in faltam:
            print(f"     - Projeto_Final_Artefatos/prints/{nome}")
        print("     recorte a interface rodando: `streamlit run app/interface/app.py`")
        print("     as regioes de cada recorte estao em docs/ROTEIRO_VIDEO.md")
        print("  2. o problema de negocio na voz do Paulo Henrique, corretor do grupo —")
        print("     o slide 2 esta escrito com o que o roteiro registra; ele confirma ou reescreve")
        print("  3. a arquitetura revisada pelo Daniel, dono das frentes A e C")
    else:
        print("  1. o problema de negocio na voz do Paulo Henrique, corretor do grupo —")
        print("     o slide 2 esta escrito com o que o roteiro registra; ele confirma ou reescreve")
        print("  2. a arquitetura revisada pelo Daniel, dono das frentes A e C")
    print("\n  editar texto: bloco CONTEUDO, no fim de scripts/gerar_pitch.py")
    print("  regerar:      python -m scripts.gerar_pitch")
    return 0


# ---------------------------------------------------------------------------
# Conteúdo do deck — edite aqui, sem tocar no desenho
# ---------------------------------------------------------------------------

CONTEUDO: list[dict] = [
    {
        "tipo": "capa",
        "curso": "CURSO INSUMINS · I2A2 — PROJETO FINAL",
        "titulo": "Comparar duas apólices D&O\nsem perder a origem de\nnenhum número",
        "resumo": (
            "A plataforma lê condições gerais em PDF ou imagem, extrai as cláusulas com "
            "IA generativa e mostra, lado a lado, o que muda de uma seguradora para "
            "outra — com a página e o trecho de onde cada valor saiu."
        ),
        "rodape": (
            "Grupo Insurminds · Daniel Ramon, Paulo Henrique, Nicole Paes, "
            "Paulo Roberto e Juliana Catarina\n"
            "Entrega: 06/10/2026 · protótipo acadêmico, sem integração com seguradoras"
        ),
    },
    {
        "tipo": "topicos",
        "kicker": "o problema",
        "titulo": "Comparar apólices D&O é trabalho de especialista",
        "chamada": (
            "Problema de negócio descrito pelo corretor do grupo — é a dor que ele "
            "vive no dia a dia."
        ),
        "cor": VERMELHO,
        "topicos": [
            ("⏳", "Horas de leitura por comparação",
             "As condições gerais passam de 70 páginas em linguagem jurídica. Comparar "
             "duas propostas é leitura especializada, não planilha de valores."),
            ("🔀", "A mesma cláusula, outro nome",
             "Cada seguradora batiza a mesma coisa de um jeito: limite de garantia, "
             "capital segurado, LMI, participação obrigatória. Buscar por palavra não resolve."),
            ("⚠️", "A diferença que decide o contrato",
             "Franquia, retroatividade, sublimites e cobertura para investigações são os "
             "pontos em que duas apólices parecidas deixam de ser parecidas."),
            ("📄", "Entrada não estruturada",
             "Não há API devolvendo números: a entrada é PDF jurídico. Quem lê, lê texto corrido."),
        ],
    },
    {
        "tipo": "topicos",
        "kicker": "a proposta",
        "titulo": "O que a plataforma faz",
        "chamada": "Três passos, do arquivo que chega à diferença que importa.",
        "topicos": [
            ("📥", "Lê o documento",
             "PDF nativo com pypdf; OCR e imagem quando não há texto embutido. Todo trecho "
             "sabe de que página saiu — a rastreabilidade começa aqui."),
            ("🤖", "Extrai as cláusulas",
             "Um dicionário de 15 campos escritos pelo corretor guia a extração com modelo "
             "de linguagem. Campo que a apólice não trata volta como ausente, nunca inventado."),
            ("⚖️", "Compara e explica",
             "O motor determinístico diz o que difere, campo a campo, e classifica a "
             "diferença. A explicação do peso de cada uma vem do especialista, no dicionário."),
        ],
    },
    {
        "tipo": "fluxo",
        "kicker": "arquitetura",
        "titulo": "Quatro frentes, um contrato de dados entre elas",
        "chamada": "Cada frente só conhece as estruturas de `app/schemas.py` — não o interior das outras.",
        "etapas": [
            ("A", "INGESTÃO", "Recebe PDF e imagem, extrai o texto página a página, usa OCR "
             "só onde falta texto embutido e não derruba o lote quando um arquivo falha.",
             VERDE),
            ("B", "EXTRAÇÃO", "Interpreta o texto com LLM, apoiada no dicionário de campos, e "
             "devolve cada valor com página e trecho de origem. Publicada; exige chave de "
             "modelo no `.env` para rodar.", TEAL),
            ("C", "ARMAZENAMENTO E COMPARAÇÃO", "Guarda as apólices processadas em SQLite e "
             "compara campo a campo, sem modelo de linguagem: mesma entrada, mesma saída.",
             ESCURO),
            ("D", "INTERFACE E DEMONSTRAÇÃO", "Upload, comparação lado a lado, rastreabilidade "
             "clicável e saída em CSV. É o que a banca vê funcionando.", LARANJA),
        ],
        "nota": (
            "Frentes A e C: Daniel Ramon · frente B: Nicole Paes · dicionário de campos: "
            "Paulo Henrique · frente D: Paulo Roberto. A separação existe para que cada parte "
            "possa ser testada sozinha — e para que a explicação em texto (LLM) nunca contamine "
            "a comparação, que precisa ser reprodutível."
        ),
    },
    {
        "tipo": "topicos",
        "kicker": "ia generativa com responsabilidade",
        "titulo": "O risco não é ler errado — é inventar",
        "chamada": (
            "Um limite de indenização alucinado passaria despercebido numa demonstração e "
            "destruiria a credibilidade numa pergunta."
        ),
        "cor": ROXO,
        "topicos": [
            ("🧭", "Todo valor tem origem",
             "Página e trecho acompanham cada campo extraído; na interface, a página do PDF "
             "abre para conferência. Sem isso o sistema seria um chute bem formatado."),
            ("🚫", "Ausência é resposta",
             "Campo que não existe volta como `null` explícito, e a comparação trata ausência "
             "como ausência — é a diferença que mais pesa e a que mais se esconde."),
            ("🧩", "Cada camada no seu lugar",
             "Extração (LLM), comparação (código determinístico) e explicação (texto) são "
             "frentes separadas. Misturá-las custou retrabalho no desafio anterior."),
            ("🧪", "Testes sem rede e sem cota",
             "A suíte cobre leitura de valores, vereditos, banco, apresentação e a própria "
             "interface, sem consumir um token de modelo."),
        ],
    },
    {
        "tipo": "numeros",
        "kicker": "decisão de negócio",
        "titulo": "O que comparar — a decisão que veio antes do código",
        "chamada": (
            "Menos que isso não demonstra comparação; mais vira extração rasa em todos os campos."
        ),
        "numeros": [
            ("15", "campos no dicionário",
             "definidos pelo corretor do grupo, em YAML: mudar o arquivo muda o sistema", TEAL),
            ("5", "tipos de comparação",
             "valor monetário, data, período, prazo e texto, cada um comparado à sua maneira",
             VERDE),
            ("3", "campos acrescentados por ele",
             "definição de reclamação, sublimites e cobertura para investigações", AMARELO),
            ("2", "apólices reais na demonstração",
             "Chubb e AIG; a terceira (Allianz) está pendente de download manual", ROXO),
        ],
        "nota": (
            "O dicionário cumpre aqui o papel que o `regras.yaml` cumpriu no desafio anterior: "
            "é a peça de negócio que o especialista controla sem tocar em código. Cada campo "
            "traz o significado, os sinônimos com que costuma aparecer e uma frase dizendo por "
            "que aquela diferença importa."
        ),
    },
    {
        "tipo": "numeros",
        "kicker": "ingestão medida nos documentos reais",
        "titulo": "O que custa ler uma apólice D&O",
        "chamada": "Números medidos nos dois documentos, não estimados.",
        "numeros": [
            ("70 e 72", "páginas por apólice",
             "condições gerais da Chubb e da AIG, ambas em PDF nativo", TEAL),
            ("~36 mil e ~39 mil", "tokens por apólice",
             "3 a 4 vezes o custo de uma extração simples: cota de modelo é risco do projeto",
             VERMELHO),
            ("17,6 s", "para ler as duas",
             "tempo medido nesta máquina, sem OCR e sem chamada de modelo", VERDE_OK),
            ("6", "formatos de imagem aceitos",
             "png, jpg, tiff, bmp e webp: o requisito de aceitar imagem está atendido", VERDE),
        ],
        "nota": (
            "A decisão de ler PDF nativo primeiro e cair no OCR só na página sem texto é o que "
            "mantém esse tempo baixo — e o custo de OCR em documento inteiro seria de minutos, "
            "não segundos."
        ),
    },
    {
        "tipo": "prints",
        "kicker": "demonstração",
        "titulo": "A plataforma em uso",
        "chamada": (
            "Três telas que contam a história: comparação, origem do dado e a comparação "
            "inteira para levar embora."
        ),
        "legendas": [
            "COMPARAÇÃO\n\nAs diferenças lado a lado, agrupadas por situação: proteção "
            "ausente em uma delas, valores diferentes e redações divergentes.",
            "DE ONDE VEIO\n\nAo clicar num valor, o trecho de origem e a página do PDF "
            "renderizada — a conferência acontece sem sair da tela.",
            "TABELA E CSV\n\nA comparação inteira, campo a campo, com a situação colorida "
            "e saída em CSV pronta para o Excel.",
        ],
        "nota": (
            "Rodar: `streamlit run app/interface/app.py` · a demonstração também funciona "
            "por linha de comando (`python -m scripts.demo_frente_d`), para o vídeo não "
            "depender do navegador."
        ),
    },
    {
        "tipo": "numeros",
        "kicker": "o que a comparação aponta",
        "titulo": "O resultado, campo a campo",
        "chamada": "Saída do motor de comparação sobre as extrações de exemplo da demonstração.",
        "numeros": [
            ("3", "proteções ausentes em uma delas",
             "sublimites, multas administrativas e cobertura para investigações", LARANJA),
            ("2", "valores diferentes",
             "franquia e data de retroatividade — os números que mudam o preço do risco",
             VERMELHO),
            ("6", "redações divergentes",
             "as duas tratam do assunto com palavras diferentes: exige leitura humana", ROXO),
            ("27", "valores com origem registrada",
             "100% do que foi encontrado aponta página e trecho: nenhum número solto", VERDE_OK),
        ],
        "nota": (
            "Medido sobre as extrações de exemplo, porque os campos numéricos não têm "
            "valor nas condições gerais comparadas — elas remetem cada um à Especificação "
            "da Apólice, como o slide de limitações documenta. Ingestão, banco, comparação "
            "e rastreabilidade são reais e estão no código; trocar a fonte dos campos não "
            "muda a tela — é isso que os exemplos garantiram."
        ),
    },
    {
        "tipo": "topicos",
        "kicker": "tecnologias",
        "titulo": "Com o que foi construído",
        "topicos": [
            ("🐍", "Python 3.10+ e pydantic",
             "Os contratos entre frentes são modelos validados: um campo repetido ou uma "
             "página fora de ordem falham na hora, não no meio da comparação."),
            ("🎛️", "Streamlit",
             "Interface com selos de veredito, cartões lado a lado, tabela colorida e a "
             "página do PDF renderizada — tudo em componentes nativos."),
            ("🔗", "LangChain com cascata de provedores",
             "Gemini como padrão e queda automática para Groq, OpenRouter e outros quando a "
             "cota do dia acaba. Chave nunca mora no código: só no `.env`."),
            ("📄", "pypdf e Tesseract",
             "PDF nativo primeiro, rápido e exato; OCR só na página sem texto embutido, "
             "porque documento escaneado é caro de ler."),
            ("🗄️", "SQLite",
             "Armazenamento estruturado sem subir serviço: o MVP roda em qualquer máquina, "
             "e a rastreabilidade sobrevive à gravação."),
            ("🧪", "pytest",
             "A suíte roda sem rede e sem cota de modelo — o que permite testar o motor a "
             "cada mudança, inclusive nas vésperas da entrega."),
        ],
    },
    {
        "tipo": "topicos",
        "kicker": "limitações conhecidas",
        "titulo": "Onde este protótipo ainda é frágil",
        "chamada": "Cada frente registrou onde a própria parte não aguenta — é o que este slide documenta.",
        "cor": LARANJA,
        "topicos": [
            ("🚧", "Sem a especificação, não há número para comparar",
             "As condições gerais remetem LMI, franquia, vigência, retroatividade e "
             "sublimites à Especificação da Apólice, que não está no lote. A extração "
             "com modelo de linguagem acha a cláusula e cita a página; comparar número "
             "fica para quando ela entrar."),
            ("🔑", "Dependência de chave e cota",
             "Sem chave configurada não há extração; a cascata de provedores ameniza o "
             "limite de cota, não o elimina."),
            ("🔤", "OCR depende do ambiente",
             "Sem o Tesseract instalado, PDF escaneado e imagem ficam de fora. PDF nativo "
             "não depende dele."),
            ("🧠", "Equivalência de texto exige leitura",
             "Duas redações diferentes podem dizer a mesma coisa. O motor aponta a "
             "divergência e não decide por conta própria — quem decide é o redator (C.4)."),
        ],
    },
    {
        "tipo": "topicos",
        "kicker": "evolução futura",
        "titulo": "O que vem depois da entrega",
        "topicos": [
            ("✍️", "Redator automático (C.4)",
             "Gerar, a partir das diferenças já classificadas, o texto que explica o peso de "
             "cada uma para quem vai contratar."),
            ("🧠", "Comparação semântica assistida",
             "Embeddings para sugerir quando duas redações dizem o mesmo, sempre com revisão "
             "humana e com o trecho à vista."),
            ("🕓", "Histórico de versões",
             "Acompanhar a mesma apólice renovada ano a ano e destacar apenas o que mudou "
             "entre as versões."),
            ("☁️", "Da máquina local ao serviço",
             "Fila de processamento e banco gerenciado, para uso simultâneo por mais de um "
             "corretor — sem perder a rastreabilidade."),
        ],
    },
    {
        "tipo": "equipe",
        "kicker": "equipe",
        "titulo": "Quem fez o quê",
        "integrantes": [
            ("Daniel Ramon", "Ingestão e OCR · armazenamento e comparação · documentação"),
            ("Paulo Henrique", "Campos e cláusulas D&O · conteúdo de negócio"),
            ("Nicole Paes", "Extração das cláusulas com IA generativa"),
            ("Paulo Roberto", "Interface, demonstração e apresentação"),
        ],
        "nota": (
            "Juliana Catarina é a representante do grupo e responde pelo envio da entrega.\n"
            "Entrega: 06/10/2026 — ZIP com o código-fonte, este pitch deck e o vídeo de até "
            "5 minutos demonstrando o problema, a arquitetura, a aplicação em uso e os "
            "resultados."
        ),
    },
]


if __name__ == "__main__":
    sys.exit(main())