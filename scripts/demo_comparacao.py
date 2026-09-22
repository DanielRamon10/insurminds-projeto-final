"""Demonstração das frentes C.1 a C.3: armazenamento e comparação.

Roda com extrações fabricadas à mão, porque a frente B ainda está sendo escrita.
Serve a dois propósitos: mostrar o motor de comparação funcionando e deixar
visível o contrato que a extração precisa produzir.

    python -m scripts.demo_comparacao
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.armazenamento import Banco  # noqa: E402
from app.domain.campos import carregar_campos  # noqa: E402
from app.domain.comparacao import Veredito, comparar  # noqa: E402
from app.schemas import ApoliceExtraida, CampoExtraido  # noqa: E402

SIMBOLO = {
    Veredito.AUSENTE_EM_ALGUMA: "[!]",
    Veredito.DIFERENTE: "[x]",
    Veredito.REDACAO_DIVERGENTE: "[~]",
    Veredito.IGUAL: "[=]",
    Veredito.AUSENTE_EM_TODAS: "[ ]",
}

# Extrações fabricadas — é o formato que a frente B vai devolver.
CHUBB = ApoliceExtraida(
    documento="chubb_do_capital_fechado.pdf",
    seguradora="Chubb",
    modelo_usado="(exemplo, sem LLM)",
    campos=[
        CampoExtraido(campo_id="limite_maximo_indenizacao", valor="R$ 10.000.000,00",
                      trecho_origem="Limite Maximo de Indenizacao de R$ 10.000.000,00",
                      pagina=4, paginas_possiveis=[4]),
        CampoExtraido(campo_id="franquia", valor="R$ 50.000,00",
                      trecho_origem="franquia de R$ 50.000,00 por reclamacao",
                      pagina=12, paginas_possiveis=[12]),
        CampoExtraido(campo_id="prazo_complementar", valor="90 dias",
                      trecho_origem="prazo complementar de 90 dias", pagina=18),
        CampoExtraido(campo_id="sublimites", valor="R$ 1.000.000,00 para custos de defesa",
                      trecho_origem="sublimite de R$ 1.000.000,00", pagina=9),
        CampoExtraido(campo_id="exclusao_ambiental",
                      valor="Estao excluidos danos decorrentes de poluicao",
                      trecho_origem="excluidos os danos decorrentes de poluicao", pagina=31),
        CampoExtraido(campo_id="cobertura_investigacoes",
                      valor="Cobre custos de investigacao antes da acao judicial",
                      trecho_origem="custos de investigacao", pagina=22),
    ],
)

AIG = ApoliceExtraida(
    documento="aig_do.pdf",
    seguradora="AIG",
    modelo_usado="(exemplo, sem LLM)",
    campos=[
        # mesmo valor do LMI, escrito de outro jeito — não pode virar "diferente"
        CampoExtraido(campo_id="limite_maximo_indenizacao", valor="R$ 10 milhões",
                      trecho_origem="Limite de Garantia de R$ 10 milhoes",
                      pagina=6, paginas_possiveis=[6]),
        CampoExtraido(campo_id="franquia", valor="R$ 80.000,00",
                      trecho_origem="retencao de R$ 80.000,00", pagina=7),
        # mesmo prazo em outra unidade
        CampoExtraido(campo_id="prazo_complementar", valor="3 meses",
                      trecho_origem="prazo adicional de 3 meses", pagina=15),
        CampoExtraido(campo_id="exclusao_ambiental",
                      valor="Sem cobertura para contaminacao do meio ambiente",
                      trecho_origem="contaminacao do meio ambiente", pagina=28),
        # sublimites e cobertura de investigações: ausentes de propósito
    ],
)


def main() -> int:
    dicionario = carregar_campos()
    print(f"dicionario: {len(dicionario)} campos, definidos por {dicionario.definido_por}\n")

    # C.1 — guarda e recupera
    banco = Banco(":memory:")
    for a in (CHUBB, AIG):
        banco.salvar(a)
    apolices = banco.carregar_varias([CHUBB.documento, AIG.documento])
    print("guardadas e recuperadas do banco:")
    for linha in banco.listar():
        print(f"  {linha['seguradora']:8} {linha['encontrados']}/{linha['total_campos']} campos")

    # C.2 e C.3 — compara
    resultado = comparar(apolices, dicionario)

    print(f"\n{'=' * 74}")
    print(f"COMPARACAO: {' x '.join(resultado.apolices)}")
    print("=" * 74)

    resumo = resultado.resumo
    print(f"  diferentes: {resumo['diferente']} | "
          f"ausentes em alguma: {resumo['ausente_em_alguma']} | "
          f"redacao divergente: {resumo['redacao_divergente']} | "
          f"iguais: {resumo['igual']} | "
          f"fora das duas: {resumo['ausente_em_todas']}")

    print(f"\n{'-' * 74}")
    print("O QUE DISTINGUE AS DUAS (em ordem de leitura)")
    print("-" * 74)
    for d in resultado.relevantes:
        print(f"\n{SIMBOLO[d.veredito]} {d.campo.rotulo}  ({d.veredito.value})")
        for nome, valor in d.valores.items():
            pagina = d.paginas.get(nome)
            onde = f"  (p. {pagina})" if pagina else ""
            print(f"      {nome:8}: {valor or '— nao trata do assunto —'}{onde}")
        print(f"      por que importa: {d.campo.porque_importa[:96]}...")

    iguais = resultado.por_veredito(Veredito.IGUAL)
    if iguais:
        print(f"\n{'-' * 74}")
        print("IGUAIS NAS DUAS")
        print("-" * 74)
        for d in iguais:
            valor = next(v for v in d.valores.values() if v)
            print(f"  [=] {d.campo.rotulo}: {valor}")

    print(f"\n{'=' * 74}")
    print("Nota: o motor nao usa LLM. Ele diz O QUE difere; explicar POR QUE a")
    print("diferenca pesa para o cliente e a tarefa C.4, com o redator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
