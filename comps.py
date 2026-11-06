"""阵容页 comps.html（首页也放同一组卡片）+ 每个阵容组的详情页 comps/<md5[:8]>.html（静态生成）。
数据：tactics.tools team-compositions 的阵容组（快照 comp_groups，白名单字段见 checks.GROUP_FIELDS）和组内
展示的变体（快照 comps）；羁绊激活人数和图标来自 Community Dragon（快照 official.trait_meta）。
排序：按场次（人气），不是强度排行：阵容强度目前无法从最终棋盘可靠测出（首页说明），强度评级标「待验证」。
口径（全部是对局结束时最终棋盘的描述，评级 C）：
- 场次 = 该组棋盘数；选率 = 场次 / 全部棋盘数。均名 / 前四率 / 吃鸡率和主流阵容组的加权基线、
  以及 4.50 / 50% / 12.5% 的均匀基线对比。
- ★★★：该英雄 3★（含 4★）占本组棋盘 ≥ STAR3_MAJOR 金色、≥ STAR3_MINOR 灰色。描述终局棋盘，
  不是“该追三星”：三星价值要逐阶段数据（Phase 4）。
- 1st/2nd/3rd：本组每盘平均持有成装件数（tactics.tools carryUnits）前三的英雄，下面是它最常带的 3 件：
  玩家把装备给谁，不说明给它装备更能赢。
- 终局等级只给分布、不给各等级均名：等级几乎由活了多久决定，按等级比名次只会重复幸存者偏差。
- 站位示意来自 sets/ 的人工标注（前/中/后排），不是实测站位（接口没有棋盘坐标）。
传入自采导出（crawl，schema tftlab-comps/1）时：阵容页加自采对照表、详情页加「自采数据」一节；不传时都不出现。"""
import hashlib
from html import escape as e

from generate_tft_table import COST_COLORS, item_cn, item_icon

STAR3_MAJOR = 0.5   # 3★ 占本组棋盘 >= 50%：金色 ★★★
STAR3_MINOR = 0.2   # 20%–50%：灰色 ★★★
CARRY_MARKS = 3     # 成装持有量前 3 的英雄标 1st/2nd/3rd
ITEMS_PER_CARRY = 3
TRAIT_SHARE = 0.5   # 羁绊标签：本组 >= 50% 棋盘激活
UNIT_SHARE = 0.25   # 详情页「英雄与装备」：出场 >= 25% 的英雄（八人阵容里的英雄总列出）
ITEM_THIN = 500     # 装备行、变体行场次低于此数淡化（同英雄页 BEST_MIN_N）
PLACE_SD = 2.29     # 单局名次的标准差（1–8 均匀分布）：区间半宽按它粗算，同英雄页
RANKS = ("1st", "2nd", "3rd")
POS = (("back", "后排"), ("mid", "中排"), ("front", "前排"))  # 示意图从上到下：后排在上


def slug(name):
    return hashlib.md5(name.encode()).hexdigest()[:8]


def halfwidths(n):
    """n 盘时 均名 与 吃鸡率（按 12.5% 算）的 95% 区间半宽：(名次, 百分点)，粗算口径同英雄页。"""
    return 1.96 * PLACE_SD / n ** 0.5, 196 * (0.125 * 0.875 / n) ** 0.5


def interval_note(n, what):
    hp, hw = halfwidths(n)
    return "%s最小 %s 盘：均名 95%% 区间半宽 ≤ %.2f 名、吃鸡率 ≤ ±%.1f 个百分点（按单局名次标准差 2.29 粗算，同英雄页）" % (
        what, num(n), hp, hw)


def pct(x, d=0):
    return ("%%.%df%%%%" % d) % (x * 100)


def num(n):
    return "{:,}".format(n)


def star_rows(g):
    """{英雄: {星级: 棋盘数}}，取自 tactics.tools 的 units 行（[英雄, 星级, 棋盘数, 均名]，只给前 100 行，缺的行很少见）。"""
    out = {}
    for u, s, c, _ in g.get("units") or []:
        d = out.setdefault(u, {})
        d[s] = d.get(s, 0) + c
    return out


def items_held(g):
    """{英雄: {成装件数: 棋盘数}}，取自 unitItemCounts（"英雄-件数" -> [棋盘数, 均名]）。"""
    out = {}
    for k, (c, _) in (g.get("unitItemCounts") or {}).items():
        u, k2 = k.rsplit("-", 1)
        out.setdefault(u, {})[int(k2)] = c
    return out


def by_unit(rows):
    out = {}
    for r in rows or []:
        out.setdefault(r["unitId"], []).append(r)
    return out


def baselines(groups):
    """主流阵容组棋盘的加权基线（页面上的数字要和它比，不是和 4.5 / 12.5% 比）。"""
    n = sum(g["count"] for g in groups) or 1
    return {"n": n, "place": sum(g["place"] * g["count"] for g in groups) / n,
            "top4": sum(g["top4"] for g in groups) / n, "win": sum(g["win"] for g in groups) / n}


