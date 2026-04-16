# BriefAI — Legal Brief Analyzer

Upload a legal brief PDF and get a full litigation analysis in minutes. A 4-agent AI pipeline extracts claims, scores weaknesses against real case law, predicts counterarguments, and builds a prioritized strategy.

**Live demo:** [brief-ai-one.vercel.app](https://brief-ai-one.vercel.app)

---

## Quick Start

### Prerequisites

- Python 3.9+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone and install

```bash
git clone https://github.com/asish-kun/Lawyer.com.git
cd Lawyer.com
pip install -r requirements.txt
```

### 2. Add your API key

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your real key:

```
MODEL_NAME_OPENAI=gpt-4o-mini
OpenAI_API_KEY=sk-proj-your-actual-key-here
```

### 3. Run the server

```bash
python3 -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000** in your browser. Upload a PDF and go.

---

## How It Works

The system runs a LangGraph directed acyclic graph with four agents:

```
PDF Upload
    │
    ▼
┌──────────┐
│ Extractor │  → Parses claims, parties, dates, contacts, action flags
└────┬─────┘
     │
     ├──────────────────────┐
     ▼                      ▼
┌──────────────┐   ┌────────────────────┐
│  Weakness    │   │  Counterargument   │   ← Run in parallel
│  Analyzer    │   │  Predictor         │   ← Both use RAG search
└──────┬───────┘   └────────┬───────────┘
       │                    │
       └────────┬───────────┘
                ▼
         ┌──────────────┐
         │  Synthesizer  │  → Prioritized litigation strategy
         └──────────────┘
```

- **Extractor** — Structured extraction using GPT-4o-mini with Pydantic output contracts
- **Weakness Analyzer** — ReAct agent that searches ~8,000 case law embeddings to score each claim
- **Counterargument Predictor** — Runs adversarial searches to find where similar arguments have failed
- **Synthesizer** — Merges all findings into a ranked strategy with confidence scores

The frontend streams results in real time via Server-Sent Events as each agent completes.

---

## Project Structure

```
├── app/
│   ├── api.py              # FastAPI endpoints (REST + SSE streaming)
│   ├── graph.py             # LangGraph DAG definition
│   ├── schemas.py           # Pydantic data contracts between agents
│   ├── agents/              # Agent node functions
│   ├── prompts/             # System prompts for each agent
│   └── tools/               # PDF parser, vector search tool
├── frontend/
│   ├── index.html           # UI
│   ├── styles.css           # Light/dark theme with gold accent
│   ├── app.js               # Frontend logic, Chart.js, SSE handling
│   └── config.js            # API base URL (for split deployments)
├── data_collection/         # Scripts to collect and embed case law
├── vectorstore/             # Pre-built embeddings (~8K cases)
├── requirements.txt         # Runtime dependencies
└── Procfile                 # Railway deployment config
```

---

## CLI Usage

You can also run analysis from the command line:

```bash
python3 -m app.run path/to/brief.pdf
```

---

## Rebuilding the Vector Store

The repo includes a pre-built vector store. To rebuild it from scratch with fresh case law data:

```bash
pip install -r requirements-collection.txt
python3 -m data_collection.main
```

This collects cases from Harvard Caselaw Access Project, CourtListener, and SEC EDGAR, then chunks and embeds them. Requires an OpenAI API key for embedding generation.

---

## Deployment

The app is deployed as a split setup:

| Component | Platform | Purpose |
|-----------|----------|---------|
| Frontend | Vercel | Static HTML/CSS/JS |
| Backend | Railway | FastAPI + agents + vector store |

To deploy your own instance, see the [deployment guide](Development%20planning/brief_ai_v2_upgrade_9109002d.plan.md).

---

## Tech Stack

- **Agents:** LangGraph, LangChain, OpenAI GPT-4o-mini
- **RAG:** OpenAI text-embedding-3-small, NumPy cosine similarity
- **Backend:** FastAPI, SSE-Starlette, PyMuPDF
- **Frontend:** Vanilla JS, Chart.js, CSS custom properties
