import re
from collections import defaultdict
from neo4j import GraphDatabase
from config import NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD

driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

def normalize_act_key(name):
    cleaned = name.strip()
    cleaned = re.sub(r'^Indian\s+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+of\s+India$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', cleaned)
    return cleaned.lower()

with driver.session() as session:
    result = session.run("MATCH (a:Act) RETURN a.name AS name")
    names = [record["name"] for record in result]

groups = defaultdict(list)
for name in names:
    groups[normalize_act_key(name)].append(name)

for key, variants in groups.items():
    if len(variants) > 1:
        print(f"{key}: {variants}")

def merge_act_group(canonical_name, variant_names):
    with driver.session() as session:
        for variant in variant_names:
            if variant == canonical_name:
                continue
            session.run("""
                MATCH (s:Section)-[r:PART_OF]->(old:Act {name: $variant})
                MERGE (new:Act {name: $canonical})
                MERGE (s)-[:PART_OF]->(new)
                DELETE r
                WITH old
                WHERE NOT (old)--()
                DELETE old
            """, variant=variant, canonical=canonical_name)

merge_act_group("Constitution of India", ["Constitution"])
merge_act_group("Indian Income-tax Act", ["Income Tax Act", "Income-tax Act", "Indian Income Tax Act"])
merge_act_group("Indian Limitation Act", ["Limitation Act"])