def chips(g, zh, tmeta):
    """本组 >= TRAIT_SHARE 棋盘激活的羁绊，按激活占比降序；人数 = 最常见档位的官方激活人数。"""
    n = g["count"]
    by = {}
    for t, tier, c, _ in g.get("traits") or []:
        d = by.setdefault(t, {})
        d[tier] = d.get(tier, 0) + c
    out = []
    for t, tiers in by.items():
        share = sum(tiers.values()) / n
        if share < TRAIT_SHARE or t not in zh:
            continue
        tier = max(tiers, key=lambda k: (tiers[k], -k))
        br = (tmeta.get(t) or {}).get("breaks") or []
        out.append(dict(api=t, zh=zh[t], tier=tier, units=br[tier - 1] if 0 < tier <= len(br) else None,
                        share=min(share, 1.0), breaks=list(dict.fromkeys(br)),  # 显示用：官方表偶有重复档（宿敌 1/1/2）
                        icon=(tmeta.get(t) or {}).get("icon") or ""))
    out.sort(key=lambda x: (-x["share"], x["api"]))
    return out


def comp_name(g, ch, U):
    """主羁绊（最常见档位人数最多的标签羁绊）· 主C（成装持有量第一的英雄）。"""
    carry = (g.get("carryUnits") or [[None]])[0][0]
    main = max(ch, key=lambda x: (x["units"] or 0, x["share"]), default=None)
    parts = [x for x in (main["zh"] if main else None, U(carry)["name"] if carry else None) if x]
    return " · ".join(parts) or "阵容组 %d" % (g["group"] + 1)


def item_img(meta, iid):
    return '<img src="%s" alt="%s" title="%s" data-it="%s" loading="lazy">' % (
        e(item_icon(meta, iid)), e(item_cn(meta, iid)), e(item_cn(meta, iid)), e(iid))


def chip_html(c):
    tiers = " > ".join(str(b) for b in c["breaks"])
    t = "%s：本组 %s 的棋盘激活；最常见 %s 人档%s" % (
        c["zh"], pct(c["share"]), c["units"] or "?", "（%s）" % tiers if tiers else "")
    return ('<span class="tc" title="%s"><img src="%s" alt="" loading="lazy" onerror="this.remove()">%s<b>%s</b></span>'
            % (e(t), e(c["icon"]), e(c["zh"]), c["units"] or ""))


def stats_html(g, total, base):
    n = g["count"]

    def box(label, val, sub, title):
        return '<div class="sb" title="%s"><span>%s</span><b>%s</b><small>%s</small></div>' % (e(title), label, val, sub)
    return '<div class="cstats">%s%s%s%s%s</div>' % (
        box("场次", num(n), "tactics.tools", "本组棋盘数（组内全部变体）"),
        box("选率", pct(n / total, 2), "全部棋盘", "本组棋盘 / 全部 %s 个棋盘" % num(total)),
        box("均名", "%.2f" % g["place"], "基线 %.2f" % base["place"], "主流阵容组基线 %.2f · 均匀基线 4.50" % base["place"]),
        box("前四率", pct(g["top4"] / n, 1), "基线 %s" % pct(base["top4"], 1), "主流阵容组基线 %s · 均匀基线 50%%" % pct(base["top4"], 1)),
        box("吃鸡率", pct(g["win"] / n, 1), "基线 %s" % pct(base["win"], 1), "主流阵容组基线 %s · 均匀基线 12.5%%" % pct(base["win"], 1)))


def strip_html(g, units, U, meta):
    """op.gg 式英雄条：按费用排；★★★ = 3★ 占本组棋盘的比例；1st/2nd/3rd = 成装持有量前三 + 最常带的 3 件。"""
    n = g["count"]
    st = star_rows(g)
    score = {u: s for u, s in g.get("carryUnits") or []}
    carries = [u for u, _ in (g.get("carryUnits") or [])[:CARRY_MARKS]]
    top_items = by_unit(g.get("unitItems"))
    cells = []
    for u in sorted(units, key=lambda x: (U(x).get("cost") or 9, U(x)["name"])):
        info = U(u)
        s3 = sum(c for s, c in st.get(u, {}).items() if s >= 3) / n
        cls = "maj" if s3 >= STAR3_MAJOR else "min" if s3 >= STAR3_MINOR else ""
        star = ('<div class="cs %s" title="%s">★★★</div>' % (cls, e(
            "%s：3★（含 4★）占本组棋盘 %s。描述对局结束时的棋盘，不是“该追三星”的建议：能留到三星的棋盘本来就活得久"
            % (info["name"], pct(s3))))) if cls else '<div class="cs"></div>'
        rank = carries.index(u) if u in carries else -1
        badge = its = ""
        if rank >= 0:
            badge = '<em class="ck r%d" title="%s">%s</em>' % (rank + 1, e(
                "%s：本组每盘平均持有 %.2f 件成装，第 %d 多。玩家把装备给谁，不说明给它装备更能赢"
                % (info["name"], score.get(u, 0), rank + 1)), RANKS[rank])
            its = '<span class="ci">%s</span>' % "".join(
                item_img(meta, r["itemId"]) for r in top_items.get(u, [])[:ITEMS_PER_CARRY])
        cells.append('<div class="cu">%s<div class="cp" style="--c:%s"><img src="%s" alt="%s" loading="lazy" '
                     'onerror="this.style.opacity=.2">%s%s</div><div class="cn">%s</div></div>' % (
                         star, COST_COLORS.get(info.get("cost"), "#666"), e(info["icon"]), e(info["name"]),
                         badge, its, e(info["name"])))
    return '<div class="cstrip">%s</div>' % "".join(cells)


