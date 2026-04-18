import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';

export default function OutputPreview({ agentId }: { agentId: string }) {
  const { globalState } = usePipelineStore();
  
  // Basic generic renderer based on agent type
  
  const renderContent = () => {
    switch (agentId) {
      case 'research':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-accent mb-4">Research Report</h3>
            {globalState?.research_report ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(globalState.research_report, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for research data...</p>
            )}
          </div>
        );
      case 'pm':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-[var(--agent-pm)] mb-4">Product Requirements Document</h3>
            {globalState?.prd ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(globalState.prd, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for PM data...</p>
            )}
          </div>
        );
      case 'designer':
        return (
          <div className="bg-surface border border-border rounded-lg p-6">
            <h3 className="text-lg font-bold text-[var(--agent-designer)] mb-4">Design Specification</h3>
            {globalState?.design_spec ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(globalState.design_spec, null, 2)}
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
            {globalState?.developer_output ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(globalState.developer_output, null, 2)}
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
            {globalState?.qa_output ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(globalState.qa_output, null, 2)}
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
            {globalState?.devops_output ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(globalState.devops_output, null, 2)}
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
            {globalState?.docs_output ? (
              <pre className="text-sm font-mono text-text-code whitespace-pre-wrap">
                {JSON.stringify(globalState.docs_output, null, 2)}
              </pre>
            ) : (
              <p className="text-text-secondary italic">Waiting for documentation...</p>
            )}
          </div>
        );
      default:
        return <div className="text-text-primary">Select an agent to view output.</div>;
    }
  };

  return (
    <div className="w-full animate-type-in">
      {renderContent()}
    </div>
  );
}
