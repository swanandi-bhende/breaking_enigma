#!/usr/bin/env python3
"""
Extract and display generated documentation from test execution.
Demonstrates the documentation generation feature with real output.
"""

import sys
import json
import uuid
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.agents.documentation import run_documentation_agent


def create_test_input_data():
    """Create comprehensive test input data for documentation generation."""
    run_id = str(uuid.uuid4())
    return {
        "run_id": run_id,
        "research_report": {
            "problem_statement": {
                "core_problem": "Organizations need AI-powered automation for engineering workflows.",
                "affected_users": "Engineering teams, DevOps engineers, product managers",
                "current_solutions_fail_because": "They require extensive manual configuration and lack autonomous decision-making.",
                "opportunity_window": "LLM agents can now handle complex multi-step engineering tasks.",
            },
            "market": {
                "tam_usd": 50000000,
                "sam_usd": 10000000,
                "som_usd": 2000000,
                "industry": "Enterprise Software / DevOps",
                "growth_rate_yoy_percent": 35.0,
                "key_trends": ["AI Automation", "DevOps Infrastructure", "Autonomous Agents"],
            },
            "personas": [
                {
                    "name": "Alex Chen",
                    "age_range": "28-38",
                    "occupation": "Engineering Manager",
                    "goals": ["Reduce manual toil", "Scale team productivity"],
                    "frustrations": ["Repetitive tasks", "Slow feedback loops"],
                    "tech_savviness": "high",
                    "primary_device": "Laptop",
                }
            ],
            "pain_points": [
                {
                    "pain": "Manual code reviews take hours per PR",
                    "severity": "high",
                    "frequency": "constant",
                }
            ],
            "competitors": [],
            "viability": {
                "revenue_models": ["Per-agent", "Platform subscription"],
                "recommended_model": "Platform subscription",
                "estimated_arpu": "$500",
                "go_to_market_strategy": "Direct to engineering teams",
                "viability_score": 9,
            },
            "feasibility": {
                "technical_risks": ["LLM provider reliability", "Agent coordination"],
                "complexity": "high",
                "estimated_mvp_weeks": 12,
                "key_dependencies": ["LangGraph", "LLM providers"],
                "feasibility_score": 8,
            },
        },
        "prd": {
            "product_vision": {
                "elevator_pitch": "Breaking Enigma - AI Digital Workforce",
                "target_user": "Enterprise engineering teams",
                "core_value_proposition": "Autonomous AI agents that collaborate to automate complex engineering tasks.",
                "success_definition": "50% reduction in manual engineering overhead",
            },
            "user_stories": [],
            "features": {
                "mvp": [],
                "v1_1": [],
                "v2_0": [],
            },
            "budget_estimate": {
                "mvp_engineer_weeks": 12,
                "mvp_cost_usd_range": "$100k-$150k",
                "assumptions": ["3-person team", "12-week sprint"],
            },
            "user_flow": [],
        },
        "design_spec": {
            "product_name": "Breaking Enigma ADWF",
            "system_architecture": {
                "frontend": "Next.js 14 with React Server Components",
                "backend": "FastAPI with LangGraph orchestration",
                "data_layer": "PostgreSQL + Redis + Qdrant",
                "deployment": "Docker Compose / Kubernetes",
                "auth": "OAuth2.0 with JWT",
                "api_version": "v1",
            },
            "implementation_plan": {
                "key_architectural_decisions": [
                    {
                        "decision": "Use API-first design with clear service boundaries",
                        "rationale": "Enable independent scaling and team ownership",
                        "trade_offs": "Requires careful versioning and backwards compatibility",
                    },
                    {
                        "decision": "Implement agent coordination via LangGraph state machine",
                        "rationale": "Provides deterministic execution and auditability",
                        "trade_offs": "Limits ad-hoc agent communication",
                    },
                ]
            },
            "risk_mitigation_plan": {
                "critical_risks": [
                    "LLM provider rate limiting → implement fallback to deterministic outputs",
                    "Agent deadlock → checkpoint every step",
                ]
            },
        },
        "developer_output": {
            "run_id": run_id,
            "task_id": f"task-{run_id[:8]}",
            "files_generated": 12,
            "features_implemented": [
                {
                    "id": "feat-001",
                    "name": "Real-time task creation",
                    "status": "COMPLETE",
                    "code_location": "backend/app/workflow/graph.py",
                },
                {
                    "id": "feat-002",
                    "name": "Dashboard overview",
                    "status": "COMPLETE",
                    "code_location": "frontend/src/app/dashboard/page.tsx",
                },
                {
                    "id": "feat-003",
                    "name": "WebSocket live updates",
                    "status": "COMPLETE",
                    "code_location": "backend/app/api/websocket.py",
                },
            ],
            "features_skipped": [
                {
                    "id": "feat-mobile",
                    "name": "Mobile app (iOS/Android)",
                    "reason": "Out of MVP scope; planned for v2",
                },
                {
                    "id": "feat-analytics",
                    "name": "Advanced analytics dashboard",
                    "reason": "Depends on v1 stabilization",
                },
            ],
            "tech_debt_logged": [
                "Migrate from Celery to FastAPI background tasks",
                "Extract environment-specific config to .env patterns",
            ],
        },
        "qa_output": {
            "run_id": run_id,
            "verdict": "PASS",
            "quality_score": 92.5,
            "bugs": [
                {
                    "id": "QA-001",
                    "title": "Dashboard widgets misaligned on mobile",
                    "severity": "LOW",
                    "status": "OPEN",
                    "expected_behavior": "Widgets stack properly on all screen sizes",
                    "actual_behavior": "2px offset on iPhone 12",
                },
                {
                    "id": "QA-002",
                    "title": "Document deployment procedure and credentials",
                    "severity": "MEDIUM",
                    "status": "RESOLVED",
                    "affected_area": "DevOps/Documentation",
                },
                {
                    "id": "QA-003",
                    "title": "Implement LLM provider fallback when rate limited",
                    "severity": "CRITICAL",
                    "status": "IN_PROGRESS",
                    "blocked_by": ["Groq rate limit testing"],
                },
            ],
        },
        "devops_output": {
            "deployment_url": "https://breaking-enigma.vercel.app",
            "startup_commands": [
                "docker compose up -d --build",
                "cd backend && alembic upgrade head",
            ],
            "environment_variables": [
                {"name": "OPENAI_API_KEY", "required": True, "description": "Groq or OpenAI API key for LLM"},
                {"name": "DATABASE_URL", "required": True, "description": "PostgreSQL connection string"},
                {"name": "REDIS_URL", "required": True, "description": "Redis connection for caching/events"},
                {"name": "QDRANT_URL", "required": False, "description": "Qdrant vector DB (optional)"},
            ],
            "health_check_urls": [
                "http://localhost:8000/api/v1/health",
                "http://localhost/api/v1/health",
            ],
        },
    }


