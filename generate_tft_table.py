#!/usr/bin/env python3
"""Generate Chinese TFT trait x position HTML with 2/3-item builds.

Live data: tactics.tools + Community Dragon (zh_CN). Stdlib only.

  python3 generate_tft_table.py
  python3 generate_tft_table.py --out out.html
"""
from __future__ import annotations

import argparse
import time
import concurrent.futures
import html as htmlmod
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (compatible; TFT-Table-Generator/1.0)"}
TACTICS = "https://tactics.tools"
CDRAGON = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global"

CD_TFT = "https://raw.communitydragon.org/latest/cdragon/tft/zh_cn.json"
SETS = Path(__file__).resolve().parent / "sets"
COST_COLORS = {1: "#9aa4af", 2: "#11b288", 3: "#207ac7", 4: "#c440c4", 5: "#ffb93b"}
NO_CLASS = "（无职业/特殊）"
# Costs, names and trait lists come from Community Dragon. Trait types (class / origin), row order,
# positions and the Lux forms to hide are not in any official data: they are hand-written per set
# in sets/set<N>.json (the 65 Set 18 costs once hand-written here all matched Community Dragon 16.21).


def load_manual(set_no):
    """sets/set<N>.json: hand-written trait types, row order, positions, hidden ids, renames."""
    p = SETS / ("set%d.json" % set_no)
    if not p.exists():
        raise SystemExit("missing %s: annotate the new set's trait types and positions first (README: Set 迁移清单)" % p)
    return json.loads(p.read_text(encoding="utf-8"))

def official_units(cd_tft, set_no):
    """Community Dragon cdragon/tft/zh_cn.json -> {apiName: {"name", "cost", "traits"}} for one set."""
    return {c["apiName"]: {"name": c["name"], "cost": c["cost"], "traits": c["traits"]} for c in cd_tft["sets"][str(set_no)]["champions"]}

def official_traits(cd_tft, set_no):
    return {t["apiName"]: t["name"] for t in cd_tft["sets"][str(set_no)]["traits"]}

def row_orders(manual, trait_names):
    """Matrix row order: the manual file's order, with the official Chinese trait names."""
    return ([trait_names.get(t, n) for t, n in manual["classes"]] + [NO_CLASS],
            [trait_names.get(t, n) for t, n in manual["origins"]])


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_json(url):
    return json.loads(fetch(url).decode("utf-8", "replace"))

def fetch_next_data(url):
    html = fetch(url).decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("No __NEXT_DATA__ in " + url)
    return json.loads(m.group(1))

def cdragon_asset_url(square_icon_path):
    if not square_icon_path:
        return ""
    if "/ASSETS/" in square_icon_path:
        rel = square_icon_path.split("/ASSETS/", 1)[-1]
    else:
        rel = square_icon_path.split("/assets/", 1)[-1]
    return CDRAGON + "/default/assets/" + rel.lower()

ITEM_PREFIX = re.compile(r"(?:TFT\d*|DA)_Item_")  # TFT_Item_, TFT5_Item_ … TFT18_Item_, a later set's, DA_Item_

def item_keys(nid):
    """Lookup keys one item registers: its id, and the id without the set's item prefix (bare and DA_)."""
    m = ITEM_PREFIX.match(nid)
    return [nid] + ([nid[m.end():], "DA_" + nid[m.end():]] if m else [])

def build_item_meta(items_zh):
    meta = {}
    for it in items_zh:
        for key in item_keys(it.get("nameId") or ""):
            if key and key not in meta:
                meta[key] = {"name": it.get("name") or "", "icon": it.get("squareIconPath") or ""}
    return meta

def item_cn(meta, iid):
    for key in (iid, iid.replace("DA_", ""), iid.replace("DA_", "").replace("Artifact_", "")):
        if key in meta:
            return meta[key]["name"]
    return iid.replace("DA_", "").replace("Artifact_", "")

def item_icon(meta, iid):
    for key in (iid, iid.replace("DA_", "")):
        if key in meta and meta[key].get("icon"):
            return cdragon_asset_url(meta[key]["icon"])
    return ""

