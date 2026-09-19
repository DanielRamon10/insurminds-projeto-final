# Intelligent Platform for D&O Policy Analysis and Comparison

**Final Project — InsurMinds Course · Instituto de Inteligência Artificial Aplicada (I2A2)**

*[Leia em português](README.pt-BR.md)*

A prototype (MVP) that reads D&O (*Directors and Officers*) insurance policies from PDF
or image, automatically extracts the relevant information — coverages, exclusions,
deductibles, limits of liability —, stores it in structured form and compares two or more
policies, surfacing the differences that actually matter for the decision.

Comparing D&O policies is specialist work today and takes hours: the documents are long,
written in legal language, and equivalent clauses show up under different names and in
different places depending on the insurer. The goal is to automate most of that reading
without hiding where each piece of information came from.

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

In development. The roadmap covering the workstreams and their tasks lives in
[`docs/`](docs/).

**Delivery deadline: October 6, 2026 at 11:59 PM.**

---

## Installation

Requires **Python 3.10 or newer**.

```bash
git clone https://github.com/DanielRamon10/insurminds-projeto-final.git
cd insurminds-projeto-final

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

### API key configuration

```bash
copy .env.example .env           # Windows
# cp .env.example .env             # Linux / macOS
```

Open `.env` and fill in the key for your chosen provider. The `.env` file is listed in
`.gitignore` and **must never be committed** — no credential appears anywhere in the
source code.

---

## Running

*To be filled in as the workstreams deliver.*

---

## Tech stack

*To be filled in once the Phase 0 decisions are made.*

---

## Repository layout

| Path | Contents |
| --- | --- |
| `app/clients/` | Integration with external services (OCR, language models) |
| `app/domain/` | Clause extraction, structuring and policy-to-policy comparison |
| `app/agents/` | Specialised agents and the orchestrator |
| `data/` | Sample policies and structured data |
| `docs/` | Project roadmap and technical report |
| `scripts/` | Command-line demo and utilities |
| `tests/` | Automated tests |
| `Projeto_Final_Artefatos/` | Pitch deck, video and the other artifacts required for delivery |

---

## Notes

There is no integration with real insurer systems. The policies used are public
documents, and their sources are cited in the technical report.
