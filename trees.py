"""变阵路线页 trees.html + 每个开局羁绊一页 trees/<md5[:8]>.html（静态生成）。
数据：OP.GG 官方 MCP 接口的 meta 阵容（快照 opgg_decks，白名单字段见 checks.OPGG_*；来源与合规说明见
opgg.py 顶部）。每套阵容带三个阶段：5级开局、7级中期、终局八人/九人阵容，前两段有战斗回合胜负计数。

树：同一开局（early.deckId 相同）为一棵树的根；中期（middle.deckId）相同的再合成一个节点；叶子 = 终局
阵容。开局羁绊页 = 开局棋盘里该羁绊 ≥ 2 名英雄的树（一套阵容可以出现在多个羁绊页）。凡是有 1/2 费英雄的
种族/职业都有入口；官方接口只给前 10 套 meta 阵容，覆盖不到的开局标「暂无路线」。
口径（全部是 OP.GG 的描述性统计，评级 C）：
- 回合胜率 = 该阶段 board 的战斗回合 win/play（OP.GG 应用内计数；win+lose 可小于 play，余下为平局等），
  样本是到达该阶段且最终成型为这套阵容的对局——回看式路线，含幸存者/选择偏差，不是拿牌建议。
- 终局行按 OP.GG 均名从好到差排序，并标注「OP.GG 数据，非本站评级」；OP.GG 评级（OP/S/A）照登并注明是
  它家的评级——本站的强度评级仍是「待验证」（首页说明不变）。
- 战斗召唤物（checks.OPGG_SUMMONS）商店买不到，不显示、脚注说明。"""
import hashlib
from html import escape as e

from comps import COPY_JS, item_img, num, pct

STAGE_LABEL = {"early": "开局", "middle": "中期"}
CHIP_MIN_UNITS = 2   # 阶段下方的羁绊行：numUnits >= 2 的羁绊，按人数降序
CHIP_MAX = 4
UNIFORM = "均名均匀基线 4.50 · 前四 50% · 吃鸡 12.5%（每局 8 人，按定义如此）"


def slug(api):
    return hashlib.md5(api.encode()).hexdigest()[:8]


def cheap_traits(official, champions, manual):
    """有 1/2 费英雄的羁绊（种族在前、职业在后，顺序同 sets/ 的人工行序）：开局羁绊的全集，逐赛季从
    官方数据推导。隐藏英雄（如 Lux 形态）和无羁绊的非商店单位不算。"""
    zh2api = {}
    for api, zh in official["traits"].items():
        zh2api.setdefault(zh, api)
    champ_ids = {(c.get("character_record") or {}).get("character_id") for c in champions}
    hide = {i for i, _ in manual["hide"]}
    bucket = {}
    for cid, info in official["units"].items():
        if cid in hide or cid not in champ_ids or not info.get("traits"):
            continue
        for zh in info["traits"]:
            bucket.setdefault(zh, []).append({"id": cid, "name": info["name"], "cost": info["cost"]})
    tmeta = official.get("trait_meta") or {}
    out = []
    for kind, rows in (("种族", manual["origins"]), ("职业", manual["classes"])):
        for api, name in rows:
            zh = official["traits"].get(api, name)
            units = sorted(bucket.get(zh) or [], key=lambda u: (u["cost"], u["name"]))
            cheap = [u for u in units if u["cost"] <= 2]
            if not cheap:
                continue
            out.append({"api": api, "zh": zh, "kind": kind, "icon": (tmeta.get(api) or {}).get("icon") or "",
                        "cheap": cheap, "all_units": units})
    return out


def stage_units(stage, official):
    """阶段 board 上的商店英雄 id（按出现顺序；召唤物过滤掉，由页面脚注说明）。"""
    out, dropped = [], 0
    for u in stage.get("units") or []:
        uid = u.get("key") or u.get("characterId")
        if uid in official["units"]:
            out.append(uid)
        else:
            dropped += 1
    return out, dropped


