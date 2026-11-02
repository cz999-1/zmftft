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
        # two units of one class on top of the origin pair, so origin x class cells exist in the tests
        cls = classes[o % len(classes)][0]
        units = [i for i in roster if traits[i][1] in pair][:6]
        units += [i for i in roster if traits[i][0] == cls and i not in units][:2]
        n = rnd.randint(200, 5000)
        comps.append({"units": units, "count": n, "place": round(rnd.uniform(3, 6), 3), "top4": n // 2, "win": n // 8,
                      "spatItems": [], "extraTraits": [], "group": o % 4})
    parts = ["Part%d" % k for k in range(10)]
    return {
        "meta": {"set": s, "set_marker": "TFT_Set%d" % s, "patch": 0, "patch_label": "0.0z", "rank_label": "测试分段",
                 "tactics_set": s, "aperture": {}, "total": 1_000_000, "last_updated": "2026-01-01T00:00:00Z",
                 "fetched_at": "2026-01-01T00:00:00Z", "cdragon": {"latest_version": "16.21.0+fixture", "folder": "16.21"}, "sources": {}},
        "official": {"units": {i: {"name": name[i], "cost": 1 + j % 5, "traits": [trait_names[t] for t in traits[i]]} for j, i in enumerate(ids)},
                     "traits": trait_names},
        "unit_stats": {i: stats(rnd.randint(1000, 50000)) for i in ids},
        "champions": [{"character_record": {"character_id": i, "display_name": name[i],
                                            "squareIconPath": "/lol-game-data/assets/ASSETS/Characters/Fixture/%s.png" % i,
                                            "traits": [{"name": trait_names[t], "id": t} for t in traits[i]]}} for i in ids],
        "items": [{"nameId": it, "name": "测试装备%d" % k, "squareIconPath": "/lol-game-data/assets/ASSETS/Maps/TFT/Icons/Items/Fixture%d.png" % k}
                  for k, it in enumerate(items)],
        "unit_builds": {i: {"itemPairs": [dict(stats(rnd.randint(100, 900)), items=rnd.sample(items, 2))],
                            "itemTrios": [dict(stats(rnd.randint(100, 900)), items=rnd.sample(items, 3))],
                            "bestPair": dict(stats(rnd.randint(500, 900)), items=rnd.sample(items, 2)),
                            "bestTrio": dict(stats(rnd.randint(500, 900)), items=rnd.sample(items, 3)) if j % 7 else None,
                            "starLevelData": [dict(stats(rnd.randint(10, 9000)), id=k) for k in (1, 2, 3)],
                            "itemCountData": [dict(stats(rnd.randint(100, 9000)), id=k) for k in range(4)]} for j, i in enumerate(ids)},
        "comps": comps,
        "craft": {"components": [[p, "测试散件%d" % k, ICONS + "part%d.png" % k] for k, p in enumerate(parts)],
                  "recipes": [{"api": "TFT_Item_Recipe_%s_%s" % (a, b), "name": "测试成装 %s+%s" % (a, b), "icon": ICONS + "recipe.png",
                               "desc": "测试", "emblem": False, "pair": [a, b]}
                              for x, a in enumerate(parts) for b in parts[x:]]},
    }


def riot_doc(snap, seed=1):
    """A made-up tft-lab heroes export (schema tftlab-heroes/1) for the hover panel: families from
    the snapshot's comp groups, cells for the first few units. Invented numbers, no identifiers."""
    rnd = random.Random(seed)
    groups = {}
    for c in snap["comps"]:
        groups.setdefault(c["group"], []).append(c)
    fams = [{"id": g, "units": max(cs, key=lambda c: c["count"])["units"], "variants": len(cs),
             "tt_count": sum(c["count"] for c in cs)} for g, cs in sorted(groups.items())]
    units = {}
    for i in list(snap["unit_stats"])[:6]:
        cells = []
        for f in fams[:3]:
            n = rnd.randint(25, 400)
            pm = round(rnd.uniform(1.5, 5.5), 3)
            cells.append({"family": f["id"], "n_boards": n, "n_matches": n, "place_mean": pm,
                          "place_ci95": [round(pm - 0.4, 3), round(pm + 0.4, 3)],
                          "top1": 0.2, "top1_ci95": [0.1, 0.3], "top4": 0.7, "top4_ci95": [0.6, 0.8]})
        cells.sort(key=lambda c: c["place_mean"])
        units[i] = {"n_fielded": 500, "n_star3_full": sum(c["n_boards"] for c in cells) + 7,
                    "unmatched_boards": 3, "suppressed_cells": 1, "suppressed_boards": 7, "cells": cells}
    return {"schema": "tftlab-heroes/1", "generated_utc": "2026-11-01T00:00:00Z", "publishable": False,
            "publishable_note": "fixture", "grade": "C", "label_zh": "自采 Riot 对局（测试）", "estimand": "fixture",
            "params": {"min_n": 20, "min_overlap": 6, "star_min": 3, "completed_items_min": 3,
                       "n_boot": 50, "seed": seed, "rank_cells_by": "place_mean"},
            "population": {"set": snap["meta"]["set"], "patch": "0.0", "window_utc": ["2026-10-22", "2026-11-04"],
                           "queue_id": 1100, "hosts": ["americas"], "platforms": ["NA1"], "matches": 1000,
                           "boards": 8000, "known_rank_boards": {"MASTER": 900, "CHALLENGER": 100},
                           "rank_note": "fixture"},
            "comp_source": {"file": "snap.json", "patch_label": snap["meta"]["patch_label"],
                            "n_comps": len(snap["comps"]), "n_families": len(fams)},
            "families": fams, "units": units,
            "threshold_report": {"cells_total": 20, "cells_kept": 18, "cells_suppressed": 2,
                                 "boards_in_suppressed_cells": 14, "unmatched_boards": 18, "qualifying_boards": 900}}
