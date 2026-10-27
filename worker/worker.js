// Cloudflare Worker: relays the Wiener Linien realtime API and adds the CORS
// header it lacks, so the GitHub Pages app can read it from the browser.
//
//   GET https://<worker>/monitor?diva=60200657&activateTrafficInfo=aufzugsinfo
//   -> https://www.wienerlinien.at/ogd_realtime/monitor?diva=...
//
// Only the read-only realtime endpoints are relayed (it is not an open proxy).
// Responses are cached at the edge for a few seconds, which is well within how
// often the departure data changes and keeps the upstream load low.
//
// Optional env var ALLOWED_ORIGINS: comma-separated origins that may call this
// worker (e.g. "https://name.github.io"). Unset = any origin.

const UPSTREAM = "https://www.wienerlinien.at/ogd_realtime/";
const ENDPOINTS = new Set(["monitor", "trafficInfoList", "trafficInfo", "newsList", "news", "version"]);
const CACHE_SECONDS = 15;

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const allowed = (env.ALLOWED_ORIGINS || "*").split(",").map((s) => s.trim());
    const allowOrigin = allowed.includes("*") ? "*" : allowed.includes(origin) ? origin : null;

    const cors = {
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Accept, Content-Type",
      "Access-Control-Max-Age": "86400",
      Vary: "Origin",
    };
    if (allowOrigin) cors["Access-Control-Allow-Origin"] = allowOrigin;

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "GET") return json({ error: "method not allowed" }, 405, cors);
    if (!allowOrigin) return json({ error: "origin not allowed" }, 403, cors);

    const url = new URL(request.url);
    const endpoint = url.pathname.replace(/^\/+|\/+$/g, "");
    if (!ENDPOINTS.has(endpoint)) {
      return json({ error: "unknown endpoint", endpoints: [...ENDPOINTS] }, 404, cors);
    }

    const target = UPSTREAM + endpoint + url.search;
    const cache = caches.default;
    const cacheKey = new Request(target, { method: "GET" });
    let upstream = await cache.match(cacheKey);

    if (!upstream) {
      try {
        const res = await fetch(target, {
          headers: { Accept: "application/json", "User-Agent": "wien-ausgang (Cloudflare Worker)" },
        });
        upstream = new Response(res.body, res);
        upstream.headers.set("Cache-Control", `public, max-age=${CACHE_SECONDS}`);
        if (res.ok) ctx.waitUntil(cache.put(cacheKey, upstream.clone()));
      } catch (err) {
        return json({ error: "upstream unreachable", detail: String(err) }, 502, cors);
      }
    }

    const out = new Response(upstream.body, upstream);
    for (const h of ["Set-Cookie", "set-cookie"]) out.headers.delete(h);
    for (const [k, v] of Object.entries(cors)) out.headers.set(k, v);
    return out;
  },
};

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...headers, "Content-Type": "application/json; charset=utf-8" },
  });
}
