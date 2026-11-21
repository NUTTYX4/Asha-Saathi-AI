import basicSsl from "@vitejs/plugin-basic-ssl";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The only Node global used here (avoids adding @types/node for two env reads).
declare const process: { env: Record<string, string | undefined> };

// HTTPS (self-signed) because phone browsers only allow microphone access in a
// secure context. /api and /ws are proxied to FastAPI so the phone talks to a
// single origin and never sees backend credentials.
//
// Browser e2e tests only (e2e/phase4_browser.py) set ASHA_BACKEND_URL to the disposable e2e API
// and ASHA_DEV_HTTP=1 to serve plain HTTP on localhost (a secure context, so no certificate
// warning has to be bypassed). Without them, behaviour is unchanged.
const backend = process.env.ASHA_BACKEND_URL ?? "http://127.0.0.1:8000";
const https = process.env.ASHA_DEV_HTTP !== "1";

export default defineConfig({
  plugins: [react(), tailwindcss(), ...(https ? [basicSsl()] : [])],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      // changeOrigin stays false for /ws: the backend checks Origin == Host on the V2 voice socket,
      // so the browser's own Host (localhost, LAN IP or the e2e port) must reach it unchanged.
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true, changeOrigin: false },
    },
  },
});
