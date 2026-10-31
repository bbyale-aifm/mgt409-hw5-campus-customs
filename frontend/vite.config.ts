import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend allows exactly this origin (see backend/main.py), so the port is fixed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
