import React from 'react';

type Priority = 'must-have' | 'should-have' | 'could-have' | 'wont-have';

interface AcceptanceCriterion {
  given?: string;
  when?: string;
  then?: string;
}

interface UserStory {
  id?: string;
  persona?: string;
  action?: string;
  outcome?: string;
  priority?: Priority | string;
  estimated_effort?: string;
  acceptance_criteria?: AcceptanceCriterion[];
}

interface Feature {
  id?: string;
  name?: string;
  description?: string;
}

interface UserFlowStep {
  step?: number;
  screen_name?: string;
  user_action?: string;
  system_response?: string;
  next_step?: number | null;
}

interface ProductVision {
  elevator_pitch?: string;
  target_user?: string;
  core_value_proposition?: string;
  success_definition?: string;
}

interface BudgetEstimate {
  mvp_engineer_weeks?: number;
  mvp_cost_usd_range?: string;
  assumptions?: string[];
}

interface PRDFeatures {
  mvp?: Feature[];
  v1_1?: Feature[];
  v2_0?: Feature[];
}

interface PRDPayload {
  product_vision?: ProductVision;
  user_stories?: UserStory[];
  features?: PRDFeatures;
  budget_estimate?: BudgetEstimate;
  user_flow?: UserFlowStep[];
}

function priorityClass(priority: Priority | string | undefined): string {
  if (priority === 'must-have') return 'bg-red-500/20 text-red-300 border-red-500/40';
  if (priority === 'should-have') return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  if (priority === 'could-have') return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
  return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
}

function asArray<T>(value: T[] | null | undefined): T[] {
  if (!Array.isArray(value)) return [];
  return value;
}

