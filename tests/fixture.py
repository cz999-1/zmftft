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
                     "traits": trait_names,
                     "trait_meta": {t: {"breaks": [2, 4, 6], "icon": ICONS + "trait%d.png" % k} for k, t in enumerate(trait_names)}},
        "comp_groups": comp_groups(comps, traits, items, rnd, s),
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


def comp_groups(comps, traits, items, rnd, set_no):
    """One block per comp group, consistent with the group's variants (the fields of checks.GROUP_FIELDS).
    The heaviest variant's first unit is 3-star on 60% of the group's boards (the strip's major badge),
    its second on 30% (minor badge), the others never; the first two units are the carries."""
    out = []
    for g in sorted({c["group"] for c in comps}):
        vs = [c for c in comps if c["group"] == g]
        top = max(vs, key=lambda c: c["count"])
        n = 2 * sum(c["count"] for c in vs)
        dist = [n // 8] * 8
        dist[3] += n - sum(dist)
        lv = [[7, n // 4], [8, n // 2], [9, n - n // 4 - n // 2]]
        units = sorted({u for c in vs for u in c["units"]})
        rows = []
        for u in units:
            share3 = 0.6 if u == top["units"][0] else 0.3 if u == top["units"][1] else 0.0
            rows += [[u, 2, int(n * (0.85 - share3)), 4.4]] + ([[u, 3, int(n * share3), 3.1]] if share3 else [])
        carries = top["units"][:2]
        unit_items = [{"unitId": u, "itemId": items[(k + j) % len(items)], "count": 900 - 100 * j, "place": 4.1,
                       "top4": 450, "won": 110} for k, u in enumerate(carries) for j in range(4)]
        pairs = [{"unitId": u, "items": [items[k], items[k + 1]], "count": 600, "place": 4.0, "top4": 300, "won": 80}
                 for k, u in enumerate(carries)]
        tcount = {}
        for u in top["units"]:
            for t in traits[u]:
                tcount[t] = tcount.get(t, 0) + 1
        trs = [[t, 1, int(n * 0.9), 4.3] for t, k in sorted(tcount.items()) if k >= 2]
        trs += [[t, 1, int(n * 0.2), 4.6] for t, k in sorted(tcount.items()) if k < 2][:1]  # rare: below the chip share
        out.append({"group": g, "count": n, "place": round(rnd.uniform(3.8, 4.8), 3), "top4": sum(dist[:4]),
                    "win": dist[0], "code": "02%sTFTSet%d" % ("%03x" % g * 8, set_no),
                    "placementDistribution": dist, "levels": [[lvl, k, round(k * (12.5 - lvl))] for lvl, k in lv],
                    "carryUnits": [[u, 2.9 - k] for k, u in enumerate(carries)], "units": rows,
                    "unitItemCounts": {"%s-%d" % (u, k): [n // 4, 4.4] for u in carries for k in range(4)},
                    "traits": trs, "unitItems": unit_items, "unitItemPairs": pairs})
    return out


def riot_comps_doc(snap, seed=3):
    """A made-up tft-lab comps export (schema tftlab-comps/1): families from the snapshot's comp groups,
    cells for all but the last family. Invented numbers, no identifiers."""
    rnd = random.Random(seed)
    groups = {}
    for c in snap["comps"]:
        groups.setdefault(c["group"], []).append(c)
    fams = [{"id": g, "units": max(cs, key=lambda c: c["count"])["units"], "variants": len(cs),
             "tt_count": sum(c["count"] for c in cs)} for g, cs in sorted(groups.items())]
    items = [it["nameId"] for it in snap["items"]]
    cells = []
    for f in fams[:-1]:
        n = rnd.randint(300, 1500)
        pm = round(rnd.uniform(3.6, 5.0), 3)
        units = []
        for k, u in enumerate(f["units"][:5]):
            units.append({"unit": u, "n": n - 10 * k, "presence": round(1 - 0.01 * k, 4),
                          "stars": {"1": 5, "2": n - 60 - 10 * k, "3": 55}, "star3": round(55 / n, 4),
                          "star3_ci95": [round(40 / n, 4), round(70 / n, 4)],
                          "items_per_board": round(2.5 - 0.5 * k, 3), "item_share": round(0.3 - 0.05 * k, 4),
                          "item_share_ci95": [round(0.28 - 0.05 * k, 4), round(0.32 - 0.05 * k, 4)],
                          "full_rate": round(0.8 - 0.1 * k, 4),
                          "combos": [{"items": items[k:k + 3], "n": 40, "share": 0.1, "place_mean": 4.2,
                                      "place_ci95": [3.8, 4.6]}] if k < 2 else []})
        cells.append({"family": f["id"], "n_boards": n, "n_matches": n - 5, "pick_rate": round(n / 8000, 4),
                      "pick_ci95": [round(n / 8000 - 0.01, 4), round(n / 8000 + 0.01, 4)],
                      "place_mean": pm, "place_ci95": [round(pm - 0.1, 3), round(pm + 0.1, 3)],
                      "top1": 0.14, "top1_ci95": [0.12, 0.16], "top4": 0.55, "top4_ci95": [0.52, 0.58],
                      "placement_hist": [0.14, 0.14, 0.14, 0.13, 0.12, 0.12, 0.11, 0.1],
                      "levels": [{"level": 8, "n": n // 2, "share": 0.5}, {"level": 9, "n": n - n // 2, "share": 0.5}],
                      "traits": [{"trait": t, "active_share": 0.9, "tiers": {"1": n - 50, "2": 50}}
                                 for t in list(snap["official"]["traits"])[:2]],
                      "units": units})
    return {"schema": "tftlab-comps/1", "generated_utc": "2026-11-03T00:00:00Z", "publishable": False,
            "publishable_note": "fixture", "grade": "C", "label_zh": "自采 Riot 对局（测试）", "estimand": "fixture",
            "params": {"min_n": 20, "min_overlap": 6, "combo_min_n": 20, "trait_share_min": 0.5, "n_boot": 50,
                       "seed": seed},
            "population": {"set": snap["meta"]["set"], "patch": "0.0", "window_utc": ["2026-10-22", "2026-11-04"],
                           "queue_id": 1100, "hosts": ["americas"], "platforms": ["NA1"], "matches": 1000,
                           "boards": 8000, "known_rank_boards": {"MASTER": 900, "CHALLENGER": 100},
                           "rank_note": "fixture"},
            "comp_source": {"file": "snap.json", "patch_label": snap["meta"]["patch_label"],
                            "n_comps": len(snap["comps"]), "n_families": len(fams)},
            "families": fams,
            "baseline": {"n_boards": 8000, "n_matches": 1000, "place_mean": 4.5, "top1": 0.125, "top4": 0.5},
            "unmatched": {"n_boards": 2100, "share": 0.2625},
            "cells": cells,
            "threshold_report": {"units_total": 40, "units_kept": 15, "units_suppressed": 25,
                                 "combos_total": 30, "combos_kept": 6, "combos_suppressed": 24,
                                 "matched_boards": 5900, "unmatched_boards": 2100}}


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


def riot_synergy_doc(snap, manual, seed=2):
    """A made-up tft-lab synergy export (schema tftlab-synergy/1): trait pairs over the manual's
    apiNames with invented numbers; one thin pair (n < 1000) and one class x class pair that the
    page must count but not render. No identifiers."""
    rnd = random.Random(seed)
    oris = [t for t, _ in manual["origins"]]
    clss = [t for t, _ in manual["classes"]]

    def pair(a, b, n):
        a, b = sorted((a, b))
        pm = round(rnd.uniform(3.2, 5.2), 3)
        wr = round(rnd.uniform(0.06, 0.3), 4)
        lf = round(rnd.uniform(-0.6, 0.6), 3)
        return {"a": a, "b": b, "n_boards": n, "n_matches": max(1, n * 7 // 8),
                "place_mean": pm, "place_ci95": [round(pm - 0.2, 3), round(pm + 0.2, 3)],
                "win_rate": wr, "win_ci95": [round(max(0.0, wr - 0.03), 4), round(wr + 0.03, 4)],
                "lift": lf, "lift_ci95": [round(lf - 0.15, 3), round(lf + 0.15, 3)]}

    pairs = [pair(oris[0], oris[1], 2400), pair(oris[1], oris[2], 640),
             pair(oris[0], clss[0], 1800), pair(oris[2], clss[1], 900),
             pair(clss[0], clss[1], 700)]
    traits = {t: {"en": t, "n_boards": 5000, "n_matches": 4000, "place_mean": 4.4, "win_rate": 0.13}
              for p in pairs for t in (p["a"], p["b"])}
    return {"schema": "tftlab-synergy/1", "generated_utc": "2026-11-01T00:00:00Z", "publishable": False,
            "publishable_note": "fixture", "grade": "C", "label_zh": "自采 Riot 对局（测试）", "estimand": "fixture",
            "params": {"activation": "tier_current >= 1", "min_n": 500, "n_boot": 50, "seed": seed},
            "population": {"set": snap["meta"]["set"], "patch": "0.0", "window_utc": ["2026-10-22", "2026-11-04"],
                           "queue_id": 1100, "hosts": ["americas"], "platforms": ["NA1"], "matches": 4000,
                           "boards": 32000, "known_rank_boards": {"MASTER": 900}, "rank_note": "fixture"},
            "baseline": {"n_boards": 32000, "n_matches": 4000, "place_mean": 4.5, "place_ci95": [4.5, 4.5],
                         "win_rate": 0.125, "win_ci95": [0.125, 0.125]},
            "traits": traits, "pairs": pairs,
            "threshold_report": {"pairs_total": 600, "pairs_kept": 5, "pairs_suppressed": 595,
                                 "boards_in_suppressed_pairs": 40000, "note": "fixture"}}
