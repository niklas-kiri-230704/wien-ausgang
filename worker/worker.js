// Cloudflare Worker: relays the Wiener Linien realtime API and adds the CORS
// header it lacks, so the GitHub Pages app can read it from the browser.
//
//   GET https://<worker>/monitor?diva=60200657&activateTrafficInfo=aufzugsinfo
//   -> https://www.wienerlinien.at/ogd_realtime/monitor?diva=...
//   GET https://<worker>/trip?type_origin=stopID&name_origin=60200657&...
//   -> https://www.wienerlinien.at/ogd_routing/XML_TRIP_REQUEST2?...&outputFormat=JSON
//
// Only the read-only realtime endpoints and the trip planner are relayed (it is
// not an open proxy).
// Responses are cached at the edge for a few seconds, which is well within how
// often the departure data changes and keeps the upstream load low.
//
// Optional env var ALLOWED_ORIGINS: comma-separated origins that may call this
// worker (e.g. "https://name.github.io"). Unset = any origin.

const UPSTREAM = "https://www.wienerlinien.at/ogd_realtime/";
const ENDPOINTS = new Set(["monitor", "trafficInfoList", "trafficInfo", "newsList", "news", "version"]);
const CACHE_SECONDS = 15;
// Trip planner (EFA). It answers JSON but labels it text/html, so we relabel it.
const ROUTING = "https://www.wienerlinien.at/ogd_routing/";
const ROUTING_ENDPOINTS = { trip: "XML_TRIP_REQUEST2" };
const ROUTING_CACHE_SECONDS = 30;

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
    let target, maxAge = CACHE_SECONDS;
    if (ENDPOINTS.has(endpoint)) {
      target = UPSTREAM + endpoint + url.search;
    } else if (ROUTING_ENDPOINTS[endpoint]) {
      url.searchParams.set("outputFormat", "JSON");
      target = ROUTING + ROUTING_ENDPOINTS[endpoint] + url.search;
      maxAge = ROUTING_CACHE_SECONDS;
    } else {
      return json({ error: "unknown endpoint", endpoints: [...ENDPOINTS, ...Object.keys(ROUTING_ENDPOINTS)] }, 404, cors);
    }

    const cache = caches.default;
    const cacheKey = new Request(target, { method: "GET" });
    let upstream = await cache.match(cacheKey);

    if (!upstream) {
      try {
        const res = await fetch(target, {
          headers: { Accept: "application/json", "User-Agent": "wien-ausgang (Cloudflare Worker)" },
        });
        upstream = new Response(res.body, res);
        upstream.headers.set("Cache-Control", `public, max-age=${maxAge}`);
        upstream.headers.set("Content-Type", "application/json; charset=utf-8");
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
