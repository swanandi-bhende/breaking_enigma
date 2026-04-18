"use client";

import React from 'react';
import { usePipelineStore } from '@/store/pipelineStore';
import { usePipelineSocket } from '@/hooks/usePipelineSocket';
import TopBar from '@/components/layout/TopBar';
import BottomInputBar from '@/components/layout/BottomInputBar';
import LeftRail from '@/components/pipeline/LeftRail';
import MainCanvas from '@/components/canvas/MainCanvas';
import RightPanel from '@/components/rightpanel/RightPanel';

export default function Dashboard() {
  const { runId } = usePipelineStore();
  
  // Initialize WebSocket connection if we have a runId
  usePipelineSocket(runId);

  return (
    <div className="flex flex-col h-screen w-full overflow-hidden bg-bg-base text-text-primary">
      <TopBar />
      
      <div className="flex flex-1 overflow-hidden">
        <LeftRail />
        <MainCanvas />
        <RightPanel />
      </div>
      
      <BottomInputBar />
    </div>
  );
}
