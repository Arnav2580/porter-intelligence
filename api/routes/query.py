"""Query endpoint for natural language ops queries."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    query: str
    context: Optional[str] = None


class QueryResponse(BaseModel):
    query:       str
    answer:      str
    source:      str
    response_ms: int


@router.post("/query", response_model=QueryResponse)
async def natural_language_query(request: QueryRequest):
    """
    Answer natural language questions about fraud, cases, and operations data.

    Examples:
      "Show me fraud rings in Bangalore"
      "Which drivers have highest risk?"
      "What zones have most fraud?"
      "Give me the KPI summary"

    Structured queries are resolved from local data artifacts first.
    Unstructured questions fall back to the local language model when available.
    """
    from api.state import app_state
    from model.query import answer_query

    trips_df   = app_state.get("trips_df")
    drivers_df = app_state.get("drivers_df")
    context    = app_state.get("query_context", {})

    result = answer_query(
        request.query,
        trips_df,
        drivers_df,
        preloaded_context=context,
    )

    return QueryResponse(**result)
