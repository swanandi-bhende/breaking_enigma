import React, { useMemo, useState } from 'react';

type QASeverity = 'critical' | 'high' | 'medium' | 'low';

interface QABug {
  bug_id: string;
  severity: QASeverity;
  title: string;
  description: string;
  affected_file: string;
  affected_user_story?: string | null;
  root_cause_phase?: string | null;
  fix_owner?: string | null;
  suggested_fix?: string | null;
  status?: string;
}

interface QATraceabilityRow {
  user_story_id: string;
  feature_name: string;
  status: 'COVERED' | 'PARTIAL' | 'MISSING' | string;
  implementing_files: string[];
}

interface QAJourneyStep {
  step: number;
  action: string;
  status: 'PASS' | 'FAIL' | 'UNTESTABLE' | string;
  reason?: string | null;
}

interface QAJourney {
  journey_id: string;
  journey_name: string;
  completion_status: 'PASS' | 'FAIL' | string;
  completion_percent: number;
  blocked_at_step?: number | null;
  notes?: string | null;
  steps: QAJourneyStep[];
}

interface QABreakdown {
  feature_coverage?: number;
  consistency?: number;
  journey_completion?: number;
  code_quality?: number;
  weighted_total?: number;
}

interface QAIssue {
  issue_id: string;
  severity: QASeverity;
  description: string;
  owner?: string;
  fix_instruction?: string;
}

interface QARoutingDecision {
  route_to?: string;
  reason?: string;
  fix_instructions?: Array<Record<string, unknown>>;
}

interface QAPayload {
  verdict?: 'PASS' | 'FAIL' | string;
  qa_score?: number;
  iteration?: number;
  critical_bugs_count?: number;
  must_have_coverage_percent?: number;
  bugs?: QABug[];
  score_breakdown?: QABreakdown;
  traceability_matrix?: QATraceabilityRow[];
  journey_simulations?: QAJourney[];
  cross_document_issues?: QAIssue[];
  routing_decision?: QARoutingDecision;
  meta_quality_report?: {
    verdict_consistent?: boolean;
    notes?: string[];
  };
}

const severityTone: Record<QASeverity, string> = {
  critical: 'bg-red-500/20 text-red-300 border-red-500/40',
  high: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  medium: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  low: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
};

function scoreBarColor(score: number): string {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 60) return 'bg-amber-500';
  return 'bg-rose-500';
}

function prettyLabel(value: string): string {
  return value
    .split('_')
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(' ');
}

function normalizeBugs(payload: QAPayload): QABug[] {
  return Array.isArray(payload.bugs) ? payload.bugs : [];
}

function normalizeTraceability(payload: QAPayload): QATraceabilityRow[] {
  return Array.isArray(payload.traceability_matrix) ? payload.traceability_matrix : [];
}

function normalizeJourneys(payload: QAPayload): QAJourney[] {
  return Array.isArray(payload.journey_simulations) ? payload.journey_simulations : [];
}

function normalizeIssues(payload: QAPayload): QAIssue[] {
  return Array.isArray(payload.cross_document_issues) ? payload.cross_document_issues : [];
}

function normalizePayload(payload: unknown): QAPayload {
  if (payload && typeof payload === 'object') return payload as QAPayload;
  if (typeof payload === 'string') {
    try {
      const parsed = JSON.parse(payload) as unknown;
      if (parsed && typeof parsed === 'object') return parsed as QAPayload;
    } catch {
      return {};
    }
  }
  return {};
}