def card_html(g, c, total, base, U, meta, href):
    link = ('<a class="cgo" href="%s">阵容详情 →</a>' % href) if href else ""
    return ('<article class="cc"><div class="ch1"><h3>%s</h3><span class="tierp" title="阵容强度目前无法从最终棋盘可靠测出：'
            '这里按场次排列，不是强度排行">强度评级：待验证</span><span class="cmeta">%d 个展示变体</span></div>'
            '<div class="crow">%s<div class="tcs">%s</div></div>%s%s</article>') % (
        e(c["name"]), c["n_variants"], stats_html(g, total, base), "".join(chip_html(x) for x in c["chips"]),
        strip_html(g, c["strip"], U, meta), link)


def bars_html(vals, labels, line=None, good=4):
    """竖条图：vals = 份额（0–1）；line = 虚线（如均匀基线 1/8）；前 good 条绿色。"""
    mx = max(list(vals) + ([line] if line else [])) or 1
    ln = ('<i class="pbl" style="bottom:%.1f%%" title="均匀基线 %s"></i>' % (line / mx * 100, pct(line, 1))) if line else ""
    bars = "".join('<div class="pbv%s" style="height:%.1f%%" title="%s：%s"><small>%s</small></div>' % (
        " g" if k < good else "", v / mx * 100, e(lab), pct(v, 1), pct(v)) for k, (v, lab) in enumerate(zip(vals, labels)))
    return '<div class="pbx"><div class="pba">%s%s</div><div class="pbn">%s</div></div>' % (
        ln, bars, "".join("<span>%s</span>" % e(lab) for lab in labels))


def place_bars(counts):
    n = sum(counts) or 1
    return bars_html([c / n for c in counts], ["第%d名" % (k + 1) for k in range(8)], line=1 / 8)


def level_bars(rows):
    """rows = [(等级, 棋盘数)]：只给分布。"""
    rows = sorted(rows)
    n = sum(k for _, k in rows) or 1
    return bars_html([k / n for _, k in rows], ["%d级" % lv for lv, _ in rows], good=0)


def units_html(g, strip, U, face, meta):
    """详情页「英雄与装备」：出场、星级分布、平均成装 / 满装率、常带成装与两件组合（场次、均名）。"""
    n = g["count"]
    st, held = star_rows(g), items_held(g)
    its, prs = by_unit(g.get("unitItems")), by_unit(g.get("unitItemPairs"))
    pres = {u: min(1.0, sum(s.values()) / n) for u, s in st.items()}
    rows = []
    for u in sorted({u for u in st if pres[u] >= UNIT_SHARE} | set(strip), key=lambda x: (-pres.get(x, 0), x)):
        s = st.get(u, {})
        f = sum(s.values()) or 1
        s1, s2, s3 = s.get(1, 0) / f, s.get(2, 0) / f, sum(v for k, v in s.items() if k >= 3) / f
        sbar = ('<div class="sbar" title="%s"><i class="s1" style="width:%.1f%%"></i><i class="s2" style="width:%.1f%%"></i>'
                '<i class="s3" style="width:%.1f%%"></i></div><small>3★ %s</small>') % (
            e("占该英雄出场棋盘：1★ %s · 2★ %s · 3★（含 4★）%s" % (pct(s1), pct(s2), pct(s3))), s1 * 100, s2 * 100, s3 * 100,
            pct(sum(v for k, v in s.items() if k >= 3) / n))
        h = held.get(u, {})
        hn = sum(h.values())
        avg = sum(k * v for k, v in h.items()) / n
        full = (h.get(3, 0) / hn) if hn else 0
        itm = "".join('<span class="it%s" title="%s">%s<small>%s</small></span>' % (
            " thin" if r["count"] < ITEM_THIN else "", e("%s · %s 盘带（本组 %s）" % (
                item_cn(meta, r["itemId"]), num(r["count"]), pct(r["count"] / n))),
            item_img(meta, r["itemId"]), pct(r["count"] / n)) for r in its.get(u, [])[:5])
        pr = "".join('<div class="pr%s">%s<small>%s 盘 · 本组 %s</small></div>' % (
            " thin" if r["count"] < ITEM_THIN else "", "".join(item_img(meta, i) for i in r["items"]),
            num(r["count"]), pct(r["count"] / n)) for r in prs.get(u, [])[:2])
        rows.append('<tr><td class="us">%s <span>%s</span></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                    '<td class="its">%s</td><td>%s</td></tr>' % (
                        face(U(u), "sm"), e(U(u)["name"]), pct(pres.get(u, 0)), sbar,
                        ("%.2f" % avg) if hn else "—", pct(full) if hn else "—", itm or "—", pr or "—"))
    return ('<div class="smx"><table class="vt utab"><tr><th>英雄</th><th>出场</th><th>星级</th><th>每盘成装<small>（本组全部棋盘）</small></th>'
            '<th>满装率<small>（出场时）</small></th><th>常带成装（本组带它的棋盘占比）</th><th>常见两件（场次 · 占本组）</th></tr>%s</table></div>'
            % "".join(rows))


