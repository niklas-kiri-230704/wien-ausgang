#!/usr/bin/env python3
"""Build data.js: stop list, U-Bahn stations, their exits and lifts.

Sources (all open data, re-run this script to refresh):
  - Wiener Linien OGD: stops (DIVA), stop points (RBL), lines, route patterns
  - Stadt Wien WFS: lifts (AUFZUGOGD)
  - OpenStreetMap via Overpass: railway=subway_entrance nodes, stairs and
    escalators (highway=steps, conveying=*) and lifts around each station

Usage: python3 scripts/build-data.py   (writes ./data.js)
"""
import csv, io, json, math, sys, time, urllib.parse, urllib.request
from datetime import date

UA = {"User-Agent": "wien-ausgang-build/1.0 (+https://github.com/)"}
WFS = ("https://data.wien.gv.at/daten/geo?service=WFS&request=GetFeature&version=1.1.0"
       "&srsName=EPSG:4326&outputFormat=json&typeName=ogdwien:")
OGD = "https://www.wienerlinien.at/ogd_realtime/doku/ogd/"
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
OVERPASS_Q = ('[out:json][timeout:90];'
              '(node["railway"="subway_entrance"](48.11,16.18,48.33,16.58););out body;')

EXIT_RADIUS = 400   # m: entrance/lift counts for the nearest station within this
WAY_RADIUS = 250    # m: stairs/escalators/lifts fetched around each station


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def overpass(q):
    """Overpass is often busy: try each mirror a few times."""
    body = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(3):
        for url in OVERPASS:
            try:
                return json.loads(get(url, body))
            except Exception as e:  # noqa: BLE001 - retry anything, report the last
                print(f"  overpass {url}: {e}", file=sys.stderr)
                time.sleep(5 * attempt)
    sys.exit("overpass: all mirrors failed")


def dist(a, b):
    """Metres between (lat, lon) pairs (equirectangular, fine at city scale)."""
    x = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    y = math.radians(b[0] - a[0])
    return 6371000 * math.hypot(x, y)


def line_sort(ls):
    """U1..U6 first, then trams (numbers/letters), then buses (13A...), night lines last."""
    def key(l):
        kind = 0 if l.startswith("U") else 3 if l.startswith("N") else 2 if l[-1:] in "AB" and l[:-1].isdigit() else 1
        num = "".join(c for c in l if c.isdigit())
        return (kind, int(num) if num else 0, l)
    return sorted(ls, key=key)


def r5(x):
    return round(x, 6)


