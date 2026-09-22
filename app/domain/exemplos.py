"""Extrações de exemplo, para demonstrar a plataforma sem gastar cota de LLM.

Servem a três situações, todas reais neste projeto:

* **A interface é construída antes da extração ficar pronta.** Quem trabalha na
  frente D precisa de dados no formato final hoje, não quando a frente B entregar.
* **A demonstração não pode depender de rede.** No Desafio 5 foram os cenários
  climáticos forçados que salvaram a apresentação; aqui é este módulo.
* **Os testes não devem consumir cota.** Extrair uma apólice custa ~37 mil tokens.

Os valores imitam o que as condições gerais da Chubb e da AIG realmente trazem, mas
**foram escritos à mão** — não saíram de nenhuma extração. Nada aqui deve aparecer
no relatório como resultado do sistema.

Cada caso foi escolhido para exercitar um veredito diferente do motor de comparação:
mesmo valor em formatos distintos, valores realmente diferentes, campo ausente numa
das apólices, e redações que só um leitor distingue.
"""

from __future__ import annotations

from ..schemas import ApoliceExtraida, CampoExtraido

#: Marca que estes dados não vieram de um modelo, e o relatório precisa dizer isso.
FONTE_EXEMPLO = "exemplo fabricado (sem LLM)"


def _campo(campo_id: str, valor: str | None, trecho: str | None = None,
           pagina: int | None = None) -> CampoExtraido:
    return CampoExtraido(
        campo_id=campo_id,
        valor=valor,
        trecho_origem=trecho,
        pagina=pagina,
        paginas_possiveis=[pagina] if pagina else [],
    )


CHUBB = ApoliceExtraida(
    documento="chubb_do_capital_fechado.pdf",
    seguradora="Chubb",
    modelo_usado=FONTE_EXEMPLO,
    campos=[
        _campo("limite_maximo_indenizacao", "R$ 10.000.000,00",
               "Limite Maximo de Indenizacao de R$ 10.000.000,00 por reclamacao e no agregado", 4),
        _campo("franquia", "R$ 50.000,00",
               "franquia de R$ 50.000,00 por reclamacao", 12),
        _campo("vigencia", "12 meses a partir de 01/01/2026",
               "vigencia de 12 meses contados de 01/01/2026", 3),
        _campo("retroatividade", "01/01/2020",
               "data retroativa de 01/01/2020", 5),
        _campo("prazo_complementar", "90 dias",
               "prazo complementar de 90 dias apos o termino", 18),
        _campo("ambito_geografico", "Territorio nacional",
               "cobertura limitada ao territorio nacional", 6),
        _campo("definicao_segurado",
               "Diretores, conselheiros e administradores, incluindo conjuge e espolio",
               "entende-se por Segurado os diretores, conselheiros e administradores", 8),
        _campo("custos_defesa", "Cobertos, consomem o limite",
               "os custos de defesa integram o Limite Maximo de Indenizacao", 14),
        _campo("multas_administrativas", "Cobertas quando seguráveis em lei",
               "multas e penalidades civis, quando seguraveis", 16),
        _campo("exclusao_atos_dolosos", "Excluidos apos decisao judicial transitada em julgado",
               "atos dolosos comprovados por decisao judicial transitada em julgado", 24),
        _campo("exclusao_ambiental", "Estao excluidos danos decorrentes de poluicao",
               "excluidos os danos decorrentes de poluicao ou contaminacao", 31),
        _campo("clausula_rescisao", "Rescisao mediante aviso previo de 30 dias",
               "a apolice podera ser rescindida mediante aviso previo de 30 dias", 40),
        _campo("definicao_reclamacao", "Notificacao escrita de ato danoso",
               "considera-se Reclamacao a notificacao escrita", 7),
        _campo("sublimites", "R$ 1.000.000,00 para custos de defesa",
               "sublimite de R$ 1.000.000,00 para custos de defesa", 9),
        _campo("cobertura_investigacoes", "Cobre custos de investigacao antes da acao judicial",
               "custos de investigacao, inqueritos e procedimentos administrativos", 22),
    ],
)

AIG = ApoliceExtraida(
    documento="aig_do.pdf",
    seguradora="AIG",
    modelo_usado=FONTE_EXEMPLO,
    campos=[
        # mesmo limite da Chubb, escrito por extenso — não pode virar "diferente"
        _campo("limite_maximo_indenizacao", "R$ 10 milhões",
               "Limite de Garantia de R$ 10 milhoes", 6),
        _campo("franquia", "R$ 80.000,00",
               "retencao de R$ 80.000,00 por reclamacao", 7),
        _campo("vigencia", "12 meses a partir de 01/01/2026",
               "prazo de seguro de 12 meses a contar de 01/01/2026", 4),
        _campo("retroatividade", "01/01/2018",
               "cobertura retroativa a 01/01/2018", 8),
        # mesmo prazo da Chubb, em outra unidade
        _campo("prazo_complementar", "3 meses",
               "prazo adicional de notificacao de 3 meses", 15),
        _campo("ambito_geografico", "Mundial, exceto Estados Unidos e Canada",
               "abrangencia mundial, excluidos Estados Unidos e Canada", 9),
        _campo("definicao_segurado", "Diretores e conselheiros eleitos ou nomeados",
               "Pessoa Segurada: diretores e conselheiros eleitos ou nomeados", 11),
        _campo("custos_defesa", "Cobertos em acrescimo ao limite",
               "as despesas de defesa serao pagas em acrescimo ao Limite de Garantia", 13),
        _campo("multas_administrativas", None),
        _campo("exclusao_atos_dolosos", "Excluidos atos desonestos ou fraudulentos",
               "excluidos os atos desonestos, fraudulentos ou criminosos", 26),
        _campo("exclusao_ambiental", "Sem cobertura para contaminacao do meio ambiente",
               "nao havera cobertura para contaminacao do meio ambiente", 28),
        _campo("clausula_rescisao", "Rescisao mediante aviso previo de 30 dias",
               "rescisao com aviso previo de 30 dias", 38),
        _campo("definicao_reclamacao", "Qualquer procedimento judicial ou administrativo",
               "Reclamacao: qualquer procedimento judicial ou administrativo", 10),
        # sublimites e cobertura de investigações: ausentes de propósito
        _campo("sublimites", None),
        _campo("cobertura_investigacoes", None),
    ],
)

#: As duas apólices de exemplo, prontas para comparar.
APOLICES = [CHUBB, AIG]


def carregar_exemplos() -> list[ApoliceExtraida]:
    """Cópias das apólices de exemplo, para quem quiser alterá-las sem efeito colateral."""
    return [a.model_copy(deep=True) for a in APOLICES]