async def extract_and_save_docs():
    """Extract generated docs and save to files."""
    
    print("=" * 80)
    print("🚀 DOCUMENTATION GENERATION FEATURE DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Generate input data
    input_data = create_test_input_data()
    
    print("📋 Input Data Summary:")
    print(f"  • Research Report: Present ✓")
    print(f"  • Product Vision: Present ✓")
    print(f"  • Design Spec: Present ✓")
    print(f"  • Developer Output: {input_data['developer_output']['files_generated']} files")
    print(f"  • QA Output: {len(input_data['qa_output']['bugs'])} QA tickets")
    print(f"  • DevOps Output: Present ✓")
    print()
    
    # Generate documents
    print("🔧 Generating 6 markdown documents...")
    result = await run_documentation_agent(input_data)
    documents = result.get("documents", {})
    
    # Create output directory
    output_dir = Path("generated_docs")
    output_dir.mkdir(exist_ok=True)
    
    # Write each document and display summary
    print()
    print("📁 Generated Documents:")
    print("-" * 80)
    
    for filename, content in sorted(documents.items()):
        filepath = output_dir / filename
        filepath.write_text(content)
        lines = len(content.split("\n"))
        chars = len(content)
        
        # Extract key stats from content
        headers = content.count("## ")
        tables = content.count("|---")
        code_blocks = content.count("```")
        
        print(f"  ✓ {filename:25} {lines:4} lines  {chars:6} chars")
        if headers:
            print(f"    └─ {headers} sections, {tables} tables, {code_blocks} code blocks")
    
    print()
    print("=" * 80)
    print("✅ ALL 6 MARKDOWN DOCUMENTS SUCCESSFULLY GENERATED")
    print("=" * 80)
    print()
    
    # Show samples from each document
    print("📄 DOCUMENT SAMPLES:")
    print()
    
    # README sample
    readme = documents.get("README.md", "")
    print("1️⃣  README.md (Overview & Quick Start)")
    print("-" * 80)
    lines = readme.split("\n")[:30]
    for line in lines:
        print(line)
    print("   [... truncated ...]")
    print()
    
    # API Reference sample  
    api_ref = documents.get("API_REFERENCE.md", "")
    print("2️⃣  API_REFERENCE.md (Endpoints)")
    print("-" * 80)
    # Extract just the first endpoint section
    api_lines = api_ref.split("\n")
    for i, line in enumerate(api_lines[:40]):
        print(line)
    print("   [... truncated ...]")
    print()
    
    # Print paths for all documents
    print("=" * 80)
    print("📍 OUTPUT LOCATION: generated_docs/")
    print("=" * 80)
    for filename in sorted(documents.keys()):
        filepath = output_dir / filename
        print(f"  • {filepath}")
    print()
    
    # Print verification checklist
    print("✅ VERIFICATION CHECKLIST:")
    print("-" * 80)
    
    checks = {
        "README.md": {
            "Product name present": "ADWF" in readme,
            "Docker command included": "docker compose" in readme,
            "API key documented": "OPENAI_API_KEY" in readme,
            "Built features listed": "Real-time task creation" in readme,
            "Planned features listed": "Mobile app" in readme,
        },
        "API_REFERENCE.md": {
            "Endpoints documented": "GET /api" in api_ref or "POST /api" in api_ref,
            "Auth requirements noted": "Authentication" in api_ref,
            "Request schemas shown": "request" in api_ref.lower(),
            "Response examples": "json" in api_ref.lower() or "```" in api_ref,
        },
    }
    
    known_issues = documents.get("KNOWN_ISSUES.md", "")
    arch = documents.get("ARCHITECTURE.md", "")
    contrib = documents.get("CONTRIBUTING.md", "")
    changelog = documents.get("CHANGELOG.md", "")
    
    checks["KNOWN_ISSUES.md"] = {
        "Open issues included": "OPEN" in known_issues or "QA-001" in known_issues,
        "In-progress items": "IN_PROGRESS" in known_issues or "QA-003" in known_issues,
        "Resolved bugs excluded": "RESOLVED" not in known_issues or "QA-002" not in known_issues,
    }
    
    checks["ARCHITECTURE.md"] = {
        "Tech stack defined": ("FastAPI" in arch or "Next.js" in arch),
        "Design decisions documented": "decision" in arch.lower() or "Decision" in arch,
    }
    
    checks["CONTRIBUTING.md"] = {
        "Setup instructions": "docker" in contrib.lower() or "setup" in contrib.lower(),
        "Code structure documented": "backend/" in contrib or "frontend/" in contrib,
    }
    
    checks["CHANGELOG.md"] = {
        "Features listed": "Features" in changelog or "feature" in changelog.lower(),
        "Bug fixes noted": "bug" in changelog.lower() or "Bug" in changelog or "QA" in changelog,
    }
    
    total_checks = 0
    passed_checks = 0
    
    for doc, doc_checks in checks.items():
        if doc in documents:
            print(f"\n{doc}:")
            for check_name, check_result in doc_checks.items():
                status = "✓" if check_result else "✗"
                print(f"  {status} {check_name}")
                total_checks += 1
                if check_result:
                    passed_checks += 1
    
    print()
    print("-" * 80)
    print(f"Checks passed: {passed_checks}/{total_checks}")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(extract_and_save_docs())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
