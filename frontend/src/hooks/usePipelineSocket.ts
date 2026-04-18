/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect } from "react";
import { usePipelineStore, AgentStatus } from "@/store/pipelineStore";

const AGENT_NAME_MAP: Record<string, string> = {
  product_manager: "pm",
  documentation: "docs",
};

function normalizeAgentName(agentName: string): string {
  return AGENT_NAME_MAP[agentName] ?? agentName;
}

export function usePipelineSocket(runId: string | null) {
  const { setAgentStatus, appendLog, setQAScore, setGlobalState } = usePipelineStore();

  useEffect(() => {
    if (!runId) return;

    // NEXT_PUBLIC_WS_URL should point to /ws (for example ws://localhost:8000/ws).
    const rawWsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    const url = new URL(rawWsUrl);
    url.searchParams.set("run_id", runId);

    const ws = new WebSocket(url.toString());

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data as string) as Record<string, any>;
        const eventType = payload.event_type as string | undefined;

        if (eventType === "AGENT_STATUS_CHANGED") {
          const agentName = normalizeAgentName(String(payload.agent_name || "unknown"));
          const status = payload.new_status as AgentStatus | undefined;
          if (status) setAgentStatus(agentName, status);
          return;
        }

        if (eventType === "AGENT_LOG_LINE") {
          const agentName = normalizeAgentName(String(payload.agent_name || "system"));
          appendLog({
            agent: agentName,
            text: String(payload.line || ""),
            level: payload.level ? String(payload.level) : undefined,
            timestamp: Date.now(),
          });
          return;
        }

        if (eventType === "QA_VERDICT") {
          setQAScore({
            score: typeof payload.qa_score === "number" ? payload.qa_score : null,
            verdict: payload.verdict ? String(payload.verdict) : null,
            bugsCount: typeof payload.bugs_count === "number" ? payload.bugs_count : null,
          });
          return;
        }

        if (eventType === "GLOBAL_STATE_UPDATED" && payload.state) {
          setGlobalState(payload.state as Record<string, any>);
        }
      } catch {
        // Ignore malformed messages to keep the dashboard responsive.
      }
    };

    ws.onerror = () => {
      appendLog({
        agent: "system",
        text: "WebSocket connection error",
        level: "error",
        timestamp: Date.now(),
      });
    };

    return () => {
      ws.close();
    };
  }, [runId, setAgentStatus, appendLog, setQAScore, setGlobalState]);
}
