"""
Standalone, read-mostly. Run as: python eval_harness.py

Retrieval evaluation harness. Loads hand-written ground-truth questions from
eval_questions.json, runs three retrieval modes against your live Neo4j +
Qdrant (vector-only, graph-only, hybrid-as-deployed), and reports Recall@5,
Precision@5, and MRR for each.

Cost note: this calls classify_query() once per question — a small LLM call
on just the query text, not a full judgment, so it's cheap relative to
ingestion. It never calls generate_answer(), so no answer-generation tokens
are spent. Makes no writes to Neo4j or Qdrant.

Place this file at the project root (same level as config.py) and create
eval_questions.json (copy eval_questions.template.json and fill in real
case IDs from case_overview.md) before running.
"""

import json
import statistics
import sys

from agent.graph_agent import classify_query, run_graph_search
from retrieval.vector_retriever import vector_search

QUESTIONS_FILE = "eval_questions.json"
RESULTS_FILE = "eval_results.json"
VECTOR_TOP_K = 10
MAX_PER_SOURCE = 4  # mirrors generate_answer()'s balancing in agent/graph_agent.py


def load_questions(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            questions = json.load(f)
    except FileNotFoundError:
        print(f"Couldn't find {path}.")
        print("Copy eval_questions.template.json to eval_questions.json and fill in real case IDs first.")
        sys.exit(1)

    for q in questions:
        if not q.get("relevant_case_ids"):
            print(f"  WARNING: '{q.get('id', '?')}' has no relevant_case_ids — it will be skipped in metrics")
    return questions


def recall_at_k(retrieved, relevant, k):
    if not relevant:
        return None
    top_k = retrieved[:k]
    return len(set(top_k) & set(relevant)) / len(relevant)


def precision_at_k(retrieved, relevant, k):
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return len(set(top_k) & set(relevant)) / len(top_k)


def reciprocal_rank(retrieved, relevant):
    for i, cid in enumerate(retrieved, start=1):
        if cid in relevant:
            return 1.0 / i
    return 0.0


def dedup_ids(ids):
    seen = set()
    out = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def run_one(question):
    query = question["query"]
    relevant = set(question.get("relevant_case_ids", []))

    classification = classify_query({"query": query})["classification"]

    # Vector arm: always run, regardless of how the classifier routed this
    # query — gives a true vector-only baseline to compare against, not just
    # "vector when the classifier happened to allow it."
    vector_hits = vector_search(query, top_k=VECTOR_TOP_K)
    vector_ids = [h["case_id"] for h in vector_hits]

    # Graph arm: only runs if the classifier actually decided this needs
    # graph retrieval. Intentional — a routing miss should show up here as
    # zero graph results, since that's a real failure mode worth seeing.
    if classification.needs_graph and classification.graph_query_type != "none":
        graph_hits = run_graph_search({"classification": classification})["graph_results"]
    else:
        graph_hits = []
    graph_ids = [h["case_id"] for h in graph_hits]

    # Hybrid arm: mirrors generate_answer()'s merge logic exactly (top
    # MAX_PER_SOURCE from each source, deduped) so this number reflects what
    # the deployed agent actually shows the LLM today.
    hybrid_ids = dedup_ids(vector_ids[:MAX_PER_SOURCE] + graph_ids[:MAX_PER_SOURCE])

    return {
        "id": question["id"],
        "query": query,
        "relevant_case_ids": sorted(relevant),
        "classification": {
            "needs_vector": classification.needs_vector,
            "needs_graph": classification.needs_graph,
            "graph_query_type": classification.graph_query_type,
            "section_number": classification.section_number,
            "act_name": classification.act_name,
            "judge_name": classification.judge_name,
            "case_id": classification.case_id,
        },
        "vector_ids": vector_ids,
        "graph_ids": graph_ids,
        "hybrid_ids": hybrid_ids,
        "metrics": {
            "vector": {
                "recall@5": recall_at_k(vector_ids, relevant, 5),
                "precision@5": precision_at_k(vector_ids, relevant, 5),
                "mrr": reciprocal_rank(vector_ids, relevant),
            },
            "graph": {
                "recall@5": recall_at_k(graph_ids, relevant, 5),
                "precision@5": precision_at_k(graph_ids, relevant, 5),
                "mrr": reciprocal_rank(graph_ids, relevant),
            },
            "hybrid": {
                "recall@5": recall_at_k(hybrid_ids, relevant, 5),
                "precision@5": precision_at_k(hybrid_ids, relevant, 5),
                "mrr": reciprocal_rank(hybrid_ids, relevant),
            },
        },
    }


def summarize(results):
    arms = ["vector", "graph", "hybrid"]
    metrics = ["recall@5", "precision@5", "mrr"]
    summary = {}
    for arm in arms:
        summary[arm] = {}
        for metric in metrics:
            values = [
                r["metrics"][arm][metric]
                for r in results
                if r["metrics"][arm][metric] is not None
            ]
            summary[arm][metric] = round(statistics.mean(values), 3) if values else None
    return summary


def main():
    questions = load_questions(QUESTIONS_FILE)
    if not questions:
        print(f"No questions found in {QUESTIONS_FILE}.")
        sys.exit(1)

    print(f"Running {len(questions)} questions through classify -> vector/graph/hybrid...\n")

    results = []
    for q in questions:
        print(f"  [{q['id']}] {q['query']}")
        try:
            results.append(run_one(q))
        except Exception as e:
            print(f"    FAILED: {e}")

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    summary = summarize(results)
    print("\n=== Summary (mean across questions with ground truth) ===")
    try:
        import pandas as pd
        print(pd.DataFrame(summary).T.to_string())
    except ImportError:
        for arm, vals in summary.items():
            print(f"  {arm}: {vals}")

    print("\n=== Questions where hybrid recall@5 < 1.0 (look here first) ===")
    for r in results:
        h = r["metrics"]["hybrid"]["recall@5"]
        if h is not None and h < 1.0:
            c = r["classification"]
            print(
                f"  [{r['id']}] recall@5={h:.2f}  "
                f"needs_vector={c['needs_vector']} needs_graph={c['needs_graph']} "
                f"type={c['graph_query_type']}"
            )

    print(f"\nFull per-question breakdown (incl. routing decisions) written to {RESULTS_FILE}")


if __name__ == "__main__":
    main()