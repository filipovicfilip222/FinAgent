"""FastAPI wrapper exposing the agent as a service.

    uvicorn finagent.api:app --reload
    curl -s localhost:8000/query -H 'content-type: application/json' \
         -d '{"query":"What was Apple revenue in FY2025?"}' | jq

Not built for production load — it's a clean interface so a frontend or the eval
harness can call the agent over HTTP. The graph (and LLM provider) is created lazily on
the first request so the module imports without any API key (handy for CI).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from .graph import build_graph, run_query
from .schemas import FinalAnswer

app = FastAPI(title="FinAgent", version="0.1.0")


class QueryRequest(BaseModel):
    query: str
    max_iterations: int = 6


class QueryResponse(BaseModel):
    query: str
    answer: FinalAnswer
    tools_used: list[str]
    iterations: int
    reflection_notes: list[str]


@lru_cache(maxsize=1)
def _graph():
    return build_graph()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "finagent"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    state = run_query(req.query, max_iterations=req.max_iterations, graph=_graph())
    return QueryResponse(
        query=req.query,
        answer=state.final_answer,
        tools_used=state.tools_used,
        iterations=state.iteration,
        reflection_notes=state.reflection_notes,
    )