function toText(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function buildPrdDocumentText(prd: PRDPayload): string {
  const stories = asArray(prd?.user_stories);
  const mvpFeatures = asArray(prd?.features?.mvp);
  const v11Features = asArray(prd?.features?.v1_1);
  const v20Features = asArray(prd?.features?.v2_0);
  const assumptions = asArray(prd?.budget_estimate?.assumptions);
  const userFlow = asArray(prd?.user_flow);

  const lines: string[] = [];
  lines.push('Product Requirements Document');
  lines.push('');
  lines.push('1. Product Vision');
  lines.push(`Elevator Pitch: ${toText(prd?.product_vision?.elevator_pitch)}`);
  lines.push(`Target User: ${toText(prd?.product_vision?.target_user)}`);
  lines.push(`Core Value Proposition: ${toText(prd?.product_vision?.core_value_proposition)}`);
  lines.push(`Success Definition: ${toText(prd?.product_vision?.success_definition)}`);
  lines.push('');
  lines.push('2. User Stories');
  stories.forEach((story: UserStory, index: number) => {
    lines.push(`${index + 1}. ${toText(story?.id)} | ${toText(story?.priority)} | Effort: ${toText(story?.estimated_effort)}`);
    lines.push(`Persona: ${toText(story?.persona)}`);
    lines.push(`Action: ${toText(story?.action)}`);
    lines.push(`Outcome: ${toText(story?.outcome)}`);
    asArray(story?.acceptance_criteria).forEach((ac: AcceptanceCriterion, acIndex: number) => {
      lines.push(`  AC ${acIndex + 1}: GIVEN ${toText(ac?.given)} | WHEN ${toText(ac?.when)} | THEN ${toText(ac?.then)}`);
    });
    lines.push('');
  });
  lines.push('3. Feature Roadmap');
  lines.push('MVP Features:');
  mvpFeatures.forEach((feature: Feature) => lines.push(`- ${toText(feature?.id)} ${toText(feature?.name)}: ${toText(feature?.description)}`));
  lines.push('v1.1 Features:');
  v11Features.forEach((feature: Feature) => lines.push(`- ${toText(feature?.id)} ${toText(feature?.name)}: ${toText(feature?.description)}`));
  lines.push('v2.0 Features:');
  v20Features.forEach((feature: Feature) => lines.push(`- ${toText(feature?.id)} ${toText(feature?.name)}: ${toText(feature?.description)}`));
  lines.push('');
  lines.push('4. Budget Estimate');
  lines.push(`MVP Engineer Weeks: ${toText(prd?.budget_estimate?.mvp_engineer_weeks)}`);
  lines.push(`MVP Cost Range: ${toText(prd?.budget_estimate?.mvp_cost_usd_range)}`);
  lines.push('Assumptions:');
  assumptions.forEach((assumption: string) => lines.push(`- ${toText(assumption)}`));
  lines.push('');
  lines.push('5. User Flow');
  userFlow.forEach((step: UserFlowStep) => {
    lines.push(`Step ${toText(step?.step)}: ${toText(step?.screen_name)}`);
    lines.push(`  User Action: ${toText(step?.user_action)}`);
    lines.push(`  System Response: ${toText(step?.system_response)}`);
    lines.push(`  Next Step: ${toText(step?.next_step)}`);
  });

  return lines.join('\n');
}

async function downloadPRDAsPdf(prd: PRDPayload): Promise<void> {
  const { jsPDF } = await import('jspdf');

  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const margin = 48;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const lineHeight = 16;
  const maxWidth = pageWidth - margin * 2;
  let y = margin;

  const lines = doc.splitTextToSize(buildPrdDocumentText(prd), maxWidth) as string[];
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(11);

  lines.forEach((line) => {
    if (y > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
    doc.text(line, margin, y);
    y += lineHeight;
  });

  const fileName = `prd-${new Date().toISOString().slice(0, 10)}.pdf`;
  doc.save(fileName);
}

export default function PRDPanel({ payload }: { payload: PRDPayload }) {
  const stories = asArray(payload?.user_stories);
  const userFlow = asArray(payload?.user_flow);
  const features = payload?.features || {};
  const assumptions = asArray(payload?.budget_estimate?.assumptions);

  return (
    <div className="bg-surface border border-border rounded-lg p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-[var(--agent-pm)]">Product Requirements Document</h3>
          <p className="text-xs text-text-secondary mt-1">Readable PRD layout generated from Product Manager output.</p>
        </div>
        <button
          type="button"
          className="px-3 py-2 rounded-md border border-[var(--agent-pm)]/40 text-sm text-[var(--agent-pm)] hover:bg-[var(--agent-pm)]/10 transition"
          onClick={() => {
            void downloadPRDAsPdf(payload);
          }}
        >
          Download PDF
        </button>
      </div>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-2">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">1. Product Vision</h4>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Elevator Pitch:</span> {toText(payload?.product_vision?.elevator_pitch)}</p>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Target User:</span> {toText(payload?.product_vision?.target_user)}</p>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Core Value Proposition:</span> {toText(payload?.product_vision?.core_value_proposition)}</p>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Success Definition:</span> {toText(payload?.product_vision?.success_definition)}</p>
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">2. User Stories</h4>
        {stories.length > 0 ? stories.map((story: UserStory, index: number) => (
          <article key={`story-${index}`} className="border border-border rounded-md p-3 bg-surface">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <p className="text-sm font-semibold text-text-primary">{toText(story?.id)}</p>
              <span className={`text-xs px-2 py-0.5 rounded-full border ${priorityClass(story?.priority)}`}>
                {toText(story?.priority)}
              </span>
              <span className="text-xs text-text-secondary">Effort: {toText(story?.estimated_effort)}</span>
            </div>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Persona:</span> {toText(story?.persona)}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Action:</span> {toText(story?.action)}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Outcome:</span> {toText(story?.outcome)}</p>
            <div className="mt-2">
              <p className="text-xs uppercase tracking-wide text-text-secondary mb-1">Acceptance Criteria</p>
              <div className="space-y-1">
                {asArray(story?.acceptance_criteria).map((ac: AcceptanceCriterion, acIndex: number) => (
                  <p key={`ac-${index}-${acIndex}`} className="text-xs text-text-primary">
                    GIVEN {toText(ac?.given)} | WHEN {toText(ac?.when)} | THEN {toText(ac?.then)}
                  </p>
                ))}
              </div>
            </div>
          </article>
        )) : <p className="text-sm text-text-secondary">No user stories available.</p>}
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary mb-2">3. Feature Roadmap</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <p className="text-xs uppercase text-text-secondary mb-1">MVP</p>
            <div className="space-y-2">
              {asArray(features?.mvp).map((feature: Feature, idx: number) => (
                <div key={`mvp-${idx}`} className="border border-border rounded-md p-2 bg-surface">
                  <p className="text-sm text-text-primary font-medium">{toText(feature?.id)} - {toText(feature?.name)}</p>
                  <p className="text-xs text-text-secondary mt-1">{toText(feature?.description)}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase text-text-secondary mb-1">v1.1</p>
            <div className="space-y-2">
              {asArray(features?.v1_1).map((feature: Feature, idx: number) => (
                <div key={`v11-${idx}`} className="border border-border rounded-md p-2 bg-surface">
                  <p className="text-sm text-text-primary font-medium">{toText(feature?.id)} - {toText(feature?.name)}</p>
                  <p className="text-xs text-text-secondary mt-1">{toText(feature?.description)}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase text-text-secondary mb-1">v2.0</p>
            <div className="space-y-2">
              {asArray(features?.v2_0).map((feature: Feature, idx: number) => (
                <div key={`v20-${idx}`} className="border border-border rounded-md p-2 bg-surface">
                  <p className="text-sm text-text-primary font-medium">{toText(feature?.id)} - {toText(feature?.name)}</p>
                  <p className="text-xs text-text-secondary mt-1">{toText(feature?.description)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary mb-2">4. Budget Estimate</h4>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">MVP Engineer Weeks:</span> {toText(payload?.budget_estimate?.mvp_engineer_weeks)}</p>
        <p className="text-sm text-text-primary mt-1"><span className="text-text-secondary">MVP Cost Range:</span> {toText(payload?.budget_estimate?.mvp_cost_usd_range)}</p>
        <div className="mt-2">
          <p className="text-xs uppercase tracking-wide text-text-secondary mb-1">Assumptions</p>
          <ul className="list-disc list-inside space-y-1">
            {assumptions.length > 0 ? assumptions.map((assumption: string, idx: number) => (
              <li key={`assumption-${idx}`} className="text-sm text-text-primary">{toText(assumption)}</li>
            )) : <li className="text-sm text-text-secondary">No assumptions provided.</li>}
          </ul>
        </div>
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary mb-2">5. User Flow</h4>
        <div className="space-y-2">
          {userFlow.length > 0 ? userFlow.map((step: UserFlowStep, index: number) => (
            <div key={`flow-${index}`} className="border border-border rounded-md p-3 bg-surface">
              <p className="text-sm text-text-primary font-medium">Step {toText(step?.step)}: {toText(step?.screen_name)}</p>
              <p className="text-sm text-text-primary mt-1"><span className="text-text-secondary">User Action:</span> {toText(step?.user_action)}</p>
              <p className="text-sm text-text-primary mt-1"><span className="text-text-secondary">System Response:</span> {toText(step?.system_response)}</p>
              <p className="text-sm text-text-primary mt-1"><span className="text-text-secondary">Next Step:</span> {toText(step?.next_step)}</p>
            </div>
          )) : <p className="text-sm text-text-secondary">No user flow provided.</p>}
        </div>
      </section>
    </div>
  );
}