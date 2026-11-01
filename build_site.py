#!/usr/bin/env python3
"""云顶攻略台 · zmftft — 生成站点页面 (stdlib only).
用法: python3 build_site.py [--out .] [--no-cache] [--data cache/snapshots/set<N>/<patch>.json]
先抓取并存快照（fetch_data.py，存在不入库的 cache/），页面只从快照渲染；--data 只渲染、不联网。
依赖同目录 generate_tft_table.py 中的映射与工具函数。"""
import argparse, html as H, json, re
from collections import Counter, defaultdict
from pathlib import Path
from generate_tft_table import (COST_COLORS, build_item_meta, item_cn, item_icon, item_keys, build_roster, cdragon_asset_url,
    load_manual, row_orders, NO_CLASS)

import craft, synergy, fetch_data, checks
e = lambda s: H.escape(str(s))

def face(u, size=""):
    col = COST_COLORS.get(u.get("cost"), "#666")
    return ('<span class="av %s" style="--c:%s" title="%s"><img src="%s" alt="%s" loading="lazy" '
            'onerror="this.style.opacity=.2"></span>') % (size, col, e(u["name"]), e(u["icon"]), e(u["name"]))

def build_ids(b):
    return b["items"] if isinstance(b["items"], list) else [b["items"]]

def build_html(meta, b, label):
    if not b:
        return '<div class="bd none"><b>%s</b>—</div>' % label
    ids = build_ids(b)
    icons = "".join('<img src="%s" title="%s" alt="%s" data-it="%s" loading="lazy">' % (
        e(item_icon(meta, i)), e(item_cn(meta, i)), e(item_cn(meta, i)), e(i)) for i in ids)
    return '<div class="bd" title="%s · 吃鸡率 %.1f%%（全体基线 12.5%%）· %d 场"><b>%s</b>%s<span>%.0f%%</span></div>' % (
        e(" + ".join(item_cn(meta, i) for i in ids)), b.get("won") or 0, b.get("count") or 0, label, icons, b.get("won") or 0)

def item_tips(meta, craft_snap, ids):
    """Hover data for item icons: id -> [component, component, effect] for an item made from two components, else
    [kind] ("神器", "光明装备", "纹章" or ""). The recipe is found by the item's key, else by its Chinese name:
    tactics.tools uses current ids (DA_EdgeOfNight) where the recipe table keeps Riot's older api names
    (TFT_Item_GuardianAngel). A name shared by two recipes matches neither."""
    recipes = craft_snap["recipes"]
    by_key = {}
    for r in recipes:
        for k in item_keys(r["api"]):
            by_key.setdefault(k, r)
    names = Counter(r["name"] for r in recipes)
    by_name = {r["name"]: r for r in recipes if names[r["name"]] == 1}
    out = {}
    for i in ids:
        r = by_key.get(i) or by_key.get(i.replace("DA_", "")) or by_name.get(item_cn(meta, i))
        out[i] = list(r["pair"]) + [tidy(r["desc"])] if r else [
            "神器" if "Artifact" in i else "光明装备" if "Radiant" in i else "纹章" if "Emblem" in i else ""]
    return out

def tidy(desc):
    """An effect text from the snapshot (craft.blurb) can keep a {{keyword}} token, or end in a label whose value
    was a game variable ("…的治疗。 友军治疗："); the tooltip drops both."""
    d = re.sub(r"\s*\{\{[^}]*\}\}", "", desc).strip()
    return re.sub(r"\s*[^\s。：]*：$", "", d)

def card(meta, r, us, total):
    s = us.get(r["id"]) or {}
    stat = ""
    if s:
        stat = '<div class="st">选率 %.1f%%</div>' % (s["count"] / total * 100)
    ic = {d.get("id"): d.get("count") or 0 for d in r.get("item_counts") or []}
    n = sum(ic.values())
    if n:  # 描述：玩家把成装给谁（代替以前的「阵眼—装备」）
        stat += '<div class="st" title="该英雄在场的 %d 个棋盘里，拿着 3 件成装的占 %.0f%%。这是玩家把装备给谁，不说明给它装备更能赢">满装率 %.0f%%</div>' % (
            n, ic.get(3, 0) / n * 100, ic.get(3, 0) / n * 100)
    tags = "".join("<i>%s</i>" % e(t) for t in r["traits"])
    return ('<div class="ch" data-k="%s" data-cost="%s" data-pos="%s" style="--c:%s"><div class="ph"><img src="%s" alt="%s" loading="lazy" onerror="this.style.opacity=.2">'
            '<em>%s</em></div><div class="nm">%s</div><div class="tg">%s</div>%s%s%s</div>') % (
        e(r["name"] + " " + " ".join(r["traits"])), r["cost"] or "", r.get("pos") or "",
        COST_COLORS.get(r["cost"], "#666"), e(r["icon"]), e(r["name"]),
        r["cost"] or "?", e(r["name"]), tags, stat, build_html(meta, r["top2"], "二"), build_html(meta, r["top3"], "三"))

