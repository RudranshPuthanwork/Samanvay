import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The console is served by the Python process from dist/; the dev server is for
// front-end work only and stays on loopback, matching the run-time binding rule.
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173, strictPort: true },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true },
  build: { outDir: "dist", assetsInlineLimit: 0 },
});
