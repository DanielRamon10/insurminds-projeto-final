"""Cliente de LLM da frente B — portado do Desafio 5.

O que veio de lá e continua valendo:

* **timeout por thread**: o `timeout` das bibliotecas nem sempre é respeitado
  quando a conexão trava no nível do socket, então o prazo é imposto por fora;
* **rotação de modelo por cota**: se um modelo do provedor esgota, o seguinte da
  lista assume;
* **correção do formato de resposta do Gemini**, que às vezes devolve uma lista de
  partes em vez de string.

O que mudou para ler apólice em vez de redigir SMS:

* **cascata entre provedores**: esgotado o Google, tenta Groq e OpenRouter, na
  ordem de `ORDEM_CASCATA`. Uma extração custa ~37 mil tokens de entrada, e a cota
  gratuita de um provedor só não aguenta um dia de testes;
* **temperatura 0**: extração não é redação, e a mesma apólice tem de render os
  mesmos campos nas duas vezes em que for lida;
* **timeout longo**: o modelo lê 70 páginas antes de responder;
* **consumo de tokens devolvido junto com o texto**, porque cota estourada já
  derrubou o grupo duas vezes e medir cedo é a única defesa.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import socket
import time
from dataclasses import dataclass

from ..config import ORDEM_CASCATA, PROVEDORES, ConfigLLM, obter_api_key

log = logging.getLogger(__name__)

#: No Desafio 5 eram 20 s, para uma mensagem curta. Aqui o modelo lê a apólice
#: inteira antes de escrever a primeira palavra. Três minutos dão folga sem
#: deixar a demo pendurada; ajustável por LLM_TIMEOUT no .env.
TIMEOUT_SEGUNDOS = int(os.environ.get("LLM_TIMEOUT", "180"))

#: Algumas redes têm IPv6 mal configurado: a conexão abre, mas os dados nunca
#: chegam. Forçar IPv4 evita a trava silenciosa. Desative com FORCAR_IPV4=0.
if os.environ.get("FORCAR_IPV4", "1") != "0":
    _getaddrinfo_original = socket.getaddrinfo

    def _getaddrinfo_apenas_ipv4(host, port, family=0, type=0, proto=0, flags=0):
        return _getaddrinfo_original(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _getaddrinfo_apenas_ipv4


#: Sobrecarga do provedor (503 "high demand") passa em segundos, ao contrário de
#: cota estourada. Quando só sobrecarga impediu a resposta, a cascata inteira é
#: refeita depois de uma espera — aconteceu duas vezes seguidas no primeiro teste
#: com a apólice real, nos três modelos do Gemini ao mesmo tempo.
RODADAS_SOBRECARGA = int(os.environ.get("LLM_RODADAS_SOBRECARGA", "3"))
ESPERA_SOBRECARGA_SEGUNDOS = 20

_SINAIS_SOBRECARGA = ("503", "unavailable", "overloaded", "high demand")


def _sobrecarga(erro: Exception) -> bool:
    texto = str(erro).lower()
    return any(s in texto for s in _SINAIS_SOBRECARGA)


class LLMIndisponivel(Exception):
    """Nenhum provedor configurado conseguiu responder."""


class TimeoutLLM(LLMIndisponivel):
    """O modelo não respondeu no prazo."""


@dataclass(frozen=True)
class RespostaLLM:
    """O texto gerado e quem o gerou — o relatório e a medição de cota precisam dos dois."""

    texto: str
    provedor: str
    modelo: str
    tokens_entrada: int | None = None
    tokens_saida: int | None = None

    @property
    def identificacao(self) -> str:
        """Como o modelo aparece em `ApoliceExtraida.modelo_usado`."""
        return f"{self.provedor}/{self.modelo}"


def _extrair_texto(conteudo) -> str:
    """`resposta.content` costuma ser string, mas o Gemini pode devolver uma lista
    de partes (quando usa "thinking", por exemplo). Sem isto, `.strip()` numa lista
    quebra, e o erro se disfarça de falha do provedor."""
    if isinstance(conteudo, str):
        return conteudo.strip()
    if isinstance(conteudo, list):
        partes = []
        for item in conteudo:
            if isinstance(item, str):
                partes.append(item)
            elif isinstance(item, dict):
                texto = item.get("text") or item.get("content")
                if texto:
                    partes.append(str(texto))
        return "".join(partes).strip()
    return str(conteudo or "").strip()


def _montar_chat_model(provedor: str, modelo: str, api_key: str, json: bool):
    if provedor == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=modelo, google_api_key=api_key, temperature=0,
            timeout=TIMEOUT_SEGUNDOS, max_retries=1,
            response_mime_type="application/json" if json else None,
        )
    if provedor == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=modelo, api_key=api_key, temperature=0,
            timeout=TIMEOUT_SEGUNDOS, max_tokens=8192,
        )
    if provedor in {"openai", "groq", "openrouter"}:
        # Groq e OpenRouter falam a API da OpenAI: muda só o endereço.
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=modelo, api_key=api_key, temperature=0,
            timeout=TIMEOUT_SEGUNDOS, max_retries=1,
            base_url=PROVEDORES[provedor]["base_url"],
        )
    raise LLMIndisponivel(f"provedor '{provedor}' nao suportado")


def _invocar_com_timeout(chat, prompt: str, timeout_segundos: int):
    """`chat.invoke()` numa thread separada, com prazo de verdade.

    Se a conexão travar no socket, a thread fica pendurada em segundo plano, mas
    o fluxo principal segue — o que importa é nunca deixar a demo esperando.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    futuro = executor.submit(chat.invoke, prompt)
    try:
        return futuro.result(timeout=timeout_segundos)
    except concurrent.futures.TimeoutError as e:
        raise TimeoutLLM(f"sem resposta em {timeout_segundos}s") from e
    finally:
        # sem esperar: a thread travada não pode prender quem chamou
        executor.shutdown(wait=False)


