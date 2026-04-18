# AI Digital Workforce: Autonomous Multi-Agent Product Lifecycle System

> **Prepared for:** Antigravity  
> **Project Codename:** `ADWF-v1`  
> **Version:** 1.0.0  
> **Status:** Implementation-Ready Specification  
> **Team:** Nisarg · Aditya · Swanandi · Anshul

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Vision & Goals](#3-vision--goals)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [Agent Design — Detailed Specifications](#5-agent-design--detailed-specifications)
   - 5.1 [Orchestrator Agent](#51-orchestrator-agent)
   - 5.2 [Research Agent](#52-research-agent)
   - 5.3 [Product Manager Agent](#53-product-manager-agent)
   - 5.4 [Designer Agent](#54-designer-agent)
   - 5.5 [Developer Agent](#55-developer-agent)
   - 5.6 [QA Agent](#56-qa-agent)
   - 5.7 [DevOps Agent](#57-devops-agent)
   - 5.8 [Documentation Agent](#58-documentation-agent)
6. [Shared State & Memory Layer](#6-shared-state--memory-layer)
7. [Workflow Orchestration](#7-workflow-orchestration)
8. [Developer–QA Feedback Loop](#8-developerqa-feedback-loop)
9. [Full Tech Stack](#9-full-tech-stack)
10. [Dashboard System Design](#10-dashboard-system-design)
11. [Auto-Documentation System](#11-auto-documentation-system)
12. [DevOps & Deployment Architecture](#12-devops--deployment-architecture)
13. [Phase-Wise Implementation Plan](#13-phase-wise-implementation-plan)
14. [MECE Team Task Division](#14-mece-team-task-division)
15. [Risks, Constraints & Mitigations](#15-risks-constraints--mitigations)
16. [Future Scope](#16-future-scope)
17. [Appendix — Environment Variables & Config](#17-appendix--environment-variables--config)

---

## 1. Project Overview

**AI Digital Workforce (ADWF)** is an autonomous, multi-agent AI system that accepts a single product idea as input and produces a fully scoped, designed, coded, tested, deployed, and documented software product as output — without human intervention between stages.

The system mimics an entire product team:

| Agent | Human Role Equivalent |
|---|---|
| Orchestrator | Engineering Manager / CTO |
| Research | UX Researcher + Market Analyst |
| Product Manager | Product Manager |
| Designer | UX Designer + System Architect |
| Developer | Senior Full-Stack Engineer |
| QA | QA Engineer |
| DevOps | DevOps/SRE Engineer |
| Documentation | Technical Writer |

Each agent is a self-contained LLM-powered service with defined inputs, outputs, tools, and a JSON contract. Agents communicate via a shared global state object persisted in PostgreSQL and Redis, with semantic memory stored in a Vector DB (Qdrant).

The entire pipeline is controlled by a **LangGraph-based workflow engine** with state machines, retry logic, and feedback routing. A **real-time Next.js dashboard** serves as mission control — users submit an idea and watch the system build their product live.

---

## 2. Problem Statement

Building software products requires coordinating across research, design, engineering, QA, deployment, and documentation — a process that typically takes weeks, requires a large team, and suffers from:

- **Context loss between handoffs** — designers don't know what researchers found; developers don't know what QA will check.
- **Inconsistent outputs** — no structured contract between stages means downstream agents receive ambiguous inputs.
- **Manual iteration loops** — bug fixes require human triage, re-prioritization, and re-tasking.
- **Documentation lag** — docs are written after everything else, often incomplete or stale.
- **High cost and slow time-to-first-prototype** — a solo founder or small team cannot afford or assemble a full product team.

**ADWF solves this by replacing the coordination layer with an autonomous agent graph** where every handoff is a structured JSON contract, every loop is programmatic, and every output is machine-readable and human-reviewable.

---

## 3. Vision & Goals

### Vision Statement

> *"Give anyone — a founder, a student, a solo developer — the ability to transform a one-sentence idea into a working, tested, deployed software product in under 60 minutes, with zero team required."*

### Primary Goals

1. **End-to-end automation** — from idea to deployed MVP with documentation, no human steps required between agents.
2. **Structured inter-agent contracts** — every agent input and output is a validated JSON schema, enabling reliable machine-to-machine handoffs.
3. **Observable pipeline** — every agent action, decision, and state transition is visible in real time via a dashboard.
4. **Iterative quality gates** — QA failures route back automatically; the system self-corrects up to N iterations before surfacing issues to the user.
5. **Customizable workflows** — teams can define their own agent pipelines, skip agents, or inject human checkpoints.

### Success Metrics

| Metric | Target |
|---|---|
| Time from idea to deployed MVP | < 60 minutes |
| QA pass rate on first iteration | > 70% |
| Feature coverage from PRD to code | > 90% |
| Documentation completeness score | > 85% |
| Dashboard real-time latency | < 500ms state update |

---

## 4. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER / DASHBOARD                            │
│              Next.js 14 App — Real-time via WebSocket               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP / WebSocket
┌───────────────────────────────▼─────────────────────────────────────┐
│                        API GATEWAY LAYER                            │
│                  FastAPI (Python) — /api/v1/*                       │
│        Auth (JWT) · Rate Limiting · Request Validation              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                    WORKFLOW ORCHESTRATION ENGINE                     │
│                     LangGraph StateMachine                          │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │  Research │──▶│    PM    │──▶│ Designer │──▶│Developer │        │
│  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘        │
│                                                      │              │
│                               ┌──────────────────────▼──────┐      │
│                               │          QA Agent            │      │
│                               │  Pass → DevOps + Docs        │      │
│                               │  Fail → Developer (loop)     │      │
│                               └──────────────────────────────┘      │
│                                                                     │
│  ┌──────────────────────┐   ┌──────────────────────┐               │
│  │    DevOps Agent       │   │  Documentation Agent  │ (parallel)   │
│  └──────────────────────┘   └──────────────────────┘               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                     SHARED STATE & MEMORY LAYER                     │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐   │
│  │ PostgreSQL  │  │    Redis     │  │  Qdrant (Vector DB)       │   │
│  │ global_state│  │ live events  │  │  semantic memory / RAG    │   │
│  │ agent_runs  │  │ pub/sub      │  │  research context         │   │
│  │ artifacts   │  │ agent locks  │  │  past project embeddings  │   │
│  └─────────────┘  └─────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

1. **Agent Isolation** — Each agent runs in its own Python process/container. Agents do not call each other directly; they read from and write to shared global state.
2. **Event-Driven State Updates** — When an agent writes to PostgreSQL, a Postgres NOTIFY fires → Redis pub/sub → WebSocket pushes update to dashboard.
3. **Immutable Artifact Store** — All agent outputs are stored as versioned JSON blobs in PostgreSQL. Nothing is overwritten; new iterations create new records.
4. **Retry-Safe Operations** — All agent runs are idempotent. Re-running an agent with the same `run_id` produces the same output or resumes from the last checkpoint.
5. **Schema-First Contracts** — Every agent input/output is validated against a JSON Schema (using Pydantic in Python) before being accepted by the next agent.

---

## 5. Agent Design — Detailed Specifications

### 5.1 Orchestrator Agent

#### Role
The Orchestrator is the **brain of the pipeline**. It does not perform any product work itself. Its sole responsibility is to:
- Parse the user's input idea
- Decide the workflow execution order
- Validate each agent's output before passing it downstream
- Route failures back to the appropriate agent
- Maintain the global `run_state` object
- Emit real-time events to the dashboard

#### Tasks
1. Parse and normalize the raw idea string into a structured `project_brief`
2. Initialize the `global_state` record in PostgreSQL
3. Trigger agents in sequence (or parallel where appropriate)
4. After each agent completes, validate output against the downstream agent's input schema
5. On validation failure: log error, increment retry count, re-trigger agent with error context
6. On max retries exceeded: set `run_state = "FAILED"`, surface error to dashboard
7. On all agents complete: set `run_state = "COMPLETE"`, trigger ZIP export

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "OrchestratorInput",
  "type": "object",
  "required": ["run_id", "idea", "config"],
  "properties": {
    "run_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for this pipeline run"
    },
    "idea": {
      "type": "string",
      "minLength": 10,
      "maxLength": 1000,
      "description": "The raw product idea from the user"
    },
    "config": {
      "type": "object",
      "properties": {
        "max_qa_iterations": { "type": "integer", "default": 3 },
        "skip_agents": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Agent names to skip in this run"
        },
        "human_checkpoints": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Agent names after which to pause and await human approval"
        },
        "llm_model": { "type": "string", "default": "gpt-4o" },
        "target_platform": {
          "type": "string",
          "enum": ["web", "mobile", "api-only"],
          "default": "web"
        }
      }
    }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "OrchestratorOutput",
  "type": "object",
  "required": ["run_id", "run_state", "project_brief", "phases"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "run_state": {
      "type": "string",
      "enum": ["INITIALIZING", "RUNNING", "AWAITING_HUMAN", "FAILED", "COMPLETE"]
    },
    "project_brief": {
      "type": "object",
      "properties": {
        "title": { "type": "string" },
        "normalized_idea": { "type": "string" },
        "domain": { "type": "string" },
        "target_platform": { "type": "string" }
      }
    },
    "phases": {
      "type": "object",
      "description": "Status of each phase keyed by agent name",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "status": {
            "type": "string",
            "enum": ["PENDING", "RUNNING", "COMPLETE", "FAILED", "SKIPPED"]
          },
          "started_at": { "type": "string", "format": "date-time" },
          "completed_at": { "type": "string", "format": "date-time" },
          "iteration": { "type": "integer" },
          "error": { "type": ["string", "null"] }
        }
      }
    },
    "artifact_urls": {
      "type": "object",
      "description": "S3/local paths to all output artifacts keyed by agent name"
    }
  }
}
```

#### Connectivity
- **Receives from:** User (via API Gateway)
- **Sends to:** All agents (via LangGraph node triggers)
- **Reads:** `global_state` table in PostgreSQL
- **Writes:** `run_state`, `phases` fields in `global_state`
- **Emits:** Redis pub/sub events on every state change → WebSocket → Dashboard

---

### 5.2 Research Agent

#### Role
The Research Agent is the **intelligence gathering layer**. It takes the raw product idea and builds a comprehensive market and user intelligence report that becomes the foundation for every downstream agent decision.

#### Tasks
1. **Problem Clarification** — Decompose the idea into a clear problem statement, user hypothesis, and solution hypothesis
2. **Market Research** — TAM/SAM/SOM estimation, industry overview, growth trends, market timing assessment
3. **User Research** — Age group identification, behavioral patterns, persona creation (3–5 archetypes), target segment definition
4. **Pain Point Extraction** — Ranked list of user pains mapped to existing solutions and gaps
5. **Competitor Analysis** — Top 5 competitors: features, pricing, positioning, weaknesses
6. **Business Viability** — Revenue model options, monetization potential, sustainability assessment
7. **Technical Feasibility** — Tech risk assessment, key technical challenges, estimated build complexity

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "ResearchAgentInput",
  "type": "object",
  "required": ["run_id", "project_brief"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "project_brief": {
      "type": "object",
      "required": ["normalized_idea", "domain", "target_platform"],
      "properties": {
        "normalized_idea": { "type": "string" },
        "domain": { "type": "string" },
        "target_platform": { "type": "string" }
      }
    },
    "tools_available": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of tool names the agent can use: web_search, serp_api, crunchbase_api"
    }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "ResearchAgentOutput",
  "type": "object",
  "required": ["run_id", "research_report"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "research_report": {
      "type": "object",
      "required": ["problem_statement", "market", "personas", "pain_points", "competitors", "viability", "feasibility"],
      "properties": {
        "problem_statement": {
          "type": "object",
          "properties": {
            "core_problem": { "type": "string" },
            "affected_users": { "type": "string" },
            "current_solutions_fail_because": { "type": "string" },
            "opportunity_window": { "type": "string" }
          }
        },
        "market": {
          "type": "object",
          "properties": {
            "tam_usd": { "type": "number" },
            "sam_usd": { "type": "number" },
            "som_usd": { "type": "number" },
            "industry": { "type": "string" },
            "growth_rate_yoy_percent": { "type": "number" },
            "key_trends": {
              "type": "array",
              "items": { "type": "string" }
            }
          }
        },
        "personas": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": { "type": "string" },
              "age_range": { "type": "string" },
              "occupation": { "type": "string" },
              "goals": { "type": "array", "items": { "type": "string" } },
              "frustrations": { "type": "array", "items": { "type": "string" } },
              "tech_savviness": { "type": "string", "enum": ["low", "medium", "high"] },
              "primary_device": { "type": "string" }
            }
          }
        },
        "pain_points": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "pain": { "type": "string" },
              "severity": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
              "frequency": { "type": "string", "enum": ["rare", "occasional", "frequent", "constant"] },
              "existing_workaround": { "type": "string" }
            }
          }
        },
        "competitors": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": { "type": "string" },
              "url": { "type": "string" },
              "positioning": { "type": "string" },
              "pricing_model": { "type": "string" },
              "key_features": { "type": "array", "items": { "type": "string" } },
              "weaknesses": { "type": "array", "items": { "type": "string" } },
              "user_sentiment": { "type": "string" }
            }
          }
        },
        "viability": {
          "type": "object",
          "properties": {
            "revenue_models": { "type": "array", "items": { "type": "string" } },
            "recommended_model": { "type": "string" },
            "estimated_arpu": { "type": "string" },
            "go_to_market_strategy": { "type": "string" },
            "viability_score": { "type": "integer", "minimum": 1, "maximum": 10 }
          }
        },
        "feasibility": {
          "type": "object",
          "properties": {
            "technical_risks": { "type": "array", "items": { "type": "string" } },
            "complexity": { "type": "string", "enum": ["low", "medium", "high"] },
            "estimated_mvp_weeks": { "type": "integer" },
            "key_dependencies": { "type": "array", "items": { "type": "string" } },
            "feasibility_score": { "type": "integer", "minimum": 1, "maximum": 10 }
          }
        }
      }
    },
    "embedding_ids": {
      "type": "array",
      "items": { "type": "string" },
      "description": "IDs of vectors stored in Qdrant for this research output"
    }
  }
}
```

#### Connectivity
- **Input from:** Orchestrator (project_brief)
- **Output to:** PM Agent (research_report JSON)
- **Tools used:** `web_search`, `serp_api`, `crunchbase_lookup`
- **Stores to:** PostgreSQL (`agent_outputs` table), Qdrant (semantic embeddings of all research content)

---

### 5.3 Product Manager Agent

#### Role
The PM Agent is the **product decision engine**. It takes the research output and produces a complete, implementation-ready Product Requirements Document (PRD) that every downstream agent uses as its source of truth.

#### Tasks
1. **Define Product Direction** — What are we building, who is it for, why will they use it
2. **Pain Point Prioritization** — Rank pain points by (severity × frequency × market size) using a weighted scoring matrix
3. **User Stories Generation** — Full set of user stories in "As a [persona], I want to [action] so that [outcome]" format
4. **Acceptance Criteria** — Specific, testable acceptance criteria for every user story (Given/When/Then format)
5. **Solution Design** — Concrete solution approach mapped to prioritized pains
6. **Feature Definition** — Features grouped as Must-Have (MVP), Should-Have (v1.1), Could-Have (v2.0)
7. **Budget Estimation** — Rough build cost in engineer-weeks at different quality levels
8. **Value Projection** — Estimated user value and business value after solving each pain
9. **Basic User Flow** — High-level step-by-step user journey for the Designer Agent

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "PMAgentInput",
  "type": "object",
  "required": ["run_id", "research_report"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "research_report": { "$ref": "ResearchAgentOutput#/properties/research_report" }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "PMAgentOutput",
  "type": "object",
  "required": ["run_id", "prd"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "prd": {
      "type": "object",
      "required": ["product_vision", "user_stories", "features", "user_flow"],
      "properties": {
        "product_vision": {
          "type": "object",
          "properties": {
            "elevator_pitch": { "type": "string" },
            "target_user": { "type": "string" },
            "core_value_proposition": { "type": "string" },
            "success_definition": { "type": "string" }
          }
        },
        "user_stories": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "persona", "action", "outcome", "priority", "acceptance_criteria"],
            "properties": {
              "id": { "type": "string", "pattern": "^US-[0-9]{3}$" },
              "persona": { "type": "string" },
              "action": { "type": "string" },
              "outcome": { "type": "string" },
              "priority": { "type": "string", "enum": ["must-have", "should-have", "could-have", "wont-have"] },
              "acceptance_criteria": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "given": { "type": "string" },
                    "when": { "type": "string" },
                    "then": { "type": "string" }
                  }
                }
              },
              "estimated_effort": { "type": "string", "enum": ["XS", "S", "M", "L", "XL"] }
            }
          }
        },
        "features": {
          "type": "object",
          "properties": {
            "mvp": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": { "type": "string" },
                  "name": { "type": "string" },
                  "description": { "type": "string" },
                  "maps_to_user_stories": { "type": "array", "items": { "type": "string" } },
                  "technical_notes": { "type": "string" }
                }
              }
            },
            "v1_1": { "type": "array" },
            "v2_0": { "type": "array" }
          }
        },
        "budget_estimate": {
          "type": "object",
          "properties": {
            "mvp_engineer_weeks": { "type": "number" },
            "mvp_cost_usd_range": { "type": "string" },
            "assumptions": { "type": "array", "items": { "type": "string" } }
          }
        },
        "user_flow": {
          "type": "array",
          "description": "Ordered steps of the primary user journey",
          "items": {
            "type": "object",
            "properties": {
              "step": { "type": "integer" },
              "screen_name": { "type": "string" },
              "user_action": { "type": "string" },
              "system_response": { "type": "string" },
              "next_step": { "type": ["integer", "null"] }
            }
          }
        }
      }
    }
  }
}
```

#### Connectivity
- **Input from:** Research Agent (research_report)
- **Output to:** Designer Agent (prd JSON)
- **Stores to:** PostgreSQL (`agent_outputs`), Qdrant (PRD embeddings for RAG by downstream agents)

---

### 5.4 Designer Agent

#### Role
The Designer Agent is the **architectural and visual design engine**. It takes the PRD and produces the full design specification: UI/UX wireframes (text-based), system architecture, API contracts, and data models. Downstream agents treat this output as their technical blueprint.

#### Tasks

**UI/UX Design:**
- Screen-level breakdown (list every screen, its purpose, and its components)
- Wireframe descriptions (text-based structured format for MVP; image-based for full runs)
- Component hierarchy definition (Navbar, Cards, Forms, Modals per screen)
- UX decision log (navigation style, interaction patterns, responsive strategy)

**Interaction Flow Design:**
- Flow diagrams: step-by-step interaction for every primary user journey
- State transition map: all UI states (loading, error, empty, success, auth)
- Edge case catalog: every exception state and how the UI handles it

**System Architecture Design:**
- High-level architecture diagram (frontend, backend, DB, cache, external services)
- Service boundary definitions
- Communication flow (REST vs WebSocket vs SSE per interaction type)

**API Specification:**
- Full endpoint definitions (method, path, auth, request body, response, errors)
- Authentication method and token flow
- Rate limiting rules

**Data Model Design:**
- All entities with fields and types
- Relationships (FK, many-to-many)
- Indexing strategy

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DesignerAgentInput",
  "type": "object",
  "required": ["run_id", "prd"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "prd": { "$ref": "PMAgentOutput#/properties/prd" },
    "research_context_embedding_ids": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Qdrant IDs to retrieve for context augmentation"
    }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DesignerAgentOutput",
  "type": "object",
  "required": ["run_id", "design_spec"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "design_spec": {
      "type": "object",
      "required": ["screens", "system_architecture", "api_spec", "data_models"],
      "properties": {
        "screens": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["screen_id", "screen_name", "route", "components", "ux_decisions"],
            "properties": {
              "screen_id": { "type": "string" },
              "screen_name": { "type": "string" },
              "route": { "type": "string" },
              "purpose": { "type": "string" },
              "components": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "component_name": { "type": "string" },
                    "type": { "type": "string", "enum": ["layout", "form", "display", "navigation", "feedback"] },
                    "props": { "type": "object" },
                    "state_dependencies": { "type": "array", "items": { "type": "string" } }
                  }
                }
              },
              "ux_decisions": { "type": "array", "items": { "type": "string" } },
              "edge_cases": { "type": "array", "items": { "type": "string" } },
              "wireframe_description": { "type": "string" }
            }
          }
        },
        "interaction_flows": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "flow_id": { "type": "string" },
              "flow_name": { "type": "string" },
              "trigger": { "type": "string" },
              "steps": { "type": "array", "items": { "type": "string" } },
              "happy_path_end": { "type": "string" },
              "failure_paths": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "system_architecture": {
          "type": "object",
          "properties": {
            "frontend": { "type": "string" },
            "backend": { "type": "string" },
            "database": { "type": "string" },
            "cache": { "type": "string" },
            "external_services": { "type": "array", "items": { "type": "string" } },
            "communication_patterns": {
              "type": "object",
              "additionalProperties": { "type": "string" }
            }
          }
        },
        "api_spec": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["endpoint_id", "method", "path", "auth_required", "request_body", "responses"],
            "properties": {
              "endpoint_id": { "type": "string" },
              "method": { "type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"] },
              "path": { "type": "string" },
              "auth_required": { "type": "boolean" },
              "description": { "type": "string" },
              "request_body": {
                "type": "object",
                "properties": {
                  "content_type": { "type": "string" },
                  "schema": { "type": "object" },
                  "validation_rules": { "type": "array", "items": { "type": "string" } }
                }
              },
              "responses": {
                "type": "object",
                "description": "HTTP status code → response schema",
                "additionalProperties": {
                  "type": "object",
                  "properties": {
                    "description": { "type": "string" },
                    "schema": { "type": "object" },
                    "example": { "type": "object" }
                  }
                }
              },
              "rate_limit": { "type": "string" },
              "maps_to_user_stories": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "data_models": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["entity_name", "table_name", "fields"],
            "properties": {
              "entity_name": { "type": "string" },
              "table_name": { "type": "string" },
              "fields": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "name": { "type": "string" },
                    "type": { "type": "string" },
                    "nullable": { "type": "boolean" },
                    "unique": { "type": "boolean" },
                    "indexed": { "type": "boolean" },
                    "foreign_key": { "type": ["string", "null"] },
                    "default": { "type": ["string", "null"] }
                  }
                }
              },
              "relationships": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "type": { "type": "string", "enum": ["one-to-one", "one-to-many", "many-to-many"] },
                    "with_entity": { "type": "string" },
                    "foreign_key": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

#### Connectivity
- **Input from:** PM Agent (prd), Qdrant (research embeddings via RAG)
- **Output to:** Developer Agent (design_spec)
- **Feedback loop:** QA Agent can trigger re-run of Designer Agent when API contracts are incomplete
- **Parallel output:** Documentation Agent reads design_spec simultaneously with Developer Agent

---

### 5.5 Developer Agent

#### Role
The Developer Agent is the **code generation engine**. It follows a strict 5-step protocol — read, plan, generate, verify, output — and returns machine-readable artifacts that map directly to the design spec.

#### 5-Step Developer Protocol

**Step 1 — Read & Extract:**
Parse the design_spec to extract: user flows, all screens, component hierarchy, API endpoints, data models, edge cases, MVP-must features.

**Step 2 — Technical Implementation Plan:**
Produce a granular task list:
- Folder/file structure definition
- State management setup (Zustand stores)
- API route handlers (FastAPI)
- Database migrations (Alembic)
- Component stubs
- Validation logic
- Test file stubs

**Step 3 — Generate Artifacts:**
Produce actual file contents: TypeScript/React components, Python FastAPI routes, Alembic migration files, Pydantic schemas, test files, environment config templates.

**Step 4 — Self-Verification:**
- Schema consistency check: do API request/response types match Pydantic models?
- Route completeness: is every API endpoint from the spec implemented?
- Feature coverage: does every must-have feature have at least one corresponding file?
- Test existence: does every API route have a test stub?

**Step 5 — Return Structured Output:**
Return a machine-readable output object (see schema below).

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DeveloperAgentInput",
  "type": "object",
  "required": ["run_id", "design_spec", "prd"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "design_spec": { "$ref": "DesignerAgentOutput#/properties/design_spec" },
    "prd": { "$ref": "PMAgentOutput#/properties/prd" },
    "qa_feedback": {
      "type": ["object", "null"],
      "description": "Non-null on re-runs triggered by QA failures",
      "properties": {
        "iteration": { "type": "integer" },
        "failed_tests": { "type": "array", "items": { "type": "object" } },
        "bugs": { "type": "array", "items": { "type": "object" } },
        "fix_instructions": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DeveloperAgentOutput",
  "type": "object",
  "required": ["run_id", "task_id", "status", "summary", "files_created", "features_implemented"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "task_id": { "type": "string" },
    "status": { "type": "string", "enum": ["completed", "partial", "failed"] },
    "summary": { "type": "string" },
    "files_created": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "purpose", "content"],
        "properties": {
          "path": { "type": "string" },
          "purpose": { "type": "string" },
          "content": { "type": "string" },
          "language": { "type": "string" },
          "maps_to_endpoint_ids": { "type": "array", "items": { "type": "string" } },
          "maps_to_screen_ids": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "features_implemented": { "type": "array", "items": { "type": "string" } },
    "features_skipped": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "feature": { "type": "string" },
          "reason": { "type": "string" }
        }
      }
    },
    "tests_written": { "type": "array", "items": { "type": "string" } },
    "tech_debt_logged": { "type": "array", "items": { "type": "string" } },
    "self_check_results": {
      "type": "object",
      "properties": {
        "schema_consistent": { "type": "boolean" },
        "all_routes_implemented": { "type": "boolean" },
        "feature_coverage_percent": { "type": "number" },
        "test_coverage_percent": { "type": "number" },
        "issues_found": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

#### Connectivity
- **Input from:** Designer Agent (design_spec), PM Agent (prd), QA Agent (qa_feedback on re-runs)
- **Output to:** QA Agent
- **Stores to:** PostgreSQL (files as blobs), artifact file system (ZIP)

---

### 5.6 QA Agent

#### Role
The QA Agent is the **quality gate and feedback router**. It validates that the Developer Agent's output fully satisfies the PRD's acceptance criteria, checks for bugs, and either approves the build (routing to DevOps + Docs) or sends structured fix instructions back to the Developer Agent.

#### Tasks
1. **Feature Traceability Matrix** — Map every `must-have` feature/user story to its implementation file. Mark as COVERED / PARTIAL / MISSING.
2. **Acceptance Criteria Verification** — For each user story's `Given/When/Then` acceptance criteria, check if the corresponding code logically satisfies it.
3. **Bug Detection** — Identify logic errors, missing validation, unhandled errors, missing auth checks.
4. **Edge Case Audit** — Cross-reference the Designer Agent's edge case catalog against implementation.
5. **API Contract Validation** — Verify that implemented API routes match the spec: correct HTTP method, path params, request body shape, response shape.
6. **Routing Decision** — If `critical_bugs > 0` OR `must_have_coverage < 100%` → FAIL and route back to Developer. Else → PASS and route to DevOps + Docs.

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "QAAgentInput",
  "type": "object",
  "required": ["run_id", "developer_output", "design_spec", "prd"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "developer_output": { "$ref": "DeveloperAgentOutput" },
    "design_spec": { "$ref": "DesignerAgentOutput#/properties/design_spec" },
    "prd": { "$ref": "PMAgentOutput#/properties/prd" },
    "iteration": { "type": "integer", "default": 1 }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "QAAgentOutput",
  "type": "object",
  "required": ["run_id", "verdict", "qa_score", "traceability_matrix", "bugs"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "verdict": { "type": "string", "enum": ["PASS", "FAIL"] },
    "qa_score": { "type": "number", "minimum": 0, "maximum": 100 },
    "iteration": { "type": "integer" },
    "traceability_matrix": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "user_story_id": { "type": "string" },
          "feature_name": { "type": "string" },
          "status": { "type": "string", "enum": ["COVERED", "PARTIAL", "MISSING"] },
          "implementing_files": { "type": "array", "items": { "type": "string" } },
          "acceptance_criteria_results": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "criterion": { "type": "string" },
                "result": { "type": "string", "enum": ["PASS", "FAIL", "UNTESTABLE"] },
                "notes": { "type": "string" }
              }
            }
          }
        }
      }
    },
    "bugs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["bug_id", "severity", "title", "description", "affected_file", "status"],
        "properties": {
          "bug_id": { "type": "string" },
          "severity": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
          "title": { "type": "string" },
          "description": { "type": "string" },
          "affected_file": { "type": "string" },
          "affected_user_story": { "type": "string" },
          "reproduction_steps": { "type": "array", "items": { "type": "string" } },
          "suggested_fix": { "type": "string" },
          "status": { "type": "string", "enum": ["open", "in_progress", "resolved", "wont_fix"] }
        }
      }
    },
    "routing_decision": {
      "type": "object",
      "properties": {
        "route_to": { "type": "string", "enum": ["developer", "devops_and_docs", "human_review"] },
        "reason": { "type": "string" },
        "fix_instructions": { "type": "array", "items": { "type": "string" } }
      }
    },
    "must_have_coverage_percent": { "type": "number" },
    "critical_bugs_count": { "type": "integer" }
  }
}
```

#### Connectivity
- **Input from:** Developer Agent
- **Output to:** Developer Agent (on FAIL) OR DevOps Agent + Documentation Agent (on PASS)
- **Routing:** Orchestrator evaluates `routing_decision` field and triggers appropriate next node

---

### 5.7 DevOps Agent

#### Role
The DevOps Agent is the **deployment and infrastructure provisioning engine**. It takes the final approved code artifacts and produces a complete deployment package: Dockerfiles, docker-compose, GitHub Actions CI/CD pipelines, environment configs, and a working deployment manifest.

#### Tasks
1. **Project File Tree Finalization** — Organize all Developer Agent files into a proper monorepo structure
2. **Dockerfile Generation** — Separate Dockerfiles for frontend (Next.js) and backend (FastAPI) with multi-stage builds
3. **docker-compose.yml** — Full local dev compose file: frontend, backend, PostgreSQL, Redis, Qdrant
4. **GitHub Actions CI/CD** — `.github/workflows/ci.yml` and `deploy.yml` pipelines
5. **Environment Config** — `.env.example` with all required variables and descriptions
6. **Health Check Endpoints** — Ensure `/health` and `/ready` endpoints exist
7. **Deployment Manifest** — Render/Railway/Vercel config files for one-click deployment
8. **README Quickstart Section** — "Up and running in 3 commands" instructions

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DevOpsAgentInput",
  "type": "object",
  "required": ["run_id", "developer_output", "qa_output"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "developer_output": { "$ref": "DeveloperAgentOutput" },
    "qa_output": { "$ref": "QAAgentOutput" },
    "deployment_target": {
      "type": "string",
      "enum": ["docker-local", "render", "railway", "vercel-frontend-only"],
      "default": "docker-local"
    }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DevOpsAgentOutput",
  "type": "object",
  "required": ["run_id", "deployment_artifacts", "startup_commands"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "deployment_artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "type": { "type": "string", "enum": ["dockerfile", "compose", "ci_workflow", "env_template", "config"] },
          "content": { "type": "string" }
        }
      }
    },
    "startup_commands": {
      "type": "array",
      "description": "Ordered list of commands to start the project from scratch",
      "items": { "type": "string" }
    },
    "environment_variables": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "key": { "type": "string" },
          "description": { "type": "string" },
          "required": { "type": "boolean" },
          "example_value": { "type": "string" }
        }
      }
    },
    "health_check_urls": { "type": "array", "items": { "type": "string" } },
    "deployment_url": { "type": ["string", "null"] }
  }
}
```

#### Connectivity
- **Input from:** Developer Agent (final files), QA Agent (approval)
- **Output to:** Documentation Agent (startup_commands), global_state (deployment_artifacts)
- **Runs parallel with:** Documentation Agent (no dependency between them)

---

### 5.8 Documentation Agent

#### Role
The Documentation Agent is the **auto-documentation engine**. It reads outputs from ALL previous agents and produces a complete, publication-ready documentation suite that is guaranteed to match the actual implementation because it is generated directly from the same JSON contracts the code was built against.

#### Tasks

**Step 1 — README.md Generation:**
Quick-start guide, feature list, tech stack summary, environment variables, "up in 3 commands" section.

**Step 2 — API Reference Generation:**
For every endpoint in `design_spec.api_spec`: HTTP method, path, auth requirements, request body (field types, validation rules), success response with example JSON, all error codes with explanations.

**Step 3 — Architecture Decision Log:**
Captures the "why" behind every major decision pulled from agent outputs: Orchestrator config assumptions, PM prioritization rationale, Designer trade-offs, Developer tech debt logged.

**Step 4 — Known Issues Generation:**
From `qa_output.bugs` where `status = "open"`: bug title, severity, user-friendly description, workaround, fix status.

**Step 5 — CONTRIBUTING.md:**
Developer setup guide, how to run locally, how to run tests, branch naming convention, PR checklist.

**Step 6 — CHANGELOG.md:**
Auto-generated from agent outputs: what was researched, what was scoped, what was built, what was tested.

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DocumentationAgentInput",
  "type": "object",
  "required": ["run_id", "research_report", "prd", "design_spec", "developer_output", "qa_output", "devops_output"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "research_report": { "$ref": "ResearchAgentOutput#/properties/research_report" },
    "prd": { "$ref": "PMAgentOutput#/properties/prd" },
    "design_spec": { "$ref": "DesignerAgentOutput#/properties/design_spec" },
    "developer_output": { "$ref": "DeveloperAgentOutput" },
    "qa_output": { "$ref": "QAAgentOutput" },
    "devops_output": { "$ref": "DevOpsAgentOutput" }
  }
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "DocumentationAgentOutput",
  "type": "object",
  "required": ["run_id", "documents"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "documents": {
      "type": "object",
      "properties": {
        "README.md": { "type": "string" },
        "API_REFERENCE.md": { "type": "string" },
        "ARCHITECTURE.md": { "type": "string" },
        "KNOWN_ISSUES.md": { "type": "string" },
        "CONTRIBUTING.md": { "type": "string" },
        "CHANGELOG.md": { "type": "string" }
      }
    }
  }
}
```

#### Connectivity
- **Reads from:** Research Agent, PM Agent, Designer Agent, Developer Agent, QA Agent, DevOps Agent
- **Writes to:** `global_state.phases.documentation.output`, output ZIP
- **Runs parallel with:** DevOps Agent

---

## 6. Shared State & Memory Layer

### 6.1 PostgreSQL — Persistent State Store

PostgreSQL is the **system of record**. Every agent run, output, and artifact is stored here with full versioning.

#### Schema

```sql
-- Core run tracking
CREATE TABLE pipeline_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea TEXT NOT NULL,
  config JSONB NOT NULL DEFAULT '{}',
  run_state VARCHAR(50) NOT NULL DEFAULT 'INITIALIZING',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  user_id UUID
);

-- Per-agent execution records
CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  agent_name VARCHAR(100) NOT NULL,
  iteration INTEGER NOT NULL DEFAULT 1,
  status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
  input_payload JSONB,
  output_payload JSONB,
  error_details JSONB,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,
  tokens_used INTEGER
);

-- Versioned artifact storage
CREATE TABLE artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  agent_run_id UUID REFERENCES agent_runs(id),
  artifact_type VARCHAR(100) NOT NULL, -- 'research_report', 'prd', 'design_spec', etc.
  version INTEGER NOT NULL DEFAULT 1,
  content JSONB NOT NULL,
  file_path TEXT, -- local FS or S3 path for large blobs
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(pipeline_run_id, artifact_type, version)
);

-- Global state mirror (denormalized for fast reads)
CREATE TABLE global_state (
  pipeline_run_id UUID PRIMARY KEY REFERENCES pipeline_runs(id),
  state JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- QA iterations log
CREATE TABLE qa_iterations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id UUID REFERENCES pipeline_runs(id),
  iteration_number INTEGER NOT NULL,
  verdict VARCHAR(10) NOT NULL,
  qa_score NUMERIC(5,2),
  bugs_count INTEGER,
  critical_bugs_count INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_agent_runs_pipeline ON agent_runs(pipeline_run_id);
CREATE INDEX idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX idx_artifacts_run_type ON artifacts(pipeline_run_id, artifact_type);
CREATE INDEX idx_pipeline_runs_state ON pipeline_runs(run_state);
```

### 6.2 Redis — Real-Time Event Bus & Cache

Redis serves two roles: **pub/sub event bus** for real-time dashboard updates, and **ephemeral cache** for agent locks and rate limiting.

#### Key Patterns

```
# Agent lock (prevents concurrent runs of the same agent)
agent_lock:{run_id}:{agent_name}  →  "locked" (TTL: 300s)

# Live agent status (fast reads for dashboard)
agent_status:{run_id}:{agent_name}  →  JSON { status, started_at, progress_percent }

# Pub/Sub channels
channel: pipeline:{run_id}:events    # All state change events for a run
channel: pipeline:{run_id}:logs      # Streaming log lines
channel: pipeline:global             # System-wide notifications

# Rate limiting
rate_limit:llm:{agent_name}  →  request count (TTL: 60s)
```

#### Event Schema (published to Redis)

```json
{
  "event_type": "AGENT_STATUS_CHANGED",
  "run_id": "uuid",
  "agent_name": "research",
  "previous_status": "PENDING",
  "new_status": "RUNNING",
  "timestamp": "2024-01-01T00:00:00Z",
  "metadata": {}
}
```

#### Event Types

```
PIPELINE_STARTED
AGENT_STATUS_CHANGED     (PENDING → RUNNING → COMPLETE / FAILED)
AGENT_LOG_LINE           (streaming thought/action lines)
QA_VERDICT               (PASS / FAIL with score)
QA_ROUTING_LOOP          (shows feedback arrow on dashboard)
PIPELINE_COMPLETE
PIPELINE_FAILED
ARTIFACT_READY           (agent output available for download)
```

### 6.3 Qdrant — Vector Database (Semantic Memory)

Qdrant stores **embeddings of all agent outputs**, enabling downstream agents to retrieve relevant context via semantic search (RAG) rather than injecting entire previous outputs into LLM context windows.

#### Collections

```python
# Collection: research_context
# Stores: chunked research report content
# Vector size: 1536 (OpenAI text-embedding-3-small)
# Used by: PM Agent, Designer Agent, Documentation Agent

# Collection: prd_features
# Stores: individual user stories and features
# Used by: QA Agent (for traceability verification)

# Collection: past_projects
# Stores: summaries of previously run pipelines
# Used by: Research Agent (avoid re-researching similar domains)

qdrant_client.create_collection(
    collection_name="research_context",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)
```

#### Retrieval Pattern (used in Designer Agent)

```python
# Instead of injecting 10k-token research report, retrieve top-5 relevant chunks
results = qdrant_client.search(
    collection_name="research_context",
    query_vector=embed("user authentication pain points"),
    query_filter=Filter(
        must=[FieldCondition(key="run_id", match=MatchValue(value=run_id))]
    ),
    limit=5
)
context_chunks = [r.payload["text"] for r in results]
```

---

## 7. Workflow Orchestration

### 7.1 LangGraph State Machine

The pipeline is implemented as a **LangGraph StateGraph** where each node is an agent and edges encode the routing logic.

#### State Definition

```python
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END

class PipelineState(TypedDict):
    run_id: str
    project_brief: dict
    research_report: Optional[dict]
    prd: Optional[dict]
    design_spec: Optional[dict]
    developer_output: Optional[dict]
    qa_output: Optional[dict]
    devops_output: Optional[dict]
    docs_output: Optional[dict]
    qa_iteration: int
    max_qa_iterations: int
    run_state: Literal["RUNNING", "FAILED", "COMPLETE"]
    error: Optional[str]
```

#### Graph Definition

```python
def build_pipeline_graph():
    graph = StateGraph(PipelineState)

    # Add nodes (each is an async agent function)
    graph.add_node("research", run_research_agent)
    graph.add_node("product_manager", run_pm_agent)
    graph.add_node("designer", run_designer_agent)
    graph.add_node("developer", run_developer_agent)
    graph.add_node("qa", run_qa_agent)
    graph.add_node("devops", run_devops_agent)
    graph.add_node("documentation", run_documentation_agent)
    graph.add_node("parallel_final", run_parallel_final)  # Joins devops + docs

    # Linear flow
    graph.set_entry_point("research")
    graph.add_edge("research", "product_manager")
    graph.add_edge("product_manager", "designer")
    graph.add_edge("designer", "developer")
    graph.add_edge("developer", "qa")

    # Conditional routing at QA
    graph.add_conditional_edges(
        "qa",
        route_after_qa,
        {
            "developer": "developer",       # QA FAIL: loop back
            "parallel_final": "parallel_final",  # QA PASS: proceed
            "human_review": END,            # Max iterations exceeded
        }
    )

    graph.add_edge("parallel_final", END)

    return graph.compile()


def route_after_qa(state: PipelineState) -> str:
    qa = state["qa_output"]
    if qa["verdict"] == "PASS":
        return "parallel_final"
    if state["qa_iteration"] >= state["max_qa_iterations"]:
        return "human_review"
    return "developer"
```

#### Parallel Final Stage (DevOps + Docs)

```python
import asyncio

async def run_parallel_final(state: PipelineState) -> PipelineState:
    """Run DevOps and Documentation agents in parallel — no dependency between them."""
    devops_task = asyncio.create_task(run_devops_agent_async(state))
    docs_task = asyncio.create_task(run_documentation_agent_async(state))

    devops_result, docs_result = await asyncio.gather(devops_task, docs_task)

    return {
        **state,
        "devops_output": devops_result,
        "docs_output": docs_result,
        "run_state": "COMPLETE"
    }
```

### 7.2 Agent Execution Pattern

Every agent follows this execution wrapper:

```python
async def agent_executor(agent_name: str, agent_fn, state: PipelineState) -> dict:
    run_id = state["run_id"]

    # 1. Acquire lock
    lock_key = f"agent_lock:{run_id}:{agent_name}"
    if not await redis.set(lock_key, "locked", nx=True, ex=300):
        raise AgentLockError(f"{agent_name} already running for {run_id}")

    # 2. Update status → RUNNING
    await update_agent_status(run_id, agent_name, "RUNNING")
    await publish_event(run_id, "AGENT_STATUS_CHANGED", {"agent": agent_name, "status": "RUNNING"})

    try:
        # 3. Validate input
        validated_input = validate_agent_input(agent_name, state)

        # 4. Run agent
        output = await agent_fn(validated_input)

        # 5. Validate output
        validated_output = validate_agent_output(agent_name, output)

        # 6. Persist to PostgreSQL
        await save_agent_output(run_id, agent_name, validated_output)

        # 7. Store embeddings in Qdrant
        await embed_and_store(run_id, agent_name, validated_output)

        # 8. Update status → COMPLETE
        await update_agent_status(run_id, agent_name, "COMPLETE")
        await publish_event(run_id, "AGENT_STATUS_CHANGED", {"agent": agent_name, "status": "COMPLETE"})

        return validated_output

    except Exception as e:
        await update_agent_status(run_id, agent_name, "FAILED", error=str(e))
        await publish_event(run_id, "AGENT_STATUS_CHANGED", {"agent": agent_name, "status": "FAILED"})
        raise
    finally:
        await redis.delete(lock_key)
```

### 7.3 Human Checkpoint Support

When a stage is configured as a human checkpoint, the pipeline pauses and emits a `PIPELINE_AWAITING_HUMAN` event. The dashboard shows an "Approve" / "Reject" button. On approval, the pipeline resumes; on rejection, the user can provide feedback and the relevant agent re-runs.

```python
async def maybe_checkpoint(state: PipelineState, after_agent: str):
    if after_agent in state["config"]["human_checkpoints"]:
        await update_run_state(state["run_id"], "AWAITING_HUMAN")
        await publish_event(state["run_id"], "PIPELINE_AWAITING_HUMAN", {"after_agent": after_agent})
        # Pipeline suspends here — resumes on /api/v1/runs/{run_id}/approve POST
        await wait_for_approval(state["run_id"])
```

---

## 8. Developer–QA Feedback Loop

### Loop Architecture

```
Developer Agent Output
         │
         ▼
    QA Agent runs
         │
    ┌────┴────┐
    │         │
  PASS       FAIL
    │         │
    ▼         ▼
DevOps    Structured qa_feedback object
  +         │
 Docs       ▼
         Developer Agent (re-run with qa_feedback)
         │
         ▼
    QA Agent runs again
         │
    (repeat up to max_qa_iterations)
         │
    If still FAIL after max iterations:
         ▼
    Human Review Mode
```

### Structured Fix Instructions Format

When QA returns `verdict = "FAIL"`, it produces machine-readable fix instructions that the Developer Agent can parse and act on deterministically:

```json
{
  "fix_instructions": [
    {
      "instruction_id": "FIX-001",
      "type": "missing_implementation",
      "severity": "critical",
      "description": "POST /api/auth/refresh endpoint is missing entirely",
      "target_file": "backend/app/api/routes/auth.py",
      "action": "add_endpoint",
      "spec_reference": "endpoint_id: EP-005",
      "acceptance_criteria": "US-003 criterion 2 must pass"
    },
    {
      "instruction_id": "FIX-002",
      "type": "validation_missing",
      "severity": "high",
      "description": "Email field in POST /api/users accepts invalid email format",
      "target_file": "backend/app/schemas/user.py",
      "action": "add_validator",
      "suggested_code": "email: EmailStr  # use pydantic EmailStr"
    },
    {
      "instruction_id": "FIX-003",
      "type": "edge_case_unhandled",
      "severity": "medium",
      "description": "No error handling when database is unreachable in UserRepository.find_by_id",
      "target_file": "backend/app/repositories/user.py",
      "action": "add_error_handling",
      "suggested_code": "try/except SQLAlchemyError → raise DatabaseUnavailableError"
    }
  ]
}
```

### Developer Agent Re-Run Behavior

On receiving `qa_feedback`, the Developer Agent:
1. Groups fix instructions by `target_file`
2. Retrieves current file content from the artifact store
3. Applies targeted patches (not full rewrites) using the `suggested_code` hints
4. Re-runs self-check for patched files only
5. Returns a new `DeveloperAgentOutput` with `iteration` incremented

### QA Score Calculation

```python
def calculate_qa_score(traceability_matrix, bugs) -> float:
    # Feature coverage component (60% weight)
    total_must_haves = len([s for s in traceability_matrix if s["priority"] == "must-have"])
    covered_must_haves = len([s for s in traceability_matrix
                               if s["priority"] == "must-have" and s["status"] == "COVERED"])
    coverage_score = (covered_must_haves / total_must_haves) * 100 if total_must_haves > 0 else 0

    # Bug penalty component (40% weight)
    severity_weights = {"critical": 20, "high": 10, "medium": 5, "low": 2}
    total_penalty = sum(severity_weights.get(b["severity"], 0) for b in bugs if b["status"] == "open")
    bug_score = max(0, 100 - total_penalty)

    return round((coverage_score * 0.6) + (bug_score * 0.4), 2)
```

---

## 9. Full Tech Stack

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| Next.js | 14.x (App Router) | Main dashboard UI framework |
| TypeScript | 5.x | Type safety across all UI code |
| Tailwind CSS | 3.x | Utility-first styling |
| Zustand | 4.x | Global client state management |
| React Query (TanStack) | 5.x | Server state, caching, background refetching |
| Socket.io-client | 4.x | Real-time WebSocket connection to backend |
| Framer Motion | 11.x | Agent activation animations, transitions |
| Prism / Shiki | latest | Syntax highlighting in Developer Agent output |
| Recharts | 2.x | QA score meter and trend charts |
| JetBrains Mono | — | Monospace font (logs, code, timers) |
| Syne | — | Display/heading font |

### Backend

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Primary backend language |
| FastAPI | 0.110+ | REST API server + WebSocket |
| Uvicorn + Gunicorn | latest | ASGI server |
| Pydantic v2 | 2.x | Request/response validation and JSON schema generation |
| SQLAlchemy | 2.x | ORM for PostgreSQL |
| Alembic | 1.x | Database migrations |
| asyncpg | 0.29+ | Async PostgreSQL driver |
| Redis-py (async) | 5.x | Redis client for pub/sub and caching |
| Celery | 5.x | Background task queue for heavy agent runs |

### AI / Agent Framework

| Technology | Version | Purpose |
|---|---|---|
| LangChain | 0.2+ | LLM abstraction, tool calling, chains |
| LangGraph | 0.1+ | Multi-agent state machine orchestration |
| OpenAI SDK | 1.x | GPT-4o for all agent LLM calls |
| Qdrant Client | 1.x | Vector DB SDK for embeddings storage/retrieval |
| tiktoken | latest | Token counting for context window management |

### Data Layer

| Technology | Version | Purpose |
|---|---|---|
| PostgreSQL | 15+ | Persistent state, artifact storage |
| Redis | 7.x | Pub/sub event bus, ephemeral cache, locks |
| Qdrant | 1.x | Vector DB for semantic memory (RAG) |

### DevOps / Infrastructure

| Technology | Version | Purpose |
|---|---|---|
| Docker | 24+ | Containerization of all services |
| Docker Compose | 2.x | Local multi-service orchestration |
| GitHub Actions | — | CI/CD pipelines |
| Nginx | 1.25+ | Reverse proxy, WebSocket proxying |
| Render / Railway | — | Cloud deployment targets |
| Vercel | — | Next.js frontend deployment |

### Testing

| Technology | Version | Purpose |
|---|---|---|
| Pytest | 8.x | Backend unit and integration tests |
| pytest-asyncio | latest | Async test support |
| Vitest | 1.x | Frontend unit tests |
| Playwright | 1.x | E2E testing of dashboard |
| httpx | 0.27+ | HTTP client for FastAPI test client |

---

## 10. Dashboard System Design

### Overview

The dashboard is a **real-time mission control interface** built in Next.js 14 with App Router and WebSocket connections. Users submit an idea and watch the AI workforce build their product live.

### Color System

```css
:root {
  --bg-base:        #0A0A0F;   /* near-black base */
  --surface:        #111118;   /* card backgrounds */
  --surface-hover:  #1A1A24;   /* elevated/hovered cards */
  --border:         #2A2A3A;   /* subtle dividers */
  --accent:         #00FF88;   /* terminal green — primary action */
  --accent-dim:     #00FF8833; /* glows and pulse effects */
  --warning:        #F59E0B;   /* amber — assumptions, warnings */
  --error:          #EF4444;   /* red — failures, critical bugs */
  --success:        #10B981;   /* teal — complete states */
  --text-primary:   #F0F0F8;   /* near-white */
  --text-secondary: #8888AA;   /* muted labels */
  --text-code:      #A8FF78;   /* code blocks, JSON */
}

/* Per-agent accent colors for active state glows */
--agent-research:   #3B82F6;   /* blue */
--agent-pm:         #8B5CF6;   /* purple */
--agent-designer:   #EC4899;   /* pink */
--agent-developer:  #06B6D4;   /* cyan */
--agent-qa:         #F59E0B;   /* amber */
--agent-devops:     #F97316;   /* orange */
--agent-docs:       #10B981;   /* teal */
```

### Layout (1440px Desktop)

```
┌──────────────────────────────────────────────────────────────────────┐
│  TOPBAR                                                              │
│  [⬡⬡] ADWF  │  Project Title (editable)  ● RUNNING  │  00:04:32  │
├────────────────┬───────────────────────────────┬────────────────────┤
│                │                               │                    │
│  LEFT RAIL     │  MAIN CANVAS                  │  RIGHT PANEL       │
│  (240px)       │  (fluid)                      │  (320px)           │
│                │                               │                    │
│  ● Research ▶  │  ┌─ Active Agent Header ────┐  │  Global State JSON │
│  ○ PM          │  │ 🔵 Research Agent         │  │  (collapsible)    │
│  ○ Designer    │  │ Stage 4 of 7 — Competitor │  │                    │
│  ○ Developer   │  │ Analysis...               │  │  ──────────────── │
│  ○ QA          │  └───────────────────────────┘  │                    │
│  ○ DevOps  ∥   │  ┌─ Output Preview ─────────┐  │  Live Log Stream  │
│  ○ Docs    ∥   │  │ [live-populating table]   │  │  (terminal-style) │
│                │  └───────────────────────────┘  │                    │
│  ── Pipeline ──│                               │  ──────────────── │
│  [=====>    ]  │                               │  QA Score Meter   │
│                │                               │  ◯ 87/100         │
└────────────────┴───────────────────────────────┴────────────────────┘
│  [  Describe your product idea...          ] [▶ Run Pipeline] [⬇ ZIP]│
└──────────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
src/
├── app/
│   ├── page.tsx                  # Root — redirects to /dashboard
│   ├── dashboard/
│   │   └── page.tsx              # Main dashboard layout
│   └── api/
│       └── ws/route.ts           # WebSocket upgrade handler
├── components/
│   ├── layout/
│   │   ├── TopBar.tsx            # Logo, project title, status, timer
│   │   └── BottomInputBar.tsx    # Idea input + Run/Stop/Export buttons
│   ├── pipeline/
│   │   ├── LeftRail.tsx          # Agent list with live statuses
│   │   ├── AgentCard.tsx         # Individual agent card with glow
│   │   ├── ParallelBadge.tsx     # ∥ indicator between parallel agents
│   │   └── PipelineProgress.tsx  # Overall progress bar
│   ├── canvas/
│   │   ├── MainCanvas.tsx        # Active agent view container
│   │   ├── AgentHeader.tsx       # Agent name, stage, thinking indicator
│   │   ├── OutputPreview.tsx     # Dynamic output renderer per agent
│   │   └── outputs/
│   │       ├── ResearchOutput.tsx    # Personas table, competitor matrix
│   │       ├── PMOutput.tsx          # Feature list with priorities
│   │       ├── DesignerOutput.tsx    # Screen breakdown cards
│   │       ├── DeveloperOutput.tsx   # Syntax-highlighted code blocks
│   │       ├── QAOutput.tsx          # Traceability matrix with PASS/FAIL
│   │       ├── DevOpsOutput.tsx      # File tree view
│   │       └── DocsOutput.tsx        # Rendered markdown preview
│   └── rightpanel/
│       ├── RightPanel.tsx        # Container for 3 right panel sections
│       ├── GlobalStateViewer.tsx # Collapsible JSON tree with amber flash
│       ├── LiveLogStream.tsx     # Terminal-style colored log stream
│       └── QAScoreMeter.tsx      # Circular arc meter + bug breakdown
├── hooks/
│   ├── usePipelineSocket.ts      # WebSocket connection + event handling
│   ├── usePipelineRun.ts         # Run initiation and status polling
│   └── useAgentOutput.ts         # Fetch and cache agent-specific outputs
├── store/
│   └── pipelineStore.ts          # Zustand global state
├── lib/
│   ├── api.ts                    # Typed API client (fetch wrapper)
│   ├── socket.ts                 # Socket.io singleton
│   └── schemas.ts                # Zod schemas matching backend JSON schemas
└── styles/
    └── globals.css               # CSS variables, base styles, animations
```

### WebSocket Event Handling

```typescript
// hooks/usePipelineSocket.ts
import { useEffect } from "react";
import { usePipelineStore } from "@/store/pipelineStore";
import { io } from "socket.io-client";

export function usePipelineSocket(runId: string) {
  const { setAgentStatus, appendLog, setQAScore, setGlobalState } = usePipelineStore();

  useEffect(() => {
    const socket = io(process.env.NEXT_PUBLIC_WS_URL!, {
      query: { run_id: runId },
    });

    socket.on("AGENT_STATUS_CHANGED", ({ agent_name, new_status }) => {
      setAgentStatus(agent_name, new_status);
    });

    socket.on("AGENT_LOG_LINE", ({ agent_name, line, level }) => {
      appendLog({ agent: agent_name, text: line, level, timestamp: Date.now() });
    });

    socket.on("QA_VERDICT", ({ qa_score, verdict, bugs_count }) => {
      setQAScore({ score: qa_score, verdict, bugsCount: bugs_count });
    });

    socket.on("GLOBAL_STATE_UPDATED", ({ state }) => {
      setGlobalState(state);
    });

    return () => { socket.disconnect(); };
  }, [runId]);
}
```

### Key Animations

```css
/* Agent activation pulse */
@keyframes agentPulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--accent-dim); }
  50%       { box-shadow: 0 0 20px 8px var(--accent-dim); }
}

/* Text streaming (typewriter) */
@keyframes typeIn {
  from { opacity: 0; transform: translateY(2px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* JSON field update flash */
@keyframes fieldFlash {
  0%   { background-color: #F59E0B33; }
  100% { background-color: transparent; }
}

/* QA routing arrow (Developer ← QA) */
@keyframes routingArrow {
  0%   { stroke-dashoffset: 100; opacity: 0; }
  30%  { opacity: 1; }
  100% { stroke-dashoffset: 0; opacity: 1; }
}
```

### Dashboard States

**State 1 — Idle:** Clean layout, all agents PENDING (dim), idea input centered with placeholder, subtle dot-grid background pattern.

**State 2 — Running:** One agent RUNNING (glowing with agent-specific accent), logs streaming, output preview building live in main canvas.

**State 3 — QA Failure Loop:** QA card shows FAILED (amber border), animated arrow from QA back to Developer in left rail, iteration counter shows "Iteration 2/3", Developer re-activates.

**State 4 — Complete:** All agents green checkmarks, top bar turns `--success` teal, coherence score displayed (e.g. 94/100), "⬇ Export ZIP" button glows and pulses, downloadable artifacts listed in main canvas.

---

## 11. Auto-Documentation System

### Philosophy

Documentation is not an afterthought — it is **generated directly from the same JSON contracts** that were used to build the product. This guarantees:
- API docs always match implemented routes (sourced from `design_spec.api_spec`)
- Feature descriptions always match what was scoped (sourced from `prd.features`)
- Known issues are always current (sourced from `qa_output.bugs`)

### Generation Pipeline

```python
class DocumentationAgent:
    async def generate_readme(self, inputs: DocumentationAgentInput) -> str:
        """Generate README.md from structured inputs, not free-form LLM."""
        prd = inputs.prd
        devops = inputs.devops_output

        sections = [
            self._render_header(prd.product_vision),
            self._render_features(prd.features.mvp),
            self._render_tech_stack(inputs.design_spec.system_architecture),
            self._render_quickstart(devops.startup_commands, devops.environment_variables),
            self._render_environment_vars(devops.environment_variables),
        ]
        return "\n\n".join(sections)

    async def generate_api_reference(self, inputs: DocumentationAgentInput) -> str:
        """Each endpoint section is auto-generated from api_spec JSON."""
        lines = ["# API Reference\n"]
        for endpoint in inputs.design_spec.api_spec:
            lines.append(f"## {endpoint['method']} {endpoint['path']}")
            lines.append(f"**Auth Required:** {'Yes' if endpoint['auth_required'] else 'No'}")
            lines.append(f"\n**Request Body:**\n```json\n{json.dumps(endpoint['request_body']['schema'], indent=2)}\n```")
            for status, response in endpoint['responses'].items():
                lines.append(f"\n**{status} Response:**\n```json\n{json.dumps(response['example'], indent=2)}\n```")
        return "\n".join(lines)
```

### Output Files

| File | Source Data | Description |
|---|---|---|
| `README.md` | prd + devops_output | Quick start, features, env vars, 3-command setup |
| `API_REFERENCE.md` | design_spec.api_spec | Every endpoint with examples |
| `ARCHITECTURE.md` | design_spec + agent decision logs | System design and trade-offs |
| `KNOWN_ISSUES.md` | qa_output.bugs (open) | Open bugs, severity, workarounds |
| `CONTRIBUTING.md` | devops_output.startup_commands | Dev setup, test commands, PR guide |
| `CHANGELOG.md` | All agent outputs | What was built in this pipeline run |

---

## 12. DevOps & Deployment Architecture

### Repository Structure

```
adwf-project/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Runs on every PR
│       └── deploy.yml             # Runs on merge to main
├── frontend/                      # Next.js 14 app
│   ├── src/
│   ├── Dockerfile
│   ├── .env.example
│   └── package.json
├── backend/                       # FastAPI app
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── runs.py        # Pipeline run CRUD
│   │   │   │   ├── agents.py      # Agent status endpoints
│   │   │   │   └── artifacts.py   # Artifact download
│   │   │   └── websocket.py       # WebSocket handler
│   │   ├── agents/
│   │   │   ├── orchestrator.py
│   │   │   ├── research.py
│   │   │   ├── product_manager.py
│   │   │   ├── designer.py
│   │   │   ├── developer.py
│   │   │   ├── qa.py
│   │   │   ├── devops.py
│   │   │   └── documentation.py
│   │   ├── core/
│   │   │   ├── config.py          # Settings (pydantic-settings)
│   │   │   ├── database.py        # SQLAlchemy async engine
│   │   │   ├── redis.py           # Redis connection
│   │   │   └── qdrant.py          # Qdrant client
│   │   ├── models/                # SQLAlchemy ORM models
│   │   ├── schemas/               # Pydantic request/response schemas
│   │   ├── workflow/
│   │   │   ├── graph.py           # LangGraph StateGraph definition
│   │   │   ├── executor.py        # Agent execution wrapper
│   │   │   └── state.py           # PipelineState TypedDict
│   │   └── main.py
│   ├── alembic/
│   │   └── versions/
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── docker-compose.yml             # Full local stack
├── docker-compose.prod.yml        # Production overrides
└── README.md
```

### Dockerfile — Backend (FastAPI)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS dev
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM deps AS prod
COPY . .
RUN addgroup --system app && adduser --system --group app
USER app
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--timeout", "120"]
```

### Dockerfile — Frontend (Next.js)

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS base
WORKDIR /app

FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
RUN addgroup --system nodejs && adduser --system --group nextjs
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

### docker-compose.yml (Local Dev)

```yaml
version: "3.9"

services:
  frontend:
    build:
      context: ./frontend
      target: dev
    ports:
      - "3000:3000"
    volumes:
      - ./frontend/src:/app/src
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_WS_URL=http://localhost:8000
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      target: dev
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
    env_file:
      - ./backend/.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: adwf
      POSTGRES_PASSWORD: adwf_dev_password
      POSTGRES_DB: adwf
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U adwf"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - frontend
      - backend

volumes:
  postgres_data:
  qdrant_data:
```

### GitHub Actions — CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main, develop]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: adwf
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: adwf_test
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run migrations
        run: alembic upgrade head
        working-directory: backend
        env:
          DATABASE_URL: postgresql+asyncpg://adwf:test_password@localhost:5432/adwf_test
      - name: Run tests
        run: pytest tests/ -v --cov=app --cov-report=xml
        working-directory: backend
        env:
          DATABASE_URL: postgresql+asyncpg://adwf:test_password@localhost:5432/adwf_test
          REDIS_URL: redis://localhost:6379
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY_TEST }}

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm run typecheck
        working-directory: frontend
      - run: npm run test
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
```

### GitHub Actions — Deploy Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Render
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_BACKEND }}"

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./frontend
          vercel-args: "--prod"
```

---

## 13. Phase-Wise Implementation Plan

### Phase 0 — Foundation (Week 1)

**Goal:** Skeleton up, services running, data layer proven.

- [ ] Initialize monorepo with frontend (Next.js) and backend (FastAPI)
- [ ] Set up Docker Compose with PostgreSQL, Redis, Qdrant
- [ ] Run initial Alembic migration with all tables
- [ ] Set up GitHub Actions CI (linting + type check only)
- [ ] Create FastAPI app skeleton: `/health`, `/ready`, `/api/v1/runs` (stub)
- [ ] Create Next.js app skeleton: dashboard layout, color system, font imports
- [ ] Implement Zustand store structure (empty)
- [ ] Implement WebSocket server (FastAPI) and client hook (Next.js)
- [ ] Verify WebSocket connection: backend → Redis pub/sub → frontend
- [ ] **Milestone:** `docker-compose up` runs all 5 services; WebSocket test message appears in browser

### Phase 1 — Core Agents + State Machine (Weeks 2–3)

**Goal:** End-to-end pipeline runs with real LLM calls for first 3 agents.

- [ ] Implement LangGraph graph with all node stubs
- [ ] Implement Orchestrator: normalize idea, initialize global_state
- [ ] Implement Research Agent: full LLM prompt chain, all 7 research tasks, Qdrant storage
- [ ] Implement PM Agent: PRD generation from research_report
- [ ] Implement agent execution wrapper (lock, status, events, persist)
- [ ] Connect PostgreSQL persistence for agent_runs and artifacts
- [ ] Connect Redis pub/sub event emission from executor
- [ ] Frontend: Left rail renders agent statuses from WebSocket
- [ ] Frontend: Main canvas renders Research output (persona table)
- [ ] Frontend: Live log stream renders AGENT_LOG_LINE events
- [ ] **Milestone:** Submit "Duolingo for cooking" → Research + PM agents complete → dashboard shows live output

### Phase 2 — Designer + Developer Agents (Week 4)

**Goal:** Design spec and code artifacts generated end-to-end.

- [ ] Implement Designer Agent: all 4 design tasks, full JSON output
- [ ] Implement Developer Agent: 5-step protocol, file generation
- [ ] Implement artifact ZIP packing (all files → downloadable archive)
- [ ] Frontend: Designer output view (screen breakdown cards)
- [ ] Frontend: Developer output view (syntax-highlighted code blocks, file tree)
- [ ] Frontend: Export ZIP button functional
- [ ] **Milestone:** Full pipeline Research → PM → Designer → Developer completes; ZIP download works

### Phase 3 — QA + Feedback Loop (Week 5)

**Goal:** QA agent functional, feedback loop runs, pipeline self-heals.

- [ ] Implement QA Agent: traceability matrix, bug detection, scoring, routing
- [ ] Implement Developer Agent re-run with qa_feedback parsing
- [ ] Implement Orchestrator retry routing logic in LangGraph
- [ ] Frontend: QA output view (traceability matrix with PASS/FAIL badges)
- [ ] Frontend: QA score meter (circular arc, bug count chips)
- [ ] Frontend: QA routing loop animation (arrow from QA back to Developer)
- [ ] Frontend: Iteration counter in TopBar
- [ ] **Milestone:** Pipeline runs 3 QA iterations autonomously; dashboard shows routing loop animation

### Phase 4 — DevOps + Documentation Agents (Week 6)

**Goal:** Parallel final stage complete; full output ZIP.

- [ ] Implement DevOps Agent: Dockerfile, docker-compose, CI/CD, env template
- [ ] Implement Documentation Agent: all 6 documents from structured inputs
- [ ] Implement parallel final stage (asyncio.gather)
- [ ] Frontend: DevOps output view (file tree with generated files)
- [ ] Frontend: Docs output view (rendered markdown preview)
- [ ] Frontend: Complete state (top bar teal, confetti, artifact list)
- [ ] **Milestone:** Full 8-agent pipeline completes; downloadable ZIP contains all code + docs

### Phase 5 — Polish, Testing, Deploy (Week 7)

**Goal:** Production-ready, deployed, tested.

- [ ] Write backend test suite (pytest): all agents mocked, schema validation, routing logic
- [ ] Write frontend tests (Vitest): store, hooks, key components
- [ ] Playwright E2E test: full pipeline submission to completion
- [ ] Performance: WebSocket latency < 500ms, dashboard FPS > 30 during animations
- [ ] Set up Render (backend), Vercel (frontend), Render PostgreSQL + Redis
- [ ] Configure production environment variables
- [ ] Final CI/CD deploy pipeline tested
- [ ] Human checkpoint feature (approve/reject buttons in dashboard)
- [ ] **Milestone:** `adwf.yourdomain.com` live; full pipeline runs in production

---

## 14. MECE Team Task Division

> **MECE** = Mutually Exclusive, Collectively Exhaustive. Each team member owns a non-overlapping domain. No task belongs to two people. No task is unassigned.

### Nisarg — Workflow Engine & Agent Orchestration

**Primary domain:** Everything related to the LangGraph state machine, agent execution, and inter-agent data flow.

**Owns:**
- `backend/app/workflow/` — entire workflow engine (`graph.py`, `executor.py`, `state.py`)
- `backend/app/agents/orchestrator.py` — Orchestrator agent logic
- LangGraph graph definition, conditional edges, retry logic
- Agent execution wrapper (lock, event emission, persist, retry)
- QA feedback routing logic in the graph
- Parallel final stage (asyncio.gather for DevOps + Docs)
- Human checkpoint suspension/resumption logic
- Redis pub/sub emission from workflow layer
- Background task queue integration (Celery for long-running pipelines)
- Agent input/output validation (Pydantic schemas for all agents)

**Key Deliverables:**
- Working LangGraph pipeline from Research → Documentation
- QA retry loop (max 3 iterations) functional
- `PipelineState` TypedDict complete and validated
- All agent JSON schemas defined in `backend/app/schemas/`

**Does NOT own:** Individual agent LLM logic, frontend, database schema, CI/CD

---

### Aditya — AI Agent Implementation (Research, PM, Designer)

**Primary domain:** The first three agents — the intelligence and design layers.

**Owns:**
- `backend/app/agents/research.py` — full Research Agent LLM chain
- `backend/app/agents/product_manager.py` — full PM Agent LLM chain
- `backend/app/agents/designer.py` — full Designer Agent LLM chain
- LangChain prompt templates for all three agents
- Tool integrations: web_search, SERP API, Crunchbase lookup
- Qdrant storage/retrieval for research and PRD embeddings
- RAG retrieval patterns for Designer Agent context augmentation
- Token management: chunking large research outputs before embedding
- Prompt engineering: system prompts, few-shot examples for each agent
- Output parser implementations (structured JSON extraction from LLM)

**Key Deliverables:**
- Research Agent that produces complete `ResearchAgentOutput` JSON
- PM Agent that produces valid `PMAgentOutput` with user stories in Given/When/Then format
- Designer Agent that produces complete `DesignerAgentOutput` with API spec and data models
- All three agents handle failures gracefully (retry on malformed LLM output)

**Does NOT own:** Developer/QA/DevOps/Docs agents, workflow engine, frontend, database schema

---

### Swanandi — Frontend Dashboard & Real-Time UI

**Primary domain:** The entire Next.js dashboard, all UI components, real-time state, and animations.

**Owns:**
- `frontend/src/` — entire frontend codebase
- Component architecture (all components listed in Section 10)
- Zustand store design and implementation
- WebSocket client hook (`usePipelineSocket.ts`)
- All agent-specific output renderers (ResearchOutput, PMOutput, DeveloperOutput, QAOutput, etc.)
- Animation system (agent pulse, text streaming, routing arrow, completion confetti)
- Color system implementation (CSS variables, Tailwind config)
- Responsive layout (1440px → 768px → mobile)
- Export ZIP download functionality
- Human checkpoint UI (approve/reject buttons)
- Accessibility (keyboard navigation, screen reader labels)
- Vitest unit tests for store and hooks
- Playwright E2E tests for full pipeline flow

**Key Deliverables:**
- All 4 dashboard states fully designed and functional (Idle, Running, QA Loop, Complete)
- WebSocket → UI latency < 500ms
- QA routing arrow animation working
- Export ZIP button functional
- Full responsive behavior across breakpoints

**Does NOT own:** Backend agents, workflow engine, database, CI/CD

---

### Anshul — Backend Infrastructure, Developer/QA/DevOps/Docs Agents & CI/CD

**Primary domain:** The last four agents, all infrastructure, database layer, and deployment.

**Owns:**
- `backend/app/agents/developer.py` — Developer Agent (5-step protocol)
- `backend/app/agents/qa.py` — QA Agent (traceability, bug detection, routing decision)
- `backend/app/agents/devops.py` — DevOps Agent (Dockerfile, compose, CI/CD gen)
- `backend/app/agents/documentation.py` — Documentation Agent (all 6 docs)
- `backend/app/core/` — database, Redis, Qdrant connection setup
- `backend/app/models/` — SQLAlchemy ORM models
- Alembic migrations (all versions)
- `backend/app/api/routes/` — all FastAPI route handlers
- FastAPI WebSocket server handler
- PostgreSQL schema design and migration history
- Redis key patterns and TTL management
- Qdrant collection initialization
- `docker-compose.yml` and `docker-compose.prod.yml`
- `Dockerfile` for both frontend and backend
- `.github/workflows/ci.yml` and `deploy.yml`
- Render/Vercel deployment configuration
- Environment variable management (`.env.example`, secrets)
- Pytest backend test suite (all agents mocked)
- Nginx reverse proxy config

**Key Deliverables:**
- All 4 agents produce valid output JSON
- QA Agent produces correct `routing_decision` field (routes to developer vs devops+docs)
- Developer Agent's self-check catches schema mismatches
- `docker-compose up` starts entire stack from scratch in < 2 minutes
- CI pipeline passes on every PR
- Production deployment on Render + Vercel functional

**Does NOT own:** Frontend, Research/PM/Designer agents, LangGraph workflow engine internals

---

### Cross-Team Interfaces

| Interface | Owner A | Owner B | Contract |
|---|---|---|---|
| Agent output JSON schemas | Aditya (produces) | Nisarg (validates in executor) | Pydantic models in `backend/app/schemas/` |
| WebSocket event spec | Anshul (emits from backend) | Swanandi (consumes in frontend) | Event type enum in `backend/app/core/events.py` |
| QA routing decision | Anshul (QA Agent) | Nisarg (LangGraph router) | `routing_decision.route_to` field in `QAAgentOutput` |
| Developer output → QA | Anshul (both) | — | Internal; Anshul owns both sides |
| Qdrant collection IDs | Aditya (creates collections) | Anshul (core/qdrant.py setup) | Collection names documented in `backend/app/core/qdrant.py` |

---

## 15. Risks, Constraints & Mitigations

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| LLM produces invalid JSON (fails schema validation) | High | High | Retry up to 3× with stricter prompt; fallback to `json_repair` library |
| LLM context window exceeded for large research outputs | Medium | High | Chunk outputs before embedding; use RAG retrieval instead of full injection |
| OpenAI API rate limits hit during parallel pipeline runs | Medium | Medium | Implement exponential backoff; queue requests via Celery; use tier-appropriate model |
| WebSocket connection drops mid-pipeline | Medium | Medium | Reconnect logic with run_id resubscription; dashboard polls HTTP as fallback |
| QA feedback loop never converges (cycles indefinitely) | Low | High | Hard cap at `max_qa_iterations` (default 3); route to human review beyond cap |
| Agent generates code with security vulnerabilities | Medium | High | QA Agent includes security check pass; add static analysis (bandit) in CI |
| Qdrant vector storage grows unbounded | Low | Medium | TTL policy on old pipeline embeddings; prune after 30 days |

### Constraints

| Constraint | Description |
|---|---|
| **LLM Costs** | Each full pipeline run costs approximately $0.50–$2.00 in GPT-4o tokens. Rate-limit users in production. |
| **Pipeline Duration** | Full pipeline takes 10–30 minutes depending on idea complexity. Must communicate progress clearly to user. |
| **No Real Code Execution** | Developer Agent generates code artifacts but does not execute them. QA is logic-based, not runtime-based. |
| **No Real Deployment** | DevOps Agent generates deployment configs but does not execute actual cloud deployments. |
| **Stateless LLM** | Each LLM call is stateless; all context must be injected explicitly. Managed by the RAG + global state layers. |

### Mitigation: Prompt Reliability

```python
# All agent prompts follow this structure for reliable JSON output:
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

## 16. Future Scope

### v1.1 — Customizable Pipelines
- Drag-and-drop pipeline builder in dashboard: users add, remove, and reorder agents
- Agent configuration panels: set custom prompts, skip certain tasks, inject domain context
- Save pipeline templates: "Startup MVP template", "API-only template", "Mobile-first template"

### v1.2 — Real Code Execution
- Integrate E2B sandbox (cloud code execution environment)
- Developer Agent writes code → E2B runs it → real test results feed back to QA Agent
- QA Agent runs actual pytest suite, not just logical analysis
- Error stack traces from real execution as structured feedback

### v2.0 — Team Collaboration Mode
- Multiple users can observe the same pipeline run simultaneously
- Human-in-the-loop at any agent: annotate outputs, suggest changes, continue
- Role-based access: stakeholders see high-level outputs; developers see technical artifacts
- Async approval workflows: Slack/email notification for human checkpoints

### v2.1 — Memory Across Projects
- Cross-project knowledge base: agents learn from past pipeline runs
- "You've built a SaaS before — here's what worked in the Auth module"
- Competitor database grows with each Research Agent run
- Component library accumulates reusable implementations across runs

### v3.0 — Marketplace
- Community-contributed agents: specialized agents for fintech, healthcare, edtech
- Shared pipeline templates
- Output marketplace: sell generated MVPs or component libraries

### Long-Term
- Real cloud deployment (DevOps Agent executes actual `terraform apply`)
- Multi-model support: different LLMs for different agents based on cost/capability trade-off
- Voice input: describe idea in natural speech, pipeline transcribes and normalizes
- Mobile app: submit ideas from phone, monitor pipeline on the go

---

## 17. Appendix — Environment Variables & Config

### Backend `.env.example`

```bash
# Database
DATABASE_URL=postgresql+asyncpg://adwf:your_password@localhost:5432/adwf
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                         # Leave empty for local

# OpenAI
OPENAI_API_KEY=sk-...                   # Required
OPENAI_MODEL=gpt-4o                     # Default model for all agents
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Application
SECRET_KEY=your-32-char-secret-key      # For JWT signing
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
LOG_LEVEL=INFO

# Pipeline Config
MAX_QA_ITERATIONS=3
DEFAULT_TARGET_PLATFORM=web
ARTIFACT_STORAGE_PATH=/app/artifacts    # Local FS path for ZIP artifacts

# Optional: External APIs for Research Agent
SERP_API_KEY=                           # For web search tool
CRUNCHBASE_API_KEY=                     # For market data
```

### Frontend `.env.example`

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=AI Digital Workforce
```

---

*Document version 1.0.0 — Generated for Antigravity by ADWF project team.*  
*All JSON schemas, component structures, and workflow definitions in this document are implementation-ready and should be used as the single source of truth during development.*

---

**END OF DOCUMENT**
