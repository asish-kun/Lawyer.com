"""
Agent 1 — Extractor

Converts raw PDF text into a typed BriefExtraction via structured output.
No tools, no RAG — pure LLM extraction chain.

Used as the first node in the LangGraph DAG.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import OPENAI_API_KEY, LLM_MODEL
from app.schemas import BriefExtraction
from app.prompts.extractor import EXTRACTOR_SYSTEM_PROMPT


def build_extractor_chain():
    """Build the structured extraction chain (reusable)."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )
    return llm.with_structured_output(BriefExtraction)


def run_extractor(state):
    """
    LangGraph node function for Agent 1.

    Reads `state["pdf_text"]`, calls the structured extraction chain,
    writes the result to `state["extraction"]` as a dict.
    """
    pdf_text = state.get("pdf_text", "")
    if not pdf_text:
        return {"error": "No PDF text provided to extractor."}

    chain = build_extractor_chain()

    messages = [
        SystemMessage(content=EXTRACTOR_SYSTEM_PROMPT),
        HumanMessage(content="Extract structured information from this legal brief:\n\n" + pdf_text),
    ]

    extraction = chain.invoke(messages)
    return {"extraction": extraction.model_dump()}
