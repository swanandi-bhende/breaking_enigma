import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import AgentHeader from './AgentHeader';
import OutputPreview from './OutputPreview';
import { Hexagon } from 'lucide-react';

const AGENT_META: Record<string, { label: string, colorVar: string }> = {
  research: { label: 'Research', colorVar: '--agent-research' },
  pm: { label: 'Product Manager', colorVar: '--agent-pm' },
  designer: { label: 'Designer', colorVar: '--agent-designer' },
  developer: { label: 'Developer', colorVar: '--agent-developer' },
  qa: { label: 'QA', colorVar: '--agent-qa' },
  bugfix: { label: 'BugFix', colorVar: '--agent-qa' },
  docs: { label: 'Documentation', colorVar: '--agent-docs' },
};

export default function MainCanvas() {
  const { agentStatuses, runId, selectedAgent } = usePipelineStore();

  // If user manually selected an agent, show it (even if no output yet)
  if (selectedAgent) {
    const meta = AGENT_META[selectedAgent];
    const status = agentStatuses[selectedAgent];
    return (
      <div className="flex-1 flex flex-col bg-bg-base overflow-hidden">
        <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="max-w-4xl mx-auto w-full">
            <AgentHeader 
              agentName={meta.label} 
              colorVar={meta.colorVar} 
              stageInfo={status === 'RUNNING' ? 'Generating output...' : status === 'COMPLETE' ? 'Completed' : `Status: ${status}`}
            />
            <OutputPreview agentId={selectedAgent} />
          </div>
        </div>
      </div>
    );
  }

  // Find the currently active agent (RUNNING)
  const activeAgent = Object.keys(agentStatuses).find(key => agentStatuses[key] === 'RUNNING');
  
  // If no agent is running, check if pipeline is complete
  const isComplete = Object.values(agentStatuses).every(s => s === 'COMPLETE' || s === 'SKIPPED') && runId;
  
  // Find the last completed agent if none is running but pipeline isn't complete yet
  const lastCompletedAgent = Object.keys(agentStatuses).reverse().find(key => agentStatuses[key] === 'COMPLETE');

  const displayAgent = activeAgent || (isComplete ? 'docs' : lastCompletedAgent);

  if (!displayAgent) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-bg-base bg-dot-pattern">
        <div className="w-24 h-24 mb-6 opacity-20 text-accent">
          <Hexagon className="w-full h-full" strokeWidth={1} />
        </div>
        <h2 className="text-xl font-bold text-text-primary mb-2">Ready to Build</h2>
        <p className="text-text-secondary text-center max-w-md">
          Describe your product idea below to start the autonomous AI workforce.
        </p>
      </div>
    );
  }

  const meta = AGENT_META[displayAgent];

  return (
    <div className="flex-1 flex flex-col bg-bg-base overflow-hidden">
      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-4xl mx-auto w-full">
          <AgentHeader 
            agentName={meta.label} 
            colorVar={meta.colorVar} 
            stageInfo={activeAgent ? 'Generating output...' : 'Completed'}
          />
          <OutputPreview agentId={displayAgent} />
        </div>
      </div>
    </div>
  );
}
