#!/usr/bin/env python3
"""Build the site into ./site from config.json + data/*.json.

  data/history.json             hand-researched places (anyone can edit by pull request)
  data/suggestions_applied.json public suggestions accepted by the reviewer (additions + corrections)
  data/osm_current.json         today's businesses from OpenStreetMap (scripts/fetch_osm.py)
  data/geocache.json            address -> [lat, lng] cache (Nominatim), committed so builds are fast

Places without "lat"/"lng" are geocoded from "address" + config geocodeSuffix.
"""
import json, os, re, shutil, sys, time, datetime, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)
CUR = datetime.date.today().year
cfg = json.load(open(D("config.json")))
cache = json.load(open(D("data/geocache.json"))) if os.path.exists(D("data/geocache.json")) else {}
UA = {"User-Agent": f"neighborhood-timeline-map/1.0 ({cfg.get('github', {}).get('repo', 'unknown')})"}
CATS = {"retail", "food", "entertainment", "tech", "hotel", "landmark", "services", "fitness"}

def geocode(addr):
    if addr in cache: return cache[addr]
    q = urllib.parse.urlencode({"q": f"{addr}, {cfg['geocodeSuffix']}", "format": "json", "limit": 1})
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q, headers=UA), timeout=20))
    except Exception as ex:
        print(f"  geocode failed for {addr!r}: {ex}", file=sys.stderr); return None
    time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
    cache[addr] = [float(r[0]["lat"]), float(r[0]["lon"])] if r else None
    return cache[addr]

def inside(lat, lng, poly):
    """Ray casting point-in-polygon on [lat, lng] points."""
    hit = False
    for i in range(len(poly)):
        (y1, x1), (y2, x2) = poly[i], poly[i - 1]
        if (y1 > lat) != (y2 > lat) and lng < (x2 - x1) * (lat - y1) / (y2 - y1) + x1: hit = not hit
    return hit

def norm(t): return re.sub(r"[^a-z0-9]", "", t.lower())

def place(p, source):
    if p.get("category") not in CATS: p["category"] = "retail"
    if "lat" in p and "lng" in p: ll = [p["lat"], p["lng"]]
    else: ll = geocode(p["address"])
    if not ll: missing.append(p["address"]); return None
    rec = {"name": p["name"], "address": p["address"], "start": p.get("start") or CUR, "end": p.get("end"),
           "category": p["category"], "approx": bool(p.get("approx")), "note": p.get("note", ""),
           "lat": ll[0], "lng": ll[1], "source": p.get("source", source)}
    if not p.get("start"): rec["start_unknown"] = True
    return rec

missing, out = [], []
for p in json.load(open(D("data/history.json"))):
    r = place(p, "history");  out.append(r) if r else None
sug = json.load(open(D("data/suggestions_applied.json"))) if os.path.exists(D("data/suggestions_applied.json")) else {}
for p in sug.get("additions", []):
    r = place(dict(p, source="suggestion"), "suggestion");  out.append(r) if r else None

# ---- today's businesses from OpenStreetMap
FOOD = {"restaurant","cafe","bar","pub","fast_food","ice_cream","bakery","pastry","chocolate","confectionery","tea","food_court","biergarten","coffee","deli","wine","alcohol"}
ENT = {"cinema","theatre","nightclub"}; HOTEL = {"hotel","motel","guest_house"}
FIT = {"fitness_centre","sports_centre","dance","climbing","yoga","pilates","fitness","boxing"}
SERV = {"bank","hairdresser","beauty","hairdresser;beauty","dry_cleaning","optician","massage","copyshop","laundry","tailor","mobile_phone","pharmacy","chemist","glaziery","travel_agency"}
ABBR = [(" Avenue", " Ave"), (" Street", " St"), (" Road", " Rd"), (" Boulevard", " Blvd"), (" Drive", " Dr")]
def short(a):
    for x, y in ABBR: a = a.replace(x, y)
    return a