def load_unit_builds(unit_ids, workers=12):
    def one(uid, tries=4):
        url = TACTICS + "/zh/units/" + uid.lower()
        err = None
        for t in range(tries):  # one request per try; sleep only after a failure
            try:
                ud = fetch_next_data(url)["props"]["pageProps"].get("unitData") or {}
                return uid, {"itemPairs": ud.get("itemPairs") or [], "itemTrios": ud.get("itemTrios") or [],
                             "starLevelData": ud.get("starLevelData") or [], "itemCountData": ud.get("itemCountData") or []}, None
            except Exception as e:
                err = e
                if t < tries - 1:
                    time.sleep(1 + t)
        return uid, None, str(err)
    out, errs = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for uid, data, err in ex.map(lambda u: one(u), unit_ids):
            if err:
                errs.append((uid, err))
            else:
                out[uid] = data
    if errs:
        print("warning: %d unit pages failed (e.g. %s)" % (len(errs), errs[0]))
    return out

# Removed (2026-11-01, docs in README): best_trait_perf (羁绊强度 = minimum of noisy tier averages),
# carry_tags (阵眼 = 3★/3-item 1st-place lift) and the 站位结论 verdict. All three read final-board
# results that need a long game to reach, so they show who was already winning, not what wins.

def build_roster(champs_zh, unit_builds, costs, manual):
    """costs: {character_id: cost} from official data; manual: sets/set<N>.json (load_manual)."""
    hide = {i for i, _ in manual["hide"]}
    class_ids = {t for t, _ in manual["classes"]}
    roster = []
    for item in champs_zh:
        cr = item.get("character_record") or {}
        path = cr.get("squareIconPath") or ""
        cid = cr.get("character_id") or ""
        if cid in hide:
            continue
        name = manual["rename"].get(cid) or cr.get("display_name") or ""
        tr = cr.get("traits") or []
        traits = [t.get("name") for t in tr]
        classes = [t.get("name") for t in tr if t.get("id") in class_ids]
        origins = [t.get("name") for t in tr if t.get("id") not in class_ids]
        cost = costs.get(cid)
        pos = (manual["positions"].get(cid) or [None])[0]
        builds = unit_builds.get(cid) or {}
        pairs = builds.get("itemPairs") or []
        trios = builds.get("itemTrios") or []
        roster.append({
            "id": cid, "name": name, "cost": cost, "pos": pos,
            "classes": classes, "origins": origins, "traits": traits,
            "icon": cdragon_asset_url(path),
            "top2": pairs[0] if pairs else None,
            "top3": trios[0] if trios else None,
            "item_counts": builds.get("itemCountData") or [],  # boards by # of finished items the unit holds
        })
    return roster

def render_build(meta, build, label):
    if not build:
        return '<div class="build emptyb">%s —</div>' % htmlmod.escape(label)
    ids = build["items"] if isinstance(build["items"], list) else [build["items"]]
    won, place = build.get("won"), build.get("place")
    icons = "".join(
        '<img class="ii" src="%s" alt="%s" title="%s" loading="lazy">' % (
            htmlmod.escape(item_icon(meta, i)), htmlmod.escape(item_cn(meta, i)), htmlmod.escape(item_cn(meta, i)))
        for i in ids
    )
    names = "+".join(item_cn(meta, i) for i in ids)
    bs = ("%.0f%%·%.1f" % (won, place)) if won is not None and place is not None else ""
    return '<div class="build" title="%s"><span class="bl">%s</span>%s<span class="bs">%s</span></div>' % (
        htmlmod.escape(names), htmlmod.escape(label), icons, htmlmod.escape(bs))

def render_unit(meta, r):
    cost = r["cost"] if r["cost"] else "?"
    col = COST_COLORS.get(r["cost"], "#666")
    tags = "".join('<span class="tag">%s</span>' % htmlmod.escape(t) for t in r["traits"])
    return (
        '<div class="u"><span class="cost" style="background:%s">%s</span>'
        '<img class="face" src="%s" alt="%s" loading="lazy" onerror="this.style.opacity=.2">'
        '<span class="n">%s</span><div class="tags">%s</div>%s%s</div>'
    ) % (
        col, cost, htmlmod.escape(r["icon"]), htmlmod.escape(r["name"]),
        htmlmod.escape(r["name"]), tags,
        render_build(meta, r["top2"], "二"), render_build(meta, r["top3"], "三"),
    )

def render_cell(meta, units):
    if not units:
        return '<td class="empty">—</td>'
    seen, uniq = set(), []
    for u in sorted(units, key=lambda x: (x["cost"] or 9, x["name"])):
        if u["id"] in seen:
            continue
        seen.add(u["id"]); uniq.append(u)
    return '<td><div class="cell">%s</div></td>' % "".join(render_unit(meta, u) for u in uniq)

