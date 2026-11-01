"""python3 -m unittest discover -s tests   (stdlib only, no network)

The tests use a made-up snapshot (tests/fixture.py); the real one is not in the repository. When a real
snapshot exists in cache/snapshots/, it is checked too."""
import copy, json, sys, tempfile, unittest
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
            self.assertEqual(set(pages), {"index.html", "class.html", "origin.html", "synergy.html", "craft.html"})
            self.assertTrue(list(Path(d, "synergy").glob("*.html")))
            self.assertIn("版本 %s" % self.snap["meta"]["patch_label"], pages["index.html"])
            for gone in ("阵眼—", "三星价值</h3>", "羁绊强度</h3>", "最强阵容</h3>", "站位结论（"):
                for name, html in pages.items():
                    self.assertNotIn(gone, html, name)
            self.assertIn("人工标注", pages["class.html"])
            for page in ("class.html", "origin.html"):  # cards: 选率 and 满装率, no 均名 / 前四 (owner, 2026-11-01)
                self.assertIn("满装率", pages[page]); self.assertIn("选率", pages[page])
                self.assertNotIn("均名", pages[page]); self.assertNotIn("前四", pages[page])
            allpages = list(pages.values()) + [p.read_text(encoding="utf-8") for p in Path(d, "synergy").glob("*.html")]
            self.assertFalse([h for h in allpages if "communitydragon.org/latest/" in h])
            import html
            self.assertTrue(all(html.escape(build_site.RIOT_NOTICE) in h for h in allpages))  # Riot's notice on every page
            self.assertFalse([h for h in allpages if "build_site.py" in h])  # build commands live in the README
            self.assertTrue(all("communitydragon.org/16.21/" in h for h in allpages if "<img" in h))

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


if __name__ == "__main__":
    unittest.main()
