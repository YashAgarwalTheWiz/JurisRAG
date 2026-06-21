from neo4j import GraphDatabase
from config import NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD

driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

query = """
MATCH (c1:Case {id: '1947_378'}), (c2:Case {id: '2014_170'})
OPTIONAL MATCH (c1)-[:PRESIDED_BY]->(j1:Judge)
OPTIONAL MATCH (c2)-[:PRESIDED_BY]->(j2:Judge)
RETURN c1.text AS text1, collect(DISTINCT j1.name) AS judges1,
       c2.text AS text2, collect(DISTINCT j2.name) AS judges2
"""

with driver.session() as session:
    record = session.run(query).single()
    if record is None:
        print("One or both case IDs not found.")
    else:
        print("Judges 1947_378:", record["judges1"])
        print("Judges 2014_170:", record["judges2"])
        print()
        print("Text 1947_378 (first 500 chars):\n", (record["text1"] or "")[:500])
        print()
        print("Text 2014_170 (first 500 chars):\n", (record["text2"] or "")[:500])