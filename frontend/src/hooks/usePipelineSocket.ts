import { useEffect } from "react";
import { usePipelineStore, AgentStatus } from "@/store/pipelineStore";
import { io } from "socket.io-client";

export function usePipelineSocket(runId: string | null) {
  const { setAgentStatus, appendLog, setQAScore, setGlobalState } = usePipelineStore();

  useEffect(() => {
    if (!runId) return;

    // Use environment variable or fallback to localhost during dev
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:8000";
    
    const socket = io(wsUrl, {
      query: { run_id: runId },
    });

    socket.on("AGENT_STATUS_CHANGED", ({ agent_name, new_status }: { agent_name: string, new_status: AgentStatus }) => {
      setAgentStatus(agent_name, new_status);
    });

    socket.on("AGENT_LOG_LINE", ({ agent_name, line, level }: { agent_name: string, line: string, level?: string }) => {
      appendLog({ agent: agent_name, text: line, level, timestamp: Date.now() });
    });

    socket.on("QA_VERDICT", ({ qa_score, verdict, bugs_count }: { qa_score: number, verdict: string, bugs_count: number }) => {
      setQAScore({ score: qa_score, verdict, bugsCount: bugs_count });
    });

    socket.on("GLOBAL_STATE_UPDATED", ({ state }: { state: Record<string, any> }) => {
      setGlobalState(state);
    });

    return () => { 
      socket.disconnect(); 
    };
  }, [runId, setAgentStatus, appendLog, setQAScore, setGlobalState]);
}
