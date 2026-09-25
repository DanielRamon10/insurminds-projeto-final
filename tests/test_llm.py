"""Testes do cliente de LLM: cascata entre provedores e leitura da resposta.

Nenhum teste usa rede: o modelo de chat é trocado por um falso.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from app.agents import llm
from app.config import ConfigLLM


class ChatFalso:
    def __init__(self, resposta=None, erro=None, demora=0.0):
        self.resposta, self.erro, self.demora = resposta, erro, demora

    def invoke(self, prompt):
        if self.demora:
            time.sleep(self.demora)
        if self.erro:
            raise self.erro
        return self.resposta


def _resposta(texto, entrada=10, saida=2):
    return SimpleNamespace(
        content=texto, usage_metadata={"input_tokens": entrada, "output_tokens": saida}
    )


@pytest.fixture
def chaves(monkeypatch):
    """Google e Groq configurados, os outros não."""
    for p in llm.PROVEDORES.values():
        monkeypatch.delenv(str(p["env_key"]), raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    monkeypatch.setenv("GROQ_API_KEY", "y")


def _instalar(monkeypatch, comportamento: dict):
    """`comportamento[(provedor, modelo)]` diz o que cada modelo faz."""
    tentados = []

    def montar(provedor, modelo, api_key, json):
        tentados.append((provedor, modelo))
        return comportamento.get((provedor, modelo), ChatFalso(erro=RuntimeError("429 cota")))

    monkeypatch.setattr(llm, "_montar_chat_model", montar)
    return tentados


def test_primeiro_modelo_que_responde_e_usado(monkeypatch, chaves):
    _instalar(monkeypatch, {
        ("google", "gemini-3.6-flash"): ChatFalso(_resposta("ok", 37000, 900)),
    })
    r = llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))
    assert (r.texto, r.identificacao) == ("ok", "google/gemini-3.6-flash")
    assert (r.tokens_entrada, r.tokens_saida) == (37000, 900)


def test_cota_estourada_passa_para_o_proximo_modelo_e_depois_provedor(monkeypatch, chaves):
    tentados = _instalar(monkeypatch, {
        ("groq", "openai/gpt-oss-120b"): ChatFalso(_resposta("do groq")),
    })
    r = llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))

    assert r.provedor == "groq"
    # todos os modelos do Google foram tentados antes de trocar de provedor
    assert [t for t in tentados if t[0] == "google"] == [
        ("google", m) for m in llm.PROVEDORES["google"]["modelos"]
    ]


def test_provedor_sem_chave_nao_e_tentado(monkeypatch, chaves):
    tentados = _instalar(monkeypatch, {})
    with pytest.raises(llm.LLMIndisponivel):
        llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))
    assert {p for p, _ in tentados} == {"google", "groq"}


def test_sem_chave_nenhuma_explica_o_que_falta(monkeypatch):
    for p in llm.PROVEDORES.values():
        monkeypatch.delenv(str(p["env_key"]), raising=False)
    with pytest.raises(llm.LLMIndisponivel, match="GOOGLE_API_KEY"):
        llm.gerar_texto("p", ConfigLLM(provedor="google"))


def test_timeout_pula_para_o_proximo_provedor(monkeypatch, chaves):
    monkeypatch.setattr(llm, "TIMEOUT_SEGUNDOS", 0.2)
    tentados = _instalar(monkeypatch, {
        ("google", "gemini-3.6-flash"): ChatFalso(_resposta("tarde"), demora=2),
        ("groq", "openai/gpt-oss-120b"): ChatFalso(_resposta("a tempo")),
    })
    inicio = time.time()
    r = llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))

    assert r.texto == "a tempo"
    assert time.time() - inicio < 1.5, "quem chamou nao pode esperar a thread travada"
    # os outros modelos do Google usariam a mesma rota: não são tentados
    assert ("google", "gemini-3.5-flash-lite") not in tentados


class ChatSobrecarregado(ChatFalso):
    """Responde 503 nas primeiras chamadas e depois volta ao normal."""

    def __init__(self, falhas: int, resposta):
        super().__init__(resposta)
        self.falhas = falhas

    def invoke(self, prompt):
        if self.falhas:
            self.falhas -= 1
            raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand")
        return self.resposta


def test_sobrecarga_refaz_a_cascata_depois_de_esperar(monkeypatch, chaves):
    """O 503 do Gemini passa em segundos: esperar e refazer resolve."""
    monkeypatch.setattr(llm, "ESPERA_SOBRECARGA_SEGUNDOS", 0)
    monkeypatch.delenv("GROQ_API_KEY")
    sobrecarregado = ChatSobrecarregado(1, _resposta("voltou"))
    comportamento = {
        ("google", m): ChatSobrecarregado(1, _resposta("voltou"))
        for m in llm.PROVEDORES["google"]["modelos"]
    }
    comportamento[("google", "gemini-3.6-flash")] = sobrecarregado
    tentados = _instalar(monkeypatch, comportamento)

    r = llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))

    assert r.texto == "voltou"
    assert r.modelo == "gemini-3.6-flash", "na segunda rodada o modelo preferido volta a ser o primeiro"
    assert tentados.count(("google", "gemini-3.6-flash")) == 2


def test_cota_estourada_nao_espera_nem_repete(monkeypatch, chaves):
    """Cota não volta em 20 segundos: repetir só atrasaria a mensagem de erro."""
    monkeypatch.setattr(llm, "ESPERA_SOBRECARGA_SEGUNDOS", 60)
    tentados = _instalar(monkeypatch, {})  # tudo responde "429 cota"

    inicio = time.time()
    with pytest.raises(llm.LLMIndisponivel):
        llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))

    assert time.time() - inicio < 1
    assert len(tentados) == len(set(tentados)), "cada modelo tentado uma vez so"


def test_sobrecarga_persistente_desiste_apos_as_rodadas(monkeypatch, chaves):
    monkeypatch.setattr(llm, "ESPERA_SOBRECARGA_SEGUNDOS", 0)
    monkeypatch.setattr(llm, "RODADAS_SOBRECARGA", 2)
    monkeypatch.delenv("GROQ_API_KEY")
    tentados = _instalar(monkeypatch, {
        ("google", m): ChatSobrecarregado(99, None) for m in llm.PROVEDORES["google"]["modelos"]
    })
    with pytest.raises(llm.LLMIndisponivel, match="503"):
        llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))
    assert len(tentados) == 2 * len(llm.PROVEDORES["google"]["modelos"])


def test_resposta_vazia_conta_como_falha(monkeypatch, chaves):
    _instalar(monkeypatch, {
        ("google", "gemini-3.6-flash"): ChatFalso(_resposta("   ")),
        ("google", "gemini-3.5-flash-lite"): ChatFalso(_resposta("cheia")),
    })
    r = llm.gerar_texto("p", ConfigLLM(provedor="google", modelo="gemini-3.6-flash"))
    assert r.modelo == "gemini-3.5-flash-lite"


@pytest.mark.parametrize("conteudo, esperado", [
    ("  texto  ", "texto"),
    ([{"type": "text", "text": '{"a":'}, {"type": "text", "text": " 1}"}], '{"a": 1}'),
    (["parte 1 ", "parte 2"], "parte 1 parte 2"),
    (None, ""),
])
def test_formatos_de_resposta_do_gemini(conteudo, esperado):
    """A lista de partes do Gemini era o bug que se disfarçava de fallback no Desafio 5."""
    assert llm._extrair_texto(conteudo) == esperado
