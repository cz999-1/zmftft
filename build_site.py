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

def card(meta, r, us, total):
    s = us.get(r["id"]) or {}
    stat = ""
    if s:
        stat = '<div class="st"><span class="%s">均名%.2f</span> · 前四%.0f%% · 选率%.1f%%</div>' % (
            pcls(s["place"]), s["place"], s["top4"], s["count"] / total * 100)
    tags = "".join("<i>%s</i>" % e(t) for t in r["traits"])
    return ('<div class="ch" data-k="%s" style="--c:%s"><div class="ph"><img src="%s" alt="%s" loading="lazy" onerror="this.style.opacity=.2">'
            '<em>%s</em></div><div class="nm">%s</div><div class="tg">%s</div>%s%s%s</div>') % (
        e(r["name"] + " " + " ".join(r["traits"])), COST_COLORS.get(r["cost"], "#666"), e(r["icon"]), e(r["name"]),
        r["cost"] or "?", e(r["name"]), tags, stat, build_html(meta, r["top2"], "二"), build_html(meta, r["top3"], "三"))

def matrix(meta, roster, key, order, us, total, sid, title):
    g = defaultdict(lambda: {"front": [], "mid": [], "back": []})
    for r in roster:
        ts = r[key] or (["（无职业/特殊）"] if key == "classes" else [])
        for t in ts:
            g[t][r["pos"]].append(r)
    names = [n for n in order if n in g] + sorted(n for n in g if n not in order)
    rows = []
    for n in names:
        cols = []
        for p, lab in (("front", "前排"), ("mid", "中排"), ("back", "后排")):
            us_ = sorted(g[n][p], key=lambda x: (x["cost"] or 9, x["name"]))
            inner = "".join(card(meta, r, us, total) for r in us_) or '<div class="emp">—</div>'
            cols.append('<div class="col"><div class="cl">%s</div><div class="cards">%s</div></div>' % (lab, inner))
        rows.append('<div class="trow"><div class="tn">%s<small>%d 名英雄</small></div>%s</div>' % (
            e(n), len({r["id"] for p in g[n].values() for r in p}), "".join(cols)))
    return '<section id="%s"><h2>%s</h2><div class="legend">前排 / 中排 / 后排 · 均名颜色：<span class="good">≤3.8 强</span> <span class="bad">≥4.5 弱</span> · 二/三件装为出场最多组合（胜率%%）</div>%s</section>' % (sid, title, "".join(rows))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="index.html")
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
    comp_html = "".join(
        '<div class="cc"><div class="row">%s</div><div class="kv"><span class="%s">均名 <b>%.2f</b></span><span>前四 <b>%.0f%%</b></span><span>吃鸡 <b>%.0f%%</b></span><span>样本 <b>%d</b></span></div><div class="sub">%s</div></div>' % (
            "".join(face(U(i)) for i in c["units"]), pcls(c["place"]), c["place"], c["top4"] / c["count"] * 100,
            c["win"] / c["count"] * 100, c["count"], e("、".join(U(i)["name"] for i in c["units"]))) for c in top)
    rid = {r["id"]: r for r in roster}
    def ulist(items, fmt):
        return "".join('<li>%s<span class="ln">%s</span><span class="lv">%s</span></li>' % (face(r, "sm"), e(r["name"]), fmt(s)) for r, s in items)
    hid = [(rid[k], s) for k, s in us.items() if k in rid and s["count"] >= 800 and s["count"] / total < 0.04]
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
    body = insights + matrix(meta, roster, "classes", CLASS_ORDER, us, total, "cls", "职业羁绊 × 站位") + \
        matrix(meta, roster, "origins", ORIGIN_ORDER, us, total, "ori", "种族羁绊 × 站位") + \
        '<section id="ver"><h2>站位结论（种族）</h2><div class="verdict">%s</div></section>' % verdict
    doc = TPL.replace("{{PATCH}}", e(patch)).replace("{{N}}", "%d" % total).replace("{{DATE}}", time.strftime("%Y-%m-%d %H:%M")).replace("{{BODY}}", body)
    Path(a.out).write_text(doc, encoding="utf-8")
    print("done →", a.out, len(doc), "bytes;", len(roster), "champions;", len(top), "comps")

TPL = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>云顶攻略台 · zmftft</title><style>
:root{--bg:#0e1116;--pn:#161b22;--pn2:#1c232d;--bd:#2a323d;--tx:#e6edf3;--mu:#8b98a8;--ac:#f0b429;--good:#3fb950;--bad:#e5737a;--r:12px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 -apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px}
nav{position:sticky;top:0;z-index:9;background:rgba(14,17,22,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--bd)}
nav .wrap{display:flex;gap:16px;align-items:center;height:56px}nav .lg{font-weight:800;color:var(--ac);white-space:nowrap}
nav a{color:var(--mu);text-decoration:none;white-space:nowrap}nav a:hover{color:var(--tx)}
nav input{margin-left:auto;background:var(--pn2);border:1px solid var(--bd);color:var(--tx);border-radius:8px;padding:7px 12px;width:220px}
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
.nm{font-weight:700;font-size:13px;margin-top:4px}.tg i{font-style:normal;display:inline-block;background:var(--pn2);color:var(--mu);border-radius:4px;padding:0 4px;margin:2px 2px 0 0}
.st{color:var(--mu);margin:4px 0}.st span{font-weight:700}
.bd{display:flex;align-items:center;gap:2px;margin-top:3px}.bd b{color:var(--ac);width:14px}.bd img{width:22px;height:22px;border-radius:3px}.bd span{margin-left:auto;color:var(--tx)}.bd.none{color:var(--mu)}
.verdict{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.verdict>*{background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:14px}
.verdict img{max-width:40px}
footer{color:var(--mu);border-top:1px solid var(--bd);padding:24px 0 60px;font-size:12px}code{background:var(--pn2);padding:1px 6px;border-radius:4px}
.hide{display:none!important}
@media(max-width:800px){nav .wrap{flex-wrap:wrap;height:auto;padding:8px 12px}nav input{width:100%;margin:0}.trow{grid-template-columns:1fr}.comps{grid-template-columns:1fr}}
</style></head><body>
<nav><div class="wrap"><span class="lg">zmftft</span><a href="#ins">洞察</a><a href="#cls">职业</a><a href="#ori">种族</a><a href="#ver">结论</a><input id="q" placeholder="搜索英雄 / 羁绊…"></div></nav>
<div class="wrap"><header><h1>云顶攻略台 · zmftft</h1><p><span class="pill">Set 18 · patch {{PATCH}}</span><span class="pill">{{N}} 场样本</span><span class="pill">更新 {{DATE}}</span></p>
<p>数据来源 <a href="https://tactics.tools/zh/units" style="color:var(--ac)">tactics.tools</a> · 图标 Community Dragon</p></header>
{{BODY}}
<footer>新版本重新生成：<code>python3 build_site.py --no-cache</code> 然后 <code>git push</code>。非官方粉丝站，数据仅供参考。</footer></div>
<script>
var q=document.getElementById('q');q.addEventListener('input',function(){var v=q.value.trim();
document.querySelectorAll('.ch').forEach(function(c){c.classList.toggle('hide',v&&c.dataset.k.indexOf(v)<0)});
document.querySelectorAll('.trow').forEach(function(r){r.classList.toggle('hide',v&&!r.querySelector('.ch:not(.hide)')&&r.querySelector('.tn').textContent.indexOf(v)<0)});});
</script></body></html>'''

if __name__ == "__main__":
    main()
