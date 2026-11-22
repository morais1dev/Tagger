import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Porta fixa: o tauri.conf.json aponta o devUrl para ela.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/testes/preparar.ts"],
    css: false,
  },
});
