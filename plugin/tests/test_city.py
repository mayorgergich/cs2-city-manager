"""Tests for city.py, the reader of the mod's city snapshot (city.json, city-start.json): on a small made-up city."""
import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/city-manager/scripts"))
import city  # noqa: E402


def pts(x0, z0, x1, z1, y=30.0):
    return [[x0, z0, y], [x0 + (x1 - x0) / 3, z0 + (z1 - z0) / 3, y], [x0 + 2 * (x1 - x0) / 3, z0 + 2 * (z1 - z0) / 3, y], [x1, z1, y]]


BEFORE = {
    "format": 1, "mod": "0.6.0", "taken": "2026-11-24T20:00:00Z", "why": "start", "session": {"start": "2026-11-24T19:59:55Z"},
    "city": {"name": "Riverton", "population": 1000, "happiness": 60, "money": 50000, "xp": 900, "milestone": 3, "tiles": 9,
             "date": {"year": 2026, "month": 3, "hour": 8, "minute": 0, "text": "March 2026, 08:00"}},
    "budget": {"income": {"TaxResidential": 40000, "FeeWater": 0}, "expenses": {"ServiceUpkeep": 30000},
               "totalIncome": 40000, "totalExpenses": 30000, "balance": 10000},
    "prefabs": ["Small Road", "Medium Road", "EU_Residential01", "Elementary School"],
    "streets": ["Main Street", "River Road"],
    "nodes": [{"id": 1, "x": 0.0, "z": 0.0, "y": 30.0}, {"id": 2, "x": 100.0, "z": 0.0, "y": 30.0},
              {"id": 3, "x": 200.0, "z": 0.0, "y": 30.0}, {"id": 4, "x": 200.0, "z": 300.0, "y": 30.0}],
    "edges": [
        {"id": 11, "prefab": 0, "kind": "road", "a": 1, "b": 2, "street": 0, "length": 100.0, "pts": pts(0, 0, 100, 0), "lanes": [1, 1], "flow": 90},
        {"id": 12, "prefab": 0, "kind": "road", "a": 2, "b": 3, "street": 0, "length": 100.0, "pts": pts(100, 0, 200, 0), "lanes": [1, 1], "flow": 40},
        {"id": 13, "prefab": 0, "kind": "road", "a": 3, "b": 4, "street": 1, "length": 300.0, "pts": pts(200, 0, 200, 300), "lanes": [1, 1]},
    ],
    "buildings": [{"id": 50, "prefab": 2, "kind": "residential", "level": 1, "lot": [2, 2], "x": 50.0, "z": 20.0, "y": 30.0, "angle": 0}],
    "districts": [{"name": "Old Town", "outline": [[0, 0], [10, 0], [10, 10]]}], "tiles": [], "truncated": [],
}


