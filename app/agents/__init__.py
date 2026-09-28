"""Frente B — extração das cláusulas com IA generativa.

Este módulo é a **ponte pública** da extração. A frente D combinou um contrato
para não precisar mudar a interface quando a extração entrasse: procurar aqui, em
`app.agents`, uma função que receba um `DocumentoExtraido` e devolva uma
`ApoliceExtraida` (ver `apresentacao.encontrar_extrator`).

O porquê deste arquivo existir: `extrator.extrair` devolve um `Extracao`, que
carrega a apólice **e** o consumo de tokens da chamada. Esse detalhe é
interessante para o relatório de cota, mas é ruído para quem só quer a apólice.
Reexportar `extrair` direto faria a tela usar `Extracao.documento`, que não
existe, e a extração falharia com um `AttributeError` difícil de diagnosticar.

Por isso a função pública deste módulo é `extrair_apolice`, que cumpre o
contrato ao pé da letra. `extrair` continua disponível para quem precisa da
medição de tokens (o console e os testes usam).
"""

from __future__ import annotations

from .extrator import (
    Extracao,
    RespostaInvalida,
    extrair,
    extrair_arquivo,
    interpretar_resposta,
    montar_prompt,
)
from .llm import LLMIndisponivel, RespostaLLM, TimeoutLLM, gerar_texto
from .validacao import Localizador, numeros_sem_apoio, validar_campos

__all__ = [
    "Extracao",
    "LLMIndisponivel",
    "Localizador",
    "RespostaInvalida",
    "RespostaLLM",
    "TimeoutLLM",
    "extrair",
    "extrair_apolice",
    "extrair_arquivo",
    "gerar_texto",
    "interpretar_resposta",
    "montar_prompt",
    "numeros_sem_apoio",
    "validar_campos",
]


def extrair_apolice(documento, dicionario=None, **kwargs):
    """A apólice estruturada a partir de um documento já lido.

    É a assinatura que a interface consome: recebe um `DocumentoExtraido` e
    devolve uma `ApoliceExtraida`, com a rastreabilidade já conferida contra o
    documento (B.3 e B.4).

    `dicionario` é opcional porque a interface não tem por que saber qual é o
    dicionário: quando vem `None`, `extrair` carrega o de `data/campos_do.yaml`,
    que é o do especialista. O resto vai direto para `extrair` — é o que
    permite a um teste trocar o modelo por uma resposta pronta e exercitar o
    contrato sem rede e sem cota.
    """
    return extrair(documento, dicionario, **kwargs).apolice