def group_by(roster, key):
    g = defaultdict(lambda: {"front": [], "mid": [], "back": []})
    for r in roster:
        tags = r[key]
        if not tags and key == "classes":
            g[NO_CLASS][r["pos"]].append(r)
            continue
        for t in tags:
            g[t][r["pos"]].append(r)
    return g

def table_rows(meta, grouped, order):
    rows, used = [], set()
    for name in order:
        if name not in grouped:
            continue
        g = grouped[name]
        if not (g["front"] or g["mid"] or g["back"]):
            continue
        used.add(name)
        rows.append('<tr><th class="origin">%s</th>%s%s%s</tr>' % (
            htmlmod.escape(name), render_cell(meta, g["front"]), render_cell(meta, g["mid"]), render_cell(meta, g["back"])))
    for name, g in sorted(grouped.items()):
        if name in used or not (g["front"] or g["mid"] or g["back"]):
            continue
        rows.append('<tr><th class="origin">%s</th>%s%s%s</tr>' % (
            htmlmod.escape(name), render_cell(meta, g["front"]), render_cell(meta, g["mid"]), render_cell(meta, g["back"])))
    return "".join(rows)

CSS = """
:root { --bg:#0f1419; --card:#1a222c; --text:#e8eef4; --muted:#9aa4af; --line:#2a3542; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); padding:20px; }
h1 { font-size:22px; margin:0 0 6px; } h2 { font-size:17px; margin:28px 0 12px; }
.sub { color:var(--muted); font-size:13px; margin-bottom:14px; }
table { width:100%; border-collapse:collapse; background:var(--card); border-radius:12px; overflow:hidden; margin-bottom:8px; }
th, td { border:1px solid var(--line); vertical-align:top; padding:10px; } th { background:#121820; font-weight:600; }
.origin { white-space:nowrap; width:100px; text-align:left; font-size:14px; }
.cell { display:flex; flex-wrap:wrap; gap:10px; }
.u { display:flex; flex-direction:column; align-items:center; width:108px; gap:3px; position:relative; background:#121820; border-radius:10px; padding:8px 6px 6px; }
.face { width:48px; height:48px; border-radius:8px; object-fit:cover; background:#0b0f14; }
.n { font-size:12px; text-align:center; line-height:1.2; }
.cost { position:absolute; top:4px; left:8px; font-size:11px; font-weight:700; color:#111; border-radius:4px; padding:1px 5px; z-index:1; }
.tags { display:flex; flex-wrap:wrap; gap:2px; justify-content:center; min-height:16px; }
.tag { font-size:9px; background:#243041; color:#c5d0db; border-radius:3px; padding:1px 3px; }
.build { display:flex; align-items:center; gap:2px; flex-wrap:wrap; justify-content:center; font-size:9px; color:var(--muted); width:100%; }
.bl { color:#7f8b98; margin-right:2px; } .bs { margin-left:2px; white-space:nowrap; }
.ii { width:16px; height:16px; border-radius:3px; background:#0b0f14; }
.empty { color:var(--muted); text-align:center; } .emptyb { opacity:.5; }
.legend { display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 16px; font-size:12px; color:var(--muted); }
.dot { width:14px; height:14px; border-radius:3px; display:inline-block; }
.note { font-size:12px; color:var(--muted); margin-top:8px; }
"""

