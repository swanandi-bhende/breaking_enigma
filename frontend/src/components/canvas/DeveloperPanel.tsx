import React, { useMemo, useState } from 'react';

interface GeneratedFile {
  path: string;
  purpose: string;
  content: string;
  language?: string;
  maps_to_endpoint_ids?: string[];
  maps_to_screen_ids?: string[];
}

interface GenerationPhase {
  phase: number;
  name: string;
  status: string;
  api_calls: number;
  details?: string;
}

interface ImplementationPlan {
  project_slug?: string;
  tech_stack_confirmation?: string[];
  architecture_decisions?: string[];
  build_sequence?: string[];
  dependency_ordered_build_sequence?: string[];
  key_architectural_decisions?: string[];
  required_files?: Array<{
    path: string;
    language?: string;
    description?: string;
  }>;
  mapped_user_story_ids?: string[];
}

interface DeveloperPayload {
  run_id?: string;
  task_id?: string;
  status?: string;
  summary?: string;
  files_created?: GeneratedFile[];
  features_implemented?: string[];
  tests_written?: string[];
  tech_debt_logged?: string[];
  self_check_results?: {
    schema_consistent?: boolean;
    all_routes_implemented?: boolean;
    feature_coverage_percent?: number;
    test_coverage_percent?: number;
    issues_found?: string[];
  };
  implementation_plan?: ImplementationPlan;
  generation_phases?: GenerationPhase[];
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function toCleanStringArray(value: unknown): string[] {
  return asArray<unknown>(value)
    .map((item) => String(item ?? '').trim())
    .filter((item) => item.length > 0);
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function extractProjectName(payload: DeveloperPayload): string {
  const summary = payload.summary || '';
  const phase3Match = summary.match(/for\s+(.+?):\s+plan,\s+manifest,\s+and\s+file\s+content\s+generated/i);
  if (phase3Match?.[1]) return phase3Match[1];
  const phase2Match = summary.match(/for\s+(.+?):\s+implementation\s+plan\s+and\s+file\s+manifest\s+generated/i);
  if (phase2Match?.[1]) return phase2Match[1];
  const match = summary.match(/for\s+(.+?)\s+with\s+\d+\s+files/i);
  if (match?.[1]) return match[1];
  return payload.implementation_plan?.project_slug || 'generated-project';
}

function fallbackPhases(payload: DeveloperPayload): GenerationPhase[] {
  const filesCount = asArray<GeneratedFile>(payload.files_created).length;
  const status = String(payload.status || 'completed');
  return [
    {
      phase: 1,
      name: 'Implementation Plan',
      status,
      api_calls: 1,
      details: 'Generated a detailed implementation strategy from PRD and design constraints.',
    },
    {
      phase: 2,
      name: 'File Manifest',
      status,
      api_calls: 1,
      details: `Mapped architecture into concrete deliverables (${filesCount} generated files detected).`,
    },
    {
      phase: 3,
      name: 'File Generation',
      status,
      api_calls: Math.max(1, Math.ceil(filesCount / 3)),
      details: 'Produced code in batched generations with schema-safe fallbacks for missing outputs.',
    },
    {
      phase: 4,
      name: 'Bundle Assembly',
      status,
      api_calls: 0,
      details: 'Prepared ZIP and PDF artifacts with runnable setup instructions and metadata.',
    },
  ];
}

function fallbackTechStack(files: GeneratedFile[]): string[] {
  const hasFrontend = files.some((file) => file.path.startsWith('frontend/'));
  const hasBackend = files.some((file) => file.path.startsWith('backend/'));
  const hasTests = files.some((file) => file.path.toLowerCase().includes('test'));
  const stack = [
    'Frontend baseline: Next.js 14, React 18, TypeScript, and Tailwind CSS for typed UI development.',
    'Backend baseline: FastAPI + Celery with Redis task broker for asynchronous orchestration.',
    'Persistence baseline: PostgreSQL-compatible data modeling with schema-first contracts.',
    'Delivery baseline: downloadable ZIP packaging with setup docs and environment templates.',
  ];
  if (hasFrontend) stack.push('Generated deliverables include frontend modules mapped from design screens.');
  if (hasBackend) stack.push('Generated deliverables include backend routes/services aligned to API contracts.');
  if (hasTests) stack.push('Generated deliverables include test assets to support smoke and regression checks.');
  return stack;
}

function fallbackBuildSequence(files: GeneratedFile[]): string[] {
  const hasBackend = files.some((file) => file.path.startsWith('backend/'));
  return [
    'Set up repository scaffolding, environment variables, and shared constants.',
    'Define data contracts and validation schemas before writing endpoint logic.',
    hasBackend
      ? 'Implement backend route handlers and service modules mapped to key user flows.'
      : 'Implement application service interfaces and client abstractions for API boundaries.',
    'Build typed UI components and page shells based on the design specification.',
    'Connect state, loading, and failure handling across API and UI layers.',
    'Run quality checks and package deployment/runtime instructions for execution.',
  ];
}

function fallbackArchitectureDecisions(projectName: string): string[] {
  return [
    'Adopt contract-first implementation to keep frontend, backend, and worker interfaces synchronized.',
    'Split responsibilities by layer (routes, services, schemas, UI modules) to reduce coupling.',
    'Use deterministic file boundaries so QA reruns can patch targeted areas without regressions.',
    'Prefer explicit types and defensive validation over implicit behavior in generated code.',
    `Optimize for immediate runnability so ${projectName} can be executed and extended with minimal setup friction.`,
  ];
}

function buildDocumentText(payload: DeveloperPayload): string {
  const plan = payload.implementation_plan || {};
  const phases = asArray<GenerationPhase>(payload.generation_phases);
  const files = asArray<GeneratedFile>(payload.files_created);
  const lines: string[] = [];

  lines.push('Developer Output');
  lines.push('');
  lines.push(`Run ID: ${asText(payload.run_id)}`);
  lines.push(`Task ID: ${asText(payload.task_id)}`);
  lines.push(`Status: ${asText(payload.status)}`);
  lines.push(`Summary: ${asText(payload.summary)}`);
  lines.push('');

  lines.push('Phases');
  phases.forEach((phase) => {
    lines.push(`- Phase ${phase.phase}: ${phase.name} (${phase.status}, API calls: ${phase.api_calls})`);
  });
  lines.push('');

  lines.push('Tech Stack Confirmation');
  asArray<string>(plan.tech_stack_confirmation).forEach((item) => lines.push(`- ${item}`));
  lines.push('');

  lines.push('Build Sequence');
  const buildSequence = asArray<string>(plan.dependency_ordered_build_sequence || plan.build_sequence);
  buildSequence.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  lines.push('');

  lines.push('Architecture Decisions');
  const architectureDecisions = asArray<string>(plan.key_architectural_decisions || plan.architecture_decisions);
  architectureDecisions.forEach((item) => lines.push(`- ${item}`));
  lines.push('');

  lines.push('Generated Files');
  files.forEach((file) => {
    lines.push(`- ${file.path} | ${asText(file.language)} | ${file.purpose}`);
  });

  return lines.join('\n');
}

async function downloadAsPdf(payload: DeveloperPayload): Promise<void> {
  const { jsPDF } = await import('jspdf');
  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const margin = 48;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const maxWidth = pageWidth - margin * 2;
  let y = margin;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(11);

  const lines = doc.splitTextToSize(buildDocumentText(payload), maxWidth) as string[];
  lines.forEach((line) => {
    if (y > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
    doc.text(line, margin, y);
    y += 16;
  });

  doc.save(`developer-${new Date().toISOString().slice(0, 10)}.pdf`);
}

async function downloadProjectZip(payload: DeveloperPayload): Promise<void> {
  const JSZip = (await import('jszip')).default;
  const zip = new JSZip();
  const files = asArray<GeneratedFile>(payload.files_created);
  const rootFolder = 'spliteasy';

  files.forEach((file) => {
    if (!file.path) return;
    const normalizedPath = file.path.replace(/^\/+/, '');
    zip.file(`${rootFolder}/${normalizedPath}`, file.content || '');
  });

  const hasEnvExample = files.some((file) => file.path.replace(/^\/+/, '') === '.env.example');
  if (!hasEnvExample) {
    zip.file(
      `${rootFolder}/.env.example`,
      [
        'DATABASE_URL="postgresql://postgres:postgres@localhost:5432/spliteasy"',
        'NEXT_PUBLIC_APP_URL="http://localhost:3000"',
        'NEXTAUTH_SECRET="replace-with-strong-secret"',
      ].join('\n')
    );
  }

  const hasPackageJson = files.some((file) => file.path.replace(/^\/+/, '') === 'package.json');
  if (!hasPackageJson) {
    zip.file(
      `${rootFolder}/package.json`,
      JSON.stringify(
        {
          name: 'spliteasy',
          private: true,
          scripts: {
            dev: 'next dev',
            build: 'next build',
            start: 'next start',
          },
          dependencies: {
            next: '^14.2.35',
            react: '^18.2.0',
            'react-dom': '^18.2.0',
            '@prisma/client': '^5.20.0',
          },
          devDependencies: {
            prisma: '^5.20.0',
            typescript: '^5.5.4',
          },
        },
        null,
        2
      )
    );
  }

  const meta = {
    run_id: payload.run_id,
    task_id: payload.task_id,
    status: payload.status,
    summary: payload.summary,
    generated_at: new Date().toISOString(),
  };

  zip.file(`${rootFolder}/developer-output.json`, JSON.stringify(meta, null, 2));
  zip.file(
    `${rootFolder}/README.md`,
    [
      '# SplitEasy',
      '',
      'Generated project bundle from Developer Phase 4 ZIP assembly.',
      '',
      '## Quick Start',
      '',
      '1. npm install',
      '2. cp .env.example .env',
      '3. npx prisma db push',
      '4. npm run dev',
      '',
      'Open http://localhost:3000 after startup.',
    ].join('\n')
  );
  zip.file(`${rootFolder}/README.generated.md`, buildDocumentText(payload));

  const blob = await zip.generateAsync({ type: 'blob' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'spliteasy.zip';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export default function DeveloperPanel({ payload }: { payload: DeveloperPayload }) {
  const files = asArray<GeneratedFile>(payload.files_created);
  const rawPhases = asArray<GenerationPhase>(payload.generation_phases);
  const plan = payload.implementation_plan || {};

  const initialFile = files.length > 0 ? files[0].path : '';
  const [selectedPath, setSelectedPath] = useState<string>(initialFile);

  const selectedFile = useMemo(
    () => files.find((file) => file.path === selectedPath) || files[0],
    [files, selectedPath]
  );

  const projectName = extractProjectName(payload);

  const phases = rawPhases.length > 0 ? rawPhases : fallbackPhases(payload);
  const techStackItems = toCleanStringArray(plan.tech_stack_confirmation);
  const sequenceItems = toCleanStringArray(plan.dependency_ordered_build_sequence || plan.build_sequence);
  const decisionItems = toCleanStringArray(plan.key_architectural_decisions || plan.architecture_decisions);

  const resolvedTechStack = techStackItems.length > 0 ? techStackItems : fallbackTechStack(files);
  const resolvedBuildSequence = sequenceItems.length > 0 ? sequenceItems : fallbackBuildSequence(files);
  const resolvedArchitecturalDecisions = decisionItems.length > 0 ? decisionItems : fallbackArchitectureDecisions(projectName);

  return (
    <div className="bg-surface border border-border rounded-lg p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-[var(--agent-developer)]">Developer Phase 4: ZIP Assembly</h3>
          <p className="text-xs text-text-secondary mt-1">
            JSZip assembles all generated files under the spliteasy folder and downloads a runnable project archive.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          {files.length > 0 ? (
            <button type="button" className="px-3 py-2 rounded-md border border-[var(--agent-developer)]/40 text-sm text-[var(--agent-developer)] hover:bg-[var(--agent-developer)]/10 transition" onClick={() => { void downloadProjectZip(payload); }}>
              Download SplitEasy ZIP
            </button>
          ) : null}
          <button type="button" className="px-3 py-2 rounded-md border border-[var(--agent-developer)]/40 text-sm text-[var(--agent-developer)] hover:bg-[var(--agent-developer)]/10 transition" onClick={() => { void downloadAsPdf(payload); }}>
            Download PDF
          </button>
        </div>
      </div>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-bg-base border border-border rounded-md p-4">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Project</p>
          <p className="text-sm text-text-primary mt-1">{projectName}</p>
        </div>
        <div className="bg-bg-base border border-border rounded-md p-4">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Generated Files</p>
          <p className="text-sm text-text-primary mt-1">{files.length}</p>
        </div>
        <div className="bg-bg-base border border-border rounded-md p-4">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Status</p>
          <p className="text-sm text-text-primary mt-1">{asText(payload.status)}</p>
        </div>
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Generation Phases</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {phases.map((phase) => (
            <article key={`phase-${phase.phase}`} className="bg-surface border border-border rounded-md p-3">
              <p className="text-xs text-text-secondary">Phase {phase.phase}</p>
              <p className="text-sm text-text-primary font-semibold mt-1">{phase.name}</p>
              <p className="text-xs text-text-secondary mt-1">{phase.status} | API calls: {phase.api_calls}</p>
              {phase.details ? <p className="text-xs text-text-primary/90 mt-2 leading-5">{phase.details}</p> : null}
            </article>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <article className="bg-bg-base border border-border rounded-md p-4 space-y-2">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Tech Stack Confirmation</h4>
          <ul className="space-y-1 text-sm text-text-primary">
            {resolvedTechStack.map((item, index) => (
              <li key={`stack-${index}`}>{item}</li>
            ))}
          </ul>
        </article>
        <article className="bg-bg-base border border-border rounded-md p-4 space-y-2">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Build Sequence</h4>
          <ol className="space-y-1 text-sm text-text-primary list-decimal ml-4">
            {resolvedBuildSequence.map((item, index) => (
              <li key={`sequence-${index}`}>{item}</li>
            ))}
          </ol>
        </article>
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Key Architectural Decisions</h4>
        <ul className="space-y-1 text-sm text-text-primary">
          {resolvedArchitecturalDecisions.map((item, index) => (
            <li key={`decision-${index}`}>{item}</li>
          ))}
        </ul>
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Generated Files Explorer</h4>
        {files.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
            <aside className="lg:col-span-4 bg-surface border border-border rounded-md max-h-80 overflow-auto">
              {files.map((file) => (
                <button
                  type="button"
                  key={file.path}
                  onClick={() => setSelectedPath(file.path)}
                  className={`w-full text-left p-3 border-b border-border/40 hover:bg-bg-base transition ${selectedFile?.path === file.path ? 'bg-bg-base' : ''}`}
                >
                  <p className="text-xs text-text-secondary uppercase tracking-wide">{asText(file.language)}</p>
                  <p className="text-sm text-text-primary mt-1 break-all">{file.path}</p>
                  <p className="text-xs text-text-secondary mt-1">{file.purpose}</p>
                </button>
              ))}
            </aside>
            <article className="lg:col-span-8 bg-surface border border-border rounded-md p-3 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-text-primary break-all">{selectedFile?.path || '-'}</p>
                <span className="text-xs px-2 py-0.5 rounded-full border border-border text-text-secondary">{asText(selectedFile?.language)}</span>
              </div>
              <p className="text-xs text-text-secondary">{selectedFile?.purpose || '-'}</p>
              <pre className="text-xs whitespace-pre-wrap bg-bg-base border border-border rounded-md p-3 overflow-auto max-h-[22rem] text-text-code">
                {selectedFile?.content || '// No file content available'}
              </pre>
            </article>
          </div>
        ) : (
          <p className="text-sm text-text-secondary">No generated files available yet.</p>
        )}
      </section>
    </div>
  );
}
