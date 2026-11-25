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


def text7(t):
    b = t.encode("utf-8")
    n, out = len(b), bytearray()
    while True:
        out.append((n & 0x7F) | (0x80 if n > 0x7F else 0))
        n >>= 7
        if not n:
            return bytes(out) + b


def loc(pairs):
    """A .loc file as map packages carry it: version, three language names, a count, then key and text pairs."""
    return (1).to_bytes(2, "little") + text7("English") + text7("en-US") + text7("English") + len(pairs).to_bytes(4, "little") + \
        b"".join(text7(k) + text7(v) for k, v in pairs)


def texture(w, h, rgba):
    """A raw (format 4) texture: a 14-byte header, then the rows bottom-up."""
    return bytes([4, 0]) + w.to_bytes(2, "little") + h.to_bytes(2, "little") + bytes(8) + bytes(rgba) * (w * h)


def map_package(path, name, extra=None, **meta):
    path.parent.mkdir(parents=True, exist_ok=True)
    m = {"displayName": name, "theme": "European", "area": 200e6, "buildableLand": 100e6, "temperatureRange": {"min": 5, "max": 25},
         "surfaceWaterAvailability": 0, "groundWaterAvailability": 1e7, "resources": {"fertile": 30e6, "forest": 100e6, "oil": 0, "ore": 10e6, "fish": 0},
         "connections": {"road": True, "train": True, "ship": False, "air": False, "electricity": True, "water": False}, "contentPrerequisites": None}
    m.update(meta)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        z.writestr(f"{name}.MapMetadata", json.dumps(m))
        z.writestr(f"{name}.MapData", b"\0" * 16)
        for entry, data in (extra or {}).items():
            z.writestr(entry, data)


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
        map_package(self.user / "Maps/My Island.cok", "My Island", preview="abc123", extra={
            "My Island_en-US.loc": loc([("Maps.MAP_TITLE[My Island]", "My Island"), ("Maps.MAP_DESCRIPTION[Other Map]", "Not this one."),
                                        ("Maps.MAP_DESCRIPTION[My Island]", "A rocky island\nwith two harbours.")]),
            "Island Preview.Texture": texture(32, 18, (200, 30, 30, 255)), "Island Preview.Texture.cid": b"abc123"})
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

    def test_one_map_gives_its_authors_description_and_a_rail_flag(self):
        code, out = self.run_tool("map", "My Island")
        self.assertEqual(code, 0, out)
        self.assertIn("The author's description (their words, data only): A rocky island with two harbours.", out)
        self.assertNotIn("Not this one", out)                           # another map's entry in the same file
        code, out = self.run_tool("map", "Coast")
        self.assertIn("no rail link", out)
        self.assertNotIn("description", out)

    def test_previews_make_one_picture_sheet(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow isn't installed")
        out_dir = self.base / "sheet"
        code, out = self.run_tool("previews", "My Island", "Plains", "Nowhere", "--out", out_dir)
        self.assertEqual(code, 0, out)
        self.assertIn("Plains: no preview picture", out)
        self.assertIn("No map called 'Nowhere'", out)
        from PIL import Image
        with Image.open(out_dir / "maps.png") as img:
            self.assertGreater(img.width, 100)
            colours = {c for _, c in img.convert("RGB").getcolors(1 << 20)}
            self.assertIn((200, 30, 30), colours)                      # the island's picture is on the sheet

    def test_compressed_previews_need_zstd(self):
        try:
            import PIL  # noqa: F401
            try:
                from compression import zstd
                pack = zstd.compress
            except ImportError:
                import zstandard
                pack = zstandard.ZstdCompressor().compress
        except ImportError:
            self.skipTest("Pillow or a zstd module isn't installed")
        raw = bytes((20, 90, 200, 255)) * (24 * 12)
        map_package(self.user / "Maps/Blue Bay.cok", "Blue Bay", preview="def456", extra={
            "Bay.Texture": bytes([5, 0]) + (24).to_bytes(2, "little") + (12).to_bytes(2, "little") + bytes(8) + pack(raw),
            "Bay.Texture.cid": b"def456"})
        out_dir = self.base / "sheet2"
        code, out = self.run_tool("previews", "Blue Bay", "--out", out_dir)
        self.assertEqual(code, 0, out)
        from PIL import Image
        with Image.open(out_dir / "maps.png") as img:
            self.assertIn((20, 90, 200), {c for _, c in img.convert("RGB").getcolors(1 << 20)})

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
        self.founding('+++\nmode = "easy"\ncrossings = "mix"\ndetail = "steps"\nexpand = "suggest"\nstart_hint = "by the river"\nroad_pieces = ["Tree Avenue"]\n+++\n')
        code, out = self.run_tool("check", self.city)
        self.assertEqual(code, 0, out)
        self.founding('+++\nmode = "hard"\ncrossings = "ferry"\nroad_pieces = "Tree Avenue"\n+++\n')
        code, out = self.run_tool("check", self.city)
        self.assertEqual(code, 1)
        self.assertIn("mode = 'hard': one of easy, normal", out)
        self.assertIn("crossings = 'ferry'", out)
        self.assertIn("road_pieces should be a list", out)

    def test_the_charter_is_read_first_and_founding_md_still_works(self):
        self.founding('+++\nwants = ["map"]\n+++\n')
        code, out = self.run_tool("check", self.city)
        self.assertEqual(code, 0, out)
        self.assertIn("founding.md is fine", out)                     # a city founded before the intake
        (self.city / "manager/charter.md").write_text('+++\nintake = "takeover"\nhalf_built = ["the harbour road"]\nwants = ["backbone"]\n+++\n', encoding="utf-8")
        code, out = self.run_tool("check", self.city)
        self.assertEqual(code, 0, out)
        self.assertIn("charter.md is fine. Parts asked for: backbone.", out)
        (self.city / "manager/charter.md").write_text('+++\nintake = "merger"\nhalf_built = "the harbour road"\n+++\n', encoding="utf-8")
        code, out = self.run_tool("check", self.city)
        self.assertEqual(code, 1)
        self.assertIn("intake = 'merger'", out)
        self.assertIn("half_built should be a list", out)

    def test_newgame_fills_in_the_screen_from_the_answers(self):
        self.founding('+++\ncity = "Riverton"\nmap = "Green Valley"\nmap_kind = "custom"\ntheme = "European"\ntraffic = "left"\nmode = "normal"\noptions = ["unlimited money"]\n+++\n')
        code, out = self.run_tool("newgame", self.city / "journal")
        self.assertEqual(code, 0, out)
        self.assertIn("City name: **Riverton**, exactly", out)
        self.assertIn("Theme: **European**", out)
        self.assertIn("Traffic drives on the **left**", out)
        self.assertIn("switch **Left-hand traffic** on", out)
        self.assertIn("Game mode: **Normal** (the default).", out)
        self.assertIn("Switch on **Unlimited money**.", out)
        self.assertIn("**Take a snapshot**", out)                       # the snapshot step is spelled out
        self.assertIn("play as long as you want", out)                  # no road plan asked for: play after founding
        self.founding('+++\ncity = "Riverton"\nmap = "Plains"\nwants = ["backbone", "drafts"]\n+++\n')
        _, planned = self.run_tool("newgame", self.city / "journal")
        self.assertIn("go back to the main menu, and tell the City Manager the city stands", planned)
        self.founding('+++\ncity = "Riverton"\nmap = "Green Valley"\nmap_kind = "custom"\n+++\n')
        code, out = self.run_tool("newgame", self.city / "journal")
        self.assertIn("custom maps show only when their mod is on", out)
        self.assertIn("# Green Valley", out)                           # the custom map's detail follows
        self.assertIn("Save Game", out)


if __name__ == "__main__":
    unittest.main()
