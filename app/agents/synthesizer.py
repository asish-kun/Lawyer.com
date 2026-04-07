"""
Agent 4 — Synthesizer

Pure reasoning agent — no tools, no RAG. Reads the full accumulated state
(extraction, weaknesses, counterarguments) and produces a prioritized
StrategyReport via structured output.

Final node in the LangGraph DAG.
"""

import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import OPENAI_API_KEY, LLM_MODEL
from app.schemas import StrategyReport
from app.prompts.synthesizer import SYNTHESIZER_SYSTEM_PROMPT


def _build_synthesizer_chain():
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )
    return llm.with_structured_output(StrategyReport)


def _format_state_for_agent(extraction, weaknesses, counterarguments):
    """Assemble a single user message from all upstream agent outputs."""
    parts = []

    parts.append("=== EXTRACTED CLAIMS ===")
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
    parts.append("Jurisdiction: %s" % extraction.get("jurisdiction", ""))
    parts.append("Case type: %s" % extraction.get("case_type", ""))
    parts.append("Procedural posture: %s" % extraction.get("procedural_posture", ""))
    parts.append("Relief sought: %s" % extraction.get("relief_sought", ""))

    parts.append("\n=== WEAKNESS ANALYSIS ===")
    for w in weaknesses:
        parts.append(
            "Claim %d — weakness_score: %.2f\n  Reasoning: %s"
            % (w.get("claim_id", 0), w.get("weakness_score", 0.5), w.get("reasoning", ""))
        )
        for sc in w.get("supporting_cases", []):
            parts.append("  Supporting: %s (%s, %s) — %s" % (
                sc.get("title", ""), sc.get("court", ""), sc.get("date", ""), sc.get("relevance", "")
            ))
        for cc in w.get("contradicting_cases", []):
            parts.append("  Contradicting: %s (%s, %s) — %s" % (
                cc.get("title", ""), cc.get("court", ""), cc.get("date", ""), cc.get("relevance", "")
            ))

    parts.append("\n=== PREDICTED COUNTERARGUMENTS ===")
    for ca in counterarguments:
        parts.append(
            "Claim %d [%s]: %s\n  Suggested preemption: %s"
            % (
                ca.get("claim_id", 0),
                ca.get("severity", ""),
                ca.get("predicted_rebuttal", ""),
                ca.get("suggested_preemption", ""),
            )
        )
        for gc in ca.get("grounding_cases", []):
            parts.append("  Grounding case: %s (%s, %s) — %s" % (
                gc.get("title", ""), gc.get("court", ""), gc.get("date", ""), gc.get("relevance", "")
            ))

    return "\n".join(parts)


def run_synthesizer(state):
    """
    LangGraph node function for Agent 4.

    Reads state["extraction"], state["weaknesses"], state["counterarguments"].
    Produces a StrategyReport via structured output.
    Writes state["strategy"] as a serialized dict.
    """
    extraction = state.get("extraction", {})
    weaknesses = state.get("weaknesses", [])
    counterarguments = state.get("counterarguments", [])

    if not extraction.get("claims"):
        return {"strategy": {
            "overall_assessment": "weak",
            "actions": [],
            "key_risks": ["No claims were extracted from the brief."],
            "recommended_focus_areas": [],
        }}

    chain = _build_synthesizer_chain()
    user_msg = _format_state_for_agent(extraction, weaknesses, counterarguments)

    messages = [
        SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    strategy = chain.invoke(messages)
    return {"strategy": strategy.model_dump()}
