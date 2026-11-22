#!/usr/bin/env python3
"""Fetch today's businesses inside config.json's area polygon from OpenStreetMap (Overpass API)
into data/osm_current.json. Run weekly by .github/workflows/refresh-osm.yml."""
import json, os, sys, urllib.parse, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(ROOT, "config.json")))
lats = [p[0] for p in cfg["area"]["polygon"]]; lngs = [p[1] for p in cfg["area"]["polygon"]]
pad = 0.001
bbox = f"{min(lats)-pad},{min(lngs)-pad},{max(lats)+pad},{max(lngs)+pad}"
q = f"""[out:json][timeout:60];
(
  nwr["shop"]({bbox});
  nwr["amenity"~"^(restaurant|cafe|bar|pub|fast_food|ice_cream|cinema|theatre|nightclub|bank|pharmacy|food_court|biergarten)$"]({bbox});
  nwr["tourism"~"^(hotel|motel|guest_house)$"]({bbox});
  nwr["leisure"~"^(fitness_centre|sports_centre|dance|climbing)$"]({bbox});
  nwr["sport"~"yoga|pilates|fitness|boxing|climbing"]["name"]({bbox});
);
out center tags;"""
for url in ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": "neighborhood-timeline-map/1.0"})
        d = json.load(urllib.request.urlopen(req, timeout=90))
        if len(d.get("elements", [])) == 0: print(f"{url}: 0 elements, trying next"); continue
        json.dump(d, open(os.path.join(ROOT, "data", "osm_current.json"), "w"), indent=0)
        print(f"{len(d['elements'])} places from {url}"); sys.exit(0)
    except Exception as ex:
        print(f"{url} failed: {ex}")
sys.exit("all Overpass servers failed; keeping the previous data")
