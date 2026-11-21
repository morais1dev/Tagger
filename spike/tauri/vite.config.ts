import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Porta fixa: o tauri.conf.json aponta o devUrl para ela.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true },
});
