"""Demonstração da frente D por linha de comando — tarefa D.4.

O vídeo não pode depender da interface. Se o Streamlit não subir na máquina de
quem grava, tem de existir um caminho que mostre o sistema funcionando sem
navegador — este é esse caminho.

Duas coisas que este script não faz, de propósito:

* **não reimplementa nada.** Usa a ingestão da frente A, o banco e o motor da
  frente C, e as *mesmas* regras de apresentação da tela
  (`app/interface/apresentacao.py`). Se um rótulo de veredito mudar, muda aqui
  e na interface na mesma hora — era o risco de ter duas telas contando a mesma
  história com palavras diferentes;
* **não gasta cota.** Trabalha sobre as extrações de exemplo, e diz isso em voz
  alta no começo e no fim.

    python -m scripts.demo_frente_d              # ingestão real dos PDFs + comparação
    python -m scripts.demo_frente_d --rapido     # pula a ingestão
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RAIZ = Path(__file__).resolve().parent.parent

#: Onde a demonstração deixa o CSV. `data/saida/` está no `.gitignore`, então
#: rodar a demonstração não suja o repositório com arquivo gerado.
SAIDA_DIR = RAIZ / "data" / "saida"

from app.clients.extracao import ocr_disponivel  # noqa: E402
from app.config import APOLICES_DIR  # noqa: E402
from app.domain.armazenamento import Banco  # noqa: E402
from app.domain.campos import carregar_campos  # noqa: E402
from app.domain.comparacao import comparar  # noqa: E402
from app.domain.exemplos import FONTE_EXEMPLO, carregar_exemplos  # noqa: E402
from app.domain.ingestao import receber_varios  # noqa: E402
from app.interface.apresentacao import (  # noqa: E402
    estilo,
    exportar_csv,
    formatar_pagina,
    linhas_rastreabilidade,
    montar_cartoes,
    montar_kpis,
    nome_arquivo_csv,
)

LARGURA = 78


def titulo(texto: str) -> None:
    print(f"\n{'=' * LARGURA}\n{texto.upper()}\n{'=' * LARGURA}")


def passo(numero: int, texto: str) -> None:
    print(f"\n{'-' * LARGURA}\n{numero}. {texto}\n{'-' * LARGURA}")


def frente_a() -> None:
    """A ingestão, sobre os PDFs reais — a única etapa que não é demonstração."""
    passo(1, "FRENTE A — leitura dos PDFs reais (pypdf, OCR só quando falta texto)")
    alvos = sorted(APOLICES_DIR.glob("*.pdf"))
    if not alvos:
        print(f"  nenhuma apolice em {APOLICES_DIR}")
        return

    print(f"  OCR disponivel nesta maquina: {'sim' if ocr_disponivel() else 'nao'}")
    inicio = time.time()
    documentos, falhas = receber_varios(alvos)
    duracao = time.time() - inicio

    for documento in documentos:
        tokens = int(len(documento.texto_com_marcadores.split()) / 0.75)
        print(f"\n  {documento.nome_arquivo}")
        print(f"    {documento.total_paginas} paginas | {len(documento.texto_completo):,} "
              f"caracteres | ~{tokens:,} tokens".replace(",", "."))
        print(f"    por OCR: {documento.paginas_por_ocr} | vazias: {documento.paginas_vazias}")

        # a rastreabilidade da frente B depende disto: cada trecho sabe sua página
        meio = documento.paginas[documento.total_paginas // 2]
        palavras = meio.texto.split()
        if len(palavras) > 40:
            trecho = " ".join(palavras[len(palavras) // 2:][:8])
            print(f"    trecho da pagina {meio.numero} localizado em "
                  f"{documento.paginas_de(trecho)}")

    for nome, motivo in falhas:
        print(f"\n  fora do lote: {nome} — {motivo}")

    print(f"\n  {len(documentos)} documento(s) em {duracao:.1f}s, sem gastar um token")


def extracao_e_banco() -> Banco:
    """As extrações de exemplo no banco — o que a frente B vai substituir."""
    passo(2, "FRENTE B — campos estruturados (hoje: extrações de exemplo)")
    print(f"  fonte dos campos: {FONTE_EXEMPLO}")
    print("  a extração real com LLM ainda está sendo escrita; estes valores foram")
    print("  escritos à mão para a interface e a demonstração não ficarem paradas.")

    banco = Banco(":memory:")
    for apolice in carregar_exemplos():
        banco.salvar(apolice)

    passo(3, "FRENTE C — armazenamento e comparação (determinístico, sem LLM)")
    print("  guardadas e recuperadas do SQLite em memória:")
    for linha in banco.listar():
        print(f"    {linha['seguradora']:8} {linha['encontrados']}/{linha['total_campos']} campos")
    return banco


def comparacao(banco: Banco) -> None:
    """Os números e os cartões, com o mesmo vocabulário da tela."""
    dicionario = carregar_campos()
    apolices = banco.carregar_varias([linha["documento"] for linha in banco.listar()])
    resultado = comparar(apolices, dicionario)

    print(f"\n  dicionario: {len(dicionario)} campos, definidos por {dicionario.definido_por}")
    print(f"  comparacao: {' x '.join(resultado.apolices)}")

    print("\n  os numeros que a interface mostra no topo:")
    for kpi in montar_kpis(resultado):
        print(f"    {kpi.icone} {kpi.rotulo:24} {kpi.valor}")

    passo(4, "D.2 — as diferencas lado a lado, na ordem do motor")
    cartoes = montar_cartoes(resultado, apolices)
    for cartao in cartoes:
        est = estilo(cartao.veredito)
        print(f"\n  {est.simbolo} {cartao.rotulo}  [{est.rotulo}]")
        for valor in cartao.valores:
            onde = f"  ({valor.ancoragem})" if not valor.ausente else ""
            print(f"      {valor.apolice:8}: {valor.texto}{onde}")
        print(f"      por que importa: {cartao.porque_importa[:150]}")
        if cartao.ausentes:
            print(f"      nao trata do assunto: {', '.join(cartao.ausentes)}")

    passo(5, "D.3 — de onde veio cada valor (pagina, trecho e conferencia)")
    linhas = linhas_rastreabilidade(resultado, apolices)
    for linha in linhas:
        print(f"\n  {linha['Campo']} — {linha['Apólice']}")
        print(f"    {formatar_pagina(linha['Página'], [])} | confere: {linha['Confere']}")
        print(f"    \"{linha['Trecho de origem'][:120]}\"")

    print(f"\n  {len(linhas)} valores encontrados, "
          f"{sum(1 for l in linhas if l['Confere'] == 'sim')} com origem registrada")

    destino = Path(SAIDA_DIR) / nome_arquivo_csv(resultado)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(exportar_csv(resultado), encoding="utf-8")
    print(f"\n  CSV da comparacao gravado em {destino.relative_to(RAIZ)} "
          f"({len(destino.read_text(encoding='utf-8').splitlines())} linhas)")


def main() -> int:
    print(f"{'=' * LARGURA}")
    print("FRENTE D — INTERFACE, DEMONSTRACAO E APRESENTACAO")
    print("Plataforma de analise e comparacao de apolices D&O · grupo Insurminds / I2A2")
    print("=" * LARGURA)
    print("\nEste caminho existe para o video nao depender do navegador (tarefa D.4).")
    print("A interface mostra o mesmo, com selos, cartoes e a pagina do PDF renderizada:")
    print("    streamlit run app/interface/app.py")

    if "--rapido" not in sys.argv:
        frente_a()
    else:
        print("\n  (ingestao pulada por --rapido)")

    banco = extracao_e_banco()
    try:
        comparacao(banco)
    finally:
        banco.fechar()

    titulo("o que acabou de rodar")
    print("  real .....: ingestao dos PDFs, banco SQLite, motor de comparacao,")
    print("             rastreabilidade (pagina e trecho de cada valor)")
    print("  exemplo ..: os campos extraidos, à espera da frente B (LLM)")
    print("  nenhuma chamada de modelo de linguagem foi feita nesta demonstracao.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
