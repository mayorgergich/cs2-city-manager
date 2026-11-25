"""Tests for plan.py ship, the plan file to the game in one run, on the made-up map (made_up_map.py): a fake game user-data
folder (CS2_USERDATA) with the city's snapshot, City Planning Draft's Exports folder, and a journal source beside it.
Main Street, a Four-Lane Road, runs north to south at x 0 from z 150 to -150; the owned tiles are the middle one and the
one west of it; a railway runs north to south at x 250."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PLAN = HERE.parent / "skills/city-manager/scripts/plan.py"
import made_up_map as mm  # noqa: E402


def road(name, cls, pts, **kw):
    return dict(name=name, **{"class": cls}, points=pts, **kw)


PLANS = {"plans": [
    {"name": "Now · Streets", "areas": [], "junctions": [], "roads": [
        road("1 Main link", "Arterial", [[0, 140], [0, -140]], piece="Four-Lane Road"),
        road("2 West lane", "Local", [[0, -100], [-150, -100]], piece="Two-Lane Road")]},
    {"name": "Next · Homes", "roads": [
        road("4 North, first street", "Local", [[-100, 100], [-100, 0]], piece="Two-Lane Road"),
        road("4 North, second street", "Local", [[-212, 100], [-212, 0]], piece="Two-Lane Road")], "junctions": [], "areas": [
        {"name": "3 Homes", "type": "Residential", "polygon": [[-170, -170], [-50, -170], [-50, -120], [-170, -120]]},
        {"name": "4 North homes", "type": "Residential", "polygon": [[-220, 0], [-90, 0], [-90, 100], [-220, 100]]}],
     "cards": {"4": {"text": "4 North streets: two Two-Lane Roads north off the lane, then zone homes"}}},
    {"name": "Later · Far off", "areas": [], "junctions": [], "roads": [road("20 Far road", "Local", [[-150, 150], [-150, 120]])]},
    {"name": "Base · Roads", "areas": [], "junctions": [], "roads": [road("Main Street", "Arterial", [[0, 150], [0, -150]], existing=True)]},
]}

STREETS = """+++
id = "streets"
title = "Streets"
scale = "district"
status = "active"
priority = 1

[[plans]]
kind = "draft"
name = "Riverton 1"
layers = ["Now · Streets"]

[[steps]]
id = "main"
text = "1 Main link"

[[steps]]
id = "lights"
text = "Take the lights off Old Lane"
done = true
+++
Why these streets: the Mayor's own words stay as they are.
"""

CITY_PLAN = """+++
id = "city-plan"
title = "City plan"
scale = "city"
status = "active"

