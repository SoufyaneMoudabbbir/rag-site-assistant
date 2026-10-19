import { defineConfig } from "vite";

// One self-contained file that any website can load with a <script> tag.
export default defineConfig({
  build: {
    lib: { entry: "src/widget.ts", name: "SiteAssistant", formats: ["iife"], fileName: () => "widget.js" },
    outDir: "dist",
    emptyOutDir: true,
    minify: true,
  },
});
