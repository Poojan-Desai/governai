import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { sites } from "@openai/sites-vite-plugin";

export default defineConfig({
  plugins: [react(), sites()],
  build: {
    // Sites binds browser assets from dist/client and executes the worker from
    // dist/server. Keep those deployment targets explicit.
    outDir: "dist/client",
  },
  server: { host: "0.0.0.0" },
});
