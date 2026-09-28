"""Carrega no banco as extrações reais produzidas pelo LLM (frente B).

Por que este script existe, e por que não é luxo:

* `python -m scripts.demo_extracao` grava o resultado da leitura em
  `data/extracoes/<arquivo>.json`, mas **ninguém o levava para o banco** — o
  passo entre "extraí" e "a tela mostra" estava faltando;
* o `.db` **não entra na entrega** (`gerar_entrega.py` exclui `*.db`), então quem
  abre o projeto entregue recebe um banco vazio. Sem este script, a única forma
  de a tela ter apólice é a demonstração semear as extrações de exemplo — e a
  entrega passaria a mostrar **dado fabricado**, justamente o que a frente D
  passou a avisar na tela em três lugares;
* os JSON da extração **entram** na entrega, por ficarem em `data/`. Portanto o
  caminho para dado real na máquina de quem avalia existe, e não custa cota
  nenhuma: é este comando.

    python -m scripts.carregar_extracoes              # todas em data/extracoes/
    python -m scripts.carregar_extracoes --simular    # mostra o que faria

O script é idempotente e não faz rede. Ele **não** chama o LLM: lê o que a
frente B já extraiu e grava no SQLite, que é a etapa C.1 da arquitetura.
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR  # noqa: E402
from app.domain.armazenamento import Banco  # noqa: E402
from app.domain.exemplos import FONTE_EXEMPLO  # noqa: E402
from app.schemas import ApoliceExtraida  # noqa: E402

EXTRACOES_DIR = DATA_DIR / "extracoes"

#: A resposta crua do modelo mora ao lado, com este sufixo. Não é apólice
#: extraída: é o JSON do provedor, e passá-lo a `ApoliceExtraida` seria falso.
SUFFIXO_RESPOSTA = ".resposta_llm.json"


def arquivos_extraidos(diretorio: Path = EXTRACOES_DIR) -> list[Path]:
    """Os JSON de apólice extraída, em ordem de nome."""
    if not diretorio.is_dir():
        return []
    return sorted(
        p for p in diretorio.glob("*.json")
        if not p.name.endswith(SUFFIXO_RESPOSTA)
    )


def carregar(caminhos: list[Path], banco: Banco, simular: bool = False) -> list[str]:
    """Grava cada extração no banco e devolve o que aconteceu, por documento.

    A ordem de resolução é a que evita o pior acidente: se o banco já tem
    extração **real** daquele documento, ela é preservada, a menos que o script
    esteja justamente substituindo por outra real. Extração de exemplo é sempre
    substituível — é o contrário que machuca: um `null` honesto perdido para um
    valor fabricado.
    """
    relatorio: list[str] = []

    for caminho in caminhos:
        try:
            apolice = ApoliceExtraida.model_validate_json(
                caminho.read_text(encoding="utf-8")
            )
        except Exception as exc:  # noqa: BLE001 — um arquivo ruim não derruba o lote
            relatorio.append(f"{caminho.name}: ignorado, não é uma apólice extraída ({exc})")
            continue

        existente = banco.carregar(apolice.documento)
        if (
            existente is not None
            and (existente.modelo_usado or "") != FONTE_EXEMPLO
            and not simular
        ):
            relatorio.append(
                f"{apolice.documento}: preservada, o banco já tem extração real "
                f"({existente.modelo_usado})"
            )
            continue

        if not simular:
            banco.salvar(apolice)

        if existente is None:
            situacao = "gravada"
        elif (existente.modelo_usado or "") == FONTE_EXEMPLO:
            situacao = "gravada, substituiu a extração de exemplo"
        else:
            situacao = "gravada, substituiu a extração real anterior"
        relatorio.append(f"{apolice.documento}: {situacao}")

    return relatorio


def main() -> int:
    simular = "--simular" in sys.argv[1:]
    caminhos = arquivos_extraidos()

    print(f"{'Simulando' if simular else 'Carregando'} as extrações de "
          f"{EXTRACOES_DIR.relative_to(DATA_DIR.parent)}\n")

    if not caminhos:
        print("  nenhuma extração encontrada. Rode antes:\n"
              "    python -m scripts.demo_extracao")
        return 1

    banco = Banco()
    relatorio = carregar(caminhos, banco, simular=simular)
    for linha in relatorio:
        print(f"  {linha}")

    print("\n  Estado do banco:")
    for registro in banco.listar():
        print(
            f"    {registro['documento']}: {registro['encontrados']}/"
            f"{registro['total_campos']} campos · modelo: {registro['modelo_usado']}"
        )

    if simular:
        print("\n  Simulação: nada foi gravado. Rode sem --simular para aplicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
