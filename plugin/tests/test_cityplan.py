"""Offline tests for the guide exporter (cityplan.py), the bridge to City Planning Draft, the build overlay.
Run: python3 -m unittest discover -s plugin/tests

Every test works in a throwaway game user-data folder (CS2_USERDATA). cityplan_format_1.2.2.json holds the key names
City Planning Draft 1.2.2 writes in its own planner document, so a change in the planner's format, or in ours, shows up.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CITYPLAN = REPO / "plugin/skills/city-manager/scripts/cityplan.py"
FORMAT = json.loads((Path(__file__).parent / "cityplan_format_1.2.2.json").read_text(encoding="utf-8"))

PLAN = {"plans": [
    {"name": "Now · Road fixes",
     "roads": [{"name": "1 Main link", "class": "Collector", "points": [[0, 0], [100, 0], [200, 50]]},
               {"name": "1 Side street", "class": "Local", "points": [[100, -100], [100, 100]]}],
     "areas": [{"name": "2 New shops", "type": "Commercial", "polygon": [[10, 10], [60, 10], [60, 60], [10, 60]]}],
     "junctions": [{"name": "3 Crossing", "type": "Roundabout", "position": [100, 0], "road_a": "1 Main link", "road_b": "1 Side street"}]},
    {"name": "Base · Roads", "roads": [{"name": "Ring road", "class": "Arterial", "points": [[-500, -500], [500, -500]]}], "areas": [], "junctions": []},
]}


class Exporter(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cj-cityplan-"))
        self.userdata = self.base / "LocalLow"
        self.planner = self.userdata / "ModsData/CityPlanningDraft"
        self.planner.mkdir(parents=True)
        self.plan = self.base / "plan.json"
        self.plan.write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def run_tool(self, *args):
        env = dict(os.environ, CS2_USERDATA=str(self.userdata))
        r = subprocess.run([sys.executable, "-I", str(CITYPLAN), *map(str, args)], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def export(self, *extra):
        return self.run_tool("export", self.plan, "--map-id", "Testville", *extra)

    def test_an_export_has_the_planners_format(self):
        code, out = self.export("--name", "Testville 2")
        self.assertEqual(code, 0, out)
        doc = json.loads((self.planner / "Exports/Testville 2.cityplan.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], FORMAT["schema_version"])
        self.assertEqual(doc["map_id"], "Testville")
        self.assertEqual(doc["active_plan_id"], doc["plans"][0]["id"])
        for part, items in (("doc", [doc]), ("plan", doc["plans"]), ("roads", [r for p in doc["plans"] for r in p["roads"]]),
                            ("areas", [a for p in doc["plans"] for a in p["areas"]]), ("junctions", [j for p in doc["plans"] for j in p["junctions"]]),
                            ("point", [q for p in doc["plans"] for r in p["roads"] for q in r["points"]])):
            expected = set(FORMAT[part]) - set(FORMAT["optional"].get(part, []))
            for item in items:
                self.assertEqual(set(item), expected, f"{part}: {sorted(set(item) ^ expected)}")

    def test_front_makes_a_guide_the_newest_for_import(self):
        for n in ("Testville 1", "Testville 2"):
            code, out = self.export("--name", n)
            self.assertEqual(code, 0, out)
        exports = self.planner / "Exports"
        one, two = exports / "Testville 1.cityplan.json", exports / "Testville 2.cityplan.json"
        os.utime(one, (1_700_000_000, 1_700_000_000))
        before = one.read_bytes()
        code, out = self.run_tool("front", "Testville 1")
        self.assertEqual(code, 0, out)
        self.assertIn("Testville 1.cityplan.json is now the newest guide", out)
        self.assertGreater(one.stat().st_mtime, two.stat().st_mtime)
        self.assertEqual(one.read_bytes(), before, "the same guide, only newer")
        self.assertFalse(any(p.suffix == ".tmp" for p in exports.iterdir()))
        code, out = self.run_tool("front", "Testville 9")
        self.assertNotEqual(code, 0)
        self.assertIn("there are: Testville 1, Testville 2", out)

    def test_names_that_follow_the_convention_get_no_warning(self):
        code, out = self.export("--name", "Testville 2")
        self.assertEqual(code, 0, out)
        self.assertNotIn("naming:", out)

    def test_names_that_break_the_convention_are_warned_about(self):
        bad = {"plans": [dict(PLAN["plans"][1], name="A5-1 City roads"), dict(PLAN["plans"][0], name="Now · " + "x" * 30)]}
        self.plan.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        code, out = self.export("--name", "New City 1-guide-A14")
        self.assertEqual(code, 0, out)
        for expected in ("file 'New City 1-guide-A14' should be", "plan 'A5-1 City roads' should be", "characters; the planner cuts it"):
            self.assertIn(expected, out)
        self.plan.write_text(json.dumps({"plans": [PLAN["plans"][1], PLAN["plans"][0]]}, ensure_ascii=False), encoding="utf-8")
        code, out = self.export("--name", "Testville 3")
        self.assertIn("plans should run Now, Next, Later, Base, Done", out)

    def test_a_junction_must_name_roads_of_its_own_plan(self):
        broken = json.loads(json.dumps(PLAN))
        broken["plans"][0]["junctions"][0]["road_b"] = "6.2 Old name"
        self.plan.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        code, out = self.export("--name", "Testville 2")
        self.assertNotEqual(code, 0)
        self.assertIn("road_a/road_b must name roads in this plan", out)
        self.assertFalse((self.planner / "Exports/Testville 2.cityplan.json").exists())

    def test_the_map_id_comes_from_the_planners_own_document(self):
        (self.planner / "New City 1").mkdir()
        (self.planner / "New City 1/planning.cityplan.json").write_text(json.dumps({"schema_version": "1.0", "map_id": "New City 1", "plans": []}), encoding="utf-8")
        code, out = self.run_tool("export", self.plan, "--name", "Riverton 2")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads((self.planner / "Exports/Riverton 2.cityplan.json").read_text(encoding="utf-8"))["map_id"], "New City 1")

    def test_the_mayors_own_planner_drawings_read_back(self):
        self.export("--name", "Testville 2")
        doc = json.loads((self.planner / "Exports/Testville 2.cityplan.json").read_text(encoding="utf-8"))
        doc["view_settings"] = {"anything": 1}             # what the planner itself adds when it saves
        for p in doc["plans"]:
            for r in p["roads"]:
                r["style"] = {"anything": 1}
        (self.planner / "Testville").mkdir()
        (self.planner / "Testville/planning.cityplan.json").write_text("﻿" + json.dumps(doc), encoding="utf-8")
        code, out = self.run_tool("read", "Testville", "--plan", "Now · Road fixes")
        self.assertEqual(code, 0, out)
        simple = json.loads(out)
        self.assertEqual([r["name"] for r in simple["roads"]], ["1 Main link", "1 Side street"])
        self.assertEqual(simple["junctions"][0]["road_b"], "1 Side street")
        self.assertEqual(simple["areas"][0]["type"], "Commercial")


if __name__ == "__main__":
    unittest.main()
