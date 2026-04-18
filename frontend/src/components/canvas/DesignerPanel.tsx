import React, { useEffect, useMemo, useState } from 'react';

type ComponentType = 'layout' | 'form' | 'display' | 'navigation' | 'feedback';
type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
type RelationType = 'one-to-one' | 'one-to-many' | 'many-to-many';

interface ScreenComponent {
  component_name: string;
  type: ComponentType;
  props?: Record<string, unknown>;
  state_dependencies?: string[];
}

interface ScreenSpec {
  screen_id: string;
  screen_name: string;
  route: string;
  purpose?: string;
  components?: ScreenComponent[];
  ux_decisions?: string[];
  edge_cases?: string[];
  wireframe_description?: string;
}

interface InteractionFlowSpec {
  flow_id: string;
  flow_name: string;
  trigger: string;
  steps?: string[];
  happy_path_end: string;
  failure_paths?: string[];
}

interface RequestBodySpec {
  content_type?: string;
  request_schema?: Record<string, unknown>;
  schema_def?: Record<string, unknown>;
  validation_rules?: string[];
}

interface ResponseSpec {
  description: string;
  response_schema?: Record<string, unknown>;
  schema_def?: Record<string, unknown>;
  example?: Record<string, unknown>;
}

interface APIEndpointSpec {
  endpoint_id: string;
  method: HttpMethod;
  path: string;
  auth_required: boolean;
  description?: string;
  request_body?: RequestBodySpec | null;
  responses?: Record<string, ResponseSpec>;
  rate_limit?: string | null;
  maps_to_user_stories?: string[];
}

interface DataModelField {
  name: string;
  type: string;
  nullable?: boolean;
  unique?: boolean;
  indexed?: boolean;
  foreign_key?: string | null;
  default?: string | null;
}

interface Relationship {
  type: RelationType;
  with_entity: string;
  foreign_key: string;
}

interface DataModelSpec {
  entity_name: string;
  table_name: string;
  fields: DataModelField[];
  relationships?: Relationship[];
}

interface DesignerPayload {
  screens?: ScreenSpec[];
  interaction_flows?: InteractionFlowSpec[];
  system_architecture?: {
    frontend?: string;
    backend?: string;
    database?: string;
    cache?: string;
    external_services?: string[];
    communication_patterns?: Record<string, string>;
  };
  api_spec?: APIEndpointSpec[];
  data_models?: DataModelSpec[];
}

type DownloadKind = 'pdf' | 'architecture-svg' | 'flows-svg' | 'wireframes-svg';

