from typing import TypedDict, Optional, List, Dict, Any
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from config import GROQ_API_KEY
from retrieval.vector_retriever import vector_search
from retrieval.cypher_retriever import (
    get_cases_by_section,
    get_cases_by_judge,
    get_cited_cases,
    get_cases_by_act,
    get_case_by_id,
)

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)


class QueryClassification(BaseModel):
    needs_vector: bool
    needs_graph: bool
    graph_query_type: str  # "by_section" | "by_judge" | "by_citation" | "by_act" | "by_case_id" | "none"
    section_number: Optional[str] = None
    act_name: Optional[str] = None
    judge_name: Optional[str] = None
    case_id: Optional[str] = None


structured_llm = llm.with_structured_output(QueryClassification)


class AgentState(TypedDict):
    query: str
    classification: QueryClassification
    vector_results: List[Dict[str, Any]]
    graph_results: List[Dict[str, Any]]
    answer: str


def classify_query(state: AgentState) -> dict:
    prompt = f"""
    You are a routing system for a legal research assistant. Given a query,
    decide what kind of retrieval it needs.

    - needs_vector: true if the query is about meaning/topic/similarity
      (e.g. "cases about bail in economic offences")
    - needs_graph: true if the query references a specific section, act,
      judge, citation relationship, or a specific case by its own ID
    - graph_query_type: if needs_graph is true, pick exactly one:
      "by_section", "by_judge", "by_citation", "by_act", "by_case_id", or "none"
      - Use "by_case_id" when the query asks about one specific case
        directly by its ID (e.g. "what happened in case 1952_93",
        "summarize case 2019_890") — this looks up that case itself,
        not cases it cites.
      - Use "by_citation" only when asking what OTHER cases a given
        case cites, not what happened in the case itself.
    - Fill in only the parameter fields relevant to the graph_query_type
      you picked. Leave the rest null.
    - If a section number is given but the act isn't named, default
      act_name to "Indian Penal Code" — it's the overwhelmingly common
      statute in this context. Only leave act_name null if the query
      genuinely gives no basis to guess (e.g. asking about sections
      across multiple unspecified acts).

    Query: {state['query']}
    """
    classification = structured_llm.invoke(prompt)
    print(f"[DEBUG] classification: {classification}")
    return {"classification": classification}


def run_vector_search(state: AgentState) -> dict:
    if not state["classification"].needs_vector:
        return {"vector_results": []}
    results = vector_search(state["query"])
    print(f"[DEBUG] vector_results count: {len(results)}")
    return {"vector_results": results}


def run_graph_search(state: AgentState) -> dict:
    c = state["classification"]
    if not c.needs_graph:
        print("[DEBUG] graph search skipped — needs_graph=False")
        return {"graph_results": []}

    if c.graph_query_type == "by_section":
        results = get_cases_by_section(c.section_number, c.act_name)
    elif c.graph_query_type == "by_judge":
        results = get_cases_by_judge(c.judge_name)
    elif c.graph_query_type == "by_citation":
        results = get_cited_cases(c.case_id)
    elif c.graph_query_type == "by_act":
        results = get_cases_by_act(c.act_name)
    elif c.graph_query_type == "by_case_id":
        results = get_case_by_id(c.case_id)
    else:
        results = []

    print(f"[DEBUG] graph_query_type={c.graph_query_type} -> {len(results)} results")
    return {"graph_results": results}


def generate_answer(state: AgentState) -> dict:
    vector_results = state.get("vector_results", [])
    graph_results = state.get("graph_results", [])

    # Reserve slots for both sources up front. Without this, vector results
    # being listed first could crowd out every graph result whenever both
    # sources return hits — even when graph results are the precise match
    # for a structured query like "Section 302 IPC".
    MAX_PER_SOURCE = 4
    balanced = vector_results[:MAX_PER_SOURCE] + graph_results[:MAX_PER_SOURCE]

    seen = set()
    unique_cases = []
    for case in balanced:
        if case["case_id"] not in seen:
            seen.add(case["case_id"])
            unique_cases.append(case)

    MAX_CHARS_PER_CASE = 1500

    context = "\n\n".join(
        f"Case {c['case_id']}: {c['text'][:MAX_CHARS_PER_CASE]}"
        for c in unique_cases
        if c.get('text')
    )

    prompt = f"""
    Answer the following legal query using only the case information below.
    Cite case IDs in your answer. If the cases don't contain enough
    information to answer, say so explicitly.

    Query: {state['query']}

    Retrieved cases:
    {context}
    """
    response = llm.invoke(prompt)
    return {"answer": response.content}


builder = StateGraph(AgentState)
builder.add_node("classify", classify_query)
builder.add_node("vector_search", run_vector_search)
builder.add_node("graph_search", run_graph_search)
builder.add_node("generate", generate_answer)

builder.set_entry_point("classify")
builder.add_edge("classify", "vector_search")
builder.add_edge("classify", "graph_search")
builder.add_edge("vector_search", "generate")
builder.add_edge("graph_search", "generate")
builder.add_edge("generate", END)

graph = builder.compile()


def run_agent(query: str) -> str:
    result = graph.invoke({"query": query})
    return result["answer"]