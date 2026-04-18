const UPSTREAM = "https://dimly-disinfect-upright.ngrok-free.dev";

export default async (request) => {
  const url = new URL(request.url);
  const upstreamUrl = UPSTREAM + url.pathname.replace(/^\/api/, "") + url.search;

  const headers = new Headers(request.headers);
  headers.set("ngrok-skip-browser-warning", "true");

  const upstreamRequest = new Request(upstreamUrl, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
  });

  return fetch(upstreamRequest);
};

export const config = { path: "/api/*" };
