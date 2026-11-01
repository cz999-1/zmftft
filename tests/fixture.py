"""A made-up snapshot for the tests, built from the committed sets/set<N>.json: real unit and trait ids and
names, invented numbers, items and comps. No tactics.tools or Riot figures are committed; the real snapshot
stays in the ignored cache/snapshots/."""
import random

ICONS = "https://raw.communitydragon.org/16.21/game/assets/fixture/"


def snapshot(manual, seed=0):
    rnd = random.Random(seed)
    s = manual["set"]
    classes, origins = manual["classes"], manual["origins"]
    trait_names = {t: n for t, n in classes + origins}
    roster = list(manual["positions"])
    ids = roster + [i for i, _ in manual["hide"]]
    name = {i: n for i, (_, n) in manual["positions"].items()}
    name.update({i: n for i, n in manual["hide"]})
    traits = {i: [classes[j % len(classes)][0], origins[j % len(origins)][0]] for j, i in enumerate(ids)}
    items = ["TFT_Item_Fixture%d" % k for k in range(12)]

    def stats(n):
        return {"count": n, "place": round(rnd.uniform(3.5, 5.5), 2), "top4": round(rnd.uniform(35, 65), 2), "won": round(rnd.uniform(6, 20), 2)}

    comps = []
    for o in range(12):
        pair = {origins[o][0], origins[(o + 1) % len(origins)][0]}
        units = [i for i in roster if traits[i][1] in pair][:8]
        n = rnd.randint(200, 5000)
        comps.append({"units": units, "count": n, "place": round(rnd.uniform(3, 6), 3), "top4": n // 2, "win": n // 8,
                      "spatItems": [], "extraTraits": []})
    parts = ["Part%d" % k for k in range(10)]
    return {
        "meta": {"set": s, "set_marker": "TFT_Set%d" % s, "patch": 0, "patch_label": "0.0z", "rank_label": "测试分段",
                 "tactics_set": s, "aperture": {}, "total": 1_000_000, "last_updated": "2026-01-01T00:00:00Z",
                 "fetched_at": "2026-01-01T00:00:00Z", "sources": {}},
        "official": {"units": {i: {"name": name[i], "cost": 1 + j % 5, "traits": [trait_names[t] for t in traits[i]]} for j, i in enumerate(ids)},
                     "traits": trait_names},
        "unit_stats": {i: {k: v for k, v in stats(rnd.randint(1000, 50000)).items() if k != "won"} for i in ids},
        "champions": [{"character_record": {"character_id": i, "display_name": name[i],
                                            "squareIconPath": "/lol-game-data/assets/ASSETS/Characters/Fixture/%s.png" % i,
                                            "traits": [{"name": trait_names[t], "id": t} for t in traits[i]]}} for i in ids],
        "items": [{"nameId": it, "name": "测试装备%d" % k, "squareIconPath": "/lol-game-data/assets/ASSETS/Maps/TFT/Icons/Items/Fixture%d.png" % k}
                  for k, it in enumerate(items)],
        "unit_builds": {i: {"itemPairs": [dict(stats(rnd.randint(100, 900)), items=rnd.sample(items, 2))],
                            "itemTrios": [dict(stats(rnd.randint(100, 900)), items=rnd.sample(items, 3))],
                            "itemCountData": [dict(stats(rnd.randint(100, 9000)), id=k) for k in range(4)]} for i in ids},
        "comps": comps,
        "craft": {"components": [[p, "测试散件%d" % k, ICONS + "part%d.png" % k] for k, p in enumerate(parts)],
                  "recipes": [{"api": "TFT_Item_Recipe_%s_%s" % (a, b), "name": "测试成装 %s+%s" % (a, b), "icon": ICONS + "recipe.png",
                               "desc": "测试", "emblem": False, "pair": [a, b]}
                              for x, a in enumerate(parts) for b in parts[x:]]},
    }