poly = cfg["area"]["polygon"]
open_now = [s for s in out if s["end"] is None]
added = merged = 0; seen = []
if os.path.exists(D("data/osm_current.json")):
    for e in json.load(open(D("data/osm_current.json"))).get("elements", []):
        t = e.get("tags", {}); name = t.get("name")
        la = e.get("lat") or e.get("center", {}).get("lat"); ln = e.get("lon") or e.get("center", {}).get("lon")
        if not name or la is None or not inside(la, ln, poly): continue
        hn, st = t.get("addr:housenumber", "").split(";")[0], t.get("addr:street", "")
        addr = short(f"{hn} {st}".strip()) if hn and st else (short(st) if st else "")
        words = set(re.findall(r"[a-z]{4,}", name.lower()))
        dup = False
        for s in open_now:   # already in history (same address + shared word, or same name nearby)?
            near = abs(s["lat"] - la) < 0.0015 and abs(s["lng"] - ln) < 0.0015
            if (addr and norm(s["address"]) == norm(addr) and words & set(re.findall(r"[a-z]{4,}", s["name"].lower()))) or \
               (near and (norm(s["name"]) == norm(name) or (words and words <= set(re.findall(r"[a-z]{4,}", s["name"].lower()))))):
                dup = True; break
        if dup: merged += 1; continue
        if any(n == norm(name) and abs(a - la) < 0.0004 and abs(b - ln) < 0.0004 for n, a, b in seen): continue
        seen.append((norm(name), la, ln))
        kind = t.get("amenity") or t.get("tourism") or t.get("leisure") or t.get("shop") or (t.get("sport", "").split(";")[0])
        cat = "fitness" if kind in FIT else "food" if kind in FOOD else "entertainment" if kind in ENT else "hotel" if kind in HOTEL else "services" if kind in SERV else "retail"
        out.append({"name": name, "address": addr or "address not listed", "start": CUR, "end": None, "category": cat,
                    "approx": False, "start_unknown": True, "source": "osm",
                    "note": f"Open today ({kind.replace('_', ' ').replace(';', ', ')}). Listed in OpenStreetMap; the year it opened isn't known yet.",
                    "lat": la, "lng": ln})
        added += 1

# ---- accepted corrections (match by name, and address if given)
fixed = 0
for c in sug.get("corrections", []):
    for x in [x for x in out if x["name"].lower() == c["target"].lower() and (not c.get("target_address") or x["address"] == c["target_address"])]:
        f = c.get("fields", {})
        for k in ("name", "start", "end", "category", "note", "approx"):
            if k in f: x[k] = f[k]
        if f.get("start"): x.pop("start_unknown", None)
        if f.get("address") and f["address"] != x["address"]:
            ll = geocode(f["address"])
            if ll: x["address"], x["lat"], x["lng"] = f["address"], ll[0], ll[1]
        fixed += 1

# ---- write the site
json.dump(cache, open(D("data/geocache.json"), "w"), indent=1)
os.makedirs(D("site"), exist_ok=True)
json.dump(out, open(D("site/places.json"), "w"), indent=1, ensure_ascii=False)
public_cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
html = open(D("web/index.html")).read()
html = html.replace("/*SITE_CONFIG*/{}", json.dumps(public_cfg, ensure_ascii=False))
esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
html = html.replace("{{TITLE}}", esc(cfg["title"])).replace("{{DESCRIPTION}}", esc(cfg["description"])).replace("{{START}}", str(cfg["startYear"]))
open(D("site/index.html"), "w").write(html)
for extra in ("robots.txt",):
    if os.path.exists(D("web", extra)): shutil.copy(D("web", extra), D("site", extra))
print(f"{len(out)} places ({added} from OpenStreetMap, {merged} merged, {fixed} corrections); not geocoded: {missing}")
if missing and os.environ.get("STRICT_GEOCODE"): sys.exit(1)
