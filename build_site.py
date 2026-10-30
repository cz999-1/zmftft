#!/usr/bin/env python3
"""云顶攻略台 · zmftft — 生成单页站点 index.html (stdlib only).
用法: python3 build_site.py [--out index.html] [--no-cache]
依赖同目录 generate_tft_table.py 中的映射与工具函数。"""
import argparse, json, os, time, html as H
from collections import defaultdict
from pathlib import Path
from generate_tft_table import (fetch_json, fetch_next_data, TACTICS, CDRAGON, DEFAULT_COSTS, COST_COLORS,
    CLASS_ORDER, ORIGIN_ORDER, ZH_TRAIT_TO_TID, build_item_meta, item_cn, item_icon, load_unit_builds,
    best_trait_perf, build_roster, detect_set_filter, verdict_section, cdragon_asset_url, CLASS_SET)

import craft, synergy
CACHE = "/tmp/unit_items.json"
e = lambda s: H.escape(str(s))

def pcls(p):
    return "good" if p <= 3.8 else ("bad" if p >= 4.5 else "mid")

def face(u, size=""):
    col = COST_COLORS.get(u.get("cost"), "#666")
    return ('<span class="av %s" style="--c:%s" title="%s"><img src="%s" alt="%s" loading="lazy" '
            'onerror="this.style.opacity=.2"></span>') % (size, col, e(u["name"]), e(u["icon"]), e(u["name"]))

def build_html(meta, b, label):
    if not b:
        return '<div class="bd none"><b>%s</b>—</div>' % label
    ids = b["items"] if isinstance(b["items"], list) else [b["items"]]
    icons = "".join('<img src="%s" title="%s" alt="%s" loading="lazy">' % (e(item_icon(meta, i)), e(item_cn(meta, i)), e(item_cn(meta, i))) for i in ids)
    return '<div class="bd" title="%s"><b>%s</b>%s<span>%.0f%%</span></div>' % (
        e(" + ".join(item_cn(meta, i) for i in ids)), label, icons, b.get("won") or 0)

EYE_LBL = {"star": ("ey3", "阵眼—三星", "3★ 比 2★ 吃鸡率 +%.1fpp"), "item": ("eyi", "阵眼—装备", "满3件装比0件 吃鸡率 +%.1fpp")}
def eyes(tags):
    return "".join('<b class="eye %s" title="%s">%s</b>' % (EYE_LBL[k][0], EYE_LBL[k][2] % d, EYE_LBL[k][1]) for k, d in tags)

def card(meta, r, us, total):
    s = us.get(r["id"]) or {}
    stat = ""
    if s:
        stat = '<div class="st"><span class="%s">均名%.2f</span> · 前四%.0f%% · 选率%.1f%%</div>' % (
            pcls(s["place"]), s["place"], s["top4"], s["count"] / total * 100)
    tags = "".join("<i>%s</i>" % e(t) for t in r["traits"])
    return ('<div class="ch" data-k="%s" data-cost="%s" data-pos="%s" style="--c:%s"><div class="ph"><img src="%s" alt="%s" loading="lazy" onerror="this.style.opacity=.2">'
            '<em>%s</em></div><div class="nm">%s</div><div class="eyes">%s</div><div class="tg">%s</div>%s%s%s</div>') % (
        e(r["name"] + " " + " ".join(r["traits"])), r["cost"] or "", r.get("pos") or "",
        COST_COLORS.get(r["cost"], "#666"), e(r["icon"]), e(r["name"]),
        r["cost"] or "?", e(r["name"]), eyes(r.get("eye") or []), tags, stat, build_html(meta, r["top2"], "二"), build_html(meta, r["top3"], "三"))

