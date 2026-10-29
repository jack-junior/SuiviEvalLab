import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// L'interface est servie depuis des fichiers locaux : chemins relatifs, aucun appel réseau.
export default defineConfig({
  root: "src/renderer",
  base: "./",
  plugins: [react()],
  build: {
    outDir: "../../dist/renderer",
    emptyOutDir: true,
  },
});
