# JurisRAG

GraphRAG over Indian Supreme Court judgments — combines a Neo4j knowledge graph (citations, statutes, judges) with semantic search (Qdrant + Cohere embeddings), routed by a LangGraph agent, served via FastAPI, with a Streamlit UI on top.

Built as a portfolio project to demonstrate multi-hop legal reasoning that neither pure vector search nor a pure knowledge graph can do alone — a query like *"which cases under the Income Tax Act discuss reasoning similar to property valuation disputes"* needs structured retrieval (the Act) **and** semantic retrieval (the similar-reasoning part) at once.

## Architecture

```
User query
    │
    ▼
classify_query  ──  LLM routes the query (vector / graph / both)
    │                                   │
    ▼                                   ▼
vector_search (Qdrant)          graph_search (Neo4j, Cypher)
    │                                   │
    └─────────────────┬─────────────────┘
                       ▼
         generate_answer  ──  merges, dedupes, cites sources
```

Ingestion side: HuggingFace dataset → LLM structured extraction → dual write into Neo4j (graph structure) and Qdrant (embeddings), checkpointed so a crashed or rate-limited run can resume.

## Tech stack

Neo4j (graph) · Qdrant Cloud (vectors) · Cohere `embed-english-v3.0` (embeddings) · Groq `llama-3.3-70b-versatile` (extraction + agent LLM) · LangGraph (orchestration) · FastAPI (backend) · Streamlit (frontend) · dataset: [`Exploration-Lab/IL-TUR`](https://huggingface.co/datasets/Exploration-Lab/IL-TUR) (`cjpe` config)

## Project structure

```
.
├── config.py                # loads all secrets/URLs from .env
├── dataset.py                # standalone — preview the HF dataset, no DB needed
├── cleanup_duplicates.py    # standalone — one-off Act-name dedup utility (destructive, read before running)
├── requirements.txt
├── graph/
│   └── schema.py             # standalone — creates Neo4j uniqueness constraints (run once)
├── ingestion/
│   ├── extract.py            # LLM structured extraction from case text
│   ├── neo4j_loader.py       # writes extracted structure into Neo4j
│   ├── qdrant_loader.py      # embeds + upserts case text into Qdrant
│   └── pipeline.py           # standalone — runs ingestion end-to-end, checkpointed
├── retrieval/
│   ├── cypher_retriever.py   # structured graph queries
│   └── vector_retriever.py   # semantic search against Qdrant
├── agent/
│   └── graph_agent.py        # LangGraph agent: classify → (vector ∥ graph) → generate
├── api/
│   └── main.py                # standalone — FastAPI server
└── frontend/
    └── app.py                 # standalone — Streamlit UI
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

A couple of these files import other local modules with package-qualified imports (e.g. `from ingestion.extract import extract`). Running them as a bare script path breaks that — always run from the project root using `-m`, not `python path/to/file.py`.

Run in this order:

1. **`python dataset.py`** — optional sanity check, just downloads and previews the dataset. No Neo4j/Qdrant connection required.
2. **`python -m graph.schema`** — one-time setup, creates the Neo4j uniqueness constraints. Run before ingesting anything.
3. **`python -m ingestion.pipeline`** — the actual ingestion job. Extracts structure via LLM, writes to Neo4j + Qdrant, checkpoints progress to `processed_ids.txt`. Safe to stop and re-run — already-processed cases are skipped.
4. **`python cleanup_duplicates.py`** — optional, situational. A one-off data-quality utility that detects and merges duplicate Act-name variants (e.g. `"Income Tax Act"` vs `"Indian Income-tax Act"`) created by inconsistent LLM extraction. It's destructive (deletes graph nodes) and the merge targets at the bottom are specific to this project's data — review and adjust before running it again on a different ingestion run.
5. **`python -m uvicorn api.main:app --reload --port 8000`** — start the backend, from the project root.
6. **`streamlit run frontend/app.py`** — start the UI in a separate terminal. Expects the backend running at `localhost:8000`.

## Known limitations

- Act-name matching is fuzzy (normalized + `CONTAINS`) but judge-name and section-key matching are still exact-string — fragmented LLM extraction (e.g. `"Mahajan"` vs `"Mehr Chand Mahajan"`) can still cause silent under-retrieval there.
- Retrieved context is capped at a fixed number of results per source for prompt-size control; extra matches beyond the cap aren't surfaced to the user.
- Citation targets that were never themselves ingested exist in the graph as stub nodes (id only, no text) so the citation graph stays connected — they're filtered out at query time.