import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/admin/",
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8100", "/widget.js": "http://127.0.0.1:8100" } },
  build: { outDir: "dist", emptyOutDir: true },
});
