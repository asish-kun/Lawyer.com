"""
LangGraph DAG definition for the Legal Brief Analyzer.

Graph topology:
  START -> extractor -> [conditional] -> weakness   \
                                      -> counter    -> synthesizer -> END
                        [no claims]   -> error_node -> END

Fan-out: Agent 2 (Weakness) and Agent 3 (Counterargument) run in parallel.
Fan-in:  Agent 4 (Synthesizer) waits for both to complete before executing.
"""

from langgraph.graph import StateGraph, START, END

from app.state import AgentState
from app.agents.extractor import run_extractor
from app.agents.weakness import run_weakness_analyzer
from app.agents.counterargument import run_counterargument_predictor
from app.agents.synthesizer import run_synthesizer


def _route_after_extraction(state):
    """
    Conditional edge after Agent 1.
    If claims were extracted, fan out to weakness + counterargument in parallel.
    Otherwise, route to the error node.
    """
    if state.get("error"):
        return "error_node"

    extraction = state.get("extraction")
    if not extraction:
        return "error_node"

    claims = extraction.get("claims", [])
    if not claims:
        return "error_node"

    return ["weakness_analyzer", "counterargument_predictor"]


def _error_node(state):
    """Terminal node for unrecoverable errors (no PDF text, no claims found)."""
    existing_error = state.get("error", "")
    if not existing_error:
        return {"error": "No claims could be extracted from the brief."}
    return {}


def build_graph():
    """
    Construct and compile the analysis DAG.
    Returns a compiled LangGraph runnable.
    """
    graph = StateGraph(AgentState)

    graph.add_node("extractor", run_extractor)
    graph.add_node("weakness_analyzer", run_weakness_analyzer)
    graph.add_node("counterargument_predictor", run_counterargument_predictor)
    graph.add_node("synthesizer", run_synthesizer)
    graph.add_node("error_node", _error_node)

    graph.add_edge(START, "extractor")

    graph.add_conditional_edges(
        "extractor",
        _route_after_extraction,
        ["weakness_analyzer", "counterargument_predictor", "error_node"],
    )

    graph.add_edge("weakness_analyzer", "synthesizer")
    graph.add_edge("counterargument_predictor", "synthesizer")

    graph.add_edge("synthesizer", END)
    graph.add_edge("error_node", END)

    return graph.compile()


# Singleton — import this from other modules
app_graph = build_graph()
