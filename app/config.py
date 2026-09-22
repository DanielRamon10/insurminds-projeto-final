"""Configuração do projeto: caminhos, provedores de LLM e OCR.

Nenhuma credencial mora aqui. As chaves vêm do `.env`, que está no `.gitignore`;
o `.env.example` mostra o formato sem conter segredo nenhum.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
APOLICES_DIR = DATA_DIR / "apolices"
CACHE_DIR = DATA_DIR / "cache"

load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Leitura de documentos
# ---------------------------------------------------------------------------

#: Extensões aceitas na recepção (tarefa A.1).
EXTENSOES_PDF = {".pdf"}
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

#: Abaixo disto a página é tratada como "sem texto embutido" e vai para o OCR.
#: Uma página de apólice com texto real passa de mil caracteres; uma página só com
#: o logotipo escaneado devolve algumas dezenas de caracteres de ruído.
MINIMO_CARACTERES_PAGINA = 80

#: Resolução do render antes do OCR. 300 dpi é o que o Tesseract recomenda para
#: texto impresso; abaixo disso a taxa de erro sobe rápido em fonte pequena.
DPI_OCR = 300

#: Idioma do OCR. `por` está instalado junto com o Tesseract padrão em português.
IDIOMA_OCR = "por"


def caminho_tesseract() -> str | None:
    """Onde está o executável do Tesseract, ou `None` se não houver.

    Procura no PATH e nos lugares onde o instalador do Windows costuma deixá-lo —
    ele não entra no PATH por padrão, e falhar por isso seria confuso.
    """
    if forcado := os.environ.get("TESSERACT_CMD"):
        return forcado if Path(forcado).is_file() else None

    if achado := shutil.which("tesseract"):
        return achado

    candidatos = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path("/usr/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
        Path("/opt/homebrew/bin/tesseract"),
    ]
    return next((str(c) for c in candidatos if c.is_file()), None)


# ---------------------------------------------------------------------------
# Modelos de linguagem
# ---------------------------------------------------------------------------

#: Provedores em ordem de preferência. A ordem importa: extrair cláusula jurídica
#: é tarefa em que a qualidade do modelo pesa muito — um modelo fraco inventa
#: limite de indenização —, então a cascata cai por qualidade, não por acaso.
#:
#: `base_url` presente significa API compatível com a da OpenAI: o mesmo pacote
#: `langchain-openai` serve, só mudando o endereço. É o caso do OpenRouter e do
#: Groq, que por isso custam uma integração só em vez de duas.
PROVEDORES: dict[str, dict[str, object]] = {
    "google": {
        "rotulo": "Google (Gemini)",
        "env_key": "GOOGLE_API_KEY",
        "modelo_padrao": "gemini-3.6-flash",
        # Camada gratuita, com cota diária por modelo: se um esgotar, o seguinte
        # da lista assume sem esperar o dia virar.
        "modelos": [
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
        ],
        "pacote": "langchain-google-genai",
        "base_url": None,
    },
    "anthropic": {
        "rotulo": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "modelo_padrao": "claude-sonnet-5",
        "modelos": ["claude-sonnet-5", "claude-haiku-4-5"],
        "pacote": "langchain-anthropic",
        "base_url": None,
    },
    "openai": {
        "rotulo": "OpenAI (GPT)",
        "env_key": "OPENAI_API_KEY",
        "modelo_padrao": "gpt-4.1",
        "modelos": ["gpt-4.1", "gpt-4.1-mini"],
        "pacote": "langchain-openai",
        "base_url": None,
    },
    "groq": {
        "rotulo": "Groq",
        "env_key": "GROQ_API_KEY",
        "modelo_padrao": "openai/gpt-oss-120b",
        "modelos": ["openai/gpt-oss-120b"],
        "pacote": "langchain-openai",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "openrouter": {
        "rotulo": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "modelo_padrao": "qwen/qwen3.8-27b:free",
        "modelos": ["qwen/qwen3.8-27b:free"],
        "pacote": "langchain-openai",
        "base_url": "https://openrouter.ai/api/v1",
    },
}

#: Ordem em que a cascata tenta os provedores quando um esgota a cota. Só entram
#: os que tiverem chave configurada — a lista é uma preferência, não uma exigência.
ORDEM_CASCATA = ["google", "groq", "openrouter", "anthropic", "openai"]


def provedores_disponiveis() -> list[str]:
    """Provedores com chave configurada, na ordem de preferência da cascata."""
    return [p for p in ORDEM_CASCATA if obter_api_key(p)]


@dataclass(frozen=True)
class ConfigLLM:
    """Provedor e modelo em uso, lidos do ambiente."""

    provedor: str = os.environ.get("LLM_PROVIDER", "google")
    modelo: str = ""

    def __post_init__(self) -> None:
        if self.provedor not in PROVEDORES:
            raise ValueError(
                f"provedor '{self.provedor}' desconhecido "
                f"(validos: {', '.join(PROVEDORES)})"
            )
        if not self.modelo:
            padrao = os.environ.get("LLM_MODEL") or PROVEDORES[self.provedor]["modelo_padrao"]
            object.__setattr__(self, "modelo", str(padrao))

    @property
    def env_key(self) -> str:
        return str(PROVEDORES[self.provedor]["env_key"])


def obter_api_key(provedor: str) -> str | None:
    """Chave do provedor, ou `None` se não estiver configurada."""
    if provedor not in PROVEDORES:
        return None
    return os.environ.get(str(PROVEDORES[provedor]["env_key"])) or None
