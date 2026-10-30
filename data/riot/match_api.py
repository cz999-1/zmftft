"""Riot TFT Match API sampler (needs RIOT_API_KEY).

Key: env RIOT_API_KEY, or gitignored file data/riot/riot.local.json {"api_key": "RGAPI-..."}.
Rate limits (dev key): 20 req/1s and 100 req/2min -> client sleeps to stay under, retries 429 with Retry-After.

Usage:
  python3 -m data.riot.match_api --platform kr --region asia --players 5 --matches 4
Flow: tft-league-v1 challenger -> puuids -> tft-match-v1 ids -> match detail.
Output: data/riot/cache/sample_matches.json + per-unit stats (top4 / win rate, star levels).
"""
import argparse, collections, json, os, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(__file__)

def api_key():
    k = (os.environ.get("RIOT_API_KEY") or "").strip()
    if k:
        return k
    repo = os.path.abspath(os.path.join(HERE, "..", ".."))
    envp = os.path.join(repo, ".env")
    if os.path.exists(envp):
        for line in open(envp):
            if line.startswith("RIOT_API_KEY="):
                k = line.split("=", 1)[1].strip().strip(chr(34)+chr(39))
                if k:
                    return k
    loc = os.path.join(HERE, "riot.local.json")
    if os.path.exists(loc):
        k = (json.load(open(loc)).get("api_key") or "").strip()
        if k:
            return k
    return ""


class Client:
    def __init__(self, key, per2min=95, per1s=18):
        self.key, self.hits, self.lim2, self.lim1 = key, collections.deque(), per2min, per1s

    def _throttle(self):
        now = time.time()
        while self.hits and now - self.hits[0] > 120: self.hits.popleft()
        if len(self.hits) >= self.lim2:
            time.sleep(120 - (now - self.hits[0]) + 0.5)
        recent = [t for t in self.hits if now - t < 1]
        if len(recent) >= self.lim1: time.sleep(1)
        self.hits.append(time.time())

    def get(self, host, path, tries=4):
        for _ in range(tries):
            self._throttle()
            req = urllib.request.Request(f"https://{host}.api.riotgames.com{path}",
                                         headers={"X-Riot-Token": self.key, "User-Agent": "zmftft"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(int(e.headers.get("Retry-After", "10"))); continue
                if e.code in (500, 502, 503, 504): time.sleep(2); continue
                raise
        raise RuntimeError(f"failed {path}")

def sample(c, platform, region, players, matches):
    league = c.get(platform, "/tft/league/v1/challenger")
    puuids = [e["puuid"] for e in sorted(league["entries"], key=lambda e: -e["leaguePoints"])[:players]]
    ids = []
    for p in puuids:
        for m in c.get(region, f"/tft/match/v1/matches/by-puuid/{p}/ids?count={matches}"):
            if m not in ids: ids.append(m)
    return [c.get(region, f"/tft/match/v1/matches/{m}") for m in ids]

def unit_stats(games):
    st = collections.defaultdict(lambda: {"n": 0, "top4": 0, "win": 0, "place": 0, "star3": 0, "items3": 0})
    for g in games:
        for p in g["info"]["participants"]:
            for u in p["units"]:
                s = st[u["character_id"]]
                s["n"] += 1; s["place"] += p["placement"]
                s["top4"] += p["placement"] <= 4; s["win"] += p["placement"] == 1
                s["star3"] += u.get("tier") == 3; s["items3"] += len(u.get("itemNames", [])) >= 3
    return {k: {**v, "avg_place": round(v["place"] / v["n"], 2)} for k, v in st.items()}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default="kr"); ap.add_argument("--region", default="asia")
    ap.add_argument("--players", type=int, default=5); ap.add_argument("--matches", type=int, default=4)
    a = ap.parse_args()
    k = api_key()
    if not k:
        print("RIOT_API_KEY not set; skipping Match API sample (site build unaffected).")
        return 0
    games = sample(Client(k), a.platform, a.region, a.players, a.matches)
    out = os.path.join(HERE, "cache"); os.makedirs(out, exist_ok=True)
    stats = unit_stats(games)
    json.dump({"matches": len(games), "units": stats}, open(os.path.join(out, "sample_stats.json"), "w"), indent=1)
    json.dump(games, open(os.path.join(out, "sample_matches.json"), "w"))
    print(f"{len(games)} matches sampled -> data/riot/cache/")
    return 0

if __name__ == "__main__":
    sys.exit(main())
