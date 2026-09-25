"""Agente extrator — tarefa B.2.

Recebe o texto de uma apólice e devolve os campos de `data/campos_do.yaml`
estruturados, cada um com a citação de onde saiu.

Três decisões de desenho:

* **o documento vai inteiro, numa chamada só.** Uma apólice tem ~37 mil tokens e
  cabe folgado no contexto; fragmentar arriscaria cortar uma cláusula ao meio e
  obrigaria a juntar respostas contraditórias de pedaços diferentes;
* **o prompt é gerado do dicionário.** Rótulo, significado e sinônimos vêm do YAML
  do especialista — "Âmbito Geográfico" não aparece com esse nome numa das
  apólices, e é o sinônimo que leva o modelo à cláusula certa. Acrescentar um
  campo ao YAML acrescenta ao prompt sem tocar em código;
* **o modelo não tem a palavra final.** Tudo o que ele devolve passa por
  `validacao.py`, que confere cada citação contra o PDF (B.3 e B.4).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..domain.campos import DicionarioCampos, TipoCampo, carregar_campos
from ..domain.ingestao import receber
from ..schemas import ApoliceExtraida, DocumentoExtraido
from .llm import RespostaLLM, gerar_texto
from .validacao import Localizador, validar_campos

log = logging.getLogger(__name__)


class RespostaInvalida(Exception):
    """O modelo respondeu, mas não no formato pedido."""


#: Como pedir o valor de cada tipo. O formato importa para a frente C: é ele que
#: deixa o motor de comparação reconhecer `R$ 10.000.000,00` e `R$ 10 milhões`
#: como o mesmo número, e `90 dias` e `3 meses` como o mesmo prazo.
_FORMATO_POR_TIPO = {
    TipoCampo.VALOR_MONETARIO: 'valor em reais como no documento, ex.: "R$ 1.000.000,00"',
    TipoCampo.DATA: 'data no formato dd/mm/aaaa, ou a regra que define a data',
    TipoCampo.PERIODO: 'início e fim, ou a duração, como o documento define',
    TipoCampo.PRAZO: 'duração com número e unidade, ex.: "90 dias", "12 meses"',
    TipoCampo.TEXTO: "resumo fiel em até 30 palavras do que a cláusula estabelece",
}

_INSTRUCOES = """\
Você é um analista de seguros D&O. Acima está o texto integral de uma apólice (ou
das condições gerais de um seguro D&O). Cada página começa com um marcador
"=== PÁGINA N ===".

Procure no documento os campos listados abaixo. Para cada um, devolva:

- "valor": o que o documento estabelece sobre o campo, no formato indicado.
- "trecho": uma cópia LITERAL, contínua, de 10 a 50 palavras, do texto da
  cláusula de onde o valor saiu.
- "pagina": o número do marcador "=== PÁGINA N ===" sob o qual o trecho está.
- "observacao": ressalva curta, quando necessária; senão null.

REGRAS — seguir todas:

1. Use SOMENTE o documento acima. Nunca complete com conhecimento geral sobre
   seguros nem com o que "costuma" constar em apólices D&O.
2. O "trecho" é copiado caractere por caractere: sem reticências, sem corrigir
   ortografia, sem juntar frases de lugares diferentes. Ele será procurado no
   documento; se não for achado, o campo inteiro é descartado.
3. Cite o CORPO da cláusula. Nunca cite cabeçalho, rodapé, número de processo
   SUSEP ou título que se repete em todas as páginas — isso não prova origem.
4. Todo número que aparecer em "valor" tem de aparecer no "trecho". Não
   converta, não arredonde, não calcule.
5. Se o documento não trata do campo: "valor", "trecho" e "pagina" são null.
   Não invente. Um null honesto vale mais que um valor plausível.
6. Se a cláusula existe mas o valor concreto é deixado para a especificação,
   frontispício ou proposta (comum em condições gerais — limites, franquias e
   datas costumam ser "os indicados na apólice"): "valor" null, "trecho" com a
   cláusula que remete, e "observacao" explicando que o valor fica na
   especificação.
7. A mesma cláusula aparece com nomes diferentes em cada seguradora. Use o
   significado e os outros nomes de cada campo para achá-la.

CAMPOS:

{campos}

Responda APENAS com um objeto JSON, sem texto antes ou depois, neste formato:

{{
  "seguradora": "nome da seguradora como aparece no documento, ou null",
  "campos": {{
{exemplo}
  }}
}}
"""


def _descrever_campos(dicionario: DicionarioCampos) -> str:
    blocos = []
    for c in dicionario:
        linhas = [f'- "{c.id}" — {c.rotulo}', f"  Significado: {c.significado}"]
        if c.sinonimos:
            linhas.append(f"  Também chamado de: {', '.join(c.sinonimos)}")
        linhas.append(f"  Formato do valor: {_FORMATO_POR_TIPO[c.tipo]}")
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


def montar_prompt(documento: DocumentoExtraido, dicionario: DicionarioCampos) -> str:
    """O documento primeiro, as instruções depois.

    Com um texto de dezenas de milhares de tokens, a pergunta no fim é lida com o
    documento já "na cabeça" do modelo — e as regras ficam mais perto da resposta.
    """
    exemplo = ",\n".join(
        f'    "{cid}": {{"valor": ..., "trecho": ..., "pagina": ..., "observacao": ...}}'
        for cid in dicionario.ids
    )
    instrucoes = _INSTRUCOES.format(campos=_descrever_campos(dicionario), exemplo=exemplo)
    return (
        f"<documento arquivo=\"{documento.nome_arquivo}\">\n"
        f"{documento.texto_com_marcadores}\n"
        f"</documento>\n\n{instrucoes}"
    )


def interpretar_resposta(texto: str) -> dict:
    """O JSON dentro da resposta do modelo.

    Tolera o que os modelos fazem mesmo quando se pede "apenas JSON": cercas de
    código markdown e frase de cortesia antes ou depois do objeto.
    """
    sem_cerca = re.sub(r"```(?:json)?", "", texto)
    inicio, fim = sem_cerca.find("{"), sem_cerca.rfind("}")
    if inicio == -1 or fim <= inicio:
        raise RespostaInvalida(f"a resposta nao contem JSON: {texto[:200]!r}")
    try:
        dados = json.loads(sem_cerca[inicio:fim + 1])
    except json.JSONDecodeError as exc:
        raise RespostaInvalida(f"JSON invalido na resposta: {exc}") from exc

    campos = dados.get("campos") if isinstance(dados, dict) else None
    # alguns modelos devolvem lista de objetos em vez de dicionário por id
    if isinstance(campos, list):
        campos = {
            str(c.get("campo_id") or c.get("id")): c
            for c in campos if isinstance(c, dict) and (c.get("campo_id") or c.get("id"))
        }
    if not isinstance(campos, dict):
        raise RespostaInvalida("a resposta nao tem o objeto 'campos'")

    return {"seguradora": dados.get("seguradora"), "campos": campos}


@dataclass(frozen=True)
class Extracao:
    """A apólice estruturada e o que custou obtê-la."""

    apolice: ApoliceExtraida
    resposta: RespostaLLM

    @property
    def tokens_entrada(self) -> int | None:
        return self.resposta.tokens_entrada

    @property
    def tokens_saida(self) -> int | None:
        return self.resposta.tokens_saida


def _seguradora(nome, localizador: Localizador) -> str | None:
    """O nome só é aceito se estiver escrito no documento."""
    if not isinstance(nome, str) or not nome.strip():
        return None
    nome = nome.strip()
    return nome if localizador.contem(nome) else None


def extrair(
    documento: DocumentoExtraido,
    dicionario: DicionarioCampos | None = None,
    gerar: Callable[..., RespostaLLM] = gerar_texto,
) -> Extracao:
    """Lê a apólice com o LLM e devolve os campos já conferidos contra o documento.

    `gerar` existe para os testes trocarem o modelo por uma resposta pronta, sem
    rede e sem cota.
    """
    dicionario = dicionario or carregar_campos()
    prompt = montar_prompt(documento, dicionario)

    log.info("%s: enviando ~%d mil caracteres ao modelo",
             documento.nome_arquivo, len(prompt) // 1000)
    resposta = gerar(prompt, json=True)
    log.info("%s: resposta de %s (%s tokens de entrada, %s de saida)",
             documento.nome_arquivo, resposta.identificacao,
             resposta.tokens_entrada, resposta.tokens_saida)

    dados = interpretar_resposta(resposta.texto)
    campos = validar_campos(dados["campos"], dicionario, documento)

    apolice = ApoliceExtraida(
        documento=documento.nome_arquivo,
        seguradora=_seguradora(dados["seguradora"], Localizador(documento)),
        campos=campos,
        modelo_usado=resposta.identificacao,
    )
    return Extracao(apolice=apolice, resposta=resposta)


def extrair_arquivo(caminho: Path | str, **kwargs) -> Extracao:
    """Atalho: lê o arquivo (frente A) e extrai os campos (frente B)."""
    return extrair(receber(caminho), **kwargs)
