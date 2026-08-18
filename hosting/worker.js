export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // The Sites asset binding does not automatically map `/` to Vite's
    // `index.html`. Resolve document requests explicitly so the production
    // entry point cannot degrade into an empty 404 page after sign-in.
    if (request.method === "GET" || request.method === "HEAD") {
      const isDocumentRequest =
        url.pathname === "/" || request.headers.get("accept")?.includes("text/html");

      if (isDocumentRequest) {
        url.pathname = "/index.html";
        return env.ASSETS.fetch(new Request(url, request));
      }
    }

    return env.ASSETS.fetch(request);
  },
};
