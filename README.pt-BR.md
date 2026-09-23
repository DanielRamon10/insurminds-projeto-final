# Plataforma Inteligente para Análise e Comparação de Apólices D&O

*[Read in English](README.md)*

**Projeto Final — Curso InsurMinds · Instituto de Inteligência Artificial Aplicada (I2A2)**

Protótipo (MVP) que lê apólices de seguro D&O (*Directors and Officers*) em PDF ou
imagem, extrai automaticamente as informações relevantes — coberturas, exclusões,
franquias, limites de responsabilidade —, armazena de forma estruturada e compara
duas ou mais apólices, apontando as diferenças que importam para a decisão.

Comparar apólices D&O é hoje trabalho de especialista e leva horas: são documentos
longos, em linguagem jurídica, cujas cláusulas equivalentes aparecem com nomes e em
lugares diferentes em cada seguradora. A proposta é automatizar a maior parte dessa
leitura **sem esconder de onde cada informação veio**.

Licenciado sob a **licença MIT** (ver [LICENSE](LICENSE)).

---

## Grupo

| Integrante | Frente |
| --- | --- |
| Daniel Ramon | Ingestão e OCR · Armazenamento e comparação · Documentação |
| Paulo Henrique | Campos e cláusulas D&O (regras de negócio) |
| Nicole Paes | Extração das cláusulas com IA Generativa |
| Paulo Roberto | Interface, demonstração e apresentação |
| Juliana Catarina | Representante do grupo |

---

## Estado do projeto

| Frente | Situação |
| --- | --- |
| Ingestão de documentos e OCR | pronta |
| Dicionário de campos D&O | pronto |
| Extração das cláusulas com LLM | em desenvolvimento |
| Armazenamento e comparação | pronto |
| Relatório comparativo em prosa | aguarda a extração |
| Interface de demonstração | em desenvolvimento |

**Prazo de entrega: 06/10/2026 às 23h59.** O roteiro completo está em
[`docs/ROTEIRO_PROJETO_FINAL.pt-BR.md`](docs/ROTEIRO_PROJETO_FINAL.pt-BR.md).

---

## Instalação

Requer **Python 3.10 ou superior**.

```bash
git clone https://github.com/DanielRamon10/insurminds-projeto-final.git
cd insurminds-projeto-final

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

### OCR (opcional)

As apólices de exemplo são PDFs com texto embutido e **não precisam de OCR**. Ele só
entra quando o documento é escaneado ou quando a entrada é uma imagem — o que o
enunciado exige que a plataforma aceite.

Para esse caso, instale o [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
com o pacote de português:

```bash
# Windows: instalador do link acima, marcando "Portuguese" nos idiomas
# Linux:   sudo apt install tesseract-ocr tesseract-ocr-por
# macOS:   brew install tesseract tesseract-lang
```

Se ele ficar fora do `PATH`, aponte o caminho no `.env`:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Chave de API

```bash
copy .env.example .env           # Windows
# cp .env.example .env             # Linux / macOS
```

Abra o `.env` e preencha a chave de pelo menos um provedor. Quanto mais provedores
configurados, mais a cascata aguenta antes de ficar sem cota — **comparar duas
apólices custa cerca de 78 mil tokens de entrada**.

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=sua-chave-aqui
GROQ_API_KEY=
OPENROUTER_API_KEY=
```

O arquivo `.env` está no `.gitignore` e **nunca deve ser versionado**. Nenhuma
credencial aparece no código-fonte.

---

## Execução

### Leitura de documentos

```bash
python -m scripts.demo_ingestao                    # as apólices de data/apolices/
python -m scripts.demo_ingestao caminho/para/outra.pdf
```

Mostra quantas páginas cada documento tem, quanto texto rendeu, quantas páginas
precisaram de OCR e uma amostra do que é entregue ao modelo.

### Comparação entre apólices

```bash
python -m scripts.demo_comparacao
```

Roda o motor de comparação e imprime o que distingue duas apólices, campo a campo,
com a página de origem de cada valor.

### Testes

```bash
python -m pytest -q
```

Nenhum teste depende de rede: as respostas do modelo de linguagem são simuladas, e
os que usam as apólices reais são pulados caso os arquivos não estejam presentes.

---

## Tecnologias utilizadas

| Camada | Tecnologia | Papel |
| --- | --- | --- |
| Leitura de PDF | `pypdf` | extrai o texto embutido, preservando o número da página |
| Renderização | `pypdfium2` | converte página em imagem para o OCR, sem depender do poppler |
| OCR | Tesseract + `pytesseract` | lê documento escaneado e imagem, em português |
| Contratos de dados | Pydantic v2 | valida a fronteira entre as frentes de trabalho |
| Regras de negócio | YAML | dicionário de campos alterável sem tocar em código |
| Modelos de linguagem | LangChain + Google Gemini, Groq, OpenRouter | extração das cláusulas |
| Armazenamento | SQLite | guarda as extrações com a rastreabilidade intacta |
| Interface | Streamlit | demonstração da comparação |
| Testes | pytest | suíte sem dependência de rede |

---

## Como a solução está organizada

```
documento (PDF ou imagem)
        |
        v
  INGESTAO (app/domain/ingestao.py)
  le pagina a pagina, OCR onde faltar texto
        |
        v  DocumentoExtraido — o texto nunca perde o numero da pagina
        |
  EXTRACAO (app/agents/)
  o LLM procura os campos de data/campos_do.yaml
        |
        v  ApoliceExtraida — cada campo guarda pagina e trecho de origem
        |
  ARMAZENAMENTO (app/domain/armazenamento.py)
        |
        v
  COMPARACAO (app/domain/comparacao.py)
  campo a campo, sem LLM: deterministico e testavel
        |
        v
  RELATORIO + INTERFACE
```

A decisão que atravessa todo o desenho: **o texto nunca perde o número da página**,
e todo campo extraído guarda o trecho de onde saiu. É o que separa uma extração
auditável de um chute bem formatado — e num documento jurídico um limite de
indenização inventado é pior que nenhum.

### Estrutura de pastas

| Caminho | Conteúdo |
| --- | --- |
| `app/clients/` | Extração de texto de PDF e OCR |
| `app/domain/` | Ingestão, dicionário de campos, comparação e armazenamento |
| `app/agents/` | Agentes de extração e redação com LLM |
| `data/apolices/` | Condições gerais públicas usadas nos testes, com as fontes citadas |
| `data/campos_do.yaml` | Os campos que a plataforma procura, definidos pelo corretor do grupo |
| `docs/` | Roteiro do projeto e relatório técnico |
| `scripts/` | Demonstrações por linha de comando |
| `tests/` | Testes automatizados |
| `Projeto_Final_Artefatos/` | Pitch deck, vídeo e demais artefatos da entrega |

---

## Observações

Nenhuma integração com sistemas reais de seguradoras. As apólices utilizadas são
**condições gerais públicas**, publicadas pelas próprias seguradoras para consulta
aberta, e suas fontes estão citadas em
[`data/apolices/FONTES.md`](data/apolices/FONTES.md). Nenhum documento contém dado
de cliente.