def deck_traits_zh(deck, trait_api_zh, which):
    """阶段的羁绊行：numUnits >= CHIP_MIN_UNITS，按人数降序，zh 名。"""
    rows = sorted((t for t in (deck[which].get("traits") or []) if (t.get("numUnits") or 0) >= CHIP_MIN_UNITS),
                  key=lambda t: (-(t.get("numUnits") or 0), t.get("key") or ""))
    return [(trait_api_zh.get(t["key"], t["key"]), t.get("numUnits")) for t in rows[:CHIP_MAX]]


def build_forest(decks):
    """[{early 组}]：{"eid", "decks", "early"（取第一套的 early), "mids": [{"mid", "decks"}]}，
    组内叶子按 OP.GG 均名升序，组间按场次合计降序。"""
    roots = {}
    for d in decks:
        roots.setdefault(d["early"].get("deckId") or d["id"], []).append(d)
    out = []
    for eid, ds in roots.items():
        mids = {}
        for d in ds:
            mids.setdefault(d["middle"].get("deckId") or d["id"], []).append(d)
        mid_rows = []
        for mid, md in mids.items():
            md.sort(key=lambda d: (d["stat"]["deck"].get("avgPlacement") or 9, d["id"]))
            mid_rows.append({"mid": mid, "decks": md, "middle": md[0]["middle"]})
        mid_rows.sort(key=lambda r: (min(d["stat"]["deck"].get("avgPlacement") or 9 for d in r["decks"]), r["mid"]))
        out.append({"eid": eid, "decks": ds, "early": ds[0]["early"], "mids": mid_rows,
                    "n": sum(d["stat"]["deck"].get("compsCount") or 0 for d in ds)})
    out.sort(key=lambda r: (-r["n"], r["eid"]))
    return out


def wr_html(stage):
    play, win = stage.get("play") or 0, stage.get("win") or 0
    if not play:
        return '<span class="vt-wr" title="OP.GG 这段暂无回合计数">回合胜率 —</span>'
    t = ("该阶段 board 的战斗回合胜率 = 胜 %s / 共 %s 回合（OP.GG 按阶段 board 计数，win+lose 可小于 play，余下为平局等；"
         "分叉节点的计数为走到下方任一终局的对局共用）。回看式统计，含幸存者偏差，不是拿牌建议") % (num(win), num(play))
    return '<span class="vt-wr" title="%s">回合胜率 <b>%s</b><small>%s 回合</small></span>' % (e(t), pct(win / play), num(play))


def board_html(uids, prev, deck_units, U, face, meta):
    """一行棋盘：按费用排；相比上一阶段新增的亮框；终局行带星级与装备（data-it 图标）。"""
    info = {}
    for u in deck_units or []:
        uid = u.get("key") or u.get("characterId")
        info[uid] = u
    cells = []
    for uid in sorted(uids, key=lambda x: (U(x).get("cost") or 9, U(x)["name"])):
        u = info.get(uid) or {}
        star = u.get("tier")
        star_html = ('<em class="vt-s3" title="OP.GG 展示阵容里该英雄为 %d★">%d★</em>' % (star, star)) if star and star >= 3 else ""
        its = "".join(item_img(meta, i) for i in (u.get("items") or [])[:3])
        its = ('<span class="vt-it">%s</span>' % its) if its else ""
        cell = '%s%s%s' % (face(U(uid), "sm"), star_html, its)
        cells.append('<span class="vt-u%s">%s</span>' % (" vt-nu" if prev is not None and uid not in prev else "", cell))
    return '<div class="vt-board">%s</div>' % "".join(cells)


def diff_line(uids, prev, U):
    if prev is None:
        return ""
    add = [U(u)["name"] for u in uids if u not in prev]
    # prev 是集合：迭代顺序随哈希种子变，排序后页面才能逐字节复现（README 的承诺）
    cut = [U(u)["name"] for u in sorted((x for x in prev if x not in uids),
                                        key=lambda x: (U(x).get("cost") or 9, U(x)["name"]))]
    parts = []
    if add:
        parts.append("拿牌：" + "、".join(add))
    if cut:
        parts.append('<span class="vt-cut">换下：%s</span>' % "、".join(cut))
    return ('<div class="vt-diff">%s</div>' % " · ".join(parts)) if parts else ""


