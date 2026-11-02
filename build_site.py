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

PLACE_SD = 2.29  # 单局名次的标准差（1–8 均匀分布）；英雄页图例里的区间上界用它


def check_riot(snap, riot):
    """自采数据（tft-lab 的 heroes 导出）的护栏：对不上就不构建。"""
    if not str(riot.get("schema", "")).startswith("tftlab-heroes/"):
        raise SystemExit("--riot 文件不是 tftlab-heroes 导出（schema=%r）" % riot.get("schema"))
    rset = (riot.get("population") or {}).get("set")
    if rset != snap["meta"]["set"]:
        raise SystemExit("--riot 数据是 Set %s，快照是 Set %s" % (rset, snap["meta"]["set"]))
    fams = {f["id"] for f in riot.get("families") or []}
    for u, d in (riot.get("units") or {}).items():
        for c in d.get("cells") or []:
            if c["family"] not in fams:
                raise SystemExit("--riot 单元格引用了不存在的阵容组 %s（%s）" % (c["family"], u))


def riot_label(riot):
    """自采样本的一行说明，全部取自导出文件本身。"""
    pop = riot.get("population") or {}
    tiers = "/".join(sorted(pop.get("known_rank_boards") or {})) or "?"
    win = " → ".join((w or "")[:10] for w in (pop.get("window_utc") or ["", ""]))
    base = "自采 Riot API · %s · 种子段位 %s（对手段位未知）· %s (UTC) · %s 盘 · n<%d 的格子不显示 · C 级描述" % (
        "/".join(pop.get("platforms") or pop.get("hosts") or ["?"]), tiers, win,
        "{:,}".format(pop.get("boards") or 0), riot["params"]["min_n"])
    if riot.get("publishable") is False:
        base += " · 开发 key 数据，仅本地预览"
    return base


def hero_panel(r, b, riot, fams, runits, U):
    """悬停面板：星级数据（tactics.tools）+ 3★ 满装所在阵容（自采，可缺）。"""
    star = "".join('<tr><td>%d★</td><td>%s 盘</td><td>均名 %.2f</td><td>吃鸡 %.1f%%</td></tr>' % (
        srow["id"], "{:,}".format(srow["count"]), srow["place"], srow["won"])
        for srow in b.get("starLevelData") or [] if srow.get("count"))
    star = ('<div class="hp-s">星级数据 <small>tactics.tools</small><table>%s</table></div>' % star) if star else ""
    if riot:
        ru = runits.get(r["id"])
        mn = riot["params"]["min_n"]
        if not ru:
            body = '<p class="emp3">自采样本里没有该英雄的 3★ 满装棋盘</p>'
        elif not ru["cells"]:
            body = '<p class="emp3">自采样本不足：3★ 满装共 %d 盘，没有 n ≥ %d 的阵容格子</p>' % (ru["n_star3_full"], mn)
        else:
            cells = []
            for c in ru["cells"][:3]:
                faces = "".join(face(U(uid), "sm") for uid in fams[c["family"]]["units"])
                cells.append('<div class="hpc"><div class="fcs">%s</div><div class="cst">均名 <b>%.2f</b> '
                             '<small>(95%% %.2f–%.2f)</small> · 吃鸡 %.0f%% · %s 盘</div></div>' % (
                                 faces, c["place_mean"], c["place_ci95"][0], c["place_ci95"][1],
                                 c["top1"] * 100, "{:,}".format(c["n_boards"])))
            sup = ('；%d 组 n &lt; %d 不显示' % (ru["suppressed_cells"], mn)) if ru["suppressed_cells"] else ""
            unm = ('；未归入任何阵容组 %d 盘' % ru["unmatched_boards"]) if ru["unmatched_boards"] else ""
            body = "".join(cells) + '<p class="hint">该英雄 3★ 满装共 %d 盘%s%s</p>' % (ru["n_star3_full"], sup, unm)
        rp = '<div class="hp-s">3★ 满装 · 所在阵容<small>（按均名排，自采样本）</small>%s</div>' % body
    else:
        rp = '<div class="hp-s">3★ 满装 · 所在阵容<p class="emp3">暂无自采样本（构建时未提供 --riot 数据）</p></div>'
    warn = '<p class="hint">能亮出三星和满装的棋盘本来就活得久：以下是结果的描述，不是打法建议。</p>'
    return '<div class="hp"><div class="hp-t">%s</div>%s%s%s</div>' % (e(r["name"]), warn, star, rp)