def render_html(roster, item_meta, patch_label, class_order, origin_order):
    by_class = group_by(roster, "classes")
    by_origin = group_by(roster, "origins")
    return """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>TFT 羁绊站位 + 装备表（%s）</title>
<style>%s</style>
</head>
<body>
<h1>TFT 羁绊 × 站位 + 装备</h1>
<p class="sub">%s · 数据来自 tactics.tools + Community Dragon · 二/三件装为出场最多组合（吃鸡率%% · 平均名次；吃鸡率全体基线 12.5%%）· 站位为人工标注</p>
<div class="legend">
  <span><i class="dot" style="background:#9aa4af"></i>1费</span>
  <span><i class="dot" style="background:#11b288"></i>2费</span>
  <span><i class="dot" style="background:#207ac7"></i>3费</span>
  <span><i class="dot" style="background:#c440c4"></i>4费</span>
  <span><i class="dot" style="background:#ffb93b"></i>5费</span>
  <span>标签=全部羁绊 · 「二」「三」=二件装 / 三件装</span>
</div>
<h2>职业羁绊（特质）× 前 / 中 / 后排</h2>
<table>
<thead><tr><th>职业羁绊</th><th>前排</th><th>中排</th><th>后排</th></tr></thead>
<tbody>%s</tbody>
</table>
<h2>种族羁绊 × 前 / 中 / 后排</h2>
<table>
<thead><tr><th>种族羁绊</th><th>前排</th><th>中排</th><th>后排</th></tr></thead>
<tbody>%s</tbody>
</table>
<p class="sub" style="margin-top:20px">由 generate_tft_table.py 自动生成。换版本后重新运行即可刷新。</p>
</body>
</html>
""" % (
        htmlmod.escape(patch_label), CSS, htmlmod.escape(patch_label),
        table_rows(item_meta, by_class, class_order),
        table_rows(item_meta, by_origin, origin_order),
    )

def detect_set_filter(champs_zh):
    counts = defaultdict(int)
    for item in champs_zh:
        path = (item.get("character_record") or {}).get("squareIconPath") or ""
        m = re.search(r"(Set\d+|TFT_Set\d+)", path, re.I)
        if m:
            counts[m.group(1)] += 1
    if not counts:
        raise SystemExit("cannot detect the current set from Community Dragon icon paths; pass --set")
    return max(counts.items(), key=lambda x: x[1])[0]

def set_number(set_marker):
    return int(re.search(r"(\d+)$", set_marker).group(1))

def main():
    ap = argparse.ArgumentParser(description="Generate TFT Chinese trait x position HTML table")
    ap.add_argument("--out", default="tft-traits-items.html")
    ap.add_argument("--costs", help="optional JSON map character_id -> cost, overrides Community Dragon")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--set", dest="set_marker", default="")
    args = ap.parse_args()

    print("1/5 fetching tactics.tools units page…")
    units_pp = fetch_next_data(TACTICS + "/zh/units")["props"]["pageProps"]
    stats_data = units_pp["statsData"]
    unit_ids = list(stats_data["units"].keys())
    patch =(units_pp.get("aperture") or {}).get("patch") or {}
    patch_label = "tactics.tools patch=%s · %d units" % (patch.get("_0", "?"), len(unit_ids))

    print("2/5 fetching Community Dragon zh champions + items…")
    champs_zh = fetch_json(CDRAGON + "/zh_cn/v1/tftchampions.json")
    items_zh = fetch_json(CDRAGON + "/zh_cn/v1/tftitems.json")
    item_meta = build_item_meta(items_zh)
    set_marker = args.set_marker or detect_set_filter(champs_zh)
    print("   set marker:", set_marker)
    filtered = []
    for item in champs_zh:
        path = ((item.get("character_record") or {}).get("squareIconPath") or "")
        if set_marker.lower() in path.lower():
            filtered.append(item)
    if len(filtered) >= 20:
        champs_zh = filtered
        print("   champions in set:", len(champs_zh))
    set_no = set_number(set_marker)
    cd_tft = fetch_json(CD_TFT)
    costs = {k: v["cost"] for k, v in official_units(cd_tft, set_no).items()}
    if args.costs:
        costs.update(json.loads(Path(args.costs).read_text(encoding="utf-8")))
    manual = load_manual(set_no)

    print("3/5 fetching item pairs/trios for %d units…" % len(unit_ids))
    unit_builds = load_unit_builds(unit_ids, workers=args.workers)

    print("4/5 building roster…")
    roster = build_roster(champs_zh, unit_builds, costs, manual)
    missing = [r["name"] for r in roster if not r["cost"] or not r["pos"]]
    if missing:
        print("   missing cost or position (%d): %s" % (len(missing), ", ".join(missing[:12])))
        print("   tip: pass --costs costs.json, or add positions to sets/set%d.json" % set_no)

    print("5/5 writing HTML…")
    doc = render_html(roster, item_meta, patch_label, *row_orders(manual, official_traits(cd_tft, set_no)))
    out = Path(args.out)
    out.write_text(doc, encoding="utf-8")
    print("done → %s (%d bytes, %d champions)" % (out.resolve(), out.stat().st_size, len(roster)))

if __name__ == "__main__":
    main()
