"""种族 × 种族 搭配矩阵 + 每格详情页（静态生成）。
数据: tactics.tools team-compositions（主流阵容）。
定义: 一个阵容"包含"某种族 = 场上该种族英雄 ≥2（单一英雄种族 ≥1）。
一格 A×B = 同时包含 A 和 B 的所有阵容；变体 = 该阵容中属于 A 或 B 的英雄集合。
指标: 均名(按场次加权)、前四率、吃鸡率、选率 = 场次 / 总对局棋盘数。均名来自最终棋盘，只和主流阵容的平均名次比，不代表强度。"""
import hashlib
from html import escape as e
from itertools import combinations
from collections import defaultdict

MIN = 2  # 多英雄种族至少几名英雄才算"带了"

def slug(a, b):
    return hashlib.md5(("%s|%s" % (a, b)).encode()).hexdigest()[:8]

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

def build(comps, roster, order, total, face, U, page):
    cells = aggregate(comps, roster, order, "tt")
    order = [o for o in order if any(o in k for k in cells)]
    nb = sum(c["count"] for c in comps) or 1
    base = sum(c["place"] * c["count"] for c in comps) / nb  # 这些主流阵容棋盘的平均名次
    detail = {}
    head = "".join('<th class="vh"><span>%s</span></th>' % e(o) for o in order)
    rows = []
    for i, a in enumerate(order):
        tds = []
        for j, b in enumerate(order):
            if i == j: tds.append('<td class="dg"></td>'); continue
            k = (a, b) if i < j else (b, a)
            vs = cells.get(k, {})
            n = sum(s[0] for s in vs.values())
            if not n: tds.append('<td class="na">·</td>'); continue
            sg = slug(*k); fn = "synergy/%s.html" % sg
            pl = sum(s[1] for s in vs.values()) / n
            tds.append('<td><a href="%s" title="%s × %s · %d 个棋盘 · %d 种组合"><b>%.2f</b><small>%.1f%%</small></a></td>' % (
                fn, e(k[0]), e(k[1]), n, len(vs), pl, n / total * 100))
            detail[sg] = (k, vs)
        rows.append('<tr><th class="rh">%s</th>%s</tr>' % (e(a), "".join(tds)))
    mat = '''<section id="syn"><h2>种族 × 种族 搭配矩阵</h2>
<p class="hint">格内：<b>均名</b> + 选率。点格子看该搭配下所有英雄组合。灰对角线=同种族；“·”=无样本。<br>
口径：阵容中某种族英雄 ≥2（单一英雄种族 ≥1）即算“带了”该种族。数据是 tactics.tools 的主流阵容，共 %s 个棋盘（全部 %s 个棋盘的 %.1f%%），它们的平均名次是 <b>%.2f</b>，格内均名要和这个数比，不是和 4.5 比。均名来自对局结束时的最终棋盘，名次好的搭配多半是“这局本来就在赢”的棋盘，不说明照这样搭就能赢。选率 = 场次 / 全部棋盘数。</p>
<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div></section>''' % (
        "{:,}".format(nb), "{:,}".format(total), nb / total * 100, base, head, "".join(rows))
    pages = {}
    for sg, (k, vs) in detail.items():
        n = sum(s[0] for s in vs.values()) or 1
        tr = "".join('<tr><td class="us">%s<div class="sub">%s</div></td><td>%.2f</td><td>%.0f%%</td><td>%.0f%%</td><td>%d</td><td>%.2f%%</td><td>%.0f%%</td></tr>' % (
            "".join(face(U(u), "sm") for u in v), e("、".join(U(u)["name"] for u in v)), s[1] / s[0], s[2] / s[0] * 100, s[3] / s[0] * 100,
            s[0], s[0] / total * 100, s[0] / n * 100) for v, s in sorted(vs.items(), key=lambda x: -x[1][0]))
        tbl = '<h3>tactics.tools 主流阵容</h3><div class="smx"><table class="vt"><tr><th>英雄组合（%s/%s 内）</th><th>均名</th><th>前四</th><th>吃鸡</th><th>场次</th><th>选率</th><th>格内占比</th></tr>%s</table></div>' % (e(k[0]), e(k[1]), tr)
        body = '<section><p><a href="../synergy.html" style="color:var(--ac)">← 返回矩阵</a></p><h2>%s × %s</h2>%s<p class="hint">选率 = 场次 / 全部棋盘数；格内占比 = 该组合在这格里的场次份额。主流阵容棋盘的平均名次是 %.2f，吃鸡率的全体基线是 12.5%%；这些都是最终棋盘统计，不代表强度。</p></section>' % (
            e(k[0]), e(k[1]), tbl, base)
        pages["synergy/%s.html" % sg] = ("%s × %s" % k, body)
    return mat, pages

CSS = '''.smx{overflow:auto}table.syn{border-collapse:collapse;font-size:12px}.syn td,.syn th{border:1px solid var(--bd);text-align:center;min-width:44px;height:40px;padding:0}
.syn .vh{height:110px;vertical-align:bottom}.syn .vh span{writing-mode:vertical-rl;padding:4px}.syn .rh{text-align:right;padding:0 6px;white-space:nowrap;position:sticky;left:0;background:var(--pn)}
.syn td a{display:block;color:inherit;text-decoration:none;padding:3px}.syn td a:hover{background:var(--pn2)}.syn small{display:block;color:var(--mu);font-size:10px}
.syn .dg{background:#222a35}.syn .na{color:#444}
table.vt{border-collapse:collapse;width:100%}.vt td,.vt th{border-bottom:1px solid var(--bd);padding:6px;text-align:center}.vt .us{text-align:left}'''
