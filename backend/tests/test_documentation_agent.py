from __future__ import annotations

import uuid

import pytest

from app.agents.documentation import run_documentation_agent


@pytest.mark.asyncio
async def test_run_documentation_agent_builds_all_documents_from_structured_outputs() -> None:
    run_id = uuid.uuid4()
    input_data = {
        "run_id": str(run_id),
        "research_report": {
            "problem_statement": {
                "core_problem": "Teams need a faster way to ship product documentation.",
                "affected_users": "Small product teams",
                "current_solutions_fail_because": "They are fragmented and manual.",
                "opportunity_window": "Automated generation pipelines are now viable.",
            },
            "market": {
                "tam_usd": 1000000,
                "sam_usd": 250000,
                "som_usd": 50000,
                "industry": "Developer Tools",
                "growth_rate_yoy_percent": 18.5,
                "key_trends": ["Automation", "AI-assisted workflows"],
            },
            "personas": [
                {
                    "name": "Avery",
                    "age_range": "25-34",
                    "occupation": "Product Manager",
                    "goals": ["Ship faster"],
                    "frustrations": ["Manual docs"],
                    "tech_savviness": "high",
                    "primary_device": "Laptop",
                }
            ],
            "pain_points": [
                {
                    "pain": "Documentation drifts from implementation",
                    "severity": "high",
                    "frequency": "frequent",
                    "existing_workaround": "Manual reviews",
                }
            ],
            "competitors": [],
            "viability": {
                "revenue_models": ["Subscription"],
                "recommended_model": "Subscription",
                "estimated_arpu": "$40",
                "go_to_market_strategy": "Direct sales",
                "viability_score": 8,
            },
            "feasibility": {
                "technical_risks": ["Integration drift"],
                "complexity": "medium",
                "estimated_mvp_weeks": 6,
                "key_dependencies": ["LLM provider", "Workflow engine"],
                "feasibility_score": 7,
            },
        },
        "prd": {
            "product_vision": {
                "elevator_pitch": "Task Forge",
                "target_user": "small product teams",
                "core_value_proposition": "Turn structured inputs into shippable documentation and output artifacts.",
                "success_definition": "Teams can publish docs without manual drafting.",
            },
            "user_stories": [],
            "features": {
                "mvp": [],
                "v1_1": [],
                "v2_0": [],
            },
            "budget_estimate": {
                "mvp_engineer_weeks": 4,
                "mvp_cost_usd_range": "$20k-$30k",
                "assumptions": ["Single environment"],
            },
            "user_flow": [],
        },
        "design_spec": {
            "screens": [],
            "interaction_flows": [],
            "system_architecture": {
                "frontend": "Next.js 14 dashboard",
                "backend": "FastAPI workflow service",
                "database": "PostgreSQL",
                "cache": "Redis",
                "external_services": ["Qdrant"],
                "communication_patterns": {
                    "frontend_to_backend": "HTTP + WebSocket",
                    "backend_to_workers": "Celery",
                },
            },
            "api_spec": [
                {
                    "endpoint_id": "api-items-list",
                    "method": "GET",
                    "path": "/api/v1/items",
                    "auth_required": True,
                    "description": "List items",
                    "request_body": {
                        "content_type": "application/json",
                        "request_schema": {},
                        "validation_rules": ["No request body"],
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "response_schema": {},
                            "example": {"items": []},
                        }
                    },
                    "rate_limit": "60 requests/minute",
                    "maps_to_user_stories": [],
                },
                {
                    "endpoint_id": "api-items-create",
                    "method": "POST",
                    "path": "/api/v1/items",
                    "auth_required": True,
                    "description": "Create an item",
                    "request_body": {
                        "content_type": "application/json",
                        "request_schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "priority": {"type": "integer", "minimum": 1},
                            },
                            "required": ["name"],
                        },
                        "validation_rules": ["name is required", "priority must be positive"],
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "response_schema": {},
                            "example": {"id": "item-1", "name": "Demo"},
                        },
                        "400": {
                            "description": "Validation error",
                            "response_schema": {},
                            "example": {"error": "Invalid input"},
                        },
                    },
                    "rate_limit": "60 requests/minute",
                    "maps_to_user_stories": [],
                },
            ],
            "data_models": [],
        },
        "developer_output": {
            "run_id": str(run_id),
            "task_id": f"dev-{run_id}",
            "status": "completed",
            "summary": "Developer output summary",
            "files_created": [
                {
                    "path": "frontend/src/app/page.tsx",
                    "purpose": "Landing page",
                    "content": "export default function Page() { return null; }",
                    "language": "typescript",
                    "maps_to_endpoint_ids": [],
                    "maps_to_screen_ids": [],
                }
            ],
            "features_implemented": [
                "Real-time task creation",
                "Dashboard overview",
            ],
            "features_skipped": [
                {
                    "feature": "Bulk edit",
                    "reason": "Not implemented in the current release",
                }
            ],
            "tests_written": ["tests/test_workflow.py"],
            "tech_debt_logged": ["Document provider credentials and rollout notes"],
            "self_check_results": {
                "schema_consistent": True,
                "all_routes_implemented": True,
                "feature_coverage_percent": 100,
                "test_coverage_percent": 80,
                "issues_found": [],
            },
            "implementation_plan": {
                "project_slug": "task-forge",
                "tech_stack_confirmation": ["Frontend: Next.js 14", "Backend: FastAPI"],
                "dependency_ordered_build_sequence": [],
                "key_architectural_decisions": ["Use API-first design"],
                "required_files": [],
                "phase2_file_manifest": [],
                "mapped_user_story_ids": [],
                "technical_execution_plan": [],
                "backend_execution_plan": [],
                "frontend_execution_plan": [],
                "data_and_infra_plan": [],
                "testing_and_rollout_plan": [],
                "risk_mitigation_plan": ["Keep feature flags for unfinished capabilities"],
            },
            "generation_phases": [],
        },
        "qa_output": {
            "run_id": str(run_id),
            "verdict": "FAIL",
            "qa_score": 72.5,
            "iteration": 1,
            "traceability_matrix": [],
            "cross_document_issues": [],
            "journey_simulations": [],
            "bugs": [
                {
                    "bug_id": "QA-001",
                    "severity": "high",
                    "title": "Missing loading state",
                    "description": "Users may see a blank screen during async loading.",
                    "affected_file": "frontend/src/app/page.tsx",
                    "affected_user_story": None,
                    "root_cause_phase": "developer",
                    "fix_owner": "developer",
                    "reproduction_steps": ["Open the dashboard"],
                    "suggested_fix": "Add a loading state.",
                    "status": "open",
                },
                {
                    "bug_id": "QA-002",
                    "severity": "low",
                    "title": "Copy update",
                    "description": "Minor copy update requested.",
                    "affected_file": "README.md",
                    "affected_user_story": None,
                    "root_cause_phase": "product_manager",
                    "fix_owner": "product_manager",
                    "reproduction_steps": ["Open the README"],
                    "suggested_fix": "Adjust the text.",
                    "status": "resolved",
                },
                {
                    "bug_id": "QA-003",
                    "severity": "medium",
                    "title": "Investigate retry behavior",
                    "description": "Retries are inconsistent for one flow.",
                    "affected_file": "backend/app/worker.py",
                    "affected_user_story": None,
                    "root_cause_phase": "developer",
                    "fix_owner": "developer",
                    "reproduction_steps": ["Trigger a retry"],
                    "suggested_fix": "Normalize retry policy.",
                    "status": "in_progress",
                },
            ],
            "score_breakdown": None,
            "routing_decision": {
                "route_to": "developer",
                "reason": "Quality gaps remain",
                "fix_instructions": [],
            },
            "meta_quality_report": None,
            "must_have_coverage_percent": 50,
            "critical_bugs_count": 0,
        },
        "devops_output": {
            "run_id": str(run_id),
            "deployment_artifacts": [],
            "startup_commands": ["docker compose up -d --build"],
            "environment_variables": [
                {
                    "key": "OPENAI_API_KEY",
                    "description": "Groq/OpenAI-compatible API key",
                    "required": True,
                    "example_value": "gsk_...",
                }
            ],
            "health_check_urls": ["http://localhost:8000/health"],
            "deployment_url": None,
        },
    }

    result = await run_documentation_agent(input_data)
    documents = result["documents"]

    assert set(documents) == {
        "README.md",
        "API_REFERENCE.md",
        "ARCHITECTURE.md",
        "KNOWN_ISSUES.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
    }

    readme = documents["README.md"]
    assert "Task Forge" in readme
    assert "docker compose up -d --build" in readme
    assert "OPENAI_API_KEY" in readme
    assert "Real-time task creation" in readme
    assert "Bulk edit" in readme
    assert "Not implemented in the current release" in readme

    api_reference = documents["API_REFERENCE.md"]
    assert "GET /api/v1/items" in api_reference
    assert "POST /api/v1/items" in api_reference
    assert "Authentication: required" in api_reference
    assert "name is required" in api_reference
    assert '"id": "item-1"' in api_reference
    assert "400" in api_reference
    assert "Validation error" in api_reference

    known_issues = documents["KNOWN_ISSUES.md"]
    assert "QA-001" in known_issues
    assert "QA-003" in known_issues
    assert "QA-002" not in known_issues
    assert "OPEN" in known_issues
    assert "IN_PROGRESS" in known_issues
    assert "RESOLVED" not in known_issues

    architecture = documents["ARCHITECTURE.md"]
    assert "Next.js 14 dashboard" in architecture
    assert "FastAPI workflow service" in architecture
    assert "Use API-first design" in architecture
    assert "Keep feature flags for unfinished capabilities" in architecture

    contributing = documents["CONTRIBUTING.md"]
    assert "docker compose up -d --build" in contributing
    assert "backend/app/agents" in contributing
    assert "backend/tests" in contributing

    changelog = documents["CHANGELOG.md"]
    assert "Version 1.0.0" in changelog
    assert "Real-time task creation" in changelog
    assert "Dashboard overview" in changelog
    assert "Document provider credentials and rollout notes" in changelog
    assert "QA-002" in changelog