def matrix(meta, roster, key, order, us, total, sid, title):
    g = defaultdict(lambda: {"front": [], "mid": [], "back": []})
    for r in roster:
        ts = r[key] or (["（无职业/特殊）"] if key == "classes" else [])
        for t in ts:
            g[t][r["pos"]].append(r)
    names = [n for n in order if n in g] + sorted(n for n in g if n not in order)
    cnt = lambda n: len({r["id"] for p in g[n].values() for r in p})
    solo = [n for n in names if key == "origins" and cnt(n) == 1]
    if solo:
        names = [n for n in names if n not in solo]
        sg = {"front": [], "mid": [], "back": []}
        for n in solo:
            for p in sg: sg[p] += g[n][p]
        g["单一英雄种族"] = sg; names.append("单一英雄种族")
        print("solo origins:", solo)
    rows = []
    for n in names:
        cols = []
        for p, lab in (("front", "前排"), ("mid", "中排"), ("back", "后排")):
            us_ = sorted(g[n][p], key=lambda x: (x["cost"] or 9, x["name"]))
            inner = "".join(card(meta, r, us, total) for r in us_) or '<div class="emp">—</div>'
            cols.append('<div class="col"><div class="cl">%s</div><div class="cards">%s</div></div>' % (lab, inner))
        sub = ('<small>%s</small>' % e("、".join(solo))) if n == "单一英雄种族" else ""
        rows.append(('<div class="trow"><div class="tn">%s<small>%d 名英雄</small>' + sub + '</div>%s</div>') % (
            e(n), len({r["id"] for p in g[n].values() for r in p}), "".join(cols)))
    return '<section id="%s"><h2>%s</h2><div class="legend">前排 / 中排 / 后排 · 均名颜色：<span class="good">≤3.8 强</span> <span class="bad">≥4.5 弱</span> · 二/三件装为出场最多组合（胜率%%） · <b class="eye ey3">阵眼—三星</b> 3★比2★吃鸡率≥+6pp（3★样本≥2000） <b class="eye eyi">阵眼—装备</b> 3件装比0件吃鸡率≥+5pp（样本≥3000）</div>%s</section>' % (sid, title, "".join(rows))

