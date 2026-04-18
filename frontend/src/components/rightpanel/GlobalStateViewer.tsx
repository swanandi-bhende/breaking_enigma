import React, { useState } from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { ChevronDown, ChevronRight, Database } from 'lucide-react';

export default function GlobalStateViewer() {
  const { globalState } = usePipelineStore();
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="flex flex-col border border-border rounded-lg bg-surface overflow-hidden">
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between p-3 bg-surface-hover hover:bg-opacity-80 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <Database className="w-4 h-4 text-accent" />
          <span className="text-xs font-bold uppercase tracking-wider text-text-primary">Global State JSON</span>
        </div>
        {isExpanded ? <ChevronDown className="w-4 h-4 text-text-secondary" /> : <ChevronRight className="w-4 h-4 text-text-secondary" />}
      </button>
      
      {isExpanded && (
        <div className="p-3 bg-bg-base overflow-y-auto max-h-64 custom-scrollbar">
          {globalState ? (
            <pre className="text-[10px] font-mono text-text-code whitespace-pre-wrap animate-field-flash">
              {JSON.stringify(globalState, null, 2)}
            </pre>
          ) : (
            <div className="text-xs text-text-secondary italic text-center py-4">
              State initializing...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