[[plans]]
kind = "draft"
name = "Riverton 1"
layers = ["Base · Roads"]
+++
"""


class Ship(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cm-ship-"))
        self.addCleanup(lambda: shutil.rmtree(self.base, ignore_errors=True))
        self.userdata = self.base / "LocalLow"
        self.root = self.userdata / "ModsData/CityManager"
        (self.root / "riverton").mkdir(parents=True)
        (self.root / "riverton/city.json").write_text(json.dumps(mm.snapshot()), encoding="utf-8")
        self.exports = self.userdata / "ModsData/CityPlanningDraft/Exports"
        self.exports.mkdir(parents=True)
        (self.exports / "Riverton 1.cityplan.json").write_text(json.dumps({"map_id": "riverton-map", "plans": []}), encoding="utf-8")
        (self.exports / "Other Town 3.cityplan.json").write_text(json.dumps({"map_id": "other-map", "plans": []}), encoding="utf-8")
        self.src = self.base / "riverton/journal"
        for d in ("projects", "images"):
            (self.src / d).mkdir(parents=True)
        (self.src / "journal.toml").write_text('id = "riverton"\ncity = "Riverton"\nmanager = "Tester"\n', encoding="utf-8")
        (self.src / "projects/streets.md").write_text(STREETS, encoding="utf-8")
        (self.src / "projects/city-plan.md").write_text(CITY_PLAN, encoding="utf-8")
        self.plan_path = self.base / "plan.json"
        self.write_plan(PLANS)
        self.env = dict(os.environ, CS2_USERDATA=str(self.userdata), CITY_MANAGER_ROOT=str(self.root),
                        CITY_MANAGER_HOME=str(self.base / "home"))

    def write_plan(self, plans):
        self.plan_path.write_text(json.dumps(plans, ensure_ascii=False), encoding="utf-8")

    def ship(self, *extra):
        r = subprocess.run([sys.executable, "-I", str(PLAN), "ship", str(self.plan_path), str(self.src), *map(str, extra)],
                           capture_output=True, text=True, encoding="utf-8", env=self.env, timeout=180)
        return r.returncode, r.stdout + r.stderr

    def page(self, name):
        text = (self.src / "projects" / name).read_text(encoding="utf-8")
        front = text[4:text.index("\n+++", 3)]
        return tomllib.loads(front), text

    def test_one_run_exports_draws_and_writes_the_steps(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("# Shipped: Riverton 2", out)
        guide = json.loads((self.exports / "Riverton 2.cityplan.json").read_text(encoding="utf-8"))
        self.assertEqual(guide["map_id"], "riverton-map", "the map id comes from the city's last guide, never another city's")
        self.assertEqual(len(guide["plans"]), 4, "the guide has every layer, Later and Base included")
        self.assertTrue((self.exports / "old/Riverton 1.cityplan.json").exists(), "the city's older guide is put away")
        self.assertTrue((self.exports / "Other Town 3.cityplan.json").exists(), "another city's guide stays where it is")

        meta, text = self.page("streets.md")
        steps = {s["id"]: s for s in meta["steps"]}
        self.assertEqual(list(steps), ["main", "c-2", "lights"], "the hand-written step 1 is adopted, id and all; the cards go where it was")
        self.assertEqual(steps["main"]["text"], "1 Main link")
        self.assertTrue(steps["main"].get("done"), "Main Street is already there: built")
        self.assertNotIn("note", steps["main"], "an adopted step keeps the Manager's words: no note added")
        self.assertFalse(steps["c-2"].get("done"))
        self.assertEqual((steps["c-2"]["text"], steps["c-2"]["note"]), ("2 West lane", "Two-Lane Road, about 150 m"))
        self.assertEqual(steps["c-2"]["picture"], "card-2-streets.png")
        self.assertEqual(set(steps["c-2"]["where"]), {"label", "x", "z", "zoom"})
        self.assertTrue((self.src / "images/card-2-streets.png").exists())
        self.assertEqual(meta["plans"][0]["name"], "Riverton 2", "the project's guide link follows the new guide")
        self.assertEqual(len(meta["plans"]), 1)
        self.assertTrue(steps["lights"]["done"], "the Mayor's other steps stay as they were")
        self.assertIn("the Mayor's own words stay as they are", text)

        homes, _ = self.page("homes.md")
        self.assertEqual((homes["title"], homes["status"]), ("Homes", "next"), "a Next plan with no project gets a new one")
        self.assertEqual(homes["plans"][0]["name"], "Riverton 2")
        self.assertEqual(homes["plans"][0]["layers"], ["Next · Homes"])
        self.assertEqual([(s["id"], s["text"]) for s in homes["steps"]],
                         [("c-3", "3 Homes"), ("c-4", "4 North streets: two Two-Lane Roads north off the lane, then zone homes")],
                         "one card per step number: step 4's two streets and its homes are one step, its words from the plan's cards")
        self.assertEqual(homes["steps"][0]["note"], "Zone Residential")
        self.assertEqual(homes["steps"][1]["note"], "Two-Lane Road ×2 (about 200 m in all); zone Residential")
        self.assertTrue((self.src / "images/card-4-homes.png").exists())
        self.assertNotIn("20 Far road", out + text, "Later plans get no build cards")
        city_plan, _ = self.page("city-plan.md")
        self.assertEqual(city_plan["plans"][0]["name"], "Riverton 2", "every project's link follows the new guide")
        self.assertIn("1 other project now links to Riverton 2", out)

        journal = json.loads((self.root / "riverton/journal.json").read_text(encoding="utf-8"))
        ids = {p["id"]: [s["id"] for s in p["steps"]] for p in journal["projects"]}
        self.assertEqual(ids["streets"], ["main", "c-2", "lights"], "and the journal is built")

    def test_shipping_again_keeps_ids_and_ticks(self):
        self.assertEqual(self.ship()[0], 0)
        path = self.src / "projects/streets.md"
        text = path.read_text(encoding="utf-8").replace('id = "c-2"\n', 'id = "c-2"\ndone = true\n')
        path.write_text(text.replace('"2 West lane"', '"2 West lane: the Manager\'s own words"'), encoding="utf-8")
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("# Shipped: Riverton 3", out)
        self.assertTrue((self.exports / "old/Riverton 2.cityplan.json").exists())
        meta, text = self.page("streets.md")
        steps = {s["id"]: s for s in meta["steps"]}
        self.assertEqual(list(steps), ["main", "c-2", "lights"])
        self.assertTrue(steps["c-2"].get("done"), "a tick is never taken back")
        self.assertEqual(steps["c-2"]["text"], "2 West lane: the Manager's own words", "words changed in the block stay")
        self.assertEqual(text.count("# >>> build cards"), 1, "one block, replaced each time")
        self.assertEqual(meta["plans"][0]["name"], "Riverton 3")

    def test_stops_on_errors_and_dry_run_writes_nothing(self):
        bad = json.loads(json.dumps(PLANS))
        bad["plans"][0]["roads"].append(road("4 Rail street", "Local", [[150, -100], [350, -100]], piece="Two-Lane Road"))
        self.write_plan(bad)
        before = (self.src / "projects/streets.md").read_text(encoding="utf-8")
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("Not shipped", out)
        self.assertFalse((self.exports / "Riverton 2.cityplan.json").exists())
        self.assertEqual((self.src / "projects/streets.md").read_text(encoding="utf-8"), before)

        self.write_plan(PLANS)
        code, out = self.ship("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("# Would ship: Riverton 2", out)
        self.assertIn("New project homes.md: 2 build-card steps", out)
        self.assertFalse((self.exports / "Riverton 2.cityplan.json").exists())
        self.assertFalse((self.src / "projects/homes.md").exists())
        self.assertEqual(list((self.src / "images").iterdir()), [])
        self.assertEqual((self.src / "projects/streets.md").read_text(encoding="utf-8"), before)

    def test_two_steps_with_one_number_are_left_alone(self):
        path = self.src / "projects/streets.md"
        path.write_text(path.read_text(encoding="utf-8").replace('+++\nWhy', '\n[[steps]]\nid = "w2"\ntext = "2 West lane, east half"\n'
                                                                 '\n[[steps]]\nid = "w2b"\ntext = "2 West lane, west half"\n+++\nWhy'), encoding="utf-8")
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("two steps start with 2, so ship left them as they are", out)
        meta, _ = self.page("streets.md")
        self.assertEqual([s["id"] for s in meta["steps"]], ["main", "w2", "w2b", "lights"], "kept word for word, in number order")

    def test_no_map_id_without_the_citys_own_guide_or_planner(self):
        (self.exports / "Riverton 1.cityplan.json").unlink()
        code, out = self.ship()
        self.assertNotEqual(code, 0)
        self.assertIn("No map id for Riverton", out, "never another city's map id")
        planner = self.userdata / "ModsData/CityPlanningDraft/Riverton"
        planner.mkdir(parents=True)
        (planner / "planning.cityplan.json").write_text(json.dumps({"map_id": "Riverton", "plans": []}), encoding="utf-8")
        code, out = self.ship("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("# Would ship: Riverton 1 (map id 'Riverton')", out)


if __name__ == "__main__":
    unittest.main()
