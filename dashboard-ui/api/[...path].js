/**
 * Vercel Edge Function — API proxy
 *
 * Routes /api/* → PORTER_API_UPSTREAM/*
 * Set PORTER_API_UPSTREAM in the Vercel project environment variables
 * (e.g. https://abc123.ngrok-free.app when running locally with ngrok).
 *
 * Mirrors the Netlify edge function at netlify/edge-functions/api-proxy.js.
 */

export const config = { runtime: 'edge' };

export default async function handler(request) {
  const upstream = process.env.PORTER_API_UPSTREAM || '';

  if (!upstream) {
    return new Response(
      JSON.stringify({ error: 'PORTER_API_UPSTREAM is not configured' }),
      {
        status: 503,
        headers: { 'content-type': 'application/json' },
      },
    );
  }

  const url = new URL(request.url);
  // Strip leading /api prefix before forwarding
  const upstreamPath = url.pathname.replace(/^\/api/, '') || '/';
  const targetUrl = upstream.replace(/\/$/, '') + upstreamPath + url.search;

  const headers = new Headers(request.headers);
  headers.set('ngrok-skip-browser-warning', 'true');

  const upstreamRequest = new Request(targetUrl, {
    method: request.method,
    headers,
    body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
  });

  try {
    return await fetch(upstreamRequest);
  } catch (err) {
    return new Response(
      JSON.stringify({ error: 'Upstream unreachable', detail: String(err) }),
      {
        status: 502,
        headers: { 'content-type': 'application/json' },
      },
    );
  }
}
