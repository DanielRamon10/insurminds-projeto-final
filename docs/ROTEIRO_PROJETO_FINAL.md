# Final Project Roadmap — D&O Policy Analysis and Comparison Platform

**Insurminds group · InsurMinds Course / I2A2**
**Deadline: October 6, 2026 at 11:59 PM** — this document was written on September 14, 2026; **22 days remain**.

---

## What changes relative to Challenge 5

Three new things, and all three carry weight:

| What's new | Why it needs attention |
| --- | --- |
| **Pitch deck** (`InsurMinds_Projeto_Final.pptx`) | Mandatory, literal filename. This is not a supporting slide: it is a graded deliverable |
| **Video, 5 minutes maximum** (`InsurMinds_Projeto_Final.mp4`) | Needs a working product to record. Leave it to the end and it won't exist |
| **Unstructured input document** | In Challenge 5 the API handed back ready-made numbers. Here the input is a legal PDF dozens of pages long |

And a change in kind: **this is the course's final assessment**. Without it the group does
not pass and nobody receives the advanced-module certificate.

---

## Phase 0 — Decisions to make before writing code

None of this is technical enough for one person to decide alone. There are four
decisions, and every one of them blocks work in more than one workstream.

### F0.1 — Which fields to compare

**The most important decision in the project.** A D&O policy has dozens of clauses; the
system doesn't need to extract all of them, it needs to extract the ones that change a
decision.

Candidates for the discussion: maximum indemnity limit, deductible (retention), policy
period, geographic scope, definition of the insured, main exclusions, defence-costs
coverage, retroactive date, extended reporting period.

> **Who decides:** Paulo Henrique leads — he's a broker, and this is exactly the reading
> he does at work. The group confirms the scope.
> **Target:** 8 to 12 fields. Fewer than that doesn't demonstrate comparison; more turns
> into shallow extraction across the board.

### F0.2 — Where to get the policies

The assignment suggests public documents: templates published by insurers, SUSEP
material, standard market clauses. **We need at least three real policies from three
different insurers** — comparing two versions of the same template demonstrates nothing.

> **Who decides:** Paulo Henrique points at where to look; anyone can download them.
> **Note:** the source of each document has to be cited in the report.

### F0.3 — How to read the document

Three routes, and the choice reshapes all of workstream A:

1. **Native PDF** (embedded text) — `pypdf` handles it, it's fast and it costs nothing.
2. **Scanned PDF** — requires OCR (Tesseract locally, or a cloud service).
3. **Multimodal LLM** — send the page as an image and let the model read it.

> **Recommendation:** try route 1 first and fall back to OCR only when a page has no
> text. Most public policy templates are native PDFs. But **the assignment requires
> accepting images**, so route 2 has to exist even if only for one document.

### F0.4 — Where to store what was extracted

The assignment asks for "structured storage" and mentions SQL or NoSQL. For an MVP,
SQLite handles it and requires standing up no service at all.

> **Recommendation:** SQLite. The question to answer in the report isn't "which database",
> it's "why this database is enough for this problem".

---

## The five workstreams

### Workstream A — Ingestion and text extraction

Turn the incoming file into reliable text, knowing which page each passage came from —
without that, workstream B's traceability dies.

| Task | What it delivers |
| --- | --- |
| **A.1** | Document intake: accepts PDF and image, rejects everything else with a clear message |
| **A.2** | Native-PDF extraction, preserving the page number |
| **A.3** | OCR for pages with no embedded text |
| **A.4** | Fault tolerance: a corrupt document or an unreadable page doesn't take down the batch |

**Done when:** the three policies chosen in F0.2 become text, and every passage can say
which page it came from.

### Workstream B — Clause extraction (the heart of the project)

This is where Generative AI genuinely comes in, and it's what the assignment grades as
"correct use of Generative AI".

| Task | What it delivers |
| --- | --- |
| **B.1** | Dictionary of the F0.1 fields: name, what it means, how it usually appears in the text |
| **B.2** | LLM extraction agent: takes the text, returns the structured fields |
| **B.3** | **Traceability**: every extracted field records its source page and passage |
| **B.4** | Validation: a missing field is an explicit `null`, never invented |

**Done when:** running over the three policies produces a filled-in structure, and for
any field it's possible to point at where it was in the document.

> **The lesson from Challenge 5, applied here:** there, the guardrail stopped the model
> from quoting a number the forecast didn't contain. Here the stakes are higher — an
> invented indemnity limit is worse than a wrong message. **B.3 is not decoration: it's
> what separates this project from a well-formatted guess.**

### Workstream C — Storage and comparison

| Task | What it delivers |
| --- | --- |
| **C.1** | Database schema and persistence of processed policies |
| **C.2** | Comparison engine: field by field, across two or more policies |
| **C.3** | Difference classification: identical, different, missing in one of them |
| **C.4** | Comparative report in prose, generated by an LLM from the differences |

**Done when:** given two policies, out comes a table of differences plus a summary
explaining what they mean for the buyer.

