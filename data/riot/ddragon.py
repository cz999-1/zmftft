"""Riot official TFT Data Dragon fetcher (no API key needed).

Usage: python3 -m data.riot.ddragon [--lang zh_CN] [--out data/riot/cache]
Writes champions/items/traits JSON for the latest patch, filtered to current set.
"""
import argparse, json, os, re, urllib.request

BASE = "https://ddragon.leagueoflegends.com"

def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "zmftft"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def latest_version():
    return get(f"{BASE}/api/versions.json")[0]

def load(kind, version, lang="zh_CN"):
    """kind: tft-champion | tft-item | tft-trait | tft-augments | tft-tactician ..."""
    return get(f"{BASE}/cdn/{version}/data/{lang}/{kind}.json")["data"]

def current_set(champs):
    sets = [int(m.group(1)) for k in champs for m in [re.search(r"TFTSet(\d+)", k)] if m]
    return max(sets) if sets else None

def image_url(version, group, full):
    return f"{BASE}/cdn/{version}/img/{group}/{full}"

def snapshot(lang="zh_CN"):
    v = latest_version()
    champs, items, traits = (load(k, v, lang) for k in ("tft-champion", "tft-item", "tft-trait"))
    s = current_set(champs)
    tag = f"TFTSet{s}"
    cur = {c["id"]: {"name": c["name"], "cost": c.get("cost"),
                     "icon": image_url(v, "tft-champion", c["image"]["full"])}
           for k, c in champs.items() if tag in k}
    tr = {t["id"]: {"name": t["name"], "icon": image_url(v, "tft-trait", t["image"]["full"])}
          for t in traits.values() if f"_{s}_" in t["id"] or f"Set{s}" in t["id"] or f"TFT{s}_" in t["id"]}
    it = {i["id"]: {"name": i["name"], "icon": image_url(v, "tft-item", i["image"]["full"])}
          for i in items.values()}
    return {"version": v, "set": s, "lang": lang, "champions": cur, "traits": tr, "items": it}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="zh_CN")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "cache"))
    a = ap.parse_args()
    snap = snapshot(a.lang)
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, f"ddragon_{a.lang}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    print(f"Data Dragon {snap['version']} Set {snap['set']}: {len(snap['champions'])} champs, "
          f"{len(snap['traits'])} traits, {len(snap['items'])} items -> {p}")

if __name__ == "__main__":
    main()
