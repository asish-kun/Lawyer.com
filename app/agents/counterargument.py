"""
Agent 3 — Counterargument Predictor

ReAct agent that performs adversarial retrieval — searching for cases where
similar claims failed or the opposing side prevailed — then predicts the
strongest counterarguments and suggests preemptive responses.

Runs in parallel with Agent 2 (Weakness Analyzer).
"""

from typing import List

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import OPENAI_API_KEY, LLM_MODEL
from app.schemas import Counterargument
from app.prompts.counterargument import COUNTERARGUMENT_SYSTEM_PROMPT
from app.tools.vector_search import search_case_law


class CounterargumentResult(BaseModel):
    """Wrapper so the ReAct agent can return a list as structured output."""
    counterarguments: List[Counterargument] = Field(
        description="One Counterargument per claim analyzed"
    )


def _build_counterargument_agent():
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )
    return create_react_agent(
        llm,
        tools=[search_case_law],
        prompt=COUNTERARGUMENT_SYSTEM_PROMPT,
        response_format=CounterargumentResult,
    )


def _format_claims_for_agent(extraction):
    """Build the user message describing claims for adversarial analysis."""
    parts = ["Predict counterarguments for the following claims:\n"]

    jurisdiction = extraction.get("jurisdiction", "")
    case_type = extraction.get("case_type", "")
    if jurisdiction:
        parts.append("Jurisdiction: %s" % jurisdiction)
    if case_type:
        parts.append("Case type: %s" % case_type)
    parts.append("")

    for claim in extraction.get("claims", []):
        parts.append(
            "Claim %d: %s\n  Legal basis: %s\n  Supporting facts: %s"
            % (
                claim.get("claim_id", 0),
                claim.get("text", ""),
                claim.get("legal_basis", ""),
                "; ".join(claim.get("supporting_facts", [])),
            )
        )
    return "\n".join(parts)


def run_counterargument_predictor(state):
    """
    LangGraph node function for Agent 3.

    Reads state["extraction"], invokes the ReAct agent with adversarial
    search queries, writes state["counterarguments"] as a list of dicts.
    """
    extraction = state.get("extraction", {})
    claims = extraction.get("claims", [])
    if not claims:
        return {"counterarguments": []}

    agent = _build_counterargument_agent()
    user_msg = _format_claims_for_agent(extraction)

    result = agent.invoke({"messages": [("user", user_msg)]})

    structured = result.get("structured_response")
    if structured and isinstance(structured, CounterargumentResult):
        return {"counterarguments": [c.model_dump() for c in structured.counterarguments]}

    return {"counterarguments": []}
