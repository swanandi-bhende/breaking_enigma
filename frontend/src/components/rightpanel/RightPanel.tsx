import React from 'react';
import GlobalStateViewer from './GlobalStateViewer';
import LiveLogStream from './LiveLogStream';
import QAScoreMeter from './QAScoreMeter';

export default function RightPanel() {
  return (
    <div className="w-80 flex flex-col bg-bg-base border-l border-border h-full p-4">
      <GlobalStateViewer />
      <LiveLogStream />
      <QAScoreMeter />
    </div>
  );
}