export default function QAPanel({ payload }: { payload: unknown }) {
  const normalizedPayload = useMemo(() => normalizePayload(payload), [payload]);

  const bugs = normalizeBugs(normalizedPayload);
  const traceability = normalizeTraceability(normalizedPayload);
  const journeys = normalizeJourneys(normalizedPayload);
  const crossDocIssues = normalizeIssues(normalizedPayload);

  const [severityFilter, setSeverityFilter] = useState<'all' | QASeverity>('all');
  const [activeTab, setActiveTab] = useState<'overview' | 'defects' | 'journeys' | 'governance'>('overview');
  const [selectedJourneyId, setSelectedJourneyId] = useState<string>(journeys[0]?.journey_id || '');

  const verdict = String(normalizedPayload.verdict || 'PENDING');
  const qaScore = typeof normalizedPayload.qa_score === 'number' ? normalizedPayload.qa_score : 0;
  const mustHaveCoverage = typeof normalizedPayload.must_have_coverage_percent === 'number' ? normalizedPayload.must_have_coverage_percent : 0;
  const criticalCount = typeof normalizedPayload.critical_bugs_count === 'number' ? normalizedPayload.critical_bugs_count : 0;

  const bugCounts = useMemo(() => {
    const counters: Record<QASeverity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    bugs.forEach((bug) => {
      if (bug.severity in counters) counters[bug.severity] += 1;
    });
    return counters;
  }, [bugs]);

  const ownershipCounts = useMemo(() => {
    const counters: Record<string, number> = {};
    bugs.forEach((bug) => {
      const owner = bug.fix_owner || 'unassigned';
      counters[owner] = (counters[owner] || 0) + 1;
    });
    return Object.entries(counters).sort((a, b) => b[1] - a[1]);
  }, [bugs]);

  const filteredBugs = useMemo(() => {
    if (severityFilter === 'all') return bugs;
    return bugs.filter((bug) => bug.severity === severityFilter);
  }, [bugs, severityFilter]);

  const selectedJourney = journeys.find((journey) => journey.journey_id === selectedJourneyId) || journeys[0];
  const scoreBreakdown = normalizedPayload.score_breakdown || {};

  return (
    <div className="space-y-5">
      <section className="bg-surface border border-border rounded-lg p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-[var(--agent-qa)]">QA Insights Dashboard</h3>
            <p className="text-xs text-text-secondary mt-1">Interactive quality analysis across coverage, consistency, journeys, and defects.</p>
          </div>
          <span className={`text-xs px-3 py-1 rounded-full border ${verdict === 'PASS' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' : 'bg-rose-500/20 text-rose-300 border-rose-500/40'}`}>
            Verdict: {verdict}
          </span>
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          {[
            ['overview', 'Overview'],
            ['defects', 'Defects'],
            ['journeys', 'Journeys'],
            ['governance', 'Governance'],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setActiveTab(value as 'overview' | 'defects' | 'journeys' | 'governance')}
              className={`px-3 py-1.5 rounded-full border text-xs transition ${activeTab === value ? 'border-[var(--agent-qa)] text-[var(--agent-qa)] bg-[var(--agent-qa)]/10' : 'border-border text-text-secondary hover:text-text-primary'}`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
          <article className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-xs uppercase tracking-wide text-text-secondary">QA Score</p>
            <p className="text-2xl font-semibold text-text-primary mt-1">{qaScore.toFixed(1)}</p>
            <div className="h-2 rounded-full bg-slate-700/40 mt-3 overflow-hidden">
              <div className={`h-full ${scoreBarColor(qaScore)}`} style={{ width: `${Math.max(0, Math.min(100, qaScore))}%` }} />
            </div>
          </article>

          <article className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-xs uppercase tracking-wide text-text-secondary">Must-have Coverage</p>
            <p className="text-2xl font-semibold text-text-primary mt-1">{mustHaveCoverage.toFixed(1)}%</p>
            <p className="text-xs text-text-secondary mt-2">Traceability to critical user stories</p>
          </article>

          <article className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-xs uppercase tracking-wide text-text-secondary">Critical Bugs</p>
            <p className="text-2xl font-semibold text-text-primary mt-1">{criticalCount}</p>
            <p className="text-xs text-text-secondary mt-2">Blocking issues requiring immediate fix</p>
          </article>

          <article className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-xs uppercase tracking-wide text-text-secondary">Iteration</p>
            <p className="text-2xl font-semibold text-text-primary mt-1">{normalizedPayload.iteration || 1}</p>
            <p className="text-xs text-text-secondary mt-2">QA cycle index</p>
          </article>
        </div>
      </section>

      {activeTab === 'overview' ? <section className="bg-surface border border-border rounded-lg p-5 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Score Breakdown</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {[
            ['Feature Coverage', scoreBreakdown.feature_coverage],
            ['Consistency', scoreBreakdown.consistency],
            ['Journey Completion', scoreBreakdown.journey_completion],
            ['Code Quality', scoreBreakdown.code_quality],
            ['Weighted Total', scoreBreakdown.weighted_total],
          ].map(([label, raw]) => {
            const score = typeof raw === 'number' ? raw : 0;
            return (
              <article key={String(label)} className="bg-bg-base border border-border rounded-md p-3">
                <p className="text-xs uppercase tracking-wide text-text-secondary">{label}</p>
                <p className="text-xl font-semibold text-text-primary mt-1">{score.toFixed(1)}</p>
                <div className="h-1.5 rounded-full bg-slate-700/40 mt-2 overflow-hidden">
                  <div className={`h-full ${scoreBarColor(score)}`} style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
                </div>
              </article>
            );
          })}
        </div>
      </section> : null}

      {activeTab === 'defects' ? <section className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <article className="lg:col-span-8 bg-surface border border-border rounded-lg p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Bugs & Fix Insights</h4>
            <div className="flex flex-wrap gap-2">
              {(['all', 'critical', 'high', 'medium', 'low'] as const).map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setSeverityFilter(level)}
                  className={`px-2.5 py-1 rounded-full border text-xs transition ${severityFilter === level ? 'border-[var(--agent-qa)] text-[var(--agent-qa)] bg-[var(--agent-qa)]/10' : 'border-border text-text-secondary hover:text-text-primary'}`}
                >
                  {level === 'all' ? 'All' : prettyLabel(level)}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2 max-h-[24rem] overflow-auto pr-1">
            {filteredBugs.length > 0 ? filteredBugs.map((bug) => (
              <div key={bug.bug_id} className="bg-bg-base border border-border rounded-md p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-text-primary">{bug.title}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${severityTone[bug.severity] || severityTone.low}`}>
                    {bug.severity}
                  </span>
                </div>
                <p className="text-xs text-text-secondary mt-1">{bug.bug_id} | File: {bug.affected_file || '-'}</p>
                <p className="text-sm text-text-primary mt-2">{bug.description}</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2 text-xs text-text-secondary">
                  <p>Fix Owner: <span className="text-text-primary">{prettyLabel(String(bug.fix_owner || 'unassigned'))}</span></p>
                  <p>Root Cause: <span className="text-text-primary">{prettyLabel(String(bug.root_cause_phase || 'unknown'))}</span></p>
                </div>
                {bug.suggested_fix ? <p className="text-xs text-text-primary mt-2 bg-slate-700/20 rounded-md p-2 border border-border">Suggested Fix: {bug.suggested_fix}</p> : null}
              </div>
            )) : <p className="text-sm text-text-secondary">No bugs match the selected severity filter.</p>}
          </div>
        </article>

        <article className="lg:col-span-4 bg-surface border border-border rounded-lg p-5 space-y-3">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Defect Analytics</h4>
          <div className="space-y-2">
            {(['critical', 'high', 'medium', 'low'] as const).map((level) => (
              <div key={level} className="flex items-center justify-between bg-bg-base border border-border rounded-md px-3 py-2">
                <span className={`text-xs px-2 py-0.5 rounded-full border ${severityTone[level]}`}>{prettyLabel(level)}</span>
                <span className="text-sm font-semibold text-text-primary">{bugCounts[level]}</span>
              </div>
            ))}
          </div>

          <h5 className="text-xs uppercase tracking-wide text-text-secondary pt-2">Ownership Load</h5>
          <div className="space-y-2">
            {ownershipCounts.length > 0 ? ownershipCounts.map(([owner, count]) => (
              <div key={owner} className="flex items-center justify-between bg-bg-base border border-border rounded-md px-3 py-2">
                <span className="text-sm text-text-primary">{prettyLabel(owner)}</span>
                <span className="text-xs text-text-secondary">{count}</span>
              </div>
            )) : <p className="text-sm text-text-secondary">No ownership data yet.</p>}
          </div>
        </article>
      </section> : null}

      {activeTab === 'journeys' ? <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <article className="bg-surface border border-border rounded-lg p-5 space-y-3">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Traceability Matrix</h4>
          <div className="space-y-2 max-h-72 overflow-auto pr-1">
            {traceability.length > 0 ? traceability.map((row) => {
              const tone = row.status === 'COVERED' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' : row.status === 'PARTIAL' ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-rose-500/20 text-rose-300 border-rose-500/40';
              return (
                <div key={`${row.user_story_id}-${row.feature_name}`} className="bg-bg-base border border-border rounded-md p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm text-text-primary font-medium">{row.user_story_id} - {row.feature_name}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${tone}`}>{row.status}</span>
                  </div>
                  <p className="text-xs text-text-secondary mt-1">Implementing files: {row.implementing_files?.length || 0}</p>
                </div>
              );
            }) : <p className="text-sm text-text-secondary">No traceability rows found.</p>}
          </div>
        </article>

        <article className="bg-surface border border-border rounded-lg p-5 space-y-3">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Journey Simulation</h4>
          {journeys.length > 0 ? (
            <>
              <div className="flex flex-wrap gap-2">
                {journeys.map((journey) => (
                  <button
                    key={journey.journey_id}
                    type="button"
                    onClick={() => setSelectedJourneyId(journey.journey_id)}
                    className={`px-2.5 py-1 rounded-full border text-xs transition ${selectedJourney?.journey_id === journey.journey_id ? 'border-[var(--agent-qa)] text-[var(--agent-qa)] bg-[var(--agent-qa)]/10' : 'border-border text-text-secondary hover:text-text-primary'}`}
                  >
                    {journey.journey_id}
                  </button>
                ))}
              </div>

              {selectedJourney ? (
                <div className="bg-bg-base border border-border rounded-md p-3 space-y-2">
                  <p className="text-sm font-medium text-text-primary">{selectedJourney.journey_name}</p>
                  <p className="text-xs text-text-secondary">Completion: {selectedJourney.completion_percent?.toFixed(1) || '0.0'}%</p>
                  <div className="h-2 rounded-full bg-slate-700/40 overflow-hidden">
                    <div className={`h-full ${scoreBarColor(selectedJourney.completion_percent || 0)}`} style={{ width: `${Math.max(0, Math.min(100, selectedJourney.completion_percent || 0))}%` }} />
                  </div>
                  <div className="space-y-1 pt-1 max-h-40 overflow-auto pr-1">
                    {(selectedJourney.steps || []).map((step) => (
                      <div key={`${selectedJourney.journey_id}-${step.step}`} className="text-xs border border-border rounded-md px-2 py-1 bg-slate-700/20">
                        <p className="text-text-primary">Step {step.step}: {step.action}</p>
                        <p className="text-text-secondary">{step.status}{step.reason ? ` - ${step.reason}` : ''}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : <p className="text-sm text-text-secondary">No journey simulations available yet.</p>}
        </article>
      </section> : null}

      {activeTab === 'governance' ? <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <article className="bg-surface border border-border rounded-lg p-5 space-y-3">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Routing Decision</h4>
          <div className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-xs text-text-secondary">Route To</p>
            <p className="text-base font-semibold text-text-primary mt-1">{prettyLabel(String(normalizedPayload.routing_decision?.route_to || 'pending'))}</p>
            <p className="text-sm text-text-primary mt-2">{normalizedPayload.routing_decision?.reason || 'No routing reason available yet.'}</p>
            {Array.isArray(normalizedPayload.routing_decision?.fix_instructions) && normalizedPayload.routing_decision?.fix_instructions?.length ? (
              <ul className="mt-3 space-y-1 text-xs text-text-primary">
                {normalizedPayload.routing_decision.fix_instructions.slice(0, 8).map((item, index) => (
                  <li key={`routing-fix-${index}`}>{String(item.instruction || item.bug_id || 'Fix instruction')}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </article>

        <article className="bg-surface border border-border rounded-lg p-5 space-y-3">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Cross-document Issues</h4>
          <div className="space-y-2 max-h-48 overflow-auto pr-1">
            {crossDocIssues.length > 0 ? crossDocIssues.map((issue) => (
              <div key={issue.issue_id} className="bg-bg-base border border-border rounded-md p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm text-text-primary font-medium">{issue.issue_id}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${severityTone[issue.severity] || severityTone.low}`}>{issue.severity}</span>
                </div>
                <p className="text-sm text-text-primary mt-2">{issue.description}</p>
                {issue.fix_instruction ? <p className="text-xs text-text-secondary mt-1">Fix: {issue.fix_instruction}</p> : null}
              </div>
            )) : <p className="text-sm text-text-secondary">No cross-document issues found.</p>}
          </div>
        </article>
      </section> : null}

      {activeTab === 'governance' ? <section className="bg-surface border border-border rounded-lg p-5 space-y-2">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Meta Quality Coherence</h4>
        <p className="text-sm text-text-primary">
          Verdict Consistency: {normalizedPayload.meta_quality_report?.verdict_consistent === false ? 'Needs review' : 'Consistent'}
        </p>
        {(normalizedPayload.meta_quality_report?.notes || []).length > 0 ? (
          <ul className="space-y-1 text-sm text-text-primary">
            {(normalizedPayload.meta_quality_report?.notes || []).map((note, index) => (
              <li key={`meta-note-${index}`}>{note}</li>
            ))}
          </ul>
        ) : <p className="text-sm text-text-secondary">No additional coherence notes.</p>}
      </section> : null}
    </div>
  );
}
