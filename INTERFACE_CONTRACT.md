# Cross-Team Interface Contract
## ADWF — Nisarg's Workflow Engine ↔ Teammates

> **Read this if you are Aditya or Anshul.**  
> This document defines every interface point between the workflow engine (Nisarg) and your domain. Follow these contracts exactly — the executor validates against them at runtime.

---

## 1. For Aditya — Research, PM, Designer Agents

### What Nisarg provides you

The executor calls your agent function with a **validated dict** matching your agent's Input schema. You don't need to validate it yourself.

### What you must return

An **unvalidated dict** matching your agent's Output schema. The executor validates it — if it fails, your agent is retried up to 2 times.

### Function signatures you must implement

```python
# backend/app/agents/research.py
async def run_research_agent(input_dict: dict) -> dict:
    # input_dict is a validated ResearchAgentInput.model_dump()
    # must return ResearchAgentOutput.model_dump()
    ...

# backend/app/agents/product_manager.py
async def run_pm_agent(input_dict: dict) -> dict:
    # input_dict is a validated PMAgentInput.model_dump()
    # must return PMAgentOutput.model_dump()
    ...

# backend/app/agents/designer.py
async def run_designer_agent(input_dict: dict) -> dict:
    # input_dict is a validated DesignerAgentInput.model_dump()
    # must return DesignerAgentOutput.model_dump()
    ...
```

### Schemas (source of truth)
All schemas live in `backend/app/schemas/agents.py`. Import them directly:

```python
from app.schemas.agents import (
    ResearchAgentInput, ResearchAgentOutput,
    PMAgentInput, PMAgentOutput,
    DesignerAgentInput, DesignerAgentOutput,
)
```

### Qdrant — where to store embeddings

The executor does **not** call Qdrant for you. Your agent function is responsible for:
1. Chunking research content into embedding-sized pieces
2. Calling `qdrant_client.upsert()` to store them
3. Returning the vector IDs in the output's `embedding_ids` field

