import basicSsl from "@vitejs/plugin-basic-ssl";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// HTTPS (self-signed) because phone browsers only allow microphone access in a
// secure context. /api and /ws are proxied to FastAPI so the phone talks to a
// single origin and never sees backend credentials.
export default defineConfig({
  plugins: [react(), tailwindcss(), basicSsl()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true, changeOrigin: true },
    },
  },
});
