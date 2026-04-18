"""
Developer Agent — LLM-powered code generation engine.

Given the DesignSpec and PRD, generates all source files for the application.
Supports QA feedback loop: if qa_feedback is provided, fixes flagged bugs.

Entry-point: run_developer_agent(input_dict: dict) -> dict
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.agents import (
    DeveloperAgentInput,
    DeveloperAgentOutput,
    DeveloperStatus,
    GeneratedFile,
    DeveloperSelfCheck,
    SkippedFeature,
)

from app.schemas.agents import DeveloperAgentInput

logger = logging.getLogger(__name__)

# ── System prompts ────────────────────────────────────────────────────────────

DEVELOPER_SYSTEM_PROMPT = """\
You are the Developer Agent in an autonomous product development system.
Your role is to generate production-ready source code based on the design specification and PRD.

## 5-Step Protocol:
1. **Parse Design** - Understand all screens, API endpoints, and data models
2. **Plan Implementation** - Decide tech stack, file structure, dependencies
3. **Generate Code** - Write complete, functional source files
4. **Write Tests** - Generate unit and integration tests for core functionality
5. **Self-Check** - Verify schema consistency and route coverage

## Code Quality Rules:
- Generate COMPLETE files, not snippets
- All API endpoints from design_spec must be implemented
- All must-have features must be implemented
- Include proper error handling and input validation
- Write clean, commented code

## Output Requirements:
You MUST respond with ONLY a valid JSON object. No markdown fences, no explanations.

OUTPUT SCHEMA:
{
  "run_id": "string",
  "task_id": "string",
  "status": "completed|partial|failed",
  "summary": "Brief description of what was built",
  "files_created": [
    {
      "path": "relative/path/to/file.py",
      "purpose": "What this file does",
      "content": "complete file content here",
      "language": "python|javascript|typescript|yaml|other",
      "maps_to_endpoint_ids": ["EP-001"],
      "maps_to_screen_ids": ["S-001"]
    }
  ],
  "features_implemented": ["Feature name 1", "Feature name 2"],
  "features_skipped": [
    {"feature": "Feature name", "reason": "Why it was skipped"}
  ],
  "tests_written": ["test_user_auth.py", "test_api_endpoints.py"],
  "tech_debt_logged": ["item1", "item2"],
  "self_check_results": {
    "schema_consistent": true,
    "all_routes_implemented": true,
    "feature_coverage_percent": 95.0,
    "test_coverage_percent": 70.0,
    "issues_found": []
  }
}
"""

FIX_SYSTEM_PROMPT = """\
You are the Developer Agent fixing bugs identified by the QA team.
You will receive the original code files and QA bug reports.
Generate fixed versions of the affected files.

Rules:
- Fix ALL critical and high severity bugs
- Preserve existing functionality while fixing bugs
- Return the same JSON schema as the initial development task
- Set status to "completed" only if all critical bugs are fixed

OUTPUT SCHEMA: same as initial development - JSON only, no markdown.
"""


async def _call_llm(
    system_prompt: str,
    user_prompt: str,
    run_id: str,
) -> str:
    """Call Groq LLM and return raw response text."""
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=8000,
    )
    return response.choices[0].message.content or "{}"


def _parse_developer_output(raw: str, run_id: str) -> Dict[str, Any]:
    """Parse LLM JSON output, with fallback on parse failure."""
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        data = json.loads(text)
        data["run_id"] = run_id
        if "task_id" not in data:
            data["task_id"] = str(uuid.uuid4())
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse developer output: {e}")
        return {
            "run_id": run_id,
            "task_id": str(uuid.uuid4()),
            "status": "partial",
            "summary": "Code generation completed with parsing issues",
            "files_created": [],
            "features_implemented": [],
            "features_skipped": [],
            "tests_written": [],
            "tech_debt_logged": ["JSON parse error in developer output"],
            "self_check_results": {
                "schema_consistent": False,
                "all_routes_implemented": False,
                "feature_coverage_percent": 0.0,
                "test_coverage_percent": 0.0,
                "issues_found": [f"JSON parse error: {e}"],
            },
        }


def _build_dev_prompt(
    design_spec: Dict[str, Any],
    prd: Dict[str, Any],
    qa_feedback: Optional[Dict[str, Any]],
) -> str:
    """Build the user prompt for the developer agent."""

    # Summarise key elements
    screens = design_spec.get("screens", [])
    endpoints = design_spec.get("api_spec", [])
    data_models = design_spec.get("data_models", [])
    arch = design_spec.get("system_architecture", {})
    mvp_features = prd.get("features", {}).get("mvp", [])
    user_stories = prd.get("user_stories", [])
    must_haves = [s for s in user_stories if s.get("priority") == "must-have"]

    prompt = f"""## System Architecture:
Frontend: {arch.get('frontend', 'React/Next.js')}
Backend: {arch.get('backend', 'FastAPI/Python')}
Database: {arch.get('database', 'PostgreSQL')}
Cache: {arch.get('cache', 'Redis')}