function toText(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function getBodySchema(body: RequestBodySpec | null | undefined): Record<string, unknown> {
  if (!body) return {};
  return body.request_schema || body.schema_def || {};
}

function getResponseSchema(response: ResponseSpec | undefined): Record<string, unknown> {
  if (!response) return {};
  return response.response_schema || response.schema_def || {};
}

function downloadFile(content: string, mimeType: string, fileName: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function renderMermaidSvg(diagram: string, title: string): Promise<string> {
  const mermaid = await import('mermaid');
  mermaid.default.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'strict',
  });
  const id = `download-${title.replace(/[^a-z0-9]+/gi, '-')}-${Math.random().toString(36).slice(2)}`;
  const { svg } = await mermaid.default.render(id, diagram);
  return svg;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function wrapText(value: string, maxLength = 26): string[] {
  const words = value.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = '';

  words.forEach((word) => {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > maxLength && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  });

  if (current) lines.push(current);
  return lines.length > 0 ? lines : [value];
}

function buildArchitectureMermaid(payload: DesignerPayload): string {
  const architecture = payload.system_architecture || {};
  const services = asArray<string>(architecture.external_services);
  const screens = asArray<ScreenSpec>(payload.screens);
  const apis = asArray<APIEndpointSpec>(payload.api_spec);
  const models = asArray<DataModelSpec>(payload.data_models);
  const commPatterns = architecture.communication_patterns || {};

  const serviceNodes = services.length > 0
    ? services.map((service, index) => `  ext${index}[${JSON.stringify(service)}]`).join('\n')
    : '  ext["External services"]';

  const screenNodes = screens.slice(0, 4).map((screen, index) => `  ui${index}[${JSON.stringify(screen.screen_name)}]`).join('\n');
  const modelNodes = models.slice(0, 4).map((model, index) => `  dm${index}[${JSON.stringify(model.entity_name)}]`).join('\n');
  const apiNodes = apis.slice(0, 6).map((api, index) => `  ep${index}[${JSON.stringify(`${api.method} ${api.path}`)}]`).join('\n');

  const uiEdges = screens.length > 0
    ? screens.slice(0, 4).map((screen, index) => `  browser -->|Route ${index + 1}| ui${index}`).join('\n')
    : '  browser -->|Route| api';

  const apiEdges = apis.length > 0
    ? apis.slice(0, 6).map((_, index) => `  ui${Math.min(index, Math.max(0, Math.min(3, screens.length - 1)))} --> ep${index}\n  ep${index} --> api`).join('\n')
    : '  browser --> api';

  const modelEdges = models.length > 0
    ? models.slice(0, 4).map((_, index) => `  api --> dm${index}`).join('\n')
    : '  api --> db';

  const commNodes = Object.entries(commPatterns)
    .slice(0, 4)
    .map(([key, value], index) => `  cp${index}[${JSON.stringify(`${key}: ${toText(value)}`)}]`)
    .join('\n');
  const commEdges = Object.entries(commPatterns)
    .slice(0, 4)
    .map((_, index) => `  api -.-> cp${index}`)
    .join('\n');

  return `flowchart TB
  user((User))
  browser[${JSON.stringify(architecture.frontend ? toText(architecture.frontend) : 'Web Frontend')}]
  api[${JSON.stringify(architecture.backend ? toText(architecture.backend) : 'Backend API')}]
  worker["Celery Worker"]
  db[(${JSON.stringify(architecture.database ? toText(architecture.database) : 'Database')})]
  cache[(${JSON.stringify(architecture.cache ? toText(architecture.cache) : 'Cache')})]
  rag[("Qdrant")]
${serviceNodes}
${screenNodes || ''}
${apiNodes || ''}
${modelNodes || ''}
${commNodes || ''}

  user --> browser
${uiEdges}
${apiEdges}
  api --> worker
  api --> db
  api --> cache
  worker --> db
  worker --> cache
  api --> rag
  worker --> rag
${modelEdges}
${commEdges}
${services.length > 0 ? services.map((_, index) => `  api --> ext${index}`).join('\n') : '  api --> ext'}
`;
}

function buildFlowMermaid(payload: DesignerPayload): string {
  const flows = asArray<InteractionFlowSpec>(payload.interaction_flows);
  if (flows.length === 0) {
    return 'flowchart LR\n  start((Start)) --> finish((Finish))';
  }

  const flowBlocks = flows.slice(0, 2).map((flow, flowIndex) => {
    const prefix = `f${flowIndex}`;
    const steps = asArray<string>(flow.steps).slice(0, 6);
    const nodes = steps.length > 0
      ? steps.map((step, index) => `  ${prefix}s${index}[${JSON.stringify(step)}]`).join('\n')
      : `  ${prefix}s0["Review screen"]\n  ${prefix}s1["Submit action"]`;

    const chain = steps.length > 0
      ? steps.map((_, index) => `  ${index === 0 ? `${prefix}start` : `${prefix}s${index - 1}`} --> ${prefix}s${index}`).join('\n') + `\n  ${prefix}s${steps.length - 1} --> ${prefix}finish`
      : `  ${prefix}start --> ${prefix}s0\n  ${prefix}s0 --> ${prefix}s1\n  ${prefix}s1 --> ${prefix}finish`;

    const failureStates = asArray<string>(flow.failure_paths)
      .join(', ')
      .replace(/\|/g, ', ') || 'Validation error';

    return `
  ${prefix}start((${JSON.stringify(flow.trigger)}))
${nodes}
  ${prefix}finish(("${escapeXml(flow.happy_path_end ? toText(flow.happy_path_end) : 'Success')}"))
${chain}
  ${prefix}start -.-> ${prefix}error["Failure: ${escapeXml(failureStates)}"]
`;
  }).join('\n');

  const crossFlow = flows.length > 1 ? '  f0finish --> f1start' : '';

  return `flowchart LR
${flowBlocks}
${crossFlow}
`;
}

function buildWireframeSvg(payload: DesignerPayload): string {
  const screens = asArray<ScreenSpec>(payload.screens).slice(0, 4);
  const width = 1440;
  const cardWidth = 320;
  const cardHeight = 420;
  const gap = 24;
  const margin = 32;
  const height = 560;
  const totalWidth = margin * 2 + screens.length * cardWidth + Math.max(0, screens.length - 1) * gap;

  const componentNames = (screen: ScreenSpec): string[] => asArray<ScreenComponent>(screen.components).map((component) => component.component_name);

  const renderComponentPills = (x: number, y: number, screen: ScreenSpec): string => {
    const names = componentNames(screen).slice(0, 4);
    if (names.length === 0) {
      return `<rect x="${x}" y="${y}" width="90" height="22" rx="11" fill="#1A1A24" stroke="#2A2A3A" /><text x="${x + 45}" y="${y + 15}" text-anchor="middle" fill="#8888AA" font-size="10" font-family="sans-serif">Core UI</text>`;
    }

    return names.map((name, index) => {
      const pillX = x + index * 72;
      return `<rect x="${pillX}" y="${y}" width="64" height="22" rx="11" fill="#1A1A24" stroke="#2A2A3A" /><text x="${pillX + 32}" y="${y + 15}" text-anchor="middle" fill="#F0F0F8" font-size="9" font-family="sans-serif">${escapeXml(name.slice(0, 10))}</text>`;
    }).join('');
  };

  const renderInputField = (x: number, y: number, widthValue: number, label: string): string => {
    return `<rect x="${x}" y="${y}" width="${widthValue}" height="34" rx="8" fill="#111118" stroke="#2A2A3A" /><text x="${x + 12}" y="${y + 22}" fill="#8888AA" font-size="10" font-family="sans-serif">${escapeXml(label)}</text>`;
  };

  const renderScreenWireframe = (screen: ScreenSpec, index: number): string => {
    const x = margin + index * (cardWidth + gap);
    const screenTitle = escapeXml(screen.screen_name);
    const routeLabel = escapeXml(screen.route);
    const purposeLines = wrapText(toText(screen.purpose), 30).slice(0, 3);
    const components = asArray<ScreenComponent>(screen.components);
    const hasForm = components.some((component) => component.type === 'form');
    const hasNavigation = components.some((component) => component.type === 'navigation');
    const hasDisplay = components.some((component) => component.type === 'display');
    const hasFeedback = components.some((component) => component.type === 'feedback');

    const frame = `<rect x="${x}" y="${margin}" width="${cardWidth}" height="${cardHeight}" rx="20" fill="#111118" stroke="#2A2A3A" stroke-width="1.5" />`;
    const bezel = `<rect x="${x + 10}" y="${margin + 10}" width="${cardWidth - 20}" height="${cardHeight - 20}" rx="16" fill="#0A0A0F" stroke="#1A1A24" />`;
    const topBar = `<rect x="${x + 22}" y="${margin + 24}" width="${cardWidth - 44}" height="34" rx="10" fill="#1A1A24" stroke="#2A2A3A" />`;
    const topDots = `<circle cx="${x + 38}" cy="${margin + 41}" r="4" fill="#00FF88" /><circle cx="${x + 54}" cy="${margin + 41}" r="4" fill="#8888AA" /><circle cx="${x + 70}" cy="${margin + 41}" r="4" fill="#8888AA" />`;
    const title = `<text x="${x + 92}" y="${margin + 44}" fill="#F0F0F8" font-size="16" font-family="sans-serif" font-weight="700">${screenTitle}</text>`;
    const route = `<text x="${x + 22}" y="${margin + 82}" fill="#8888AA" font-size="11" font-family="sans-serif">${routeLabel}</text>`;

    const heroY = margin + 102;
    const hero = `<rect x="${x + 22}" y="${heroY}" width="${cardWidth - 44}" height="74" rx="14" fill="#0F1118" stroke="#2A2A3A" />`;
    const heroTitle = `<text x="${x + 36}" y="${heroY + 24}" fill="#F0F0F8" font-size="13" font-family="sans-serif" font-weight="700">Primary Experience</text>`;
    const heroText = purposeLines.map((line, lineIndex) => `<text x="${x + 36}" y="${heroY + 43 + lineIndex * 15}" fill="#F0F0F8" font-size="10" font-family="sans-serif">${escapeXml(line)}</text>`).join('');

    const contentY = margin + 192;
    const contentLeft = `<rect x="${x + 22}" y="${contentY}" width="${cardWidth - 108}" height="120" rx="14" fill="#0A0A0F" stroke="#00FF8855" />`;
    const contentRight = `<rect x="${x + cardWidth - 78}" y="${contentY}" width="56" height="120" rx="14" fill="#111118" stroke="#2A2A3A" />`;
    const contentTitle = `<text x="${x + 36}" y="${contentY + 22}" fill="#F0F0F8" font-size="11" font-family="sans-serif" font-weight="700">${hasForm ? 'Form / Inputs' : hasDisplay ? 'Data Cards' : 'Content Area'}</text>`;

    const bodyBlocks = hasForm
      ? [
          renderInputField(x + 36, contentY + 32, cardWidth - 136, 'Search / title'),
          renderInputField(x + 36, contentY + 74, cardWidth - 136, 'Primary input'),
        ].join('')
      : hasDisplay
        ? [
            `<rect x="${x + 36}" y="${contentY + 32}" width="${cardWidth - 136}" height="26" rx="8" fill="#1A1A24" />`,
            `<rect x="${x + 36}" y="${contentY + 66}" width="${cardWidth - 136}" height="26" rx="8" fill="#1A1A24" />`,
            `<rect x="${x + 36}" y="${contentY + 100}" width="${cardWidth - 136}" height="26" rx="8" fill="#1A1A24" />`,
          ].join('')
        : [
            `<rect x="${x + 36}" y="${contentY + 32}" width="${cardWidth - 136}" height="34" rx="8" fill="#1A1A24" />`,
            `<rect x="${x + 36}" y="${contentY + 78}" width="${cardWidth - 136}" height="34" rx="8" fill="#1A1A24" />`,
          ].join('');

    const sidebar = `
      <rect x="${x + cardWidth - 74}" y="${contentY + 10}" width="40" height="22" rx="8" fill="#1A1A24" />
      <rect x="${x + cardWidth - 74}" y="${contentY + 40}" width="40" height="22" rx="8" fill="#1A1A24" />
      <rect x="${x + cardWidth - 74}" y="${contentY + 70}" width="40" height="22" rx="8" fill="#1A1A24" />
    `;

    const ctaY = margin + 332;
    const cta = `<rect x="${x + 22}" y="${ctaY}" width="${cardWidth - 44}" height="30" rx="15" fill="#00FF88" />`;
    const ctaText = `<text x="${x + cardWidth / 2}" y="${ctaY + 20}" text-anchor="middle" fill="#0A0A0F" font-size="11" font-family="sans-serif" font-weight="700">Primary CTA</text>`;
    const helperText = hasNavigation
      ? 'Navigation-first layout + actions'
      : hasFeedback
        ? 'Inline validation + status'
        : 'Structured content + actions';
    const helper = `<text x="${x + 22}" y="${margin + cardHeight - 24}" fill="#8888AA" font-size="10" font-family="sans-serif">${helperText}</text>`;

    return `${frame}${bezel}${topBar}${topDots}${title}${route}${renderComponentPills(x + 22, margin + 70, screen)}${hero}${heroTitle}${heroText}${contentLeft}${contentRight}${contentTitle}${bodyBlocks}${sidebar}${cta}${ctaText}${helper}`;
  };

  const cards = screens.map((screen, index) => renderScreenWireframe(screen, index)).join('');

  const background = `<rect width="${Math.max(width, totalWidth)}" height="${height}" fill="#0A0A0F" />`;
  const heading = `<text x="32" y="28" fill="#F0F0F8" font-size="20" font-family="sans-serif" font-weight="700">UI Wireframes</text>`;
  const subheading = `<text x="32" y="50" fill="#8888AA" font-size="12" font-family="sans-serif">Text-based mockups exported as SVG pictures</text>`;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.max(width, totalWidth)}" height="${height}" viewBox="0 0 ${Math.max(width, totalWidth)} ${height}">${background}${heading}${subheading}${cards}</svg>`;
}

