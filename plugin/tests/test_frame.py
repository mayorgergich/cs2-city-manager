"""Tests for the street frame (frame.py) and plan.py frame, road, zone and junction, on the made-up map (made_up_map.py):
Main Street runs from (0, -150) north to (0, 150), a Four-Lane Road; Entry Highway goes on north to Ring Highway at
(0, 300); Ring Highway runs west to east at z 300; Old Lane runs from (400, 100) north to (400, 600), across Ring Highway
at (400, 300); a railway runs north to south at x 250."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "skills/city-manager/scripts"))
import made_up_map as mm  # noqa: E402
import frame  # noqa: E402
import plan  # noqa: E402


class Frame(unittest.TestCase):
    def setUp(self):
        self.st = frame.Streets(mm.snapshot())

    def test_parts_run_west_to_east_or_south_to_north(self):
        main = self.st.part("Main Street")
        self.assertEqual((main.pts[0], main.pts[-1], round(main.length)), ((0.0, -150.0), (0.0, 150.0), 300))
        self.assertEqual(main.left_word(), "west", "left of a street running north is west")
        ring = self.st.part("ring highway")
        self.assertEqual(round(ring.length), 1790, "a name in any case")
        self.assertEqual([round(s) for s, _ in ring.joints], [0, 495, 895, 1295, 1790])
        self.assertEqual(len(self.st.parts("Old Lane")), 1, "Old Lane goes straight on across the highway: one part")

    def test_places(self):
        place = lambda spec: tuple(round(v, 1) for v in self.st.place(spec))
        self.assertEqual(place("Main Street@100+50"), (-50.0, -50.0), "100 m along, 50 m to the left (west)")
        self.assertEqual(place("Main Street@100-50"), (50.0, -50.0))
        self.assertEqual(place("Main Street@-50"), (0.0, 100.0), "negative: from the far end")
        self.assertEqual(place("Main Street@mid"), (0.0, 0.0))
        self.assertEqual(place("Ring Highway x Old Lane"), (400.0, 300.0), "where two streets share a junction")
        self.assertEqual(place("Main Street x Entry Highway"), (0.0, 150.0))
        self.assertEqual(place("120,-340"), (120.0, -340.0))
        self.assertEqual(place("Main Street/1@10"), (0.0, -140.0))
        with self.assertRaises(SystemExit) as e:
            self.st.place("Mian Street@10")
        self.assertIn("did you mean 'Main Street'", str(e.exception))
        with self.assertRaises(SystemExit) as e:
            self.st.place("Main Street/2@10")
        self.assertIn("has 1 part", str(e.exception))
        with self.assertRaises(SystemExit):
            self.st.place("Main Street, somewhere")

    def test_lines_and_projection(self):
        main = self.st.part("Main Street")
        line = main.line(0, 300, -20, step=100)
        self.assertEqual([tuple(round(v) for v in p) for p in line], [(20, -150), (20, -50), (20, 50), (20, 150)])
        self.assertEqual([round(v) for v in main.project(-30, 0)], [150, 30, 30])


class Builders(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cm-frame-"))
        self.addCleanup(lambda: shutil.rmtree(self.base, ignore_errors=True))
        self.snap = self.base / "city.json"
        self.snap.write_text(json.dumps(mm.snapshot()), encoding="utf-8")
        self.plan = self.base / "plan.json"
        self.plan.write_text(json.dumps({"plans": [{"name": "Now · Streets", "roads": [], "areas": [], "junctions": []}]}), encoding="utf-8")

    def run_plan(self, *args):
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                code = plan.main(["plan.py", *map(str, args)])
        except SystemExit as e:
            return 1, out.getvalue() + str(e)
        return code, out.getvalue()

    def items(self, plan_name="Now · Streets"):
        doc = json.loads(self.plan.read_text(encoding="utf-8"))
        p = next(q for q in doc["plans"] if q["name"] == plan_name)
        return {it["name"]: it for kind in ("roads", "areas", "junctions") for it in p[kind]}

    def test_frame_lists_what_is_along_a_street(self):
        code, out = self.run_plan("frame", self.snap, "Ring Highway")
        self.assertEqual(code, 0, out)
        self.assertIn("## Part 1 (`Ring Highway@…`): 1.8 km, east", out)
        self.assertIn("Starts at its west end (x -895, z 300); left is north.", out)
        self.assertIn("| 0 | leaves the map |", out)
        self.assertIn("| 895 | Entry Highway, to the right (south) |", out)
        self.assertIn("| 1,295 | Old Lane, across |", out)
        self.assertIn("Pieces: 0–495 Four-Lane Two-Way Highway (2+2); 495–895 Four-Lane Two-Way Highway (2+2), bridge;", out)
        code, out = self.run_plan("frame", self.snap, "Main Street")
        self.assertIn("| 0 | the end: open (nothing joins) |", out)
        self.assertIn("| 300 | the end: Entry Highway, straight on |", out)

    def test_road_off_along_and_through(self):
        code, out = self.run_plan("road", self.plan, self.snap, "--plan", "Now · Streets", "--name", "1 West lane", "--piece", "Two-Lane Road",
                                  "--off", "Main Street", "--at", "100", "--side", "left", "--length", "150")
        self.assertEqual(code, 0, out)
        self.assertIn("road '1 West lane' (Two-Lane Road, 150 m), off Main Street at 100 m to its left, 150 m", out)
        self.assertEqual(self.items()["1 West lane"]["points"], [[0.0, -50.0], [-150.0, -50.0]])
        self.run_plan("road", self.plan, self.snap, "--plan", "Now · Streets", "--name", "2 Side street", "--along", "Old Lane",
                      "--from", "0", "--to", "200", "--offset", "30", "--piece", "Two-Lane Road")
        pts = self.items()["2 Side street"]["points"]
        self.assertEqual((pts[0], pts[-1]), ([370.0, 100.0], [370.0, 300.0]), "30 m to the left (west) of Old Lane")
        self.run_plan("road", self.plan, self.snap, "--plan", "Now · Streets", "--name", "3 Link", "--through", "Main Street@100-50",
                      "--to-street", "Old Lane", "--piece", "Two-Lane Road", "--tunnel")
        link = self.items()["3 Link"]
        self.assertEqual(link["points"], [[50.0, -50.0], [400.0, 100.0]], "on to Old Lane's nearest point")
        self.assertTrue(link["tunnel"])
        code, out = self.run_plan("road", self.plan, self.snap, "--plan", "Now · Streets", "--name", "Lane", "--through", "Main Street@0", "Main Street@50")
        self.assertIn("has no step number, so it gets no build card", out)
        code, out = self.run_plan("check", self.plan, self.snap)
        self.assertIn("# Plan check against city.json", out, "the plan check reads what the builders write")
        self.assertIn("**3 Link**: runs onto 1 tile(s) the city doesn't own", out)

    def test_zone_band_and_polygon(self):
        self.run_plan("zone", self.plan, self.snap, "--plan", "Now · Streets", "--name", "4 Homes", "--type", "Residential",
                      "--along", "Main Street", "--from", "0", "--to", "300", "--side", "right")
        poly = self.items()["4 Homes"]["polygon"]
        xs = sorted({round(p[0], 1) for p in poly})
        self.assertEqual((xs[0], xs[-1]), (13.0, 61.0), "Main Street is 24 m wide: from 1 m off its edge, 48 m deep to the east")
        self.assertEqual(self.items()["4 Homes"]["type"], "Residential")
        self.run_plan("zone", self.plan, self.snap, "--plan", "Now · Streets", "--name", "5 Yard", "--type", "Custom",
                      "--polygon", "Main Street@0+20", "Main Street@100+20", "Main Street@100+80")
        self.assertEqual(len(self.items()["5 Yard"]["polygon"]), 3)
        code, out = self.run_plan("zone", self.plan, self.snap, "--plan", "Now · Streets", "--name", "6 X", "--type", "Parkland", "--polygon", "0,0", "1,1", "2,0")
        self.assertNotEqual(code, 0)
        self.assertIn("--type is one of", out)

    def test_junction_where_two_streets_meet(self):
        code, out = self.run_plan("junction", self.plan, self.snap, "--plan", "Now · Streets", "--name", "6 Old Lane interchange",
                                  "--type", "Interchange", "--at", "Ring Highway x Old Lane")
        self.assertEqual(code, 0, out)
        it = self.items()
        self.assertEqual(it["6 Old Lane interchange"]["position"], [400.0, 300.0])
        self.assertEqual((it["6 Old Lane interchange"]["road_a"], it["6 Old Lane interchange"]["road_b"]), ("Ring Highway", "Old Lane"))
        self.assertTrue(it["Ring Highway"]["existing"])
        self.assertEqual(it["Ring Highway"]["class"], "Highway")
        self.assertEqual(it["Old Lane"]["class"], "Local")
        code, out = self.run_plan("junction", self.plan, self.snap, "--plan", "Now · Streets", "--name", "7 Lights", "--type", "Normal",
                                  "--at", "Main Street@0", "--roads", "Main Street", "Nowhere")
        self.assertNotEqual(code, 0)
        self.assertIn("'Nowhere' isn't a road of 'Now · Streets'", out)
        import cityplan
        doc = json.loads(self.plan.read_text(encoding="utf-8"))
        _, errors = cityplan.build_plan(doc["plans"][0], lambda x, z: 0.0)
        self.assertEqual(errors, [], "the exporter takes what the builders write")


if __name__ == "__main__":
    unittest.main()
