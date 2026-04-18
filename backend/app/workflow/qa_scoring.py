"""
QA score calculation utility — used by the QA Agent (Anshul's domain)
but defined here as Nisarg owns the scoring formula specified in Section 8.

Formula (from spec):
  score = (coverage_score × 0.60) + (bug_score × 0.40)

  coverage_score = (covered_must_haves / total_must_haves) × 100
  bug_score      = max(0, 100 − Σ severity_weights[bug.severity])

Severity penalty weights:  critical=20, high=10, medium=5, low=2

Routing rule:
  PASS if critical_bugs == 0 AND must_have_coverage == 100%
  FAIL otherwise
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


def calculate_qa_score(
    traceability_matrix: List[Dict[str, Any]],
    bugs: List[Dict[str, Any]],
) -> float:
    """
    Calculate the QA score as specified in Section 8 of the ADWF spec.

    Args:
        traceability_matrix: List of traceability entries. Each entry has:
            - priority (str): 'must-have' | 'should-have' | 'could-have' | 'wont-have'
            - status (str):   'COVERED' | 'PARTIAL' | 'MISSING'
        bugs: List of bug dicts. Each has:
            - severity (str): 'critical' | 'high' | 'medium' | 'low'
            - status (str):   'open' | 'in_progress' | 'resolved' | 'wont_fix'

    Returns:
        Rounded float in [0, 100].
    """
    # ── Coverage component (60% weight) ──────────────────────────────────────
    must_haves = [s for s in traceability_matrix if s.get("priority") == "must-have"]
    total_must_haves = len(must_haves)

    if total_must_haves == 0:
        coverage_score = 100.0  # No must-haves → vacuously complete
    else:
        covered = sum(1 for s in must_haves if s.get("status") == "COVERED")
        coverage_score = (covered / total_must_haves) * 100.0

    # ── Bug penalty component (40% weight) ────────────────────────────────────
    open_bugs = [b for b in bugs if b.get("status", "open") == "open"]
    total_penalty = sum(
        SEVERITY_WEIGHTS.get(b.get("severity", "low"), 0) for b in open_bugs
    )
    bug_score = max(0.0, 100.0 - total_penalty)

    # ── Composite score ────────────────────────────────────────────────────────
    final = (coverage_score * 0.60) + (bug_score * 0.40)
    return round(final, 2)


def determine_qa_verdict(
    traceability_matrix: List[Dict[str, Any]],
    bugs: List[Dict[str, Any]],
    max_iterations_reached: bool = False,
) -> Dict[str, Any]:
    """
    Apply the QA routing rule from Section 5.6:
      PASS  → critical_bugs == 0 AND must_have_coverage == 100%
      FAIL  → otherwise
      route_to:
        'devops_and_docs'  on PASS
        'developer'        on FAIL (with iterations remaining)
        'human_review'     on FAIL (max iterations reached)

    Returns a dict with:
      verdict, qa_score, must_have_coverage_percent, critical_bugs_count, route_to
    """
    score = calculate_qa_score(traceability_matrix, bugs)

    # Must-have coverage percentage
    must_haves = [s for s in traceability_matrix if s.get("priority") == "must-have"]
    total = len(must_haves)
    if total == 0:
        coverage_pct = 100.0
    else:
        covered = sum(1 for s in must_haves if s.get("status") == "COVERED")
        coverage_pct = round((covered / total) * 100.0, 2)

    open_criticals = [
        b for b in bugs
        if b.get("severity") == "critical" and b.get("status", "open") == "open"
    ]
    critical_count = len(open_criticals)

    # Routing decision
    if critical_count == 0 and coverage_pct >= 100.0:
        verdict = "PASS"
        route_to = "devops_and_docs"
    else:
        verdict = "FAIL"
        route_to = "human_review" if max_iterations_reached else "developer"

    return {
        "verdict": verdict,
        "qa_score": score,
        "must_have_coverage_percent": coverage_pct,
        "critical_bugs_count": critical_count,
        "route_to": route_to,
    }
