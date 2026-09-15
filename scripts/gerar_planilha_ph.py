"""Gera a planilha da Fase 0 para o especialista de seguros do grupo (F0.1 e F0.2).

O Paulo Henrique é corretor e não programa. No Desafio 5 a planilha preenchível
funcionou muito melhor que qualquer texto explicando o que era preciso, então o
formato se repete aqui: ele reage a uma lista de candidatos em vez de escrever do
zero, e o resultado vira o dicionário de campos D&O (tarefa B.1).

    python -m scripts.gerar_planilha_ph
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs" / "FASE0_campos_apolice_DO.xlsx"

AZUL = "1F4E79"
CINZA_CLARO = "F2F6FA"
AMARELO = "FFF4CE"

#: Candidatos a campo comparável numa apólice D&O. Ele confirma, corrige e completa —
#: a coluna "Comparar?" é o que decide o escopo do projeto.
CANDIDATOS = [
    ("Limite Máximo de Indenização (LMI)",
     "Valor máximo que a seguradora paga no total da apólice",
     "Limite de Garantia, Capital Segurado, LMG"),
    ("Franquia / Retenção",
     "Valor que o segurado paga antes de a cobertura começar",
     "Participação Obrigatória do Segurado, Retention, Dedutível"),
    ("Vigência",
     "Data de início e fim da cobertura",
     "Período de Vigência, Prazo de Seguro"),
    ("Retroatividade",
     "A partir de que data atos anteriores à apólice ficam cobertos",
     "Data Retroativa, Cobertura Retroativa"),
    ("Prazo Complementar / Suplementar",
     "Tempo após o fim da apólice em que ainda se pode reclamar",
     "Extended Reporting Period, Prazo de Notificação"),
    ("Âmbito Geográfico",
     "Em que países a cobertura vale",
     "Abrangência Territorial, Jurisdição"),
    ("Definição de Segurado",
     "Quem exatamente está coberto (diretores, conselheiros, cônjuge, espólio)",
     "Pessoa Segurada, Insured Person"),
    ("Custos de Defesa",
     "Se honorários advocatícios entram e se consomem o limite",
     "Despesas de Defesa, Defence Costs"),
    ("Cobertura para Multas Administrativas",
     "Se multas de órgãos reguladores são cobertas",
     "Penalidades Civis e Administrativas"),
    ("Exclusão de Atos Dolosos",
     "Como a apólice trata fraude e dolo comprovado",
     "Conduta Dolosa, Atos Fraudulentos"),
    ("Exclusão de Poluição / Ambiental",
     "Se danos ambientais ficam de fora",
     "Riscos Ambientais"),
    ("Cláusula de Rescisão",
     "Em que condições a apólice pode ser cancelada",
     "Cancelamento, Resilição"),
]

FONTES_SUGERIDAS = [
    ("SUSEP", "Superintendência de Seguros Privados — condições gerais registradas",
     "https://www.susep.gov.br"),
    ("Site de seguradora", "Modelos de condições gerais publicados para consulta", ""),
    ("Corretora / material de mercado", "Condições padrão que circulam no setor", ""),
]


def cabecalho(ws, titulos: list[str], larguras: list[int]) -> None:
    fill = PatternFill("solid", fgColor=AZUL)
    borda = Border(bottom=Side(style="thin", color="AAB7C4"))
    for i, (titulo, largura) in enumerate(zip(titulos, larguras), start=1):
        c = ws.cell(row=1, column=i, value=titulo)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.fill = fill
        c.alignment = Alignment(vertical="center", wrap_text=True)
        c.border = borda
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "A2"


def aba_campos(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "1. Campos a comparar"

    cabecalho(
        ws,
        ["Campo", "O que significa", "Como aparece na apólice (outros nomes)",
         "Comparar?", "Por que importa (sua justificativa)"],
        [34, 46, 40, 13, 56],
    )

    validacao = DataValidation(type="list", formula1='"SIM,NAO,TALVEZ"', allow_blank=True)
    ws.add_data_validation(validacao)

    linha = 2
    for nome, significado, sinonimos in CANDIDATOS:
        ws.cell(row=linha, column=1, value=nome).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=linha, column=2, value=significado).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=linha, column=3, value=sinonimos).alignment = Alignment(wrap_text=True, vertical="top")
        c = ws.cell(row=linha, column=4)
        c.fill = PatternFill("solid", fgColor=AMARELO)
        c.alignment = Alignment(horizontal="center", vertical="top")
        validacao.add(c)
        d = ws.cell(row=linha, column=5)
        d.fill = PatternFill("solid", fgColor=AMARELO)
        d.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[linha].height = 42
        linha += 1

    # espaço para campos que faltaram na lista
    for extra in range(6):
        for col in range(1, 6):
            c = ws.cell(row=linha, column=col)
            c.fill = PatternFill("solid", fgColor=AMARELO if col in (1, 2, 4, 5) else CINZA_CLARO)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        validacao.add(ws.cell(row=linha, column=4))
        ws.row_dimensions[linha].height = 42
        linha += 1

    ws.cell(row=linha + 1, column=1,
            value="As linhas em amarelo são para você preencher. "
                  "As seis últimas estão vazias de propósito: se faltou algum campo "
                  "que você olha e que não está na lista, acrescente ali.").font = Font(
        italic=True, color="555555", size=10)


def aba_fontes(wb: Workbook) -> None:
    ws = wb.create_sheet("2. Onde achar apólices")
    cabecalho(ws, ["Fonte", "O que é", "Link", "Encontrou? (link ou arquivo)"],
              [30, 52, 34, 46])

    linha = 2
    for nome, oque, link in FONTES_SUGERIDAS:
        ws.cell(row=linha, column=1, value=nome).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=linha, column=2, value=oque).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=linha, column=3, value=link).alignment = Alignment(wrap_text=True, vertical="top")
        c = ws.cell(row=linha, column=4)
        c.fill = PatternFill("solid", fgColor=AMARELO)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[linha].height = 40
        linha += 1

    for extra in range(5):
        for col in range(1, 5):
            c = ws.cell(row=linha, column=col)
            c.fill = PatternFill("solid", fgColor=AMARELO)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[linha].height = 40
        linha += 1

    ws.cell(row=linha + 1, column=1,
            value="Precisamos de pelo menos TRÊS apólices de seguradoras DIFERENTES. "
                  "Comparar duas versões do mesmo modelo não demonstra nada. "
                  "Podem ser condições gerais públicas — não precisa ser apólice "
                  "de cliente, e não deve conter dado de ninguém.").font = Font(
        italic=True, color="555555", size=10)


def aba_instrucoes(wb: Workbook) -> None:
    ws = wb.create_sheet("Leia primeiro", 0)
    ws.column_dimensions["A"].width = 108

    blocos = [
        ("Projeto Final — o que preciso de você", True, 14),
        ("", False, 11),
        ("Paulo, a plataforma vai ler apólices D&O em PDF e apontar as diferenças "
         "entre elas automaticamente. Para isso funcionar, alguém precisa dizer "
         "QUAIS diferenças importam. Esse alguém é você.", False, 11),
        ("", False, 11),
        ("No Desafio 5 foram os seus limiares de chuva e vento que fizeram o sistema "
         "avisar as pessoas certas. Aqui é a mesma coisa: sem a sua lista, o programa "
         "compara tudo e não destaca nada.", False, 11),
        ("", False, 11),
        ("São duas abas para preencher:", True, 12),
        ("", False, 11),
        ("ABA 1 — Campos a comparar", True, 11),
        ("Listei 12 candidatos com o que entendi que cada um significa. Para cada linha, "
         "diga na coluna amarela se vale comparar (SIM / NAO / TALVEZ) e escreva por quê "
         "em uma frase. Se eu escrevi alguma definição errada, corrija sem dó.", False, 11),
        ("Se faltou campo que você olha na prática, use as linhas vazias do fim.", False, 11),
        ("", False, 11),
        ("ABA 2 — Onde achar apólices", True, 11),
        ("Precisamos de pelo menos três apólices D&O de seguradoras diferentes, "
         "documentos públicos. Se souber onde baixar, coloque o link. Se tiver o "
         "arquivo, me mande direto.", False, 11),
        ("", False, 11),
        ("Quanto preencher: se der, marque todos os 12. Se o tempo for curto, "
         "priorize marcar SIM nos 8 mais importantes — é o suficiente para começarmos.", False, 11),
        ("", False, 11),
        ("Prazo: até 17/09. É a primeira coisa do projeto e trava o trabalho de "
         "todo mundo, então quanto antes melhor.", True, 11),
        ("", False, 11),
        ("Não precisa mexer em nada de programação. Preencha, salve e me devolva "
         "por WhatsApp.", False, 11),
    ]

    linha = 1
    for texto, negrito, tamanho in blocos:
        c = ws.cell(row=linha, column=1, value=texto)
        c.font = Font(bold=negrito, size=tamanho, color=AZUL if negrito and tamanho >= 12 else "000000")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[linha].height = 34 if texto else 8
        linha += 1


def main() -> None:
    wb = Workbook()
    aba_campos(wb)
    aba_fontes(wb)
    aba_instrucoes(wb)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(DESTINO)
    print(f"planilha gerada: {DESTINO.relative_to(RAIZ)}")
    print(f"  {len(CANDIDATOS)} campos candidatos + 6 linhas livres")


if __name__ == "__main__":
    main()