def variants_html(vs, U, face, meta, total):
    rows = "".join('<tr%s><td class="us">%s%s</td><td>%s</td><td>%s</td><td>%.2f</td><td>%s</td><td>%s</td></tr>' % (
        ' class="thin"' if c["count"] < ITEM_THIN else "",
        "".join(face(U(u), "sm") for u in sorted(c["units"], key=lambda x: (U(x).get("cost") or 9, U(x)["name"]))),
        ('<span class="spx">%s</span>' % "".join(item_img(meta, s) for s in c["spatItems"])) if c.get("spatItems") else "",
        num(c["count"]), pct(c["count"] / total, 2), c["place"], pct(c["top4"] / c["count"]), pct(c["win"] / c["count"]))
        for c in sorted(vs, key=lambda c: -c["count"]))
    return ('<div class="smx"><table class="vt"><tr><th>变体（八人阵容 + 纹章）</th><th>场次</th><th>选率</th><th>均名</th>'
            '<th>前四</th><th>吃鸡</th></tr>%s</table></div>' % rows)


def positions_html(units, manual, U, face):
    pos = manual.get("positions") or {}
    rows = []
    for p, lab in POS:
        us = [u for u in units if (pos.get(u) or ["?"])[0] == p]
        rows.append('<div class="prow"><b>%s</b>%s</div>' % (lab, "".join(face(U(u)) for u in us) or '<span class="hint">—</span>'))
    un = [u for u in units if (pos.get(u) or ["?"])[0] not in dict(POS)]
    if un:
        rows.append('<div class="prow"><b>未标注</b>%s</div>' % "".join(face(U(u)) for u in un))
    return "".join(rows)


def similar_html(gid, cards, U, face):
    me = set(cards[gid]["strip"])
    near = sorted(((len(me & set(c["strip"])), o) for o, c in cards.items() if o != gid), key=lambda x: (-x[0], x[1]))
    rows = ['<div class="prow"><a href="%s.html" style="color:var(--ac);min-width:180px">%s</a>%s<span class="hint">共用 %d 名英雄</span></div>' % (
        cards[o]["slug"], e(cards[o]["name"]), "".join(face(U(u), "sm") for u in sorted(me & set(cards[o]["strip"]))), k)
        for k, o in near if k >= 2]
    return "".join(rows) or '<p class="hint">没有和本组共用 2 名以上英雄的其他阵容组。</p>'


def why_not(rel=""):
    """「为什么没有」说明框；rel = 到站点根的相对前缀（详情页传 "../"）。"""
    return ('<section id="why" class="whyn"><h3>为什么没有：重置（D 牌）次数 · 强化符文 · 实测站位 · 逐等级实测阵容</h3>'
            '<p class="hint">这几项需要对局<b>过程中</b>的数据：每个等级、每个阶段场上是什么、重置（D 牌）了几次、拿了哪些强化符文、'
            '英雄站在哪一格。本站的数据（tactics.tools 的阵容统计）只有<b>对局结束时的最终棋盘</b>，本项目自采的 Riot 对局数据也一样：'
            '没有逐等级的阵容、没有重置次数、Set 18 的对局数据里没有强化符文字段，也没有棋盘坐标。'
            '<a href="%strees.html" style="color:var(--ac)">变阵路线</a>页的「5级开局 → 7级中期 → 终局」来自 OP.GG 的官方数据接口'
            '（它家应用的对局内采集）：外部数据，只有这三个阶段，不是本站实测。要自己补上逐等级数据需要在对局中逐阶段采集快照'
            '（本项目规划中的 Phase 4，例如经游戏内插件，尚未开始）。在那之前，这里只放最终棋盘能支持的描述。</p></section>' % rel)

COPY_JS = '''<script>(function(){document.addEventListener('click',function(ev){var b=ev.target.closest('[data-copy]');
if(!b||!navigator.clipboard)return;navigator.clipboard.writeText(b.dataset.copy).then(function(){b.textContent='已复制';
setTimeout(function(){b.textContent='复制';},1500);});});})();</script>'''


def ci(x, lo_hi, f):
    return '%s <small>(95%% %s–%s)</small>' % (f(x), f(lo_hi[0]), f(lo_hi[1]))


def crawl_warn(rc):
    if rc.get("publishable") is False:
        return ('<p class="hint" style="color:var(--bad)">注意：自采数据来自开发 key，按 Riot 开发者政策不可用于公开网站'
                '——这份构建仅限本地预览，不要推送上线。</p>')
    return ""


