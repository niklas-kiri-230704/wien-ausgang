# Öffi Ausgang

Single-page web app (PWA) for Vienna public transport, built for someone who
wants to know not just *which* line to take but *which exit* to use:

- **Live departures** for every line at a stop.
- **Station maps** of every U-Bahn station: numbered exits, lifts, escalators
  (with running direction) and stairs. Tap where you want to go and the closest
  exit is marked.
- **Route planner** from A to B that picks the entrance and exit at every
  U-Bahn station and uses live times.
- **Address → nearest station and exit**, ranked by real walking distance.
- **Unterwegs mode**: step-by-step guidance while travelling, with a warning one
  stop before getting off.

Live at <https://niklas-kiri-230704.github.io/wien-ausgang/> (GitHub Pages).
Requests that the Wiener Linien servers don't allow from a browser go through
a small Cloudflare Worker (see [Why a Worker?](#why-a-worker)).

It's a PWA: on iPhone, Safari → Share → "Zum Home-Bildschirm" installs it with
its own icon, full-screen. The app, station maps and the last search work
offline; live times, new searches and address lookup need network.

## Features

### Start page

- **Schnell hin**: one big button per saved place ("Zuhause", "Arzt", …); a tap
  plans the route from your current position.
- Station search, "In meiner Nähe", starred stations, and buttons for
  **Route planen** and **Adresse → Ausgang**.

### Station page (`#/s/<diva>`)

- Live departures (every 30 s); tap one to highlight its platform on the map.
- Lift/escalator outages and disruptions. A broken lift is crossed out on the
  map. Planned maintenance is shown as "geplant" with its time window and only
  counts as broken while it is on.
- Map with exits, lifts, escalators, stairs; tap a destination to get the
  nearest exit. `#/s/<diva>?to=lat,lon` opens it with a destination already set.
- **⋮ menu**: "Fehlenden Ausgang eintragen" (tap the map, name it, step-free or
  not) and "Ausgänge umbenennen / löschen" (rename any exit, delete your own,
  reset a name). See [Data on the device](#data-on-the-device).

### Route planner (`#/route`)

- From/to: address, station, place or "Mein Standort", with suggestions as you
  type; saved places first, then recent ones. Swap button, "Jetzt / Abfahrt um /
  Ankunft um", and **stufenlos** (step-free).
- Trips come from the Wiener Linien trip planner (EFA). It only knows the
  timetable, so every ride is matched to the **live monitor** of its boarding
  stop. The live time is the first vehicle that actually leaves in that
  direction after the planned time; on busy lines that is often an earlier,
  delayed train, so the app doesn't track the scheduled run.
- Each trip shows "Losgehen in N min", live delays, transfer time, and
  **"Anschluss gefährdet"** when a delay breaks a connection. Trips that have
  already left are hidden; when all are gone it searches again.
- **Entrance and exit** at every U-Bahn station: the entrance closest to where
  you come from, the exit closest to where you go next (the address, or the
  tram/bus stop you change to). Changing lines inside one station needs no exit.
  In step-free mode exits without step-free access, or whose lift is out, are
  avoided.
- **Faults on the route**: line disruptions per ride, lift/escalator outages
  per station, and a warning on the trip summary when the lift at a used exit
  is out.
- **Where to board**: no open data says which car stops at which stairs, so
  every U-Bahn ride has "vorne / Mitte / hinten" (in the direction of travel)
  to note it once. It is remembered per line, direction, stop and exit (or the
  U-line you change to) and shown on every later trip that uses it.
- Under 1.5 km it also says how long walking takes.
- "☆ Ziel speichern" saves the destination as a place.
- The last search is kept for 12 h and comes back after closing the app or
  without network.

### Unterwegs mode (`#/unterwegs`)

Started with "▶ Unterwegs-Modus starten" on an opened trip. One big step at a
time: "Zum Eingang 3 – noch 230 m", "U1 Richtung Oberlaa – in 2 min, vorne
einsteigen", "Noch 3 Stationen", **"Nächste Station aussteigen!"**, "Dann
Ausgang 1".

- Walking steps advance by GPS (near the entrance, stop or destination), or when
  the next ride is about to leave.
- Rides advance by the planner's per-stop times plus the live delay, because GPS
  doesn't work underground; a good GPS fix at a station overrides that.
- One stop before getting off, the card turns red and three beeps play (Web
  Audio, unlocked by the start tap). `navigator.vibrate` is used where supported,
  which is not iPhone. The beep is silent when the iPhone's mute switch is on.
- It asks the browser to keep the screen on (Wake Lock).
- It only works while the app is open on screen: iOS gives web apps no
  background GPS or audio.
- "Zurück" / "Weiter" correct the step by hand (after "Zurück" it waits a
  minute before moving on by itself). The current step survives a reload.

### Adresse → Ausgang (`#/ort`)

Enter an address (or "Mein Standort") and get the three nearest U-Bahn stations
with their best exit, ranked by **real walking distance**, with the walks drawn
on the map, plus all stops nearby. If the walking-route server doesn't answer it
falls back to straight-line distance. "Route hierher planen" and "☆ Ort
speichern" are there too.

## Data on the device

Everything personal lives in that browser's `localStorage` only (nothing is
sent anywhere). On iPhone the home-screen app and Safari have **separate**
storage, so set things up in the one that is actually used. Clearing website
data or removing the app deletes it.

| Key | What |
|---|---|
| `wa.places` | saved places (also editable under ⚙) |
| `wa.board` | "where to board" notes (count and "Alle löschen" under ⚙) |
| `wa.ownExits`, `wa.exitNames` | exits added / renamed via the station ⋮ menu |
| `wa.lastPlan`, `wa.nav` | last search (12 h) and the current Unterwegs step |
| `wa.recent`, `wa.favs`, `wa.wc`, `wa.worker` | recent places, starred stations, step-free setting, worker override |

Own exits are merged into the station data at startup and used by the planner
and the address search like any other exit. They are not part of `data.js`, so
the monthly refresh never touches them.

## Files

```
index.html                         the app (vanilla JS + Leaflet from cdnjs)
manifest.webmanifest               PWA manifest; icons/ from scripts/make-icons.py (Pillow)
sw.js                              service worker: offline app shell (bump CACHE on releases)
data.js                            baked station data (generated, ~330 KB, ~80 KB gzipped)
scripts/build-data.py              regenerates data.js from open data
.github/workflows/refresh-data.yml monthly data refresh
worker/worker.js                   Cloudflare Worker: CORS relay for realtime API + trip planner
worker/wrangler.toml               worker config
```

## Why a Worker?

The Wiener Linien realtime API (`wienerlinien.at/ogd_realtime/…`) and trip
planner (`wienerlinien.at/ogd_routing/XML_TRIP_REQUEST2`) are free and keyless,
but send no `Access-Control-Allow-Origin` header, so browsers block a page on
another domain from reading them (verified in Chrome, 2026-10-27). The worker
fetches them server-side and adds that header.

| Worker path | Upstream | Cache |
|---|---|---|
| `/monitor`, `/trafficInfoList`, `/trafficInfo`, `/newsList`, `/news`, `/version` | `ogd_realtime/<same>` | 15 s |
| `/trip` | `ogd_routing/XML_TRIP_REQUEST2` (forces `outputFormat=JSON`, relabels it `application/json`) | 30 s |

Nothing else is relayed, so it isn't an open proxy.

## Data sources

| What | Source | When |
|---|---|---|
| Departures, disruptions, lift/escalator outages | Wiener Linien realtime API (via worker) | live, every 30 s |
| Trips | Wiener Linien trip planner, EFA (via worker) | per search |
| Addresses, named places | Stadt Wien address service `OGDAddressService` (CORS, no key) | per search |
| Shops, sights (fallback) | Photon by komoot (OpenStreetMap) | per search |
| Walking distances and routes | OSRM foot server, routing.openstreetmap.de (FOSSGIS) | address view |
| Stops, lines, platforms | Wiener Linien OGD CSVs | baked into `data.js` |
| Lifts (with descriptions) | Stadt Wien WFS `AUFZUGOGD` | baked |
| Exits, stairs, escalators, more lifts | OpenStreetMap (Overpass) | baked |
| Map tiles | basemap.at (grey) | live |

Things worth knowing about the data:

- Outages name lifts as `SL 03`, the baked data as `SL A03`; `liftKey()` maps
  both to the same key. A broken lift marks every exit within 60 m.
- The trip planner's timetable can differ from the live monitor by a minute;
  live matching allows for that.
- Live times exist only for Wiener Linien vehicles; S-Bahn and other trains
  show timetable times.
- Exit names come from OpenStreetMap and are only as good as the mapping; some
  exits have no name, and Floridsdorf has no exits mapped at all (add them with
  the station ⋮ menu).

### Refreshing the baked data

```sh
python3 scripts/build-data.py   # stdlib only; Overpass can be slow, it retries
```

The GitHub Action `.github/workflows/refresh-data.yml` does this on the 1st of
every month (04:17 UTC) and commits `data.js` only if the data changed. It
refuses to commit when the result looks incomplete (fewer than 90 stations, or
more than 10% fewer exits or stops than before), which happens when Overpass
half-fails. Run it by hand under Actions → "Refresh station data" → Run
workflow. Because it commits to `main`, pull before pushing local changes.

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

The deployed worker is `https://wien-ausgang.niklaskiri.workers.dev`. Changes to
`worker/worker.js` only take effect after `npx wrangler deploy`; pushing to
GitHub does not deploy it.

### 2. Point the app at it

Set `WORKER_URL` near the top of the script in `index.html` to the worker URL.
(Any device can also override it under ⚙ Einstellungen.)

### 3. GitHub Pages

Push this repo to GitHub, then Settings → Pages → Source: *Deploy from a
branch* → `main` / `/ (root)`. The app is then at
`https://<user>.github.io/wien-ausgang/`.

Optionally lock the worker to that origin: uncomment `ALLOWED_ORIGINS` in
`worker/wrangler.toml` (set it to `https://<user>.github.io`) and redeploy.

### Releasing

Push to `main`; Pages redeploys within about a minute. Bump `CACHE` in `sw.js`
with each release so installed apps drop their old cached files. On a phone,
close the app completely and reopen it to get the new version.

## Local development

```sh
cd worker && npx wrangler dev --port 8787     # local worker
python3 -m http.server 8766                   # in the repo root
# open http://127.0.0.1:8766, ⚙ → http://127.0.0.1:8787
```

Data: Wiener Linien and Stadt Wien (CC BY 4.0), © OpenStreetMap contributors (ODbL).
Not an official Wiener Linien product.
