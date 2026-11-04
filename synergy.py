"""种族 × 种族、种族 × 职业 搭配矩阵 + 每格详情页（静态生成）。
数据: tactics.tools team-compositions（主流阵容）。
定义: 一个阵容"带了"某羁绊（种族或职业）= 场上该羁绊英雄 ≥2（单一英雄羁绊 ≥1）。
一格 A×B = 同时带 A 和 B 的所有阵容；变体 = 该阵容中属于 A 或 B 的英雄集合。
指标: 均名(按场次加权) / 吃鸡率 / 协同差（页内按钮切换，无 JS 时显示均名）+ 选率 = 场次 / 总对局棋盘数。
协同差 = 格内均名 − (两羁绊各自边际均名之和 − 基线)，负 = 优于"两边平均水平叠加"的预期。
均名与吃鸡率都来自最终棋盘，只和主流阵容的基线比，不代表强度。
只由一个阵容组支撑的格子灰字（数字只描述那一套阵容的最终棋盘，不是这对羁绊的性质）；场次 < THIN 的格子淡化。
一个羁绊的棋盘全部同时带另一个时（嵌套），协同差恒等于“基线 − 另一羁绊的边际均名”，无从定义，显示 —。
comps 由 build_site 传入时已去掉 tactics.tools 列表里逐字重复的行。
行/列标题的 title 显示该羁绊前/中/后排各有几个不同英雄（站位为本站人工标注）。
只有一个五费英雄的羁绊整行/列标橙：五费英雄搭配什么都强，这类格子参考价值低。
传入自采导出（crawl, schema tftlab-synergy/1）时，额外渲染「自采对局搭配矩阵」：口径为游戏自己的
激活档位（tier_current ≥ 1），格内三项指标都带 95% 区间；职业×职业与未展示羁绊的配对只计数不入矩阵。"""
import hashlib
from html import escape as e
from itertools import combinations, product
from collections import defaultdict

MIN = 2  # 多英雄羁绊至少几名英雄才算"带了"
THIN = 1000  # 场次低于此数的格子淡化
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

def _solo5(order, roster, key):
    """只有一个英雄、且该英雄费用 >= 5 的羁绊（标记用：五费英雄搭配什么都强）。"""
    out = set()
    for t in order:
        us = [r for r in roster if t in r[key]]
        if len(us) == 1 and (us[0].get("cost") or 0) >= 5:
            out.add(t)
    return out

def _tally(s, b, n):
    s[0] += n; s[1] += b["place"] * n; s[2] += b["top4"]; s[3] += b["win"]

def aggregate(boards, roster, ori_order, cls_order):
    om = {r["id"]: r["origins"] for r in roster}
    cm = {r["id"]: r["classes"] for r in roster}
    solo_o = {o for o in ori_order if sum(o in r["origins"] for r in roster) == 1}
    solo_c = {c for c in cls_order if sum(c in r["classes"] for r in roster) == 1}
    oo = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0, 0]))  # (种族, 种族) -> 变体 -> [场次, 名次*场次, 前四数, 吃鸡数]
    oc = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0, 0]))  # (种族, 职业) -> 同上
    marg = defaultdict(lambda: [0, 0.0])  # 羁绊 -> [场次, 名次*场次]（带该羁绊的所有主流阵容棋盘，协同差的边际）
    grp = defaultdict(set)  # 配对 -> 支撑它的阵容系（tactics.tools group）
    for b in boards:
        n = b["count"]; byo = defaultdict(set); byc = defaultdict(set)
        for u in b["units"]:
            for o in om.get(u, []): byo[o].add(u)
            for c in cm.get(u, []): byc[c].add(u)
        ao = [o for o in ori_order if len(byo[o]) >= (1 if o in solo_o else MIN)]
        ac = [c for c in cls_order if len(byc[c]) >= (1 if c in solo_c else MIN)]
        for t in ao + ac:
            m = marg[t]; m[0] += n; m[1] += b["place"] * n
        g = b.get("group")
        for x, y in combinations(ao, 2):
            grp[(x, y)].add(g)
            _tally(oo[(x, y)][tuple(sorted(byo[x] | byo[y]))], b, n)
        for x, y in product(ao, ac):
            grp[(x, y)].add(g)
            _tally(oc[(x, y)][tuple(sorted(byo[x] | byc[y]))], b, n)
    return oo, oc, marg, grp

