"""python3 -m unittest discover -s tests   (stdlib only, no network)"""
import copy, json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_site, checks, fetch_data
from generate_tft_table import load_manual

SNAP = sorted(ROOT.glob("data/set*/*.json"))[-1]


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = fetch_data.load(SNAP)
        cls.manual = load_manual(cls.snap["meta"]["set"])

    def problems(self, snap=None, manual=None):
        return checks.check(snap or self.snap, manual or self.manual)

    def test_committed_snapshot_passes_the_guard(self):
        self.assertEqual(self.problems(), [])

    def test_pages_render_from_the_snapshot_alone(self):
        with tempfile.TemporaryDirectory() as d:
            build_site.render(self.snap, Path(d))
            pages = {p.name: p.read_text(encoding="utf-8") for p in Path(d).glob("*.html")}
            self.assertEqual(set(pages), {"index.html", "class.html", "origin.html", "synergy.html", "craft.html"})
            self.assertTrue(list(Path(d, "synergy").glob("*.html")))
            m = self.snap["meta"]
            self.assertIn("版本 %s" % m["patch_label"], pages["index.html"])
            for gone in ("阵眼—", "三星价值</h3>", "羁绊强度</h3>", "最强阵容</h3>", "站位结论（"):
                for name, html in pages.items():
                    self.assertNotIn(gone, html, name)
            self.assertIn("人工标注", pages["class.html"])

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
        self.check_catches(lambda s, m: s["unit_stats"].update(DA_New19_Unit={"count": 5, "place": 4.0, "top4": 50}), "DA_New19_Unit")

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
        p = ROOT / "sets" / ("set%d.json" % self.snap["meta"]["set"])
        self.assertEqual(checks.dump_manual(self.manual), p.read_text(encoding="utf-8").replace("\r\n", "\n"))

    def test_failed_guard_writes_no_snapshot(self):
        snap = copy.deepcopy(self.snap); snap["meta"]["tactics_set"] = None
        target = fetch_data.snapshot_path(snap); before = target.read_bytes() if target.exists() else None
        with self.assertRaises(SystemExit):
            fetch_data.save(snap)
        self.assertEqual(target.read_bytes() if target.exists() else None, before)


if __name__ == "__main__":
    unittest.main()
