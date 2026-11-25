"""Tests for mods.py, the scan of the Mayor's mods, on a made-up launcher folder: a code mod, a pack in the community's
JSON prefab format, a pack in the official packs' binary format (with a .loc of menu names), a vehicle pack, a mod that
is switched off, and an Extra Assets Importer pack."""
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

HERE = Path(__file__).resolve().parent
MODS = HERE.parent / "skills/city-manager/scripts/mods.py"


def s16(text):
    """A string as the binary prefab format writes it: a 1, the length in characters, then UTF-16."""
    return b"\x01" + len(text).to_bytes(4, "little") + text.encode("utf-16-le")


def binary_prefab(name, lot):
    return (s16("Game.Prefabs.BuildingPrefab, Game") + s16("name") + s16(name) + s16("Game.Prefabs.UIObject, Game")
            + s16("Game.Prefabs.SignatureBuilding, Game") + s16("m_LotWidth") + lot[0].to_bytes(4, "little")
            + s16("m_LotDepth") + lot[1].to_bytes(4, "little")) + s16("m_ConstructionCost") + (250000).to_bytes(4, "little")


def loc(pairs):
    def st(t):
        b = t.encode("utf-8")
        return bytes([len(b)]) + b
    out = b"\x01\x00" + st("English") + st("en-US") + st("English") + len(pairs).to_bytes(4, "little")
    for k, v in pairs.items():
        out += st(k) + st(v)
    return out + b"\x00\x00\x00\x00"


JSON_PARK = {"$id": 0, "$type": "0|Game.Prefabs.BuildingPrefab, Game", "name": "Pocket Park 01", "m_LotWidth": 2, "m_LotDepth": 3,
             "components": {"$rcontent": [{"$type": "1|Game.Prefabs.UIObject, Game"},
                                          {"$type": "2|Game.Prefabs.PlaceableObject, Game", "m_ConstructionCost": 12000},
                                          {"$type": "3|Game.Prefabs.ServiceConsumption, Game", "m_Upkeep": 900},
                                          {"$type": "4|Game.Prefabs.Park, Game"}]}}
JSON_HOUSE = {"$type": "0|Game.Prefabs.BuildingPrefab, Game", "name": "Row House 4", "m_LotWidth": 1, "m_LotDepth": 4,
              "components": {"$rcontent": [{"$type": "1|Game.Prefabs.SpawnableBuilding, Game"}]}}
JSON_BENCH_PART = {"$type": "0|Game.Prefabs.StaticObjectPrefab, Game", "name": "Bench part", "components": {"$rcontent": []}}