def crawl_section(crawl, zh, ori_order, cls_order, ot, ct, s5o, s5c, label):
    """tft-lab 自采导出（python -m tftlab.report.synergy_export）→「自采对局搭配矩阵」一节。
    zh = 官方羁绊表（apiName -> 中文名，快照 official.traits）；配对按中文名归入 种族×种族 /
    种族×职业，职业×职业与未展示羁绊的配对只计数。格子无详情页，悬停看区间与样本量。"""
    oset, cset = set(ori_order), set(cls_order)
    kind = lambda z: "o" if z in oset else "c" if z in cset else "?"
    oi = {o: i for i, o in enumerate(ori_order)}
    total = (crawl.get("population") or {}).get("boards") or 1
    coo, coc, cc, un, nun = {}, {}, [0, 0], set(), 0
    for p in crawl["pairs"]:
        za, zb = zh[p["a"]], zh[p["b"]]
        kk = kind(za) + kind(zb)
        if "?" in kk:
            un |= {z for z in (za, zb) if kind(z) == "?"}; nun += 1
        elif kk == "oo":
            coo[(za, zb) if oi[za] < oi[zb] else (zb, za)] = p
        elif kk == "cc":
            cc[0] += 1; cc[1] += p["n_boards"]
        else:
            coc[(za, zb) if kk == "oc" else (zb, za)] = p

    def td(k, p, mark):
        if p is None:
            return '<td class="na">·</td>'
        cl = " ".join(c for c, f in (("s5c", mark), ("thin", p["n_boards"] < THIN)) if f)
        t = ("%s × %s · 均名 %.2f（95%% %.2f–%.2f）· 吃鸡率 %.1f%%（95%% %.1f–%.1f）· "
             "协同差 %+.2f（95%% %+.2f–%+.2f）· %s 盘 / %s 场 · C 级描述") % (
            e(k[0]), e(k[1]), p["place_mean"], p["place_ci95"][0], p["place_ci95"][1],
            p["win_rate"] * 100, p["win_ci95"][0] * 100, p["win_ci95"][1] * 100,
            p["lift"], p["lift_ci95"][0], p["lift_ci95"][1],
            "{:,}".format(p["n_boards"]), "{:,}".format(p["n_matches"]))
        return ('<td%s><span class="cv" title="%s"><b class="mp">%.2f</b><b class="mw">%.0f%%</b>'
                '<b class="ml">%+.2f</b><small>%.1f%%</small></span></td>') % (
            (' class="%s"' % cl) if cl else "", t, p["place_mean"], p["win_rate"] * 100, p["lift"],
            p["n_boards"] / total * 100)

    o1 = [o for o in ori_order if any(o in k for k in coo)]
    if o1:
        head = "".join('<th class="vh%s" title="%s"><span>%s</span></th>' % (
            " s5" if o in s5o else "", e(ot[o]), e(o)) for o in o1)
        rows = []
        for i, a in enumerate(o1):
            tds = []
            for j, b in enumerate(o1):
                if i == j: tds.append('<td class="dg"></td>'); continue
                k = (a, b) if i < j else (b, a)
                tds.append(td(k, coo.get(k), a in s5o or b in s5o))
            rows.append('<tr><th class="rh%s" title="%s">%s</th>%s</tr>' % (
                " s5" if a in s5o else "", e(ot[a]), e(a), "".join(tds)))
        t1 = '<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div>' % (head, "".join(rows))
    else:
        t1 = '<p class="hint">没有达到阈值的种族 × 种族配对。</p>'
    orows = [o for o in ori_order if any(k[0] == o for k in coc)]
    ocols = [c for c in cls_order if any(k[1] == c for k in coc)]
    if orows:
        head2 = "".join('<th class="vh%s" title="%s"><span>%s</span></th>' % (
            " s5" if c in s5c else "", e(ct[c]), e(c)) for c in ocols)
        rows2 = "".join('<tr><th class="rh%s" title="%s">%s</th>%s</tr>' % (
            " s5" if a in s5o else "", e(ot[a]), e(a),
            "".join(td((a, c), coc.get((a, c)), a in s5o or c in s5c) for c in ocols)) for a in orows)
        t2 = '<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div>' % (head2, rows2)
    else:
        t2 = '<p class="hint">没有达到阈值的种族 × 职业配对。</p>'
    th = crawl.get("threshold_report") or {}
    bl = crawl.get("baseline") or {}
    pr = crawl.get("params") or {}
    exc = ["n &lt; %s 的 %s 对已在导出时隐去（重叠计 %s 盘）" % (
        pr.get("min_n"), th.get("pairs_suppressed"), "{:,}".format(th.get("boards_in_suppressed_pairs") or 0))]
    if cc[0]:
        exc.append("职业 × 职业的 %d 对不入矩阵（重叠计 %s 盘）" % (cc[0], "{:,}".format(cc[1])))
    if nun:
        exc.append("涉及未展示羁绊（%s）的 %d 对不入矩阵" % (e("、".join(sorted(un))), nun))
    warn = ""
    if crawl.get("publishable") is False:
        warn = ('<p class="hint" style="color:var(--bad)">注意：自采矩阵来自开发 key，按 Riot 开发者政策'
                '不可用于公开网站——这份构建仅限本地预览，不要推送上线。</p>')
    hint = ('<p class="hint">口径与上方矩阵不同：这里“带了” = <b>对局结束时游戏判定该羁绊已激活</b>'
            '（tier_current ≥ 1，纹章也算数），统计的是自采的全部排位棋盘，不限主流阵容。%s。<br>'
            '格内仍为 均名 / 吃鸡率 / 协同差（上方按钮一起切换）+ 选率；悬停看每格三项指标的 95%% 区间'
            '（按“场”整群自助法，B = %s）和盘数/场数。全部棋盘的基线：均名 %.2f、吃鸡率 %.1f%%'
            '（每场 8 人，这两个数按定义如此）。协同差 = 格内均名 − (两羁绊各自边际均名之和 − 基线)，'
            '负数 = 好于“两边平均水平叠加”的预期；边际含该格自身，是描述性对比，不是因果交互。'
            '<b class="s5l">橙色</b>行/列含义同上；淡化格 = 盘数 &lt; %d。<br>取舍：%s。'
            '活得越久激活的羁绊越多：格子描述“结束时两个羁绊都亮着”的棋盘停在哪里，'
            '不说明点亮它们能赢。</p>') % (
        e(label), pr.get("n_boot"), bl.get("place_mean") or 0, (bl.get("win_rate") or 0) * 100, THIN, "；".join(exc))
    return ('<section id="syncrawl"><h2>自采对局搭配矩阵（Riot API）</h2>%s%s'
            '<h3>种族 × 种族</h3>%s<h3>种族 × 职业</h3>%s</section>') % (hint, warn, t1, t2)

