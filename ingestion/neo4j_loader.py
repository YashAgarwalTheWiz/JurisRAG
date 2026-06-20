from neo4j import GraphDatabase
from config import NEO4J_URL,NEO4J_USERNAME,NEO4J_PASSWORD
from ingestion.extract import CaseExtraction

driver=GraphDatabase.driver(NEO4J_URL,auth=(NEO4J_USERNAME,NEO4J_PASSWORD))

def load_case(case_id, text, label, extraction: CaseExtraction):
    with driver.session() as session:
        session.run(
            "MERGE (c:Case {id: $id}) SET c.text = $text, c.label = $label",
            id=case_id, text=text, label=label
        )
        for cited_id in extraction.cited_cases:
            session.run(
                """
                MATCH (c:Case {id: $case_id})
                MERGE (cited:Case {id: $cited_id})
                MERGE (c)-[:CITES]->(cited)
                """,
                case_id=case_id, cited_id=cited_id
            )
        for act_name in extraction.acts:
            session.run(
                "MERGE (:Act {name: $name})",
                name=act_name
            )

        for section in extraction.sections:
            section_key = f"{section.act_name.replace(' ', '')}_Section{section.number}"
            session.run(
                """
                MATCH (c:Case {id: $case_id})
                MERGE (a:Act {name: $act_name})
                MERGE (s:Section {section_key: $section_key})
                  SET s.number = $number, s.act_name = $act_name
                MERGE (s)-[:PART_OF]->(a)
                MERGE (c)-[:INVOKES]->(s)
                """,
                case_id=case_id,
                act_name=section.act_name,
                section_key=section_key,
                number=section.number
            )
        for judge_name in extraction.judges:
            session.run(
                """
                MATCH (c:Case {id: $case_id})
                MERGE (j:Judge {name: $name})
                MERGE (c)-[:PRESIDED_BY]->(j)
                """,
                case_id=case_id, name=judge_name
            )