def main():
    try:  # optional: refresh Riot Data Dragon snapshot (no key needed); never blocks build
        from data.riot import ddragon
        snap = ddragon.snapshot()
        print(f"[riot] Data Dragon {snap['version']} Set {snap['set']}: {len(snap['champions'])} champs")
    except Exception as err:
        print("[riot] Data Dragon skipped:", err)
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    print("fetch units…")
    pp = fetch_next_data(TACTICS + "/zh/units")["props"]["pageProps"]
    sd = pp["statsData"]; us = sd["units"]; ts = sd.get("traits") or {}; total = sd["totalEntries"]
    patch = ((pp.get("aperture") or {}).get("patch") or {}).get("_0", "?")
    print("fetch cdragon…")
    champs = fetch_json(CDRAGON + "/zh_cn/v1/tftchampions.json")
    meta = build_item_meta(fetch_json(CDRAGON + "/zh_cn/v1/tftitems.json"))
    mk = detect_set_filter(champs)
    f = [c for c in champs if mk.lower() in ((c.get("character_record") or {}).get("squareIconPath") or "").lower()]
    if len(f) >= 20: champs = f
    # all units incl. Lux skins for comp icons
    allmap = {}
    for c in champs:
        cr = c.get("character_record") or {}
        allmap[cr.get("character_id")] = {"name": cr.get("display_name") or cr.get("character_id"),
            "icon": cdragon_asset_url(cr.get("squareIconPath")), "cost": DEFAULT_COSTS.get((cr.get("display_name") or "").split(" (")[0])}
    builds = None
    if not a.no_cache and os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < 6 * 3600:
        builds = json.load(open(CACHE))
        print("using cache", CACHE)
    if not builds:
        print("fetch unit pages…")
        builds = load_unit_builds(list(us), workers=12)
        json.dump(builds, open(CACHE, "w"))
    roster = build_roster(champs, builds, DEFAULT_COSTS)
    print("fetch comps…")
    groups = fetch_next_data(TACTICS + "/zh/team-compositions")["props"]["pageProps"]["initialData"]["groups"]
    comps = []
    for gr in groups:
        for v in gr.values():
            if isinstance(v, dict): comps += v.get("comps") or []
    seen, top = set(), []
    for c in sorted([c for c in comps if c["count"] >= 200], key=lambda c: c["place"]):
        k = tuple(sorted(c["units"]))
        if k in seen: continue
        seen.add(k); top.append(c)
        if len(top) == 6: break
    def U(i): return allmap.get(i) or {"name": i.replace("DA_", ""), "icon": "", "cost": None}
    rid0 = {r["id"]: r for r in roster}
    def cface(i):
        t = (rid0.get(i) or {}).get("eye") or []
        mk = "".join('<b class="eb %s">%s</b>' % (EYE_LBL[k][0], "3★" if k == "star" else "装") for k, _ in t)
        return '<span class="cf">%s%s</span>' % (face(U(i)), mk)
    def ceyes(c):
        out = []
        for i in c["units"]:
            for k, d in (rid0.get(i) or {}).get("eye") or []:
                out.append('<b class="eye %s" title="%s">%s · %s</b>' % (EYE_LBL[k][0], EYE_LBL[k][2] % d, e(U(i)["name"]), EYE_LBL[k][1]))
        return '<div class="eyes">%s</div>' % ("".join(out) or '<span class="hint">无明显阵眼</span>')
    comp_html = "".join(
        '<div class="cc"><div class="row">%s</div><div class="kv"><span class="%s">均名 <b>%.2f</b></span><span>前四 <b>%.0f%%</b></span><span>吃鸡 <b>%.0f%%</b></span><span>样本 <b>%d</b></span></div>%s<div class="sub">%s</div></div>' % (
            "".join(cface(i) for i in c["units"]), pcls(c["place"]), c["place"], c["top4"] / c["count"] * 100,
            c["win"] / c["count"] * 100, c["count"], ceyes(c), e("、".join(U(i)["name"] for i in c["units"]))) for c in top)
    rid = {r["id"]: r for r in roster}
    def ulist(items, fmt):
        return "".join('<li>%s<span class="ln">%s</span><span class="lv">%s</span></li>' % (face(r, "sm"), e(r["name"]), fmt(s)) for r, s in items)
    def is_lux(r):
        return r["name"] == "拉克丝" or r["name"].startswith("拉克丝")
    hid = [(rid[k], s) for k, s in us.items()
           if k in rid and s["count"] >= 800 and s["count"] / total < 0.04 and not is_lux(rid[k])]
    hid = sorted(hid, key=lambda x: x[1]["place"])[:8]
    star = [(rid[k], s) for k, s in us.items() if k in rid and s.get("starCount", 0) >= 80]
    star = sorted(star, key=lambda x: x[1]["place"] - x[1]["starPlace"], reverse=True)[:8]
    tr = []
    for zh, tid in ZH_TRAIT_TO_TID.items():
        b = best_trait_perf(ts, tid, 200)
        if b: tr.append((zh, b))
    tr = sorted(tr, key=lambda x: x[1]["place"])[:6]
    tr_html = "".join('<li><span class="tb">%s</span><span class="ln">%s %s 档 <small>%s</small></span><span class="lv %s">%.2f</span></li>' % (
        "职业" if zh in CLASS_SET else "种族", e(zh), e(b["tier"]), "样本%d" % b["count"], pcls(b["place"]), b["place"]) for zh, b in tr)
    insights = '''<section id="ins"><h2>洞察速览</h2><h3>🏆 本版本最强阵容 <small>样本≥200，按均名排序</small></h3><div class="grid comps">%s</div>
<div class="grid three"><div class="box"><h3>💎 冷门高胜率</h3><p class="hint">选率&lt;4%%、样本≥800，按均名</p><ul class="lst">%s</ul></div>
<div class="box"><h3>⭐ 三星价值</h3><p class="hint">均名 − 三星均名，越大越值得追三</p><ul class="lst">%s</ul></div>
<div class="box"><h3>🔗 羁绊强度</h3><p class="hint">各羁绊最佳激活档（样本≥200）</p><ul class="lst">%s</ul></div></div></section>''' % (
        comp_html,
        ulist(hid, lambda s: '<b class="%s">%.2f</b><small>选率%.1f%%</small>' % (pcls(s["place"]), s["place"], s["count"] / total * 100)),
        ulist(star, lambda s: '<b class="good">+%.2f</b><small>%.2f→%.2f</small>' % (s["place"] - s["starPlace"], s["place"], s["starPlace"])),
        tr_html)
    verdict = verdict_section(roster, ts, "origin")
    cls_html = matrix(meta, roster, "classes", CLASS_ORDER, us, total, "cls", "职业羁绊 × 站位")
    ori_html = matrix(meta, roster, "origins", ORIGIN_ORDER, us, total, "ori", "种族羁绊 × 站位")
    ver_html = '<section id="ver"><h2>站位结论（种族）</h2><div class="verdict">%s</div></section>' % verdict
    links = '<section id="go"><h2>去哪看</h2><div class="grid three">' + "".join(
        '<a class="box golink" href="%s"><h3>%s</h3><p class="hint">%s</p></a>' % x for x in PAGES[1:]) + '</div></section>'
    bodies = {"index.html": insights + links + "<script>var H={'#craft':'craft.html','#cls':'class.html','#ori':'origin.html','#ver':'origin.html#ver'};if(H[location.hash])location.replace(H[location.hash]);</script>", "class.html": cls_html, "origin.html": ori_html + ver_html, "synergy.html": "", "craft.html": craft.section()[0]}
    syn_mat, syn_pages = synergy.build(comps, roster, ORIGIN_ORDER, total, face, U, None)
    bodies["synergy.html"] = syn_mat
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); (out / "synergy").mkdir(exist_ok=True)
    for old in (out / "synergy").glob("*.html"): old.unlink()
    for fn, (t, body) in syn_pages.items():
        nav = "".join('<a href="../%s"%s>%s</a>' % (f, ' class="cur"' if f == "synergy.html" else "", tt) for f, tt, _ in PAGES)
        doc = TPL.replace("{{PATCH}}", e(patch)).replace("{{N}}", "%d" % total).replace("{{DATE}}", time.strftime("%Y-%m-%d %H:%M")) \
            .replace("{{CRAFTCSS}}", craft.CSS + synergy.CSS).replace("{{NAV}}", nav).replace("{{TITLE}}", t).replace("{{FILTERS}}", "").replace("{{SEARCH}}", "").replace("{{BODY}}", body).replace('href="index.html"', 'href="../index.html"')
        (out / fn).write_text(doc, encoding="utf-8")
    for fn, title, _ in PAGES:
        nav = "".join('<a href="%s"%s>%s</a>' % (f, ' class="cur"' if f == fn else "", t) for f, t, _ in PAGES)
        filt = FILTERS if fn in ("class.html", "origin.html") else ""
        search = SEARCH if filt else ""
        doc = TPL.replace("{{PATCH}}", e(patch)).replace("{{N}}", "%d" % total).replace("{{DATE}}", time.strftime("%Y-%m-%d %H:%M")) \
            .replace("{{CRAFTCSS}}", craft.CSS + synergy.CSS).replace("{{NAV}}", nav).replace("{{TITLE}}", title).replace("{{FILTERS}}", filt).replace("{{SEARCH}}", search).replace("{{BODY}}", bodies[fn])
        (out / fn).write_text(doc, encoding="utf-8")
        print("done →", out / fn, len(doc), "bytes")
    print(len(roster), "champions;", len(top), "comps")

