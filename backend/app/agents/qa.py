import logging
import json
from typing import Any, Dict, List, Tuple

try:
    import json_repair
except Exception:  # pragma: no cover
    json_repair = None

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None

from app.core.config import settings
from app.schemas.agents import (
    BugOwner,
    BugSeverity,
    BugStatus,
    CoverageStatus,
    CriterionResult,
    QAAgentInput,
)
from app.workflow.qa_scoring import calculate_weighted_qa_score, determine_qa_verdict

logger = logging.getLogger(__name__)


QA_LLM_SYSTEM_PROMPT = """You are a senior QA lead.
Evaluate implementation quality from PRD + design spec + developer output.

Rules:
1. Return ONLY valid JSON.
2. Use schema exactly.
3. Prefer concrete findings tied to files/endpoints/screens.
4. Do not fabricate files not present in input.

Schema:
{
    "verdict": "PASS|FAIL",
    "qa_score": 0-100,
    "must_have_coverage_percent": 0-100,
    "critical_bugs_count": 0,
    "cross_document_issues": [
        {
            "issue_id": "XDOC-001",
            "severity": "critical|high|medium|low",
            "description": "...",
            "source_documents": ["Designer", "Developer"],
            "owner": "developer|designer|system_architect|product_manager|orchestrator|qa",
            "fix_instruction": "..."
        }
    ],
    "journey_simulations": [
        {
            "journey_id": "J-001",
            "journey_name": "...",
            "completion_status": "PASS|FAIL",
            "completion_percent": 0-100,
            "blocked_at_step": 1,
            "notes": "...",
            "steps": [{"step": 1, "action": "...", "status": "PASS|FAIL", "reason": "..."}]
        }
    ],
    "bugs": [
        {
            "bug_id": "QA-001",
            "severity": "critical|high|medium|low",
            "title": "...",
            "description": "...",
            "affected_file": "...",
            "affected_user_story": "US-001",
            "root_cause_phase": "developer|designer|system_architect|product_manager|orchestrator|qa",
            "fix_owner": "developer|designer|system_architect|product_manager|orchestrator|qa",
            "reproduction_steps": ["..."],
            "suggested_fix": "...",
            "status": "open|in_progress|resolved|wont_fix"
        }
    ],
    "routing_decision": {
        "route_to": "developer|devops_and_docs|human_review",
        "reason": "...",
        "fix_instructions": [{"bug_id": "...", "owner": "developer", "instruction": "..."}]
    },
    "score_breakdown": {
        "feature_coverage": 0-100,
        "consistency": 0-100,
        "journey_completion": 0-100,
        "code_quality": 0-100,
        "weighted_total": 0-100
    }
}
"""


SEVERITY_PENALTY = {
    BugSeverity.CRITICAL.value: 30,
    BugSeverity.HIGH.value: 18,
    BugSeverity.MEDIUM.value: 8,
    BugSeverity.LOW.value: 3,
}


