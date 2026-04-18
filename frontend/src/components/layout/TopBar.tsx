import React, { useState, useEffect } from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { Hexagon, CircleDot } from 'lucide-react';

export default function TopBar() {
  const [projectTitle, setProjectTitle] = useState('Untitled Project');
  const [timeElapsed, setTimeElapsed] = useState(0);
  const { runId, agentStatuses } = usePipelineStore();

  const isRunning = Object.values(agentStatuses).includes('RUNNING');
  const isComplete = Object.values(agentStatuses).every(s => s === 'COMPLETE' || s === 'SKIPPED') && runId;
  const isFailed = Object.values(agentStatuses).includes('FAILED');

  let statusText = 'IDLE';
  let statusColor = 'text-text-secondary';
  let indicatorColor = 'text-text-secondary';

  if (isRunning) {
    statusText = 'RUNNING';
    statusColor = 'text-accent';
    indicatorColor = 'text-accent animate-pulse';
  } else if (isFailed) {
    statusText = 'FAILED';
    statusColor = 'text-error';
    indicatorColor = 'text-error';
  } else if (isComplete) {
    statusText = 'COMPLETE';
    statusColor = 'text-success';
    indicatorColor = 'text-success';
  }

  // Timer logic
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isRunning) {
      interval = setInterval(() => {
        setTimeElapsed(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRunning]);

  const formatTime = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface text-text-primary z-50">
      <div className="flex items-center space-x-6">
        {/* Logo area */}
        <div className="flex items-center space-x-2 font-bold text-xl tracking-tight">
          <div className="flex -space-x-1">
            <Hexagon className="w-5 h-5 text-accent" />
            <Hexagon className="w-5 h-5 text-accent opacity-70" />
          </div>
          <span>ADWF</span>
        </div>
        
        <div className="h-6 w-px bg-border"></div>
        
        {/* Project Title */}
        <input 
          type="text" 
          value={projectTitle}
          onChange={(e) => setProjectTitle(e.target.value)}
          className="bg-transparent border-none outline-none font-medium text-lg focus:ring-2 focus:ring-accent-dim rounded px-2 py-1 w-64"
          placeholder="Project Title"
        />
      </div>

      <div className="flex items-center space-x-6 font-mono text-sm">
        {/* Status Indicator */}
        <div className={`flex items-center space-x-2 ${statusColor}`}>
          <CircleDot className={`w-4 h-4 ${indicatorColor}`} />
          <span>{statusText}</span>
        </div>
        
        <div className="h-6 w-px bg-border"></div>
        
        {/* Timer */}
        <div className="tabular-nums font-mono text-text-secondary">
          {formatTime(timeElapsed)}
        </div>
      </div>
    </header>
  );
}
