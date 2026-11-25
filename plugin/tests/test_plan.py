"""Tests for plan.py, the plan checker and drawer, on the made-up map (made_up_map.py): the owned tiles are the middle one
and the one west of it; Ring Highway runs west to east at z 300 (on a bridge from x -400 to 0); Entry Highway ends at
z 150 where Main Street carries on; a railway runs north to south at x 250; a river in the west, a 30% hill in the east,
a 10% rise in the north."""
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "skills/city-manager/scripts"))
import made_up_map as mm  # noqa: E402
import cityplan  # noqa: E402
import plan  # noqa: E402

RING = {"name": "Ring Highway", "class": "Highway", "existing": True, "points": [[-895, 300], [895, 300]]}


def road(name, cls, pts, **kw):
    return dict(name=name, **{"class": cls}, points=pts, **kw)


def plans(*items):
    return list(items)


def problems(results, level=None, item=None):
    out = []
    for r in results:
        for p in r["problems"]:
            if (level is None or p["level"] == level) and (item is None or p["item"] == item):
                out.append(p)
    return out


class Checks(unittest.TestCase):
    def check(self, *ps, snap=None, name=None):
        chk = plan.Check(snap or mm.snapshot(), list(ps), name)
        chk.run()
        return chk

    def test_a_clean_first_phase(self):
        chk = self.check({"name": "Now · First streets",
                          "roads": [road("1 Main Avenue", "Arterial", [[-150, -100], [150, -100]], piece="Four-Lane Road"),
                                    road("2 Side Street", "Local", [[-300, -150], [-300, 150]], piece="Two-Lane Road"),
                                    road("3 East Street", "Collector", [[0, 150], [150, 150]], piece="Two-Lane Road")],
                          "areas": [{"name": "4 Downtown", "type": "Commercial", "polygon": [[-150, -50], [150, -50], [150, 100], [-150, 100]]}],
                          "junctions": [{"name": "5 Corner", "type": "Roundabout", "position": [0, -100], "road_a": "1 Main Avenue",
                                         "road_b": "2 Side Street", "piece": "a small roundabout"}]})
        self.assertEqual(problems(chk.results), [], "3 East Street carries on from where Entry Highway ends: no at-grade join")
        self.assertEqual(chk.errors(), 0)
        self.assertEqual(chk.results[0]["km"], {"Arterial": 0.3, "Local": 0.3, "Collector": 0.15})

    def test_crossing_a_highway_at_grade(self):
        chk = self.check({"name": "Base · Roads", "roads": [road("Cross", "Collector", [[100, 100], [100, 500]])], "areas": [], "junctions": []})
        errs = problems(chk.results, "error", "Cross")
        self.assertEqual(len(errs), 1)
        self.assertIn("crosses Ring Highway at grade", errs[0]["text"])
        self.assertEqual(errs[0]["at"], [100, 300])

    def test_an_underpass_or_a_tunnel_makes_it_fine(self):
        under = {"name": "Base · Roads", "roads": [RING, road("Cross", "Collector", [[100, 100], [100, 500]])], "areas": [],
                 "junctions": [{"name": "Under", "type": "Underpass", "position": [100, 300], "road_a": "Cross", "road_b": "Ring Highway"}]}
        self.assertEqual(problems(self.check(under).results, "error"), [])
        tunnel = {"name": "Base · Roads", "roads": [road("Cross", "Collector", [[100, 100], [100, 500]], tunnel=True)], "areas": [], "junctions": []}
        self.assertEqual(problems(self.check(tunnel).results, "error"), [])

    def test_passing_under_a_highway_bridge(self):
        chk = self.check({"name": "Base · Roads", "roads": [road("Under the bridge", "Collector", [[-200, 100], [-200, 500]])], "areas": [], "junctions": []})
        self.assertEqual(problems(chk.results, "error"), [])
        self.assertTrue(any("on a bridge or in a tunnel" in p["text"] for p in problems(chk.results, "note")))

    def test_joining_a_highway_at_grade(self):
        chk = self.check({"name": "Base · Roads", "roads": [road("Spur", "Collector", [[200, 100], [200, 300]])], "areas": [], "junctions": []})
        self.assertTrue(any("joins Ring Highway at grade" in p["text"] for p in problems(chk.results, "error", "Spur")))
        ramp = self.check({"name": "Base · Roads", "roads": [road("Ramp", "Highway", [[200, 100], [200, 300]], piece="One-Lane One-Way Highway")],
                           "areas": [], "junctions": []})
        self.assertEqual(problems(ramp.results, "error"), [], "a ramp (a highway piece) joins a highway")

    def test_crossing_the_railway(self):
        chk = self.check({"name": "Base · Roads", "roads": [road("Rail street", "Local", [[150, -300], [350, -300]])], "areas": [], "junctions": []})
        self.assertTrue(any("railway at grade" in p["text"] for p in problems(chk.results, "error", "Rail street")))
        bridge = self.check({"name": "Base · Roads", "roads": [road("Rail street", "Local", [[150, -300], [350, -300]], bridge=True)], "areas": [], "junctions": []})
        self.assertEqual(problems(bridge.results, "error"), [])

    def test_steep_ground(self):
        chk = self.check({"name": "Base · Roads", "roads": [road("Hill climb", "Arterial", [[500, 0], [850, 0]]),
                                                            road("North rise", "Local", [[-100, 620], [-100, 880]])], "areas": [], "junctions": []})
        hill = problems(chk.results, "error", "Hill climb")
        self.assertTrue(hill and "refuses roads over 20%" in hill[0]["text"])
        rise = problems(chk.results, "warn", "North rise")
        self.assertTrue(rise and "under 8%" in rise[0]["text"], "a 10% street that gets zoned")
        arterial = self.check({"name": "Base · Roads", "roads": [road("North rise", "Arterial", [[-100, 620], [-100, 880]])], "areas": [], "junctions": []})
        self.assertEqual([p for p in problems(arterial.results) if "steep" in p["text"]], [], "8% is for zoned streets")

    def test_water_wants_a_bridge(self):
        chk = self.check({"name": "Base · Roads", "roads": [road("River road", "Arterial", [[-650, -50], [-450, -50]])], "areas": [], "junctions": []})
        self.assertTrue(any("of water" in p["text"] for p in problems(chk.results, "warn", "River road")))
        bridge = self.check({"name": "Base · Roads", "roads": [road("River road", "Arterial", [[-650, -50], [-450, -50]], bridge=True)],
                             "areas": [], "junctions": []})
        self.assertEqual([p for p in problems(bridge.results) if "water" in p["text"]], [])

    def test_now_and_next_must_be_on_owned_tiles(self):
        south = road("3 South Road", "Collector", [[0, -100], [0, -400]], piece="Two-Lane Road")
        now = self.check({"name": "Now · Streets", "roads": [south], "areas": [], "junctions": []})
        self.assertTrue(any("doesn't own" in p["text"] for p in problems(now.results, "error", "3 South Road")))
        base = self.check({"name": "Base · Roads", "roads": [south], "areas": [], "junctions": []})
        self.assertEqual(problems(base.results, "error"), [])
        self.assertTrue(any("needs 1 more tile" in p["text"] for p in problems(base.results, "note")))
        everything = {(r, c) for r in range(5) for c in range(5)}
        owned = self.check({"name": "Now · Streets", "roads": [south], "areas": [], "junctions": []}, snap=mm.snapshot(owned=everything))
        self.assertEqual(problems(owned.results, "error"), [])

    def test_pieces_from_the_catalogue(self):
        chk = self.check({"name": "Now · Streets", "roads": [
            road("1 Big Road", "Arterial", [[-150, -100], [150, -100]], piece="Six-Lane Road"),
            road("2 Odd Road", "Local", [[-150, -150], [150, -150]], piece="Made Up Road"),
            road("3 No Piece", "Local", [[-150, 0], [150, 0]])], "areas": [],
            "junctions": [{"name": "4 Trumpet", "type": "Interchange", "position": [0, 100], "road_a": "1 Big Road", "road_b": "3 No Piece",
                           "piece": "Trumpet Intersection"}]})
        self.assertIn("locked until milestone 6", problems(chk.results, "error", "1 Big Road")[0]["text"])
        self.assertIn("isn't in the snapshot's catalogue", problems(chk.results, "warn", "2 Odd Road")[0]["text"])
        self.assertIn("no road piece named", problems(chk.results, "warn", "3 No Piece")[0]["text"])
        self.assertIn("locked until milestone 8", problems(chk.results, "error", "4 Trumpet")[0]["text"])
        by_prefab = self.check({"name": "Now · Streets", "roads": [road("1 Main", "Arterial", [[-150, -100], [150, -100]], prefab="Medium Road")],
                                "areas": [], "junctions": []})
        self.assertEqual(problems(by_prefab.results), [], "the game's own prefab name works too")

    def test_highways_in_the_plan(self):
        new_hw = road("New Highway", "Highway", [[-400, -700], [200, -700]])   # stops short of the railway at x 250
        feeder = road("Feeder", "Collector", [[0, -800], [0, -700]])
        normal = self.check({"name": "Base · Roads", "roads": [new_hw, feeder], "areas": [],
                             "junctions": [{"name": "Flat", "type": "Normal", "position": [0, -700], "road_a": "New Highway", "road_b": "Feeder"}]})
        self.assertTrue(any("traffic lights or a roundabout on the highway" in p["text"] for p in problems(normal.results, "error", "Flat")))
        inter = self.check({"name": "Base · Roads", "roads": [new_hw, feeder], "areas": [],
                            "junctions": [{"name": "Exit", "type": "Interchange", "position": [0, -700], "road_a": "New Highway", "road_b": "Feeder"}]})
        self.assertEqual(problems(inter.results, "error"), [])
        ramp = self.check({"name": "Base · Roads", "roads": [road("Ramp east", "Highway", [[-400, -700], [0, -700]]), feeder], "areas": [],
                           "junctions": [{"name": "Ramp end", "type": "Normal", "position": [0, -700], "road_a": "Ramp east", "road_b": "Feeder"}]})
        self.assertEqual(problems(ramp.results, "error"), [], "a ramp ends on a street with an ordinary junction")
        cross = self.check({"name": "Base · Roads", "roads": [new_hw, road("Cross street", "Collector", [[0, -900], [0, -500]])], "areas": [], "junctions": []})
        self.assertTrue(any("at grade" in p["text"] for p in problems(cross.results, "error", "Cross street")))

    def test_what_the_exporter_would_refuse_and_naming(self):
        chk = self.check({"name": "Roads", "roads": [], "junctions": [],
                          "areas": [{"name": "Bow tie", "type": "Custom", "polygon": [[0, 0], [100, 100], [100, 0], [0, 100]]}]})
        self.assertTrue(any("export would refuse" in p["text"] for p in problems(chk.results, "error")))
        self.assertTrue(any("<Status> · <Topic>" in w for w in chk.naming))
        self.assertFalse(any(w.startswith("file ") for w in chk.naming), "no file name given, so no file warning")
        named = self.check({"name": "Base · Roads", "roads": [], "areas": [], "junctions": []}, name="Riverton")
        self.assertTrue(any(w.startswith("file ") for w in named.naming))

    def test_junctions_close_together_on_an_arterial(self):
        chk = self.check({"name": "Now · Streets", "roads": [
            road("1 Main Avenue", "Arterial", [[-150, -100], [150, -100]], piece="Four-Lane Road"),
            road("2 West lane", "Local", [[-100, -100], [-100, 100]], piece="Two-Lane Road"),
            road("3 East lane", "Local", [[-40, -100], [-40, 100]], piece="Two-Lane Road")], "areas": [], "junctions": []})
        notes = problems(chk.results, "note", "1 Main Avenue")
        self.assertTrue(notes and "60 m apart" in notes[0]["text"])


