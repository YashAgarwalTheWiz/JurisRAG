from neo4j import GraphDatabase
from config import NEO4J_URL,NEO4J_USERNAME,NEO4J_PASSWORD

driver=GraphDatabase.driver(NEO4J_URL,auth=(NEO4J_USERNAME,NEO4J_PASSWORD))

constraints=[
    'CREATE CONSTRAINT case_id_unique IF NOT EXISTS FOR (n:Case) REQUIRE n.id IS UNIQUE',
    'CREATE CONSTRAINT act_name_unique IF NOT EXISTS FOR (n:Act) REQUIRE n.name IS UNIQUE',
    'CREATE CONSTRAINT section_key_unique IF NOT EXISTS FOR (n:Section) REQUIRE n.section_key IS UNIQUE',
    'CREATE CONSTRAINT judge_name_unique IF NOT EXISTS FOR (n:Judge) REQUIRE n.name IS UNIQUE'
]

with driver.session() as session:
    for constraint in constraints:
        session.run(constraint)