> **Mind the boundary:** C.2 decides *what* is different (deterministic, testable); C.4
> explains *why it matters* (LLM). Mixing the two was the mistake that cost us a
> consolidation PR in Challenge 5.

### Workstream D — Interface and demo

| Task | What it delivers |
| --- | --- |
| **D.1** | Policy upload through the interface |
| **D.2** | Side-by-side view of the differences |
| **D.3** | Traceability on screen: click a field and see where it came from |
| **D.4** | Command-line demo, so the video doesn't depend on the interface |

**Done when:** you can upload two policies and see the comparison without touching a
terminal.

### Workstream E — Documentation, pitch and video

Bigger than in Challenge 5, and with two deliverables that aren't text.

| Task | What it delivers |
| --- | --- |
| **E.1** | README with the **six** items the assignment requires |
| **E.2** | Technical report with **seven** sections (two new: known limitations and future work) |
| **E.3** | `InsurMinds_Projeto_Final.pptx` — pitch deck |
| **E.4** | `InsurMinds_Projeto_Final.mp4` — video, 5 minutes maximum |
| **E.5** | Code ZIP and organisation of the `Projeto_Final_Artefatos` folder |

---

## Suggested split

Based on what each person demonstrated in Challenge 5. **Juliana is travelling**, so
workstream E has been divided among the four of us — she stays on as the group
representative, responsible for submission, and picks back up whatever makes sense when
she returns.

| Member | Workstream | Why |
| --- | --- | --- |
| **Paulo Henrique** | F0.1, F0.2, B.1 + the business content of the pitch | He's the broker. The D&O field dictionary is this project's `regras.yaml` — the piece that gave Challenge 5 its strongest argument. And the pitch's problem statement is the pain he lives: specialist hours spent comparing clauses |
| **Nicole Paes** | Workstream B (B.2 to B.4) | She delivered the agents and found the LLM bug that was disguising itself as a correct fallback |
| **Daniel Ramon** | Workstreams A and C + E.1, E.5 + consolidating the report | Collection and the rules engine were his in Challenge 5, and so were the README and the packaging |
| **Paulo Roberto** | Workstream D + **E.3 (pitch)** + **E.4 (video)** | He built the interface and the demo; he's the one who best knows how to show the system working |
| **Juliana Catarina** | Submitting the delivery | Group representative — the submission must go out from her email |

### The technical report without Juliana

E.2 is the largest orphaned piece. Instead of a single owner, **each workstream writes
the section that corresponds to it** and Daniel consolidates:

| Report section | Who writes it |
| --- | --- |
| Solution architecture | Daniel |
| Tech stack | Daniel |
| Description of the agents | Nicole (workstream B) and Paulo Roberto (workstream D) |
| Processing flow | Daniel |
| Rationale for the architectural decisions | whoever made each decision, in one sentence |
| Known limitations | everyone — each of us knows where our own workstream is fragile |
| Future work | everyone |

> **When Juliana returns**, the natural move is to hand her back the review and final
> formatting of the report — that's what she did well in Challenge 5, and it's
> end-of-cycle work. If she's back in time, the pitch can go to her as well, freeing
> Paulo Roberto to focus on the video. Reassess around **September 27**.

> **Why the video goes to Paulo Roberto:** recording requires the application running in
> the hands of whoever built it. He assembles the pitch and records; Paulo Henrique
> supplies the business-problem content, which is the first part of the deck.

---

## Suggested calendar

| By | What has to be ready |
| --- | --- |
| **Sep 17** | Phase 0 closed. Policies downloaded, fields defined, stack chosen |
| **Sep 22** | Workstreams A and B working: a document goes in, structured fields come out |
| **Sep 27** | Workstream C: comparison between two policies producing output. **Reassess what to hand back to Juliana** |
| **Sep 30** | Workstream D: demonstrable interface. **Feature freeze** |
| **Oct 2** | Video recorded and pitch ready |
| **Oct 4** | Final report and ZIP. Group review |
| **Oct 6** | Delivery — **do not leave it for this day** |

The September 30 freeze isn't bureaucracy: **without a stable product there is no video**,
and the video is the deliverable easiest to lose for lack of time.

---

## Known risks

1. **The video slipping to the end.** It's the item most likely to be late. That's why it
   has its own owner and its own date.
2. **Hallucinated extraction.** An invented indemnity limit slides past unnoticed in a
   demo and destroys credibility the moment someone asks about it. B.3 and B.4 exist
   against exactly this.
3. **LLM quota.** It already bit us in Challenges 4 and 5. Processing a whole policy burns
   far more tokens than generating an SMS — **test consumption early**.
4. **Difficult policies.** If all three documents turn out to be scanned and illegible,
   workstream A becomes the bottleneck. That's why F0.2 comes before everything else.
5. **Four people instead of five.** With Juliana travelling, workstream E is split and the
   report has no single owner. The risk isn't the writing — it's nobody noticing that a
   section ended up without an author. The section table above exists for that; check it
   at the October 4 review, and **don't count on her return** for the delivery to happen.