def _ordem_provedores(cfg: ConfigLLM) -> list[str]:
    """O provedor do `.env` primeiro, depois o resto da cascata que tiver chave."""
    ordem = [cfg.provedor] + [p for p in ORDEM_CASCATA if p != cfg.provedor]
    return [p for p in ordem if obter_api_key(p)]


def _modelos(provedor: str, cfg: ConfigLLM) -> list[str]:
    lista = [str(m) for m in PROVEDORES[provedor]["modelos"]]
    if provedor == cfg.provedor and cfg.modelo:
        return [cfg.modelo] + [m for m in lista if m != cfg.modelo]
    return lista


def gerar_texto(prompt: str, cfg: ConfigLLM | None = None, json: bool = False) -> RespostaLLM:
    """Gera texto com o primeiro modelo que responder.

    Percorre os modelos de cada provedor e depois os provedores seguintes. Um
    timeout pula direto para o próximo provedor: os outros modelos do mesmo
    provedor passam pela mesma rota de rede e provavelmente travariam igual.

    `json=True` pede resposta em JSON a quem sabe garantir isso (o Gemini); os
    demais recebem o pedido só pelo prompt, e quem chama deve tolerar isso.
    """
    cfg = cfg or ConfigLLM()
    provedores = _ordem_provedores(cfg)
    if not provedores:
        raise LLMIndisponivel(
            "nenhuma chave de LLM configurada no .env "
            f"(procurei: {', '.join(str(PROVEDORES[p]['env_key']) for p in ORDEM_CASCATA)})"
        )

    erros: list[str] = []
    for rodada in range(1, RODADAS_SOBRECARGA + 1):
        so_sobrecarga = True
        for provedor in provedores:
            api_key = obter_api_key(provedor)
            for modelo in _modelos(provedor, cfg):
                try:
                    chat = _montar_chat_model(provedor, modelo, api_key, json)
                    resposta = _invocar_com_timeout(chat, prompt, TIMEOUT_SEGUNDOS)
                except TimeoutLLM as e:
                    so_sobrecarga = False
                    erros.append(f"{provedor}/{modelo}: {e}")
                    log.warning("%s/%s: %s — tentando o proximo provedor", provedor, modelo, e)
                    break
                except ImportError:
                    so_sobrecarga = False
                    erros.append(f"{provedor}: instale {PROVEDORES[provedor]['pacote']}")
                    break
                except Exception as e:  # cota estourada, sobrecarga, erro da API
                    so_sobrecarga = so_sobrecarga and _sobrecarga(e)
                    erros.append(f"{provedor}/{modelo}: {str(e)[:200]}")
                    log.warning("%s/%s falhou: %s", provedor, modelo, str(e)[:200])
                    continue

                texto = _extrair_texto(resposta.content)
                if not texto:
                    so_sobrecarga = False
                    erros.append(f"{provedor}/{modelo}: resposta vazia")
                    continue

                uso = getattr(resposta, "usage_metadata", None) or {}
                return RespostaLLM(
                    texto=texto,
                    provedor=provedor,
                    modelo=modelo,
                    tokens_entrada=uso.get("input_tokens"),
                    tokens_saida=uso.get("output_tokens"),
                )

        if not so_sobrecarga or rodada == RODADAS_SOBRECARGA:
            break
        log.warning("provedores sobrecarregados — nova tentativa em %ds (rodada %d de %d)",
                    ESPERA_SOBRECARGA_SEGUNDOS, rodada + 1, RODADAS_SOBRECARGA)
        time.sleep(ESPERA_SOBRECARGA_SEGUNDOS)

    raise LLMIndisponivel("todos os provedores falharam:\n  " + "\n  ".join(erros))
