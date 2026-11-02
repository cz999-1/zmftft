"""种族 × 种族、种族 × 职业 搭配矩阵 + 每格详情页（静态生成）。
数据: tactics.tools team-compositions（主流阵容）。
定义: 一个阵容"带了"某羁绊（种族或职业）= 场上该羁绊英雄 ≥2（单一英雄羁绊 ≥1）。
一格 A×B = 同时带 A 和 B 的所有阵容；变体 = 该阵容中属于 A 或 B 的英雄集合。
指标: 均名(按场次加权) / 吃鸡率（页内按钮切换，无 JS 时显示均名）+ 选率 = 场次 / 总对局棋盘数。
均名与吃鸡率都来自最终棋盘，只和主流阵容的基线比，不代表强度。
行/列标题的 title 显示该羁绊前/中/后排各有几个不同英雄（站位为本站人工标注）。"""
import hashlib
from html import escape as e
from itertools import combinations, product
from collections import defaultdict

MIN = 2  # 多英雄羁绊至少几名英雄才算"带了"
POS = (("front", "前排"), ("mid", "中排"), ("back", "后排"))

def slug(a, b):
    return hashlib.md5(("%s|%s" % (a, b)).encode()).hexdigest()[:8]

def pos_title(name, roster, key):
    """标题 tooltip：该羁绊（key = "origins"/"classes"）前/中/后排各有几个不同英雄。"""
    by = {p: set() for p, _ in POS}
    for r in roster:
        if name in r[key] and r["pos"] in by:
            by[r["pos"]].add(r["id"])
    return "%s：%s" % (name, " · ".join("%s %d" % (lab, len(by[p])) for p, lab in POS))

def _tally(s, b, n):
    s[0] += n; s[1] += b["place"] * n; s[2] += b["top4"]; s[3] += b["win"]

def aggregate(boards, roster, ori_order, cls_order):
    om = {r["id"]: r["origins"] for r in roster}
    cm = {r["id"]: r["classes"] for r in roster}
    solo_o = {o for o in ori_order if sum(o in r["origins"] for r in roster) == 1}
    solo_c = {c for c in cls_order if sum(c in r["classes"] for r in roster) == 1}
    oo = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0, 0]))  # (种族, 种族) -> 变体 -> [场次, 名次*场次, 前四数, 吃鸡数]
    oc = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0, 0]))  # (种族, 职业) -> 同上
    for b in boards:
        n = b["count"]; byo = defaultdict(set); byc = defaultdict(set)
        for u in b["units"]:
            for o in om.get(u, []): byo[o].add(u)
            for c in cm.get(u, []): byc[c].add(u)
        ao = [o for o in ori_order if len(byo[o]) >= (1 if o in solo_o else MIN)]
        ac = [c for c in cls_order if len(byc[c]) >= (1 if c in solo_c else MIN)]
        for x, y in combinations(ao, 2):
            _tally(oo[(x, y)][tuple(sorted(byo[x] | byo[y]))], b, n)
        for x, y in product(ao, ac):
            _tally(oc[(x, y)][tuple(sorted(byo[x] | byc[y]))], b, n)
    return oo, oc