def crawl_table(rc, order, cards, label):
    """阵容页（预览构建）：每组的自采对照，顺序同上方卡片（按 tactics.tools 场次），不按自采数字重排。"""
    cells = {c["family"]: c for c in rc.get("cells") or []}
    f2 = lambda x: "%.2f" % x
    p1 = lambda x: pct(x, 1)
    rows = []
    for g in order:
        c, cd = cells.get(g), cards[g]
        if c is None:
            rows.append('<tr><td class="us"><a href="comps/%s.html">%s</a></td><td colspan="5" class="hint">自采样本里没有归入本组的棋盘</td></tr>' % (
                cd["slug"], e(cd["name"])))
            continue
        rows.append('<tr><td class="us"><a href="comps/%s.html">%s</a></td><td>%s <small>/ %s 场</small></td><td>%s</td>'
                    '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                        cd["slug"], e(cd["name"]), num(c["n_boards"]), num(c["n_matches"]),
                        ci(c["pick_rate"], c["pick_ci95"], p1), ci(c["place_mean"], c["place_ci95"], f2),
                        ci(c["top4"], c["top4_ci95"], p1), ci(c["top1"], c["top1_ci95"], p1)))
    um = rc.get("unmatched") or {}
    pr = rc.get("params") or {}
    hint = ('<p class="hint">%s。棋盘按「与该组任一变体重合 ≥ %s 名英雄」归组（同英雄页），重合不足的 %s 盘（%s）未归组。'
            '区间：按“场”整群自助法（B = %s）。全部自采棋盘的基线：均名 4.50、前四 50%%、吃鸡 12.5%%（每场 8 人，按定义如此）。'
            '人群和上方 tactics.tools 不同（地区和种子段位见本段开头），两边数字不能直接相减。行顺序同上方卡片，不按自采数字排。</p>') % (
        e(label), pr.get("min_overlap"), num(um.get("n_boards") or 0), pct(um.get("share") or 0, 1), pr.get("n_boot"))
    return ('<section id="compcrawl"><h2>自采对局对照（Riot API）</h2>%s%s<div class="smx"><table class="vt">'
            '<tr><th>阵容组</th><th>棋盘</th><th>自采选率</th><th>均名</th><th>前四</th><th>吃鸡</th></tr>%s</table></div></section>'
            % (hint, crawl_warn(rc), "".join(rows)))


def crawl_block(rc, cell, U, face, meta, zh, tmeta, label, strip=()):
    """详情页（预览构建）：本组在自采对局里的描述统计，每个数字带 95% 区间和样本量。
    英雄行和 tactics.tools 那节一样只列出场 >= UNIT_SHARE 或在八人阵容里的英雄（导出里全有），隐去的计数。"""
    pr = rc.get("params") or {}
    head = ('<p class="hint">%s。棋盘按「与本组任一变体重合 ≥ %s 名英雄」归组（同英雄页）。区间：按“场”整群自助法（B = %s）；'
            '英雄行 n &lt; %s、装备组合 n &lt; %s 的不显示。出场、3★、成装都是对局结束时的状态：活得越久越容易出现，'
            '这些数字描述玩家的结果，不是打法建议。</p>') % (
        e(label), pr.get("min_overlap"), pr.get("n_boot"), pr.get("min_n"), pr.get("combo_min_n"))
    if cell is None:
        return ('<section id="compcrawl"><h2>自采数据（Riot API）</h2>%s%s<p class="hint">自采样本里没有归入本组的棋盘。</p></section>'
                % (head, crawl_warn(rc)))
    f2 = lambda x: "%.2f" % x
    p1 = lambda x: pct(x, 1)

    def box(label_, val):
        return '<div class="sb"><span>%s</span><b>%s</b></div>' % (label_, val)
    stats = '<div class="cstats">%s%s%s%s%s</div>' % (
        box("棋盘", "%s <small>/ %s 场</small>" % (num(cell["n_boards"]), num(cell["n_matches"]))),
        box("自采选率", ci(cell["pick_rate"], cell["pick_ci95"], p1)),
        box("均名", ci(cell["place_mean"], cell["place_ci95"], f2)),
        box("前四率", ci(cell["top4"], cell["top4_ci95"], p1)),
        box("吃鸡率", ci(cell["top1"], cell["top1_ci95"], p1)))
    trs = "".join('<div><b>%s</b> 激活 %s · %s</div>' % (
        e(zh.get(t["trait"], t["trait"])), pct(t["active_share"]),
        " · ".join("%s人 %s" % (_units(tmeta, t["trait"], k), num(v)) for k, v in sorted(t["tiers"].items(), key=lambda kv: int(kv[0]))))
        for t in cell.get("traits") or [])
    rows = []
    shown = [u for u in cell.get("units") or [] if u["presence"] >= UNIT_SHARE or u["unit"] in strip]
    hidden = len(cell.get("units") or []) - len(shown)
    for u in shown:
        combos = "".join('<div class="pr">%s<small>%s 盘 · 均名 %s</small></div>' % (
            "".join(item_img(meta, i) for i in cb["items"]), num(cb["n"]),
            ci(cb["place_mean"], cb["place_ci95"], f2) if cb.get("place_mean") is not None else "—")
            for cb in (u.get("combos") or [])[:3])
        rows.append('<tr><td class="us">%s <span>%s</span></td><td>%s <small>(%s 盘)</small></td><td>%s</td><td>%s</td>'
                    '<td>%.2f</td><td>%s</td><td>%s</td></tr>' % (
                        face(U(u["unit"]), "sm"), e(U(u["unit"])["name"]), pct(u["presence"]), num(u["n"]),
                        ci(u["star3"], u["star3_ci95"], p1), ci(u["item_share"], u["item_share_ci95"], p1),
                        u["items_per_board"], pct(u["full_rate"]), combos or "—"))
    lv = [(x["level"], x["n"]) for x in cell.get("levels") or []]
    return ('<section id="compcrawl"><h2>自采数据（Riot API）</h2>%s%s%s'
            '<h3>名次分布 <small>自采</small></h3>%s<h3>终局等级 <small>自采，只给分布</small></h3>%s'
            '<h3>羁绊 <small>自采：本组 ≥ %s 棋盘激活（游戏判定 tier_current ≥ 1）</small></h3><div class="trl">%s</div>'
            '<h3>英雄与装备 <small>自采；成装份额 = 该英雄的成装 / 本组全部成装</small></h3><div class="smx"><table class="vt utab">'
            '<tr><th>英雄</th><th>出场</th><th>3★ 占本组</th><th>成装份额</th><th>每盘成装<small>（本组全部棋盘）</small></th>'
            '<th>满装率<small>（出场时）</small></th><th>常见成装组合</th></tr>'
            '%s</table></div>%s</section>') % (
        head, crawl_warn(rc), stats, place_bars([round(x * 10000) for x in cell["placement_hist"]]),
        level_bars(lv) if lv else '<p class="hint">—</p>', pct(pr.get("trait_share_min") or 0), trs or "—", "".join(rows),
        ('<p class="hint">另有 %d 名英雄出场 &lt; %s（n ≥ %s，导出文件里有），这里不列。</p>' % (hidden, pct(UNIT_SHARE), pr.get("min_n")))
        if hidden else "")


