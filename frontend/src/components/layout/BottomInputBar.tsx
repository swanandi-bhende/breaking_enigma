import React, { useState } from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { Play, Square, Download } from 'lucide-react';

export default function BottomInputBar() {
  const [idea, setIdea] = useState('');
  const { runId, setRunId, reset, agentStatuses } = usePipelineStore();

  const isRunning = Object.values(agentStatuses).includes('RUNNING');
  const isComplete = Object.values(agentStatuses).every(s => s === 'COMPLETE' || s === 'SKIPPED') && runId;

  const handleRun = async () => {
    if (!idea.trim()) return;
    
    // In a real implementation, this would POST to /api/v1/runs
    // and receive a runId. For now, we mock it.
    reset();
    const mockRunId = crypto.randomUUID();
    setRunId(mockRunId);
    
    // Mock API call to start
    console.log("Starting pipeline with idea:", idea);
  };

  const handleStop = () => {
    // Mock stop
    console.log("Stopping pipeline");
  };

  const handleExport = () => {
    console.log("Exporting ZIP");
  };

  return (
    <div className="flex items-center p-4 bg-surface border-t border-border space-x-4 z-50">
      <div className="flex-1 relative">
        <input
          type="text"
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="Describe your product idea..."
          className="w-full bg-bg-base border border-border rounded-lg py-3 px-4 text-text-primary focus:outline-none focus:border-accent transition-colors shadow-inner"
          disabled={isRunning}
        />
      </div>
      
      {!isRunning ? (
        <button 
          onClick={handleRun}
          disabled={!idea.trim() && !isComplete}
          className="flex items-center space-x-2 bg-accent text-bg-base font-bold py-3 px-6 rounded-lg hover:bg-opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play className="w-5 h-5" />
          <span>Run Pipeline</span>
        </button>
      ) : (
        <button 
          onClick={handleStop}
          className="flex items-center space-x-2 bg-error text-white font-bold py-3 px-6 rounded-lg hover:bg-opacity-90 transition-all shadow-lg shadow-error/20"
        >
          <Square className="w-5 h-5" />
          <span>Stop</span>
        </button>
      )}

      <button 
        onClick={handleExport}
        disabled={!isComplete}
        className={`flex items-center space-x-2 font-bold py-3 px-6 rounded-lg transition-all ${
          isComplete 
            ? 'bg-surface-hover border border-accent text-accent hover:bg-accent hover:text-bg-base shadow-[0_0_15px_rgba(0,255,136,0.2)]' 
            : 'bg-surface-hover border border-border text-text-secondary opacity-50 cursor-not-allowed'
        }`}
      >
        <Download className="w-5 h-5" />
        <span>ZIP</span>
      </button>
    </div>
  );
}
