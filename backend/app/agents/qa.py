"""
QA Agent — Code review, traceability matrix, and bug detection engine.

Reviews developer output against the design spec and PRD.
Uses determine_qa_verdict() from qa_scoring.py for consistent routing.

Entry-point: run_qa_agent(input_dict: dict) -> dict
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.agents import (
    QAAgentInput,
    QAAgentOutput,
    QAVerdict,
    QARoute,
    TraceabilityEntry,
    CoverageStatus,
    Bug,
    BugSeverity,
    BugStatus,
    RoutingDecision,
    AcceptanceCriterionResult,
    CriterionResult,
)
from app.workflow.qa_scoring import determine_qa_verdict

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """\
You are the QA Agent in an autonomous product development system.
Your role is to review generated code against the PRD and design spec, identify bugs, and evaluate coverage.

## Your QA Protocol:
1. **Parse Developer Output** - Review all generated files
2. **Build Traceability Matrix** - Map each must-have user story to implementing files
3. **Evaluate Coverage** - For each user story: COVERED, PARTIAL, or MISSING
4. **Identify Bugs** - Find defects, security issues, missing validations
5. **Classify Bugs** - Assign severity: critical, high, medium, low
6. **Generate Fix Instructions** - Specific instructions for each bug

## Coverage Rules:
- COVERED: the user story is fully implemented with working code
- PARTIAL: some acceptance criteria are implemented but not all
- MISSING: no implementation found for this user story

## Output Requirements:
You MUST respond with ONLY a valid JSON object. No markdown, no explanations.

OUTPUT SCHEMA:
{
  "traceability_matrix": [
    {
      "user_story_id": "US-001",
      "feature_name": "string",
      "priority": "must-have",
      "status": "COVERED|PARTIAL|MISSING",
      "implementing_files": ["path/to/file.py"],
      "acceptance_criteria_results": [
        {
          "criterion": "Given ... When ... Then ...",
          "result": "PASS|FAIL|UNTESTABLE",
          "notes": "optional notes"
        }
      ]
    }
  ],
  "bugs": [
    {
      "bug_id": "BUG-001",
      "severity": "critical|high|medium|low",
      "title": "Short bug title",
      "description": "Detailed bug description",
      "affected_file": "path/to/file.py",
      "affected_user_story": "US-001",
      "reproduction_steps": ["Step 1", "Step 2"],
      "suggested_fix": "How to fix this",
      "status": "open"
    }
  ],
  "fix_instructions": [
    {
      "bug_id": "BUG-001",
      "file": "path/to/file.py",
      "instruction": "Specific fix instruction"
    }
  ]
}
"""


async def _call_qa_llm(user_prompt: str) -> str:
    """Call Groq LLM for QA analysis."""
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": QA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=6000,
    )
    return response.choices[0].message.content or "{}"


def _build_qa_prompt(
    developer_output: Dict[str, Any],
    design_spec: Dict[str, Any],
    prd: Dict[str, Any],
    iteration: int,
) -> str:
    files = developer_output.get("files_created", [])
    user_stories = prd.get("user_stories", [])
    must_haves = [s for s in user_stories if s.get("priority") == "must-have"]
    features_impl = developer_output.get("features_implemented", [])

    # Summarise files (content truncated for token budget)
    file_summaries = []
    for f in files[:12]:
        path = f.get("path", "unknown")
        purpose = f.get("purpose", "")
        content_preview = f.get("content", "")[:300]
        file_summaries.append(f"FILE: {path}\nPURPOSE: {purpose}\nPREVIEW:\n{content_preview}\n---")

    return f"""## QA Review — Iteration {iteration}

## Developer Output Summary:
Status: {developer_output.get('status', 'unknown')}
Summary: {developer_output.get('summary', '')}
Files Generated: {len(files)}
Features Implemented: {features_impl}

## Must-Have User Stories to Evaluate ({len(must_haves)} total):
{chr(10).join([
    f"- {s.get('id', '')}: {s.get('action', '')} → {s.get('outcome', '')} "
    f"[Criteria: {[f\"{ac.get('given', '')} / {ac.get('when', '')} / {ac.get('then', '')}\" for ac in s.get('acceptance_criteria', [])[:2]]}]"
    for s in must_haves[:8]
])}

## Generated Files:
{chr(10).join(file_summaries[:10])}

## API Endpoints Expected:
{chr(10).join([f"- {e.get('method', 'GET')} {e.get('path', '/')}: {e.get('description', '')}" for e in design_spec.get('api_spec', [])[:8]])}

## Instructions:
1. Build the traceability matrix for all must-have user stories above
2. Look for bugs, missing validations, security issues
3. Provide specific fix instructions for each bug
4. Return ONLY the JSON object

Return ONLY the JSON object as specified in the system prompt.
"""


def _parse_qa_output(raw: str) -> Dict[str, Any]:
    """Parse QA agent JSON output with fallback."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse QA output JSON: {e}")
        return {
            "traceability_matrix": [],
            "bugs": [],
            "fix_instructions": [],
        }


