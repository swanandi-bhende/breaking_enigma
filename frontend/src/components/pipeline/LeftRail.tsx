import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import AgentCard from './AgentCard';
import PipelineProgress from './PipelineProgress';

const AGENTS = [
  { id: 'research', label: 'Research', colorVar: '--agent-research' },
  { id: 'pm', label: 'Product Manager', colorVar: '--agent-pm' },
  { id: 'designer', label: 'Designer', colorVar: '--agent-designer' },
  { id: 'developer', label: 'Developer', colorVar: '--agent-developer' },
  { id: 'qa', label: 'QA', colorVar: '--agent-qa' },
];

const PARALLEL_AGENTS = [
  { id: 'devops', label: 'DevOps', colorVar: '--agent-devops' },
  { id: 'docs', label: 'Documentation', colorVar: '--agent-docs' },
];

export default function LeftRail() {
  const { agentStatuses } = usePipelineStore();

  return (
    <div className="w-64 flex flex-col bg-surface border-r border-border h-full">
      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
        <h2 className="text-xs font-bold text-text-secondary uppercase tracking-wider mb-4">Pipeline</h2>
        
        {AGENTS.map((agent) => (
          <AgentCard 
            key={agent.id}
            name={agent.id}
            label={agent.label}
            status={agentStatuses[agent.id]}
            colorVar={agent.colorVar}
          />
        ))}

        <div className="flex items-center my-2 text-text-secondary text-xs px-2">
          <div className="flex-1 border-t border-border border-dashed"></div>
          <span className="mx-2 tracking-widest uppercase">Parallel</span>
          <div className="flex-1 border-t border-border border-dashed"></div>
        </div>

        <div className="relative border-l-2 border-border border-dashed ml-3 pl-3">
          {PARALLEL_AGENTS.map((agent) => (
            <AgentCard 
              key={agent.id}
              name={agent.id}
              label={agent.label}
              status={agentStatuses[agent.id]}
              colorVar={agent.colorVar}
            />
          ))}
        </div>
      </div>
      
      <div className="p-4 border-t border-border bg-bg-base">
        <PipelineProgress />
      </div>
    </div>
  );
}