def after():
    """The same city in another session (all entity numbers changed): Main Street's second piece upgraded, River Road
    removed, a new street built, a school placed, two houses grew."""
    a = copy.deepcopy(BEFORE)
    a.update(taken="2026-11-24T22:00:00Z", why="done", session={"start": "2026-11-24T21:00:00Z", "changes": {
        "since": "2026-11-24T21:00:05Z", "sinceDate": "March 2026, 09:00", "roadsAddedKm": 0.4, "roadsRemovedKm": 0.3,
        "railAddedKm": 0, "railRemovedKm": 0, "grew": 2, "placed": 1, "removed": 0, "population": 312, "money": -42000, "tiles": 1}})
    a["city"].update(population=1312, money=8000, tiles=10)
    a["streets"] = ["Main Street", "Emerson Street"]
    a["nodes"] = [{"id": 101, "x": 0.0, "z": 0.0, "y": 30.0}, {"id": 102, "x": 100.4, "z": 0.2, "y": 30.0},
                  {"id": 103, "x": 200.0, "z": 0.0, "y": 30.0}, {"id": 105, "x": 200.0, "z": -400.0, "y": 30.0}]
    a["edges"] = [
        {"id": 211, "prefab": 0, "kind": "road", "a": 101, "b": 102, "street": 0, "length": 100.0, "pts": pts(0, 0, 100, 0), "lanes": [1, 1], "flow": 88},
        {"id": 212, "prefab": 1, "kind": "road", "a": 103, "b": 102, "street": 0, "length": 100.0, "pts": pts(200, 0, 100, 0), "lanes": [2, 2], "flow": 55},
        {"id": 214, "prefab": 1, "kind": "road", "a": 103, "b": 105, "street": 1, "length": 400.0, "pts": pts(200, 0, 200, -400),
         "lanes": [2, 0], "tunnel": True, "elevation": [-12.0, -8.0]},
        {"id": 215, "prefab": 0, "kind": "road", "a": 101, "b": 103, "length": 5.0, "pts": pts(0, 0, 200, 0), "lanes": [0, 0], "owned": True},
    ]
    a["buildings"] = BEFORE["buildings"] + [
        {"id": 60, "prefab": 3, "kind": "service", "service": "Education", "name": "Elementary School", "lot": [6, 6], "x": 190.0, "z": -350.0, "y": 30.0, "angle": 90},
        {"id": 61, "prefab": 2, "kind": "residential", "level": 1, "lot": [2, 2], "x": 70.0, "z": 20.0, "y": 30.0, "angle": 0},
        {"id": 62, "prefab": 2, "kind": "residential", "level": 1, "lot": [2, 2], "x": 90.0, "z": 20.0, "y": 30.0, "angle": 0},
    ]
    return a


def with_city_parts(a):
    """The 4b parts on top of after(): demand, people, problems, services, catalogue, transit, history."""
    a["prefabs"] = a["prefabs"] + ["Hospital01", "Highway Oneway - 2 lanes", "Roundabout01"]
    a["prefabTitles"] = ["Two-Lane Road", "Four-Lane Road", "", "Elementary School", "Hospital", "Two-Lane One-Way Highway", ""]
    a["demand"] = {"residentialLow": 100, "residentialMedium": 41, "residentialHigh": 0, "commercial": 0, "industrial": 65, "office": 100}
    a["people"] = {"households": 2183, "workers": 1268, "workable": 2374, "unemploymentPercent": 46.6, "homeless": 3}
    a["jobs"] = {"total": 2811, "free": 576}
    a["happiness"] = {"average": 55, "factors": [{"factor": "Consumption", "points": 5}, {"factor": "Healthcare", "points": -4}]}
    a["utilities"] = {"electricity": {"production": 0, "consumption": 77367, "import": 77367}, "water": {"freshCapacity": 9000, "freshConsumption": 4000}}
    a["problems"] = {"kinds": [{"id": "AmbulanceNotification", "title": "Waiting for ambulance", "count": 3},
                               {"id": "TrafficBottleneck", "title": "Traffic jam", "count": 1}],
                     "items": [{"kind": 0, "x": 10.0, "z": 5.0, "level": "MajorProblem", "on": "citizen"},
                               {"kind": 0, "x": 20.0, "z": 5.0, "level": "MajorProblem", "on": "building", "prefab": 4},
                               {"kind": 0, "x": 200.0, "z": -300.0, "level": "MajorProblem", "on": "citizen"},
                               {"kind": 1, "x": 150.0, "z": 0.0, "level": "Warning", "on": "road", "street": 0}]}
    a["services"] = [{"service": "Education", "title": "Education & Research", "budget": 100, "efficiency": 100, "upkeep": 50300}]
    a["buildings"][1]["use"] = {"what": "pupils", "now": 1400, "max": 1500}
    a["buildings"][1]["efficiency"] = 87
    a["buildings"].append({"id": 70, "prefab": 4, "kind": "service", "name": "Hospital", "lot": [8, 8], "x": 40.0, "z": 30.0, "y": 30.0,
                           "angle": 0, "use": {"what": "patients", "now": 10, "max": 100}, "efficiency": 100})
    a["catalogue"] = {"milestone": 5, "items": [
        {"prefab": "Small Road", "title": "Two-Lane Road", "kind": "road", "menu": "Small Roads", "unlocked": True, "costPerKm": 4000, "upkeepPerKm": 600, "lanes": [1, 1]},
        {"prefab": "Highway Oneway - 1 lane", "title": "One-Lane One-Way Highway", "kind": "highway", "menu": "Highways", "unlocked": True, "costPerKm": 1000, "upkeepPerKm": 150, "lanes": [1, 0]},
        {"prefab": "Roundabout01", "title": "Small Roundabout", "kind": "junction", "menu": "Intersections", "unlocked": True, "upkeep": 900},
        {"prefab": "Large Road", "title": "Six-Lane Road", "kind": "road", "menu": "Large Roads", "unlocked": False, "milestone": 6, "costPerKm": 7000},
        {"prefab": "Subway Track", "title": "Subway Track", "kind": "subway", "menu": "Subway", "unlocked": False, "milestone": 9}]}
    a["transit"] = [{"kind": "Tram", "name": "T1 Campus Line", "number": 1, "color": "#16a34a", "vehicles": 4, "passengers": 26,
                     "usagePercent": 16, "length": 4200.0, "active": True, "stops": [{"x": 0, "z": 0}, {"x": 100, "z": 0}]}]
    a["history"] = {"population": [0, 1000, 1312], "money": [2000000, 90000, 8000]}
    return a


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = city.main(["city.py", *map(str, args)])
    return code, out.getvalue()


