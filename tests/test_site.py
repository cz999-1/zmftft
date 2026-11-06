"""python3 -m unittest discover -s tests   (stdlib only, no network)

The tests use a made-up snapshot (tests/fixture.py); the real one is not in the repository. When a real
snapshot exists in cache/snapshots/, it is checked too."""
import contextlib, copy, io, json, re, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site, checks, fetch_data, fixture
from generate_tft_table import load_manual

MANUAL = sorted((ROOT / "sets").glob("set*.json"))[-1]
LOCAL = sorted((ROOT / "cache" / "snapshots").glob("set*/*.json"), key=lambda p: p.stat().st_mtime)


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manual = json.loads(MANUAL.read_text(encoding="utf-8"))
        cls.snap = fixture.snapshot(cls.manual)

    def problems(self, snap=None, manual=None):
        return checks.check(snap or self.snap, manual or self.manual)

    def test_fixture_passes_the_guard(self):
        self.assertEqual(self.problems(), [])

    def test_local_snapshot_passes_the_guard(self):
        if not LOCAL:
            self.skipTest("no snapshot in cache/snapshots/ (run python3 fetch_data.py)")
        snap = fetch_data.load(LOCAL[-1])
        self.assertEqual(checks.check(snap, load_manual(snap["meta"]["set"])), [])

    def test_pages_render_from_the_snapshot_alone(self):
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d))
            pages = {p.name: p.read_text(encoding="utf-8") for p in Path(d).glob("*.html")}
            self.assertEqual(set(pages), {"index.html", "comps.html", "trees.html", "class.html", "origin.html",
                                          "heroes.html", "synergy.html", "craft.html"})
            self.assertTrue(list(Path(d, "synergy").glob("*.html")))
            details = {"comps/" + p.name: p.read_text(encoding="utf-8") for p in Path(d, "comps").glob("*.html")}
            self.assertEqual(len(details), len(self.snap["comp_groups"]))
            tdetails = {"trees/" + p.name: p.read_text(encoding="utf-8") for p in Path(d, "trees").glob("*.html")}
            self.assertTrue(tdetails)
            self.assertIn("版本 %s" % self.snap["meta"]["patch_label"], pages["index.html"])
            for gone in ("阵眼—", "三星价值</h3>", "羁绊强度</h3>", "最强阵容</h3>", "站位结论（"):
                for name, html in list(pages.items()) + list(details.items()) + list(tdetails.items()):
                    self.assertNotIn(gone, html, name)
            self.assertIn("人工标注", pages["class.html"])
            for page in ("class.html", "origin.html"):  # cards: 选率 and 满装率, no 均名 / 前四 (owner, 2026-11-01)
                self.assertIn("满装率", pages[page]); self.assertIn("选率", pages[page])
                self.assertNotIn("均名", pages[page]); self.assertNotIn("前四", pages[page])
            # item icons carry their recipe data (owner, 2026-11-01): per page, one entry per item shown, all components
            for page in ("class.html", "origin.html", "heroes.html", "comps.html", "index.html") + tuple(details) + tuple(tdetails):
                html = pages.get(page) or details.get(page) or tdetails[page]
                tips = json.loads(re.search(r'<script type="application/json" id="itd">(.*?)</script>', html, re.S).group(1))
                shown = set(re.findall(r'data-it="([^"]+)"', html))
                self.assertTrue(shown); self.assertEqual(set(tips["i"]), shown)
                self.assertEqual(sorted(tips["c"]), sorted(c for c, _, _ in self.snap["craft"]["components"]))
            for page in ("synergy.html", "craft.html"):
                self.assertNotIn('id="itd"', pages[page])
            allpages = list(pages.values()) + list(details.values()) + list(tdetails.values()) + [
                p.read_text(encoding="utf-8") for p in Path(d, "synergy").glob("*.html")]
            self.assertFalse([h for h in allpages if "communitydragon.org/latest/" in h])
            import html
            self.assertTrue(all(html.escape(build_site.RIOT_NOTICE) in h for h in allpages))  # Riot's notice on every page
            self.assertTrue(all(html.escape(build_site.RIOT_BOILERPLATE) in h for h in allpages))  # and the API boilerplate
            self.assertFalse([h for h in allpages if "build_site.py" in h])  # build commands live in the README
            self.assertTrue(all("communitydragon.org/16.21/" in h for h in allpages if "<img" in h))

    def test_synergy_page_shows_both_matrices_with_the_metric_toggle(self):
        """种族×职业 matrix beside 种族×种族, a 均名/吃鸡率 cell toggle (no-JS default shows 均名),
        and front/mid/back-row unit counts in the trait headers' tooltips (owner, 2026-11-01)."""
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d))
            h = Path(d, "synergy.html").read_text(encoding="utf-8")
            details = [p.read_text(encoding="utf-8") for p in Path(d, "synergy").glob("*.html")]
        for needle in ("种族 × 种族", "种族 × 职业", 'data-v="win"', 'data-v="lift"', 'class="mp"',
                       'class="mw"', 'class="ml"', "均匀基线 12.5%", "个阵容组", 'id="synx"'):
            self.assertIn(needle, h)
        self.assertRegex(h, r'<th class="rh" title="[^"]*前排 \d+ · 中排 \d+ · 后排 \d+')
        cls_names = {n for _, n in self.manual["classes"]}
        self.assertTrue(any(("× %s</h2>" % n) in dd for dd in details for n in cls_names))

    def test_synergy_marks_single_five_cost_traits(self):
        """羁绊 with exactly one unit of cost 5 get the orange s5/s5c marking — 五费英雄搭配什么都强,
        so those rows/columns carry little information (owner, 2026-11-01). A solo 4-cost stays unmarked."""
        import synergy
        roster = [
            {"id": "u1", "name": "U1", "cost": 5, "pos": "back", "origins": ["独五"], "classes": ["法师"]},
            {"id": "u2", "name": "U2", "cost": 2, "pos": "front", "origins": ["群族"], "classes": ["法师"]},
            {"id": "u3", "name": "U3", "cost": 3, "pos": "front", "origins": ["群族"], "classes": ["斗士"]},
            {"id": "u4", "name": "U4", "cost": 4, "pos": "mid", "origins": ["独四"], "classes": ["斗士"]},
        ]
        comps = [{"units": ["u1", "u2", "u3", "u4"], "count": 100, "place": 4.0, "top4": 50, "win": 13, "group": 0}]
        um = {r["id"]: r for r in roster}
        mat, _ = synergy.build(comps, roster, ["独五", "群族", "独四"], ["法师", "斗士"],
                               1000, lambda u, s="": "", um.get)
        self.assertIn('<th class="rh s5" title="独五：', mat)
        self.assertIn('<th class="vh s5" title="独五：', mat)
        self.assertIn('<th class="rh" title="独四：', mat)   # solo but 4-cost: unmarked
        self.assertIn("只有一个五费英雄", mat)              # header tooltip carries the reason
        self.assertIn('<td class="s5c sg thin"><a', mat)     # 5-cost mark + single comp group + thin (n=100)
        self.assertIn('class="s5l"', mat)                    # legend in the hint
        self.assertIn('<b class="ml">—</b>', mat)            # one comp: every pair is nested, 协同差 undefined
        self.assertNotIn('<b class="ml">+', mat)
        self.assertIn("· 1 个阵容组", mat)

    def test_heroes_page_is_labelled_and_degrades_without_riot_data(self):
        """The heroes page (owner request 2026-11-01) shows 均名/吃鸡率 with n, grade and the
        survivorship note on every build; without --riot data the hover panel says so."""
        hide = {i for i, _ in self.manual["hide"]}
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d))
            h = Path(d, "heroes.html").read_text(encoding="utf-8")
        for needle in ("英雄数据", "吃鸡率", "均名 = 平均名次", "评级 C（描述性）", "这局本来就在赢",
                       'data-f="s"', 'data-win="', "暂无自采样本", "星级数据", "盘"):
            self.assertIn(needle, h)
        self.assertEqual(h.count('class="hrow"'),
                         len([c for c in self.snap["champions"] if c["character_record"]["character_id"] not in hide]))
        self.assertIn("三*", h)  # a unit whose trios all miss the n >= 500 bar falls back to the most common trio

    def test_heroes_page_renders_the_riot_panel(self):
        riot = fixture.riot_doc(self.snap)
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d), riot)
            h = Path(d, "heroes.html").read_text(encoding="utf-8")
        for needle in ("3★ 满装 · 所在阵容", "自采 Riot API", "仅本地预览", "(95% ", 'class="hpc"',
                       "CHALLENGER/MASTER", "按均名排"):
            self.assertIn(needle, h)
        first_cells = riot["units"][next(iter(riot["units"]))]["cells"]
        self.assertIn("均名 <b>%.2f</b>" % first_cells[0]["place_mean"], h)

    def test_build_refuses_riot_data_that_does_not_match(self):
        riot = fixture.riot_doc(self.snap)
        riot["population"]["set"] += 1
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                build_site.render(self.snap, Path(d), riot)
        riot = fixture.riot_doc(self.snap)
        riot["units"][next(iter(riot["units"]))]["cells"][0]["family"] = 999
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                build_site.render(self.snap, Path(d), riot)

    def test_synergy_page_renders_the_crawl_matrices(self):
        """Layer 2 (owner, 2026-11-01): with the tft-lab synergy export the page adds crawl-based
        matrices under the game's own activation (tier_current >= 1), every metric with a 95% CI;
        without the export the section is absent."""
        rs = fixture.riot_synergy_doc(self.snap, self.manual)
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d), None, rs)
            h = Path(d, "synergy.html").read_text(encoding="utf-8")
        for needle in ('id="syncrawl"', "自采对局搭配矩阵", "tier_current", "（95% ", 'class="cv"',
                       "仅限本地预览，不要推送上线", "职业 × 职业的 1 对不入矩阵（重叠计 700 盘）",
                       "整群自助法", "自采 Riot API"):
            self.assertIn(needle, h)
        crawl = h.split('id="syncrawl"')[1].split("</section>")[0]
        for needle in ('<b class="mp">', '<b class="mw">', '<b class="ml">', 'class="thin"'):
            self.assertIn(needle, crawl)  # all three toggle metrics + the thin (n < 1000) fade
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d))
            h = Path(d, "synergy.html").read_text(encoding="utf-8")
        self.assertNotIn("syncrawl", h)

    def test_build_refuses_synergy_data_that_does_not_match(self):
        rs = fixture.riot_synergy_doc(self.snap, self.manual)
        rs["population"]["set"] += 1
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                build_site.render(self.snap, Path(d), None, rs)
        rs = fixture.riot_synergy_doc(self.snap, self.manual)
        rs["pairs"][0]["a"] = "DA_Fixture_Unknown"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                build_site.render(self.snap, Path(d), None, rs)

    def test_crawl_section_counts_unplaced_traits(self):
        """A pair whose trait maps to a Chinese name outside the origin/class rows is counted in
        the hint, never rendered as a row or column (this window's case: 日月双蚀)."""
        import synergy
        rs = fixture.riot_synergy_doc(self.snap, self.manual)
        zh = {t: n for t, n in self.manual["classes"] + self.manual["origins"]}
        zh["DA_Fixture_Hidden"] = "隐藏羁绊"
        rs["pairs"].append(dict(rs["pairs"][0], a="DA_Fixture_Hidden"))
        ori = [n for _, n in self.manual["origins"]]
        cls = [n for _, n in self.manual["classes"]]
        html = synergy.crawl_section(rs, zh, ori, cls, {o: o for o in ori}, {c: c for c in cls},
                                     set(), set(), "测试标签")
        self.assertIn("涉及未展示羁绊（隐藏羁绊）的 1 对不入矩阵", html)
        self.assertNotIn(">隐藏羁绊<", html)  # not a row/column header anywhere

    def render_comps(self, rc=None):
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d), None, None, rc)
            page = Path(d, "comps.html").read_text(encoding="utf-8")
            index = Path(d, "index.html").read_text(encoding="utf-8")
            details = {p.name: p.read_text(encoding="utf-8") for p in Path(d, "comps").glob("*.html")}
        return page, index, details

    def test_comps_page_sorts_by_count_and_keeps_the_no_ranking_promise(self):
        """The comps page (owner, 2026-11-03) lists tactics.tools comp groups by 场次 (popularity), says it is
        not a strength ranking, and the home page leads with the same cards; the 不放排行 promise stays."""
        page, index, _ = self.render_comps()
        counts = [int(x.replace(",", "")) for x in re.findall(r"<span>场次</span><b>([\d,]+)</b>", page)]
        self.assertEqual(counts, sorted((g["count"] for g in self.snap["comp_groups"]), reverse=True))
        for needle in ("不是强度排行", "按场次（人气）排序", "评级 C（描述性）", "这局本来就在赢", "不说明照这样玩能赢"):
            self.assertIn(needle, page)
        self.assertEqual(index.count('<article class="cc">'), len(self.snap["comp_groups"]))
        self.assertIn('href="comps.html"', index)
        self.assertIn("测出之前这里不放排行", index)
        self.assertLess(index.index('id="comps"'), index.index('id="ins"'))  # the cards lead the home page

    def test_comps_page_cards_show_stats_with_baselines_and_pending_slot(self):
        page, _, _ = self.render_comps()
        gs = self.snap["comp_groups"]
        n = sum(g["count"] for g in gs)
        base = sum(g["place"] * g["count"] for g in gs) / n
        self.assertIn("基线 %.2f" % base, page)
        self.assertIn("均名 <b>%.2f</b>" % base, page)
        self.assertIn("均匀基线 4.50 / 50% / 12.5%", page)
        self.assertEqual(page.count("强度评级：待验证"), len(gs))
        for label in ("<span>场次</span>", "<span>选率</span>", "<span>均名</span>", "<span>前四率</span>", "<span>吃鸡率</span>"):
            self.assertEqual(page.count(label), len(gs), label)
        self.assertIn("占 %.1f%%" % (n / self.snap["meta"]["total"] * 100), page)  # coverage of all boards

    def test_comps_detail_pages_render(self):
        _, _, details = self.render_comps()
        self.assertEqual(len(details), len(self.snap["comp_groups"]))
        for name, h in details.items():
            for needle in ("← 返回阵容", "变体（八人阵容 + 纹章）", 'class="pbx"', "人工标注示意（非实测站位）",
                           "为什么没有", "强化符文", "重置（D 牌）次数", "相似阵容", "只给分布", 'class="ctabs"',
                           '<a href="../comps.html" class="cur">阵容</a>', 'href="../index.html"'):
                self.assertIn(needle, h, name)
            self.assertNotIn("compcrawl", h)
            self.assertNotIn("该等级均名", h)  # final level: distribution only, no per-level placement
            # emblem icons in the variants table are size-constrained (.spx), never bare full-size imgs
            for m in re.finditer(r'<td class="us">(.*?)</td>', h):
                self.assertNotRegex(m.group(1), r'</span><img [^>]*data-it=', name)
        self.assertTrue(any('<span class="spx">' in h for h in details.values()))  # fixture has spatItems variants

    def test_comps_pages_mark_three_star_and_item_carries(self):
        """★★★ gold = 3-star on >= 50% of the group's boards, grey = 20-50%; 1st/2nd/3rd = the units holding the
        most completed items, with their most-carried items (descriptive labels, not advice)."""
        page, _, _ = self.render_comps()
        cards = re.findall(r'<article class="cc">(.*?)</article>', page, re.S)
        self.assertEqual(len(cards), len(self.snap["comp_groups"]))
        for card in cards:  # fixture: one unit 3-star on 60% of boards, one on 30%, two carries
            self.assertEqual(card.count('<div class="cs maj"'), 1)
            self.assertEqual(card.count('<div class="cs min"'), 1)
            self.assertIn(">1st</em>", card); self.assertIn(">2nd</em>", card); self.assertNotIn(">3rd</em>", card)
            self.assertEqual(len(re.findall(r'<span class="ci">(?:<img [^>]*data-it="[^"]+"[^>]*>){3}</span>', card)), 2)
        for needle in ("不是“该追三星", "不说明给它装备更能赢"):
            self.assertIn(needle, page)

    def test_comps_page_renders_the_crawl_section(self):
        """With the tft-lab comps export (preview builds only) the page adds a crawl table and each detail page a
        crawl section, every number with a 95% CI and the red preview-only line; without it neither appears."""
        rc = fixture.riot_comps_doc(self.snap)
        page, index, details = self.render_comps(rc)
        for needle in ('id="compcrawl"', "自采对局对照", "仅限本地预览，不要推送上线", "(95% ", "自采 Riot API",
                       "不按自采数字排"):
            self.assertIn(needle, page)
        self.assertNotIn("compcrawl", index)  # the home page never carries crawl data
        with_cell = [h for h in details.values() if "成装份额" in h]
        self.assertEqual(len(with_cell), len(rc["cells"]))
        self.assertTrue(all('id="compcrawl"' in h and "仅限本地预览" in h for h in details.values()))
        self.assertEqual(sum("自采样本里没有归入本组的棋盘" in h for h in details.values()), 1)
        page, index, details = self.render_comps()
        for h in [page, index] + list(details.values()):
            self.assertNotIn("compcrawl", h)
            self.assertNotIn("仅限本地预览", h)

    def test_build_refuses_comps_data_that_does_not_match(self):
        for mutate in (lambda rc: rc["population"].update(set=rc["population"]["set"] + 1),
                       lambda rc: rc.update(schema="tftlab-heroes/1"),
                       lambda rc: rc["cells"][0].update(family=999),
                       lambda rc: rc["families"][0].update(units=list(reversed(rc["families"][0]["units"]))),
                       lambda rc: rc["families"][0].update(tt_count=rc["families"][0]["tt_count"] + 1),
                       lambda rc: rc["families"][0].update(variants=rc["families"][0]["variants"] + 1),
                       lambda rc: rc["families"].pop(),
                       lambda rc: rc["cells"][0]["traits"][0].update(trait="DA_Fixture_UnknownTrait"),
                       lambda rc: rc["cells"][0]["units"][0].update(unit="DA_Fixture_Unknown")):
            rc = fixture.riot_comps_doc(self.snap)
            mutate(rc)
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(SystemExit):
                    build_site.render(self.snap, Path(d), None, None, rc)

    def test_duplicate_tactics_variants_count_once(self):
        """tactics.tools lists some variants twice, field for field (the same boards): the comps cards, variant
        tables and the synergy matrices count each once (pre-push review, 2026-11-03)."""
        snap = copy.deepcopy(self.snap)
        g0 = [c for c in snap["comps"] if c["group"] == 0]
        snap["comps"].append(copy.deepcopy(g0[0]))
        with tempfile.TemporaryDirectory() as d:
            build_site.render(snap, Path(d))
            page = Path(d, "comps.html").read_text(encoding="utf-8")
            syn = Path(d, "synergy.html").read_text(encoding="utf-8")
        self.assertIn("%d 个展示变体" % len(g0), page)
        self.assertNotIn("%d 个展示变体" % (len(g0) + 1), page)
        self.assertIn("共 {:,} 个棋盘".format(sum(c["count"] for c in self.snap["comps"])), syn)

    def test_synergy_nested_pairs_show_no_lift(self):
        """When every board with one trait also carries the other, 协同差 reduces to baseline minus the other
        trait's marginal, whatever the pair does: the cell shows — instead of a number."""
        import synergy
        roster = [{"id": "u%d" % k, "name": "U%d" % k, "cost": 1, "pos": "front", "origins": [o], "classes": ["职"]}
                  for k, o in ((1, "甲"), (2, "乙"), (3, "丙"), (4, "丁"))]
        comps = [{"units": ["u1", "u2", "u4"], "count": 100, "place": 3.0, "top4": 70, "win": 20, "group": 0},
                 {"units": ["u1", "u3"], "count": 100, "place": 5.0, "top4": 40, "win": 10, "group": 1},
                 {"units": ["u2", "u3"], "count": 100, "place": 4.0, "top4": 50, "win": 12, "group": 2}]
        um = {r["id"]: r for r in roster}
        mat, _ = synergy.build(comps, roster, ["甲", "乙", "丙", "丁"], ["职"], 1000, lambda u, s="": "", um.get)
        lift = lambda a, b: re.search(r'title="%s × %s ·[^"]*"><b class="mp">[^<]*</b><b class="mw">[^<]*</b><b class="ml">([^<]*)</b>'
                                      % (a, b), mat).group(1)
        self.assertRegex(lift("甲", "乙"), r"^[+-]\d\.\d\d$")   # 100 of 200 甲 boards: defined
        self.assertEqual(lift("甲", "丁"), "—")                 # every 丁 board carries 甲: nested
        self.assertIn("无从定义", mat)

    def test_comps_detail_pages_keep_items_to_counts_and_state_intervals(self):
        """Per-item / per-pair 均名 are not shown (the owner's decision covered per-comp numbers only); every comps
        page states its 95% interval bound; the variant table carries its survivorship caveat."""
        page, index, details = self.render_comps()
        for h in [page, index]:
            self.assertIn("95% 区间半宽", h)
        for name, h in details.items():
            self.assertNotIn("100%%", h, name)
            self.assertNotIn("常见两件（场次 · 均名）", h, name)
            self.assertNotIn("均名 %", h, name)
            self.assertIn("95% 区间半宽", h, name)
            self.assertIn("不说明该选哪个变体", h, name)
            self.assertIn("每盘成装<small>（本组全部棋盘）</small>", h, name)
        snap = copy.deepcopy(self.snap)
        tr = snap["comp_groups"][0]["traits"][0][0]
        snap["official"]["trait_meta"][tr]["breaks"] = [2, 2, 4]   # a repeated official breakpoint (宿敌 is 1/1/2)
        with tempfile.TemporaryDirectory() as d:
            build_site.render(snap, Path(d))
            h = Path(d, "comps.html").read_text(encoding="utf-8")
        self.assertIn("（2 &gt; 4）", h)
        self.assertNotIn("2 &gt; 2", h)

    def test_committed_pages_carry_no_crawl_data(self):
        """The pages in the repository (what GitHub Pages serves) never carry crawl / development-key data,
        and no player identifier of any source."""
        pages = sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("comps/*.html")) + sorted(ROOT.glob("synergy/*.html")) \
            + sorted(ROOT.glob("trees/*.html"))
        self.assertTrue(pages)
        for p in pages:
            h = p.read_text(encoding="utf-8")
            for marker in ("syncrawl", "compcrawl", "仅限本地预览", "自采 Riot API", "自采数据",
                           "puuid", "gameName", "tagLine", "recentWins"):
                self.assertNotIn(marker, h, "%s: %s" % (p.name, marker))

    def render_trees(self):
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d))
            page = Path(d, "trees.html").read_text(encoding="utf-8")
            details = {p.name: p.read_text(encoding="utf-8") for p in Path(d, "trees").glob("*.html")}
        return page, details

    def test_trees_page_lists_every_cheap_trait_and_labels_the_source(self):
        """变阵路线 (owner, 2026-11-05): one card per trait that has a 1/2-cost unit (derived from the official
        data, so it survives a set change); covered traits link to their tree page, the rest say 暂无路线; the
        data is OP.GG's official MCP interface and every page says so, with the survivorship caveat and without
        touching the site's own 待验证 promise."""
        import trees as trees_mod
        page, details = self.render_trees()
        cheap = trees_mod.cheap_traits(self.snap["official"], self.snap["champions"], self.manual)
        self.assertTrue(cheap)
        self.assertEqual(page.count('class="vt-card'), len(cheap))
        self.assertEqual(page.count('href="trees/'), len(details))
        self.assertIn("暂无路线", page)  # the fixture's 3 decks cover at most 2 opener traits
        for needle in ("OP.GG 官方数据接口", "评级 C（描述性）", "幸存者偏差", "非本站评级", "待验证",
                       "5级开局 → 7级中期 → 终局", "回合胜率"):
            self.assertIn(needle, page)
        # the monster without traits and the hidden forms never become opener traits
        self.assertFalse([t for t in cheap if not t["cheap"]])
        hide = {i for i, _ in self.manual["hide"]}
        self.assertFalse([u for t in cheap for u in t["cheap"] if u["id"] in hide or u["id"] == "TFT_FixtureMonster"])

    def test_trees_detail_shows_the_fork_the_winrates_and_filters_summons(self):
        """Decks A and B share the level-5 opener and the level-7 mid board (same deckId), so their trait page
        shows ONE opener node, ONE mid node and TWO final leaves sorted by OP.GG avgPlacement; deck C's page
        shows 回合胜率 — for the zero-count stage and filters the combat summon with a footnote."""
        page, details = self.render_trees()
        ab = next(h for h in details.values() if "测试阵容甲" in h)
        self.assertIn("测试阵容乙", ab)
        self.assertEqual(ab.count("· 开局</span>"), 1)   # shared opener renders once
        self.assertEqual(ab.count("· 中期</span>"), 1)   # shared mid board renders once
        self.assertEqual(ab.count('class="vt-leaf"'), 2)
        self.assertLess(ab.index("测试阵容甲"), ab.index("测试阵容乙"))  # 均名 3.2 before 4.1 (OP.GG order, labeled)
        self.assertIn("回合胜率 <b>56%</b>", ab)          # early: 2800 / 5000
        self.assertIn('class="vt-u vt-nu"', ab)          # new units vs the previous stage are highlighted
        self.assertIn("拿牌：", ab)
        for needle in ("OP.GG 评级", "复制阵容码", '<a href="../trees.html" class="cur">变阵路线</a>',
                       'href="../index.html"', "本页数据来源", "opgg-mcp"):
            self.assertIn(needle, ab)
        c = next(h for h in details.values() if "测试阵容丙" in h)
        self.assertIn("回合胜率 —", c)
        self.assertNotIn("DA_Elderwood18_Lifeblossom", c)
        self.assertIn("战斗召唤物", c)
        # the header pills describe the page's own source: no tactics.tools board count / scope on trees pages
        for h in [page] + list(details.values()):
            self.assertIn("OP.GG 官方接口 · %d 套 meta 阵容" % len(self.snap["opgg_decks"]), h)
            self.assertIn("样本与分段 OP.GG 未注明", h)
            self.assertNotIn("{:,} 个棋盘".format(self.snap["meta"]["total"]), h)
            self.assertNotIn("排位 · %s" % self.snap["meta"]["rank_label"], h)

    def test_builds_are_byte_identical_across_runs(self):
        """README promises byte-identical rebuilds from one snapshot; 换下 order must not depend on the hash seed
        (set iteration). Two in-process renders must match; the hash-seed case is covered by sorting in trees.py."""
        import subprocess
        outs = []
        for k in range(2):
            with tempfile.TemporaryDirectory() as d:
                env = {"PYTHONUTF8": "1", "PYTHONHASHSEED": str(k + 1), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
                with tempfile.TemporaryDirectory() as sd, mock.patch.object(fetch_data, "SNAPSHOTS", Path(sd)):
                    snap_path = fetch_data.save(self.snap)
                    code = ("import sys; sys.path.insert(0, %r); import build_site, fetch_data, json; from pathlib import Path; "
                            "build_site.render(fetch_data.load(%r), Path(%r))") % (str(ROOT), str(snap_path), d)
                    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
                    self.assertEqual(r.returncode, 0, r.stderr[-2000:])
                    outs.append({p.relative_to(d).as_posix(): p.read_bytes() for p in Path(d).rglob("*.html")})
        self.assertEqual(sorted(outs[0]), sorted(outs[1]))
        diff = [f for f in outs[0] if outs[0][f] != outs[1][f]]
        self.assertEqual(diff, [])

    def test_guard_catches_opgg_problems(self):
        self.check_catches(lambda s, m: s.pop("opgg_decks"), "opgg_decks")
        self.check_catches(lambda s, m: s["opgg_decks"][0].update(recentWins=[]), "白名单外")
        self.check_catches(lambda s, m: s["opgg_decks"][0]["name"].update(zh_CN="x puuid y"), "玩家字段")
        self.check_catches(lambda s, m: s["opgg_decks"][0]["early"]["units"][0].update(characterId="DA_New19_Summon"),
                           "OPGG_SUMMONS")
        self.check_catches(lambda s, m: s["opgg_decks"][0].update(teamCode="02xTFTSet%d" % (s["meta"]["set"] + 1)), "阵容码")
        self.check_catches(lambda s, m: s["opgg_decks"][0]["middle"].update(win=10**9), "回合计数")
        self.check_catches(lambda s, m: s["opgg_decks"][0]["stat"]["deck"].update(avgPlacement=11), "出界")

    def test_crawl_builds_refuse_to_write_into_the_repo(self):
        with self.assertRaises(SystemExit):
            build_site.check_out(ROOT, ["--riot-comps"])
        with self.assertRaises(SystemExit):
            build_site.check_out(ROOT / "comps", ["--riot"])
        build_site.check_out(ROOT / "cache" / "preview", ["--riot", "--riot-synergy", "--riot-comps"])
        build_site.check_out(ROOT, [])  # the committed build itself
        with tempfile.TemporaryDirectory() as d:
            build_site.check_out(Path(d), ["--riot-comps"])

    def test_cli_refuses_a_comps_export_from_another_snapshot(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fetch_data, "SNAPSHOTS", Path(d, "snapshots")):
            snap_path = fetch_data.save(self.snap)
            rc = fixture.riot_comps_doc(self.snap)
            for sha, ok in ((fetch_data.sha256(snap_path), True), ("0" * 64, False)):
                rc["comp_source"]["sha256"] = sha
                Path(d, "rc.json").write_text(json.dumps(rc, ensure_ascii=False), encoding="utf-8")
                argv = ["build_site.py", "--data", str(snap_path), "--riot-comps", str(Path(d, "rc.json")),
                        "--out", str(Path(d, "site"))]
                with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                    if ok:
                        build_site.main()
                        self.assertIn("compcrawl", Path(d, "site", "comps.html").read_text(encoding="utf-8"))
                    else:
                        with self.assertRaises(SystemExit):
                            build_site.main()

    def test_guard_catches_a_missing_comp_group_block(self):
        self.check_catches(lambda s, m: s.pop("comp_groups"), "comp_groups")

    def test_guard_catches_player_names_in_comp_groups(self):
        self.check_catches(lambda s, m: s["comp_groups"][0].update(topPlayers=[["someone", 1]]), "白名单外")

    def test_guard_catches_a_bad_placement_distribution(self):
        self.check_catches(lambda s, m: s["comp_groups"][0]["placementDistribution"].pop(), "名次分布")
        self.check_catches(lambda s, m: s["comp_groups"][0].update(group=99), "对不上")

    def test_guard_catches_a_unit_without_place_won(self):
        self.check_catches(lambda s, m: s["unit_stats"][self.roster_id()].pop("won"), "place/top4/won")

    def test_guard_catches_a_comp_without_group(self):
        self.check_catches(lambda s, m: s["comps"][0].pop("group"), "group")

    def test_item_tips_find_recipes_by_key_then_by_name(self):
        craft = copy.deepcopy(self.snap["craft"])
        craft["recipes"] += [
            {"api": "TFT_Item_Fixture0", "name": "旧名", "icon": "", "desc": "按 id", "emblem": False, "pair": ["Part0", "Part1"]},
            {"api": "TFT_Item_OlderApiName", "name": "测试装备1", "icon": "", "desc": "按名称", "emblem": False, "pair": ["Part2", "Part3"]}]
        meta = build_site.build_item_meta(self.snap["items"], "16.21")
        tips = build_site.item_tips(meta, craft, ["TFT_Item_Fixture0", "DA_Fixture1", "TFT_Item_Fixture2", "DA_Artifact_Fixture"])
        self.assertEqual(tips["TFT_Item_Fixture0"], ["Part0", "Part1", "按 id"])
        self.assertEqual(tips["DA_Fixture1"], ["Part2", "Part3", "按名称"])  # renamed item: tactics.tools id, Riot's older api name
        self.assertEqual(tips["TFT_Item_Fixture2"], [""])
        self.assertEqual(tips["DA_Artifact_Fixture"], ["神器"])
        craft["recipes"].append(dict(craft["recipes"][-1], api="TFT_Item_Twin"))  # two recipes with one name: neither matches
        self.assertEqual(build_site.item_tips(meta, craft, ["DA_Fixture1"])["DA_Fixture1"], [""])

    def test_tooltip_effect_text_drops_leftover_tokens(self):
        self.assertEqual(build_site.tidy("获得【技能暴击】。 {{TFT_Keyword_Precision}}"), "获得【技能暴击】。")
        self.assertEqual(build_site.tidy("提供相当于20%造成伤害值的治疗。 友军治疗："), "提供相当于20%造成伤害值的治疗。")
        self.assertEqual(build_site.tidy("每场战斗仅触发1次：在40%生命值时获得护盾。"), "每场战斗仅触发1次：在40%生命值时获得护盾。")

    def check_catches(self, mutate, needle):
        snap, manual = copy.deepcopy(self.snap), copy.deepcopy(self.manual)
        mutate(snap, manual)
        found = self.problems(snap, manual)
        self.assertTrue(any(needle in p for p in found), found)

    def roster_id(self):
        hide = {i for i, _ in self.manual["hide"]}
        return next(c["character_record"]["character_id"] for c in self.snap["champions"]
                    if c["character_record"]["character_id"] not in hide)

    def test_guard_catches_an_unseen_unit_id(self):
        self.check_catches(lambda s, m: s["unit_stats"].update(DA_New19_Unit={"count": 5}), "DA_New19_Unit")

    def test_guard_catches_an_impossible_board_count(self):
        self.check_catches(lambda s, m: s["unit_stats"][self.roster_id()].update(count=s["meta"]["total"] + 1), "棋盘数不合理")

    def test_guard_catches_a_set_mismatch(self):
        self.check_catches(lambda s, m: s["meta"].update(tactics_set=s["meta"]["set"] + 1), "赛季不一致")

    def test_guard_catches_a_missing_position(self):
        self.check_catches(lambda s, m: m["positions"].pop(self.roster_id()), "没有站位")

    def test_guard_catches_a_wrong_name_in_the_manual_file(self):
        self.check_catches(lambda s, m: m["positions"][self.roster_id()].__setitem__(1, "错名"), "官方名")

    def test_guard_catches_a_bad_cost(self):
        self.check_catches(lambda s, m: s["official"]["units"][self.roster_id()].update(cost=7), "费用")

    def test_guard_catches_an_untyped_trait(self):
        self.check_catches(lambda s, m: m["classes"].pop(0), "标职业或种族")

    def test_guard_catches_images_on_latest(self):
        self.check_catches(lambda s, m: s["meta"]["cdragon"].update(folder="latest"), "版本目录")
        self.check_catches(lambda s, m: s["craft"]["recipes"][0].update(icon="https://raw.communitydragon.org/latest/game/x.png"), "合成表图片")

    def test_guard_catches_a_count_out_of_range(self):
        self.check_catches(lambda s, m: s["meta"].update(total=5), "total")

    def test_new_set_skeleton_is_flagged_until_filled(self):
        sk = json.loads(checks.dump_manual(checks.skeleton(self.snap)))
        found = self.problems(self.snap, sk)
        self.assertTrue(any("没有站位" in p for p in found), found)
        self.assertTrue(any("标职业或种族" in p for p in found), found)
        sk.update({k: self.manual[k] for k in ("hide", "rename", "classes", "origins", "positions")})
        self.assertEqual(self.problems(self.snap, sk), [])

    def test_manual_file_is_in_the_one_entry_per_line_format(self):
        self.assertEqual(checks.dump_manual(self.manual), MANUAL.read_text(encoding="utf-8").replace("\r\n", "\n"))

    def test_snapshots_are_written_with_lf_and_hashed_reproducibly(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fetch_data, "SNAPSHOTS", Path(d)):
            p = fetch_data.save(self.snap)
            self.assertNotIn(b"\r\n", p.read_bytes())
            self.assertEqual(fetch_data.sha256(p), fetch_data.sha256(fetch_data.save(fetch_data.load(p))))

    def test_failed_guard_writes_no_snapshot(self):
        snap = copy.deepcopy(self.snap); snap["meta"]["tactics_set"] = None
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fetch_data, "SNAPSHOTS", Path(d, "snapshots")), \
                mock.patch.object(fetch_data, "RAW", Path(d, "raw")):
            with self.assertRaises(SystemExit):
                fetch_data.save(snap)
            self.assertFalse(Path(d, "snapshots").exists())
            self.assertTrue(Path(d, "failed_snapshot.json").exists())