def build(comps, roster, ori_order, cls_order, total, face, U):
    oo, oc = aggregate(comps, roster, ori_order, cls_order)
    nb = sum(c["count"] for c in comps) or 1
    base = sum(c["place"] * c["count"] for c in comps) / nb  # 主流阵容棋盘的平均名次
    wbase = sum(c["win"] for c in comps) / nb * 100  # 主流阵容棋盘的总吃鸡率（对 12.5% 均匀基线）
    ot = {o: pos_title(o, roster, "origins") for o in ori_order}
    ct = {c: pos_title(c, roster, "classes") for c in cls_order}
    detail = {}

    def td(k, vs):
        n = sum(s[0] for s in vs.values())
        if not n: return '<td class="na">·</td>'
        sg = slug(*k)
        if sg in detail and detail[sg][0] != k:  # 两个矩阵共用 synergy/<md5[:8]>.html 命名空间：冲突就停，绝不悄悄覆盖
            raise SystemExit("synergy 详情页 slug 冲突：%s 与 %s" % (" × ".join(detail[sg][0]), " × ".join(k)))
        pl = sum(s[1] for s in vs.values()) / n
        wn = sum(s[3] for s in vs.values()) / n * 100
        detail[sg] = (k, vs)
        return ('<td><a href="synergy/%s.html" title="%s × %s · 均名 %.2f · 吃鸡率 %.1f%% · %d 个棋盘 · %d 种组合">'
                '<b class="mp">%.2f</b><b class="mw">%.0f%%</b><small>%.1f%%</small></a></td>') % (
            sg, e(k[0]), e(k[1]), pl, wn, n, len(vs), pl, wn, n / total * 100)

    order1 = [o for o in ori_order if any(o in k for k in oo)]
    head = "".join('<th class="vh" title="%s"><span>%s</span></th>' % (e(ot[o]), e(o)) for o in order1)
    rows = []
    for i, a in enumerate(order1):
        tds = []
        for j, b in enumerate(order1):
            if i == j: tds.append('<td class="dg"></td>'); continue
            k = (a, b) if i < j else (b, a)
            tds.append(td(k, oo.get(k, {})))
        rows.append('<tr><th class="rh" title="%s">%s</th>%s</tr>' % (e(ot[a]), e(a), "".join(tds)))
    sec1 = '''<section id="syn"><h2>种族 × 种族 搭配矩阵</h2>
<p class="hint">格内：<b>均名</b>或<b>吃鸡率</b>（上方按钮切换，两个矩阵一起切）+ 选率。点格子看该搭配下所有英雄组合。灰对角线=同种族；“·”=无样本。悬停行/列标题看该羁绊的前/中/后排英雄数（本站人工标注）。<br>
口径：阵容中某种族英雄 ≥2（单一英雄种族 ≥1）即算“带了”该种族。数据是 tactics.tools 的主流阵容，共 %s 个棋盘（全部 %s 个棋盘的 %.1f%%），它们的平均名次是 <b>%.2f</b>、吃鸡率是 <b>%.1f%%</b>（均匀基线 12.5%%），格内数字要和这两个数比，不是和 4.5 或 12.5%% 比。均名和吃鸡率都来自对局结束时的最终棋盘，数字好的搭配多半是“这局本来就在赢”的棋盘，不说明照这样搭就能赢。选率 = 场次 / 全部棋盘数。</p>
<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div></section>''' % (
        "{:,}".format(nb), "{:,}".format(total), nb / total * 100, base, wbase, head, "".join(rows))
    if oc:
        orows = [o for o in ori_order if any(k[0] == o for k in oc)]
        ocols = [c for c in cls_order if any(k[1] == c for k in oc)]
        head2 = "".join('<th class="vh" title="%s"><span>%s</span></th>' % (e(ct[c]), e(c)) for c in ocols)
        rows2 = "".join('<tr><th class="rh" title="%s">%s</th>%s</tr>' % (
            e(ot[a]), e(a), "".join(td((a, c), oc.get((a, c), {})) for c in ocols)) for a in orows)
        body2 = '<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div>' % (head2, rows2)
    else:
        body2 = '<p class="hint">没有达到口径的种族 × 职业搭配。</p>'
    sec2 = '''<section id="synoc"><h2>种族 × 职业 搭配矩阵</h2>
<p class="hint">行 = 种族，列 = 职业。口径同上，职业一样：阵容中该职业英雄 ≥2（单一英雄职业 ≥1）即算“带了”；变体 = 阵容中属于该种族或该职业的英雄集合。格内指标、基线与注意事项见上一个矩阵的说明；“·”=无样本。</p>
%s</section>''' % body2
    toggle = ('<div class="filters"><div class="fg"><span class="fl">格内指标</span>'
              '<button type="button" class="fb on" data-v="place">均名</button>'
              '<button type="button" class="fb" data-v="win">吃鸡率</button></div></div>')
    mat = '<div id="synx">%s%s%s</div>%s' % (toggle, sec1, sec2, JS)
    pages = {}
    for sg, (k, vs) in detail.items():
        n = sum(s[0] for s in vs.values()) or 1
        tr = "".join('<tr><td class="us">%s<div class="sub">%s</div></td><td>%.2f</td><td>%.0f%%</td><td>%.0f%%</td><td>%d</td><td>%.2f%%</td><td>%.0f%%</td></tr>' % (
            "".join(face(U(u), "sm") for u in v), e("、".join(U(u)["name"] for u in v)), s[1] / s[0], s[2] / s[0] * 100, s[3] / s[0] * 100,
            s[0], s[0] / total * 100, s[0] / n * 100) for v, s in sorted(vs.items(), key=lambda x: -x[1][0]))
        tbl = '<h3>tactics.tools 主流阵容</h3><div class="smx"><table class="vt"><tr><th>英雄组合（%s/%s 内）</th><th>均名</th><th>前四</th><th>吃鸡</th><th>场次</th><th>选率</th><th>格内占比</th></tr>%s</table></div>' % (e(k[0]), e(k[1]), tr)
        body = '<section><p><a href="../synergy.html" style="color:var(--ac)">← 返回矩阵</a></p><h2>%s × %s</h2>%s<p class="hint">选率 = 场次 / 全部棋盘数；格内占比 = 该组合在这格里的场次份额。主流阵容棋盘的平均名次是 %.2f、吃鸡率是 %.1f%%（均匀基线 12.5%%）；这些都是最终棋盘统计，不代表强度。</p></section>' % (
            e(k[0]), e(k[1]), tbl, base, wbase)
        pages["synergy/%s.html" % sg] = ("%s × %s" % k, body)
    return mat, pages

JS = '''<script>(function(){
var w=document.getElementById('synx');if(!w)return;
w.addEventListener('click',function(ev){var b=ev.target.closest('.fb');if(!b)return;
w.classList.toggle('m-win',b.dataset.v==='win');
w.querySelectorAll('.fb').forEach(function(x){x.classList.toggle('on',x===b);});});
})();</script>'''

CSS = '''.smx{overflow:auto}table.syn{border-collapse:collapse;font-size:12px}.syn td,.syn th{border:1px solid var(--bd);text-align:center;min-width:44px;height:40px;padding:0}
.syn .vh{height:110px;vertical-align:bottom}.syn .vh span{writing-mode:vertical-rl;padding:4px}.syn .rh{text-align:right;padding:0 6px;white-space:nowrap;position:sticky;left:0;background:var(--pn)}
.syn td a{display:block;color:inherit;text-decoration:none;padding:3px}.syn td a:hover{background:var(--pn2)}.syn small{display:block;color:var(--mu);font-size:10px}
.syn .dg{background:#222a35}.syn .na{color:#444}
#synx b.mw{display:none}#synx.m-win b.mp{display:none}#synx.m-win b.mw{display:inline}
table.vt{border-collapse:collapse;width:100%}.vt td,.vt th{border-bottom:1px solid var(--bd);padding:6px;text-align:center}.vt .us{text-align:left}'''
