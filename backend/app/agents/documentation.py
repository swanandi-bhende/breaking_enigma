"""
Documentation Agent — Generates all project documentation.

Synthesises the entire pipeline output into 6 comprehensive markdown documents:
README, API Reference, Architecture, Known Issues, Contributing, Changelog.

Entry-point: run_documentation_agent(input_dict: dict) -> dict
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.agents import (
    DocumentationAgentInput,
    DocumentationAgentOutput,
)

logger = logging.getLogger(__name__)


async def _generate_doc(client: AsyncOpenAI, doc_type: str, context: str, run_id: str) -> str:
    """Generate a single documentation file via LLM."""
    prompts = {
        "README.md": f"""Generate a professional README.md for this project.
Include: project overview, features, tech stack, quick start, installation, configuration, usage, API overview, contributing, license.
Use compelling language and proper markdown formatting with emojis.

{context}

Return ONLY the markdown content, no JSON wrapper.""",

        "API_REFERENCE.md": f"""Generate a comprehensive API Reference document.
Include all endpoints with: HTTP method, path, description, auth requirements, request/response schemas, examples, error codes.
Format as professional API documentation with proper markdown.

{context}

Return ONLY the markdown content.""",

        "ARCHITECTURE.md": f"""Generate a detailed Architecture document.
Include: system overview, component diagram (text-based), technology choices and rationale, data flow, deployment topology, scalability considerations.

{context}

Return ONLY the markdown content.""",

        "KNOWN_ISSUES.md": f"""Generate a Known Issues document from the QA report.
List all identified bugs with: ID, severity, description, workaround (if any), status, timeline estimate.
Also include: limitations, edge cases, deprecated features.

{context}

Return ONLY the markdown content.""",

        "CONTRIBUTING.md": f"""Generate a comprehensive Contributing guide.
Include: development setup, coding standards, git workflow, PR process, testing requirements, code review guidelines, release process.

{context}

Return ONLY the markdown content.""",

        "CHANGELOG.md": f"""Generate a Changelog document.
Include: v1.0.0 Initial Release with all features implemented, known limitations, dependencies.
Use Keep a Changelog format.

{context}

Return ONLY the markdown content.""",
    }

    system = "You are a technical documentation expert. Generate clear, professional documentation. Return ONLY the markdown content."
    user = prompts.get(doc_type, f"Generate {doc_type} documentation.\n{context}")

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        return response.choices[0].message.content or f"# {doc_type}\n\nDocumentation unavailable."
    except Exception as e:
        logger.warning(f"Failed to generate {doc_type}: {e}")
        return f"# {doc_type}\n\nDocumentation generation failed: {e}"


def _build_context(input_data: DocumentationAgentInput) -> str:
    """Build a compact context string from all pipeline outputs."""
    research = input_data.research_report
    prd = input_data.prd
    design_spec = input_data.design_spec
    dev_output = input_data.developer_output
    qa_output = input_data.qa_output
    devops_output = input_data.devops_output

    research_dict = research.model_dump() if hasattr(research, "model_dump") else research
    prd_dict = prd.model_dump() if hasattr(prd, "model_dump") else prd
    design_dict = design_spec.model_dump() if hasattr(design_spec, "model_dump") else design_spec
    dev_dict = dev_output.model_dump() if hasattr(dev_output, "model_dump") else dev_output
    qa_dict = qa_output.model_dump() if hasattr(qa_output, "model_dump") else qa_output
    devops_dict = devops_output.model_dump() if hasattr(devops_output, "model_dump") else devops_output

    problem = research_dict.get("problem_statement", {})
    vision = prd_dict.get("product_vision", {})
    stories = prd_dict.get("user_stories", [])
    features = prd_dict.get("features", {}).get("mvp", [])
    endpoints = design_dict.get("api_spec", [])
    arch = design_dict.get("system_architecture", {})
    files_created = dev_dict.get("files_created", [])
    bugs = qa_dict.get("bugs", [])
    qa_score = qa_dict.get("qa_score", 0)
    startup_commands = devops_dict.get("startup_commands", [])
    env_vars = devops_dict.get("environment_variables", [])

    return f"""## Project Overview
Problem: {problem.get('core_problem', '')}
Affected Users: {problem.get('affected_users', '')}

## Product Vision
Elevator Pitch: {vision.get('elevator_pitch', '')}
Target User: {vision.get('target_user', '')}
Value Proposition: {vision.get('core_value_proposition', '')}

## Key Features (MVP)
{chr(10).join([f"- {f.get('name', '')}: {f.get('description', '')}" for f in features[:8]])}

## User Stories ({len(stories)} total)
{chr(10).join([f"- {s.get('id', '')}: {s.get('action', '')} [{s.get('priority', '')}]" for s in stories[:10]])}

## System Architecture
Frontend: {arch.get('frontend', 'React/Next.js')}
Backend: {arch.get('backend', 'FastAPI/Python')}
Database: {arch.get('database', 'PostgreSQL')}
Cache: {arch.get('cache', 'Redis')}

## API Endpoints ({len(endpoints)} total)
{chr(10).join([f"- {e.get('method', 'GET')} {e.get('path', '/')}: {e.get('description', '')}" for e in endpoints[:8]])}

## Generated Files ({len(files_created)} total)
{chr(10).join([f"- {f.get('path', '')}: {f.get('purpose', '')}" for f in files_created[:10]])}

## QA Results
Score: {qa_score}/100
Known Bugs: {len(bugs)}
{chr(10).join([f"- [{b.get('severity', '').upper()}] {b.get('title', '')}: {b.get('description', '')}" for b in bugs[:5]])}

## Deployment
Startup Commands:
{chr(10).join([f"  {cmd}" for cmd in startup_commands[:5]])}

Environment Variables:
{chr(10).join([f"- {ev.get('key', '')}: {ev.get('description', '')}" for ev in env_vars[:8]])}
"""


async def run_documentation_agent(input_dict: dict) -> dict:
    """
    Main entry-point for Documentation Agent.
    Accepts a plain dict (from executor), returns a plain dict.
    """
    input_data = DocumentationAgentInput.model_validate(input_dict)
    run_id = str(input_data.run_id)

    try:
        from app.core.redis import publish_log_line
        await publish_log_line(run_id, "documentation", "Generating project documentation...")
    except Exception:
        pass

    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    context = _build_context(input_data)
    doc_types = ["README.md", "API_REFERENCE.md", "ARCHITECTURE.md", "KNOWN_ISSUES.md", "CONTRIBUTING.md", "CHANGELOG.md"]
    documents: Dict[str, str] = {}

    for doc_type in doc_types:
        try:
            from app.core.redis import publish_log_line
            await publish_log_line(run_id, "documentation", f"Generating {doc_type}...")
        except Exception:
            pass

        content = await _generate_doc(client, doc_type, context, run_id)
        documents[doc_type] = content

    try:
        from app.core.redis import publish_log_line
        await publish_log_line(run_id, "documentation", f"Generated {len(documents)} documentation files ✓")
    except Exception:
        pass

    output = DocumentationAgentOutput(
        run_id=input_data.run_id,
        documents=documents,
    )

    return output.model_dump(mode="json")
