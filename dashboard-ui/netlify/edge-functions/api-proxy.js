/* global Deno */

const UPSTREAM = Deno.env.get("PORTER_API_UPSTREAM") || "";

export default async (request) => {
  if (!UPSTREAM) {
    return new Response("PORTER_API_UPSTREAM is not configured", {
      status: 503,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  const url = new URL(request.url);
  const upstreamUrl = new URL(
    url.pathname.replace(/^\/api/, "") + url.search,
    UPSTREAM,
  );

  const headers = new Headers(request.headers);
  headers.set("ngrok-skip-browser-warning", "true");

  const upstreamRequest = new Request(upstreamUrl.toString(), {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
  });

  return fetch(upstreamRequest);
};

export const config = { path: "/api/*" };
