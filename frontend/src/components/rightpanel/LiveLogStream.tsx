import React, { useEffect, useRef } from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { Terminal } from 'lucide-react';

export default function LiveLogStream() {
  const { logs } = usePipelineStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="flex flex-col flex-1 border border-border rounded-lg bg-surface overflow-hidden mt-4">
      <div className="flex items-center p-3 bg-surface-hover border-b border-border">
        <Terminal className="w-4 h-4 text-text-secondary mr-2" />
        <span className="text-xs font-bold uppercase tracking-wider text-text-primary">Live Log Stream</span>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 p-3 bg-bg-base overflow-y-auto font-mono text-xs custom-scrollbar space-y-1"
      >
        {logs.length === 0 ? (
          <div className="text-text-secondary italic opacity-50 py-2">
            Awaiting agent execution...
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="animate-type-in break-words">
              <span className="text-text-secondary mr-2 opacity-50">
                {new Date(log.timestamp).toISOString().substring(11, 19)}
              </span>
              <span className="text-accent opacity-70 mr-2">[{log.agent}]</span>
              <span className={log.level === 'error' ? 'text-error' : 'text-text-primary'}>
                {log.text}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