## Must-Implement Features ({len(mvp_features)} total):
{chr(10).join([f"- {f.get('id', '')}: {f.get('name', '')} — {f.get('description', '')}" for f in mvp_features[:8]])}

## Must-Have User Stories ({len(must_haves)} total):
{chr(10).join([f"- {s.get('id', '')}: As a {s.get('persona', '')}, I want to {s.get('action', '')}" for s in must_haves[:8]])}

## API Endpoints to Implement ({len(endpoints)} total):
{chr(10).join([f"- {e.get('method', 'GET')} {e.get('path', '/')} — {e.get('description', '')}" for e in endpoints[:10]])}

## Data Models:
{chr(10).join([f"- {m.get('entity_name', '')} ({m.get('table_name', '')}): {[f.get('name') for f in m.get('fields', [])[:5]]}" for m in data_models[:5]])}

## Screens to Build ({len(screens)} total):
{chr(10).join([f"- {s.get('screen_name', '')} ({s.get('route', '/')}): {s.get('purpose', '')}" for s in screens[:6]])}
"""

    if qa_feedback:
        bugs = qa_feedback.get("bugs", [])
        fix_instructions = qa_feedback.get("fix_instructions", [])
        prompt += f"""

## QA BUG FIXES REQUIRED:
You are fixing issues from QA iteration {qa_feedback.get('iteration', 1)}.

Bugs to fix ({len(bugs)} total):
{chr(10).join([f"- [{b.get('severity', 'medium').upper()}] BUG-{b.get('bug_id', i)}: {b.get('title', '')} in {b.get('affected_file', 'unknown')} — {b.get('description', '')}" for i, b in enumerate(bugs[:10])])}

Fix Instructions:
{chr(10).join([f"- {fi.get('instruction', str(fi))}" for fi in fix_instructions[:5]])}

Focus on fixing ALL critical and high severity bugs. Regenerate affected files completely.
"""

    prompt += f"""

## Instructions:
Generate a complete, working implementation. Create all necessary files for:
1. Backend API (routes, models, schemas, services)
2. Database migrations/models
3. Basic frontend components (if applicable)
4. Unit tests for core business logic

Return ONLY the JSON object as specified in the system prompt.
"""
    return prompt


async def run_developer_agent(input_dict: dict) -> dict:
    """
    Main entry-point for Developer Agent.
    Accepts a plain dict (from executor), returns a plain dict.
    """
    input_data = DeveloperAgentInput.model_validate(input_dict)
    run_id = str(input_data.run_id)

    try:
        from app.core.redis import publish_log_line
        qa_feedback = input_data.qa_feedback
        if qa_feedback and qa_feedback.get("bugs"):
            await publish_log_line(run_id, "developer", f"Fixing {len(qa_feedback.get('bugs', []))} bugs from QA iteration {qa_feedback.get('iteration', 1)}...")
        else:
            await publish_log_line(run_id, "developer", "Starting code generation from design spec...")
    except Exception:
        pass

    design_spec = input_data.design_spec
    prd = input_data.prd

    # Convert pydantic models to dicts for prompt building
    design_dict = design_spec.model_dump() if hasattr(design_spec, "model_dump") else design_spec
    prd_dict = prd.model_dump() if hasattr(prd, "model_dump") else prd
    qa_dict = input_data.qa_feedback.model_dump() if input_data.qa_feedback else None

    system_prompt = FIX_SYSTEM_PROMPT if qa_dict and qa_dict.get("bugs") else DEVELOPER_SYSTEM_PROMPT
    user_prompt = _build_dev_prompt(design_dict, prd_dict, qa_dict)

    try:
        from app.core.redis import publish_log_line
        await publish_log_line(run_id, "developer", "Calling LLM for code generation (this may take a moment)...")
    except Exception:
        pass

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            raw = await _call_llm(system_prompt, user_prompt, run_id)
            parsed = _parse_developer_output(raw, run_id)

            try:
                from app.core.redis import publish_log_line
                files_count = len(parsed.get("files_created", []))
                await publish_log_line(run_id, "developer", f"Generated {files_count} source files ✓")
            except Exception:
                pass

            # Validate through schema
            output = DeveloperAgentOutput.model_validate(parsed)
            return output.model_dump(mode="json")

        except Exception as e:
            last_error = e
            logger.warning(f"Developer attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                continue

    # Return minimal valid output on complete failure
    logger.error(f"Developer agent failed after {max_retries} attempts: {last_error}")
    fallback = DeveloperAgentOutput(
        run_id=input_data.run_id,
        task_id=str(uuid.uuid4()),
        status=DeveloperStatus.FAILED,
        summary=f"Code generation failed: {last_error}",
        files_created=[],
        features_implemented=[],
        features_skipped=[
            SkippedFeature(feature="All features", reason=f"LLM error: {last_error}")
        ],
        tests_written=[],
        tech_debt_logged=[str(last_error)],
        self_check_results=DeveloperSelfCheck(
            schema_consistent=False,
            all_routes_implemented=False,
            feature_coverage_percent=0.0,
            test_coverage_percent=0.0,
            issues_found=[str(last_error)],
        ),
    )
    return fallback.model_dump(mode="json")
