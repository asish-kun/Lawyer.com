"""
FastAPI layer for the Legal Brief Analyzer.

Endpoints:
    GET  /health          — readiness check
    POST /analyze         — synchronous analysis (returns full JSON)
    POST /analyze/stream  — SSE stream with per-agent progress events

Run:
    uvicorn app.api:app --reload
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from app.tools.pdf_parser import extract_text_from_bytes
from app.graph import build_graph

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="Legal Brief Analyzer",
    description="Upload a legal brief PDF and receive structured analysis with weakness scoring, counterarguments, and litigation strategy.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")

NODE_LABELS = {
    "extractor": "Extractor",
    "weakness_analyzer": "Weakness Analyzer",
    "counterargument_predictor": "Counterargument Predictor",
    "synthesizer": "Synthesizer",
    "error_node": "Error",
}


def _safe_result(state):
    """Strip pdf_text from response to keep payload small."""
    return {k: v for k, v in state.items() if k != "pdf_text"}


# ─────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    """Readiness check — verifies the vector store can be loaded."""
    try:
        from app.tools.vector_search import _get_store
        vs = _get_store()
        return {
            "status": "ok",
            "vectors": vs.count,
            "dimension": vs.dimension,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail="Vector store not ready: %s" % str(e))


# ─────────────────────────────────────────────
# POST /analyze  (synchronous)
# ─────────────────────────────────────────────

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Upload a legal brief PDF and receive the full analysis result.
    Runs the complete 4-agent DAG synchronously.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    try:
        text = extract_text_from_bytes(pdf_bytes, filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail="PDF parsing failed: %s" % str(e))

    if not text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the PDF.")

    graph = build_graph()
    result = await asyncio.to_thread(graph.invoke, {"pdf_text": text})

    if result.get("error"):
        return {"status": "error", "error": result["error"], "result": _safe_result(result)}

    return {"status": "ok", "result": _safe_result(result)}


# ─────────────────────────────────────────────
# POST /analyze/stream  (SSE)
# ─────────────────────────────────────────────

@app.post("/analyze/stream")
async def analyze_stream(file: UploadFile = File(...)):
    """
    Upload a legal brief PDF and receive SSE events as each agent starts/completes.

    Event types:
        agent_start    — an agent node has begun execution
        agent_complete — an agent node has finished
        final_result   — the full analysis result
        error          — something went wrong
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    try:
        text = extract_text_from_bytes(pdf_bytes, filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail="PDF parsing failed: %s" % str(e))

    if not text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the PDF.")

    async def event_generator():
        graph = build_graph()
        final_state = {}

        try:
            async for event in graph.astream_events(
                {"pdf_text": text},
                version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name in NODE_LABELS:
                    yield {
                        "event": "agent_start",
                        "data": json.dumps({
                            "agent": name,
                            "label": NODE_LABELS[name],
                        }),
                    }

                if kind == "on_chain_end" and name in NODE_LABELS:
                    output = event.get("data", {}).get("output", {})
                    summary = _summarize_node_output(name, output)
                    yield {
                        "event": "agent_complete",
                        "data": json.dumps({
                            "agent": name,
                            "label": NODE_LABELS[name],
                            **summary,
                        }),
                    }
                    final_state.update(output)

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
            return

        yield {
            "event": "final_result",
            "data": json.dumps(_safe_result(final_state)),
        }

    return EventSourceResponse(event_generator())


@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse(str(_FRONTEND_DIR / "index.html"))


def _summarize_node_output(node_name, output):
    """Extract a brief summary from a node's output for the SSE event."""
    if node_name == "extractor":
        ext = output.get("extraction", {})
        return {
            "claims_found": len(ext.get("claims", [])),
            "parties": len(ext.get("parties", [])),
            "dates": len(ext.get("key_dates", [])),
            "contacts": len(ext.get("contacts", [])),
        }
    if node_name == "weakness_analyzer":
        ws = output.get("weaknesses", [])
        return {
            "reports": len(ws),
            "avg_score": round(sum(w.get("weakness_score", 0) for w in ws) / max(len(ws), 1), 2),
        }
    if node_name == "counterargument_predictor":
        cas = output.get("counterarguments", [])
        severity_counts = {}
        for ca in cas:
            s = ca.get("severity", "unknown")
            severity_counts[s] = severity_counts.get(s, 0) + 1
        return {
            "counterarguments": len(cas),
            "severity_breakdown": severity_counts,
        }
    if node_name == "synthesizer":
        strat = output.get("strategy", {})
        return {
            "overall_assessment": strat.get("overall_assessment", ""),
            "actions": len(strat.get("actions", [])),
        }
    if node_name == "error_node":
        return {"error": output.get("error", "")}
    return {}
