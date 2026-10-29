import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The interface is served from local files: relative paths, no network calls.
export default defineConfig({
  root: "src/renderer",
  base: "./",
  plugins: [react()],
  build: {
    outDir: "../../dist/renderer",
    emptyOutDir: true,
  },
});