def build(comps, roster, ori_order, cls_order, total, face, U, crawl=None, crawl_zh=None, crawl_label=""):
    oo, oc, marg, grp = aggregate(comps, roster, ori_order, cls_order)
    ngrp = len({c.get("group") for c in comps})
    nb = sum(c["count"] for c in comps) or 1
    base = sum(c["place"] * c["count"] for c in comps) / nb  # 主流阵容棋盘的平均名次
    wbase = sum(c["win"] for c in comps) / nb * 100  # 主流阵容棋盘的总吃鸡率（对 12.5% 均匀基线）
    ot = {o: pos_title(o, roster, "origins") for o in ori_order}
    ct = {c: pos_title(c, roster, "classes") for c in cls_order}
    s5o = _solo5(ori_order, roster, "origins")
    s5c = _solo5(cls_order, roster, "classes")
    for t in s5o: ot[t] += "；只有一个五费英雄"
    for t in s5c: ct[t] += "；只有一个五费英雄"
    detail = {}

    def td(k, vs, mark=False):
        n = sum(s[0] for s in vs.values())
        if not n: return '<td class="na">·</td>'
        sg = slug(*k)
        if sg in detail and detail[sg][0] != k:  # 两个矩阵共用 synergy/<md5[:8]>.html 命名空间：冲突就停，绝不悄悄覆盖
            raise SystemExit("synergy 详情页 slug 冲突：%s 与 %s" % (" × ".join(detail[sg][0]), " × ".join(k)))
        pl = sum(s[1] for s in vs.values()) / n
        wn = sum(s[3] for s in vs.values()) / n * 100
        ea, eb = marg[k[0]], marg[k[1]]
        lf = pl - (ea[1] / ea[0] + eb[1] / eb[0] - base)  # 协同差：对两羁绊边际的叠加预期
        if n in (ea[0], eb[0]):  # 嵌套：一边的棋盘全部同时带另一边，lf 恒等于 基线 − 另一边的边际，与这对羁绊无关
            lft, lfc = "无从定义（一个羁绊的棋盘全部同时带另一个）", "—"
        else:
            lft = lfc = "%+.2f" % lf
        ng = len(grp[k])
        detail[sg] = (k, vs)
        cl = " ".join(c for c, f in (("s5c", mark), ("sg", ng == 1), ("thin", n < THIN)) if f)
        return ('<td%s><a href="synergy/%s.html" title="%s × %s · 均名 %.2f · 吃鸡率 %.1f%% · 协同差 %s · %d 个棋盘 · %d 种组合 · %d 个阵容组">'
                '<b class="mp">%.2f</b><b class="mw">%.0f%%</b><b class="ml">%s</b><small>%.1f%%</small></a></td>') % (
            (' class="%s"' % cl) if cl else '', sg, e(k[0]), e(k[1]), pl, wn, lft, n, len(vs), ng,
            pl, wn, lfc, n / total * 100)

    order1 = [o for o in ori_order if any(o in k for k in oo)]
    head = "".join('<th class="vh%s" title="%s"><span>%s</span></th>' % (
        " s5" if o in s5o else "", e(ot[o]), e(o)) for o in order1)
    rows = []
    for i, a in enumerate(order1):
        tds = []
        for j, b in enumerate(order1):
            if i == j: tds.append('<td class="dg"></td>'); continue
            k = (a, b) if i < j else (b, a)
            tds.append(td(k, oo.get(k, {}), a in s5o or b in s5o))
        rows.append('<tr><th class="rh%s" title="%s">%s</th>%s</tr>' % (
            " s5" if a in s5o else "", e(ot[a]), e(a), "".join(tds)))
    sec1 = '''<section id="syn"><h2>种族 × 种族 搭配矩阵</h2>
<p class="hint">格内：<b>均名</b>、<b>吃鸡率</b>或<b>协同差</b>（上方按钮切换，两个矩阵一起切）+ 选率。点格子看该搭配下所有英雄组合。灰对角线=同种族；“·”=无样本。悬停行/列标题看该羁绊的前/中/后排英雄数（本站人工标注）。<b class="s5l">橙色</b> = 该羁绊只有一个五费英雄：五费英雄搭配什么都强，这类行/列参考价值低。<b class="sgl">灰字格</b> = 该格棋盘全部来自同一个阵容组（主流阵容共 %d 组）：数字只描述那一套阵容的最终棋盘（不代表强度），不是这对羁绊的性质。淡化格 = 场次 &lt; %d。协同差 = 格内均名 − (两羁绊各自边际均名之和 − 基线)：负数 = 好于“两边平均水平叠加”的预期；边际含该格自身，是描述性对比，不是因果交互，仅在跨多个阵容组的格子里才略有参考；一个羁绊的棋盘全部同时带另一个时（嵌套）协同差无从定义，显示 —。<br>
口径：阵容中某种族英雄 ≥2（单一英雄种族 ≥1）即算“带了”该种族。数据是 tactics.tools 主流阵容组里展示的 %d 个变体（列表里逐字重复的行只算一次），共 %s 个棋盘（全部 %s 个棋盘的 %.1f%%），它们的平均名次是 <b>%.2f</b>、吃鸡率是 <b>%.1f%%</b>（均匀基线 12.5%%），格内数字要和这两个数比，不是和 4.5 或 12.5%% 比；「阵容」页的基线按各组全部棋盘（含未展示的变体）计，不是同一批棋盘。均名和吃鸡率都来自对局结束时的最终棋盘，数字好的搭配多半是“这局本来就在赢”的棋盘，不说明照这样搭就能赢。选率 = 场次 / 全部棋盘数。</p>
<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div></section>''' % (
        ngrp, THIN, len(comps), "{:,}".format(nb), "{:,}".format(total), nb / total * 100, base, wbase, head, "".join(rows))
    if oc:
        orows = [o for o in ori_order if any(k[0] == o for k in oc)]
        ocols = [c for c in cls_order if any(k[1] == c for k in oc)]
        head2 = "".join('<th class="vh%s" title="%s"><span>%s</span></th>' % (
            " s5" if c in s5c else "", e(ct[c]), e(c)) for c in ocols)
        rows2 = "".join('<tr><th class="rh%s" title="%s">%s</th>%s</tr>' % (
            " s5" if a in s5o else "", e(ot[a]), e(a),
            "".join(td((a, c), oc.get((a, c), {}), a in s5o or c in s5c) for c in ocols)) for a in orows)
        body2 = '<div class="smx"><table class="syn"><tr><th></th>%s</tr>%s</table></div>' % (head2, rows2)
    else:
        body2 = '<p class="hint">没有达到口径的种族 × 职业搭配。</p>'
    sec2 = '''<section id="synoc"><h2>种族 × 职业 搭配矩阵</h2>
<p class="hint">行 = 种族，列 = 职业。口径同上，职业一样：阵容中该职业英雄 ≥2（单一英雄职业 ≥1）即算“带了”；变体 = 阵容中属于该种族或该职业的英雄集合。格内指标、基线与注意事项见上一个矩阵的说明；“·”=无样本。</p>
%s</section>''' % body2
    toggle = ('<div class="filters"><div class="fg"><span class="fl">格内指标</span>'
              '<button type="button" class="fb on" data-v="place">均名</button>'
              '<button type="button" class="fb" data-v="win">吃鸡率</button>'
              '<button type="button" class="fb" data-v="lift">协同差</button></div></div>')
    sec3 = crawl_section(crawl, crawl_zh, ori_order, cls_order, ot, ct, s5o, s5c, crawl_label) if crawl else ""
    mat = '<div id="synx">%s%s%s%s</div>%s' % (toggle, sec1, sec2, sec3, JS)
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
w.classList.toggle('m-lift',b.dataset.v==='lift');
w.querySelectorAll('.fb').forEach(function(x){x.classList.toggle('on',x===b);});});
})();</script>'''

CSS = '''.smx{overflow:auto}table.syn{border-collapse:collapse;font-size:12px}.syn td,.syn th{border:1px solid var(--bd);text-align:center;min-width:44px;height:40px;padding:0}
.syn .vh{height:110px;vertical-align:bottom}.syn .vh span{writing-mode:vertical-rl;padding:4px}.syn .rh{text-align:right;padding:0 6px;white-space:nowrap;position:sticky;left:0;background:var(--pn)}
.syn td a{display:block;color:inherit;text-decoration:none;padding:3px}.syn td a:hover{background:var(--pn2)}.syn small{display:block;color:var(--mu);font-size:10px}
.syn td .cv{display:block;padding:3px;cursor:help}
.syn .dg{background:#222a35}.syn .na{color:#444}
#synx b.mw,#synx b.ml{display:none}#synx.m-win b.mp{display:none}#synx.m-win b.mw{display:inline}
#synx.m-lift b.mp{display:none}#synx.m-lift b.ml{display:inline}
.syn td.sg a b{color:var(--mu)}.hint .sgl{color:var(--mu)}.syn td.thin a,.syn td.thin .cv{opacity:.55}
.syn .s5{color:#d9a24d}.hint .s5l{color:#d9a24d}.syn td.s5c{background:rgba(217,162,77,.08)}.syn td.s5c a b,.syn td.s5c .cv b{color:#d9a24d}
.syn td.s5c.sg a b{color:var(--mu)}
table.vt{border-collapse:collapse;width:100%}.vt td,.vt th{border-bottom:1px solid var(--bd);padding:6px;text-align:center}.vt .us{text-align:left}'''