# riot.txt as committed: the code Riot issued on 2026-11-01 when the production-key application was refilled
# (it replaced the code of 06a98ff); Riot asks for the code alone, so no final newline. Riot's developer portal
# reads it at the site root to verify the product URL. If Riot issues a new code, change both.
RIOT_TXT = b"d7cdbf33-835b-4866-b5ee-885d02264391"


def one_final_newline_off(b):
    """Ignore one final newline: LF as committed, CRLF in a Windows checkout (core.autocrlf, no .gitattributes)."""
    return b[:-2] if b.endswith(b"\r\n") else b[:-1] if b.endswith(b"\n") else b


class RiotTxt(unittest.TestCase):
    def check(self, path):
        self.assertTrue(path.is_file(), "%s is gone: Riot's developer portal verifies the site with it" % path)
        self.assertEqual(one_final_newline_off(path.read_bytes()), one_final_newline_off(RIOT_TXT), path)

    def test_riot_txt_is_kept_as_committed(self):
        self.check(ROOT / "riot.txt")

    def test_a_build_keeps_riot_txt(self):
        snap = fixture.snapshot(json.loads(MANUAL.read_text(encoding="utf-8")))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fetch_data, "SNAPSHOTS", Path(d, "snapshots")):
            out = Path(d, "site"); out.mkdir(); (out / "riot.txt").write_bytes(RIOT_TXT)
            argv = ["build_site.py", "--data", str(fetch_data.save(snap)), "--out", str(out)]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                build_site.main()
            self.assertTrue((out / "index.html").is_file())  # the build ran
            self.check(out / "riot.txt")


if __name__ == "__main__":
    unittest.main()