def heroes_page(meta, roster, us, total, ub, riot, U):
    """英雄数据页：每行一个英雄（选率 / 吃鸡率 / 均名 + 最高吃鸡率出装），排序和筛选在浏览器里做。
    riot = tft-lab 自采导出（python -m tftlab.report.heroes_export），缺了页面照常构建。"""
    have = [r for r in roster if us.get(r["id"])]
    min_n = min((us[r["id"]]["count"] for r in have), default=0)
    hw_place = 1.96 * PLACE_SD / (min_n ** 0.5) if min_n else 0.0
    hw_won = 196 * (0.125 * 0.875 / min_n) ** 0.5 if min_n else 0.0
    fams = {f["id"]: f for f in (riot or {}).get("families") or []}
    runits = (riot or {}).get("units") or {}
    rows = []
    for r in sorted(have, key=lambda x: -(us[x["id"]].get("won") or 0)):
        s = us[r["id"]]
        b = ub.get(r["id"]) or {}
        sel = s["count"] / total * 100
        best2, fb2 = (b.get("bestPair"), False) if b.get("bestPair") else ((b.get("itemPairs") or [None])[0], True)
        best3, fb3 = (b.get("bestTrio"), False) if b.get("bestTrio") else ((b.get("itemTrios") or [None])[0], True)
        tags = "".join("<i>%s</i>" % e(t) for t in r["traits"])
        rows.append(
            '<div class="hrow" data-k="%s" data-cost="%s" data-sel="%.3f" data-win="%.3f" data-place="%.3f">'
            '<span class="hrk"></span><div class="hface">%s%s</div>'
            '<div class="hid"><div class="nm">%s</div><div class="tg">%s</div></div>'
            '<div class="hst"><span>选率 <b>%.1f%%</b></span><span>吃鸡率 <b>%.1f%%</b></span>'
            '<span>均名 <b>%.2f</b></span><small>%s 盘</small></div>'
            '<div class="hbd">%s%s</div></div>' % (
                e(r["name"] + " " + " ".join(r["traits"])), r["cost"] or "", sel, s["won"] or 0, s["place"] or 9,
                face(r), hero_panel(r, b, riot, fams, runits, U), e(r["name"]), tags,
                sel, s["won"] or 0, s["place"] or 0, "{:,}".format(s["count"]),
                build_html(meta, best2, "二*" if fb2 and best2 else "二"),
                build_html(meta, best3, "三*" if fb3 and best3 else "三")))
    riot_line = ""
    if riot:
        riot_line = ('<p class="hint">悬停面板的「3★ 满装 · 所在阵容」：%s。阵容组 = tactics.tools 阵容页的 %d 组'
                     '（组内为同一阵容的变体）；棋盘按「与任一变体重合 ≥ %d 个英雄」归组，重合不足记为未归组。</p>'
                     % (e(riot_label(riot)), len(fams), riot["params"]["min_overlap"]))
        if riot.get("publishable") is False:
            riot_line += ('<p class="hint" style="color:var(--bad)">注意：自采部分来自开发 key，按 Riot 开发者政策不可用于'
                          '公开网站——这份构建仅限本地预览，不要推送上线。</p>')
    legend = (
        '<p>选率 = 出现该英雄的最终棋盘占全部棋盘的比例 · 吃鸡率 = 第 1 名比例（全体基线 12.5%%）· 均名 = 平均名次（1–8）。'
        '每行标注棋盘数；本页最小样本 %s 盘，均名 95%% 区间半宽 ≤ %.2f 名、吃鸡率 ≤ ±%.1f 个百分点。评级 C（描述性）。</p>'
        '<p class="hint">这些数字只看对局结束时的最终棋盘：活得越久越容易凑出三星、满装与高费卡，所以高数值主要说明'
        '「这局本来就在赢」，不说明「照这样玩能赢」；跨费用对比主要反映费用差异，比较请先按费用筛选。'
        '「二」「三」= 场数 ≥ %d 的二/三件装组合里吃鸡率最高者（带 * 的样本不足，改显示最常见组合；场次见悬停提示）——'
        '相关非因果。悬停（手机上点按）头像看星级数据与 3★ 满装所在阵容，装备图标看合成配方。</p>'
        % ("{:,}".format(min_n), hw_place, hw_won, 500)) + riot_line
    tb = ('<div class="filters" id="htools"><div class="fg"><span class="fl">排序</span>'
          '<button type="button" class="fb on" data-f="s" data-v="win">吃鸡率</button>'
          '<button type="button" class="fb" data-f="s" data-v="sel">选率</button>'
          '<button type="button" class="fb" data-f="s" data-v="place">均名</button></div>'
          '<div class="fg"><span class="fl">费用</span>' + "".join(
              '<button type="button" class="fb%s" data-f="cost" data-v="%s">%s</button>'
              % (" on" if v == "" else "", v, t)
              for v, t in (("", "全部"), ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"))) + "</div></div>")
    return ('<section id="heroes"><h2>英雄数据</h2><div class="box">%s</div>%s<div id="hlist">%s</div></section>%s'
            % (legend, tb, "".join(rows), HERO_JS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--no-cache", action="store_true", help="忽略 cache/raw/ 重新抓取")
    ap.add_argument("--data", help="只用这个快照渲染、不联网，例如 cache/snapshots/set18/18.5c.json")
    ap.add_argument("--riot", help="tft-lab 的 heroes 导出 JSON（自采对局）：英雄页悬停面板的数据")
    a = ap.parse_args()
    if a.data:
        path = Path(a.data)
        checks.require(fetch_data.load(path))
    else:
        path = fetch_data.save(fetch_data.make_snapshot(fetch_data.collect_raw(a.no_cache)))
        print("snapshot →", path)
    riot = json.loads(Path(a.riot).read_text(encoding="utf-8")) if a.riot else None
    if riot is not None and riot.get("publishable") is False:
        print("注意：--riot 数据标记为不可公开（开发 key）——本次构建仅限本地预览，不要推送上线")
    render(fetch_data.load(path), Path(a.out), riot)
    print("snapshot sha256", fetch_data.sha256(path), "（README「页面数据快照」里记的应是这个值）")

def render(snap, out, riot=None):
    """页面只读快照（和可选的 --riot 自采导出），不联网。"""
    if riot is not None:
        check_riot(snap, riot)
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
              "heroes.html": heroes_page(meta, roster, us, total, snap["unit_builds"], riot, U),
              "craft.html": craft.section([tuple(c) for c in snap["craft"]["components"]], {tuple(r["pair"]): r for r in snap["craft"]["recipes"]}, m["set"])[0]}
    syn_mat, syn_pages = synergy.build(comps, roster, origin_order,
                                       [c for c in class_order if c != NO_CLASS], total, face, U)
    bodies["synergy.html"] = syn_mat
    tpl = TPL.replace("{{RIOT_NOTICE}}", e(RIOT_NOTICE)).replace("{{RIOT_BOILERPLATE}}", e(RIOT_BOILERPLATE))
    for k, v in (("{{SET}}", m["set"]), ("{{PATCH}}", m["patch_label"] or "tactics.tools 编号 %s" % m["patch"]),
                 ("{{SCOPE}}", ("排位 · %s" % m["rank_label"] if m["rank_label"] else "分段未注明") + " · 地区未注明"),
                 ("{{N}}", "{:,}".format(total)), ("{{DATE}}", (m["last_updated"] or m["fetched_at"]).replace("T", " ")[:16] + " UTC")):
        tpl = tpl.replace(k, e(v))
    # pages with item icons get the recipe tooltip; #itd is built per page so it holds exactly the items that page shows
    def finish(body):
        ids = sorted(set(re.findall(r'data-it="([^"]+)"', body)))
        if not ids:
            return tpl.replace("{{TIPCSS}}", "").replace("{{ITEMTIPS}}", "")
        tips = {"c": {c: [n, i] for c, n, i in snap["craft"]["components"]}, "i": item_tips(meta, snap["craft"], ids)}
        tips_json = json.dumps(tips, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
        return tpl.replace("{{TIPCSS}}", TIP_CSS).replace("{{ITEMTIPS}}", '<script type="application/json" id="itd">%s</script>%s' % (tips_json, TIP_JS))
    out.mkdir(parents=True, exist_ok=True); (out / "synergy").mkdir(exist_ok=True)
    for old in (out / "synergy").glob("*.html"): old.unlink()
    for fn, (t, body) in syn_pages.items():
        nav = "".join('<a href="../%s"%s>%s</a>' % (f, ' class="cur"' if f == "synergy.html" else "", tt) for f, tt, _ in PAGES)
        doc = finish(body).replace("{{CRAFTCSS}}", craft.CSS + synergy.CSS + HERO_CSS).replace("{{NAV}}", nav).replace("{{TITLE}}", t).replace("{{FILTERS}}", "").replace("{{SEARCH}}", "").replace("{{BODY}}", body).replace('href="index.html"', 'href="../index.html"')
        (out / fn).write_text(doc, encoding="utf-8")
    for fn, title, _ in PAGES:
        nav = "".join('<a href="%s"%s>%s</a>' % (f, ' class="cur"' if f == fn else "", t) for f, t, _ in PAGES)
        filt = FILTERS if fn in ("class.html", "origin.html") else ""
        search = SEARCH if filt or fn == "heroes.html" else ""
        doc = finish(bodies[fn]).replace("{{CRAFTCSS}}", craft.CSS + synergy.CSS + HERO_CSS).replace("{{NAV}}", nav).replace("{{TITLE}}", title).replace("{{FILTERS}}", filt).replace("{{SEARCH}}", search).replace("{{BODY}}", bodies[fn])
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
<p class="hint">它们只看对局结束时的最终棋盘：活得越久越容易凑出三星、满装、高费卡和高档羁绊，所以这些数字主要说明“这局本来就在赢”，不说明“照这样玩能赢”。阵容强度目前还无法从最终棋盘可靠测出，测出之前这里不放排行。</p>
<p class="hint">想看原始数字：「英雄数据」页提供每个英雄的选率 / 吃鸡率 / 均名、出装与 3★ 满装所在阵容——它们是对结果的描述（逐项标注样本量与上面的偏差），不是强度结论。</p></div></section>'''

PAGES = [("index.html", "首页", "说明与各页入口"),
         ("class.html", "职业站位", "各职业羁绊的前/中/后排英雄与常用出装"),
         ("origin.html", "种族站位", "各种族羁绊的前/中/后排英雄与常用出装"),
         ("heroes.html", "英雄数据", "全部英雄按选率 / 吃鸡率 / 均名排序，最高吃鸡率出装；悬停看星级数据与 3★ 满装所在阵容"),
         ("synergy.html", "羁绊搭配", "种族 × 种族、种族 × 职业 搭配矩阵（均名 / 吃鸡率 可切换 + 选率），点格子看所有英雄组合"),
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

# 英雄数据页：行、悬停面板、排序工具条
HERO_CSS = """
.hrow{display:grid;grid-template-columns:30px 48px minmax(110px,1fr) auto minmax(230px,1.1fr);gap:10px;align-items:center;background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:8px 12px;margin-bottom:8px}
.hrk{color:var(--mu);font-size:12px;text-align:right}
.hface{position:relative;width:44px;height:44px;cursor:help}.hface>.av{width:44px;height:44px}
.hp{display:none;position:absolute;left:52px;top:-6px;z-index:25;width:370px;max-width:82vw;background:var(--pn2);border:1px solid var(--bd);border-radius:10px;padding:10px 12px;box-shadow:0 10px 30px rgba(0,0,0,.55);font-size:12px;font-weight:400;cursor:auto}
.hface:hover .hp,.hface.open .hp{display:block}
.hp-t{font-weight:700;font-size:14px}
.hp-s{margin-top:8px;border-top:1px solid var(--bd);padding-top:6px;font-weight:700}.hp-s small{color:var(--mu);font-weight:400}
.hp-s table{width:100%;border-collapse:collapse;font-weight:400;margin-top:4px}.hp-s td{padding:1px 6px 1px 0;color:var(--mu);white-space:nowrap}
.hpc{font-weight:400;margin:6px 0;background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:6px}
.hpc .fcs{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:4px}
.hpc .cst{color:var(--mu)}.hpc .cst b{color:var(--tx)}
.hp .hint,.hp .emp3{font-weight:400;color:var(--mu);margin:6px 0 0;font-size:12px}
.hst{display:flex;gap:14px;align-items:baseline;white-space:nowrap}.hst span{color:var(--mu);font-size:12px}.hst b{color:var(--tx);font-size:14px}.hst small{color:var(--mu)}
.hbd .bd{margin-top:2px}.hbd .bd b{width:auto;min-width:24px}
@media(max-width:900px){.hrow{grid-template-columns:24px 44px 1fr}.hst{grid-column:2/4;flex-wrap:wrap;gap:8px 14px}.hbd{grid-column:2/4}
.hp{position:fixed;left:12px;right:12px;top:14%;width:auto;max-width:none}}
"""
HERO_JS = r'''<script>
(function(){
  // 英雄数据页：排序 / 费用筛选 / 搜索都只重排显示；悬停（手机上点按）头像看面板
  var list=document.getElementById('hlist'); if(!list) return;
  var rows=[].slice.call(list.querySelectorAll('.hrow'));
  var state={s:'win',cost:'',q:''};
  function apply(){
    var vis=[];
    rows.forEach(function(r){
      var ok=(!state.cost || r.dataset.cost===state.cost) && (!state.q || r.dataset.k.indexOf(state.q)>=0);
      r.classList.toggle('hide',!ok); if(ok) vis.push(r);
    });
    vis.sort(function(a,b){ var ka=parseFloat(a.dataset[state.s]), kb=parseFloat(b.dataset[state.s]);
      return state.s==='place' ? ka-kb : kb-ka; });
    vis.forEach(function(r,i){ r.querySelector('.hrk').textContent=i+1; list.appendChild(r); });
    rows.forEach(function(r){ if(r.classList.contains('hide')) list.appendChild(r); });
  }
  document.getElementById('htools').addEventListener('click', function(ev){
    var b=ev.target.closest('.fb'); if(!b) return;
    state[b.dataset.f]=b.dataset.v;
    b.parentNode.querySelectorAll('.fb').forEach(function(x){ x.classList.toggle('on', x===b); });
    apply();
  });
  var q=document.getElementById('q');
  if(q) q.addEventListener('input', function(){ state.q=q.value.trim(); apply(); });
  var touch=false, open=null;
  document.addEventListener('pointerdown', function(ev){ touch=ev.pointerType!=='mouse'; }, true);
  document.addEventListener('click', function(ev){
    if(!touch) return;
    if(ev.target.closest('.hp')) return;               // 点面板内部（如装备图标）不关闭
    var f=ev.target.closest('.hface');
    if(open && open!==f){ open.classList.remove('open'); open=null; }
    if(f){ f.classList.toggle('open'); open=f.classList.contains('open')?f:null; }
  });
  apply();
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