def _units(tmeta, t, tier):
    br = (tmeta.get(t) or {}).get("breaks") or []
    k = int(tier)
    return br[k - 1] if 0 < k <= len(br) else "档%d" % k


def build(groups, comps, manual, total, U, face, meta, zh, tmeta, crawl=None, crawl_label=""):
    """返回 (阵容页 body, 首页用的阵容区块, {"comps/<slug>.html": (标题, body)})。"""
    base = baselines(groups)
    order = [g["group"] for g in sorted(groups, key=lambda g: (-g["count"], g["group"]))]
    gmap = {g["group"]: g for g in groups}
    cards, seen = {}, {}
    for gid in order:
        g = gmap[gid]
        vs = [c for c in comps if c.get("group") == gid]
        ch = chips(g, zh, tmeta)
        name = comp_name(g, ch, U)
        if name in seen:  # 两组同名：补上第二主C
            second = (g.get("carryUnits") or [[None], [None]])[1:2]
            name = "%s · %s" % (name, U(second[0][0])["name"] if second and second[0][0] else "组 %d" % (gid + 1))
        sg = slug(name)
        if sg in seen.values():
            raise SystemExit("comps 详情页 slug 冲突：%s" % name)
        seen[name] = sg
        cards[gid] = dict(name=name, slug=sg, chips=ch, n_variants=len(vs), variants=vs,
                          strip=list(max(vs, key=lambda c: c["count"])["units"]) if vs else [])
    covered = sum(gmap[g]["count"] for g in order)
    legend = ('<p>tactics.tools 主流阵容的 <b>%d 个阵容组</b>（每组是一套阵容和它的变体），<b>按场次（人气）排序，不是强度排行</b>：'
              '阵容强度目前还无法从最终棋盘可靠测出，每组的强度评级标为「待验证」。评级 C（描述性）。</p>'
              '<p class="hint">场次 = 该组的棋盘数；选率 = 场次 / 全部 %s 个棋盘（%d 组合计 %s 盘，占 %s）。均名 / 前四率 / 吃鸡率要和'
              '主流阵容组的基线比：均名 <b>%.2f</b>、前四率 <b>%s</b>、吃鸡率 <b>%s</b>（均匀基线 4.50 / 50%% / 12.5%%）。'
              '这些都来自对局结束时的最终棋盘：数字好的阵容多半是「这局本来就在赢」的棋盘，不说明照这样玩能赢。%s。</p>'
              '<p class="hint"><span class="cs maj">★★★</span> = 本组过半终局棋盘上该英雄是 3★（<span class="cs min">★★★</span> = 20%%–50%%）；'
              '<b>1st/2nd/3rd</b> = 本组每盘平均持有成装最多的三个英雄，头像下是它最常带的 3 件。两者都描述玩家怎么玩，'
              '不是“该追三星 / 该给谁装备”的建议。悬停（手机上点按）装备图标看合成配方。</p>') % (
        len(order), num(total), len(order), num(covered), pct(covered / total, 1), base["place"], pct(base["top4"], 1),
        pct(base["win"], 1), interval_note(min(gmap[g]["count"] for g in order), "卡片上的组"))
    card_list = "".join(card_html(gmap[g], cards[g], total, base, U, meta, "comps/%s.html" % cards[g]["slug"]) for g in order)
    sec_crawl = crawl_table(crawl, order, cards, crawl_label) if crawl else ""
    page = '<section id="comps"><h2>阵容</h2><div class="box">%s</div><div class="clist">%s</div></section>%s%s' % (
        legend, card_list, sec_crawl, why_not())
    index = ('<section id="comps"><h2>阵容 <small class="hint">按场次（人气）排序，不是强度排行 · 评级 C（描述性）</small></h2>'
             '<p class="hint">均名 / 前四率 / 吃鸡率要和主流阵容组的基线比（均名 %.2f、前四率 %s、吃鸡率 %s），都来自最终棋盘：'
             '数字好的阵容多半是「这局本来就在赢」；%s。<span class="cs maj">★★★</span> = 本组过半终局棋盘上是 3★'
             '（<span class="cs min">★★★</span> = 20%%–50%%），1st/2nd/3rd = 每盘成装最多的英雄：描述玩家怎么玩，'
             '不是建议。口径详见<a href="comps.html" style="color:var(--ac)">阵容页</a>。</p><div class="clist">%s</div></section>') % (
        base["place"], pct(base["top4"], 1), pct(base["win"], 1),
        interval_note(min(gmap[g]["count"] for g in order), "卡片上的组"), card_list)
    cells = {c["family"]: c for c in (crawl or {}).get("cells") or []}
    pages = {}
    for gid in order:
        g, c = gmap[gid], cards[gid]
        tabs = [("ov", "概览"), ("units", "英雄与装备"), ("dist", "名次与等级"), ("vars", "变体"), ("pos", "站位示意"),
                ("sim", "相似阵容"), ("why", "为什么没有…")] + ([("compcrawl", "自采数据")] if crawl else [])
        trl = "".join('<div title="%s"><img src="%s" alt="" loading="lazy" onerror="this.remove()" class="tri"><b>%s</b> %s · 激活 %s</div>' % (
            e("最常见 %s 人档" % (x["units"] or "?")), e(x["icon"]), e(x["zh"]),
            " &gt; ".join(('<span class="on">%s</span>' % b) if b == x["units"] else str(b) for b in x["breaks"]),
            pct(x["share"])) for x in c["chips"])
        code = g.get("code") or ""
        code_html = ('<div class="tcode">阵容码 <code>%s</code><button type="button" class="fb" data-copy="%s">复制</button>'
                     '<small>tactics.tools 提供，对应本组的完整阵容（人口数可能和上面的八人阵容不同）</small></div>' % (e(code), e(code))) if code else ""
        lv = [(r[0], r[1]) for r in g.get("levels") or []]
        body = ''.join([
            '<section class="cdet"><p><a href="../comps.html" style="color:var(--ac)">← 返回阵容</a></p>',
            '<div class="ctabs">%s</div>' % "".join('<a href="#%s">%s</a>' % t for t in tabs),
            '<div id="ov">%s</div>%s' % (card_html(g, c, total, base, U, meta, None), code_html),
            '<p class="hint">tactics.tools 阵容组 · 评级 C（描述性）· 和主流阵容组基线比（均名 %.2f、前四率 %s、吃鸡率 %s）；'
            '全部来自最终棋盘，数字好多半说明「这局本来就在赢」，不说明照这样玩能赢。区间：%s；%s。</p>' % (
                base["place"], pct(base["top4"], 1), pct(base["win"], 1), interval_note(g["count"], "本组"),
                interval_note(min(v["count"] for v in c["variants"]), "下方变体行") if c["variants"] else "本组没有展示的变体"),
            '<h3>羁绊 <small>本组 ≥ %s 棋盘激活；高亮 = 最常见档位</small></h3><div class="trl">%s</div>' % (pct(TRAIT_SHARE), trl or "—"),
            '<h3 id="units">英雄与装备 <small>出场 ≥ %s 的英雄；装备场次 &lt; %d 淡化</small></h3>' % (pct(UNIT_SHARE), ITEM_THIN),
            '<p class="hint">出场按 tactics.tools 的星级行相加（同一棋盘两张同名卡会重复计，所以封顶 100%）；星级条 = 该英雄出场时'
            '各星级的占比，下方 3★ = 占本组全部棋盘；每盘成装 = 本组每个棋盘上该英雄平均持有的成装件数（没上场的棋盘记 0，同 1st/2nd/3rd）；'
            '满装率 = 该英雄出场时拿满 3 件的占比。装备只给场次和占比、不给均名：带满装、成型的棋盘本来就活得久，'
            '按装备比名次说明不了哪件更好。</p>',
            units_html(g, c["strip"], U, face, meta),
            '<h3 id="dist">名次分布 <small>%s 盘；虚线 = 均匀基线 12.5%%</small></h3>%s' % (num(g["count"]), place_bars(g.get("placementDistribution") or [0] * 8)),
            '<h3>终局等级 <small>对局结束时的人口等级，只给分布</small></h3>%s<p class="hint">不给各等级的均名：等级几乎由活了多久决定，'
            '按等级比较名次只会重复“活得久的名次好”。</p>' % (level_bars(lv) if lv else "—"),
            '<h3 id="vars">变体 <small>tactics.tools 展示的八人阵容（重复行已去重）；选率 = 场次 / 全部棋盘；场次 &lt; %d 淡化</small></h3>'
            '<p class="hint">变体的均名要和本组均名 %.2f 比。变体之间的差别主要反映棋盘成型到了哪一步（费用高、人口满的棋盘活得更久），'
            '不说明该选哪个变体。</p>%s' % (ITEM_THIN, g["place"], variants_html(c["variants"], U, face, meta, total)),
            '<h3 id="pos">站位示意 <small>人工标注示意（非实测站位）：前/中/后排来自本站的标注，接口没有棋盘坐标</small></h3>%s' % positions_html(c["strip"], manual, U, face),
            '<h3 id="sim">相似阵容 <small>按八人阵容共用的英雄数</small></h3>%s' % similar_html(gid, cards, U, face),
            '</section>', why_not("../"),
            crawl_block(crawl, cells.get(gid), U, face, meta, zh, tmeta, crawl_label, c["strip"]) if crawl else "",
            COPY_JS if code else ""])
        pages["comps/%s.html" % c["slug"]] = (c["name"], body)
    return page, index, pages


