# Öffi Ausgang

Single-page web app for Vienna public transport: **live departures** for every
line at a stop, plus a **map of the U-Bahn station** showing every numbered
exit, lift, escalator (with running direction) and station stairs. Tap where you
want to go and it marks the closest exit.

Runs on GitHub Pages. The only live request is departures, which go through a
small Cloudflare Worker (see below for why).

```
index.html            the app (vanilla JS + Leaflet from cdnjs)
data.js               baked station data (generated, ~330 KB, ~80 KB gzipped)
scripts/build-data.py regenerates data.js from open data
worker/worker.js      Cloudflare Worker: CORS relay for the realtime API
worker/wrangler.toml  worker config
```

## Why a Worker?

The Wiener Linien realtime API (`wienerlinien.at/ogd_realtime/monitor`) is free
and keyless, but it sends no `Access-Control-Allow-Origin` header, so browsers
block a page on another domain from reading it (verified in Chrome, 2026-10-27).
The worker fetches it server-side and adds that header. It only relays the
read-only realtime endpoints (`monitor`, `trafficInfoList`, `newsList`, …), so it
isn't an open proxy, and it caches responses for 15 s.

## Data

| What | Source | When |
|---|---|---|
| Departures, disruptions, lift/escalator outages | Wiener Linien realtime API | live, every 30 s |
| Stops, lines, platforms | Wiener Linien OGD CSVs | baked into `data.js` |
| Lifts (with descriptions) | Stadt Wien WFS `AUFZUGOGD` | baked |
| Exits, stairs, escalators, more lifts | OpenStreetMap (Overpass) | baked |
| Map tiles | basemap.at (grey) | live |

Refresh the baked data (stations rarely change):

```sh
python3 scripts/build-data.py   # stdlib only; Overpass can be slow, it retries
```

Limits: no open dataset says which **train car** stops nearest which exit, so
the app shows where exits are, not where to board. Floridsdorf has no exits
mapped in OSM yet. Exit names come from OSM and are only as good as the mapping.

## Setup

### 1. Cloudflare Worker

1. Create a free account at <https://dash.cloudflare.com/sign-up> (email +
   password, no credit card needed for Workers Free: 100,000 requests/day).
2. Verify the email address.
3. Deploy, either way:
   - **CLI** (from this repo):
     ```sh
     cd worker
     npx wrangler login     # opens the browser, click "Allow"
     npx wrangler deploy    # prints https://wien-ausgang.<subdomain>.workers.dev
     ```
     The first deploy asks you to pick a `workers.dev` subdomain if you don't
     have one yet.
   - **Dashboard**: Workers & Pages → Create → Create Worker → name it
     `wien-ausgang` → Deploy → Edit code → paste `worker/worker.js` → Deploy.
4. Test it: open `https://wien-ausgang.<subdomain>.workers.dev/monitor?diva=60200657`;
   you should see JSON for Karlsplatz.

### 2. Point the app at it

Set `WORKER_URL` near the top of the script in `index.html` to the worker URL.
(Any device can also override it under ⚙ Einstellungen.)

### 3. GitHub Pages

Push this repo to GitHub, then Settings → Pages → Source: *Deploy from a
branch* → `main` / `/ (root)`. The app is then at
`https://<user>.github.io/wien-ausgang/`.

Optionally lock the worker to that origin: uncomment `ALLOWED_ORIGINS` in
`worker/wrangler.toml` (set it to `https://<user>.github.io`) and redeploy.

## Local development

```sh
cd worker && npx wrangler dev --port 8787     # local worker
python3 -m http.server 8766                   # in the repo root
# open http://127.0.0.1:8766, ⚙ → http://127.0.0.1:8787
```

Data: Wiener Linien and Stadt Wien (CC BY 4.0), © OpenStreetMap contributors (ODbL).
Not an official Wiener Linien product.
