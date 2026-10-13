import React from 'react';
import { createRoot } from 'react-dom/client';
import '../app/globals.css';
import './workspace.css';
import App from './App';

const root = document.getElementById('root');
if (!root) throw new Error('Missing workspace root');
createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