def chips_line(pairs):
    if not pairs:
        return ""
    return '<div class="vt-tr">%s</div>' % " · ".join("%s <b>%s</b>" % (e(zh), n or "") for zh, n in pairs)


def stage_html(label, stage, uids, prev, deck_units, chips, U, face, meta, extra=""):
    return ('<div class="vt-stage"><div class="vt-sh"><span class="vt-lv">%s</span>%s%s</div>%s%s%s</div>' % (
        e(label), wr_html(stage), extra, board_html(uids, prev, deck_units, U, face, meta),
        diff_line(uids, prev, U), chips_line(chips)))


def leaf_html(d, prev, official, trait_api_zh, U, face, meta):
    st = d["stat"]
    dk = st["deck"]
    n = dk.get("compsCount") or 0
    uids, dropped = stage_units({"units": d["units"]}, official)
    tier = st.get("opTier") or ""
    tier_html = ('<span class="vt-tier" title="这是 OP.GG 自己的评级（OP/S/A），不是本站的：本站的强度评级仍为'
                 '「待验证」（见首页说明）">OP.GG 评级 %s</span>' % e(tier)) if tier else ""
    code = d.get("teamCode") or ""
    code_html = ('<button type="button" class="fb" data-copy="%s" title="OP.GG 提供的阵容码">复制阵容码</button>' % e(code)) if code else ""
    stats = ('<div class="vt-st4" title="OP.GG 的终局统计（%s 场）· %s · 选取率 = 该阵容占 OP.GG 样本的比例'
             '（其总量口径 OP.GG 未注明）">场次 <b>%s</b> · 均名 <b>%.2f</b> · 前四 <b>%s</b>'
             ' · 吃鸡 <b>%s</b> · 选取率 <b>%s</b></div>') % (
        num(n), UNIFORM, num(n), dk.get("avgPlacement") or 0, pct(dk.get("top4Rate") or 0, 1),
        pct(dk.get("winRate") or 0, 1), pct(dk.get("pickRate") or 0, 1))
    chips = sorted((t for t in d.get("traits") or [] if (t.get("numUnits") or 0) >= CHIP_MIN_UNITS),
                   key=lambda t: (-(t.get("numUnits") or 0), t.get("key") or ""))[:CHIP_MAX]
    html = ('<div class="vt-leaf"><div class="vt-sh"><span class="vt-lv">终局 · %d人口</span><b class="vt-nm">%s</b>%s%s</div>'
            '%s%s%s%s</div>') % (
        len(uids), e(d["name"]["zh_CN"]), tier_html, code_html,
        board_html(uids, prev, d["units"], U, face, meta), diff_line(uids, prev, U),
        chips_line([(trait_api_zh.get(t["key"], t["key"]), t.get("numUnits")) for t in chips]), stats)
    return html, dropped


def tree_html(root, official, trait_api_zh, U, face, meta):
    early_ids, drop_e = stage_units(root["early"], official)
    lv_e = root["early"].get("level")
    blocks = [stage_html("等级%s · 开局" % lv_e, root["early"], early_ids, None, root["early"].get("units"),
                         deck_traits_zh(root["decks"][0], trait_api_zh, "early"), U, face, meta,
                         extra='<span class="vt-n">%d 条路线</span>' % len(root["decks"]))]
    kids = []
    dropped = drop_e
    for mr in root["mids"]:
        mid_ids, drop_m = stage_units(mr["middle"], official)
        dropped += drop_m
        leaf_parts = [leaf_html(d, set(mid_ids), official, trait_api_zh, U, face, meta) for d in mr["decks"]]
        dropped += sum(dr for _, dr in leaf_parts)
        leaves = "".join(h for h, _ in leaf_parts)
        kids.append('<div class="vt-mid">%s<div class="vt-kids">%s</div></div>' % (
            stage_html("等级%s · 中期" % mr["middle"].get("level"), mr["middle"], mid_ids, set(early_ids),
                       mr["middle"].get("units"), deck_traits_zh(mr["decks"][0], trait_api_zh, "middle"), U, face, meta),
            leaves))
    note = ('<p class="hint">本树隐去 %d 个战斗召唤物（商店买不到，OP.GG 把它们也算进棋盘）。</p>' % dropped) if dropped else ""
    return '<div class="vt-tree">%s<div class="vt-kids">%s</div>%s</div>' % (blocks[0], "".join(kids), note)


