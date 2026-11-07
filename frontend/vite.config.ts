import tailwind from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
export default defineConfig({
  plugins: [react(), tailwind()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: { charts: ["recharts"] },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8011",
      "/docs": "http://127.0.0.1:8011",
      "/openapi.json": "http://127.0.0.1:8011",
    },
  },
});
