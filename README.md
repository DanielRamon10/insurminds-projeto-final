# Intelligent Platform for D&O Policy Analysis and Comparison

**Final Project — InsurMinds Course · Instituto de Inteligência Artificial Aplicada (I2A2)**

*[Leia em português](README.pt-BR.md)*

A prototype (MVP) that reads D&O (*Directors and Officers*) insurance policies from
PDF or image, automatically extracts the relevant information — coverages,
exclusions, deductibles, liability limits — stores it in structured form, and
compares two or more policies, surfacing the differences that matter to a decision.

Comparing D&O policies is specialist work today and takes hours: the documents are
long, written in legal language, and equivalent clauses show up under different
names and in different places at each insurer. The aim is to automate most of that
reading **without hiding where each piece of information came from**.

Licensed under the **MIT license** (see [LICENSE](LICENSE)).

---

## Team

| Member | Workstream |
| --- | --- |
| Daniel Ramon | Ingestion and OCR · Storage and comparison · Documentation |
| Paulo Henrique | D&O fields and clauses (business rules) |
| Nicole Paes | Clause extraction with Generative AI |
| Paulo Roberto | Interface, demo and presentation |
| Juliana Catarina | Group representative |

---

## Project status

| Workstream | Status |
| --- | --- |
| Document ingestion and OCR | done |
| D&O field dictionary | done |
| Clause extraction with an LLM | in progress |
| Storage and comparison | done |
| Prose comparison report | waiting on extraction |
| Demo interface | in progress |

**Deadline: October 6, 2026, 11:59 PM.** The full roadmap lives in
[`docs/ROTEIRO_PROJETO_FINAL.md`](docs/ROTEIRO_PROJETO_FINAL.md).

---

## Installation

Requires **Python 3.10 or later**.

```bash
git clone https://github.com/DanielRamon10/insurminds-projeto-final.git
cd insurminds-projeto-final

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

### OCR (optional)

The sample policies are PDFs with embedded text and **need no OCR**. It only kicks
in for scanned documents or image input — which the assignment requires the platform
to accept.

For that case, install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
with the Portuguese language pack:

```bash
# Windows: installer from the link above, ticking "Portuguese" under languages
# Linux:   sudo apt install tesseract-ocr tesseract-ocr-por
# macOS:   brew install tesseract tesseract-lang
```

If it ends up outside `PATH`, point to it in `.env`:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### API key

```bash
copy .env.example .env           # Windows
# cp .env.example .env             # Linux / macOS
```

Open `.env` and fill in a key for at least one provider. The more providers
configured, the longer the cascade holds out before running out of quota —
**comparing two policies costs roughly 78,000 input tokens**.

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your-key-here
GROQ_API_KEY=
OPENROUTER_API_KEY=
```

`.env` is in `.gitignore` and **must never be committed**. No credential appears in
the source.

---

## Running

### Reading documents

```bash
python -m scripts.demo_ingestao                    # the policies in data/apolices/
python -m scripts.demo_ingestao path/to/another.pdf
```

Shows how many pages each document has, how much text came out, how many pages
needed OCR, and a sample of what gets handed to the model.

### Comparing policies

```bash
python -m scripts.demo_comparacao
```

Runs the comparison engine and prints what separates two policies, field by field,
with the source page of every value.

### Tests

```bash
python -m pytest -q
```

No test depends on the network: language-model responses are simulated, and the ones
that use the real policies are skipped if the files aren't present.

---

## Tech stack

| Layer | Technology | Role |
| --- | --- | --- |
| PDF reading | `pypdf` | extracts embedded text, preserving the page number |
| Rendering | `pypdfium2` | turns a page into an image for OCR, with no poppler dependency |
| OCR | Tesseract + `pytesseract` | reads scanned documents and images, in Portuguese |
| Data contracts | Pydantic v2 | validates the boundary between workstreams |
| Business rules | YAML | field dictionary editable without touching code |
| Language models | LangChain + Google Gemini, Groq, OpenRouter | clause extraction |
| Storage | SQLite | keeps extractions with traceability intact |
| Interface | Streamlit | comparison demo |
| Tests | pytest | suite with no network dependency |

---

## How the solution is organised

```
document (PDF or image)
        |
        v
  INGESTION (app/domain/ingestao.py)
  reads page by page, OCR wherever text is missing
        |
        v  DocumentoExtraido - the text never loses its page number
        |
  EXTRACTION (app/agents/)
  the LLM looks for the fields in data/campos_do.yaml
        |
        v  ApoliceExtraida - every field keeps its source page and passage
        |
  STORAGE (app/domain/armazenamento.py)
        |
        v
  COMPARISON (app/domain/comparacao.py)
  field by field, no LLM: deterministic and testable
        |
        v
  REPORT + INTERFACE
```

The decision that runs through the whole design: **the text never loses its page
number**, and every extracted field keeps the passage it came from. That is what
separates an auditable extraction from a well-formatted guess — and in a legal
document an invented indemnity limit is worse than none at all.

### Repository layout

| Path | Contents |
| --- | --- |
| `app/clients/` | PDF text extraction and OCR |
| `app/domain/` | Ingestion, field dictionary, comparison and storage |
| `app/agents/` | LLM extraction and drafting agents |
| `data/apolices/` | Public general conditions used in tests, with sources cited |
| `data/campos_do.yaml` | The fields the platform looks for, defined by the group's broker |
| `docs/` | Project roadmap and technical report |
| `scripts/` | Command-line demos |
| `tests/` | Automated tests |
| `Projeto_Final_Artefatos/` | Pitch deck, video and other delivery artefacts |

---

## Notes

No integration with real insurer systems. The policies used are **public general
conditions**, published by the insurers themselves for open consultation, and their
sources are cited in [`data/apolices/FONTES.md`](data/apolices/FONTES.md). No
document contains customer data.
