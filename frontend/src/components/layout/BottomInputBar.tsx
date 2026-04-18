import React, { useState } from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { Play, Square, Download } from 'lucide-react';

export default function BottomInputBar() {
  const [idea, setIdea] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { runId, setRunId, reset, agentStatuses, appendLog } = usePipelineStore();

  const isRunning = isSubmitting || Object.values(agentStatuses).includes('RUNNING');
  const isComplete = Object.values(agentStatuses).every(s => s === 'COMPLETE' || s === 'SKIPPED') && runId;

  const handleRun = async () => {
    if (!idea.trim()) return;

    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    reset();
    setIsSubmitting(true);

    try {
      const response = await fetch(`${apiBase}/api/v1/runs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ idea: idea.trim() }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Run creation failed (${response.status}): ${errorText}`);
      }

      const data = await response.json() as { run_id: string };
      setRunId(data.run_id);
      appendLog({
        agent: 'system',
        text: `Pipeline started (run_id=${data.run_id})`,
        level: 'info',
        timestamp: Date.now(),
      });
      console.log('Starting pipeline with idea:', idea);
    } catch (error) {
      appendLog({
        agent: 'system',
        text: error instanceof Error ? error.message : 'Failed to start pipeline',
        level: 'error',
        timestamp: Date.now(),
      });
      console.error('Failed to start pipeline:', error);
    } finally {
      setIsSubmitting(false);
    }
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
