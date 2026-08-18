import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import worker from "../hosting/worker.js";

const viteConfigPath = new URL("../vite.config.ts", import.meta.url);

const runRequest = async (path, accept = "*/*") => {
  const requestedPaths = [];
  const response = await worker.fetch(
    new Request(`https://governai.example${path}`, { headers: { accept } }),
    {
      ASSETS: {
        fetch: async (request) => {
          const pathname = new URL(request.url).pathname;
          requestedPaths.push(pathname);
          return new Response(pathname, { status: pathname === "/index.html" ? 200 : 404 });
        },
      },
    },
  );

  return { requestedPaths, response };
};

test("the production root resolves to Vite's index document", async () => {
  const { requestedPaths, response } = await runRequest("/", "text/html");

  assert.equal(response.status, 200);
  assert.deepEqual(requestedPaths, ["/index.html"]);
});

test("client-side document routes fall back to the index document", async () => {
  const { requestedPaths, response } = await runRequest("/recruiter-overview", "text/html");

  assert.equal(response.status, 200);
  assert.deepEqual(requestedPaths, ["/index.html"]);
});

test("bundled assets keep their original paths", async () => {
  const { requestedPaths } = await runRequest("/assets/app.js", "text/javascript");

  assert.deepEqual(requestedPaths, ["/assets/app.js"]);
});

test("Vite emits browser files into the Sites client asset directory", async () => {
  const viteConfig = await readFile(viteConfigPath, "utf8");

  assert.match(viteConfig, /outDir:\s*["']dist\/client["']/);
});
