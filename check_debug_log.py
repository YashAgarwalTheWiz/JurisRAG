import json
from agent.graph_agent import graph

def run_and_show(query: str):
    result = graph.invoke({"query": query})
    print(f"\n=== {query} ===")
    print(json.dumps(result["debug_log"], indent=2))

# triggers BOTH branches — watch for duplicate classify_query entries here specifically
run_and_show("Cases about Andhra Pradesh local cadre recruitment disputes under Article 371-D")

# graph-only
run_and_show("Which cases did Justice Mehr Chand Mahajan preside over?")

# vector-only
run_and_show("Cases about preventive detention and habeas corpus petitions")