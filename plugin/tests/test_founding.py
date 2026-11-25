"""Tests for founding.py: the maps, the playset and the founding interview's answers, on a made-up game install."""
import io
import contextlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/city-manager/scripts"
FOUNDING = SCRIPTS / "founding.py"


def map_package(path, name, **meta):
    path.parent.mkdir(parents=True, exist_ok=True)
    m = {"displayName": name, "theme": "European", "area": 200e6, "buildableLand": 100e6, "temperatureRange": {"min": 5, "max": 25},
         "surfaceWaterAvailability": 0, "groundWaterAvailability": 1e7, "resources": {"fertile": 30e6, "forest": 100e6, "oil": 0, "ore": 10e6, "fish": 0},
         "connections": {"road": True, "train": True, "ship": False, "air": False, "electricity": True, "water": False}, "contentPrerequisites": None}
    m.update(meta)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        z.writestr(f"{name}.MapMetadata", json.dumps(m))
        z.writestr(f"{name}.MapData", b"\0" * 16)


class Founding(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cm-founding-"))
        self.game = self.base / "Cities Skylines II"
        self.user = self.base / "LocalLow"
        map_package(self.game / "Cities2_Data/Content/Game/Maps/Plains.cok", "Plains", theme="North American",
                    resources={"fertile": 60e6, "forest": 100e6, "oil": 0, "ore": 10e6, "fish": 0})
        map_package(self.game / "Cities2_Data/Content/Game/Maps/Coast.cok", "Coast",
                    resources={"fertile": 10e6, "forest": 100e6, "oil": 5e6, "ore": 10e6, "fish": 90e6},
                    connections={"road": True, "train": False, "ship": True, "air": True, "electricity": True, "water": False})
        map_package(self.user / ".cache/Mods/pdx_mods/5001_2/Green Valley.cok", "Green Valley", contentPrerequisites=["Mod:6001"],
                    resources={"fertile": 30e6, "forest": 100e6, "oil": 0, "ore": 10e6, "fish": 10e6})
        map_package(self.user / "Maps/My Island.cok", "My Island")
        (self.user / ".cache/Mods/pdx_mods/7001_1").mkdir(parents=True)
        with zipfile.ZipFile(self.user / ".cache/Mods/pdx_mods/7001_1/Houses.cok", "w") as z:   # an asset pack, not a map
            z.writestr("House.Prefab", "{}")
        self.playset([("155935", True), ("5001", False), ("6001", True)])
        con = sqlite3.connect(self.user / "launcher-v2.sqlite")
        con.execute("create table mods (pdxId text, displayName text, name text)")
        con.executemany("insert into mods values (?, ?, ?)", [("155935", "City Planning Draft", None), ("6001", "Valley Assets", None), ("5001", "Green Valley Map", None)])
        con.commit()
        con.close()
        self.city = self.base / "riverton"
        (self.city / "journal").mkdir(parents=True)
        (self.city / "journal/journal.toml").write_text('id = "riverton"\ncity = "Riverton"\n', encoding="utf-8")
        (self.city / "manager").mkdir()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def playset(self, mods):
        p = self.user / ".cache/Mods/playset_config.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"activePlaysetId": "a", "playsets": [{"id": "b", "presentation": {"name": "Other"}, "mods": []},
            {"id": "a", "presentation": {"name": "My City"}, "mods": [{"source": "pdx_mods", "sourceId": i, "isEnabled": on} for i, on in mods]}]}), encoding="utf-8")

    def run_tool(self, *args):
        env = dict(os.environ, CS2_GAME_DIR=str(self.game), CS2_USERDATA=str(self.user), CITY_MANAGER_ROOT=str(self.user / "ModsData/CityManager"))
        r = subprocess.run([sys.executable, "-I", str(FOUNDING), *map(str, args)], capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
        return r.returncode, r.stdout + r.stderr

    def founding(self, text):
        (self.city / "manager/founding.md").write_text(text, encoding="utf-8")

    def test_maps_lists_the_games_mods_and_own_maps(self):
        code, out = self.run_tool("maps")
        self.assertEqual(code, 0, out)
        self.assertIn("# Maps you can start on (4)", out)                       # the asset pack isn't a map
        self.assertIn("| Plains | game | North American | 100 km² (50%) | 5 to 25 °C | ground |", out)
        self.assertIn("fertile (high)", out.split("| Plains |")[1].split("\n")[0])   # rated against the other maps
        self.assertIn("fish (high)", out.split("| Coast |")[1].split("\n")[0])
        self.assertIn("road, ship, air, electricity", out)
        self.assertIn("| Green Valley | Paradox Mods 5001 (in the playset, switched off) |", out)
        self.assertIn("| My Island | your own |", out)

    def test_one_map_says_what_it_needs_and_whether_its_mod_is_on(self):
        code, out = self.run_tool("map", "green")
        self.assertEqual(code, 0, out)
        self.assertIn("# Green Valley", out)
        self.assertIn("in the playset but switched off", out)
        self.assertIn("Needs: Mod:6001 (Valley Assets)", out)
        code, out = self.run_tool("map", "Nowhere")
        self.assertEqual(code, 1)
        self.assertIn("founding.py maps", out)

    def test_playset(self):
        code, out = self.run_tool("playset", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("# Active playset: My City", out)
        self.assertIn("2 mods switched on, 1 switched off.", out)
        self.assertIn("City Manager: NOT on in this playset", out)
        self.assertIn("City Planning Draft (the build overlay): on.", out)
        self.assertIn("Green Valley (off)", out)
        self.assertIn("- Valley Assets (6001)", out)
        (self.user / "Mods/CityManager").mkdir(parents=True)
        (self.user / "Mods/CityManager/CityManager.dll").write_bytes(b"")
        self.playset([("5001", True)])
        code, out = self.run_tool("playset")
        self.assertIn("installed as a local mod", out)
        self.assertIn("City Planning Draft (the build overlay): NOT in this playset", out)
        self.assertIn("Green Valley (on)", out)

    def test_check_reads_the_answers_and_flags_mistakes(self):
        code, out = self.run_tool("check", self.city / "journal")
        self.assertEqual(code, 1)
        self.assertIn("No ", out)
        self.founding('+++\nwants = ["map", "backbone"]\ncity = "Riverton"\ntheme = "European"\ntransit = ["trams"]\n\n[notes]\ngeneral = "short sessions"\nbackbone = "underpasses"\n+++\nWords.\n')
        code, out = self.run_tool("check", self.city / "journal")
        self.assertEqual(code, 0, out)
        self.assertIn("Parts asked for: map, backbone.", out)
        self.founding('+++\nwants = ["map", "everything"]\ntheme = "Martian"\ntransit = "trams"\ncolour = "blue"\nnotes = "just a line"\n+++\n')
        code, out = self.run_tool("check", self.city)
        self.assertEqual(code, 1)
        self.assertIn("wants: 'everything' isn't a part", out)
        self.assertIn("theme = 'Martian': one of European, North American", out)
        self.assertIn("transit should be a list", out)
        self.assertIn("unknown key 'colour'", out)
        self.assertNotIn("notes", out.replace("founding.md", ""))    # a line of text is fine too

    def test_newgame_fills_in_the_screen_from_the_answers(self):
        self.founding('+++\ncity = "Riverton"\nmap = "Green Valley"\nmap_kind = "custom"\ntheme = "European"\ntraffic = "left"\noptions = ["unlimited money"]\n+++\n')
        code, out = self.run_tool("newgame", self.city / "journal")
        self.assertEqual(code, 0, out)
        self.assertIn("City name: **Riverton**, exactly", out)
        self.assertIn("Theme: **European**", out)
        self.assertIn("Traffic drives on the **left**", out)
        self.assertIn("Option: unlimited money.", out)
        self.assertIn("custom maps show only when their mod is on", out)
        self.assertIn("# Green Valley", out)                           # the custom map's detail follows
        self.assertIn("Save Game", out)


if __name__ == "__main__":
    unittest.main()
