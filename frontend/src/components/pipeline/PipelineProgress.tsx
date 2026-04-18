import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';

export default function PipelineProgress() {
  const { agentStatuses } = usePipelineStore();
  
  const totalAgents = Object.keys(agentStatuses).length;
  const completedAgents = Object.values(agentStatuses).filter(s => s === 'COMPLETE' || s === 'SKIPPED').length;
  
  const progressPercent = totalAgents === 0 ? 0 : Math.round((completedAgents / totalAgents) * 100);

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-text-secondary font-mono tracking-wider">PROGRESS</span>
        <span className="text-xs font-mono text-text-primary">{progressPercent}%</span>
      </div>
      
      <div className="h-2 w-full bg-surface-hover rounded-full overflow-hidden border border-border">
        <div 
          className="h-full bg-accent transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%`, boxShadow: progressPercent > 0 ? '0 0 10px var(--accent-dim)' : 'none' }}
        />
      </div>
      
      <div className="mt-2 text-[10px] text-text-secondary font-mono text-center">
        {completedAgents} / {totalAgents} AGENTS COMPLETE
      </div>
    </div>
  );
}