class Scan(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cm-mods-"))
        self.addCleanup(lambda: shutil.rmtree(self.base, ignore_errors=True))
        ll = self.base / "LocalLow"
        mods = ll / ".cache/Mods/pdx_mods"
        (mods / "1001_3").mkdir(parents=True)
        (mods / "1001_3/Traffic Helper.dll").write_bytes(b"MZ")
        (mods / "1002_1").mkdir()
        with zipfile.ZipFile(mods / "1002_1/Parks.cok", "w") as z:
            z.writestr("Pocket Park 01.Prefab", json.dumps(JSON_PARK))
            z.writestr("Row House 4.Prefab", json.dumps(JSON_HOUSE))
            z.writestr("Bench part.Prefab", json.dumps(JSON_BENCH_PART))
            z.writestr("Pocket Park 01 Mesh_ab12.Prefab", "{}")
        (mods / "1003_2").mkdir()
        with zipfile.ZipFile(mods / "1003_2/Region.cok", "w") as z:
            z.writestr("FR_Hall.Prefab", binary_prefab("FR_Hall", (4, 3)))
            z.writestr("FR_Hall_en-US.loc", loc({"Assets.NAME[FR_Hall]": "Town Hall of Lyon"}))
        (mods / "1004_1").mkdir()
        with zipfile.ZipFile(mods / "1004_1/Car.cok", "w") as z:
            z.writestr("Car.Prefab", json.dumps({"$type": "0|Game.Prefabs.CarPrefab, Game", "name": "Car", "components": {"$rcontent": []}}))
        (mods / "1006_1/CustomSurfaces/Paving/Cobbles").mkdir(parents=True)
        (mods / "1006_1/CustomSurfaces/Paving/Cobbles/surface.json").write_text("{}")
        (mods / "1006_1/lang").mkdir()
        (mods / "1006_1/lang/en-US.json").write_text(json.dumps({"Assets.NAME[Paving Pack Cobbles Surface]": "Old Cobbles"}))
        (mods / "1006_1/Paving Pack.dll").write_bytes(b"MZ")
        ll.joinpath(".cache/Mods/playset_config.json").write_text(json.dumps({"activePlaysetId": "p1", "playsets": [
            {"id": "p1", "presentation": {"name": "Test set"}, "mods": [
                {"source": "pdx_mods", "sourceId": i, "isEnabled": i != "1005"} for i in ("1001", "1002", "1003", "1004", "1005", "1006")]},
            {"id": "p2", "presentation": {"name": "Other set"}, "mods": [{"source": "pdx_mods", "sourceId": "1001", "isEnabled": True}]}]}))
        con = sqlite3.connect(ll / "launcher-v2.sqlite")
        con.execute("create table mods (pdxId text, displayName text, name text, version text, shortDescriptionPdx text, tags text)")
        for row in (("1001", "Traffic Helper", "x", "3", "Helps traffic.", '["Code Mod"]'), ("1002", "Pocket Parks", "x", "1", "", '["Building"]'),
                    ("1003", "Region Pack", "x", "2", "", '["Building"]'), ("1004", "Car Pack", "x", "1", "", '["Vehicle", "PersonalCar"]'),
                    ("1005", "Switched Off", "x", "1", "", "[]"), ("1006", "Paving Pack", "x", "1", "Surfaces for EAI.", '["Code Mod"]')):
            con.execute("insert into mods values (?,?,?,?,?,?)", row)
        con.commit()
        con.close()
        (ll / "Mods/MyLocal").mkdir(parents=True)
        (ll / "Mods/MyLocal/MyLocal.dll").write_bytes(b"MZ")
        self.city = self.base / "riverton"
        (self.city / "manager").mkdir(parents=True)
        self.env = dict(os.environ, CS2_USERDATA=str(ll), CITY_MANAGER_HOME=str(self.base / "home"))

    def run_mods(self, *args):
        r = subprocess.run([sys.executable, "-I", str(MODS), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                           env=self.env, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def scanned(self):
        return {m["name"]: m for m in json.loads((self.city / "manager/mods.json").read_text(encoding="utf-8"))["mods"]}

    def test_scan_sorts_the_mods_and_lists_what_packs_place(self):
        code, out = self.run_mods("scan", self.city)
        self.assertEqual(code, 0, out)
        m = self.scanned()
        self.assertEqual(m["Traffic Helper"]["kind"], "code mod")
        self.assertEqual(m["Pocket Parks"]["kind"], "asset pack")
        park = m["Pocket Parks"]["assets"]
        self.assertEqual(park, [{"name": "Pocket Park 01", "kind": "building", "lot": [2, 3], "cost": 12000, "upkeep": 900, "is": ["Park"]}],
                         "a building's own part and a mesh aren't listed; a growable is counted, not listed")
        self.assertEqual(m["Pocket Parks"]["grows"], 1)
        hall = m["Region Pack"]["assets"][0]
        self.assertEqual((hall["name"], hall.get("title"), hall["lot"], hall["is"], hall["cost"]),
                         ("FR_Hall", "Town Hall of Lyon", [4, 3], ["signature"], 250000), "the binary format and the .loc names")
        self.assertEqual(m["Car Pack"]["kind"], "vehicle pack")
        self.assertNotIn("Switched Off", m)
        self.assertEqual(m["Paving Pack"]["kind"], "assets (Extra Assets Importer)")
        self.assertEqual(m["Paving Pack"]["assets"], [{"name": "Old Cobbles", "kind": "surface"}])
        self.assertEqual(m["MyLocal"]["kind"], "local code mod")
        md = (self.city / "manager/mods.md").read_text(encoding="utf-8")
        self.assertIn("# Mods in the playset 'Test set'", md)
        self.assertIn("Town Hall of Lyon", md)
        self.assertIn("## Vehicle packs: 1", md)

    def test_a_second_scan_comes_from_the_cache(self):
        self.run_mods("scan", self.city)
        cache = list((self.base / "home/mods-cache").glob("*.json"))
        self.assertTrue(cache)
        before = {c.name: c.stat().st_mtime_ns for c in cache}
        self.run_mods("scan", self.city)
        self.assertEqual(before, {c.name: c.stat().st_mtime_ns for c in (self.base / "home/mods-cache").glob("*.json")})

    def test_find_by_words_kind_lot_and_service(self):
        self.run_mods("scan", self.city)
        code, out = self.run_mods("find", "lyon", "--city", self.city)
        self.assertIn("| Town Hall of Lyon (FR_Hall) | building | 4×3 | $250,000 |", out)
        code, out = self.run_mods("find", "park", "--city", self.city, "--kind", "building", "--lot", "3x2")
        self.assertIn("Pocket Park 01", out)
        code, out = self.run_mods("find", "--city", self.city, "--lot", "2x2")
        self.assertIn("# 0 assets", out)
        code, out = self.run_mods("find", "--city", self.city, "--service")
        self.assertIn("Pocket Park 01", out)
        self.assertNotIn("Town Hall of Lyon", out, "a signature alone isn't a service")
        code, out = self.run_mods("find", "x", "--city", self.base / "nowhere")
        self.assertNotEqual(code, 0)

    def test_another_playset_by_name(self):
        code, out = self.run_mods("scan", self.city, "--playset", "Other set")
        self.assertEqual(set(self.scanned()), {"Traffic Helper", "MyLocal"})


if __name__ == "__main__":
    unittest.main()
