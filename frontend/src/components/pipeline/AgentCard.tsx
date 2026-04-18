import React from 'react';
import { AgentStatus } from '@/store/pipelineStore';
import { CheckCircle2, CircleDashed, Loader2, XCircle } from 'lucide-react';

interface AgentCardProps {
  name: string;
  label: string;
  status: AgentStatus;
  colorVar: string;
}

export default function AgentCard({ name, label, status, colorVar }: AgentCardProps) {
  const isRunning = status === 'RUNNING';
  const isComplete = status === 'COMPLETE';
  const isFailed = status === 'FAILED';
  const isPending = status === 'PENDING';
  
  return (
    <div className={`relative flex items-center p-3 rounded-lg mb-2 border transition-all duration-300 ${
      isRunning 
        ? `bg-surface-hover border-[var(${colorVar})] animate-agent-pulse` 
        : isComplete
          ? 'bg-surface border-success/30'
          : isFailed
            ? 'bg-surface border-error/50'
            : 'bg-bg-base border-border opacity-50'
    }`}>
      {/* Icon status */}
      <div className="mr-3">
        {isRunning && <Loader2 className={`w-5 h-5 animate-spin text-[var(${colorVar})]`} />}
        {isComplete && <CheckCircle2 className="w-5 h-5 text-success" />}
        {isFailed && <XCircle className="w-5 h-5 text-error" />}
        {isPending && <CircleDashed className="w-5 h-5 text-text-secondary" />}
      </div>
      
      {/* Label */}
      <div className="flex-1 font-medium text-sm">
        <span className={`${isRunning ? 'text-text-primary' : 'text-text-secondary'}`}>
          {label}
        </span>
      </div>
      
      {/* Active Indicator Line */}
      {isRunning && (
        <div 
          className="absolute left-0 top-0 bottom-0 w-1 rounded-l-lg" 
          style={{ backgroundColor: `var(${colorVar})` }}
        />
      )}
    </div>
  );
}
