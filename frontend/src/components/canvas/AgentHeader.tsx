import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { Bot, Loader2 } from 'lucide-react';

interface AgentHeaderProps {
  agentName: string;
  stageInfo?: string;
  colorVar: string;
}

export default function AgentHeader({ agentName, stageInfo, colorVar }: AgentHeaderProps) {
  return (
    <div className="flex items-start justify-between border-b border-border pb-6 mb-6">
      <div className="flex items-center space-x-4">
        <div 
          className="w-12 h-12 rounded-xl flex items-center justify-center border animate-agent-pulse"
          style={{ 
            backgroundColor: `var(${colorVar})`,
            borderColor: `var(${colorVar})`,
            boxShadow: `0 0 20px 2px var(${colorVar}33)`
          }}
        >
          <Bot className="w-6 h-6 text-white" />
        </div>
        
        <div>
          <h2 className="text-xl font-bold text-text-primary flex items-center">
            <span style={{ color: `var(${colorVar})` }} className="mr-2">●</span>
            {agentName} Agent
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            {stageInfo || 'Processing...'}
          </p>
        </div>
      </div>
      
      <div className="flex items-center space-x-2 text-text-secondary bg-surface px-3 py-1.5 rounded-full border border-border">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-xs font-mono uppercase tracking-wider">Working</span>
      </div>
    </div>
  );
}
