from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.graph_agent import run_agent

app = FastAPI(title="JurisRAG API")

# CORS lets the Streamlit frontend (running on a different port) call this
# API from the browser. Without this, the browser blocks the request even
# though both are on localhost — different ports count as different origins.
# allow_origins=["*"] is fine for a local portfolio project; you'd lock this
# down to a specific domain in a real production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/response schemas — same Pydantic pattern as QueryClassification
# in graph_agent.py, but here it's defining the API's input/output contract
# instead of structuring an LLM call. FastAPI uses these to auto-validate
# incoming JSON and auto-generate the OpenAPI docs at /docs.
class QueryRequest(BaseModel):
    query: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


class QueryResponse(BaseModel):
    answer: str
    debug_log: list = []


@app.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    result = run_agent(request.query)
    return QueryResponse(answer=result["answer"], debug_log=result["debug_log"])


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)