async def run_qa_agent(input_dict: dict) -> dict:
    """
    Main entry-point for QA Agent.
    Accepts a plain dict (from executor), returns a plain dict.
    """
    input_data = QAAgentInput.model_validate(input_dict)
    run_id = str(input_data.run_id)
    iteration = input_data.iteration

    try:
        from app.core.redis import publish_log_line
        await publish_log_line(run_id, "qa", f"Starting QA review (iteration {iteration})...")
    except Exception:
        pass

    dev_output = input_data.developer_output
    design_spec = input_data.design_spec
    prd = input_data.prd

    dev_dict = dev_output.model_dump() if hasattr(dev_output, "model_dump") else dev_output
    design_dict = design_spec.model_dump() if hasattr(design_spec, "model_dump") else design_spec
    prd_dict = prd.model_dump() if hasattr(prd, "model_dump") else prd

    user_prompt = _build_qa_prompt(dev_dict, design_dict, prd_dict, iteration)

    max_retries = 2
    parsed = {"traceability_matrix": [], "bugs": [], "fix_instructions": []}

    for attempt in range(max_retries):
        try:
            try:
                from app.core.redis import publish_log_line
                await publish_log_line(run_id, "qa", f"Analysing code coverage (attempt {attempt + 1})...")
            except Exception:
                pass

            raw = await _call_qa_llm(user_prompt)
            parsed = _parse_qa_output(raw)
            break
        except Exception as e:
            logger.warning(f"QA attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"QA agent failed after {max_retries} attempts: {e}")

    # Build structured traceability matrix for qa_scoring
    traceability_raw = parsed.get("traceability_matrix", [])
    bugs_raw = parsed.get("bugs", [])
    fix_instructions = parsed.get("fix_instructions", [])

    # Enrich traceability with priorities from PRD
    user_stories_map = {
        s.get("id", ""): s.get("priority", "must-have")
        for s in prd_dict.get("user_stories", [])
    }

    scoring_matrix = []
    for entry in traceability_raw:
        story_id = entry.get("user_story_id", "")
        scoring_matrix.append({
            "priority": user_stories_map.get(story_id, entry.get("priority", "must-have")),
            "status": entry.get("status", "MISSING"),
        })

    scoring_bugs = []
    for bug in bugs_raw:
        scoring_bugs.append({
            "severity": bug.get("severity", "medium"),
            "status": bug.get("status", "open"),
        })

    max_qa_iter = 3  # from config
    verdict_data = determine_qa_verdict(
        traceability_matrix=scoring_matrix,
        bugs=scoring_bugs,
        max_iterations_reached=(iteration >= max_qa_iter),
    )

    try:
        from app.core.redis import publish_log_line
        await publish_log_line(
            run_id, "qa",
            f"QA complete: {verdict_data['verdict']} (score={verdict_data['qa_score']:.1f}, "
            f"coverage={verdict_data['must_have_coverage_percent']:.0f}%, "
            f"critical_bugs={verdict_data['critical_bugs_count']}) ✓"
        )
    except Exception:
        pass

    # Map route_to value
    route_to_map = {
        "devops_and_docs": QARoute.DEVOPS_AND_DOCS,
        "developer": QARoute.DEVELOPER,
        "human_review": QARoute.HUMAN_REVIEW,
    }
    route_to = route_to_map.get(verdict_data["route_to"], QARoute.DEVELOPER)

    # Build Pydantic traceability entries
    matrix_entries = []
    for entry in traceability_raw[:20]:
        try:
            criteria_results = []
            for cr in entry.get("acceptance_criteria_results", [])[:5]:
                try:
                    result_val = cr.get("result", "UNTESTABLE").upper()
                    if result_val not in ("PASS", "FAIL", "UNTESTABLE"):
                        result_val = "UNTESTABLE"
                    criteria_results.append(AcceptanceCriterionResult(
                        criterion=str(cr.get("criterion", "")),
                        result=CriterionResult(result_val),
                        notes=cr.get("notes"),
                    ))
                except Exception:
                    pass

            status_val = entry.get("status", "MISSING").upper()
            if status_val not in ("COVERED", "PARTIAL", "MISSING"):
                status_val = "MISSING"

            matrix_entries.append(TraceabilityEntry(
                user_story_id=str(entry.get("user_story_id", "")),
                feature_name=str(entry.get("feature_name", "")),
                status=CoverageStatus(status_val),
                implementing_files=entry.get("implementing_files", []),
                acceptance_criteria_results=criteria_results,
            ))
        except Exception as e:
            logger.warning(f"Skipping invalid traceability entry: {e}")

    # Build Bug objects
    bug_objects = []
    for bug in bugs_raw[:20]:
        try:
            sev_val = bug.get("severity", "medium").lower()
            if sev_val not in ("critical", "high", "medium", "low"):
                sev_val = "medium"
            bug_objects.append(Bug(
                bug_id=str(bug.get("bug_id", f"BUG-{len(bug_objects):03d}")),
                severity=BugSeverity(sev_val),
                title=str(bug.get("title", "Unnamed bug")),
                description=str(bug.get("description", "")),
                affected_file=str(bug.get("affected_file", "unknown")),
                affected_user_story=bug.get("affected_user_story"),
                reproduction_steps=bug.get("reproduction_steps", []),
                suggested_fix=bug.get("suggested_fix"),
                status=BugStatus.OPEN,
            ))
        except Exception as e:
            logger.warning(f"Skipping invalid bug entry: {e}")

    routing_decision = RoutingDecision(
        route_to=route_to,
        reason=f"QA score {verdict_data['qa_score']:.1f} — {verdict_data['verdict']}",
        fix_instructions=fix_instructions[:10],
    )

    output = QAAgentOutput(
        run_id=input_data.run_id,
        verdict=QAVerdict.PASS if verdict_data["verdict"] == "PASS" else QAVerdict.FAIL,
        qa_score=verdict_data["qa_score"],
        iteration=iteration,
        traceability_matrix=matrix_entries,
        bugs=bug_objects,
        routing_decision=routing_decision,
        must_have_coverage_percent=verdict_data["must_have_coverage_percent"],
        critical_bugs_count=verdict_data["critical_bugs_count"],
    )

    return output.model_dump(mode="json")