def matrix(meta, roster, key, order, us, total, sid, title):
    g = defaultdict(lambda: {"front": [], "mid": [], "back": []})
    for r in roster:
        ts = r[key] or ([NO_CLASS] if key == "classes" else [])
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
    return '<section id="%s"><h2>%s</h2><div class="legend">前排 / 中排 / 后排为本站人工标注 · 选率 = 出现该英雄的最终棋盘占全部棋盘的比例 · 满装率 = 该英雄在场的棋盘里拿着 3 件成装的比例：玩家把装备给谁，不说明给它装备更能赢 · 二/三件装为该英雄出场最多的组合，百分比为吃鸡率（第 1 名比例，全体基线 12.5%%），场次见悬停提示 · 悬停（手机上点按）装备图标看合成配方</div>%s</section>' % (sid, title, "".join(rows))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--no-cache", action="store_true", help="忽略 cache/raw/ 重新抓取")
    ap.add_argument("--data", help="只用这个快照渲染、不联网，例如 cache/snapshots/set18/18.5c.json")
    a = ap.parse_args()
    if a.data:
        path = Path(a.data)
        checks.require(fetch_data.load(path))
    else:
        path = fetch_data.save(fetch_data.make_snapshot(fetch_data.collect_raw(a.no_cache)))
        print("snapshot →", path)
    render(fetch_data.load(path), Path(a.out))
    print("snapshot sha256", fetch_data.sha256(path), "（README「页面数据快照」里记的应是这个值）")