def caveat_box(n_decks):
    return ('<div class="box"><p>数据来自 <b>OP.GG 官方数据接口</b>（op.gg 提供给 AI 代理的 MCP 接口，本站用它'
            '替代被条款禁止的网页抓取），当前提供 <b>%d 套 meta 阵容</b>的三阶段路线：<b>5级开局 → 7级中期 → 终局</b>。'
            '评级 C（描述性）。</p>'
            '<p class="hint">回合胜率 = 该阶段 board 的战斗回合胜负计数（win/play，余下为平局等；OP.GG 按阶段 board'
            ' 计数，分叉节点的计数为走到下方任一终局的对局共用），样本是<b>最终成型为下方终局</b>的对局：'
            '这是按终局回看的路线统计，活到后期的对局才会被计入——含幸存者偏差，'
            '描述“成型者当时拿了什么”，不是“照这样拿能赢”的建议。终局行按 OP.GG 均名从好到差排序'
            '（<b>OP.GG 数据，非本站评级</b>；%s）。「OP.GG 评级」为其自家 OP/S/A 分级，本站的强度评级仍为'
            '「待验证」。亮框 = 相比上一阶段新增的英雄；覆盖不到的开局羁绊标「暂无路线」，会随 OP.GG 数据更新。</p></div>') % (
        n_decks, UNIFORM)


def build_pages(decks, official, champions, manual, U, face, meta):
    """返回 (变阵路线页 body, {"trees/<slug>.html": (标题, body)})。"""
    trait_api_zh = official["traits"]
    traits = cheap_traits(official, champions, manual)
    forest_all = build_forest(decks)

    def member(root, zh):
        ids, _ = stage_units(root["early"], official)
        cnt = sum(1 for uid in ids if zh in (official["units"][uid].get("traits") or []))
        return cnt >= 2
    pages, seen = {}, {}
    cards = []
    for t in traits:
        roots = [r for r in forest_all if member(r, t["zh"])]
        sg = slug(t["api"])
        if sg in seen:
            raise SystemExit("trees 详情页 slug 冲突：%s / %s" % (t["api"], seen[sg]))
        seen[sg] = t["api"]
        cheap_faces = "".join(face(U(u["id"]), "sm") for u in t["cheap"])
        n_routes = sum(len(r["decks"]) for r in roots)
        if roots:
            cards.append('<a class="vt-card" href="trees/%s.html"><img src="%s" alt="" loading="lazy" onerror="this.remove()">'
                         '<b>%s</b><small>%s · %d 棵树 · %d 条路线</small><div class="vt-cheap">%s</div></a>' % (
                             sg, e(t["icon"]), e(t["zh"]), t["kind"], len(roots), n_routes, cheap_faces))
        else:
            cards.append('<div class="vt-card vt-none"><img src="%s" alt="" loading="lazy" onerror="this.remove()">'
                         '<b>%s</b><small>%s · 暂无路线</small><div class="vt-cheap">%s</div>'
                         '<small class="hint">OP.GG 当前 meta 阵容里没有以此开局的成型路线</small></div>' % (
                             e(t["icon"]), e(t["zh"]), t["kind"], cheap_faces))
        if not roots:
            continue
        trees_html = "".join(tree_html(r, official, trait_api_zh, U, face, meta) for r in roots)
        body = ''.join([
            '<section class="vt-det"><p><a href="../trees.html" style="color:var(--ac)">← 返回变阵路线</a></p>',
            '<div class="vt-head"><img src="%s" alt="" loading="lazy" onerror="this.remove()"><h2>%s 开局 · 变阵树</h2>'
            '<span class="cmeta">%s · 1/2 费：%s</span></div>' % (
                e(t["icon"]), e(t["zh"]), t["kind"], "、".join(u["name"] for u in t["cheap"])),
            caveat_box(len(decks)),
            '<p class="hint">树根 = 开局棋盘（该羁绊 ≥ 2 名英雄）；分叉 = 同一开局在 OP.GG 数据里演变出的不同'
            '中期/终局。拿牌/换下 = 相邻阶段的差异。</p>',
            trees_html,
            '</section>', COPY_JS])
        pages["trees/%s.html" % sg] = ("%s 开局 · 变阵路线" % t["zh"], body)
    covered = sum(1 for c in cards if "vt-none" not in c)
    page = ('<section id="vtrees"><h2>变阵路线 <small class="hint">按开局羁绊分页 · OP.GG 官方数据接口 · 评级 C（描述性）'
            '</small></h2>%s<p class="hint">%d 个开局羁绊（有 1/2 费英雄的种族/职业，逐赛季由官方数据推导），'
            '其中 %d 个有路线数据。</p><div class="vt-grid">%s</div></section>') % (
        caveat_box(len(decks)), len(traits), covered, "".join(cards))
    return page, pages


