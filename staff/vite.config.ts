import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

declare const process: { env: Record<string, string | undefined> }; // Node's, without pulling @types/node into the app

// STAFF_API_PROXY=https://<api host> (set by `make staff-live`): forward /api to that API, like the deployed
// site's vercel.json rewrite, so a local page can sign in with a real account and cookies stay same-origin.
const proxyTarget = process.env.STAFF_API_PROXY;
const proxy = proxyTarget ? { '/api': { target: proxyTarget, changeOrigin: true, secure: true } } : undefined;

// Separate app on its own port and its own Vercel project (Moderation spec 3.2; staff screens are a separate build, never part of the public app).
export default defineConfig({
  plugins: [react()],
  server: { port: 5175, strictPort: true, proxy },
  preview: { port: 5175, strictPort: true },
});
