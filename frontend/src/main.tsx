import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { syncGuestScope } from './offline/guestScope';
import { maintainDraftsOnce } from './offline/draftStore';
import './global.css';

const render = () =>
  ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );

// The guest scope secret is copied to IndexedDB, or restored from it, before anything reads it
// (Decisions 2026-11-08). It never waits more than 300 ms: storage problems must not block the app.
void Promise.race([syncGuestScope().catch(() => 'none'), new Promise((resolve) => setTimeout(resolve, 300))]).then(() => {
  render();
  // Interrupted sends back to ready, receipts older than 7 days deleted (guideline 6.1, 6.5).
  void maintainDraftsOnce();
});