function MermaidDiagram({ diagram, title }: { diagram: string; title: string }) {
  const [svgMarkup, setSvgMarkup] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      try {
        const mermaid = await import('mermaid');
        mermaid.default.initialize({
          startOnLoad: false,
          theme: 'dark',
          securityLevel: 'strict',
        });
        const id = `diagram-${Math.random().toString(36).slice(2)}`;
        const { svg } = await mermaid.default.render(id, diagram);
        if (!cancelled) {
          setSvgMarkup(svg);
          setError(null);
        }
      } catch (diagramError) {
        if (!cancelled) {
          setError(diagramError instanceof Error ? diagramError.message : 'Failed to render diagram');
        }
      }
    }

    void renderDiagram();
    return () => {
      cancelled = true;
    };
  }, [diagram]);

  return (
    <div className="bg-surface border border-border rounded-md p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">{title}</h4>
      </div>
      {error ? (
        <p className="text-sm text-red-300">{error}</p>
      ) : svgMarkup ? (
        <div className="overflow-x-auto" dangerouslySetInnerHTML={{ __html: svgMarkup }} />
      ) : (
        <p className="text-sm text-text-secondary">Rendering diagram...</p>
      )}
    </div>
  );
}

function buildDesignerDocumentText(payload: DesignerPayload): string {
  const lines: string[] = [];
  lines.push('Designer Specification');
  lines.push('');

  const architecture = payload.system_architecture || {};
  lines.push('1. System Architecture');
  lines.push(`Frontend: ${toText(architecture.frontend)}`);
  lines.push(`Backend: ${toText(architecture.backend)}`);
  lines.push(`Database: ${toText(architecture.database)}`);
  lines.push(`Cache: ${toText(architecture.cache)}`);
  lines.push(`External Services: ${asArray<string>(architecture.external_services).join(', ') || '-'}`);
  lines.push('');

  lines.push('2. Screens');
  asArray<ScreenSpec>(payload.screens).forEach((screen, index) => {
    lines.push(`${index + 1}. ${toText(screen.screen_name)} (${toText(screen.route)})`);
    lines.push(`Purpose: ${toText(screen.purpose)}`);
    lines.push(`Wireframe: ${toText(screen.wireframe_description)}`);
    lines.push(`Components: ${asArray<ScreenComponent>(screen.components).map((component) => component.component_name).join(', ') || '-'}`);
    lines.push(`UX Decisions: ${asArray<string>(screen.ux_decisions).join(' | ') || '-'}`);
    lines.push(`Edge Cases: ${asArray<string>(screen.edge_cases).join(' | ') || '-'}`);
    lines.push('');
  });

  lines.push('3. Interaction Flows');
  asArray<InteractionFlowSpec>(payload.interaction_flows).forEach((flow, index) => {
    lines.push(`${index + 1}. ${toText(flow.flow_name)}`);
    lines.push(`Trigger: ${toText(flow.trigger)}`);
    lines.push(`Steps: ${asArray<string>(flow.steps).join(' -> ') || '-'}`);
    lines.push(`Happy Path: ${toText(flow.happy_path_end)}`);
    lines.push(`Failure Paths: ${asArray<string>(flow.failure_paths).join(' | ') || '-'}`);
    lines.push('');
  });

  lines.push('4. API Specification');
  asArray<APIEndpointSpec>(payload.api_spec).forEach((endpoint) => {
    lines.push(`${endpoint.method} ${endpoint.path}`);
    lines.push(`Endpoint ID: ${endpoint.endpoint_id}`);
    lines.push(`Auth: ${endpoint.auth_required ? 'required' : 'not required'}`);
    lines.push(`Description: ${toText(endpoint.description)}`);
    lines.push(`Maps to stories: ${asArray<string>(endpoint.maps_to_user_stories).join(', ') || '-'}`);
    lines.push(`Request schema keys: ${Object.keys(getBodySchema(endpoint.request_body)).join(', ') || '-'}`);
    const responseEntries = Object.entries(endpoint.responses || {});
    lines.push(`Responses: ${responseEntries.map(([code, response]) => `${code} ${response.description}`).join(' | ') || '-'}`);
    lines.push('');
  });

  lines.push('5. Data Models');
  asArray<DataModelSpec>(payload.data_models).forEach((model) => {
    lines.push(`${model.entity_name} -> ${model.table_name}`);
    lines.push(`Fields: ${asArray<DataModelField>(model.fields).map((field) => `${field.name}:${field.type}`).join(', ') || '-'}`);
    lines.push(`Relationships: ${asArray<Relationship>(model.relationships).map((relationship) => `${relationship.type} ${relationship.with_entity}`).join(' | ') || '-'}`);
    lines.push('');
  });

  return lines.join('\n');
}