def render(snap, out):
    """页面只读快照，不联网。"""
    m = snap["meta"]; us = snap["unit_stats"]; total = m["total"]
    manual = load_manual(m["set"])
    costs = {k: v["cost"] for k, v in snap["official"]["units"].items()}
    class_order, origin_order = row_orders(manual, snap["official"]["traits"])
    champs = snap["champions"]
    folder = m["cdragon"]["folder"]  # image URLs use the snapshot's Community Dragon patch folder, not latest
    meta = build_item_meta(snap["items"], folder)
    # all units incl. Lux skins, for the unit faces on the synergy pages
    allmap = {}
    for c in champs:
        cr = c.get("character_record") or {}
        allmap[cr.get("character_id")] = {"name": cr.get("display_name") or cr.get("character_id"),
            "icon": cdragon_asset_url(cr.get("squareIconPath"), folder), "cost": costs.get(cr.get("character_id"))}
    roster = build_roster(champs, snap["unit_builds"], costs, manual, folder)
    comps = snap["comps"]
    def U(i): return allmap.get(i) or {"name": i.replace("DA_", ""), "icon": "", "cost": None}
    cls_html = matrix(meta, roster, "classes", class_order, us, total, "cls", "职业羁绊 × 站位")
    ori_html = matrix(meta, roster, "origins", origin_order, us, total, "ori", "种族羁绊 × 站位")
    links = '<section id="go"><h2>去哪看</h2><div class="grid three">' + "".join(
        '<a class="box golink" href="%s"><h3>%s</h3><p class="hint">%s</p></a>' % x for x in PAGES[1:]) + '</div></section>'
    bodies = {"index.html": REMOVED + links + "<script>var H={'#craft':'craft.html','#cls':'class.html','#ori':'origin.html','#ver':'origin.html'};if(H[location.hash])location.replace(H[location.hash]);</script>", "class.html": cls_html, "origin.html": ori_html, "synergy.html": "",
              "craft.html": craft.section([tuple(c) for c in snap["craft"]["components"]], {tuple(r["pair"]): r for r in snap["craft"]["recipes"]}, m["set"])[0]}
    syn_mat, syn_pages = synergy.build(comps, roster, origin_order, total, face, U, None)
    bodies["synergy.html"] = syn_mat
    tpl = TPL.replace("{{RIOT_NOTICE}}", e(RIOT_NOTICE)).replace("{{RIOT_BOILERPLATE}}", e(RIOT_BOILERPLATE))
    for k, v in (("{{SET}}", m["set"]), ("{{PATCH}}", m["patch_label"] or "tactics.tools 编号 %s" % m["patch"]),
                 ("{{SCOPE}}", ("排位 · %s" % m["rank_label"] if m["rank_label"] else "分段未注明") + " · 地区未注明"),
                 ("{{N}}", "{:,}".format(total)), ("{{DATE}}", (m["last_updated"] or m["fetched_at"]).replace("T", " ")[:16] + " UTC")):
        tpl = tpl.replace(k, e(v))
    # pages with item icons get the recipe tooltip: its data (only the items shown) and its CSS/JS; other pages stay as they were
    tip_ids = sorted({i for r in roster for b in (r["top2"], r["top3"]) if b for i in build_ids(b)})
    tips = {"c": {c: [n, i] for c, n, i in snap["craft"]["components"]}, "i": item_tips(meta, snap["craft"], tip_ids)}
    tips_json = json.dumps(tips, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
    tpl_items = tpl.replace("{{TIPCSS}}", TIP_CSS).replace("{{ITEMTIPS}}", '<script type="application/json" id="itd">%s</script>%s' % (tips_json, TIP_JS))
    tpl_plain = tpl.replace("{{TIPCSS}}", "").replace("{{ITEMTIPS}}", "")
    out.mkdir(parents=True, exist_ok=True); (out / "synergy").mkdir(exist_ok=True)
    for old in (out / "synergy").glob("*.html"): old.unlink()
    for fn, (t, body) in syn_pages.items():
        nav = "".join('<a href="../%s"%s>%s</a>' % (f, ' class="cur"' if f == "synergy.html" else "", tt) for f, tt, _ in PAGES)
        doc = (tpl_items if 'data-it="' in body else tpl_plain).replace("{{CRAFTCSS}}", craft.CSS + synergy.CSS).replace("{{NAV}}", nav).replace("{{TITLE}}", t).replace("{{FILTERS}}", "").replace("{{SEARCH}}", "").replace("{{BODY}}", body).replace('href="index.html"', 'href="../index.html"')
        (out / fn).write_text(doc, encoding="utf-8")
    for fn, title, _ in PAGES:
        nav = "".join('<a href="%s"%s>%s</a>' % (f, ' class="cur"' if f == fn else "", t) for f, t, _ in PAGES)
        filt = FILTERS if fn in ("class.html", "origin.html") else ""
        search = SEARCH if filt else ""
        doc = (tpl_items if 'data-it="' in bodies[fn] else tpl_plain).replace("{{CRAFTCSS}}", craft.CSS + synergy.CSS).replace("{{NAV}}", nav).replace("{{TITLE}}", title).replace("{{FILTERS}}", filt).replace("{{SEARCH}}", search).replace("{{BODY}}", bodies[fn])
        (out / fn).write_text(doc, encoding="utf-8")
        print("done →", out / fn, len(doc), "bytes")
    print(len(roster), "champions;", len(comps), "comps")

# Riot's notice for fan projects, copied from https://www.riotgames.com/en/legal ("Legal Jibber Jabber",
# section 6, last updated August 2018; read 2026-11-01). Only "[The title of your Project]" is filled in.
RIOT_NOTICE = ("云顶攻略台 zmftft was created under Riot Games' \"Legal Jibber Jabber\" policy using assets owned by Riot Games.  "
               "Riot Games does not endorse or sponsor this project.")
# Riot's legal boilerplate for third-party products, copied from https://developer.riotgames.com/policies/general
# ("Core Policies", last updated May 29, 2025; read 2026-11-01). Only "[Your product]" is filled in.
RIOT_BOILERPLATE = ("云顶攻略台 zmftft isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or "
                    "anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated "
                    "properties are trademarks or registered trademarks of Riot Games, Inc.")

# 下线说明（2026-11-01）：最强阵容、冷门高胜率、三星价值、羁绊强度、站位结论、阵眼标签
REMOVED = '''<section id="ins"><h2>说明</h2><div class="box"><p>首页的「最强阵容」「冷门高胜率」「三星价值」「羁绊强度」、种族页的「站位结论」和英雄卡上的「阵眼」标签已下线。</p>
<p class="hint">它们只看对局结束时的最终棋盘：活得越久越容易凑出三星、满装、高费卡和高档羁绊，所以这些数字主要说明“这局本来就在赢”，不说明“照这样玩能赢”。阵容强度目前还无法从最终棋盘可靠测出，测出之前这里不放排行。</p></div></section>'''

PAGES = [("index.html", "首页", "说明与各页入口"),
         ("class.html", "职业站位", "各职业羁绊的前/中/后排英雄与常用出装"),
         ("origin.html", "种族站位", "各种族羁绊的前/中/后排英雄与常用出装"),
         ("synergy.html", "种族搭配", "种族 × 种族 搭配矩阵（均名、选率），点格子看所有英雄组合"),
         ("craft.html", "装备合成", "当前赛季散件合成表、纹章与冠冕")]
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

# 装备图标的合成配方提示（只在有装备图标的页面上）
TIP_CSS = """.bd img[data-it]{cursor:help}
.tip{position:fixed;z-index:30;display:none;max-width:260px;background:var(--pn);border:1px solid var(--bd);border-radius:10px;padding:10px 12px;box-shadow:0 10px 30px rgba(0,0,0,.55);font-size:12px;line-height:1.5;pointer-events:none}
.tip .tt{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700}.tip .tt img{width:32px;height:32px;border-radius:6px}
.tip .rc{display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-top:8px}.tip .rc img{width:22px;height:22px;border-radius:4px}.tip .rc i{font-style:normal;color:var(--mu);margin:0 2px}
.tip p{margin:6px 0 0;color:var(--mu)}"""
TIP_JS = r'''<script>
(function(){
  // 悬停（手机上点按）装备图标显示合成配方。数据在 #itd：c = 散件 id -> [名称, 图标]，i = 装备 id -> [散件, 散件, 效果] 或 [类别]
  var D=JSON.parse(document.getElementById('itd').textContent), C=D.c, I=D.i, cur=null, touch=false;
  var tip=document.createElement('div'); tip.className='tip'; tip.setAttribute('role','tooltip'); document.body.appendChild(tip);
  function esc(s){ return String(s).replace(/[&<>"]/g, function(ch){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]; }); }
  function part(c){ var p=C[c]||[c,'']; return '<img src="'+esc(p[1])+'" alt="">'+esc(p[0]); }
  function show(img){
    var x=I[img.dataset.it]||[''], h='<div class="tt"><img src="'+esc(img.src)+'" alt="">'+esc(img.alt)+'</div>';
    h+=x.length>1 ? '<div class="rc">'+part(x[0])+'<i>+</i>'+part(x[1])+'</div>'+(x[2] ? '<p>'+esc(x[2])+'</p>' : '')
                  : '<p>'+(x[0] ? esc(x[0])+' · ' : '')+'不能用散件合成</p>';
    tip.innerHTML=h; tip.style.display='block'; cur=img;
    var r=img.getBoundingClientRect(), w=tip.offsetWidth, ht=tip.offsetHeight, top=r.bottom+8;
    if(top+ht>innerHeight-8) top=Math.max(8, r.top-ht-8);
    tip.style.left=Math.max(8, Math.min(r.left+r.width/2-w/2, innerWidth-w-8))+'px'; tip.style.top=top+'px';
  }
  function hide(){ tip.style.display='none'; cur=null; }
  function hit(ev){ return ev.target.closest ? ev.target.closest('img[data-it]') : null; }
  document.querySelectorAll('img[data-it]').forEach(function(i){ i.title=''; });  // 原生提示只在脚本不运行时出现
  document.addEventListener('pointerdown', function(ev){ touch=ev.pointerType!=='mouse'; }, true);
  document.addEventListener('pointerover', function(ev){ var i=hit(ev); if(i && ev.pointerType==='mouse') show(i); });
  document.addEventListener('pointerout', function(ev){ if(ev.pointerType==='mouse' && hit(ev)) hide(); });
  document.addEventListener('click', function(ev){ if(!touch) return; var i=hit(ev); if(i && i!==cur) show(i); else hide(); });
  addEventListener('scroll', hide, {passive:true}); addEventListener('resize', hide);
})();
</script>'''

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
.grid{display:grid;gap:14px}.three{grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:18px}
.box{background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:14px}
.sub{color:var(--mu);font-size:12px;margin-top:6px}
.av{display:inline-block;width:38px;height:38px;border-radius:8px;border:2px solid var(--c);overflow:hidden;background:#000}.av img{width:100%;height:100%;object-fit:cover}.av.sm{width:30px;height:30px}
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
footer{color:var(--mu);border-top:1px solid var(--bd);padding:24px 0 60px;font-size:12px}code{background:var(--pn2);padding:1px 6px;border-radius:4px}
.hide{display:none!important}
{{CRAFTCSS}}{{TIPCSS}}
@media(max-width:800px){nav .wrap{flex-wrap:wrap;height:auto;padding:8px 12px}nav input{width:100%;margin:0}.trow{grid-template-columns:1fr}.filters{padding:10px}}
</style></head><body>
<nav><div class="wrap"><a class="lg" href="index.html">zmftft</a>{{NAV}}{{SEARCH}}</div></nav>
<div class="wrap"><header><h1>{{TITLE}}</h1><p><span class="pill">Set {{SET}} · 版本 {{PATCH}}</span><span class="pill">{{SCOPE}}</span><span class="pill">{{N}} 个棋盘</span><span class="pill">数据截至 {{DATE}}</span></p>
<p>数据来源 <a href="https://tactics.tools/zh/units" style="color:var(--ac)">tactics.tools</a> · 图标 Community Dragon</p>
{{FILTERS}}
</header>
{{BODY}}
<footer>非官方粉丝站，数据仅供参考。<br>{{RIOT_NOTICE}}<br>{{RIOT_BOILERPLATE}}</footer></div>
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
</script>{{ITEMTIPS}}</body></html>'''

if __name__ == "__main__":
    main()
