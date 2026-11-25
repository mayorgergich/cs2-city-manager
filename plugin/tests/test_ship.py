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


class Base(unittest.TestCase):
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


class Ship(Base):
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


CITYPLAN = HERE.parent / "skills/city-manager/scripts/cityplan.py"


class Drawings(Base):
    """The Mayor's own drawings in the planner: Riverton 1 imported, then a road drawn, one moved 50 m, one nudged 2 m,
    an area deleted, a plan renamed (Next to Now), and a road drawn across the railway in the long-term plan."""

    def setUp(self):
        super().setUp()
        subprocess.run([sys.executable, "-I", str(CITYPLAN), "export", str(self.plan_path), "--name", "Riverton 1",
                        "--map-id", "riverton-map", "--out-dir", str(self.exports)], env=self.env, check=True,
                       capture_output=True, timeout=60)
        doc = json.loads((self.exports / "Riverton 1.cityplan.json").read_text(encoding="utf-8"))
        plans = {p["name"]: p for p in doc["plans"]}
        streets, homes, base = plans["Now · Streets"], plans["Next · Homes"], plans["Base · Roads"]

        def road(name, pts, rid):
            return {"object_type": "road", "road_class": "Local", "points": [{"x": x, "y": 50.0, "z": z} for x, z in pts],
                    "smoothing": "Light", "id": rid, "name": name, "locked": False,
                    "created_at": "2026-11-26T01:00:00.000000Z", "modified_at": "2026-11-26T01:00:00.000000Z"}
        streets["roads"].append(road("Mayor's lane", [(-100, -50), (-150, -50)], "mayor1"))
        base["roads"].append(road("Rail shortcut", [(150, -300), (350, -300)], "mayor2"))
        for r in streets["roads"]:
            if r["name"] == "2 West lane":
                for q in r["points"]:
                    q["z"] -= 50
            if r["name"] == "1 Main link":
                for q in r["points"]:
                    q["x"] += 2
        homes["areas"] = [a for a in homes["areas"] if a["name"] != "3 Homes"]
        homes["name"] = "Now · Homes"
        doc["view_settings"] = {}
        planner = self.userdata / "ModsData/CityPlanningDraft/riverton-map"
        planner.mkdir(parents=True)
        (planner / "planning.cityplan.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_ship_stops_and_lists_them_with_their_check(self):
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("# Not shipped: the Mayor's planner drawings come first", out)
        self.assertIn("The planner holds the guide **Riverton 1**.", out)
        self.assertIn("Since then the Mayor made 5 changes in the planner (and nudged 1 item a few metres, left as planned)", out)
        for row in ("| plan renamed | Now · Homes | was 'Next · Homes' |", "| drew a road | Now · Streets | Mayor's lane (Local) |",
                    "| changed a road | Now · Streets | 2 West lane: moved up to 50 m |", "| deleted an area | Next · Homes | 3 Homes |"):
            self.assertIn(row, out)
        self.assertIn("✗ **Rail shortcut** (Base · Roads): crosses the railway at grade", out, "their drawings get the plan check")
        self.assertFalse((self.exports / "Riverton 2.cityplan.json").exists(), "nothing exported")
        self.assertEqual(json.loads(self.plan_path.read_text(encoding="utf-8")), PLANS, "the plan file is untouched")
        code, out = self.run_plan("drawings", self.src)
        self.assertEqual(code, 0, out)
        self.assertIn("| drew a road | Base · Roads | Rail shortcut (Local) |", out)

    def test_keep_mayor_puts_them_into_the_plan_file(self):
        code, out = self.ship("--keep-mayor")
        self.assertEqual(code, 0, out)
        self.assertIn("- In the planner: the Mayor's 5 planner changes went into the plan file (--keep-mayor; the old file is plan.json.bak-", out)
        plans = {p["name"]: p for p in json.loads(self.plan_path.read_text(encoding="utf-8"))["plans"]}
        self.assertIn("Now · Homes", plans)
        self.assertNotIn("Next · Homes", plans)
        self.assertNotIn("3 Homes", [a["name"] for a in plans["Now · Homes"]["areas"]])
        streets = {r["name"]: r for r in plans["Now · Streets"]["roads"]}
        self.assertEqual(streets["2 West lane"]["points"], [[0, -150], [-150, -150]])
        self.assertEqual(streets["2 West lane"]["piece"], "Two-Lane Road", "the plan's own keys stay")
        self.assertEqual(streets["1 Main link"]["points"], [[0, 140], [0, -140]], "a nudge is left as planned")
        self.assertIn("Mayor's lane", streets)
        self.assertIn("Rail shortcut", [r["name"] for r in plans["Base · Roads"]["roads"]])
        self.assertTrue(list(self.base.glob("plan.json.bak-*")), "the plan file is backed up first")
        self.assertTrue((self.exports / "Riverton 2.cityplan.json").exists())
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("# Shipped: Riverton 3", out)
        self.assertIn("the Mayor's 5 changes since are in the plan file already", out,
                      "until the Mayor imports the new guide, the planner still holds Riverton 1: kept changes don't stop ship again")

    def test_drop_mayor_ships_anyway(self):
        code, out = self.ship("--drop-mayor")
        self.assertEqual(code, 0, out)
        self.assertIn("the new guide replaces the Mayor's 5 planner changes (--drop-mayor)", out)
        self.assertEqual(json.loads(self.plan_path.read_text(encoding="utf-8")), PLANS)

    def run_plan(self, *args):
        r = subprocess.run([sys.executable, "-I", str(PLAN), *map(str, args)], capture_output=True, text=True,
                           encoding="utf-8", env=self.env, timeout=180)
        return r.returncode, r.stdout + r.stderr

    def test_the_report_and_the_prep_show_them(self):
        report = HERE.parent / "skills/city-manager/scripts/report.py"
        (self.root / "riverton/city-start.json").write_text(json.dumps(mm.snapshot()), encoding="utf-8")
        for extra in ([], ["--prep"]):
            r = subprocess.run([sys.executable, "-I", str(report), str(self.src), "--plan", str(self.plan_path), *extra],
                               capture_output=True, text=True, encoding="utf-8", env=self.env, timeout=180)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            section = r.stdout.split("## In the planner", 1)[1].split("\n## ", 1)[0]
            self.assertIn("| drew a road | Now · Streets | Mayor's lane (Local) |", section)
            self.assertIn("✗ **Rail shortcut**", section)
            self.assertIn("`plan.py ship` stops until the Mayor says what to keep", section)

    def test_without_a_planner_document(self):
        shutil.rmtree(self.userdata / "ModsData/CityPlanningDraft/riverton-map")
        code, out = self.ship("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("- In the planner: no planner document for this city yet.", out)



class Advance(Base):
    """plan.py advance, the move-on step: after the first ship, Main Street (step 1) is built and the Mayor ticks step 2."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.ship()[0], 0)
        (self.root / "riverton/mayor.json").write_text(json.dumps({"ticks": {"p:streets/c-2": {"done": True, "at": "2099-01-01T00:00:00Z"}}}),
                                                     encoding="utf-8")

    def advance(self, *extra):
        r = subprocess.run([sys.executable, "-I", str(PLAN), "advance", str(self.plan_path), str(self.src), *map(str, extra)],
                           capture_output=True, text=True, encoding="utf-8", env=self.env, timeout=180)
        return r.returncode, r.stdout + r.stderr

    def names(self):
        return [p["name"] for p in json.loads(self.plan_path.read_text(encoding="utf-8"))["plans"]]

    def test_a_finished_plan_moves_to_done_and_its_project_closes(self):
        code, out = self.advance("--dry-run")
        self.assertIn("# Would move on: Riverton", out)
        self.assertEqual(self.names(), ["Now · Streets", "Next · Homes", "Later · Far off", "Base · Roads"], "a dry run writes nothing")
        code, out = self.advance()
        self.assertEqual(code, 0, out)
        self.assertIn("- Now · Streets → Done · Streets: every step built or ticked (1, 2).", out)
        self.assertIn('Nothing is Now any more: ask the Mayor which comes next, then `--promote` it: "Next · Homes".', out)
        self.assertIn("- streets.md: all 3 steps done → Done, with a log line.", out)
        self.assertEqual(self.names(), ["Done · Streets", "Next · Homes", "Later · Far off", "Base · Roads"], "Next waits for the Mayor")
        meta, _ = self.page("streets.md")
        self.assertEqual(meta["status"], "done")
        self.assertEqual(meta["plans"][0]["layers"], ["Done · Streets"], "the project's link follows the rename")
        self.assertIn("Closed by the move-on step", meta["log"][-1]["text"])
        self.assertTrue(list(self.base.glob("plan.json.bak-*")))
        self.assertIn("Journal: built.", out)

    def test_a_plan_with_steps_left_stays_now(self):
        (self.root / "riverton/mayor.json").unlink()
        code, out = self.advance()
        self.assertIn("- Now · Streets stays Now: step 2 left (1 done).", out)
        self.assertEqual(self.names()[0], "Now · Streets")
        self.assertEqual(self.page("streets.md")[0]["status"], "active")

    def test_promote_and_drop_done_after_its_round(self):
        self.advance()
        self.assertEqual(self.ship()[0], 0, "Riverton 3 shows Done · Streets")
        code, out = self.advance("--promote", "Next · Homes")
        self.assertEqual(code, 0, out)
        self.assertIn("- Done · Streets dropped: Riverton 3 showed it as Done (kept in archive.json beside the plan file).", out)
        self.assertIn("- Next · Homes → Now · Homes (--promote).", out)
        self.assertEqual(self.names(), ["Now · Homes", "Later · Far off", "Base · Roads"])
        self.assertEqual(json.loads((self.base / "archive.json").read_text(encoding="utf-8"))["plans"][0]["name"], "Done · Streets")
        self.assertEqual(self.page("homes.md")[0]["plans"][0]["layers"], ["Now · Homes"])
        meta, _ = self.page("streets.md")
        self.assertNotIn("plans", meta, "a link whose layers all dropped out goes")
        self.assertIn("- streets.md: its link to Done · Streets (dropped) is gone.", out)
        code, out = self.advance("--promote", "Later · Far off")
        self.assertNotEqual(code, 0)

    def test_old_done_projects_go_to_the_archive(self):
        (self.src / "projects/old.md").write_text('+++\nid = "old"\ntitle = "Old works"\nstatus = "done"\n\n[[log]]\ndate = "2026-11-01 10:00"\n'
                                                  'text = "Finished."\n+++\n', encoding="utf-8")
        (self.src / "briefings").mkdir(exist_ok=True)
        (self.src / "briefings/2026-11-02.md").write_text('+++\nid = "2026-11-02"\ntitle = "Old briefing"\n\n[[tasks]]\nid = "t1"\n'
                                                          'text = "Look at the works"\nproject = "old"\n+++\n', encoding="utf-8")
        (self.src / "reports").mkdir(exist_ok=True)
        for d in ("2026-11-20", "2026-11-21"):
            (self.src / f"reports/{d}.md").write_text(f'+++\nid = "{d}"\ntitle = "Report"\n+++\nA session.\n', encoding="utf-8")
        code, out = self.advance()
        self.assertTrue((self.src / "projects/old.md").exists(), "two reports since: kept")
        (self.src / "reports/2026-11-22.md").write_text('+++\nid = "2026-11-22"\ntitle = "Report"\n+++\nA session.\n', encoding="utf-8")
        code, out = self.advance("--keep-done", "5")
        self.assertTrue((self.src / "projects/old.md").exists(), "--keep-done 5")
        code, out = self.advance()
        self.assertEqual(code, 0, out)
        self.assertIn("- old.md → projects/archive/: Done since 2026-11-01, 3 reports since", out)
        self.assertTrue((self.src / "projects/archive/old.md").exists())
        self.assertIn("Journal: built.", out, "the old briefing that names it still builds")
        journal = json.loads((self.root / "riverton/journal.json").read_text(encoding="utf-8"))
        self.assertNotIn("old", [p["id"] for p in journal["projects"]], "the panel no longer lists it")


if __name__ == "__main__":
    unittest.main()