def main():
    def ogd_csv(name):
        text = get(OGD + f"wienerlinien-ogd-{name}.csv").decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text), delimiter=";"))

    # --- lines and which stop points (RBL / StopID) they serve --------------
    lines = {r["LineID"]: (r["LineText"].strip(), r["MeansOfTransport"].strip())
             for r in ogd_csv("linien")}
    pattern = {}  # (LineID, PatternID) -> [(seq, StopID, Direction)]
    for r in ogd_csv("fahrwegverlaeufe"):
        pattern.setdefault((r["LineID"], r["PatternID"]), []).append(
            (int(r["StopSeqCount"]), r["StopID"], r["Direction"] or ""))
    points = {r["StopID"]: r for r in ogd_csv("haltepunkte")}

    rbl_lines = {}  # StopID -> {(line, type, direction, terminus StopID)}
    for (lid, _), seq in pattern.items():
        if lid not in lines:
            continue
        seq.sort(key=lambda x: x[0])
        last = seq[-1][1]
        for _, sid, direction in seq[:-1]:
            rbl_lines.setdefault(sid, set()).add((*lines[lid], direction, last))

    def pt_name(sid):
        return points.get(sid, {}).get("StopText", "").strip()

    # --- all stops (search + "nearby") --------------------------------------
    stops, by_diva = [], {}
    for r in ogd_csv("haltestellen"):
        try:
            lat, lon = float(r["Latitude"]), float(r["Longitude"])
        except (ValueError, TypeError):
            continue
        st = {"diva": int(r["DIVA"]), "name": r["PlatformText"].strip(),
              "lat": lat, "lon": lon, "lines": set()}
        stops.append(st)
        by_diva[r["DIVA"]] = st
    for sid, ls in rbl_lines.items():
        st = by_diva.get(points.get(sid, {}).get("DIVA", ""))
        if st:
            st["lines"].update(l[0] for l in ls)
    print(f"stops: {len(stops)}", file=sys.stderr)

    # --- U-Bahn stations: stops served by a metro line ----------------------
    stations = {}
    for sid, ls in rbl_lines.items():
        metro = sorted({(l[0], l[2], l[3]) for l in ls if l[1] == "ptMetro"})
        p = points.get(sid)
        if not metro or not p or p["DIVA"] not in by_diva:
            continue
        try:
            lat, lon = float(p["Latitude"]), float(p["Longitude"])
        except ValueError:
            continue
        st = stations.setdefault(p["DIVA"], {**by_diva[p["DIVA"]], "pts": [], "platforms": []})
        st["pts"].append((lat, lon))
        for line, direction, last in metro:
            st["platforms"].append({"rbl": int(sid), "line": line, "dir": direction,
                                    "to": pt_name(last), "lat": r5(lat), "lon": r5(lon)})
    stations = list(stations.values())
    for s in stations:
        s["lat"] = sum(p[0] for p in s["pts"]) / len(s["pts"])
        s["lon"] = sum(p[1] for p in s["pts"]) / len(s["pts"])
        s["ulines"] = sorted({p["line"] for p in s["platforms"]})
        # route patterns repeat a platform with and without a direction: keep one
        uniq = {}
        for p in s["platforms"]:
            k = (p["rbl"], p["line"], p["to"])
            if k not in uniq or (p["dir"] and not uniq[k]["dir"]):
                uniq[k] = p
        s["platforms"] = sorted(uniq.values(), key=lambda p: (p["line"], p["dir"], p["to"]))
    print(f"u-bahn stations: {len(stations)}", file=sys.stderr)

    def nearest_station(lat, lon):
        best, bd = None, 1e9
        for s in stations:
            # distance to the closest of the station's line points (big interchanges)
            d = min(dist((lat, lon), p) for p in s["pts"])
            if d < bd:
                best, bd = s, d
        return best if bd <= EXIT_RADIUS else None

    # --- exits from OSM -----------------------------------------------------
    osm = overpass(OVERPASS_Q)
    n_exit = 0
    for e in osm["elements"]:
        t = e.get("tags", {})
        s = nearest_station(e["lat"], e["lon"])
        if not s:
            continue
        s.setdefault("exits", []).append({
            "lat": r5(e["lat"]), "lon": r5(e["lon"]),
            "name": t.get("name") or t.get("description") or "",
            "wc": t.get("wheelchair", ""),
            "lift": t.get("highway") == "elevator" or t.get("elevator") == "yes",
            "osm": e["id"],
        })
        n_exit += 1
    print(f"exits matched: {n_exit} of {len(osm['elements'])}", file=sys.stderr)

    # --- stairs, escalators and lifts from OSM around each station ----------
    around = "".join(
        f'way["highway"="steps"](around:{WAY_RADIUS},{st["lat"]},{st["lon"]});'
        f'node["highway"="elevator"](around:{WAY_RADIUS},{st["lat"]},{st["lon"]});'
        for st in stations)
    near = overpass(f"[out:json][timeout:180];({around});out tags geom;")["elements"]
    n_way = 0
    osm_lifts = []
    for e in near:
        t = e.get("tags", {})
        if e["type"] == "node":
            osm_lifts.append(e)
            continue
        esc = t.get("conveying") not in (None, "no")
        in_station = any(k in t for k in ("level", "indoor", "tunnel", "layer", "covered"))
        if not (esc or in_station) or len(e.get("geometry", [])) < 2:
            continue  # plain street stairs: not part of a station
        g = e["geometry"]
        mid = g[len(g) // 2]
        st = nearest_station(mid["lat"], mid["lon"])
        if not st:
            continue
        way = {"t": "esc" if esc else "steps", "c": [[r5(p["lat"]), r5(p["lon"])] for p in g]}
        if esc and t.get("conveying") in ("forward", "backward", "reversible"):
            way["d"] = t["conveying"]
        if t.get("step_count", "").isdigit():
            way["s"] = int(t["step_count"])
        if t.get("ramp") == "yes" or t.get("ramp:stroller") == "yes" or t.get("ramp:wheelchair") == "yes":
            way["r"] = 1
        if t.get("name") or t.get("description"):
            way["n"] = t.get("name") or t.get("description")
        st.setdefault("ways", []).append(way)
        n_way += 1
    print(f"stairs/escalators matched: {n_way} of {len(near) - len(osm_lifts)}", file=sys.stderr)

    # --- lifts from the city -----------------------------------------------
    n_lift = 0
    for f in json.loads(get(WFS + "AUFZUGOGD"))["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        s = nearest_station(lat, lon)
        if not s:
            continue
        s.setdefault("lifts", []).append({
            "lat": r5(lat), "lon": r5(lon), "id": p.get("ANLAGEN_ID") or "",
            "line": p.get("LINIE") or "", "text": (p.get("BEMERKUNG") or "").strip(),
        })
        n_lift += 1
    # OSM lifts the city list doesn't have (e.g. lifts inside the station)
    for e in osm_lifts:
        st = nearest_station(e["lat"], e["lon"])
        if not st or any(dist((e["lat"], e["lon"]), (l["lat"], l["lon"])) < 15 for l in st.get("lifts", [])):
            continue
        t = e.get("tags", {})
        lv = t.get("level", "")
        text = t.get("description") or t.get("name") or ""
        if not text and ";" in lv:
            text = "Aufzug zwischen Ebene " + " und ".join(lv.split(";"))
        st.setdefault("lifts", []).append({"lat": r5(e["lat"]), "lon": r5(e["lon"]), "id": "",
                                           "line": "", "text": text or "Aufzug"})
        n_lift += 1
    print(f"lifts matched: {n_lift} (city + OSM)", file=sys.stderr)

    out = {
        "generated": date.today().isoformat(),
        "stops": [[s["diva"], s["name"], r5(s["lat"]), r5(s["lon"]), " ".join(line_sort(s["lines"]))]
                  for s in stops if s["lines"]],
        "stations": [{
            "diva": s["diva"], "name": s["name"], "lines": s["ulines"],
            "lat": r5(s["lat"]), "lon": r5(s["lon"]), "platforms": s["platforms"],
            "exits": sorted(s.get("exits", []), key=lambda x: x["name"]),
            "lifts": s.get("lifts", []),
            "ways": s.get("ways", []),
        } for s in sorted(stations, key=lambda s: s["name"])],
    }
    with open("data.js", "w", encoding="utf-8") as fh:
        fh.write("// Generated by scripts/build-data.py - do not edit by hand.\n")
        fh.write("// Data: Wiener Linien OGD, Stadt Wien OGD (CC BY 4.0), (c) OpenStreetMap contributors (ODbL).\n")
        fh.write("window.WA_DATA = ")
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    print("wrote data.js", file=sys.stderr)


if __name__ == "__main__":
    main()
