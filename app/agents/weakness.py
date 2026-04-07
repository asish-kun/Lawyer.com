"""
Agent 2 — Weakness Analyzer

ReAct agent that searches the vector store for precedent relevant to each
extracted claim, then scores how well-supported or vulnerable each claim is.

Uses create_react_agent() with search_case_law tool and structured output.
"""

from typing import List

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import OPENAI_API_KEY, LLM_MODEL
from app.schemas import WeaknessReport
from app.prompts.weakness import WEAKNESS_SYSTEM_PROMPT
from app.tools.vector_search import search_case_law


class WeaknessAnalysisResult(BaseModel):
    """Wrapper so the ReAct agent can return a list of reports as structured output."""
    reports: List[WeaknessReport] = Field(
        description="One WeaknessReport per claim analyzed"
    )


def _build_weakness_agent():
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )
    return create_react_agent(
        llm,
        tools=[search_case_law],
        prompt=WEAKNESS_SYSTEM_PROMPT,
        response_format=WeaknessAnalysisResult,
    )


def _format_claims_for_agent(extraction):
    """Build the user message describing claims to analyze."""
    parts = ["Analyze the following claims from a legal brief:\n"]

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


def run_weakness_analyzer(state):
    """
    LangGraph node function for Agent 2.

    Reads state["extraction"], invokes the ReAct agent with search_case_law,
    writes state["weaknesses"] as a list of dicts.
    """
    extraction = state.get("extraction", {})
    claims = extraction.get("claims", [])
    if not claims:
        return {"weaknesses": []}

    agent = _build_weakness_agent()
    user_msg = _format_claims_for_agent(extraction)

    result = agent.invoke({"messages": [("user", user_msg)]})

    structured = result.get("structured_response")
    if structured and isinstance(structured, WeaknessAnalysisResult):
        return {"weaknesses": [r.model_dump() for r in structured.reports]}

    return {"weaknesses": []}
