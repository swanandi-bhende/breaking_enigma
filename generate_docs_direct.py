#!/usr/bin/env python3
"""
Direct documentation generation script - demonstrates the documentation pipeline feature.
This bypasses the full QA loop and directly calls the documentation agent to generate all 6 markdown files.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.agents.documentation import run_documentation_agent
from app.schemas.research_pm import ProductVision, Feature, FeatureCategory
from app.schemas.designer import SystemArchitecture, ArchitecturalDecision
from app.schemas.agents import (
    APIEndpoint,
    APIEndpointInput,
    APIEndpointResponse,
    ValidationRule,
)


def generate_realistic_docs():
    """Generate documentation using realistic test data to demonstrate the feature."""
    
    # Build a comprehensive input that covers all data sources
    input_data = {
        "research_report": {
            "industry": "SaaS/Fitness",
            "market_analysis": "Growing demand for AI-powered fitness coaching platforms",
            "target_users": "Fitness enthusiasts, gym owners, personal trainers",
        },
        "prd": {
            "product_name": "Breaking Enigma",
            "version": "1.0.0",
            "vision": "Enterprise-grade AI digital workforce platform enabling organizations to automate complex engineering workflows with autonomous agents.",
            "features": [
                Feature(
                    id="feat-001",
                    category=FeatureCategory.RESEARCH,
                    title="Real-time Market Research",
                    description="Automated market analysis and competitive intelligence",
                ),
                Feature(
                    id="feat-002",
                    category=FeatureCategory.DESIGN,
                    title="AI-Powered UI Design",
                    description="Generate design specifications from product requirements",
                ),
                Feature(
                    id="feat-003",
                    category=FeatureCategory.DEVELOPMENT,
                    title="Code Generation Engine",
                    description="Automatic code generation for web and mobile platforms",
                ),
            ],
        },
        "design_spec": {
            "product_name": "ADWF Platform",
            "system_architecture": SystemArchitecture(
                frontend="Next.js 14 with React Server Components and TypeScript",
                backend="FastAPI async runtime with LangGraph orchestration",
                data_layer="PostgreSQL (state) + Redis (events) + Qdrant (RAG)",
                deployment="Docker Compose local, Kubernetes ready",
                auth="OAuth2.0 with JWT tokens",
                api_version="v1",
            ),
            "implementation_plan": {
                "key_architectural_decisions": [
                    ArchitecturalDecision(
                        decision="Use API-first design",
                        rationale="Enable independent frontend/backend development and scale backend separately",
                        trade_offs="Requires careful API versioning",
                    ),
                    ArchitecturalDecision(
                        decision="Keep feature flags for unfinished capabilities",
                        rationale="Deploy early, control visibility via config, reduce merge conflicts",
                        trade_offs="Adds complexity to feature management",
                    ),
                ]
            },
            "risk_mitigation_plan": {
                "critical_risks": [
                    "LLM provider rate limiting → implement graceful fallbacks to deterministic outputs",
                    "Agent coordination deadlocks → use explicit state checkpoints",
                ]
            },
        },
        "developer_output": {
            "run_id": "dev-demo-001",
            "task_id": "task-demo",
            "files_generated": 8,
            "features_implemented": [
                {
                    "id": "feat-001",
                    "name": "Real-time task creation",
                    "status": "COMPLETE",
                    "code_location": "backend/app/workflow/graph.py:node_create_task",
                },
                {
                    "id": "feat-002",
                    "name": "Dashboard overview",
                    "status": "COMPLETE",
                    "code_location": "frontend/src/app/dashboard/page.tsx",
                },
                {
                    "id": "feat-003",
                    "name": "WebSocket live stream",
                    "status": "COMPLETE",
                    "code_location": "backend/app/api/websocket.py",
                },
            ],
            "features_skipped": [
                {
                    "id": "feat-004",
                    "name": "Mobile app native build",
                    "reason": "Out of scope for v1; requires iOS/Android infrastructure",
                },
                {
                    "id": "feat-005",
                    "name": "Advanced analytics dashboard",
                    "reason": "Planned for v2 after core features stabilize",
                },
            ],
            "tech_debt_logged": [
                "Migrate from Celery to native FastAPI background tasks for simpler deployment",
                "Extract magic strings to config constants across all agent modules",
            ],
        },
        "qa_output": {
            "run_id": "qa-demo-001",
            "verdict": "PASS",
            "quality_score": 92.5,
            "bugs": [
                {
                    "id": "QA-001",
                    "title": "Dashboard widget alignment off by 2px on mobile",
                    "severity": "LOW",
                    "status": "OPEN",
                    "expected_behavior": "Widgets align to pixel grid on all viewport sizes",
                    "actual_behavior": "2px offset visible on iPhone 12 viewports",
                },
                {
                    "id": "QA-002",
                    "title": "Document provider credentials and rollout notes",
                    "severity": "MEDIUM",
                    "status": "RESOLVED",
                    "affected_area": "DevOps/Deployment",
                },
                {
                    "id": "QA-003",
                    "title": "Implement graceful fallback when Groq rate limit exceeded",
                    "severity": "CRITICAL",
                    "status": "IN_PROGRESS",
                    "blocked_by": ["QA-002"],
                },
            ],
        },
        "devops_output": {
            "deployment_url": "https://breaking-enigma.vercel.app",
            "startup_commands": [
                "docker compose up -d --build",
                "source .venv/bin/activate && cd backend && alembic upgrade head",
            ],
            "environment_variables": [
                {"name": "OPENAI_API_KEY", "required": True, "description": "Groq or OpenAI API key"},
                {"name": "DATABASE_URL", "required": True, "description": "PostgreSQL connection string"},
                {"name": "REDIS_URL", "required": True, "description": "Redis connection string"},
            ],
            "health_check_urls": [
                "http://localhost:8000/health",
                "http://localhost/api/v1/health",
            ],
        },
    }

    print("Generating documentation from realistic data...")
    print("-" * 70)
    
    try:
        documents = run_documentation_agent(input_data)
        
        # Create output directory
        output_dir = Path("generated_docs")
        output_dir.mkdir(exist_ok=True)
        
        # Write each document to file
        for filename, content in documents.items():
            filepath = output_dir / filename
            filepath.write_text(content)
            lines = content.count("\n")
            print(f"✓ {filename:25} ({lines:3} lines)")
        
        print("-" * 70)
        print(f"✅ All 6 documentation files generated successfully!")
        print(f"📁 Output location: {output_dir.absolute()}")
        print()
        
        # Print excerpt from README
        readme = documents.get("README.md", "")
        if readme:
            print("📄 README.md Preview (first 800 chars):")
            print("-" * 70)
            print(readme[:800] + "...")
            print()
        
        # Validate all expected documents exist
        expected_docs = {
            "README.md",
            "API_REFERENCE.md",
            "ARCHITECTURE.md",
            "KNOWN_ISSUES.md",
            "CONTRIBUTING.md",
            "CHANGELOG.md",
        }
        
        generated_docs = set(documents.keys())
        if expected_docs == generated_docs:
            print(f"✅ All 6 expected documents present: {sorted(generated_docs)}")
        else:
            missing = expected_docs - generated_docs
            extra = generated_docs - expected_docs
            if missing:
                print(f"❌ Missing documents: {missing}")
            if extra:
                print(f"⚠️  Extra documents: {extra}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating documentation: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = generate_realistic_docs()
    sys.exit(0 if success else 1)
