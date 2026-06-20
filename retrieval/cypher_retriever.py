from neo4j import GraphDatabase
from config import NEO4J_URL,NEO4J_USERNAME,NEO4J_PASSWORD

driver=GraphDatabase.driver(NEO4J_URL,auth=(NEO4J_USERNAME,NEO4J_PASSWORD))

def get_cases_by_section(section_number, act_name=None):
    if act_name:
        section_key = f"{act_name.replace(' ', '')}_Section{section_number}"
        query = """
        MATCH (c:Case)-[:INVOKES]->(s:Section)
        WHERE s.section_key = $section_key
        RETURN c.id AS case_id, c.text AS text
        """
        params = {"section_key": section_key}
    else:
        query = """
        MATCH (c:Case)-[:INVOKES]->(s:Section)
        WHERE s.number = $section_number
        RETURN c.id AS case_id, c.text AS text
        """
        params = {"section_number": str(section_number)}

    with driver.session() as session:
        result = session.run(query, **params)
        return [{"case_id": record["case_id"], "text": record["text"]} for record in result]
    
def get_cases_by_judge(judge_name):
    query='''
        MATCH (c:Case)-[:PRESIDED_BY]->(j:Judge)
    WHERE j.name = $judge_name
    RETURN c.id AS case_id, c.text AS text
    '''
    with driver.session() as session:
        result=session.run(query,judge_name=judge_name)
        return [{'case_id':record['case_id'],'text':record['text']} for record in result]
    
def get_cited_cases(case_id):
    query = """
    MATCH (c:Case {id: $case_id})-[:CITES]->(cited:Case)
    WHERE cited.text IS NOT NULL
    RETURN cited.id AS case_id, cited.text AS text
    """
    with driver.session() as session:
        result = session.run(query, case_id=case_id)
        return [{"case_id": record["case_id"], "text": record["text"]} for record in result]
    
def get_cases_by_act(act_name):
    query = """
    MATCH (c:Case)-[:INVOKES]->(s:Section)-[:PART_OF]->(a:Act)
    WHERE replace(replace(toLower(a.name), '-', ''), ' ', '')
          CONTAINS replace(replace(toLower($act_name), '-', ''), ' ', '')
    RETURN DISTINCT c.id AS case_id, c.text AS text
    """
    with driver.session() as session:
        result = session.run(query, act_name=act_name)
        return [{"case_id": record["case_id"], "text": record["text"]} for record in result]
    
def get_case_by_id(case_id):
    query = """
    MATCH (c:Case {id: $case_id})
    WHERE c.text IS NOT NULL
    RETURN c.id AS case_id, c.text AS text
    """
    with driver.session() as session:
        result = session.run(query, case_id=case_id)
        return [{"case_id": record["case_id"], "text": record["text"]} for record in result]