PAGES = [("index.html", "首页 · 洞察", "最强阵容、冷门高胜率、三星价值、羁绊强度"),
         ("class.html", "职业站位", "各职业羁绊的前/中/后排英雄与推荐出装"),
         ("origin.html", "种族站位", "各种族羁绊的站位矩阵 + 站位结论"),
         ("synergy.html", "种族搭配", "种族 × 种族 胜率矩阵，点格子看所有英雄组合"),
         ("craft.html", "装备合成", "Set 18 散件合成表、纹章与冠冕")]
FILTERS = r'''<div class="filters" id="filters">
  <div class="fg"><span class="fl">费用</span>
    <button type="button" class="fb on" data-f="cost" data-v="">全部</button>
    <button type="button" class="fb" data-f="cost" data-v="1">1</button>
    <button type="button" class="fb" data-f="cost" data-v="2">2</button>
    <button type="button" class="fb" data-f="cost" data-v="3">3</button>
    <button type="button" class="fb" data-f="cost" data-v="4">4</button>
    <button type="button" class="fb" data-f="cost" data-v="5">5</button>
  </div>
  <div class="fg"><span class="fl">站位</span>
    <button type="button" class="fb on" data-f="pos" data-v="">全部</button>
    <button type="button" class="fb" data-f="pos" data-v="front">前排</button>
    <button type="button" class="fb" data-f="pos" data-v="mid">中排</button>
    <button type="button" class="fb" data-f="pos" data-v="back">后排</button>
  </div>
</div>
'''
SEARCH = '<input id="q" placeholder="搜索英雄 / 羁绊…">'

