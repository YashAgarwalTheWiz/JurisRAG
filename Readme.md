# ⚖️ JurisRAG — Indian Case Law Research Assistant

GraphRAG over Indian Supreme Court judgments — combines semantic search (Qdrant + Cohere embeddings, Cohere-reranked) with structured graph queries (Neo4j), routed by a LangGraph agent, served via FastAPI, with a Streamlit UI on top.

Built as a portfolio project to demonstrate multi-hop legal reasoning that neither pure vector search nor a pure knowledge graph can do alone — a query like *"which cases under the Income Tax Act discuss reasoning similar to property valuation disputes"* needs structured retrieval (the Act) **and** semantic retrieval (the similar-reasoning part) at once.

## Features

- **Hybrid retrieval, LLM-routed.** An LLM classifier reads the query and decides whether it needs vector search, graph search, or both — and for graph queries, which of five Cypher lookups applies (`by_section`, `by_judge`, `by_citation`, `by_act`, `by_case_id`). If a section number is given without an Act, it defaults to the Indian Penal Code rather than leaving the query unresolved.
- **Reranked semantic search.** Vector search over-fetches a wider candidate pool from Qdrant, then re-scores it with Cohere's `rerank-english-v3.0` before truncating to the final top‑k — noticeably better ordering than raw cosine similarity alone. Cohere calls are wrapped with retry/backoff so a transient 429 doesn't kill a run.
- **Balanced answer merging.** `generate_answer` reserves slots for both vector and graph results before deduping, so a precise graph hit (e.g. "Section 302 IPC") can't get crowded out by vector results when both sources return matches.
- **Normalized graph matching.** Judge names strip honorifics (`Justice`, `C.J.`, `Mr.`, etc.) before matching, and Act names match on a punctuation/case/hyphen-normalized `CONTAINS` rather than exact string — though word-order variants (e.g. "Criminal Procedure Code" vs "Code of Criminal Procedure") still need manual merging, see `cleanup_duplicates.py`.
- **Built-in observability.** Every agent node (`classify`, `vector_search`, `graph_search`, `generate`) is wrapped with a `log_node` decorator that records latency and result counts into a `debug_log`. This is returned by the API and rendered per-answer in an expandable "Debug info" panel in the Streamlit UI.
- **Resumable ingestion.** The ingestion pipeline checkpoints every successfully processed case ID to `processed_ids.txt`, so a crashed or rate-limited run can simply be restarted — already-processed cases are skipped.
- **Retrieval evaluation harness.** A hand-curated ground-truth question set drives an offline eval that computes Recall@5, Precision@5, and MRR separately for vector-only, graph-only, and hybrid-as-deployed retrieval against your live Neo4j + Qdrant data, and flags the weakest questions for follow-up.
- **Data-quality tooling.** Scripts to dump a human-skimmable overview of every ingested case (for writing eval ground truth), detect and merge duplicate Act-name variants in the graph, and inspect specific suspected-duplicate case pairs.

## Architecture

```
User query
    │
    ▼
classify_query  ──  LLM routes the query (vector / graph / both) + picks graph_query_type
    │                                   │
    ▼                                   ▼
vector_search (Qdrant + Cohere      graph_search (Neo4j, Cypher:
  embed + rerank)                     by_section / by_judge / by_citation /
    │                                  by_act / by_case_id)
    └─────────────────┬─────────────────┘
                       ▼
         generate_answer  ──  balances + dedupes sources, cites case IDs
```

Every node logs latency and result counts into `debug_log`, surfaced through the API and UI.

Ingestion side: HuggingFace dataset → LLM structured extraction (cited cases, Acts, Sections, Judges) → dual write into Neo4j (graph structure) and Qdrant (embeddings), checkpointed so a crashed or rate-limited run can resume.

## Tech stack

