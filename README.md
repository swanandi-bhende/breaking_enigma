# AI Digital Workforce (ADWF)

ADWF is an autonomous, multi-agent AI system that accepts a single product idea as input and produces a fully scoped, designed, coded, tested, deployed, and documented software product as output — without human intervention between stages.

## System Architecture
 
The pipeline is powered by a LangGraph StateMachine orchestrating 8 specialized AI agents:

1. **Orchestrator Agent:** Pipeline setup and config.
2. **Research Agent:** Market and competitor analysis.
3. **PM Agent:** Product Requirements Document (PRD) and User Stories.
4. **Designer Agent:** UI/UX breakdown, Architecture, and API contracts.
5. **Developer Agent:** Implementation, code generation.
6. **QA Agent:** Traceability matrix, bug detection, feedback loop.
7. **DevOps Agent:** Docker, Compose, and CI/CD config.
8. **Documentation Agent:** Readme, API references, architecture docs.

## Workspace Organization

- `AI_Digital_Workforce_System.md` - The complete product and agent specifications.
- `INTERFACE_CONTRACT.md` - Definition of team responsibilities and the cross-team contracts for agents interfacing with the LangGraph state machine.
- `backend/` - The FastAPI and LangGraph powered backend orchestration and agent execution layers.
  - `backend/app/workflow/` - LangGraph state machine, QA scoring routing, and agent executor logic.
  - `backend/app/schemas/` - Pydantic definition for every agent's input and output contracts.
  - `backend/app/core/` - Redis events, app configs, database config stubs.
  - `backend/app/agents/` - Individual agent executors and stubs.
  - `backend/tests/` - Comprehensive test coverage for the workflow machine, QA calculator and executor wrapper.

## Nisarg's Workflow Setup

This codebase implements the *Workflow Engine & Agent Orchestration*. The backend uses Pydantic schemas to validate all state transitions, and the LangGraph DAG defines end-to-end execution including QA loops and final-stage parallel tasks.

### Run The Full Stack (Docker)

From project root:

```bash
docker compose down
docker compose up -d --build
```

Quick health checks:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/v1/health
curl -I http://127.0.0.1:3000
```

Useful logs during pipeline runs:

```bash
docker compose logs -f backend worker
```

### Running Backend Tests

Navigate to backend:
```bash
cd backend
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the test suite using pytest:
```bash
pytest tests/ -v
```

All LangGraph routing, validation logic, lock states, redis pub/sub mocks, and QA scoring paths have comprehensive tests written.
