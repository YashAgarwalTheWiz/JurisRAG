"""
Standalone, read-only. Run as: python eval_dump_cases.py

Pulls every ingested Case from Neo4j along with its judges, acts, sections,
and outgoing citations, plus a text snippet. Writes case_overview.md so you
can skim your 70 cases in a few minutes and write real ground-truth questions
for eval_harness.py — instead of re-reading full judgments to remember what's
in there.

Does not touch Qdrant or Cohere, and makes no LLM calls. Safe to run as often
as you want.
"""

from neo4j import GraphDatabase
from config import NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD

driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

SNIPPET_CHARS = 280
OUTPUT_FILE = "case_overview.md"

QUERY = """
MATCH (c:Case)
WHERE c.text IS NOT NULL
OPTIONAL MATCH (c)-[:PRESIDED_BY]->(j:Judge)
OPTIONAL MATCH (c)-[:INVOKES]->(s:Section)-[:PART_OF]->(a:Act)
OPTIONAL MATCH (c)-[:CITES]->(cited:Case)
RETURN
    c.id AS case_id,
    c.text AS text,
    c.label AS label,
    collect(DISTINCT j.name) AS judges,
    collect(DISTINCT a.name) AS acts,
    collect(DISTINCT s.number) AS sections,
    collect(DISTINCT cited.id) AS cites
ORDER BY case_id
"""


def fetch_cases():
    with driver.session() as session:
        result = session.run(QUERY)
        return [dict(record) for record in result]


def clean_list(items):
    # OPTIONAL MATCH with no match yields a list containing one null
    return sorted(x for x in items if x)


def render_markdown(cases):
    lines = [
        "# Case overview",
        "",
        f"{len(cases)} cases with text ingested. Use this to write ground-truth "
        f"questions for eval_harness.py — for each question you write, note "
        f"which case_id(s) below are actually relevant.",
        "",
    ]
    for c in cases:
        judges = clean_list(c["judges"])
        acts = clean_list(c["acts"])
        sections = clean_list(c["sections"])
        cites = clean_list(c["cites"])
        snippet = (c["text"] or "")[:SNIPPET_CHARS].replace("\n", " ").strip()

        lines.append(f"## {c['case_id']}")
        lines.append(f"- **label:** {c['label']}")
        lines.append(f"- **judges:** {', '.join(judges) or '—'}")
        lines.append(f"- **acts:** {', '.join(acts) or '—'}")
        lines.append(f"- **sections:** {', '.join(sections) or '—'}")
        lines.append(f"- **cites:** {', '.join(cites) or '—'}")
        lines.append(f"- **snippet:** {snippet}…")
        lines.append("")
    return "\n".join(lines)


def main():
    cases = fetch_cases()
    if not cases:
        print("No cases with text found. Did ingestion actually run?")
        return

    markdown = render_markdown(cases)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(markdown)

    # Quick stats to console too — useful for the "be honest about scale" README section
    all_judges = set()
    all_acts = set()
    total_citations = 0
    for c in cases:
        all_judges.update(clean_list(c["judges"]))
        all_acts.update(clean_list(c["acts"]))
        total_citations += len(clean_list(c["cites"]))

    print(f"Wrote {OUTPUT_FILE} with {len(cases)} cases.")
    print(f"  Distinct judges: {len(all_judges)}")
    print(f"  Distinct acts:   {len(all_acts)}")
    print(f"  Outgoing CITES edges (from these {len(cases)} cases): {total_citations}")


if __name__ == "__main__":
    main()