class Drawing(unittest.TestCase):
    PLAN = {"plans": [
        {"name": "Now · First streets", "roads": [road("1 Main Avenue", "Arterial", [[-150, -100], [150, -100]], piece="Four-Lane Road"),
                                                  road("2 Under", "Collector", [[100, 100], [100, 500]], piece="Two-Lane Road", tunnel=True)],
         "areas": [{"name": "3 Downtown", "type": "Commercial", "polygon": [[-150, -50], [150, -50], [150, 100], [-150, 100]]}],
         "junctions": [{"name": "4 Corner", "type": "Roundabout", "position": [0, -100], "road_a": "1 Main Avenue", "road_b": "2 Under"}]},
        {"name": "Base · Districts", "roads": [], "junctions": [],
         "areas": [{"name": "Farm belt", "type": "Custom", "fill": "#DAA520", "polygon": [[-850, -850], [-500, -850], [-500, -500], [-850, -500]]}]},
    ]}

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cm-plan-"))
        self.snap_path = self.base / "city.json"
        self.snap_path.write_text(json.dumps(mm.snapshot(owned=mm.OWNED | {(3, 2)})), encoding="utf-8")   # and the tile north of the middle
        self.plan_path = self.base / "plan.json"
        self.plan_path.write_text(json.dumps(self.PLAN, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = plan.main(["plan.py", *map(str, args)])
        return code, out.getvalue()

    def test_draws_every_view(self):
        from PIL import Image
        for i, extra in enumerate([[], ["--view", "map"], ["--view", "start"], ["--around", "2 Under"], ["--only", "Base · Districts"]]):
            out = self.base / f"p{i}.png"
            code, text = self.run_main("draw", self.plan_path, self.snap_path, "--out", out, *extra)
            self.assertEqual(code, 0, text)
            with Image.open(out) as im:
                self.assertEqual(im.format, "PNG")
                self.assertLessEqual(im.width, 1600)

    def test_markers_are_drawn_and_left_out_of_the_check(self):
        from PIL import Image
        marked = json.loads(json.dumps(self.PLAN))
        marked["plans"][0]["markers"] = [{"name": "A", "position": [-300, 0], "note": "harbour here, deep water"},
                                         {"name": "B", "position": [200, 400]}]
        path = self.base / "marked.json"
        path.write_text(json.dumps(marked, ensure_ascii=False), encoding="utf-8")
        out = self.base / "marked.png"
        code, text = self.run_main("draw", path, self.snap_path, "--out", out, "--view", "start")
        self.assertEqual(code, 0, text)
        with Image.open(out) as im:
            colours = im.convert("RGB").getcolors(maxcolors=1 << 22)
            self.assertTrue(any(abs(r - 200) < 12 and g < 25 and abs(b - 120) < 12 for _, (r, g, b) in colours), "the marker badges")
        code, text = self.run_main("check", path, self.snap_path, "--name", "Riverton 1")
        self.assertEqual(code, 0, text)
        self.assertIn("0 to fix", text)
        self.assertNotIn("harbour here", text)

    def test_unknown_item_or_plan(self):
        with self.assertRaises(SystemExit):
            self.run_main("draw", self.plan_path, self.snap_path, "--out", self.base / "x.png", "--around", "Nowhere")
        with self.assertRaises(SystemExit):
            self.run_main("draw", self.plan_path, self.snap_path, "--out", self.base / "x.png", "--only", "Now · Nothing")

    def test_check_command_and_exit_status(self):
        code, text = self.run_main("check", self.plan_path, self.snap_path, "--name", "Riverton 1", "--json", self.base / "check.json")
        self.assertEqual(code, 0, text)
        self.assertIn("## Now · First streets", text)
        self.assertIn("0 to fix", text)
        data = json.loads((self.base / "check.json").read_text(encoding="utf-8"))
        self.assertEqual(data["errors"], 0)
        bad = json.loads(json.dumps(self.PLAN))
        bad["plans"][0]["roads"][1].pop("tunnel")
        self.plan_path.write_text(json.dumps(bad), encoding="utf-8")
        code, text = self.run_main("check", self.plan_path, self.snap_path)
        self.assertEqual(code, 1)
        self.assertIn("✗ **2 Under**: crosses Ring Highway at grade", text)

    def test_exporter_takes_ground_heights_from_the_snapshot(self):
        h = cityplan.height_fn(str(self.snap_path))
        self.assertAlmostEqual(h(0, 0), 50.0, places=1)
        self.assertAlmostEqual(h(700, 0), mm.ground(700, 28), delta=0.2)



class BuiltCheck(unittest.TestCase):
    """plan.py built, map and cards on the made-up map: Main Street runs north to south at x 0 from z 150 to -150
    (Four-Lane Road); Old Lane crosses Ring Highway at grade at x 400, with traffic lights; the Old Mill Ruins at
    (-300, -100)."""

    PLAN = {"plans": [
        {"name": "Now · Streets", "roads": [
            road("1 Main link", "Arterial", [[0, 140], [0, -140]], piece="Four-Lane Road"),
            road("3 Half", "Local", [[0, 0], [0, -450]], piece="Four-Lane Road"),
            road("4 Empty lane", "Local", [[-300, -400], [-100, -400]], piece="Two-Lane Road"),
            road("5 Highway street", "Local", [[100, 300], [350, 300]], piece="Two-Lane Road"),
            road("6 Main tunnel", "Collector", [[0, 140], [0, -140]], piece="Four-Lane Road", tunnel=True),
            road("7 Wrong piece", "Local", [[0, 140], [0, -140]], piece="Two-Lane Road"),
            road("Ring Highway", "Highway", [[-895, 300], [895, 300]], existing=True)],
         "junctions": [{"name": "8 Old Lane lights", "type": "Normal", "position": [400, 300]},
                       {"name": "9 Old Lane roundabout", "type": "Roundabout", "position": [400, 300]},
                       {"name": "10 Nowhere", "type": "Normal", "position": [-300, -400]}],
         "areas": [{"name": "11 Mill yard", "type": "Custom", "polygon": [[-350, -150], [-250, -150], [-250, -50], [-350, -50]]},
                   {"name": "12 Empty homes", "type": "Residential", "polygon": [[-600, -700], [-400, -700], [-400, -500], [-600, -500]]}]},
        {"name": "Later · Far off", "roads": [road("20 Far road", "Local", [[0, 140], [0, -140]])], "areas": [], "junctions": []},
    ]}

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cm-built-"))
        self.addCleanup(lambda: shutil.rmtree(self.base, ignore_errors=True))
        self.snap_path = self.base / "city.json"
        self.snap_path.write_text(json.dumps(mm.snapshot()), encoding="utf-8")
        self.plan_path = self.base / "plan.json"
        self.plan_path.write_text(json.dumps(self.PLAN, ensure_ascii=False), encoding="utf-8")

    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = plan.main(["plan.py", *map(str, args)])
        return code, out.getvalue()

    def built(self, *extra):
        code, text = self.run_main("built", self.plan_path, self.snap_path, "--json", self.base / "built.json", *extra)
        self.assertEqual(code, 0, text)
        data = json.loads((self.base / "built.json").read_text(encoding="utf-8"))
        return {it["name"]: it for r in data["plans"] for it in r["items"]}, text

    def test_roads_built_partly_or_not_yet(self):
        items, text = self.built()
        self.assertEqual(items["1 Main link"]["status"], "built")
        self.assertEqual((items["1 Main link"]["piece"], items["1 Main link"]["street"]), ("Four-Lane Road", "Main Street"))
        half = items["3 Half"]
        self.assertEqual(half["status"], "partly")
        self.assertTrue(25 <= half["share"] <= 45, half)
        self.assertIn("missing toward the south", half["notes"])
        self.assertEqual(items["4 Empty lane"]["status"], "not yet")
        self.assertEqual(items["5 Highway street"]["status"], "not yet", "a street along a highway isn't built")
        self.assertNotIn("Ring Highway", items, "existing roads aren't checked")
        self.assertNotIn("20 Far road", items, "Later plans only with --all")
        self.assertIn("**Built as planned**", text)
        self.assertIn("1 Main link", text.split("**Built as planned**")[1])

    def test_built_differently_from_the_card(self):
        items, _ = self.built()
        self.assertEqual(items["6 Main tunnel"]["status"], "different")
        self.assertIn("not in a tunnel: the card said a tunnel", items["6 Main tunnel"]["notes"])
        self.assertEqual(items["7 Wrong piece"]["status"], "different")
        self.assertIn("the card said Two-Lane Road", items["7 Wrong piece"]["notes"])

    def test_junctions_and_areas(self):
        items, _ = self.built()
        self.assertEqual(items["8 Old Lane lights"]["status"], "built")
        self.assertIn("with traffic lights", items["8 Old Lane lights"]["notes"])
        self.assertEqual(items["9 Old Lane roundabout"]["status"], "different")
        self.assertIn("a plain junction with traffic lights: the card said a roundabout", items["9 Old Lane roundabout"]["notes"])
        self.assertEqual(items["10 Nowhere"]["status"], "not yet")
        self.assertEqual(items["11 Mill yard"]["status"], "partly", "a building, but not one of the area's kind")
        self.assertEqual(items["12 Empty homes"]["status"], "not yet")
        self.assertIn("nothing zoned or built inside yet", items["12 Empty homes"]["notes"])

    def test_every_plan_and_the_picture(self):
        from PIL import Image
        items, _ = self.built("--all", "--out", self.base / "built.png")
        self.assertEqual(items["20 Far road"]["status"], "built")
        with Image.open(self.base / "built.png") as im:
            self.assertEqual(im.format, "PNG")
            colours = im.convert("RGB").getcolors(maxcolors=1 << 22)
            self.assertTrue(any(c == plan.RESULT["built"][0] for _, c in colours))

    def test_a_map_marks_what_was_built_since(self):
        from PIL import Image
        then = self.base / "before.json"
        then.write_text(json.dumps(mm.snapshot()), encoding="utf-8")
        now = mm.snapshot()
        now["taken"] = "2026-11-24T21:30:00Z"
        now["nodes"].append({"id": 20, "x": -300.0, "z": -400.0, "y": 50.0})
        now["edges"].append({"id": 130, "prefab": 1, "kind": "road", "a": 7, "b": 20, "street": 3, "length": 410.0,
                             "pts": mm.bez(0, -150, -300, -400), "lanes": [1, 1]})
        now["buildings"].append({"id": 51, "prefab": 4, "kind": "service", "name": "Fire Station", "lot": [4, 4], "x": -280.0, "z": -380.0, "y": 50.0, "angle": 0})
        self.snap_path.write_text(json.dumps(now), encoding="utf-8")
        out = self.base / "map.png"
        code, text = self.run_main("map", self.snap_path, "--out", out, "--before", then)
        self.assertEqual(code, 0, text)
        self.assertIn("1 new piece of road and track", text)
        self.assertIn("1 building placed", text)
        with Image.open(out) as im:
            colours = im.convert("RGB").getcolors(maxcolors=1 << 22)
            self.assertTrue(any(c == (0, 140, 255) for _, c in colours), "the new road in blue")
        code, text = self.run_main("map", self.snap_path, "--out", out, "--before", self.snap_path)
        self.assertIn("nothing to compare with", text)

    def test_cards_for_the_numbered_now_items(self):
        out = self.base / "images"
        code, text = self.run_main("cards", self.plan_path, self.snap_path, "--out-dir", out, "--width", 700)
        self.assertEqual(code, 0, text)
        files = sorted(f.name for f in out.iterdir())
        self.assertIn("card-1-main-link.png", files)
        self.assertIn("card-11-mill-yard.png", files)
        self.assertNotIn("card-20-far-road.png", files, "Later plans get no cards")
        self.assertIn('where = { label = "1 Main link", x = 0, z = 0, zoom = ', text)
        self.assertIn("![1 Main link](card-1-main-link.png)", text)
        self.assertTrue(all(re.fullmatch(r"[A-Za-z0-9._-]+", f) for f in files), "picture names the journal accepts")

if __name__ == "__main__":
    unittest.main()
