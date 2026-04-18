import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { ShieldCheck, ShieldAlert, Bug } from 'lucide-react';

export default function QAScoreMeter() {
  const { qaScore, agentStatuses } = usePipelineStore();
  const isQAPending = agentStatuses['qa'] === 'PENDING' || agentStatuses['qa'] === 'RUNNING';
  
  // If no score yet, show empty state
  if (qaScore.score === null && isQAPending) {
    return (
      <div className="flex flex-col items-center justify-center p-6 border border-border rounded-lg bg-surface mt-4 h-48">
        <ShieldCheck className="w-8 h-8 text-text-secondary opacity-30 mb-2" />
        <span className="text-xs text-text-secondary italic">QA Score Pending</span>
      </div>
    );
  }

  const score = qaScore.score || 0;
  const isPass = qaScore.verdict === 'PASS';
  
  const data = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: 100 - score }
  ];
  
  const COLORS = [isPass ? '#10B981' : '#EF4444', '#1A1A24'];

  return (
    <div className="flex flex-col border border-border rounded-lg bg-surface mt-4 overflow-hidden">
      <div className="flex items-center p-3 bg-surface-hover border-b border-border">
        {isPass ? (
          <ShieldCheck className="w-4 h-4 text-success mr-2" />
        ) : (
          <ShieldAlert className="w-4 h-4 text-error mr-2" />
        )}
        <span className="text-xs font-bold uppercase tracking-wider text-text-primary">QA Verdict</span>
      </div>
      
      <div className="p-4 flex flex-col items-center">
        <div className="relative w-32 h-16">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="100%"
                startAngle={180}
                endAngle={0}
                innerRadius={40}
                outerRadius={50}
                paddingAngle={0}
                dataKey="value"
                stroke="none"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
            <span className={`text-2xl font-bold ${isPass ? 'text-success' : 'text-error'}`}>
              {score}
            </span>
          </div>
        </div>
        
        <div className="mt-4 flex items-center space-x-2 bg-bg-base px-3 py-1.5 rounded-full border border-border">
          <Bug className="w-3.5 h-3.5 text-warning" />
          <span className="text-xs font-mono text-text-secondary">
            {qaScore.bugsCount || 0} Bugs Found
          </span>
        </div>
      </div>
    </div>
  );
}
