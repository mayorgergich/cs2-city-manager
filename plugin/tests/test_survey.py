"""Tests for survey.py, the map survey from the mod's city snapshot, on a small made-up map (made_up_map.py)."""
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
import survey  # noqa: E402


def tile_index(row, col):
    return row * 5 + col


class Survey(unittest.TestCase):
    def setUp(self):
        self.snap = mm.snapshot()
        self.s = survey.survey(self.snap)

    def test_owned_and_buyable_tiles(self):
        self.assertEqual(self.s["tiles"]["owned"], 2)
        self.assertEqual(self.s["tiles"]["permitsLeft"], 3)
        self.assertEqual(sorted(self.s["start"]["tiles"]), sorted(tile_index(*rc) for rc in mm.OWNED))
        buy = {b["tile"] for b in self.s["tiles"]["buyable"]}
        expected = {tile_index(*rc) for rc in [(1, 2), (3, 2), (2, 3), (1, 1), (3, 1), (2, 0)]}
        self.assertEqual(buy, expected, "tiles sharing a side with the owned ones, not corners")
        self.assertEqual([b["rank"] for b in self.s["tiles"]["buyable"]], list(range(1, 7)))
        worst = self.s["tiles"]["buyable"][-1]
        self.assertIn(worst["tile"], {tile_index(2, 3), tile_index(2, 0)}, "the hilly or the river tile ranks last")
        by_tile = {b["tile"]: b for b in self.s["tiles"]["buyable"]}
        self.assertEqual(by_tile[tile_index(1, 2)]["resources"].get("Oil"), "lots")
        self.assertIn("highway", by_tile[tile_index(3, 2)]["networks"])
        self.assertTrue(all(b["where"].endswith("side") for b in self.s["tiles"]["buyable"]))

    def test_ground_and_flat_land(self):
        st, whole = self.s["start"]["ground"], self.s["map"]["ground"]
        self.assertGreater(st["flat"], 80)
        self.assertGreater(st["water"], 0, "the river runs along the west owned tile")
        self.assertGreater(whole["steep"], 5, "the eastern hill is 30%")
        self.assertGreater(whole["hilly"], 0, "the northern rise is 10%")
        self.assertTrue(self.s["start"]["flatPatches"])
        self.assertGreater(self.s["flatSquare"]["metres"], 500)

    def test_river_flows_south(self):
        rivers = [b for b in self.s["water"]["bodies"] if b["kind"] == "river or creek"]
        self.assertEqual(len(rivers), 1)
        upstream, downstream = rivers[0]["flows"].split(" to ")
        self.assertIn("north", upstream)
        self.assertIn("south", downstream)
        self.assertGreater(self.s["start"]["shoreKm"], 0)

    def test_connections_highways_and_rail(self):
        rows = {(c["kind"], c["edge"].split(",")[0]) for c in self.s["connections"]}
        self.assertEqual(rows, {("highway", "west edge"), ("highway", "east edge"), ("train", "north edge"), ("train", "south edge")})
        hw = self.s["highways"]
        self.assertEqual(len(hw["atGrade"]), 1)
        self.assertEqual(hw["atGrade"][0]["roads"], ["Old Lane"])
        self.assertTrue(hw["atGrade"][0]["lights"])
        self.assertEqual([e["roads"] for e in hw["ends"]], [["Main Street"]])
        self.assertEqual(hw["ends"][0]["highway"], ["Entry Highway"])
        self.assertGreater(hw["bridgesKm"], 0)
        self.assertIn("Ring Highway", hw["names"])
        self.assertEqual({s["name"] for s in self.s["start"]["streets"]}, {"Main Street", "Old Lane"}, "the start and the tiles around it")

    def test_landmarks_and_resources(self):
        self.assertEqual([l["name"] for l in self.s["landmarks"]], ["Old Mill Ruins"])
        self.assertIn("west", self.s["resources"]["FertileLand"]["where"])
        self.assertIn("east", self.s["resources"]["Ore"]["where"])
        self.assertEqual(self.s["grids"]["landValue"], {"max": 0})

    def test_every_tile_owned(self):
        everything = {(r, c) for r in range(5) for c in range(5)}
        s = survey.survey(mm.snapshot(owned=everything))
        self.assertTrue(s["start"]["allOwned"])
        self.assertEqual(len(s["start"]["tiles"]), 9, "the 3 × 3 tiles around the map's starter road")
        self.assertIn(tile_index(2, 2), s["start"]["tiles"])
        self.assertEqual(s["tiles"]["buyable"], [])
        self.assertIn("unlock all map tiles", s["start"]["note"])

    def test_founding_names_the_map_and_its_links_the_snapshot_cannot_show(self):
        import founding
        base = Path(tempfile.mkdtemp(prefix="cm-survey-founding-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        (base / "journal").mkdir()
        (base / "journal/journal.toml").write_text('id = "riverton"\ncity = "Riverton"\n', encoding="utf-8")
        (base / "manager").mkdir()
        (base / "manager/founding.md").write_text('+++\nmap = "Test Bay"\nstart_hint = "By the river mouth"\n+++\n', encoding="utf-8")
        maps = [({"displayName": "Test Bay", "connections": {"road": True, "train": False, "ship": True, "air": True}}, "game", None, None)]
        real = founding.all_maps
        founding.all_maps = lambda: maps
        self.addCleanup(setattr, founding, "all_maps", real)
        facts = survey.founding_facts(base / "journal")
        self.assertEqual(facts, {"startHint": "By the river mouth", "map": "Test Bay", "mapConnections": ["road", "ship", "air"]})
        s = dict(self.s, founding=facts)
        text = survey.report(s)
        self.assertIn("**From the map's own file** (Test Bay): also a **ship** link and an **air** link", text)
        self.assertIn("**Where the Mayor wants to start** (the charter): By the river mouth", text)
        self.assertEqual(survey.founding_facts(self.snap_path if hasattr(self, "snap_path") else base / "nothing.json"), {})
        self.assertEqual(survey.founding_facts(base / "nowhere"), {}, "no founding.md: nothing, and no error")

    def test_every_tile_owned_on_an_irregular_map_says_how_many_tiles(self):
        everything = {(r, c) for r in range(5) for c in range(5)}
        snap = mm.snapshot(owned=everything)
        gone = {tile_index(r, c) for r, c in ((1, 1), (1, 3), (3, 1), (3, 3))}   # an odd layout: the middle has no corners
        snap["mapTiles"]["tiles"] = [t for i, t in enumerate(snap["mapTiles"]["tiles"]) if i not in gone]
        s = survey.survey(snap)
        n = len(s["start"]["tiles"])
        self.assertNotEqual(n, 9)
        self.assertIn(f"the {n} tile", s["start"]["note"])
        self.assertIn("aren't a regular grid", s["start"]["note"])
        self.assertIn("the Mayor's choice", s["start"]["note"])

    def test_report_has_words_not_coordinates(self):
        text = survey.report(self.s)
        for heading in ("## Settings that change the plan", "## The start", "## Connections off the map",
                        "## Highways and railways", "## Next tiles to buy", "## The whole map", "## Land value and pollution"):
            self.assertIn(heading, text)
        self.assertIn("Old Lane on Ring Highway", text)
        self.assertIn("All zero", text)
        self.assertNotIn("[x ", text)
        self.assertNotRegex(text, r"-\d{3}", "no raw coordinates for the Mayor")

    def test_road_builder_names(self):
        self.assertEqual(survey.piece_name("r4913eff1-0142-4ad8-9016-21f8a90e9b50-76561190000000000"), "a Road Builder road")
        self.assertEqual(survey.piece_name("Four-Lane Road"), "Four-Lane Road")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cm-survey-"))
        self.snap_path = self.base / "city-start.json"
        self.snap_path.write_text(json.dumps(mm.snapshot()), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = survey.main(["survey.py", *map(str, args)])
        return code, out.getvalue()

    def test_writes_pictures_and_facts(self):
        from PIL import Image
        code, text = self.run_main(self.snap_path, "--out", self.base / "out")
        self.assertEqual(code, 0)
        self.assertIn("# Survey of Riverton", text)
        for name in ("survey-map.png", "survey-start.png"):
            with Image.open(self.base / "out" / name) as im:
                self.assertEqual(im.format, "PNG")
                self.assertLessEqual(im.width, 1600)
                self.assertLessEqual(im.height, 3200, "the journal shows pictures up to 1600 × 3200")
        facts = json.loads((self.base / "out/survey.json").read_text(encoding="utf-8"))
        self.assertEqual(facts["city"], "Riverton")
        self.assertEqual(facts["snapshot"], str(self.snap_path))

    def test_folder_picks_the_start_snapshot_when_there_is_no_city_json(self):
        self.assertEqual(survey.snapshot_file(self.base), self.snap_path)
        (self.base / "city.json").write_text(json.dumps(mm.snapshot()), encoding="utf-8")
        self.assertEqual(survey.snapshot_file(self.base), self.base / "city.json")
        self.assertEqual(survey.snapshot_file(self.base, start=True), self.snap_path)

    def test_older_snapshot_without_tiles_grids_or_catalogue(self):
        self.snap_path.write_text(json.dumps(mm.snapshot(parts=False)), encoding="utf-8")
        code, text = self.run_main(self.snap_path, "--out", self.base / "old")
        self.assertEqual(code, 0)
        self.assertIn("Nothing to buy listed", text)
        self.assertIn("Resources:** not in this snapshot", text)
        self.assertIn("Not in this snapshot (City Manager 0.7 or later)", text)

    def test_snapshot_without_terrain(self):
        snap = mm.snapshot()
        del snap["terrain"]
        self.snap_path.write_text(json.dumps(snap), encoding="utf-8")
        code, text = self.run_main(self.snap_path, "--out", self.base / "none")
        self.assertEqual(code, 1)
        self.assertIn("no terrain part", text)


if __name__ == "__main__":
    unittest.main()
