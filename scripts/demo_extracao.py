"""Demonstração da frente B: extração das cláusulas com LLM, com rastreabilidade.

Lê cada apólice, pede os campos de `data/campos_do.yaml` ao modelo e mostra, para
cada campo, o valor, a página de origem e o que a validação descartou. Imprime
também o consumo de tokens — a cota é o risco nº 3 do roteiro.

O resultado fica em `data/extracoes/<arquivo>.json`, no formato `ApoliceExtraida`
que a frente C consome, e a resposta crua do modelo ao lado, em
`<arquivo>.resposta_llm.json`.

    python -m scripts.demo_extracao                       # todas de data/apolices/
    python -m scripts.demo_extracao data/apolices/aig_do.pdf
    python -m scripts.demo_extracao --revalidar           # sem LLM, sem cota

`--revalidar` reaplica a validação (B.3/B.4) sobre a resposta já salva. Serve
para ajustar as regras do validador sem gastar os ~60 mil tokens de cada leitura.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.extrator import RespostaInvalida, extrair_arquivo  # noqa: E402
from app.agents.llm import LLMIndisponivel, RespostaLLM  # noqa: E402
from app.config import APOLICES_DIR, DATA_DIR  # noqa: E402
from app.domain.ingestao import ArquivoRecusado  # noqa: E402

SAIDA_DIR = DATA_DIR / "extracoes"


def _mil(n: int | None) -> str:
    return "?" if n is None else f"{n:,}".replace(",", ".")


def _arquivo_resposta(caminho: Path) -> Path:
    return SAIDA_DIR / f"{caminho.stem}.resposta_llm.json"


def _resposta_salva(caminho: Path):
    """Um `gerar` que devolve a resposta gravada na última leitura real."""
    arquivo = _arquivo_resposta(caminho)
    if not arquivo.is_file():
        raise LLMIndisponivel(f"sem resposta salva em {arquivo.name}: rode sem --revalidar antes")
    salvo = json.loads(arquivo.read_text(encoding="utf-8"))

    def gerar(prompt: str, json: bool = False) -> RespostaLLM:
        return RespostaLLM(**salvo)

    return gerar


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="  [%(levelname)s] %(message)s")

    args = sys.argv[1:]
    revalidar = "--revalidar" in args
    alvos = [Path(a) for a in args if a != "--revalidar"] or sorted(APOLICES_DIR.glob("*.pdf"))
    if not alvos:
        print(f"nenhuma apolice em {APOLICES_DIR}")
        return 1

    SAIDA_DIR.mkdir(exist_ok=True)
    total_entrada = total_saida = 0
    ok = 0

    for caminho in alvos:
        print(f"{caminho.name}" + (" (revalidando a resposta salva, sem LLM)" if revalidar else ""))
        inicio = time.time()
        try:
            if revalidar:
                extracao = extrair_arquivo(caminho, gerar=_resposta_salva(caminho))
            else:
                extracao = extrair_arquivo(caminho)
        except (ArquivoRecusado, LLMIndisponivel, RespostaInvalida) as exc:
            print(f"  erro: {exc}\n")
            continue
        duracao = time.time() - inicio
        ok += 1

        a = extracao.apolice
        total_entrada += extracao.tokens_entrada or 0
        total_saida += extracao.tokens_saida or 0

        print(f"  seguradora: {a.seguradora or '(nao identificada)'} | modelo: {a.modelo_usado}")
        print(f"  tokens: {_mil(extracao.tokens_entrada)} entrada + "
              f"{_mil(extracao.tokens_saida)} saida | {duracao:.0f}s")
        print(f"  campos: {a.encontrados}/{len(a.campos)} encontrados, "
              f"{a.rastreaveis} rastreaveis\n")

        for c in a.campos:
            if c.rastreavel:
                marca = f"p.{c.pagina:<3}"
            elif c.encontrado:
                marca = "p.?  "
            else:
                marca = "null "
            valor = c.valor if c.encontrado else "—"
            print(f"  {marca} {c.campo_id:<27} {valor}")
            if c.observacao:
                print(f"        obs: {c.observacao}")

        destino = SAIDA_DIR / f"{caminho.stem}.json"
        destino.write_text(a.model_dump_json(indent=2), encoding="utf-8")
        # o que o modelo disse, antes da validação: é a outra metade da auditoria
        bruta = _arquivo_resposta(caminho)
        if not revalidar:
            bruta.write_text(
                json.dumps(extracao.resposta.__dict__, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(f"\n  salvo em {destino.relative_to(DATA_DIR.parent)} "
              f"(resposta crua do modelo em {bruta.name})\n")

    if ok:
        print(f"{ok} apolice(s) | tokens no total: {_mil(total_entrada)} entrada + "
              f"{_mil(total_saida)} saida")
    return 0 if ok == len(alvos) else 1


if __name__ == "__main__":
    sys.exit(main())