def _extract_json_object(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty qa llm response")

    if json_repair is not None:
        try:
            parsed = json_repair.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    parsed = json.loads(text)
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("qa llm output is not a json object")


def _clamp_score(value: Any, default: float) -> float:
    try:
        number = float(value)
    except Exception:
        return default
    return max(0.0, min(100.0, round(number, 2)))


def _llm_provider_configs() -> List[Dict[str, str]]:
    providers: List[Dict[str, str]] = []
    if settings.OPENAI_API_KEY:
        providers.append(
            {
                "name": "groq",
                "api_key": settings.OPENAI_API_KEY,
                "base_url": settings.OPENAI_BASE_URL,
                "model": settings.OPENAI_MODEL,
            }
        )
    if settings.GEMINI_API_KEY:
        providers.append(
            {
                "name": "gemini",
                "api_key": settings.GEMINI_API_KEY,
                "base_url": settings.GEMINI_BASE_URL,
                "model": settings.GEMINI_MODEL,
            }
        )
    return providers


async def _evaluate_with_llm(input_data: QAAgentInput, max_iterations_reached: bool) -> Dict[str, Any] | None:
    if ChatOpenAI is None:
        return None

    payload = {
        "run_id": str(input_data.run_id),
        "iteration": input_data.iteration,
        "max_iterations": input_data.max_iterations,
        "max_iterations_reached": max_iterations_reached,
        "prd": input_data.prd.model_dump(mode="json"),
        "design_spec": input_data.design_spec.model_dump(mode="json"),
        "developer_output": input_data.developer_output.model_dump(mode="json"),
    }

    prompt = (
        "Evaluate this run and return strict JSON using the required schema.\n"
        "Focus on real issues only and route to devops_and_docs when quality is acceptable.\n"
        f"INPUT: {json.dumps(payload, ensure_ascii=True)}"
    )

    for provider in _llm_provider_configs():
        try:
            llm = ChatOpenAI(
                model=provider["model"],
                api_key=provider["api_key"],
                base_url=provider["base_url"],
                temperature=0.1,
                max_retries=1,
            )
            response = await llm.ainvoke([
                ("system", QA_LLM_SYSTEM_PROMPT),
                ("human", prompt),
            ])
            parsed = _extract_json_object(response.content)
            logger.info("[qa] llm evaluation succeeded provider=%s run_id=%s", provider["name"], str(input_data.run_id))
            return parsed
        except Exception as exc:
            logger.warning("[qa] llm evaluation failed provider=%s run_id=%s error=%s", provider["name"], str(input_data.run_id), str(exc)[:250])

    return None


def _contains_any(text: str, tokens: List[str]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _new_bug(
    bug_id: str,
    severity: BugSeverity,
    title: str,
    description: str,
    affected_file: str,
    owner: BugOwner,
    suggestion: str,
    user_story_id: str | None = None,
) -> Dict[str, Any]:
    return {
        "bug_id": bug_id,
        "severity": severity.value,
        "title": title,
        "description": description,
        "affected_file": affected_file,
        "affected_user_story": user_story_id,
        "root_cause_phase": owner.value,
        "fix_owner": owner.value,
        "reproduction_steps": ["Open generated artifacts", "Follow described flow", "Observe mismatch against expected behavior"],
        "suggested_fix": suggestion,
        "status": BugStatus.OPEN.value,
    }


def _file_links_to_story(generated_file: Any, story_id: str) -> bool:
    """Check whether a generated file appears to implement the given user story.

    Some Developer outputs don't provide direct story mapping fields, so this
    method gracefully falls back to text-based hints.
    """
    story_links = getattr(generated_file, "maps_to_user_stories", None)
    if isinstance(story_links, list) and story_id in story_links:
        return True

    haystack = " ".join(
        [
            str(getattr(generated_file, "path", "") or ""),
            str(getattr(generated_file, "purpose", "") or ""),
            str(getattr(generated_file, "content", "") or ""),
        ]
    ).lower()
    return story_id.lower() in haystack


def _layer1_traceability(input_data: QAAgentInput) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    files = input_data.developer_output.files_created
    tests_written = [test_name.lower() for test_name in input_data.developer_output.tests_written]
    must_have_stories = [story for story in input_data.prd.user_stories if story.priority.value == "must-have"]

    traceability_matrix: List[Dict[str, Any]] = []
    bugs: List[Dict[str, Any]] = []

    for index, story in enumerate(must_have_stories, start=1):
        implementing_files = [f.path for f in files if _file_links_to_story(f, story.id)]
        implementing_endpoints = {
            endpoint.endpoint_id
            for endpoint in input_data.design_spec.api_spec
            if story.id in endpoint.maps_to_user_stories
        }
        mapped_endpoint_ids = {endpoint_id for f in files for endpoint_id in f.maps_to_endpoint_ids}

        if implementing_files and implementing_endpoints.issubset(mapped_endpoint_ids):
            status = CoverageStatus.COVERED.value
            criterion_result = CriterionResult.PASS.value
        elif implementing_files:
            status = CoverageStatus.PARTIAL.value
            criterion_result = CriterionResult.FAIL.value
        else:
            status = CoverageStatus.MISSING.value
            criterion_result = CriterionResult.FAIL.value

        acceptance_results = []
        for criterion in story.acceptance_criteria:
            criterion_label = f"GIVEN {criterion.given} WHEN {criterion.when} THEN {criterion.then}"
            acceptance_results.append(
                {
                    "criterion": criterion_label,
                    "result": criterion_result,
                    "notes": "Verified through generated file mappings and endpoint alignment.",
                }
            )

        traceability_matrix.append(
            {
                "user_story_id": story.id,
                "feature_name": story.action,
                "status": status,
                "implementing_files": implementing_files,
                "acceptance_criteria_results": acceptance_results,
                "priority": "must-have",
            }
        )

        if status != CoverageStatus.COVERED.value:
            severity = BugSeverity.CRITICAL if status == CoverageStatus.MISSING.value else BugSeverity.HIGH
            bugs.append(
                _new_bug(
                    bug_id=f"QA-L1-{index:03d}",
                    severity=severity,
                    title=f"Must-have user story {story.id} is not fully implemented",
                    description=f"Story {story.id} is marked {status}. Expected full implementation of all acceptance criteria.",
                    affected_file=implementing_files[0] if implementing_files else "unknown",
                    owner=BugOwner.DEVELOPER,
                    suggestion="Implement missing story flows and ensure endpoint mappings cover all required criteria.",
                    user_story_id=story.id,
                )
            )

        has_test_hint = any(story.id.lower() in test_name for test_name in tests_written)
        if not has_test_hint:
            bugs.append(
                _new_bug(
                    bug_id=f"QA-L1-T{index:03d}",
                    severity=BugSeverity.MEDIUM,
                    title=f"Missing explicit test coverage for {story.id}",
                    description=f"No test reference found for must-have story {story.id}.",
                    affected_file="tests",
                    owner=BugOwner.DEVELOPER,
                    suggestion="Add an automated test that validates this story's GIVEN/WHEN/THEN behavior.",
                    user_story_id=story.id,
                )
            )

    total = len(must_have_stories)
    covered = sum(1 for row in traceability_matrix if row["status"] == CoverageStatus.COVERED.value)
    coverage_percent = 100.0 if total == 0 else round((covered / total) * 100.0, 2)
    return traceability_matrix, bugs, coverage_percent


def _layer2_consistency(input_data: QAAgentInput) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    files = input_data.developer_output.files_created
    screen_ids = {screen.screen_id for screen in input_data.design_spec.screens}
    endpoint_ids = {endpoint.endpoint_id for endpoint in input_data.design_spec.api_spec}

    mapped_screen_ids = {screen_id for f in files for screen_id in f.maps_to_screen_ids}
    mapped_endpoint_ids = {endpoint_id for f in files for endpoint_id in f.maps_to_endpoint_ids}

    issues: List[Dict[str, Any]] = []
    bugs: List[Dict[str, Any]] = []
    issue_index = 1

    unknown_screens = sorted(mapped_screen_ids - screen_ids)
    if unknown_screens:
        issues.append(
            {
                "issue_id": f"XDOC-{issue_index:03d}",
                "severity": BugSeverity.HIGH.value,
                "description": f"Developer references undefined screens: {', '.join(unknown_screens)}",
                "source_documents": ["Designer", "Developer"],
                "owner": BugOwner.DEVELOPER.value,
                "fix_instruction": "Align generated screen mappings with design screen identifiers.",
            }
        )
        bugs.append(
            _new_bug(
                bug_id=f"QA-L2-{issue_index:03d}",
                severity=BugSeverity.HIGH,
                title="Screen mapping mismatch",
                description="Developer output references screens that do not exist in the design spec.",
                affected_file="frontend",
                owner=BugOwner.DEVELOPER,
                suggestion="Update file-to-screen mappings to valid screen_id values from design spec.",
            )
        )
        issue_index += 1

    missing_screen_impl = sorted(screen_ids - mapped_screen_ids)
    if missing_screen_impl:
        issues.append(
            {
                "issue_id": f"XDOC-{issue_index:03d}",
                "severity": BugSeverity.MEDIUM.value,
                "description": f"Design screens not mapped in implementation: {', '.join(missing_screen_impl)}",
                "source_documents": ["Designer", "Developer"],
                "owner": BugOwner.DESIGNER.value,
                "fix_instruction": "Ensure all designed screens are either implemented or explicitly scoped out.",
            }
        )
        bugs.append(
            _new_bug(
                bug_id=f"QA-L2-{issue_index:03d}",
                severity=BugSeverity.MEDIUM,
                title="Screen implementation gaps",
                description="Some design screens are not represented by generated implementation files.",
                affected_file="frontend",
                owner=BugOwner.DESIGNER,
                suggestion="Refine design scope or provide implementation-ready mappings for missing screens.",
            )
        )
        issue_index += 1

    unknown_endpoints = sorted(mapped_endpoint_ids - endpoint_ids)
    if unknown_endpoints:
        issues.append(
            {
                "issue_id": f"XDOC-{issue_index:03d}",
                "severity": BugSeverity.HIGH.value,
                "description": f"Developer references undefined API endpoints: {', '.join(unknown_endpoints)}",
                "source_documents": ["System Architect", "Developer"],
                "owner": BugOwner.SYSTEM_ARCHITECT.value,
                "fix_instruction": "Reconcile endpoint IDs between API contract and implementation manifest.",
            }
        )
        bugs.append(
            _new_bug(
                bug_id=f"QA-L2-{issue_index:03d}",
                severity=BugSeverity.HIGH,
                title="API contract mismatch",
                description="Generated endpoint mappings include identifiers not present in the design contract.",
                affected_file="backend",
                owner=BugOwner.SYSTEM_ARCHITECT,
                suggestion="Update API contracts or mappings to a single canonical endpoint set.",
            )
        )

    return issues, bugs


def _build_journey_result(
    journey_id: str,
    journey_name: str,
    steps: List[Tuple[str, bool, str]],
) -> Dict[str, Any]:
    step_rows: List[Dict[str, Any]] = []
    passed_steps = 0
    blocked_at = None
    for idx, (action, ok, reason) in enumerate(steps, start=1):
        step_rows.append(
            {
                "step": idx,
                "action": action,
                "status": CriterionResult.PASS.value if ok else CriterionResult.FAIL.value,
                "reason": reason,
            }
        )
        if ok:
            passed_steps += 1
        elif blocked_at is None:
            blocked_at = idx

    completion_percent = 100.0 if not steps else round((passed_steps / len(steps)) * 100.0, 2)
    completion_status = CriterionResult.PASS.value if completion_percent == 100.0 else CriterionResult.FAIL.value

    return {
        "journey_id": journey_id,
        "journey_name": journey_name,
        "completion_status": completion_status,
        "completion_percent": completion_percent,
        "blocked_at_step": blocked_at,
        "notes": "Simulated against generated route and endpoint artifacts.",
        "steps": step_rows,
    }


def _layer3_journey_checks(input_data: QAAgentInput) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    routes = {screen.route.lower() for screen in input_data.design_spec.screens}
    endpoints = {endpoint.path.lower() for endpoint in input_data.design_spec.api_spec}

    signup_steps = [
        ("Open onboarding/signup screen", any(_contains_any(route, ["signup", "onboard", "register"]) for route in routes), "Signup route missing"),
        ("Create account", any(_contains_any(path, ["signup", "register", "users"]) for path in endpoints), "Signup API missing"),
        ("Complete first habit/task", any(_contains_any(path, ["habit", "task", "complete", "checkin"]) for path in endpoints), "Habit completion API missing"),
    ]

    daily_steps = [
        ("Open notification/deeplink flow", any(_contains_any(route, ["notifications", "inbox", "dashboard"]) for route in routes), "Notification entry route missing"),
        ("Tap into daily action", any(_contains_any(path, ["daily", "habit", "task"]) for path in endpoints), "Daily action endpoint missing"),
        ("Mark task/habit complete", any(_contains_any(path, ["complete", "done", "checkin"]) for path in endpoints), "Completion endpoint missing"),
    ]

    journey_results = [
        _build_journey_result("J-001", "First-time user signup to first habit completion", signup_steps),
        _build_journey_result("J-002", "Returning user from notification to completion", daily_steps),
    ]

    bugs: List[Dict[str, Any]] = []
    for idx, journey in enumerate(journey_results, start=1):
        if journey["completion_status"] == CriterionResult.FAIL.value:
            bugs.append(
                _new_bug(
                    bug_id=f"QA-L3-{idx:03d}",
                    severity=BugSeverity.HIGH,
                    title=f"Journey failure: {journey['journey_name']}",
                    description=f"Journey blocked at step {journey.get('blocked_at_step')}.",
                    affected_file="frontend/backend",
                    owner=BugOwner.DEVELOPER,
                    suggestion="Implement missing route/endpoint dependencies so the journey completes end-to-end.",
                )
            )

    two_tap_promised = any(
        _contains_any(decision, ["two-tap", "two tap", "2 tap"])
        for screen in input_data.design_spec.screens
        for decision in screen.ux_decisions
    )
    if two_tap_promised:
        min_steps = min((len(j["steps"]) for j in journey_results), default=0)
        if min_steps > 2:
            bugs.append(
                _new_bug(
                    bug_id="QA-L3-900",
                    severity=BugSeverity.MEDIUM,
                    title="Two-tap UX promise not achievable",
                    description="UX promises two taps but current simulated flows require additional steps.",
                    affected_file="frontend",
                    owner=BugOwner.DESIGNER,
                    suggestion="Reduce flow friction or update UX commitments to match implementation reality.",
                )
            )

    journey_score = round(
        sum(journey["completion_percent"] for journey in journey_results) / max(1, len(journey_results)),
        2,
    )
    return journey_results, bugs, journey_score


def _layer4_code_quality(input_data: QAAgentInput) -> Tuple[List[Dict[str, Any]], float]:
    bugs: List[Dict[str, Any]] = []
    quality_penalty = 0.0

    for idx, generated_file in enumerate(input_data.developer_output.files_created, start=1):
        content = generated_file.content or ""
        if _contains_any(content, ["todo", "fixme"]):
            bugs.append(
                _new_bug(
                    bug_id=f"QA-L4-{idx:03d}",
                    severity=BugSeverity.LOW,
                    title="Placeholder implementation marker found",
                    description=f"File contains TODO/FIXME markers: {generated_file.path}",
                    affected_file=generated_file.path,
                    owner=BugOwner.DEVELOPER,
                    suggestion="Resolve TODO/FIXME markers with complete implementation or explicit backlog references.",
                )
            )
            quality_penalty += SEVERITY_PENALTY[BugSeverity.LOW.value]

        if _contains_any(content, ["eval(", "exec(", "pickle.loads("]):
            bugs.append(
                _new_bug(
                    bug_id=f"QA-L4-S{idx:03d}",
                    severity=BugSeverity.HIGH,
                    title="Potentially unsafe code pattern",
                    description=f"Potential security-sensitive primitive found in {generated_file.path}",
                    affected_file=generated_file.path,
                    owner=BugOwner.DEVELOPER,
                    suggestion="Replace unsafe runtime execution with validated, bounded logic.",
                )
            )
            quality_penalty += SEVERITY_PENALTY[BugSeverity.HIGH.value]

    if input_data.developer_output.status.value != "completed":
        bugs.append(
            _new_bug(
                bug_id="QA-L4-999",
                severity=BugSeverity.HIGH,
                title="Developer output not fully completed",
                description="Developer marked output as partial/failed.",
                affected_file="developer_output",
                owner=BugOwner.DEVELOPER,
                suggestion="Complete incomplete implementation areas before final handoff.",
            )
        )
        quality_penalty += SEVERITY_PENALTY[BugSeverity.HIGH.value]

    code_quality_score = max(0.0, round(100.0 - quality_penalty, 2))
    return bugs, code_quality_score


def _consistency_score(issues: List[Dict[str, Any]], bugs: List[Dict[str, Any]]) -> float:
    penalty = 0
    for issue in issues:
        penalty += SEVERITY_PENALTY.get(issue.get("severity", "low"), 0)
    for bug in bugs:
        penalty += SEVERITY_PENALTY.get(bug.get("severity", "low"), 0)
    return max(0.0, round(100.0 - penalty, 2))


def _meta_quality_report(verdict: str, critical_bugs_count: int, route_to: str) -> Dict[str, Any]:
    notes: List[str] = []
    consistent = True
    if critical_bugs_count > 0 and route_to != "developer":
        consistent = False
        notes.append("Critical bug exists but route is not developer.")
    if verdict == "PASS" and critical_bugs_count > 0:
        consistent = False
        notes.append("PASS verdict conflicts with critical bug count.")
    if not notes:
        notes.append("QA verdict is coherent with severity gates and routing policy.")
    return {"verdict_consistent": consistent, "notes": notes}


async def run_qa_agent(input_data: QAAgentInput | Dict[str, Any]) -> Dict[str, Any]:
    """Workflow entrypoint for QA Agent with multi-layer validation."""
    if isinstance(input_data, dict):
        input_data = QAAgentInput.model_validate(input_data)

    run_id = str(input_data.run_id)
    iteration = input_data.iteration
    max_iterations = max(1, input_data.max_iterations)
    max_iterations_reached = iteration >= max_iterations

    # Layer 1: Must-have traceability, API and test coverage
    traceability_matrix, layer1_bugs, coverage_percent = _layer1_traceability(input_data)

    # Layer 2: Cross-document consistency
    cross_document_issues, layer2_bugs = _layer2_consistency(input_data)

    # Layer 3: End-to-end journey simulations
    journey_simulations, layer3_bugs, journey_score = _layer3_journey_checks(input_data)

    # Layer 4: Code quality and static-risk checks
    layer4_bugs, code_quality_score = _layer4_code_quality(input_data)

    bugs = layer1_bugs + layer2_bugs + layer3_bugs + layer4_bugs
    consistency_score = _consistency_score(cross_document_issues, layer2_bugs)

    weighted_score = calculate_weighted_qa_score(
        {
            "feature_coverage": coverage_percent,
            "consistency": consistency_score,
            "journey_completion": journey_score,
            "code_quality": code_quality_score,
        }
    )

    verdict_data = determine_qa_verdict(
        traceability_matrix=traceability_matrix,
        bugs=bugs,
        max_iterations_reached=max_iterations_reached,
    )

    llm_eval = await _evaluate_with_llm(input_data, max_iterations_reached)
    if isinstance(llm_eval, dict):
        llm_bugs = llm_eval.get("bugs", [])
        if isinstance(llm_bugs, list):
            bugs = [item for item in llm_bugs if isinstance(item, dict)]

        llm_issues = llm_eval.get("cross_document_issues", [])
        if isinstance(llm_issues, list):
            cross_document_issues = [item for item in llm_issues if isinstance(item, dict)]

        llm_journeys = llm_eval.get("journey_simulations", [])
        if isinstance(llm_journeys, list):
            journey_simulations = [item for item in llm_journeys if isinstance(item, dict)]

        weighted_score = _clamp_score(llm_eval.get("qa_score"), weighted_score)
        coverage_percent = _clamp_score(llm_eval.get("must_have_coverage_percent"), coverage_percent)

        route_payload = llm_eval.get("routing_decision", {}) if isinstance(llm_eval.get("routing_decision", {}), dict) else {}
        route_to = str(route_payload.get("route_to", verdict_data.get("route_to", "developer"))).lower()
        if route_to not in {"developer", "devops_and_docs", "human_review"}:
            route_to = verdict_data.get("route_to", "developer")

        verdict = str(llm_eval.get("verdict", verdict_data.get("verdict", "FAIL"))).upper()
        if verdict not in {"PASS", "FAIL"}:
            verdict = verdict_data.get("verdict", "FAIL")

        critical_count = sum(
            1
            for bug in bugs
            if str(bug.get("status", "open")).lower() in {"open", "in_progress"}
            and str(bug.get("severity", "")).lower() == "critical"
        )

        verdict_data = {
            **verdict_data,
            "verdict": verdict,
            "route_to": route_to,
            "critical_bugs_count": critical_count,
            "must_have_coverage_percent": coverage_percent,
            "reason": str(route_payload.get("reason") or llm_eval.get("reason") or verdict_data.get("reason", "QA routing decision computed.")),
        }

        llm_breakdown = llm_eval.get("score_breakdown", {}) if isinstance(llm_eval.get("score_breakdown", {}), dict) else {}
        feature_cov = _clamp_score(llm_breakdown.get("feature_coverage"), coverage_percent)
        consistency_score = _clamp_score(llm_breakdown.get("consistency"), consistency_score)
        journey_score = _clamp_score(llm_breakdown.get("journey_completion"), journey_score)
        code_quality_score = _clamp_score(llm_breakdown.get("code_quality"), code_quality_score)
        weighted_score = _clamp_score(llm_breakdown.get("weighted_total"), weighted_score)

    route_to = verdict_data["route_to"]
    fix_instructions = [
        {
            "bug_id": bug["bug_id"],
            "owner": bug.get("fix_owner", BugOwner.DEVELOPER.value),
            "instruction": bug.get("suggested_fix", "Investigate and resolve this issue."),
        }
        for bug in bugs
        if bug.get("status") == BugStatus.OPEN.value
    ]

    meta_report = _meta_quality_report(
        verdict=verdict_data["verdict"],
        critical_bugs_count=verdict_data["critical_bugs_count"],
        route_to=route_to,
    )

    logger.info(
        "[qa] run_id=%s iteration=%s score=%.2f verdict=%s bugs=%s critical=%s route=%s",
        run_id,
        iteration,
        weighted_score,
        verdict_data["verdict"],
        len(bugs),
        verdict_data["critical_bugs_count"],
        route_to,
    )

    return {
        "run_id": run_id,
        "verdict": verdict_data["verdict"],
        "qa_score": weighted_score,
        "iteration": iteration,
        "traceability_matrix": traceability_matrix,
        "cross_document_issues": cross_document_issues,
        "journey_simulations": journey_simulations,
        "bugs": bugs,
        "score_breakdown": {
            "feature_coverage": coverage_percent,
            "consistency": consistency_score,
            "journey_completion": journey_score,
            "code_quality": code_quality_score,
            "weighted_total": weighted_score,
        },
        "routing_decision": {
            "route_to": route_to,
            "reason": verdict_data.get("reason", "QA routing decision computed."),
            "fix_instructions": fix_instructions,
        },
        "meta_quality_report": meta_report,
        "must_have_coverage_percent": coverage_percent,
        "critical_bugs_count": verdict_data["critical_bugs_count"],
    }