CSS = '''.vt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.vt-card{display:block;background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:12px;color:var(--tx);text-decoration:none}
.vt-card img{width:26px;height:26px;background:#000;border-radius:50%;padding:2px;float:right}
.vt-card b{font-size:15px}.vt-card small{display:block;color:var(--mu);margin:2px 0 8px}
a.vt-card:hover{border-color:var(--ac)}.vt-card.vt-none{opacity:.55}
.vt-cheap{display:flex;flex-wrap:wrap;gap:4px}
.vt-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0}
.vt-head img{width:34px;height:34px;background:#000;border-radius:50%;padding:3px}.vt-head h2{margin:0}
.vt-tree{background:var(--pn);border:1px solid var(--bd);border-radius:var(--r);padding:14px;margin:14px 0}
.vt-kids{margin:10px 0 0 14px;padding-left:14px;border-left:2px solid var(--bd)}
.vt-mid{margin:12px 0}
.vt-stage,.vt-leaf{background:var(--pn2);border:1px solid var(--bd);border-radius:10px;padding:10px 12px;margin:8px 0}
.vt-leaf{border-left:3px solid var(--ac)}
.vt-sh{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-bottom:8px}
.vt-lv{background:var(--bg);border:1px solid var(--bd);border-radius:99px;padding:1px 10px;font-size:12px;color:var(--mu)}
.vt-nm{font-size:15px}
.vt-wr{font-size:12px;color:var(--mu);cursor:help}.vt-wr b{color:var(--tx);font-size:14px}.vt-wr small{margin-left:4px}
.vt-n{font-size:12px;color:var(--mu)}
.vt-tier{font-size:12px;color:var(--mu);border:1px dashed var(--bd);border-radius:99px;padding:1px 10px;cursor:help}
.vt-board{display:flex;flex-wrap:wrap;gap:6px;align-items:flex-start}
.vt-u{position:relative;display:inline-flex;flex-direction:column;align-items:center;gap:2px;padding:2px;border-radius:8px}
.vt-u.vt-nu{outline:2px solid var(--ac);outline-offset:0}
.vt-s3{position:absolute;top:-6px;right:-4px;font-style:normal;font-size:10px;font-weight:800;color:#111;background:var(--ac);border-radius:4px;padding:0 3px;cursor:help}
.vt-it{display:flex;gap:1px}.vt-it img{width:16px;height:16px;border-radius:3px;cursor:help}
.vt-diff{font-size:12px;color:var(--tx);margin-top:6px}.vt-diff .vt-cut{color:var(--mu)}
.vt-tr{font-size:12px;color:var(--mu);margin-top:4px}.vt-tr b{color:var(--ac)}
.vt-st4{font-size:12px;color:var(--mu);margin-top:8px;cursor:help}.vt-st4 b{color:var(--tx)}
@media(max-width:800px){.vt-kids{margin-left:4px;padding-left:8px}}'''