TPL = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}} · 云顶攻略台 zmftft</title><style>
:root{--bg:#0e1116;--pn:#161b22;--pn2:#1c232d;--bd:#2a323d;--tx:#e6edf3;--mu:#8b98a8;--ac:#f0b429;--good:#3fb950;--bad:#e5737a;--r:12px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 -apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px}
nav{position:sticky;top:0;z-index:9;background:rgba(14,17,22,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--bd)}
nav .wrap{display:flex;gap:16px;align-items:center;height:56px}nav .lg{font-weight:800;color:var(--ac);white-space:nowrap}
nav a{color:var(--mu);text-decoration:none;white-space:nowrap}nav a:hover,nav a.cur{color:var(--tx)}nav a.cur{border-bottom:2px solid var(--ac)}a.golink{text-decoration:none;color:var(--tx)}a.golink:hover{border-color:var(--ac)}
nav input{margin-left:auto;background:var(--pn2);border:1px solid var(--bd);color:var(--tx);border-radius:8px;padding:7px 12px;width:220px}
.filters{display:flex;flex-wrap:wrap;gap:12px 20px;margin:16px 0 4px;padding:12px;background:var(--pn);border:1px solid var(--bd);border-radius:var(--r)}
.fg{display:flex;flex-wrap:wrap;align-items:center;gap:6px}.fl{color:var(--mu);font-size:12px;margin-right:4px}
.fb{background:var(--pn2);border:1px solid var(--bd);color:var(--mu);border-radius:99px;padding:4px 12px;cursor:pointer;font-size:12px}
.fb:hover{color:var(--tx)}.fb.on{background:var(--ac);border-color:var(--ac);color:#111;font-weight:700}

header{padding:40px 0 10px}header h1{margin:0;font-size:32px}header p{color:var(--mu);margin:6px 0}
.pill{display:inline-block;background:var(--pn2);border:1px solid var(--bd);border-radius:99px;padding:2px 10px;margin-right:6px;font-size:12px}
section{margin:36px 0}h2{font-size:22px;border-left:4px solid var(--ac);padding-left:10px;margin:0 0 16px}h3{font-size:16px;margin:18px 0 10px}h3 small,.hint{color:var(--mu);font-weight:400;font-size:12px;margin:0 0 8px}
.grid{display:grid;gap:14px}.comps{grid-template-columns:repeat(auto-fill,minmax(360px,1fr))}.three{grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:18px}
.cc,.box{background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:14px}
.row{display:flex;flex-wrap:wrap;gap:4px}.kv{display:flex;gap:14px;margin-top:10px;font-size:13px;color:var(--mu)}.kv b{color:var(--tx)}.sub{color:var(--mu);font-size:12px;margin-top:6px}
.av{display:inline-block;width:38px;height:38px;border-radius:8px;border:2px solid var(--c);overflow:hidden;background:#000}.av img{width:100%;height:100%;object-fit:cover}.av.sm{width:30px;height:30px}
.lst{list-style:none;margin:0;padding:0}.lst li{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--bd)}.lst li:last-child{border:0}
.ln{flex:1}.lv{text-align:right}.lv small{display:block;color:var(--mu);font-size:11px}.tb{font-size:11px;background:var(--pn2);border-radius:4px;padding:1px 6px;color:var(--mu)}
.good,.kv .good b{color:var(--good)!important}.bad,.kv .bad b{color:var(--bad)!important}
.legend{color:var(--mu);font-size:12px;margin:-6px 0 14px}
.trow{display:grid;grid-template-columns:120px 1fr 1fr 1fr;gap:10px;background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:12px;margin-bottom:10px}
.tn{font-weight:700;font-size:16px}.tn small{display:block;color:var(--mu);font-weight:400;font-size:12px}
.col{background:var(--pn2);border-radius:8px;padding:8px}.cl{font-size:11px;color:var(--mu);margin-bottom:6px}
.cards{display:flex;flex-wrap:wrap;gap:8px}.emp{color:var(--mu)}
.ch{width:124px;background:var(--bg);border:1px solid var(--bd);border-top:3px solid var(--c);border-radius:10px;padding:6px;font-size:11px}
.ph{position:relative}.ph img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;display:block}
.ph em{position:absolute;top:4px;left:4px;background:var(--c);color:#000;font-style:normal;font-weight:800;border-radius:4px;padding:0 5px}
.eyes{display:flex;flex-wrap:wrap;gap:3px;margin:3px 0}.eye{font-size:10px;font-weight:700;padding:1px 5px;border-radius:999px;border:1px solid;white-space:nowrap}
.ey3{color:#ffd54a;border-color:#ffd54a;background:rgba(255,213,74,.12)}.eyi{color:#ff7a59;border-color:#ff7a59;background:rgba(255,122,89,.12)}
.cf{position:relative;display:inline-block;margin-right:2px}.eb{position:absolute;bottom:-4px;font-size:8px;line-height:1;padding:1px 2px;border-radius:3px;border:1px solid;background:#111}.eb.ey3{left:-2px}.eb.eyi{right:-2px}
.nm{font-weight:700;font-size:13px;margin-top:4px}.tg i{font-style:normal;display:inline-block;background:var(--pn2);color:var(--mu);border-radius:4px;padding:0 4px;margin:2px 2px 0 0}
.st{color:var(--mu);margin:4px 0}.st span{font-weight:700}
.bd{display:flex;align-items:center;gap:2px;margin-top:3px}.bd b{color:var(--ac);width:14px}.bd img{width:22px;height:22px;border-radius:3px}.bd span{margin-left:auto;color:var(--tx)}.bd.none{color:var(--mu)}
.verdict{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.verdict>*{background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:14px}
.verdict img{max-width:40px}
footer{color:var(--mu);border-top:1px solid var(--bd);padding:24px 0 60px;font-size:12px}code{background:var(--pn2);padding:1px 6px;border-radius:4px}
.hide{display:none!important}
{{CRAFTCSS}}
@media(max-width:800px){nav .wrap{flex-wrap:wrap;height:auto;padding:8px 12px}nav input{width:100%;margin:0}.trow{grid-template-columns:1fr}.comps{grid-template-columns:1fr}.filters{padding:10px}}
</style></head><body>
<nav><div class="wrap"><a class="lg" href="index.html">zmftft</a>{{NAV}}{{SEARCH}}</div></nav>
<div class="wrap"><header><h1>{{TITLE}}</h1><p><span class="pill">Set 18 · patch {{PATCH}}</span><span class="pill">{{N}} 场样本</span><span class="pill">更新 {{DATE}}</span></p>
<p>数据来源 <a href="https://tactics.tools/zh/units" style="color:var(--ac)">tactics.tools</a> · 图标 Community Dragon</p>
{{FILTERS}}
</header>
{{BODY}}
<footer>新版本重新生成：<code>python3 build_site.py --no-cache</code>（生成 4 个页面） 然后 <code>git push</code>。非官方粉丝站，数据仅供参考。</footer></div>
<script>
(function(){
  var state={q:'',cost:'',pos:'',sec:''};
  var q=document.getElementById('q'); if(!q) return;
  function apply(){
    document.querySelectorAll('.ch').forEach(function(c){
      var ok=true;
      if(state.q && c.dataset.k.indexOf(state.q)<0) ok=false;
      if(state.cost && String(c.dataset.cost)!==state.cost) ok=false;
      if(state.pos && c.dataset.pos!==state.pos) ok=false;
      c.classList.toggle('hide', !ok);
    });
    document.querySelectorAll('.trow').forEach(function(r){
      var has=!!r.querySelector('.ch:not(.hide)');
      var nameHit=!state.q || r.querySelector('.tn').textContent.indexOf(state.q)>=0;
      r.classList.toggle('hide', !(has || (nameHit && !state.cost && !state.pos)));
    });
  }
  q.addEventListener('input', function(){ state.q=q.value.trim(); apply(); });
  document.getElementById('filters').addEventListener('click', function(ev){
    var b=ev.target.closest('.fb'); if(!b) return;
    var f=b.dataset.f, v=b.dataset.v;
    state[f]=v;
    b.parentNode.querySelectorAll('.fb').forEach(function(x){ x.classList.toggle('on', x===b); });
    apply();
  });
})();
</script></body></html>'''

if __name__ == "__main__":
    main()
