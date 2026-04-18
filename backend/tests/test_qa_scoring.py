"""
Tests for QA scoring utility — qa_scoring.py

Owned by: Nisarg
"""

from __future__ import annotations

import pytest

from app.workflow.qa_scoring import calculate_qa_score, determine_qa_verdict, SEVERITY_WEIGHTS


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _story(status: str, priority: str = "must-have") -> dict:
    return {"priority": priority, "status": status}


def _bug(severity: str, status: str = "open") -> dict:
    return {"severity": severity, "status": status}


# ════════════════════════════════════════════════════════════════════════════
# calculate_qa_score
# ════════════════════════════════════════════════════════════════════════════

class TestCalculateQAScore:
    def test_perfect_score_no_bugs_full_coverage(self):
        matrix = [_story("COVERED"), _story("COVERED")]
        score = calculate_qa_score(matrix, [])
        assert score == 100.0

    def test_zero_must_haves_treated_as_full_coverage(self):
        # No must-haves → coverage is 100 → only bug score matters
        bugs = [_bug("low")]  # penalty = 2 → bug_score = 98
        score = calculate_qa_score([], bugs)
        # (100 * 0.6) + (98 * 0.4) = 60 + 39.2 = 99.2
        assert score == 99.2

    def test_partial_coverage_penalty(self):
        matrix = [_story("COVERED"), _story("MISSING"), _story("MISSING")]
        score = calculate_qa_score(matrix, [])
        # coverage = 1/3 = 33.33 → coverage_score = 33.33
        # bug_score = 100 (no bugs)
        # final = (33.33 * 0.6) + (100 * 0.4) = 20.0 + 40.0 = 60.0
        assert score == 60.0

    def test_critical_bug_heavy_penalty(self):
        # 1 critical open bug → penalty = 20 → bug_score = 80
        matrix = [_story("COVERED")]
        bugs = [_bug("critical")]
        score = calculate_qa_score(matrix, bugs)
        # (100 * 0.6) + (80 * 0.4) = 60 + 32 = 92.0
        assert score == 92.0

    def test_resolved_bugs_dont_penalise(self):
        matrix = [_story("COVERED")]
        bugs = [_bug("critical", status="resolved"), _bug("high", status="resolved")]
        score = calculate_qa_score(matrix, bugs)
        assert score == 100.0

    def test_multiple_bugs_cumulative_penalty(self):
        # critical(20) + high(10) + medium(5) = 35 → bug_score = 65
        matrix = [_story("COVERED")]
        bugs = [_bug("critical"), _bug("high"), _bug("medium")]
        score = calculate_qa_score(matrix, bugs)
        # (100 * 0.6) + (65 * 0.4) = 60 + 26 = 86.0
        assert score == 86.0

    def test_only_should_have_stories_are_ignored_for_coverage(self):
        # should-have stories don't affect must-have coverage
        matrix = [
            _story("MISSING", priority="should-have"),
            _story("MISSING", priority="could-have"),
        ]
        score = calculate_qa_score(matrix, [])
        # No must-haves → vacuously 100% → score = 100
        assert score == 100.0

    def test_score_cannot_go_below_zero(self):
        # 6 critical bugs → penalty = 120 → bug_score = max(0, -20) = 0
        matrix = [_story("COVERED")]
        bugs = [_bug("critical")] * 6
        score = calculate_qa_score(matrix, bugs)
        # (100 * 0.6) + (0 * 0.4) = 60.0
        assert score == 60.0

    def test_partial_story_counted_as_not_covered(self):
        # PARTIAL ≠ COVERED → not counted in the numerator
        matrix = [_story("COVERED"), _story("PARTIAL")]
        score = calculate_qa_score(matrix, [])
        # covered=1, total=2 → 50% → (50*0.6)+(100*0.4) = 30+40 = 70.0
        assert score == 70.0


# ════════════════════════════════════════════════════════════════════════════
# determine_qa_verdict
# ════════════════════════════════════════════════════════════════════════════

class TestDetermineQAVerdict:
    def test_pass_when_full_coverage_no_critical(self):
        matrix = [_story("COVERED"), _story("COVERED")]
        result = determine_qa_verdict(matrix, [])
        assert result["verdict"] == "PASS"
        assert result["route_to"] == "devops_and_docs"
        assert result["critical_bugs_count"] == 0

    def test_fail_when_critical_bug_present(self):
        matrix = [_story("COVERED")]
        bugs = [_bug("critical")]
        result = determine_qa_verdict(matrix, bugs)
        assert result["verdict"] == "FAIL"
        assert result["route_to"] == "developer"
        assert result["critical_bugs_count"] == 1

    def test_fail_when_must_have_missing(self):
        matrix = [_story("COVERED"), _story("MISSING")]
        result = determine_qa_verdict(matrix, [])
        assert result["verdict"] == "FAIL"
        assert result["must_have_coverage_percent"] == 50.0

    def test_fail_routes_to_human_review_at_max_iterations(self):
        matrix = [_story("MISSING")]
        result = determine_qa_verdict(matrix, [], max_iterations_reached=True)
        assert result["verdict"] == "FAIL"
        assert result["route_to"] == "human_review"

    def test_resolved_critical_does_not_trigger_fail(self):
        matrix = [_story("COVERED")]
        bugs = [_bug("critical", status="resolved")]
        result = determine_qa_verdict(matrix, bugs)
        assert result["verdict"] == "PASS"
        assert result["critical_bugs_count"] == 0

    def test_score_included_in_result(self):
        matrix = [_story("COVERED")]
        result = determine_qa_verdict(matrix, [])
        assert result["qa_score"] == 100.0


# ════════════════════════════════════════════════════════════════════════════
# Severity weights sanity check
# ════════════════════════════════════════════════════════════════════════════

class TestSeverityWeights:
    def test_critical_heavier_than_high(self):
        assert SEVERITY_WEIGHTS["critical"] > SEVERITY_WEIGHTS["high"]

    def test_high_heavier_than_medium(self):
        assert SEVERITY_WEIGHTS["high"] > SEVERITY_WEIGHTS["medium"]

    def test_medium_heavier_than_low(self):
        assert SEVERITY_WEIGHTS["medium"] > SEVERITY_WEIGHTS["low"]

    def test_all_four_severities_defined(self):
        assert set(SEVERITY_WEIGHTS.keys()) == {"critical", "high", "medium", "low"}
