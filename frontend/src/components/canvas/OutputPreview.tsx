import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import PRDPanel from '@/components/canvas/PRDPanel';

function formatCurrency(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-';
  return `${value}%`;
}

function SeverityBadge({ severity }: { severity: string }) {
  const color =
    severity === 'critical'
      ? 'bg-red-500/20 text-red-300 border-red-500/40'
      : severity === 'high'
      ? 'bg-orange-500/20 text-orange-300 border-orange-500/40'
      : severity === 'medium'
      ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'
      : 'bg-blue-500/20 text-blue-300 border-blue-500/40';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${color}`}>
      {severity}
    </span>
  );
}

function ResearchPanel({ payload }: { payload: any }) {
  const report = payload || {};
  const market = report.market || {};
  const problem = report.problem_statement || {};
  const personas = report.personas || [];
  const painPoints = report.pain_points || [];
  const competitors = report.competitors || [];
  const viability = report.viability || {};
  const feasibility = report.feasibility || {};

  return (
    <div className="space-y-5">
      <section className="bg-surface border border-border rounded-lg p-5">
        <h3 className="text-lg font-semibold text-[var(--agent-research)] mb-3">Problem Snapshot</h3>
        <p className="text-sm text-text-primary leading-6">{problem.core_problem || '-'}</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4 text-sm">
          <div className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-text-secondary text-xs uppercase tracking-wide mb-1">Affected Users</p>
            <p className="text-text-primary">{problem.affected_users || '-'}</p>
          </div>
          <div className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-text-secondary text-xs uppercase tracking-wide mb-1">Opportunity Window</p>
            <p className="text-text-primary">{problem.opportunity_window || '-'}</p>
          </div>
        </div>
      </section>

      <section className="bg-surface border border-border rounded-lg p-5">
        <h3 className="text-lg font-semibold text-[var(--agent-research)] mb-3">Market Intelligence</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-text-secondary text-xs uppercase tracking-wide">TAM</p>
            <p className="text-xl font-semibold text-text-primary mt-1">{formatCurrency(market.tam_usd)}</p>
          </div>
          <div className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-text-secondary text-xs uppercase tracking-wide">SAM</p>
            <p className="text-xl font-semibold text-text-primary mt-1">{formatCurrency(market.sam_usd)}</p>
          </div>
          <div className="bg-bg-base border border-border rounded-md p-3">
            <p className="text-text-secondary text-xs uppercase tracking-wide">SOM</p>
            <p className="text-xl font-semibold text-text-primary mt-1">{formatCurrency(market.som_usd)}</p>
          </div>
        </div>
        <div className="mt-4 text-sm text-text-primary">
          <p><span className="text-text-secondary">Industry:</span> {market.industry || '-'}</p>
          <p><span className="text-text-secondary">YoY Growth:</span> {formatPercent(market.growth_rate_yoy_percent)}</p>
        </div>
      </section>

      <section className="bg-surface border border-border rounded-lg p-5">
        <h3 className="text-lg font-semibold text-[var(--agent-research)] mb-3">Personas</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {personas.length > 0 ? personas.map((persona: any, idx: number) => (
            <div key={`persona-${idx}`} className="bg-bg-base border border-border rounded-md p-3">
              <p className="text-text-primary font-medium">{persona.name || `Persona ${idx + 1}`}</p>
              <p className="text-xs text-text-secondary mt-1">{persona.occupation || '-'} | {persona.age_range || '-'}</p>
              <p className="text-sm text-text-primary mt-2">Primary Device: {persona.primary_device || '-'}</p>
            </div>
          )) : <p className="text-sm text-text-secondary">No persona insights available yet.</p>}
        </div>
      </section>

      <section className="bg-surface border border-border rounded-lg p-5">
        <h3 className="text-lg font-semibold text-[var(--agent-research)] mb-3">Pain Points</h3>
        <div className="space-y-2">
          {painPoints.length > 0 ? painPoints.map((pain: any, idx: number) => (
            <div key={`pain-${idx}`} className="bg-bg-base border border-border rounded-md p-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm text-text-primary">{pain.pain || '-'}</p>
                <p className="text-xs text-text-secondary mt-1">Frequency: {pain.frequency || '-'}</p>
              </div>
              <SeverityBadge severity={pain.severity || 'low'} />
            </div>
          )) : <p className="text-sm text-text-secondary">No pain point analysis available yet.</p>}
        </div>
      </section>

      <section className="bg-surface border border-border rounded-lg p-5">
        <h3 className="text-lg font-semibold text-[var(--agent-research)] mb-3">Competitor Scan</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                <th className="py-2 pr-3">Competitor</th>
                <th className="py-2 pr-3">Positioning</th>
                <th className="py-2 pr-3">Pricing</th>
              </tr>
            </thead>
            <tbody>
              {competitors.length > 0 ? competitors.map((c: any, idx: number) => (
                <tr key={`comp-${idx}`} className="border-b border-border/40">
                  <td className="py-2 pr-3 text-text-primary">{c.name || '-'}</td>
                  <td className="py-2 pr-3 text-text-primary">{c.positioning || '-'}</td>
                  <td className="py-2 pr-3 text-text-primary">{c.pricing_model || '-'}</td>
                </tr>
              )) : (
                <tr>
                  <td className="py-2 text-text-secondary" colSpan={3}>No competitor data available yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-surface border border-border rounded-lg p-5">
          <h3 className="text-lg font-semibold text-[var(--agent-research)] mb-3">Business Viability</h3>
          <p className="text-sm text-text-primary">Recommended: {viability.recommended_model || '-'}</p>
          <p className="text-sm text-text-primary mt-2">ARPU: {viability.estimated_arpu || '-'}</p>
          <p className="text-sm text-text-primary mt-2">Score: {viability.viability_score || '-'}/10</p>
        </div>
        <div className="bg-surface border border-border rounded-lg p-5">
          <h3 className="text-lg font-semibold text-[var(--agent-research)] mb-3">Technical Feasibility</h3>
          <p className="text-sm text-text-primary">Complexity: {feasibility.complexity || '-'}</p>
          <p className="text-sm text-text-primary mt-2">MVP Timeline: {feasibility.estimated_mvp_weeks || '-'} weeks</p>
          <p className="text-sm text-text-primary mt-2">Score: {feasibility.feasibility_score || '-'}/10</p>
        </div>
      </section>
    </div>
  );
}

export default function OutputPreview({ agentId }: { agentId: string }) {
  const { globalState } = usePipelineStore();

  const getAgentPayload = () => {
    switch (agentId) {
      case 'research':
        return globalState?.research_report;
      case 'pm':
        return globalState?.prd;
      case 'designer':
        return globalState?.design_spec;
      case 'developer':
        return globalState?.developer_output;
      case 'qa':
        return globalState?.qa_output;
      case 'devops':
        return globalState?.devops_output;
      case 'docs':
        return globalState?.docs_output;
      default:
        return null;
    }
  };

  const payload = getAgentPayload();
  
  // Basic generic renderer based on agent type
  // In a full implementation, these would be separate rich components
  
  const renderContent = () => {
    switch (agentId) {
      case 'research':
        return (
          payload ? <ResearchPanel payload={payload} /> : (
            <div className="bg-surface border border-border rounded-lg p-6">
              <h3 className="text-lg font-bold text-accent mb-4">Research Report</h3>
              <p className="text-text-secondary italic">Waiting for research data...</p>
            </div>
          )
        );
      case 'pm':
        return (
          payload ? <PRDPanel payload={payload} /> : (
            <div className="bg-surface border border-border rounded-lg p-6">
              <h3 className="text-lg font-bold text-[var(--agent-pm)] mb-4">Product Requirements Document</h3>
              <p className="text-text-secondary italic">Waiting for PM data...</p>
            </div>
          )
        );
      case 'designer':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-[var(--agent-designer)] mb-4">Design Specification</h3>
            {payload ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(payload, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for design data...</p>
            )}
          </div>
        );
      case 'developer':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-[var(--agent-developer)] mb-4">Code Generation</h3>
            {payload ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(payload, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for developer output...</p>
            )}
          </div>
        );
      case 'qa':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-[var(--agent-qa)] mb-4">QA Analysis</h3>
            {payload ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(payload, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for QA results...</p>
            )}
          </div>
        );
      case 'devops':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-[var(--agent-devops)] mb-4">DevOps & Deployment</h3>
            {payload ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(payload, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for DevOps output...</p>
            )}
          </div>
        );
      case 'docs':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-[var(--agent-docs)] mb-4">Documentation</h3>
            {payload ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(payload, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for documentation...</p>
            )}
          </div>
        );
      default:
        return <div>Select an agent to view output.</div>;
    }
  };

  return (
    <div className="w-full animate-type-in">
      {renderContent()}
    </div>
  );
}
