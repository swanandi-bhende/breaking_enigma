"use client";

import React, { useState } from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { Play, Square, Download, Loader2 } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function BottomInputBar() {
  const [idea, setIdea] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { runId, setRunId, reset, agentStatuses, globalState } = usePipelineStore();

  const isRunning = Object.values(agentStatuses).includes('RUNNING');
  const isComplete = runId && Object.values(agentStatuses).every(
    s => s === 'COMPLETE' || s === 'SKIPPED'
  );

  const handleRun = async () => {
    if (!idea.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    reset();

    try {
      const response = await fetch(`${API_BASE}/api/v1/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idea: idea.trim(),
          config: {
            max_qa_iterations: 1,   // keep iteration fast for demo
            target_platform: 'web',
          },
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(err.detail || 'Failed to start pipeline');
      }

      const data = await response.json();
      setRunId(data.run_id);
      console.log('Pipeline started:', data);
    } catch (err: any) {
      setError(err.message || 'Failed to start pipeline');
      console.error('Pipeline start failed:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleRun();
    }
  };

  const handleExport = () => {
    if (!globalState) return;
    const blob = new Blob([JSON.stringify(globalState, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pipeline-output-${runId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleStop = () => {
    // Pipeline runs async in the background; we can just reset the UI view
    reset();
    setIdea('');
    setError(null);
  };

  return (
    <div className="flex flex-col">
      {error && (
        <div className="px-4 py-2 bg-red-900/30 border-t border-red-500/30 text-red-400 text-sm">
          ⚠ {error}
        </div>
      )}
      <div className="flex items-center p-4 bg-surface border-t border-border space-x-4 z-50">
        <div className="flex-1 relative">
          <input
            type="text"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your product idea and press Enter or click Run Pipeline..."
            className="w-full bg-bg-base border border-border rounded-lg py-3 px-4 text-text-primary focus:outline-none focus:border-accent transition-colors shadow-inner"
            disabled={isRunning || isSubmitting}
          />
        </div>

        {isRunning ? (
          <button
            onClick={handleStop}
            className="flex items-center space-x-2 bg-error text-white font-bold py-3 px-6 rounded-lg hover:bg-opacity-90 transition-all shadow-lg shadow-error/20"
          >
            <Square className="w-5 h-5" />
            <span>Stop</span>
          </button>
        ) : (
          <button
            onClick={handleRun}
            disabled={!idea.trim() || isSubmitting}
            className="flex items-center space-x-2 bg-accent text-bg-base font-bold py-3 px-6 rounded-lg hover:bg-opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Play className="w-5 h-5" />
            )}
            <span>{isSubmitting ? 'Starting...' : 'Run Pipeline'}</span>
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
          <span>Export</span>
        </button>
      </div>
    </div>
  );
}