CSS = '''.clist{display:grid;gap:14px}
.cc{background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:14px 16px}
.ch1{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.ch1 h3{margin:0;font-size:18px}
.tierp{font-size:12px;color:var(--mu);border:1px dashed var(--bd);border-radius:99px;padding:1px 10px}.cmeta{color:var(--mu);font-size:12px}
.crow{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:flex-start;margin-top:10px}
.cstats{display:flex;flex-wrap:wrap;gap:6px 20px}.sb{display:flex;flex-direction:column;min-width:66px}
.sb span{color:var(--mu);font-size:12px}.sb b{font-size:18px}.sb b small{font-size:11px;font-weight:400;color:var(--mu)}.sb>small{color:var(--mu);font-size:11px}
.tcs{display:flex;flex-wrap:wrap;gap:6px;max-width:560px}
.tc{display:inline-flex;align-items:center;gap:4px;background:var(--pn2);border:1px solid var(--bd);border-radius:99px;padding:2px 10px 2px 3px;font-size:12px}
.tc img,.tri{width:20px;height:20px;background:#000;border-radius:50%;padding:2px}.tc b{color:var(--ac)}
.cstrip{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.cu{width:64px;text-align:center}
.cs{height:16px;font-size:13px;line-height:16px;letter-spacing:-1px;color:transparent}.cs.maj{color:#f0b429}.cs.min{color:#8b98a8}
.cp{position:relative;width:60px;height:60px;margin:0 auto;border:2px solid var(--c);border-radius:10px;overflow:hidden;background:#000}
.cp>img{width:100%;height:100%;object-fit:cover;display:block}
.ck{position:absolute;top:0;left:0;font-style:normal;font-size:10px;font-weight:800;padding:0 4px;border-bottom-right-radius:6px;color:#fff;background:#d6336c;cursor:help}
.ck.r2{background:#1c7ed6}.ck.r3{background:#e8590c}
.ci{position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:center;gap:1px;background:rgba(0,0,0,.6)}.ci img{width:18px;height:18px;border-radius:3px}
.cn{font-size:11px;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ci img,.it img,.pr img,.vt td img[data-it]{cursor:help}
.cgo{display:inline-block;margin-top:12px;color:#111;background:var(--ac);border-radius:8px;padding:5px 14px;font-weight:700;text-decoration:none}
.ctabs{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0 14px;padding:6px;background:var(--pn);border:1px solid var(--bd);border-radius:var(--r)}
.ctabs a{color:var(--mu);text-decoration:none;padding:4px 12px;border-radius:8px}.ctabs a:hover{color:var(--tx);background:var(--pn2)}
.pbx{max-width:520px;margin:18px 0 6px}.pba{position:relative;height:96px;display:flex;align-items:flex-end;gap:6px;border-bottom:1px solid var(--bd)}
.pbv{flex:1;background:#3b4a5e;border-radius:4px 4px 0 0;position:relative;min-height:2px}.pbv.g{background:#2f7d4a}
.pbv small{position:absolute;top:-16px;left:0;right:0;text-align:center;font-size:10px;color:var(--mu)}
.pbl{position:absolute;left:0;right:0;border-top:1px dashed var(--ac);opacity:.7}
.pbn{display:flex;gap:6px}.pbn span{flex:1;text-align:center;font-size:11px;color:var(--mu)}
.utab .us{white-space:nowrap}.utab .us span{vertical-align:middle;margin-left:4px}.utab td small{color:var(--mu)}
.spx{display:inline-flex;gap:2px;vertical-align:middle;margin-left:4px}.spx img{width:22px;height:22px;border-radius:3px}
.sbar{display:inline-flex;width:90px;height:8px;border-radius:4px;overflow:hidden;background:var(--pn2);vertical-align:middle}.sbar i{display:block}
.sbar .s1{background:#6c757d}.sbar .s2{background:#4dabf7}.sbar .s3{background:#f0b429}
.its{white-space:nowrap}.it{display:inline-flex;flex-direction:column;align-items:center;margin-right:4px}.it img{width:24px;height:24px;border-radius:4px}.it small{font-size:10px;color:var(--mu)}
.it.thin,.pr.thin{opacity:.5}
.pr{display:flex;align-items:center;gap:2px;white-space:nowrap;margin:2px 0}.pr img{width:22px;height:22px;border-radius:3px}.pr small{color:var(--mu);margin-left:4px}
.prow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:6px 0}.prow>b{width:44px;color:var(--mu);font-weight:400;font-size:12px}
.whyn{background:var(--pn);border:1px dashed var(--bd);border-radius:var(--r);padding:12px 14px;opacity:.85}.whyn h3{margin-top:0}
.tcode{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px;font-size:12px;color:var(--mu)}.tcode code{color:var(--tx);word-break:break-all}
.vt td a{color:var(--ac);text-decoration:none}.vt td a:hover{text-decoration:underline}.vt tr.thin td{opacity:.55}.vt th small{font-weight:400;color:var(--mu)}
.cdet [id],section[id]{scroll-margin-top:72px}
.trl{display:flex;flex-wrap:wrap;gap:8px 20px}.trl div{font-size:12px;color:var(--mu);display:flex;align-items:center;gap:4px}.trl b{color:var(--tx)}.trl .on{color:var(--ac);font-weight:700}'''
