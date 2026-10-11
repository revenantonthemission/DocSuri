import React from 'react';
import { createRoot } from 'react-dom/client';
import '../app/globals.css';

function Workspace() {
  return <main id="main">
    <h1>DocSuri</h1>
    <p role="status">로컬 연구 환경을 준비하고 있어요. 아직 논문 작업을 시작할 수 없어요.</p>
  </main>;
}

const root = document.getElementById('root');
if (!root) throw new Error('Missing workspace root');
createRoot(root).render(<React.StrictMode><Workspace /></React.StrictMode>);