Qdrant client setup is in `backend/app/core/qdrant.py` (Anshul's domain — import from there).

### Streaming log lines to the dashboard

Inside your agent function, call this to stream thoughts/progress to the Live Log stream:

```python
from app.core.redis import publish_log_line
from app.core.events import LogLevel

await publish_log_line(run_id, "research", "Analysing competitor landscape…")
await publish_log_line(run_id, "research", "Found 5 competitors", level=LogLevel.INFO)
```

> `run_id` is available as `input_dict["run_id"]`

### JSON reliability — use this prompt wrapper

```python
AGENT_SYSTEM_PROMPT = """
You are the {agent_name} in an autonomous product development system.
You MUST respond with ONLY a valid JSON object matching the schema below.
Do NOT include any explanatory text, markdown code fences, or preamble.
If you cannot complete a field, use null — never omit required fields.

OUTPUT SCHEMA:
{schema_json}
"""
```

---

## 2. For Anshul — Developer, QA, DevOps, Documentation Agents + Database + WebSocket

### Agent function signatures you must implement

```python
# backend/app/agents/developer.py
async def run_developer_agent(input_dict: dict) -> dict:
    # input_dict: DeveloperAgentInput.model_dump()
    # returns:    DeveloperAgentOutput.model_dump()
    ...

# backend/app/agents/qa.py
async def run_qa_agent(input_dict: dict) -> dict:
    # input_dict: QAAgentInput.model_dump()
    # returns:    QAAgentOutput.model_dump()
    ...

# backend/app/agents/devops.py
async def run_devops_agent(input_dict: dict) -> dict:
    # input_dict: DevOpsAgentInput.model_dump()
    # returns:    DevOpsAgentOutput.model_dump()
    ...

# backend/app/agents/documentation.py
async def run_documentation_agent(input_dict: dict) -> dict:
    # input_dict: DocumentationAgentInput.model_dump()
    # returns:    DocumentationAgentOutput.model_dump()
    ...
```

### Critical — QA routing_decision field

The workflow graph reads `qa_output["routing_decision"]["route_to"]` to decide next node.  
**You must return one of:** `"developer"` | `"devops_and_docs"` | `"human_review"`

Use the scoring utility to compute this — don't reinvent it:

```python
from app.workflow.qa_scoring import determine_qa_verdict

result = determine_qa_verdict(
    traceability_matrix=matrix,
    bugs=bugs,
    max_iterations_reached=(iteration >= max_qa_iterations),
)
# result = { verdict, qa_score, must_have_coverage_percent, critical_bugs_count, route_to }
```

### Database functions Nisarg calls (you must implement these)

These are called via late import in `executor.py` and `orchestrator.py`. Implement them in `backend/app/core/database.py`:

```python
# Called by Orchestrator
async def create_pipeline_run(run_id: str, idea: str, config: dict, user_id: str | None) -> None: ...

# Called by Executor
async def save_agent_run(
    run_id: str, agent_name: str, iteration: int,
    input_payload: dict, output_payload: dict | None,
    status: str, duration_ms: int, error_details: dict | None
) -> None: ...

async def save_artifact(run_id: str, artifact_type: str, content: dict, version: int) -> None: ...

# Called by Orchestrator + Worker
async def upsert_global_state(run_id: str, state: dict) -> None: ...

# Called by API GET /runs/{run_id}
async def get_pipeline_run(run_id: str) -> dict | None: ...

# Called by GET /ready health check
async def check_db_health() -> None: ...
```

### WebSocket event schema

The frontend (Swanandi) subscribes to these exact Redis channels via Socket.io.  
Your WebSocket server must:
1. Subscribe to `pipeline:{run_id}:events` and `pipeline:{run_id}:logs`
2. Forward every message to the frontend Socket.io connection for that `run_id`

Event types are defined in `backend/app/core/events.py` → `EventType` enum.

---

## 3. Shared Rules for Everyone

| Rule | Detail |
|---|---|
| **Never import from each other's agent files** | Use the schemas in `app/schemas/agents.py` as the interface |
| **Always use `run_id` from `input_dict["run_id"]`** | Don't generate new UUIDs inside agents |
| **Use `publish_log_line()` for progress messages** | This streams to the dashboard live log |
| **Return `null` for optional fields, never omit them** | Pydantic will reject omitted required fields |
| **Never call another agent directly** | Agents only communicate via the shared PipelineState |

---

## 4. Running Locally (Nisarg's workflow engine only)

```bash
cd backend

# Install deps
pip install -r requirements.txt

# Copy and fill in .env
cp .env.example .env
# → Set OPENAI_API_KEY

# Run FastAPI dev server (no Celery needed — uses BackgroundTasks fallback)
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v

# Start Celery worker (optional — needed for production-style runs)
celery -A app.worker.celery_app worker --loglevel=info -Q pipeline
```

---

## 5. File Ownership Quick Reference

```
backend/app/workflow/        ← Nisarg
  state.py                   ← Nisarg (PipelineState TypedDict)
  graph.py                   ← Nisarg (LangGraph)
  executor.py                ← Nisarg (execution wrapper)
  qa_scoring.py              ← Nisarg (QA score formula)

backend/app/agents/
  orchestrator.py            ← Nisarg
  research.py                ← Aditya
  product_manager.py         ← Aditya
  designer.py                ← Aditya
  developer.py               ← Anshul
  qa.py                      ← Anshul
  devops.py                  ← Anshul
  documentation.py           ← Anshul

backend/app/core/
  config.py                  ← Nisarg (settings)
  events.py                  ← Nisarg (event types)
  redis.py                   ← Nisarg (pub/sub, locks)
  database.py                ← Anshul
  qdrant.py                  ← Anshul

backend/app/schemas/
  agents.py                  ← Nisarg (ALL schemas)

backend/app/main.py          ← Nisarg (/runs + /approve endpoints)
backend/app/worker.py        ← Nisarg (Celery task)
backend/app/api/routes/      ← Anshul
backend/app/api/websocket.py ← Anshul

frontend/                    ← Swanandi
```
