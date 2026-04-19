import json
import logging
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.schemas.agents import BugFixAgentInput

logger = logging.getLogger(__name__)


BUGFIX_MODEL = "llama-3.3-70b-versatile"

BUGFIX_SYSTEM_PROMPT = """You are a senior remediation engineer.
Your task is to convert QA bug reports into precise, implementable developer fix instructions.

Hard rules:
1. Output ONLY valid JSON.
2. No markdown or explanation text.
3. Focus on practical code-level fixes.
4. Prioritize critical/high severity bugs.

Expected JSON shape:
{
  "summary": "string",
  "target_files": ["string"],
  "remediation_strategy": ["string"],
  "actions": [
    {
      "bug_id": "string",
      "owner": "developer",
      "instruction": "string",
      "path_hint": "string",
      "priority": 1
    }
  ]
}
"""


def _extract_json_object(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Could not parse bugfix JSON output")


def _default_actions(qa_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    bugs = qa_output.get("bugs", []) if isinstance(qa_output.get("bugs", []), list) else []

    for bug in bugs:
        if not isinstance(bug, dict):
            continue
        actions.append(
            {
                "bug_id": str(bug.get("bug_id", "")) or None,
                "owner": str(bug.get("fix_owner", "developer") or "developer"),
                "instruction": str(bug.get("suggested_fix", "Resolve QA-reported defect with deterministic implementation updates.")),
                "path_hint": str(bug.get("affected_file", "")) or None,
                "priority": 1 if str(bug.get("severity", "")).lower() in {"critical", "high"} else 2,
            }
        )
    return actions


def _target_files_from_actions(actions: List[Dict[str, Any]]) -> List[str]:
    files: List[str] = []
    for action in actions:
        path = str(action.get("path_hint") or "").strip()
        if not path:
            continue
        if path.lower() in {"unknown", "frontend/backend", "developer_output", "tests"}:
            continue
        files.append(path)

    unique: List[str] = []
    seen = set()
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


class BugFixAgent:
    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=BUGFIX_MODEL,
            temperature=0.1,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

    async def execute(self, input_data: BugFixAgentInput) -> Dict[str, Any]:
        qa_output = input_data.qa_output.model_dump(mode="json")
        developer_output = input_data.developer_output.model_dump(mode="json")

        prompt = (
            "Generate actionable remediation plan from QA failures.\\n"
            "Return only the expected JSON object.\\n\\n"
            f"Iteration: {input_data.iteration}\\n"
            f"QA Verdict: {qa_output.get('verdict')}\\n"
            f"QA Score: {qa_output.get('qa_score')}\\n"
            f"QA Bugs: {json.dumps(qa_output.get('bugs', [])[:40], ensure_ascii=True)}\\n"
            f"Routing Fix Instructions: {json.dumps((qa_output.get('routing_decision', {}) or {}).get('fix_instructions', [])[:40], ensure_ascii=True)}\\n"
            f"Developer Files: {json.dumps(developer_output.get('files_created', [])[:80], ensure_ascii=True)}\\n"
        )

        actions = _default_actions(qa_output)
        target_files = _target_files_from_actions(actions)
        summary = "Generated remediation plan from QA bug set."
        strategy = [
            "Patch high-severity defects first and ensure route/schema consistency.",
            "Regenerate affected files with explicit validation and production-safe behavior.",
            "Re-run QA to verify bug closure and score improvement.",
        ]

        try:
            response = await self.llm.ainvoke(
                [
                    ("system", BUGFIX_SYSTEM_PROMPT),
                    ("human", prompt),
                ]
            )
            parsed = _extract_json_object(response.content)
            model_actions = parsed.get("actions", [])
            if isinstance(model_actions, list) and model_actions:
                actions = []
                for item in model_actions[:120]:
                    if not isinstance(item, dict):
                        continue
                    actions.append(
                        {
                            "bug_id": str(item.get("bug_id", "")) or None,
                            "owner": str(item.get("owner", "developer") or "developer"),
                            "instruction": str(item.get("instruction", "Resolve the mapped QA issue.")),
                            "path_hint": str(item.get("path_hint", "")) or None,
                            "priority": int(item.get("priority", 2)) if str(item.get("priority", "2")).isdigit() else 2,
                        }
                    )
            model_files = parsed.get("target_files", [])
            if isinstance(model_files, list) and model_files:
                target_files = [str(path).strip() for path in model_files if str(path).strip()][:120]
            model_strategy = parsed.get("remediation_strategy", [])
            if isinstance(model_strategy, list) and model_strategy:
                strategy = [str(line).strip() for line in model_strategy if str(line).strip()][:20]
            model_summary = str(parsed.get("summary", "")).strip()
            if model_summary:
                summary = model_summary
        except Exception as exc:
            logger.warning("[bugfix] falling back to deterministic remediation plan: %s", str(exc)[:250])

        qa_feedback = {
            "iteration": input_data.iteration,
            "failed_tests": [
                {
                    "user_story_id": row.get("user_story_id"),
                    "feature_name": row.get("feature_name"),
                    "status": row.get("status"),
                    "implementing_files": row.get("implementing_files", []),
                }
                for row in qa_output.get("traceability_matrix", [])
                if isinstance(row, dict) and str(row.get("status", "")).upper() != "COVERED"
            ],
            "bugs": qa_output.get("bugs", []),
            "fix_instructions": [
                {
                    "bug_id": item.get("bug_id"),
                    "owner": item.get("owner", "developer"),
                    "instruction": item.get("instruction"),
                    "path_hint": item.get("path_hint"),
                    "priority": item.get("priority", 2),
                }
                for item in actions
                if str(item.get("instruction", "")).strip()
            ],
        }

        return {
            "run_id": str(input_data.run_id),
            "iteration": input_data.iteration,
            "summary": summary,
            "target_files": target_files,
            "remediation_strategy": strategy,
            "qa_feedback": qa_feedback,
            "actions": actions,
        }


async def run_bugfix_agent(input_data: BugFixAgentInput | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(input_data, dict):
        input_data = BugFixAgentInput.model_validate(input_data)
    agent = BugFixAgent()
    return await agent.execute(input_data)
