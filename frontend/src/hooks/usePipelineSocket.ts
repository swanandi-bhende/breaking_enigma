import { useEffect } from "react";
import { usePipelineStore, AgentStatus } from "@/store/pipelineStore";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:8000";

// Map backend agent names to frontend store keys
const AGENT_NAME_MAP: Record<string, string> = {
  research: "research",
  product_manager: "pm",
  designer: "designer",
  developer: "developer",
  qa: "qa",
  devops: "devops",
  documentation: "docs",
  orchestrator: "research", // orchestrator maps to research phase visually
};

function normaliseAgentName(backendName: string): string {
  return AGENT_NAME_MAP[backendName] || backendName;
}

export function usePipelineSocket(runId: string | null) {
  const { setAgentStatus, appendLog, setQAScore, setGlobalState } = usePipelineStore();

  useEffect(() => {
    if (!runId) return;

    const socket = io(WS_URL, {
      query: { run_id: runId },
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socket.on("connect", () => {
      console.log(`[Socket.IO] Connected for run_id=${runId}, socket=${socket.id}`);
    });

    socket.on("disconnect", (reason) => {
      console.log(`[Socket.IO] Disconnected: ${reason}`);
    });

    socket.on("connect_error", (err) => {
      console.warn(`[Socket.IO] Connection error: ${err.message}`);
    });

    // Agent status updates
    socket.on("AGENT_STATUS_CHANGED", ({ agent_name, new_status }: {
      agent_name: string;
      new_status: AgentStatus;
      previous_status?: string;
    }) => {
      const frontendKey = normaliseAgentName(agent_name);
      setAgentStatus(frontendKey, new_status);
    });

    // Live log lines
    socket.on("AGENT_LOG_LINE", ({ agent_name, line, level }: {
      agent_name: string;
      line: string;
      level?: string;
    }) => {
      const frontendKey = normaliseAgentName(agent_name);
      appendLog({
        agent: frontendKey,
        text: line,
        level,
        timestamp: Date.now(),
      });
    });

    // QA verdict
    socket.on("QA_VERDICT", ({ qa_score, verdict, bugs_count, critical_bugs_count }: {
      qa_score: number;
      verdict: string;
      bugs_count: number;
      critical_bugs_count?: number;
    }) => {
      setQAScore({ score: qa_score, verdict, bugsCount: bugs_count });
    });

    // Global state snapshot (from orchestrator + graph updates)
    socket.on("GLOBAL_STATE_UPDATED", ({ state }: { state: Record<string, any> }) => {
      setGlobalState(state);
      // Also sync phase statuses from global state
      if (state?.phases) {
        for (const [agentName, phaseInfo] of Object.entries(state.phases as Record<string, any>)) {
          const frontendKey = normaliseAgentName(agentName);
          const status = phaseInfo?.status as AgentStatus;
          if (status) {
            setAgentStatus(frontendKey, status);
          }
        }
      }
    });

    // Pipeline lifecycle events
    socket.on("PIPELINE_STARTED", () => {
      console.log("[Socket.IO] Pipeline started");
    });

    socket.on("PIPELINE_COMPLETE", () => {
      console.log("[Socket.IO] Pipeline complete!");
      // Mark all as complete
      ["research", "pm", "designer", "developer", "qa", "devops", "docs"].forEach(key => {
        setAgentStatus(key, "COMPLETE");
      });
    });

    socket.on("PIPELINE_FAILED", ({ error }: { error?: string }) => {
      console.error("[Socket.IO] Pipeline failed:", error);
    });

    socket.on("ARTIFACT_READY", ({ agent_name, artifact_type }: {
      agent_name: string;
      artifact_type: string;
    }) => {
      console.log(`[Socket.IO] Artifact ready: ${artifact_type} from ${agent_name}`);
    });

    return () => {
      socket.disconnect();
    };
  }, [runId, setAgentStatus, appendLog, setQAScore, setGlobalState]);
}