Neo4j (graph) · Qdrant Cloud (vectors) · Cohere `embed-english-v3.0` (embeddings) + `rerank-english-v3.0` (reranking) · Groq `llama-3.3-70b-versatile` (extraction + agent LLM) · LangGraph (orchestration) · FastAPI (backend) · Streamlit (frontend) · dataset: [`Exploration-Lab/IL-TUR`](https://huggingface.co/datasets/Exploration-Lab/IL-TUR) (`cjpe` config)

## Project structure

```
.
├── config.py                  # loads all secrets/URLs from .env
├── dataset.py                 # standalone — preview the HF dataset, no DB needed
├── requirements.txt
├── processed_ids.txt          # ingestion checkpoint — auto-generated, append-only
│
├── cleanup_duplicates.py      # standalone — Act-name dedup utility (destructive, review before running)
├── duplicate_case_check.py    # standalone — inspect a specific pair of suspected-duplicate case IDs (edit IDs before running)
├── eval_dump_cases.py         # standalone — dumps every ingested case to case_overview.md for skimming
├── eval_harness.py            # standalone — runs eval_questions.json through vector/graph/hybrid retrieval, reports Recall@5/Precision@5/MRR
├── eval_questions.json        # hand-written ground-truth questions (you maintain this)
├── eval_results.json          # auto-generated by eval_harness.py
├── case_overview.md           # auto-generated by eval_dump_cases.py
├── check_debug_log.py         # standalone — runs a few sample queries and pretty-prints their debug_log
│
├── graph/
│   └── schema.py               # standalone — creates Neo4j uniqueness constraints (run once)
├── ingestion/
│   ├── extract.py               # LLM structured extraction from case text
│   ├── neo4j_loader.py          # writes extracted structure into Neo4j
│   ├── qdrant_loader.py         # embeds + upserts case text into Qdrant
│   └── pipeline.py              # standalone — runs ingestion end-to-end, checkpointed
├── retrieval/
│   ├── cypher_retriever.py      # structured graph queries (5 lookup types)
│   └── vector_retriever.py      # semantic search against Qdrant + Cohere rerank
├── agent/
│   ├── graph_agent.py           # LangGraph agent: classify → (vector ∥ graph) → generate
│   └── observability.py         # log_node decorator — latency + result-count tracking
├── api/
│   └── main.py                  # standalone — FastAPI server
└── frontend/
    └── app.py                   # standalone — Streamlit UI
```

## Setup

```bash
git clone <your-repo-url>
cd JurisRAG
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
NEO4J_URL=
NEO4J_USERNAME=
NEO4J_PASSWORD=
QDRANT_URL=
QDRANT_API_KEY=
COLLECTION_NAME=
GROQ_API_KEY=
COHERE_API_KEY=
```

## Running it

Several files import other local modules with package-qualified imports (e.g. `from ingestion.extract import extract`, `from agent.graph_agent import graph`). Running them as a bare script path breaks that — always run from the project root using `-m`, not `python path/to/file.py`, **except** for the handful of files explicitly marked "run as `python file.py`" below, which sit at the project root and don't need module resolution.

### 1. One-time / per-run setup

| Step | Command | Notes |
|---|---|---|
| Preview dataset | `python dataset.py` | Optional sanity check — downloads and previews the HF dataset. No Neo4j/Qdrant connection needed. |
| Create graph schema | `python -m graph.schema` | One-time. Creates Neo4j uniqueness constraints. Run before ingesting anything. |
| Run ingestion | `python -m ingestion.pipeline` | The actual ingestion job. Extracts structure via LLM, writes to Neo4j + Qdrant, checkpoints progress to `processed_ids.txt`. Safe to stop and re-run — already-processed cases are skipped. |

### 2. Optional data-quality / eval scripts (run any time after ingestion)

| Step | Command | Notes |
|---|---|---|
| Generate case overview | `python eval_dump_cases.py` | Read-only, no LLM calls. Pulls every ingested case (judges, Acts, sections, citations, text snippet) into `case_overview.md` so you can skim what's actually in the graph before writing eval questions. |
| Dedup Act names | `python cleanup_duplicates.py` | **Destructive** — merges duplicate Act nodes in Neo4j. Review the merge list at the bottom of the file (canonical names + variants) before running; some merges are pre-filled, others are commented-out placeholders that need real variant strings from your own data. |
| Inspect duplicate cases | `python duplicate_case_check.py` | Edit the two hardcoded case IDs at the top of the file to the pair you want to compare, then run. Prints judges + a text snippet for each, side by side. |
| Run retrieval eval | `python eval_harness.py` | Needs `eval_questions.json` populated with real case IDs (use `case_overview.md` to write these). Runs each question through classify → vector/graph/hybrid, writes `eval_results.json`, and prints a Recall@5/Precision@5/MRR summary plus the weakest questions. Makes no writes to Neo4j/Qdrant; cheap (one small classification call per question, no answer generation). |
| Inspect agent debug log | `python check_debug_log.py` | Runs a few sample queries (hybrid, graph-only, vector-only) through the full agent and pretty-prints each node's `debug_log` — useful for sanity-checking latency and routing without going through the UI. |

### 3. Serving the app

| Step | Command | Notes |
|---|---|---|
| Start backend | `python -m uvicorn api.main:app --reload --port 8000` | From the project root. Exposes `POST /query` and `GET /health`. |
| Start frontend | `streamlit run frontend/app.py` | Separate terminal. Expects the backend running at `localhost:8000`. |

## Known limitations

- Act-name matching is fuzzy (normalized + `CONTAINS`) but doesn't catch word-order fragmentation (e.g. `"Criminal Procedure Code"` vs `"Code of Criminal Procedure"` are stored as separate Act nodes) — `cleanup_duplicates.py` needs the real variant strings filled in manually to merge these. Judge-name and section-key matching are still exact-string beyond the title-stripping already applied, so further fragmented extraction (e.g. `"Mahajan"` vs `"Mehr Chand Mahajan"`) can still cause silent under-retrieval.
- Retrieved context is capped at a fixed number of results per source (`MAX_PER_SOURCE = 4`) for prompt-size control; extra matches beyond the cap aren't surfaced to the user.
- Citation targets that were never themselves ingested exist in the graph as stub nodes (id only, no text) so the citation graph stays connected — they're filtered out at query time.
- `eval_harness.py` and `eval_dump_cases.py` reflect retrieval quality only against whatever's currently in `processed_ids.txt` (70 cases at last ingestion run, out of a `DATASET_LIMIT` of 360 in `pipeline.py`) — re-run ingestion further and regenerate `case_overview.md` before trusting eval numbers against a larger corpus.