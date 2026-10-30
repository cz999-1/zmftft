"""Compare Riot Match API sample avg placement vs tactics.tools.

Usage: python3 -m data.riot.compare  (after match_api has produced cache/sample_stats.json)
Prints per-unit: sample n, sample avg place, tactics.tools avg place, delta.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from generate_tft_table import fetch_next_data, TACTICS  # reuse existing pipeline

HERE = os.path.dirname(__file__)

def main():
    p = os.path.join(HERE, "cache", "sample_stats.json")
    if not os.path.exists(p):
        print("No sample_stats.json; run python3 -m data.riot.match_api first."); return
    mine = json.load(open(p))["units"]
    try:
        tt = fetch_next_data(f"{TACTICS}/units")
        rows = tt["props"]["pageProps"]["data"]["units"] if "props" in tt else []
        ref = {r.get("unitId") or r.get("id"): r for r in rows}
    except Exception as e:
        print("tactics.tools fetch failed:", e); ref = {}
    print(f"{'unit':28}{'n':>6}{'riot':>8}{'tt':>8}{'Δ':>7}")
    for u, s in sorted(mine.items(), key=lambda x: -x[1]["n"]):
        r = ref.get(u, {}); t = r.get("place") or r.get("avgPlace")
        d = f"{s['avg_place']-t:+.2f}" if isinstance(t, (int, float)) else "-"
        print(f"{u:28}{s['n']:>6}{s['avg_place']:>8}{(t if t else '-'):>8}{d:>7}")

if __name__ == "__main__":
    main()
