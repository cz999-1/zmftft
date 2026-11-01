#!/usr/bin/env python3
"""抓取全部数据源，存成快照 data/<set>/<patch>.json；页面只从快照渲染 (stdlib only).
用法: python3 fetch_data.py [--no-cache | --offline]
原始响应缓存在 cache/raw/（已 gitignore，6 小时内复用）；快照只保留页面用到的字段。
--offline 不联网，用 cache/raw/ 里已有的原始响应（不论新旧）重建快照。"""
import argparse, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from generate_tft_table import (fetch, fetch_json, fetch_next_data, load_unit_builds, detect_set_filter, set_number,
    official_units, official_traits, TACTICS, CDRAGON)
import craft

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "cache" / "raw"
DATA = ROOT / "data"
MAX_AGE = 6 * 3600
TOP_BUILDS = 3  # 每个英雄保留的二/三件装组合数（按 tactics.tools 原顺序）


def cached(name, fn, refresh=False, offline=False):
    """读 cache/raw/<name>.json；没有、过期或 refresh 时调用 fn() 重新抓取并写回（offline 时从不抓取）。"""
    p = RAW / (name + ".json")
    if offline:
        if not p.exists():
            raise SystemExit("--offline: 缺少 %s，先联网运行一次 python3 fetch_data.py" % p)
    elif refresh or not p.exists() or time.time() - p.stat().st_mtime >= MAX_AGE:
        RAW.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(fn(), ensure_ascii=False), encoding="utf-8")
    return json.loads(p.read_text(encoding="utf-8"))


def units_page():
    """tactics.tools 英雄页：数据 + 页面上写明的筛选条件（如「排位模式 钻石以上 18.5c」），同一次请求。"""
    html = fetch(TACTICS + "/zh/units").decode("utf-8", "replace")
    nd = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)))
    m = re.search(r"排位模式 (\S+) (\d+\.\d+[a-z]?) ", text)
    return {"pageProps": nd["props"]["pageProps"], "rank_label": m.group(1) if m else None, "patch_label": m.group(2) if m else None}


def collect_raw(refresh=False, offline=False):
    """每个源只请求一次；返回原始响应（各取页面用到的那一层）和最早一份的抓取时间。"""
    get = lambda name, fn: cached(name, fn, refresh, offline)
    raw = {"units": get("tt_units_page", units_page)}
    raw["builds"] = get("tt_unit_builds", lambda: load_unit_builds(list(raw["units"]["pageProps"]["statsData"]["units"]), workers=12))
    raw["groups"] = get("tt_comps", lambda: fetch_next_data(TACTICS + "/zh/team-compositions")["props"]["pageProps"]["initialData"]["groups"])
    raw["champs"] = get("cd_champions", lambda: fetch_json(CDRAGON + "/zh_cn/v1/tftchampions.json"))
    raw["items"] = get("cd_items", lambda: fetch_json(CDRAGON + "/zh_cn/v1/tftitems.json"))
    raw["cd_tft"] = get("cd_tft", craft.fetch)
    names = ("tt_units_page", "tt_unit_builds", "tt_comps", "cd_champions", "cd_items", "cd_tft")
    raw["fetched_at"] = min((RAW / (n + ".json")).stat().st_mtime for n in names)
    return raw


def item_keys(nid):
    """generate_tft_table.build_item_meta 会为一个装备登记的全部查找键。"""
    keys = {nid}
    for p in ("TFT_Item_", "TFT5_Item_", "TFT7_Item_", "TFT9_Item_", "TFT11_Item_",
              "TFT14_Item_", "TFT15_Item_", "TFT16_Item_", "TFT17_Item_", "TFT18_Item_", "DA_Item_"):
        if nid.startswith(p):
            keys |= {nid[len(p):], "DA_" + nid[len(p):]}
            break
    return keys


def make_snapshot(raw):
    """从原始响应取出页面用到的字段。"""
    pp = raw["units"]["pageProps"]; sd = pp["statsData"]; ap = pp.get("aperture") or {}
    champs = raw["champs"]
    mk = detect_set_filter(champs); set_no = set_number(mk)
    f = [c for c in champs if mk.lower() in ((c.get("character_record") or {}).get("squareIconPath") or "").lower()]
    if len(f) >= 20: champs = f
    builds = {u: {"itemPairs": b["itemPairs"][:TOP_BUILDS], "itemTrios": b["itemTrios"][:TOP_BUILDS], "itemCountData": b["itemCountData"]}
              for u, b in raw["builds"].items()}
    used = {i for b in builds.values() for k in ("itemPairs", "itemTrios") for x in b[k]
            for i in (x["items"] if isinstance(x["items"], list) else [x["items"]])}
    used = {k for i in used for k in (i, i.replace("DA_", ""), i.replace("DA_", "").replace("Artifact_", ""))}
    comps = []
    for gr in raw["groups"]:
        for v in gr.values():
            if isinstance(v, dict): comps += v.get("comps") or []
    components, table = craft.build(raw["cd_tft"], set_no)
    return {
        "meta": {"set": set_no, "set_marker": mk, "patch": (ap.get("patch") or {}).get("_0", "?"), "patch_label": raw["units"]["patch_label"],
                 "rank_label": raw["units"]["rank_label"], "aperture": ap, "total": sd["totalEntries"],
                 "last_updated": datetime.fromtimestamp(sd["lastUpdated"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if sd.get("lastUpdated") else None,
                 "fetched_at": datetime.fromtimestamp(raw["fetched_at"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "sources": {"tactics.tools": [TACTICS + "/zh/units", TACTICS + "/zh/units/<id>", TACTICS + "/zh/team-compositions"],
                             "community_dragon": [CDRAGON + "/zh_cn/v1/tftchampions.json", CDRAGON + "/zh_cn/v1/tftitems.json", craft.CD_JSON]}},
        "official": {"units": official_units(raw["cd_tft"], set_no), "traits": official_traits(raw["cd_tft"], set_no)},
        "unit_stats": {u: {k: s.get(k) for k in ("count", "place", "top4")} for u, s in sd["units"].items()},
        "champions": [{"character_record": {k: (c.get("character_record") or {}).get(k) for k in ("character_id", "display_name", "squareIconPath", "traits")}} for c in champs],
        "items": [{k: it.get(k) for k in ("nameId", "name", "squareIconPath")} for it in raw["items"] if item_keys(it.get("nameId") or "") & used],
        "unit_builds": builds,
        "comps": comps,
        "craft": {"components": components, "recipes": [dict(v, pair=list(k)) for k, v in table.items()]},
    }


def snapshot_path(snap):
    m = snap["meta"]
    return DATA / ("set%d" % m["set"]) / ("%s.json" % (m["patch_label"] or m["patch"]))


def save(snap):
    p = snapshot_path(snap)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cache", action="store_true", help="忽略 cache/raw/ 重新抓取")
    ap.add_argument("--offline", action="store_true", help="不联网，用 cache/raw/ 已有的原始响应重建快照")
    a = ap.parse_args()
    p = save(make_snapshot(collect_raw(a.no_cache, a.offline)))
    print("snapshot →", p, p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