class CityReader(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.dir, True))
        (self.dir / "city-start.json").write_text(json.dumps(BEFORE), encoding="utf-8")
        (self.dir / "city.json").write_text(json.dumps(after()), encoding="utf-8")

    def test_summary(self):
        code, out = run("summary", self.dir / "city.json")
        self.assertEqual(code, 0)
        self.assertIn("# Riverton: city snapshot", out)
        self.assertIn("on Done for today", out)
        self.assertIn("| People | 1,312 (happiness 60) |", out)
        self.assertIn("balance +$10,000", out)
        self.assertIn("Income: TaxResidential $40,000.", out)   # zero lines are left out
        self.assertIn("road 600 m", out)                       # the owned piece (a building's) is left out
        self.assertIn("tunnels 400 m", out)
        self.assertIn("Districts: Old Town.", out)
        self.assertIn("0.4 km of new road, 0.3 km removed", out)
        self.assertIn("+312 people, money −$42,000, +1 map tiles", out)

    def test_changes_across_sessions_match_roads_by_place(self):
        code, out = run("changes", self.dir)   # a journal folder: city.json against city-start.json
        self.assertEqual(code, 0)
        self.assertIn("## Built: 400 m", out)
        self.assertIn("- Emerson Street: 400 m (Medium Road tunnel)", out)
        self.assertIn("## Removed: 300 m", out)
        self.assertIn("- River Road: 300 m (Small Road)", out)
        self.assertIn("Main Street: Small Road → Medium Road", out)
        self.assertNotIn("Main Street: 100 m", out)   # the untouched piece matched, ends 0.4 m apart, other entity numbers
        self.assertIn("- Grew from zoning: residential 2", out)
        self.assertIn("- Placed: Elementary School (service), near Emerson Street", out)
        self.assertIn("People +312, money −$42,000, map tiles +1.", out)

    def test_changes_against_a_kept_copy(self):
        kept = self.dir / "kept.json"
        kept.write_text(json.dumps(after()), encoding="utf-8")
        code, out = run("changes", self.dir / "city.json", "--before", kept)
        self.assertEqual(code, 0)
        self.assertNotIn("## Built", out)
        self.assertIn("## Buildings: 0 new, 0 gone", out)

    def test_roads_cut_for_size_are_not_compared(self):
        cut = after()
        cut["truncated"] = ["edges (file too large)"]
        (self.dir / "city.json").write_text(json.dumps(cut), encoding="utf-8")
        code, out = run("changes", self.dir)
        self.assertEqual(code, 1)
        self.assertIn("can't be compared", out)

    def test_streets_and_one_street(self):
        code, out = run("streets", self.dir / "city.json")
        self.assertIn("| Emerson Street | 400 m | Medium Road | 2 one-way |", out)
        self.assertIn("| Main Street | 200 m | Small Road, Medium Road | 1+1, 2+2 |", out)
        code, out = run("street", self.dir / "city.json", "emerson")
        self.assertEqual(code, 0)
        self.assertIn("# Emerson Street: 400 m in 1 pieces", out)
        self.assertIn("| Medium Road | 2 one-way | 1 | 400 m | tunnel (-12 to -8 m) | – |", out)
        code, out = run("street", self.dir / "city.json", "Cypress Street")
        self.assertEqual(code, 1)
        self.assertIn("Street names change when roads are rebuilt", out)

    def test_city_wide_parts(self):
        (self.dir / "city.json").write_text(json.dumps(with_city_parts(after())), encoding="utf-8")
        code, out = run("summary", self.dir)
        self.assertIn("Demand (0 to 100): residentialLow 100, residentialMedium 41, residentialHigh 0, commercial 0, industrial 65, office 100.", out)
        self.assertIn("unemployment 46.6%, homeless 3.", out)
        self.assertIn("Jobs: 2,811 workplaces, 576 free.", out)
        self.assertIn("Happiness 55: Consumption +5, Healthcare -4.", out)
        self.assertIn("Electricity: makes 0 kW, uses 7.7 MW, imports 7.7 MW.", out)   # tenths of a kilowatt, as the game shows them
        self.assertIn("Water: pumps 9,000 m³, uses 4,000 m³", out)
        self.assertIn("Problems: Waiting for ambulance 3, Traffic jam 1.", out)
        self.assertIn("T1 Campus Line (Tram, 2 stops, 4 vehicles, 16% full)", out)
        self.assertIn("Over 3 months: people 0 → 1,312, money $2,000,000 → $8,000.", out)

        code, out = run("problems", self.dir)
        self.assertEqual(code, 0)
        self.assertIn("## Waiting for ambulance ×3", out)
        self.assertIn("Near: Main Street 2, Emerson Street.", out)
        self.assertIn("On: Hospital.", out)                      # the building's menu name
        self.assertIn("## Traffic jam ×1\n\nNear: Main Street.", out)   # a road's own street

        code, out = run("services", self.dir)
        self.assertIn("| Education & Research | 100% | 100% | $50,300 |", out)
        self.assertLess(out.index("Elementary School"), out.index("| Hospital"))   # fullest first
        self.assertIn("| Elementary School | Emerson Street | 1,400 of 1,500 pupils (93%) | 87% |", out)

        code, out = run("catalogue", self.dir)
        self.assertEqual(code, 0)
        self.assertIn("## Small Roads\n\n- Two-Lane Road (lanes 1+1; $4,000/km, upkeep $600/km a month)", out)
        self.assertIn("- One-Lane One-Way Highway (1 lane one-way; $1,000/km", out)
        self.assertIn("- Small Roundabout (upkeep $900 a month)", out)
        self.assertIn("## Milestone 6 unlocks\n\n- Six-Lane Road (Large Roads)", out)
        self.assertNotIn("Subway Track", out)                     # neither unlocked nor next

    def test_the_map_part_in_the_summary(self):
        a = with_city_parts(after())
        a["map"] = {"name": "Riverton Valley", "theme": "North American", "leftHandTraffic": False, "mode": "NormalMode",
                    "options": {}, "links": [{"kind": "road", "x": 0, "z": 0}, {"kind": "ship", "x": 1, "z": 1}, {"kind": "road", "x": 5, "z": 5}]}
        (self.dir / "city.json").write_text(json.dumps(a), encoding="utf-8")
        code, out = run("summary", self.dir / "city.json")
        self.assertIn("| Map | Riverton Valley, North American theme, right-hand traffic, NormalMode |", out)
        self.assertIn("| Links off the map | road 2, ship 1 |", out)

    def test_older_snapshots_without_the_parts(self):
        code, out = run("catalogue", self.dir)
        self.assertEqual(code, 1)
        self.assertIn("0.7 or later", out)
        code, out = run("problems", self.dir)
        self.assertIn("no problems part", out)
        code, out = run("summary", self.dir)
        self.assertNotIn("Demand", out)

    def test_lanes_text(self):
        self.assertEqual(city.lanes_text({"lanes": [0, 0]}), "no car lanes")
        self.assertEqual(city.lanes_text({"lanes": [2, 2], "bus": [1, 1]}), "2+2 (bus 1+1)")
        self.assertEqual(city.lanes_text({}), "?")

    def test_missing_or_odd_files(self):
        with self.assertRaises(SystemExit) as e:
            city.load(self.dir / "nope.json")
        self.assertIn("Take a snapshot", str(e.exception))
        odd = self.dir / "odd.json"
        odd.write_text("[1, 2]", encoding="utf-8")
        with self.assertRaises(SystemExit):
            city.load(odd)
        other = dict(BEFORE, format=2)
        odd.write_text(json.dumps(other), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            city.load(odd)
        self.assertIn("format 2", out.getvalue())

    def test_a_journal_source_finds_its_snapshot(self):
        src = self.dir / "src"
        src.mkdir()
        (src / "journal.toml").write_text('id = "riverton"\ncity = "Riverton"\n', encoding="utf-8")
        self.assertEqual(city.snapshot_path(src), city.ROOT / "riverton" / "city.json")
        self.assertEqual(city.snapshot_path(src, start=True), city.ROOT / "riverton" / "city-start.json")


class Numbers(unittest.TestCase):
    """city.py numbers and keep: the report's [[numbers]] and the copy each report keeps."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.dir, True))
        (self.dir / "city-start.json").write_text(json.dumps(BEFORE), encoding="utf-8")
        (self.dir / "city.json").write_text(json.dumps(with_city_parts(after())), encoding="utf-8")

    def test_the_table_before_and_now(self):
        code, out = run("numbers", self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("| People | 1,000 | 1,312 | +312 |", out)
        self.assertIn("| Money | $50,000 | $8,000 | −$42,000 |", out)
        self.assertIn("| Roads and highways | 500 m | 600 m | +100 m |", out)   # a building's own piece left out
        self.assertIn("| Unemployment | ? | 46.6% |  |", out)                    # the older snapshot has no people part
        self.assertIn("| Map tiles | 9 | 10 | +1 |", out)
        self.assertNotIn("Nothing new", out)

    def test_toml_for_the_report(self):
        import tomllib
        code, out = run("numbers", self.dir, "--toml")
        self.assertEqual(code, 0, out)
        rows = {r["label"]: r for r in tomllib.loads(out)["numbers"]}
        self.assertEqual(rows["People"], {"label": "People", "before": "1,000", "after": "1,312", "change": "+312"})
        self.assertEqual(rows["Warning icons"]["after"], "4")

    def test_nothing_new_saved(self):
        import tomllib
        (self.dir / "city-start.json").write_text((self.dir / "city.json").read_text(encoding="utf-8"), encoding="utf-8")
        code, out = run("numbers", self.dir)
        self.assertIn("**Nothing new:**", out)
        code, out = run("numbers", self.dir, "--toml")
        rows = {r["label"]: r for r in tomllib.loads(out)["numbers"]}
        self.assertEqual(rows["People"]["after"], "no save yet")
        self.assertEqual(rows["People"]["before"], "1,312")

    def test_a_city_that_didnt_run(self):
        now = after()
        now["city"]["date"] = BEFORE["city"]["date"]
        (self.dir / "city.json").write_text(json.dumps(now), encoding="utf-8")
        code, out = run("numbers", self.dir)
        self.assertIn("the city didn't run", out)

    def test_keep_then_compare_with_the_kept_copy(self):
        journals = self.dir / "journals"
        (journals / "riverton").mkdir(parents=True)
        src = self.dir / "riverton" / "journal"
        src.mkdir(parents=True)
        (src / "journal.toml").write_text('id = "riverton"\ncity = "Riverton"\n', encoding="utf-8")
        old_root = city.ROOT
        city.ROOT = journals
        self.addCleanup(lambda: setattr(city, "ROOT", old_root))
        (journals / "riverton" / "city-start.json").write_text(json.dumps(BEFORE), encoding="utf-8")
        (journals / "riverton" / "city.json").write_text(json.dumps(after()), encoding="utf-8")

        code, out = run("numbers", src, "--before", "kept")
        self.assertIn("no kept snapshot older than this one", out)
        self.assertIn("| People | 1,000 | 1,312 |", out)

        code, out = run("keep", src, "--date", "2026-11-24")
        self.assertEqual(code, 0, out)
        kept = self.dir / "riverton" / "manager" / "snapshots" / "2026-11-24.json"
        self.assertTrue(kept.exists())
        code, out = run("keep", src, "--date", "2026-11-24")
        self.assertIn("Already kept", out)

        later = after()
        later.update(taken="2026-11-25T21:00:00Z")
        later["city"].update(population=2000, date={"text": "April 2026, 08:00"})
        (journals / "riverton" / "city.json").write_text(json.dumps(later), encoding="utf-8")
        code, out = run("numbers", src, "--before", "kept")
        self.assertIn("Before: 2026-11-24.json", out)
        self.assertIn("| People | 1,312 | 2,000 | +688 |", out)
        code, out = run("keep", src, "--date", "2026-11-24")
        self.assertTrue((kept.parent / "2026-11-24-2.json").exists(), out)

        with self.assertRaises(SystemExit):
            run("keep", self.dir / "city.json")
        with self.assertRaises(SystemExit):
            run("keep", src, "--date", "tomorrow")

class Stage(unittest.TestCase):
    """city.py stage: whether the intake founds the city or takes it over."""

    def snap(self, people=0, road_m=0, buildings=0, highway_m=14800):
        edges = [{"kind": "highway", "length": highway_m}, {"kind": "train", "length": 9100}]
        if road_m:
            edges.append({"kind": "road", "length": road_m})
        return {"format": 1, "city": {"name": "Riverton", "population": people, "milestone": 0, "date": {"text": "June 2026"}},
                "edges": edges, "buildings": [{"kind": "residential"}] * buildings + [{"kind": "other"}] * 3,
                "districts": [], "transit": []}

    def test_a_city_with_nothing_built_is_new_and_the_maps_own_highways_dont_count(self):
        kind, f = city.stage(self.snap())
        self.assertEqual(kind, "new")
        self.assertEqual((f["roadKm"], f["highwayKm"], f["railKm"], f["buildings"]), (0.0, 14.8, 9.1, 0))

    def test_a_small_start_is_begun_and_a_real_city_is_established(self):
        self.assertEqual(city.stage(self.snap(people=120, road_m=2400, buildings=30))[0], "begun")
        self.assertEqual(city.stage(self.snap(people=3778, road_m=45200, buildings=1226))[0], "established")
        self.assertEqual(city.stage(self.snap(people=0, road_m=8000))[0], "established", "a road network is a city in progress")

    def test_stage_command_says_which_mode_fits(self):
        base = Path(tempfile.mkdtemp(prefix="cm-stage-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(base, ignore_errors=True))
        f = base / "city.json"
        f.write_text(json.dumps(self.snap()), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(city.main(["city.py", "stage", str(f)]), 0)
        self.assertIn("a brand-new city", out.getvalue())
        self.assertIn("Founding mode fits", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            city.main(["city.py", "stage", str(f), "--json"])
        self.assertEqual(json.loads(out.getvalue())["stage"], "new")


if __name__ == "__main__":
    unittest.main()