async function downloadDesignerAsPdf(payload: DesignerPayload): Promise<void> {
  const { jsPDF } = await import('jspdf');
  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const margin = 48;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const maxWidth = pageWidth - margin * 2;
  let y = margin;

  const lines = doc.splitTextToSize(buildDesignerDocumentText(payload), maxWidth) as string[];
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(11);

  lines.forEach((line) => {
    if (y > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
    doc.text(line, margin, y);
    y += 16;
  });

  doc.save(`designer-${new Date().toISOString().slice(0, 10)}.pdf`);
}

async function downloadDesignerAsset(kind: DownloadKind, payload: DesignerPayload): Promise<void> {
  const baseName = `designer-${new Date().toISOString().slice(0, 10)}`;
  if (kind === 'architecture-svg') {
    const svg = await renderMermaidSvg(buildArchitectureMermaid(payload), 'Architecture Diagram');
    downloadFile(svg, 'image/svg+xml;charset=utf-8', `${baseName}-architecture.svg`);
    return;
  }
  if (kind === 'flows-svg') {
    const svg = await renderMermaidSvg(buildFlowMermaid(payload), 'Interaction Flow Diagram');
    downloadFile(svg, 'image/svg+xml;charset=utf-8', `${baseName}-flows.svg`);
    return;
  }
  if (kind === 'wireframes-svg') {
    downloadFile(buildWireframeSvg(payload), 'image/svg+xml;charset=utf-8', `${baseName}-wireframes.svg`);
    return;
  }

  void downloadDesignerAsPdf(payload);
}

export default function DesignerPanel({ payload }: { payload: DesignerPayload }) {
  const screens = asArray<ScreenSpec>(payload.screens);
  const flows = asArray<InteractionFlowSpec>(payload.interaction_flows);
  const apiSpec = asArray<APIEndpointSpec>(payload.api_spec);
  const dataModels = asArray<DataModelSpec>(payload.data_models);
  const architecture = payload.system_architecture || {};
  const architectureDiagram = useMemo(() => buildArchitectureMermaid(payload), [payload]);
  const flowDiagram = useMemo(() => buildFlowMermaid(payload), [payload]);
  const wireframeSvg = useMemo(() => buildWireframeSvg(payload), [payload]);

  return (
    <div className="bg-surface border border-border rounded-lg p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-[var(--agent-designer)]">Design Specification</h3>
          <p className="text-xs text-text-secondary mt-1">Readable design brief plus downloadable diagrams and wireframes.</p>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <button type="button" className="px-3 py-2 rounded-md border border-[var(--agent-designer)]/40 text-sm text-[var(--agent-designer)] hover:bg-[var(--agent-designer)]/10 transition" onClick={() => { void downloadDesignerAsset('architecture-svg', payload); }}>Architecture SVG</button>
          <button type="button" className="px-3 py-2 rounded-md border border-[var(--agent-designer)]/40 text-sm text-[var(--agent-designer)] hover:bg-[var(--agent-designer)]/10 transition" onClick={() => { void downloadDesignerAsset('flows-svg', payload); }}>Flow SVG</button>
          <button type="button" className="px-3 py-2 rounded-md border border-[var(--agent-designer)]/40 text-sm text-[var(--agent-designer)] hover:bg-[var(--agent-designer)]/10 transition" onClick={() => { void downloadDesignerAsset('wireframes-svg', payload); }}>Wireframes SVG</button>
          <button type="button" className="px-3 py-2 rounded-md border border-[var(--agent-designer)]/40 text-sm text-[var(--agent-designer)] hover:bg-[var(--agent-designer)]/10 transition" onClick={() => { void downloadDesignerAsset('pdf', payload); }}>Download PDF</button>
        </div>
      </div>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-2">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">System Architecture</h4>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Frontend:</span> {toText(architecture.frontend)}</p>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Backend:</span> {toText(architecture.backend)}</p>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Database:</span> {toText(architecture.database)}</p>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">Cache:</span> {toText(architecture.cache)}</p>
        <p className="text-sm text-text-primary"><span className="text-text-secondary">External Services:</span> {asArray<string>(architecture.external_services).join(', ') || '-'}</p>
      </section>

      <MermaidDiagram title="Architecture Diagram" diagram={architectureDiagram} />
      <MermaidDiagram title="Interaction Flow Diagram" diagram={flowDiagram} />

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">UI Wireframe Mockup</h4>
        <div className="overflow-x-auto bg-surface border border-border rounded-md p-3" dangerouslySetInnerHTML={{ __html: wireframeSvg }} />
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Screens</h4>
        {screens.length > 0 ? screens.map((screen) => (
          <article key={screen.screen_id} className="bg-surface border border-border rounded-md p-4 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-text-primary">{screen.screen_name}</p>
                <p className="text-xs text-text-secondary">{screen.route}</p>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full border border-border text-text-secondary">{screen.screen_id}</span>
            </div>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Purpose:</span> {toText(screen.purpose)}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Wireframe:</span> {toText(screen.wireframe_description)}</p>
            <div>
              <p className="text-xs uppercase tracking-wide text-text-secondary mb-1">Components</p>
              <div className="space-y-1">
                {asArray<ScreenComponent>(screen.components).map((component) => (
                  <p key={component.component_name} className="text-xs text-text-primary">
                    {component.component_name} | {component.type} | deps: {component.state_dependencies?.join(', ') || '-'}
                  </p>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-text-secondary mb-1">UX Decisions</p>
                <ul className="space-y-1">
                  {asArray<string>(screen.ux_decisions).map((decision, index) => <li key={`${screen.screen_id}-ux-${index}`} className="text-text-primary">{decision}</li>)}
                </ul>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-text-secondary mb-1">Edge Cases</p>
                <ul className="space-y-1">
                  {asArray<string>(screen.edge_cases).map((edgeCase, index) => <li key={`${screen.screen_id}-edge-${index}`} className="text-text-primary">{edgeCase}</li>)}
                </ul>
              </div>
            </div>
          </article>
        )) : <p className="text-sm text-text-secondary">No screens available.</p>}
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Interaction Flows</h4>
        {flows.length > 0 ? flows.map((flow) => (
          <article key={flow.flow_id} className="bg-surface border border-border rounded-md p-4 space-y-2">
            <p className="text-sm font-semibold text-text-primary">{flow.flow_name}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Trigger:</span> {toText(flow.trigger)}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Steps:</span> {asArray<string>(flow.steps).join(' → ') || '-'}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Happy path:</span> {toText(flow.happy_path_end)}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Failure paths:</span> {asArray<string>(flow.failure_paths).join(' | ') || '-'}</p>
          </article>
        )) : <p className="text-sm text-text-secondary">No interaction flows available.</p>}
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">API Specification</h4>
        {apiSpec.length > 0 ? apiSpec.map((endpoint) => (
          <article key={endpoint.endpoint_id} className="bg-surface border border-border rounded-md p-4 space-y-2">
            <p className="text-sm font-semibold text-text-primary">{endpoint.method} {endpoint.path}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Endpoint:</span> {endpoint.endpoint_id}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Auth:</span> {endpoint.auth_required ? 'Required' : 'Not required'}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Description:</span> {toText(endpoint.description)}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Rate limit:</span> {toText(endpoint.rate_limit)}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Maps to stories:</span> {asArray<string>(endpoint.maps_to_user_stories).join(', ') || '-'}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-text-primary">
              <div>
                <p className="uppercase tracking-wide text-text-secondary mb-1">Request</p>
                <p>Content type: {toText(endpoint.request_body?.content_type)}</p>
                <p>Schema keys: {Object.keys(getBodySchema(endpoint.request_body)).join(', ') || '-'}</p>
                <p>Validation: {asArray<string>(endpoint.request_body?.validation_rules).join(' | ') || '-'}</p>
              </div>
              <div>
                <p className="uppercase tracking-wide text-text-secondary mb-1">Responses</p>
                {Object.entries(endpoint.responses || {}).map(([code, response]) => (
                  <p key={`${endpoint.endpoint_id}-${code}`}>
                    {code}: {response.description} | schema keys: {Object.keys(getResponseSchema(response)).join(', ') || '-'}
                  </p>
                ))}
              </div>
            </div>
          </article>
        )) : <p className="text-sm text-text-secondary">No API endpoints available.</p>}
      </section>

      <section className="bg-bg-base border border-border rounded-md p-4 space-y-3">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">Data Models</h4>
        {dataModels.length > 0 ? dataModels.map((model) => (
          <article key={model.entity_name} className="bg-surface border border-border rounded-md p-4 space-y-2">
            <p className="text-sm font-semibold text-text-primary">{model.entity_name}</p>
            <p className="text-sm text-text-primary"><span className="text-text-secondary">Table:</span> {model.table_name}</p>
            <div className="text-xs text-text-primary space-y-1">
              {asArray<DataModelField>(model.fields).map((field) => (
                <p key={`${model.entity_name}-${field.name}`}>{field.name} | {field.type} | nullable: {field.nullable ? 'yes' : 'no'} | unique: {field.unique ? 'yes' : 'no'}</p>
              ))}
            </div>
            <p className="text-xs text-text-secondary">
              Relationships: {asArray<Relationship>(model.relationships).map((relationship) => `${relationship.type} ${relationship.with_entity}`).join(' | ') || '-'}
            </p>
          </article>
        )) : <p className="text-sm text-text-secondary">No data models available.</p>}
      </section>
    </div>
  );
}