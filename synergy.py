"""种族 × 种族 搭配矩阵 + 每格详情页（静态生成）。
数据: tactics.tools team-compositions（大样本）+ Riot Match 抽样（data/riot/cache/sample_matches.json，若有）。
定义: 一个阵容"包含"某种族 = 场上该种族英雄 ≥2（单一英雄种族 ≥1）。
一格 A×B = 同时包含 A 和 B 的所有阵容；变体 = 该阵容中属于 A 或 B 的英雄集合。
指标: 均名(按场次加权)、前四率、吃鸡率、选率 = 场次 / 总对局棋盘数。"""
import json, os, hashlib
from html import escape as e
from itertools import combinations
from collections import defaultdict

MIN = 2  # 多英雄种族至少几名英雄才算"带了"
RIOT = os.path.join(os.path.dirname(__file__), "data", "riot", "cache", "sample_matches.json")

def slug(a, b):
    return hashlib.md5(("%s|%s" % (a, b)).encode()).hexdigest()[:8]

def riot_boards():
    try: d = json.load(open(RIOT))
    except Exception: return []
    out = []
    for m in d:
        for p in (m.get("info") or {}).get("participants", []):
            out.append({"units": [u["character_id"] for u in p.get("units", [])], "count": 1,
                        "place": p["placement"], "top4": int(p["placement"] <= 4), "win": int(p["placement"] == 1)})
    return out

def aggregate(boards, roster, order, src):
    ori = {r["id"]: r["origins"] for r in roster}
    solo = {o for o in order if sum(o in r["origins"] for r in roster) == 1}
    cells = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0, 0, src]))
    for b in boards:
        n = b["count"]; byo = defaultdict(set)
        for u in b["units"]:
            for o in ori.get(u, []): byo[o].add(u)
        act = [o for o in order if len(byo[o]) >= (1 if o in solo else MIN)]
        for x, y in combinations(act, 2):
            v = tuple(sorted(byo[x] | byo[y]))
            s = cells[(x, y)][v]
            s[0] += n; s[1] += b["place"] * n; s[2] += b["top4"]; s[3] += b["win"]
    return cells

def pcls(p): return "good" if p < 4.2 else ("bad" if p > 4.7 else "")

def build(comps, roster, order, total, face, U, page):
    cells = aggregate(comps, roster, order, "tt")
    rb = riot_boards(); rcells = aggregate(rb, roster, order, "riot")
    order = [o for o in order if any(o in k for k in list(cells) + list(rcells))]
    detail = {}
    head = "".join('<th class="vh"><span>%s</span></th>' % e(o) for o in order)
    rows = []
    for i, a in enumerate(order):
        tds = []
        for j, b in enumerate(order):
            if i == j: tds.append('<td class="dg"></td>'); continue
            k = (a, b) if i < j else (b, a)
            vs = cells.get(k, {}); rv = rcells.get(k, {})
            n = sum(s[0] for s in vs.values())
            if not n and not rv: tds.append('<td class="na">·</td>'); continue
            sg = slug(*k); fn = "synergy/%s.html" % sg
            if n:
                pl = sum(s[1] for s in vs.values()) / n
                tds.append('<td class="%s"><a href="%s" title="%s × %s · %d 场 · %d 种组合"><b>%.2f</b><small>%.1f%%</small></a></td>' % (
                    pcls(pl), fn, e(k[0]), e(k[1]), n, len(vs), pl, n / total * 100))
            else:
                tds.append('<td class="sp"><a href="%s" title="仅 Riot 抽样 %d 局">R</a></td>' % (fn, sum(s[0] for s in rv.values())))
            detail[sg] = (k, vs, rv)
        rows.append('<tr><th class="rh">%s</th>%s</tr>' % (e(a), "".join(tds)))
    rn = len(rb)
    mat = '''<section id="syn"><h2>种族 × 种族 搭配矩阵</h2>
<p class="hint">格内：<b>均名</b>（越小越好，绿&lt;4.2 红&gt;4.7）+ 选率。点格子看该搭配下所有英雄组合。灰对角线=同种族；“R”=仅 Riot 抽样有数据；“·”=无样本。<br>
口径：阵容中某种族英雄 ≥2（单一英雄种族 ≥1）即算“带了”该种族。主数据 tactics.tools 主流阵容（%d 局棋盘），选率 = 场次 / 总棋盘数；Riot Match 抽样 %d 个棋盘单列在详情页做对照（样本小，仅参考）。</p>
<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div></section>''' % (total, rn, head, "".join(rows))
    pages = {}
    for sg, (k, vs, rv) in detail.items():
        def tbl(vs, tot, lbl):
            if not vs: return '<p class="hint">%s：无样本</p>' % lbl
            n = sum(s[0] for s in vs.values()) or 1
            tr = "".join('<tr><td class="us">%s<div class="sub">%s</div></td><td class="%s">%.2f</td><td>%.0f%%</td><td>%.0f%%</td><td>%d</td><td>%.2f%%</td><td>%.0f%%</td></tr>' % (
                "".join(face(U(u), "sm") for u in v), e("、".join(U(u)["name"] for u in v)), pcls(s[1] / s[0]), s[1] / s[0], s[2] / s[0] * 100, s[3] / s[0] * 100,
                s[0], s[0] / tot * 100, s[0] / n * 100) for v, s in sorted(vs.items(), key=lambda x: -x[1][0]))
            return '<h3>%s</h3><div class="smx"><table class="vt"><tr><th>英雄组合（%s/%s 内）</th><th>均名</th><th>前四</th><th>吃鸡</th><th>场次</th><th>选率</th><th>格内占比</th></tr>%s</table></div>' % (lbl, e(k[0]), e(k[1]), tr)
        body = '<section><p><a href="../synergy.html" style="color:var(--ac)">← 返回矩阵</a></p><h2>%s × %s</h2>%s%s<p class="hint">选率 = 场次 / 总棋盘数；格内占比 = 该组合在这格里的场次份额。</p></section>' % (
            e(k[0]), e(k[1]), tbl(vs, total, "tactics.tools 主流阵容"), tbl(rv, max(rn, 1), "Riot Match 抽样（%d 棋盘）" % rn))
        pages["synergy/%s.html" % sg] = ("%s × %s" % k, body)
    return mat, pages

CSS = '''.smx{overflow:auto}table.syn{border-collapse:collapse;font-size:12px}.syn td,.syn th{border:1px solid var(--bd);text-align:center;min-width:44px;height:40px;padding:0}
.syn .vh{height:110px;vertical-align:bottom}.syn .vh span{writing-mode:vertical-rl;padding:4px}.syn .rh{text-align:right;padding:0 6px;white-space:nowrap;position:sticky;left:0;background:var(--pn)}
.syn td a{display:block;color:inherit;text-decoration:none;padding:3px}.syn td a:hover{background:var(--pn2)}.syn small{display:block;color:var(--mu);font-size:10px}
.syn .dg{background:#222a35}.syn .na{color:#444}.syn td.good b{color:var(--good)}.syn td.bad b{color:var(--bad)}.syn .sp a{color:var(--mu)}
table.vt{border-collapse:collapse;width:100%}.vt td,.vt th{border-bottom:1px solid var(--bd);padding:6px;text-align:center}.vt .us{text-align:left}.vt td.good{color:var(--good)}.vt td.bad{color:var(--bad)}'''
