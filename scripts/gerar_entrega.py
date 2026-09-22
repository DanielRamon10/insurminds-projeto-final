"""Gera o ZIP da entrega do Projeto Final.

O enunciado pede um "arquivo ZIP contendo todo o código-fonte e demais artefatos".
Este script monta o pacote e **se recusa a fechá-lo** quando algo está errado, em
vez de produzir um ZIP que só se descobre incompleto depois de enviado.

    python -m scripts.gerar_entrega              # exige tudo pronto
    python -m scripts.gerar_entrega --parcial    # aceita pitch e vídeo faltando

O modo `--parcial` existe para conferir o pacote antes de o vídeo ficar pronto.
A entrega final tem de passar no modo padrão.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "InsurMinds_Projeto_Final_codigo_fonte.zip"

INCLUIR = [
    "app",
    "scripts",
    "tests",
    "data",
    "docs",
    "Projeto_Final_Artefatos",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "README.md",
    "README.pt-BR.md",
    "LICENSE",
]

EXCLUIR_DIRS = {
    ".venv", "venv", "__pycache__", ".git", ".pytest_cache",
    ".cache", ".workspace", "cache",
}
EXCLUIR_ARQUIVOS = {".env", "secrets.toml"}
EXCLUIR_SUFIXOS = {".pyc", ".pyo", ".zip", ".log", ".db", ".html"}

#: Padrões de credencial procurados no conteúdo dos arquivos de texto. A lista
#: cresceu com os provedores que o grupo passou a usar — o enunciado avalia
#: "ocultar credenciais e chaves de API" entre as boas práticas.
PADROES_SEGREDO = [
    ("Google", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("Anthropic", re.compile(r"\bsk-ant-[0-9A-Za-z_\-]{20,}")),
    ("OpenAI", re.compile(r"\bsk-(?:proj-)?[0-9A-Za-z_\-]{32,}")),
    ("OpenRouter", re.compile(r"\bsk-or-v1-[0-9a-f]{32,}")),
    ("Groq", re.compile(r"\bgsk_[0-9A-Za-z]{40,}")),
    ("GitHub", re.compile(r"\b(?:ghp_|github_pat_)[0-9A-Za-z_]{30,}")),
    ("AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
]

#: Entregáveis que o enunciado exige nominalmente.
ARTEFATOS = RAIZ / "Projeto_Final_Artefatos"
OBRIGATORIOS = [
    (RAIZ / "README.md", "README (o enunciado exige seis itens nele)"),
    (RAIZ / "LICENSE", "licença MIT"),
    (RAIZ / "data" / "campos_do.yaml", "dicionário de campos do especialista"),
]
ARTEFATOS_FINAIS = [
    (ARTEFATOS / "InsurMinds_Projeto_Final.pptx", "pitch deck"),
    (ARTEFATOS / "InsurMinds_Projeto_Final.mp4", "vídeo de até 5 minutos"),
]

#: Seis itens que o enunciado exige no README, com o que procurar em cada idioma.
ITENS_README = [
    ("descrição do projeto", ("MVP",)),
    ("instruções de instalação", ("## Installation", "## Instalação")),
    ("instruções de execução", ("## Running", "## Execução")),
    ("tecnologias utilizadas", ("## Tech stack", "## Tecnologias")),
    ("identificação dos integrantes", ("## Team", "## Grupo")),
    ("licença MIT", ("MIT license", "licença MIT")),
]

#: O GitHub recusa arquivo acima disto, e o vídeo é o candidato natural a estourar.
LIMITE_GITHUB_MB = 100

TEXTO = {".py", ".md", ".txt", ".yaml", ".yml", ".csv", ".toml", ".json", ".example", ".cfg"}


def deve_incluir(caminho: Path) -> bool:
    if set(caminho.parts) & EXCLUIR_DIRS:
        return False
    if caminho.name in EXCLUIR_ARQUIVOS:
        return False
    return caminho.suffix.lower() not in EXCLUIR_SUFIXOS


def reunir() -> list[Path]:
    arquivos: list[Path] = []
    for alvo in INCLUIR:
        caminho = RAIZ / alvo
        if not caminho.exists():
            print(f"  aviso: {alvo} nao existe e sera ignorado")
            continue
        if caminho.is_file():
            arquivos.append(caminho)
        else:
            arquivos += [p for p in caminho.rglob("*") if p.is_file() and deve_incluir(p)]
    return sorted(arquivos)


def procurar_segredos(arquivos: list[Path]) -> list[str]:
    achados: list[str] = []
    for arquivo in arquivos:
        if arquivo.suffix.lower() not in TEXTO:
            continue
        try:
            conteudo = arquivo.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rotulo, padrao in PADROES_SEGREDO:
            if m := padrao.search(conteudo):
                achados.append(
                    f"{arquivo.relative_to(RAIZ)}: possivel chave {rotulo} "
                    f"({m.group()[:14]}...)"
                )
    return achados


#: Marcas de seção ainda não escrita. Conferir só o título deixaria passar um
#: README com todos os cabeçalhos e nenhum conteúdo — que foi o estado real deste
#: repositório por uma semana.
PENDENCIAS = ("a ser preenchido", "to be filled", "a definir", "tbd", "em breve")


def conferir_readme() -> list[str]:
    """O enunciado lista seis itens obrigatórios; confere se todos estão escritos."""
    problemas: list[str] = []
    for nome in ("README.md", "README.pt-BR.md"):
        caminho = RAIZ / nome
        if not caminho.is_file():
            continue
        texto = caminho.read_text(encoding="utf-8", errors="ignore")

        for rotulo, marcas in ITENS_README:
            if not any(m in texto for m in marcas):
                problemas.append(f"{nome}: falta '{rotulo}'")

        baixo = texto.lower()
        for pendencia in PENDENCIAS:
            if pendencia in baixo:
                problemas.append(f"{nome}: tem secao marcada como '{pendencia}'")

    return problemas


def conferir_arquivos_grandes(arquivos: list[Path]) -> list[str]:
    limite = LIMITE_GITHUB_MB * 1024 * 1024
    return [
        f"{a.relative_to(RAIZ)}: {a.stat().st_size / 1024 / 1024:.0f} MB"
        for a in arquivos if a.stat().st_size > limite
    ]


def rodar_testes() -> tuple[bool, str]:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=RAIZ, capture_output=True, text=True, timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"nao foi possivel rodar a suite: {exc}"
    linhas = [l for l in r.stdout.splitlines() if l.strip()]
    return r.returncode == 0, (linhas[-1] if linhas else "(sem saida)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o ZIP da entrega do Projeto Final")
    parser.add_argument(
        "--parcial", action="store_true",
        help="aceita pitch e video faltando (para conferir o pacote antes da entrega)",
    )
    argumentos = parser.parse_args()

    print("Empacotando a entrega do Projeto Final\n")

    arquivos = reunir()
    print(f"  {len(arquivos)} arquivos reunidos")

    faltando = [f"{c.name} ({motivo})" for c, motivo in OBRIGATORIOS if not c.is_file()]
    if faltando:
        print("\nABORTADO: entregavel obrigatorio ausente")
        for f in faltando:
            print(f"  - {f}")
        return 1

    if itens := conferir_readme():
        print("\nABORTADO: o README nao traz todos os itens que o enunciado exige")
        for i in itens:
            print(f"  - {i}")
        return 1
    print("  README com os seis itens exigidos")

    sem_artefato = [f"{c.name} ({motivo})" for c, motivo in ARTEFATOS_FINAIS if not c.is_file()]
    if sem_artefato:
        if not argumentos.parcial:
            print("\nABORTADO: artefato da entrega ausente")
            for a in sem_artefato:
                print(f"  - {a}")
            print("\nUse --parcial para gerar o pacote mesmo assim, enquanto nao ficam prontos.")
            return 1
        print("  AVISO: pacote parcial, faltam:")
        for a in sem_artefato:
            print(f"    - {a}")
    else:
        print("  pitch deck e video presentes")

    if grandes := conferir_arquivos_grandes(arquivos):
        print(f"\n  AVISO: arquivo(s) acima de {LIMITE_GITHUB_MB} MB, que o GitHub recusa:")
        for g in grandes:
            print(f"    - {g}")
        print("    O video precisa ser comprimido, ou hospedado fora com o link no repositorio.")

    if achados := procurar_segredos(arquivos):
        print("\nABORTADO: credencial encontrada no conteudo dos arquivos")
        for a in achados:
            print(f"  - {a}")
        print("\nRemova a credencial e revogue a chave antes de gerar o pacote.")
        return 1
    print("  nenhuma credencial encontrada")

    passou, resumo = rodar_testes()
    if not passou:
        print(f"\nABORTADO: a suite de testes nao passou -> {resumo}")
        return 1
    print(f"  testes: {resumo}")

    if DESTINO.exists():
        DESTINO.unlink()
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED) as z:
        for arquivo in arquivos:
            z.write(arquivo, arquivo.relative_to(RAIZ))

    tamanho = DESTINO.stat().st_size / 1024 / 1024
    print(f"\nPacote gerado: {DESTINO.name} ({tamanho:.1f} MB, {len(arquivos)} arquivos)")
    if sem_artefato:
        print("ATENCAO: pacote parcial — nao serve para a entrega final.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
