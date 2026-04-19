"""QA scoring and routing utilities.

Current policy:
    weighted_total =
            feature_coverage * 0.35 +
            consistency * 0.25 +
            journey_completion * 0.25 +
            code_quality * 0.15

Routing:
    1) Any CRITICAL open bug        -> FAIL, route developer
    2) weighted_total >= 90         -> PASS, route devops_and_docs (legacy route name)
    3) 75 <= weighted_total < 90
             + HIGH bugs + retries left -> FAIL, route developer
    4) max iterations reached       -> FAIL, route human_review
    5) otherwise                    -> FAIL, route developer
"""

from __future__ import annotations

from typing import Any, Dict, List


# ── Severity penalty weights ──────────────────────────────────────────────────

SEVERITY_WEIGHTS: Dict[str, int] = {
    "critical": 20,
    "high": 10,
    "medium": 5,
    "low": 2,
}

SCORE_WEIGHTS: Dict[str, float] = {
    "feature_coverage": 0.35,
    "consistency": 0.25,
    "journey_completion": 0.25,
    "code_quality": 0.15,
}


def calculate_weighted_qa_score(metrics: Dict[str, float]) -> float:
    """Calculate weighted QA score using the configured scoring policy."""
    total = 0.0
    for key, weight in SCORE_WEIGHTS.items():
        value = float(metrics.get(key, 0.0))
        value = max(0.0, min(100.0, value))
        total += value * weight
    return round(total, 2)


def calculate_qa_score(
    traceability_matrix: List[Dict[str, Any]],
    bugs: List[Dict[str, Any]],
) -> float:
    """Backward-compatible score helper derived from traceability and bug list.

    This function keeps the old utility signature, but computes using the current
    weighted policy by deriving approximate consistency/journey/code-quality from bugs.
    """
    must_haves = [s for s in traceability_matrix if s.get("priority") == "must-have"]
    total_must_haves = len(must_haves)

    if total_must_haves == 0:
        feature_coverage = 100.0
    else:
        covered = sum(1 for s in must_haves if s.get("status") == "COVERED")
        feature_coverage = (covered / total_must_haves) * 100.0

    open_bugs = [b for b in bugs if b.get("status", "open") == "open"]
    high_or_worse = sum(1 for b in open_bugs if b.get("severity") in {"critical", "high"})

    penalty = sum(SEVERITY_WEIGHTS.get(str(b.get("severity", "low")), 0) for b in open_bugs)
    consistency = max(0.0, 100.0 - (penalty * 1.2))
    journey_completion = max(0.0, 100.0 - (high_or_worse * 20.0))
    code_quality = max(0.0, 100.0 - penalty)

    return calculate_weighted_qa_score(
        {
            "feature_coverage": feature_coverage,
            "consistency": consistency,
            "journey_completion": journey_completion,
            "code_quality": code_quality,
        }
    )


def determine_qa_verdict(
    traceability_matrix: List[Dict[str, Any]],
    bugs: List[Dict[str, Any]],
    max_iterations_reached: bool = False,
) -> Dict[str, Any]:
    """Determine QA verdict with critical-first and iteration-aware routing rules."""
    must_haves = [s for s in traceability_matrix if s.get("priority") == "must-have"]
    total = len(must_haves)
    if total == 0:
        coverage_pct = 100.0
    else:
        covered = sum(1 for s in must_haves if s.get("status") == "COVERED")
        coverage_pct = round((covered / total) * 100.0, 2)

    open_bugs = [b for b in bugs if b.get("status", "open") == "open"]
    open_criticals = [b for b in open_bugs if b.get("severity") == "critical"]
    open_high = [b for b in open_bugs if b.get("severity") == "high"]
    critical_count = len(open_criticals)
    score = calculate_qa_score(traceability_matrix, bugs)

    if critical_count > 0:
        verdict = "FAIL"
        route_to = "developer"
        reason = "Critical bugs found; looping back is mandatory."
    elif score >= 90.0:
        verdict = "PASS"
        route_to = "devops_and_docs"
        reason = "Score threshold met with no critical bugs."
    elif 75.0 <= score < 90.0 and len(open_high) > 0 and not max_iterations_reached:
        verdict = "FAIL"
        route_to = "developer"
        reason = "High-severity issues remain with iterations available."
    elif max_iterations_reached:
        verdict = "FAIL"
        route_to = "human_review"
        reason = "Max iterations reached with unresolved quality gaps; manual intervention required."
    else:
        verdict = "FAIL"
        route_to = "developer"
        reason = "Quality gates not met."

    return {
        "verdict": verdict,
        "qa_score": score,
        "must_have_coverage_percent": coverage_pct,
        "critical_bugs_count": critical_count,
        "route_to": route_to,
        "reason": reason,
    }
