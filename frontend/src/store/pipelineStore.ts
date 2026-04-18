/* eslint-disable @typescript-eslint/no-explicit-any */
import { create } from 'zustand';

export type AgentStatus = 'PENDING' | 'RUNNING' | 'COMPLETE' | 'FAILED' | 'SKIPPED';

export interface LogLine {
  agent: string;
  text: string;
  level?: string;
  timestamp: number;
}

export interface PipelineState {
  runId: string | null;
  agentStatuses: Record<string, AgentStatus>;
  selectedAgent: string | null;
  logs: LogLine[];
  qaScore: {
    score: number | null;
    verdict: string | null;
    bugsCount: number | null;
  };
  globalState: Record<string, any> | null;
  
  // Actions
  setRunId: (runId: string) => void;
  setAgentStatus: (agentName: string, status: AgentStatus) => void;
  setSelectedAgent: (agentName: string | null) => void;
  appendLog: (log: LogLine) => void;
  setQAScore: (scoreData: { score: number | null; verdict: string | null; bugsCount: number | null }) => void;
  setGlobalState: (state: Record<string, any>) => void;
  reset: () => void;
}

const initialAgentStatuses: Record<string, AgentStatus> = {
  research: 'PENDING',
  pm: 'PENDING',
  designer: 'PENDING',
  developer: 'PENDING',
  qa: 'PENDING',
  devops: 'PENDING',
  docs: 'PENDING',
};

export const usePipelineStore = create<PipelineState>((set) => ({
  runId: null,
  agentStatuses: { ...initialAgentStatuses },
  selectedAgent: null,
  logs: [],
  qaScore: {
    score: null,
    verdict: null,
    bugsCount: null,
  },
  globalState: null,

  setRunId: (runId) => set({ runId }),
  
  setAgentStatus: (agentName, status) => set((state) => ({
    agentStatuses: {
      ...state.agentStatuses,
      [agentName]: status,
    }
  })),

  setSelectedAgent: (selectedAgent) => set({ selectedAgent }),

  appendLog: (log) => set((state) => ({
    logs: [...state.logs, log]
  })),

  setQAScore: (qaScore) => set({ qaScore }),

  setGlobalState: (globalState) => set({ globalState }),

  reset: () => set({
    runId: null,
    agentStatuses: { ...initialAgentStatuses },
    selectedAgent: null,
    logs: [],
    qaScore: { score: null, verdict: null, bugsCount: null },
    globalState: null,
  })
}));
