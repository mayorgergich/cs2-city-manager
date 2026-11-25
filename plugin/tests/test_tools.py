"""Offline tests for the manager's tools (journal.py, gather.py). Run: python3 -m unittest discover -s tests -p 'test_*.py'

Every test works in a throwaway folder: CITY_MANAGER_ROOT points journal.py at a fake ModsData/CityManager, and
CS2_USERDATA points gather.py at a fake game user-data folder holding a fake save. Nothing touches the real game.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "plugin/skills/city-manager/scripts"
JOURNAL = SCRIPTS / "journal.py"


def png(path, w=40, h=20, colour=(200, 0, 0)):
    from PIL import Image
    Image.new("RGB", (w, h), colour).save(path)


class Env:
    """A fake game user-data folder with a journal source next to it."""

    def __init__(self):
        self.base = Path(tempfile.mkdtemp(prefix="cj-tools-"))
        self.userdata = self.base / "LocalLow"
        self.root = self.userdata / "ModsData/CityManager"
        self.root.mkdir(parents=True)
        self.src = self.base / "src"
        for d in ("projects", "reports", "briefings", "images"):
            (self.src / d).mkdir(parents=True)
        self.write("journal.toml", 'id = "testcity"\ncity = "Testville"\naliases = ["Old Name"]\nmanager = "Tester"\n')
        self.write("projects/roads.md", """+++
id = "roads"
title = "Roads"
scale = "city"
status = "active"
priority = 1
where = { label = "Gate", x = 10, z = -20, zoom = 500 }

[[plans]]
kind = "draft"
name = "Town-guide-A2"

[[steps]]
id = "lights"
text = "Take the lights off"

[[steps]]
id = "gate"
text = "Build the gate"
done = true
+++
First paragraph is the summary.

![The map](map.png)
""")
        self.write("projects/later.md", '+++\nid = "later"\ntitle = "Later"\nstatus = "hold"\n\n[[steps]]\nid = "a"\ntext = "Someday"\n+++\n')
        self.write("briefing.md", """+++
id = "2026-11-24"
title = "Tonight"
date = "24 Nov"

[[tasks]]
id = "lights"
text = "Lights off"
project = "roads"
+++
Body.
""")
        png(self.src / "images/map.png")

    def write(self, rel, text):
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run(self, tool, *args, env=None):
        e = dict(os.environ, CITY_MANAGER_ROOT=str(self.root), CS2_USERDATA=str(self.userdata))
        e.update(env or {})
        r = subprocess.run([sys.executable, "-I", str(tool), *map(str, args)], capture_output=True, text=True, encoding="utf-8", env=e, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def jp(self, *args):
        return self.run(JOURNAL, *args)

    def journal(self):
        return json.loads((self.root / "testcity/journal.json").read_text(encoding="utf-8"))

    def mayor(self, data):
        (self.root / "testcity/mayor.json").write_text(json.dumps(data), encoding="utf-8")

    def close(self):
        shutil.rmtree(self.base, ignore_errors=True)


class JournalBuild(unittest.TestCase):
    def setUp(self):
        self.e = Env()

    def tearDown(self):
        self.e.close()

    def test_build_writes_the_journal_aliases_and_hashed_pictures(self):
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        j = self.e.journal()
        self.assertEqual([p["id"] for p in j["projects"]], ["later", "roads"])
        roads = next(p for p in j["projects"] if p["id"] == "roads")
        self.assertEqual(roads["summary"], "First paragraph is the summary.")
        self.assertRegex(roads["body"], r"!\[The map\]\(map\.[0-9a-f]{8}\.png\)")
        pics = list((self.e.root / "testcity/images").glob("*.png"))
        self.assertEqual(len(pics), 1)
        self.assertEqual(j["images"][pics[0].name], [40, 20])
        aliases = json.loads((self.e.root / "cities.json").read_text(encoding="utf-8"))["aliases"]
        self.assertEqual(aliases, {"Testville": "testcity", "Old Name": "testcity"})

    def test_a_second_build_without_changes_leaves_the_file_alone(self):
        self.e.jp("build", self.e.src)
        before = (self.e.root / "testcity/journal.json").stat().st_mtime_ns
        code, out = self.e.jp("build", self.e.src)
        self.assertIn("Unchanged", out)
        self.assertEqual(before, (self.e.root / "testcity/journal.json").stat().st_mtime_ns)

    def test_a_changed_picture_gets_a_new_name_and_the_old_one_is_removed(self):
        self.e.jp("build", self.e.src)
        old = {p.name for p in (self.e.root / "testcity/images").glob("*.png")}
        png(self.e.src / "images/map.png", colour=(0, 0, 255))
        self.e.jp("build", self.e.src)
        new = {p.name for p in (self.e.root / "testcity/images").glob("*.png")}
        self.assertEqual(len(new), 1)
        self.assertNotEqual(old, new)

    def test_wide_pictures_are_scaled_down(self):
        png(self.e.src / "images/map.png", w=3200, h=1000)
        self.e.jp("build", self.e.src)
        self.assertEqual(list(self.e.journal()["images"].values()), [[1600, 500]])

    def test_change_stamps_follow_only_real_changes(self):
        self.e.jp("build", self.e.src)
        roads = lambda: next(p for p in self.e.journal()["projects"] if p["id"] == "roads")
        self.assertEqual([s["changed"] for s in roads()["steps"]], ["", ""])
        self.assertEqual(roads()["statusChanged"], "")
        p = self.e.src / "projects/roads.md"
        p.write_text(p.read_text(encoding="utf-8").replace('text = "Take the lights off"', 'text = "Take the lights off"\ndone = true').replace('status = "active"', 'status = "next"'), encoding="utf-8")
        self.e.jp("build", self.e.src)
        lights, gate = roads()["steps"]
        self.assertRegex(lights["changed"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(gate["changed"], "")
        self.assertRegex(roads()["statusChanged"], r"^\d{4}-")

    def test_problems_stop_the_build_and_are_listed(self):
        cases = {
            "projects/dup.md": '+++\nid = "roads"\ntitle = "Dup"\n+++\n',
            "projects/bad.md": '+++\nid = "bad"\nstatus = "finished"\nscale = "planet"\nwhere = { x = "far" }\n+++\n',
            "projects/steps.md": '+++\nid = "steps"\ntitle = "S"\n[[steps]]\nid = "a"\ntext = "x"\n[[steps]]\nid = "a"\n+++\n',
            "briefing.md": '+++\nid = "b"\n[[tasks]]\nid = "t"\ntext = "x"\nproject = "nope"\n+++\n',
            "reports/r.md": '+++\nid = "2026-11-24"\n[[replies]]\nnote = "not-an-id"\ntext = "hi"\n+++\n![x](../../etc/passwd.png)\n![y](photo.jpg)\n',
        }
        for rel, text in cases.items():
            self.e.write(rel, text)
        from PIL import Image
        Image.new("RGB", (4, 4)).save(self.e.src / "images/photo.jpg")
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1)
        self.assertIn("Not written", out)
        for expected in ("duplicate project id roads", "status 'finished'", "scale 'planet'", "where needs numbers",
                         "needs a title", "duplicate step id a", "step a has no text", "unknown project 'nope'",
                         "a reply needs note", "picture ../../etc/passwd.png: use a .png", "picture photo.jpg: use a .png"):
            self.assertIn(expected, out)
        self.assertFalse((self.e.root / "testcity/journal.json").exists())

    def test_picture_names_the_mod_would_refuse_are_problems(self):
        for name in ("map+v2.png", "kärtchen.png", "plan@2x.png", "-dash.png", "x" * 101 + ".png"):
            shutil.copy(self.e.src / "images/map.png", self.e.src / "images" / name)
        body = "".join(f"![p]({n})\n\n" for n in ("map+v2.png", "kärtchen.png", "plan@2x.png", "-dash.png", "x" * 101 + ".png"))
        self.e.write("projects/later.md", '+++\nid = "later"\ntitle = "L"\n+++\n' + body)
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1)
        self.assertEqual(out.count("use a .png named with letters"), 5, out)

    def test_published_picture_names_pass_the_mods_own_filter(self):
        import re
        js = re.search(r"const PICTURE_NAME = /(.+)/;", (REPO / "mod/ui/CityManager.mjs").read_text(encoding="utf-8")).group(1)
        cs = re.search(r'PictureName = new Regex\(@"(.+?)"\)', (REPO / "mod/src/CityManager/JournalStore.cs").read_text(encoding="utf-8")).group(1)
        self.assertEqual(js, cs)
        shutil.copy(self.e.src / "images/map.png", self.e.src / "images/Map_v2.final.PNG")
        name = "A" + "b" * 99 + ".png"
        shutil.copy(self.e.src / "images/map.png", self.e.src / "images" / name)
        self.e.write("projects/later.md", f'+++\nid = "later"\ntitle = "L"\n+++\n![a](Map_v2.final.PNG)\n\n![b]({name})\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        published = list(self.e.journal()["images"])
        self.assertEqual(len(published), 3)
        for pub in published:
            self.assertRegex(pub, js)

    def test_change_stamps_survive_a_lost_or_damaged_journal_json(self):
        roads = lambda: next(p for p in self.e.journal()["projects"] if p["id"] == "roads")
        self.e.jp("build", self.e.src)
        p = self.e.src / "projects/roads.md"
        p.write_text(p.read_text(encoding="utf-8").replace('text = "Take the lights off"', 'text = "Take the lights off"\ndone = true'), encoding="utf-8")
        self.e.jp("build", self.e.src)
        stamp = roads()["steps"][0]["changed"]
        self.assertRegex(stamp, r"Z$")
        out_path = self.e.root / "testcity/journal.json"
        for damage in (lambda: out_path.write_text("{ damaged", encoding="utf-8"), out_path.unlink):
            damage()
            code, out = self.e.jp("build", self.e.src)
            self.assertEqual(code, 0, out)
            self.assertEqual(roads()["steps"][0]["changed"], stamp)
        (self.e.src / ".stamps.json").unlink()   # an older tool's source: the stamps come from journal.json
        self.e.jp("build", self.e.src)
        self.assertEqual(roads()["steps"][0]["changed"], stamp)
        self.assertTrue((self.e.src / ".stamps.json").exists())

    def test_touching_a_page_without_changing_it_publishes_nothing(self):
        self.e.jp("build", self.e.src)
        later = time.time() + 120
        os.utime(self.e.src / "projects/roads.md", (later, later))
        code, out = self.e.jp("build", self.e.src)
        self.assertIn("Unchanged", out)
        p = self.e.src / "projects/roads.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nOne more line.\n", encoding="utf-8")
        code, out = self.e.jp("build", self.e.src)
        self.assertIn("Wrote", out)

    def test_flags_go_anywhere_and_unknown_ones_are_refused(self):
        self.e.jp("build", self.e.src)
        code, out = self.e.jp("mayor", "--all", self.e.src)
        self.assertEqual(code, 0, out)
        code, _ = self.e.jp("build", self.e.src, "--force")
        self.assertEqual(code, 2)
        code, _ = self.e.jp("build")
        self.assertEqual(code, 2)

    def test_a_journal_id_that_is_a_path_is_refused(self):
        for bad in ("../escape", "a/b", "Upper", "", "x" * 70):
            self.e.write("journal.toml", f'id = "{bad}"\ncity = "T"\n')
            code, out = self.e.jp("build", self.e.src)
            self.assertEqual(code, 1, bad)
        self.assertFalse((self.e.base / "LocalLow/ModsData/escape").exists())
        self.assertEqual(list(self.e.root.iterdir()), [])

    def test_bad_front_matter_is_reported_not_crashed_on(self):
        self.e.write("projects/x.md", "no front matter at all\n")
        self.e.write("projects/y.md", "+++\nid = \n+++\n")
        self.e.write("projects/z.md", "+++\nid = \"z\"\n")
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1)
        for expected in ("must start with a +++", "front matter:", "no closing +++"):
            self.assertIn(expected, out)

    def test_replies_and_report_order(self):
        self.e.write("reports/2026-11-09.md", '+++\nid = "2026-11-09"\ntitle = "Nine"\ndate = "9 Nov"\n+++\n')
        self.e.write("reports/2026-11-10.md", '+++\nid = "2026-11-10"\ntitle = "Ten"\ndate = "10 Nov"\n[[replies]]\nnote = "n20261110193500-1"\ntext = "Done, see Roads."\n+++\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        j = self.e.journal()
        self.assertEqual([r["id"] for r in j["reports"]], ["2026-11-10", "2026-11-09"])
        self.assertEqual(j["replies"]["n20261110193500-1"], {"text": "Done, see Roads.", "date": "10 Nov", "report": "2026-11-10"})

    def test_stale_planner_guides_are_warned_about(self):
        exports = self.e.userdata / "ModsData/CityPlanningDraft/Exports"
        exports.mkdir(parents=True)
        for n in ("Town-guide-A2", "Town-guide-A10", "Other-guide-A1"):
            (exports / f"{n}.cityplan.json").write_text("{}", encoding="utf-8")
        self.e.write("briefing.md", '+++\nid = "2026-11-25"\n[[tasks]]\nid = "t"\ntext = "Import **Town-guide-A10** (not Town-guide-A9)"\n+++\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        self.assertIn("project roads plan: mentions Town-guide-A2, but Town-guide-A10 is the newest export", out)
        self.assertIn("briefing task t: mentions Town-guide-A9", out)
        self.assertNotIn("mentions Town-guide-A10", out)

    def test_moved_guides_and_layers_a_guide_lacks_are_warned_about(self):
        exports = self.e.userdata / "ModsData/CityPlanningDraft/Exports"
        (exports / "old").mkdir(parents=True)
        (exports / "old/Town-guide-A2.cityplan.json").write_text("{}", encoding="utf-8")
        (exports / "Testville 3.cityplan.json").write_text(json.dumps({"plans": [{"name": "Now · Lights"}, {"name": "Base · Roads"}]}), encoding="utf-8")
        p = self.e.src / "projects/roads.md"
        p.write_text(p.read_text(encoding="utf-8").replace('name = "Town-guide-A2"', 'name = "Testville 3"\nlayers = ["Now · Lights", "R Road fixes"]'), encoding="utf-8")
        self.e.write("briefing.md", '+++\nid = "2026-11-25"\n[[tasks]]\nid = "t"\ntext = "Import latest (Testville 3), not Testville 2 or Town-guide-A2"\n+++\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        self.assertIn("briefing task t: mentions Testville 2, but Testville 3 is the newest export", out)
        self.assertIn("briefing task t: mentions Town-guide-A2, which was moved to Exports/old", out)
        self.assertIn("project roads plan: layer 'R Road fixes' isn't in Testville 3", out)
        self.assertNotIn("'Now · Lights'", out)
        self.assertNotIn("mentions Testville 3", out)


class JournalRules(unittest.TestCase):
    """Rules added after the 2026-11-24 code and security reviews."""

    def setUp(self):
        self.e = Env()

    def tearDown(self):
        self.e.close()

    def roads(self):
        return next(p for p in self.e.journal()["projects"] if p["id"] == "roads")

    def test_force_lets_the_manager_overrule_the_mayor_without_changing_the_value(self):
        self.e.jp("build", self.e.src)
        self.assertEqual(self.roads()["steps"][0]["changed"], "")
        p = self.e.src / "projects/roads.md"
        p.write_text(p.read_text(encoding="utf-8").replace('text = "Take the lights off"', 'text = "Take the lights off"\nforce = true').replace('priority = 1', 'priority = 1\nforce_status = true'), encoding="utf-8")
        code, out = self.e.jp("build", self.e.src)
        self.assertIn("has force set", out)
        self.assertRegex(self.roads()["steps"][0]["changed"], r"Z$")
        self.assertRegex(self.roads()["statusChanged"], r"Z$")

    def test_archived_briefings_keep_their_change_stamps(self):
        self.e.write("briefing.md", '+++\nid = "2026-11-24"\n[[tasks]]\nid = "t"\ntext = "x"\n+++\n')
        self.e.jp("build", self.e.src)
        self.e.write("briefing.md", '+++\nid = "2026-11-24"\n[[tasks]]\nid = "t"\ntext = "x"\ndone = true\n+++\n')
        self.e.jp("build", self.e.src)
        stamp = self.e.journal()["briefing"]["tasks"][0]["changed"]
        self.assertRegex(stamp, r"Z$")
        self.e.jp("archive", self.e.src)
        self.e.write("briefing.md", '+++\nid = "2026-11-25"\n+++\n')
        self.e.jp("build", self.e.src)
        self.assertEqual(self.e.journal()["briefings"][0]["tasks"][0]["changed"], stamp)

    def test_ids_are_required_dated_and_unique(self):
        self.e.write("projects/x.md", '+++\nid = "x"\ntitle = "X"\n[[steps]]\ntext = "no id"\n+++\n')
        self.e.write("briefings/2026-11-24.md", '+++\nid = "2026-11-24"\n+++\n')
        self.e.write("reports/a.md", '+++\nid = "tonight"\n+++\n')
        self.e.write("reports/b.md", '+++\nid = "2026-11-20"\n+++\n')
        self.e.write("reports/c.md", '+++\nid = "2026-11-20"\n+++\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1)
        for expected in ("every step needs an id", "id 2026-11-24 is used by briefing.md too",
                         "id 'tonight' must be a date", "id 2026-11-20 is used by reports/b.md too"):
            self.assertIn(expected, out)

    def test_aliases_are_written_even_when_nothing_else_changed_and_never_taken_over(self):
        self.e.jp("build", self.e.src)
        (self.e.root / "cities.json").write_text(json.dumps({"aliases": {"Old Name": "testcity", "Taken": "other", "Testville": "testcity"}}), encoding="utf-8")
        self.e.write("journal.toml", 'id = "testcity"\ncity = "Testville"\naliases = ["Renamed", "Taken"]\nmanager = "Tester"\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertIn("Unchanged", out)
        self.assertIn("'Taken' already opens journal 'other'", out)
        aliases = json.loads((self.e.root / "cities.json").read_text(encoding="utf-8"))["aliases"]
        self.assertEqual(aliases, {"Taken": "other", "Testville": "testcity", "Renamed": "testcity"})

    def test_pictures_must_stand_on_their_own_line(self):
        self.e.write("projects/later.md", '+++\nid = "later"\ntitle = "L"\n+++\nsee ![map](map.png) here\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1)
        self.assertIn("must be on a line of its own", out)

    def test_a_postscript_file_named_png_is_refused_not_rendered(self):
        (self.e.src / "images/map.png").write_text("%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n{} loop\n", encoding="utf-8")
        t0 = time.time()
        code, out = self.e.jp("build", self.e.src)
        self.assertLess(time.time() - t0, 30)
        self.assertEqual(code, 1)
        self.assertIn("can't be read as PNG", out)

    def test_tall_pictures_are_capped_too(self):
        png(self.e.src / "images/map.png", w=800, h=8000)
        self.e.jp("build", self.e.src)
        self.assertEqual(list(self.e.journal()["images"].values()), [[320, 3200]])

    def test_picture_matching_stays_linear(self):
        self.e.write("projects/later.md", '+++\nid = "later"\ntitle = "L"\n+++\n' + "![" * 200000 + "\n")
        t0 = time.time()
        self.e.jp("build", self.e.src)
        self.assertLess(time.time() - t0, 20)

    def test_wrong_value_types_are_problems_not_crashes(self):
        self.e.write("projects/x.md", '+++\nid = "x"\ntitle = ["not", "text"]\npriority = "high"\nsteps = "none"\n+++\n')
        self.e.write("projects/y.md", '+++\nid = "y"\ntitle = "Y"\n[[steps]]\nid = "s"\ntext = "t"\ndone = "yes"\n+++\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", out)
        for expected in ("title should be text", "priority should be a number", "steps should be a list", "done should be true or false"):
            self.assertIn(expected, out)

    def test_a_journal_json_held_open_briefly_is_still_replaced(self):
        # Windows won't replace a file another program is reading (the game reads journal.json whenever it changes), so
        # the write is retried for about two seconds. Here a reader holds it for half a second.
        self.e.jp("build", self.e.src)
        p = self.e.src / "projects/roads.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nMore to come.\n", encoding="utf-8")
        out_path = self.e.root / "testcity/journal.json"
        reader = open(out_path, encoding="utf-8")
        threading.Timer(0.5, reader.close).start()
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        self.assertIn("More to come.", out_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "only Windows refuses to replace a file another program has open")
    def test_a_journal_json_held_open_for_good_is_reported_not_a_crash(self):
        self.e.jp("build", self.e.src)
        p = self.e.src / "projects/roads.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nMore to come.\n", encoding="utf-8")
        with open(self.e.root / "testcity/journal.json", encoding="utf-8"):
            code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1, out)
        self.assertIn("journal.json is in use by another program", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(list((self.e.root / "testcity").glob("*.writing")), [])

    def test_a_page_saved_in_the_old_windows_encoding_is_a_problem_not_a_crash(self):
        (self.e.src / "projects/later.md").write_bytes('+++\nid = "later"\ntitle = "Now · Later"\n+++\nCafé\n'.encode("cp1252"))
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 1, out)
        self.assertIn("later.md: isn't saved as UTF-8 text", out)
        self.assertNotIn("Traceback", out)

    def test_a_bom_and_empty_front_matter_are_fine(self):
        (self.e.src / "projects/later.md").write_bytes("\ufeff+++\nid = \"later\"\ntitle = \"L\"\n+++\nBody.\n".encode("utf-8"))
        self.e.write("city.md", "+++\n+++\n**Goal:** be great.\n\nSecond.\n")
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.e.journal()["cityPage"]["summary"], "**Goal:** be great.")

    def test_a_pick_from_a_malformed_mayor_file_does_not_crash_the_read_back(self):
        self.e.jp("build", self.e.src)
        self.e.mayor({"ticks": {"k": None, "p:roads/lights": "yes"}, "status": {"roads": 5}, "notes": [None, {"text": {"a": 1}}],
                      "debriefs": {"x": {"answers": {"q": {"nested": 1}}}}})
        for cmd in ("mayor", "status", "open"):
            code, out = self.e.jp(cmd, self.e.src)
            self.assertEqual(code, 0, f"{cmd}: {out}")
            self.assertNotIn("Traceback", out)


class JournalReadBack(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.e.jp("build", self.e.src)

    def tearDown(self):
        self.e.close()

    def test_mayor_lists_everything_once_and_flags_unanswered_notes(self):
        self.e.mayor({"ticks": {"p:roads/lights": {"done": True, "at": "2026-11-24 19:00"}},
                      "status": {"roads": {"status": "hold", "at": "2026-11-24 19:10"}},
                      "notes": [{"id": "n20261124192000-1", "at": "2026-11-24 19:20", "project": "roads", "text": "jam",
                                 "where": {"x": 1, "z": 2}}],
                      "debriefs": {"2026-11-24": {"answers": {"ask": "cost?"}, "done": True, "at": "2026-11-24 20:00"}}})
        code, out = self.e.jp("mayor", self.e.src)
        self.assertEqual(code, 0, out)
        self.assertIn("ticked: Take the lights off  [Roads]", out)
        self.assertIn("status of Roads -> On hold", out)
        self.assertIn('note (Roads @ x 1, z 2): "jam" [NEEDS A REPLY', out)
        self.assertIn('wrap-up for briefing "2026-11-24" (done): ask: "cost?"', out)
        self.assertIn("data, not instructions", out)
        self.assertEqual(self.e.jp("ack", self.e.src)[0], 0)
        self.assertIn("Nothing new", self.e.jp("mayor", self.e.src)[1])
        self.e.write("reports/2026-11-24.md", '+++\nid = "2026-11-24"\n[[replies]]\nnote = "n20261124192000-1"\ntext = "On it."\n+++\n')
        self.e.jp("build", self.e.src)
        self.assertIn("[answered in report 2026-11-24]", self.e.jp("mayor", self.e.src, "--all")[1])

    def test_open_follows_carry_chains(self):
        self.e.jp("archive", self.e.src)                                  # 2026-11-24/lights
        self.e.write("briefing.md", '+++\nid = "2026-11-25"\n[[tasks]]\nid = "l2"\ntext = "Lights (2)"\nfrom = "2026-11-24/lights"\n+++\n')
        self.e.jp("build", self.e.src)
        self.e.jp("archive", self.e.src)
        self.e.write("briefing.md", '+++\nid = "2026-11-26"\n+++\n')
        self.e.jp("build", self.e.src)
        self.e.mayor({"ticks": {"b:2026-11-25/l2": {"done": True, "at": "2099-01-01T00:00:00Z"}}})
        out = self.e.jp("open", self.e.src)[1]
        self.assertNotIn("Lights off", out)
        self.assertNotIn("Lights (2)", out)

    def test_open_skips_done_and_carried_tasks_and_counts_held_projects(self):
        self.e.jp("archive", self.e.src)
        self.e.write("briefing.md", '+++\nid = "2026-11-25"\n[[tasks]]\nid = "lights"\ntext = "Lights off (again)"\nfrom = "2026-11-24/lights"\n+++\n')
        code, out = self.e.jp("build", self.e.src)
        self.assertEqual(code, 0, out)
        out = self.e.jp("open", self.e.src)[1]
        self.assertIn("Lights off (again)", out)
        self.assertNotIn("earlier briefing", out)
        self.assertIn("Later (On hold): 1 steps waiting", out)
        self.assertNotIn("Build the gate", out)

    def test_a_from_link_to_nothing_is_warned_about(self):
        self.e.write("briefing.md", '+++\nid = "2026-11-25"\n[[tasks]]\nid = "x"\ntext = "x"\nfrom = "1999-01-01/x"\n+++\n')
        self.assertIn("which is no earlier briefing's task", self.e.jp("build", self.e.src)[1])

    def test_archive_refuses_a_repeated_id_and_bad_ids(self):
        self.assertEqual(self.e.jp("archive", self.e.src)[0], 0)
        self.e.write("briefing.md", '+++\nid = "2026-11-24"\ntitle = "Second session"\n+++\n')
        code, out = self.e.jp("archive", self.e.src)
        self.assertEqual(code, 1)
        self.assertIn("Give briefing.md its own id", out)
        self.e.write("briefing.md", '+++\nid = "../../escape"\n+++\n')
        self.assertEqual(self.e.jp("archive", self.e.src)[0], 1)
        self.e.write("briefing.md", '+++\nid = "2026-11-24-2"\n+++\n')
        self.assertEqual(self.e.jp("archive", self.e.src)[0], 0)
        self.assertEqual(sorted(p.name for p in (self.e.src / "briefings").glob("*.md")), ["2026-11-24-2.md", "2026-11-24.md"])
        self.assertFalse((self.e.base / "escape.md").exists())
        self.assertIn("No briefing.md", self.e.jp("archive", self.e.src)[1])

    def test_read_back_survives_a_missing_mayor_file(self):
        for cmd in ("mayor", "status", "open"):
            code, out = self.e.jp(cmd, self.e.src)
            self.assertEqual(code, 0, f"{cmd}: {out}")


class MergeRule(unittest.TestCase):
    """journal.py reads the Mayor's side back with the same rule as the panel: both run format/merge_cases.json."""

    def test_the_shared_cases(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            import journal
        finally:
            sys.path.remove(str(SCRIPTS))
        cases = json.loads((REPO / "format/merge_cases.json").read_text(encoding="utf-8"))
        for c in cases["ticks"]:
            self.assertEqual(journal.mayor_done({"k": c["tick"]}, "k", c["item"]), c["done"], c["why"])
        for c in cases["status"]:
            self.assertEqual(journal.mayor_status({c["project"]["id"]: c["mine"]}, c["project"]), (c["status"], c["byMayor"]), c["why"])


class Where(unittest.TestCase):
    """journal.py where: the folders the skill works with, the same on Windows and Linux."""

    def test_lists_the_folders_for_the_active_city(self):
        e = Env()
        try:
            home = e.base / "manager-home"
            home.mkdir()
            (home / "cities.toml").write_text('active = "testville"\n[cities.testville]\nname = "Testville"\ndir = "%s"\n' % (e.base / "testville").as_posix(), encoding="utf-8")
            code, out = e.run(JOURNAL, "where", env={"CITY_MANAGER_HOME": str(home)})
            self.assertEqual(code, 0, out)
            self.assertIn(f"city      Testville: {e.base / 'testville'}", out)
            self.assertIn(f"source    {e.base / 'testville' / 'journal'}", out)
            self.assertIn(f"journals  {e.root}", out)
            self.assertIn("CityPlanningDraft", out)
            code, out = e.run(JOURNAL, "where", "nowhere", env={"CITY_MANAGER_HOME": str(home)})
            self.assertIn("'nowhere' is not in cities.toml", out)
            code, out = e.run(JOURNAL, "where", env={"CITY_MANAGER_HOME": str(e.base / "empty")})
            self.assertIn("none yet", out)
        finally:
            e.close()


class FirstRun(unittest.TestCase):
    """journal.py doctor and init: a new player's first steps, the same on Windows and Linux."""

    def setUp(self):
        self.e = Env()
        self.home = self.e.base / "manager-home"
        self.env = {"CITY_MANAGER_HOME": str(self.home)}

    def tearDown(self):
        self.e.close()

    def jp(self, *args):
        return self.e.run(JOURNAL, *args, env=self.env)

    def cities(self):
        import tomllib
        return tomllib.loads((self.home / "cities.toml").read_text(encoding="utf-8"))

    def test_doctor_says_what_is_missing_then_what_is_there(self):
        code, out = self.jp("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("--  The City Manager mod isn't installed", out)
        self.assertIn("--  City Planning Draft (the build overlay): not found", out)
        self.assertIn("Cities set up", out)
        self.assertIn('journal.py init "<city name>"', out)
        (self.e.userdata / "Mods/CityManager").mkdir(parents=True)
        (self.e.userdata / "Mods/CityManager/CityManager.dll").write_bytes(b"")
        (self.e.userdata / "Mods/CityManager/BUILD.txt").write_text("City Manager 0.8.0 (build abc)\n", encoding="utf-8")
        (self.e.userdata / ".cache/Mods/pdx_mods/155935_4").mkdir(parents=True)
        (self.e.root / "riverton").mkdir()
        (self.e.root / "riverton/journal.json").write_text('{"format": 1, "city": "Riverton"}', encoding="utf-8")
        (self.e.root / "riverton/city.json").write_text("{}", encoding="utf-8")
        code, out = self.jp("doctor")
        self.assertIn("ok  The City Manager mod: City Manager 0.8.0 (build abc)", out)
        self.assertIn("ok  City Planning Draft (the build overlay): found", out)
        self.assertIn("riverton: snapshot", out)
        self.assertIn("can be adopted: riverton", out)

    def test_init_sets_a_city_up_in_one_go(self):
        code, out = self.jp("init", "Riverton")
        self.assertEqual(code, 0, out)
        city = self.home / "riverton"
        for rel in ("journal/journal.toml", "journal/briefing.md", "journal/city.md", "manager/manager.toml", "manager/dossier.md"):
            self.assertTrue((city / rel).exists(), rel)
        c = self.cities()
        self.assertEqual(c["active"], "riverton")
        self.assertEqual(c["cities"]["riverton"]["name"], "Riverton")
        j = json.loads((self.e.root / "riverton/journal.json").read_text(encoding="utf-8"))
        self.assertEqual(j["city"], "Riverton")
        self.assertEqual(j["briefing"]["title"], "Welcome, Mayor")
        self.assertEqual([t["id"] for t in j["briefing"]["tasks"]], ["snapshot", "note", "window", "wrapup"])
        self.assertEqual(json.loads((self.e.root / "cities.json").read_text(encoding="utf-8"))["aliases"]["Riverton"], "riverton")
        code, out = self.e.run(JOURNAL, "where", env=self.env)
        self.assertIn(f"source    {city / 'journal'}", out)
        code, out = self.jp("status", city / "journal")   # the usual tools work on it straight away
        self.assertEqual(code, 0, out)

    def test_a_second_city_and_a_name_with_accents(self):
        self.jp("init", "Riverton")
        code, out = self.jp("init", 'São "Paulo"', "--folder", self.e.base / "other place" / "sp")
        self.assertEqual(code, 0, out)
        c = self.cities()
        self.assertEqual(c["active"], "riverton")                      # the first city stays active
        self.assertEqual(c["cities"]["sao-paulo"]["name"], 'São "Paulo"')
        self.assertTrue((self.e.base / "other place/sp/journal/journal.toml").exists())
        aliases = json.loads((self.e.root / "cities.json").read_text(encoding="utf-8"))["aliases"]
        self.assertEqual(aliases['São "Paulo"'], "sao-paulo")           # the mod finds it by the city's real name

    def test_founding_sets_a_city_up_before_it_exists(self):
        self.jp("init", "Riverton")
        code, out = self.jp("init", "Little Harbour", "--founding")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.cities()["active"], "little-harbour")      # the new city, quietly
        j = json.loads((self.e.root / "little-harbour/journal.json").read_text(encoding="utf-8"))
        self.assertEqual(j["briefing"]["title"], "Founding day")
        self.assertIn("Little Harbour stands", j["briefing"]["summary"])
        self.assertEqual([t["id"] for t in j["briefing"]["tasks"]], ["pause", "save", "look", "window"])
        self.assertNotIn("Claude the city", json.dumps(j))                # nothing in it waits for Claude
        self.assertIn("starts a New Game named exactly 'Little Harbour'", out)
        code, out = self.jp("init", "--founding")
        self.assertEqual(code, 2)
        self.assertIn("needs the new city's name", out)

    def test_cities_lists_the_ones_set_up_and_journals_started_in_game(self):
        code, out = self.jp("cities")
        self.assertIn("No city has a City Manager journal yet", out)
        self.jp("init", "Riverton")
        (self.e.root / "other-town").mkdir(parents=True)
        (self.e.root / "other-town/journal.json").write_text('{"format": 1, "city": "Other Town"}', encoding="utf-8")
        (self.e.root / "other-town/city-start.json").write_text("{}", encoding="utf-8")
        code, out = self.jp("cities")
        self.assertEqual(code, 0, out)
        self.assertIn("- Riverton: set up (riverton, active); no snapshot yet", out)
        self.assertIn("- Other Town: started in game, not set up yet; snapshot", out)
        self.assertIn('journal.py init "Other Town" --active', out)
        code, out = self.jp("cities", "--json")
        rows = json.loads(out)
        self.assertEqual([(r["name"], r["setUp"]) for r in rows], [("Riverton", True), ("Other Town", False)])

    def test_doctor_says_whether_uv_is_needed(self):
        code, out = self.jp("doctor")
        self.assertIn("uv: ", out)
        self.assertIn("Map pictures for the founding chat", out)

    def test_a_new_city_can_become_the_active_one(self):
        self.jp("init", "Riverton")
        code, out = self.jp("init", "Newport", "--active")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.cities()["active"], "newport")
        self.assertIn("(active: newport)", out)
        self.assertEqual(self.cities()["cities"]["riverton"]["name"], "Riverton")   # the other city is kept
        code, out = self.jp("activate", "riverton")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.cities()["active"], "riverton")
        code, out = self.jp("activate", "nowhere")
        self.assertEqual(code, 1)
        self.assertIn("not in", out)

    def test_init_adopts_a_journal_started_in_game_and_keeps_the_mayors_notes(self):
        (self.e.root / "riverton").mkdir()
        (self.e.root / "riverton/journal.json").write_text('{"format": 1, "city": "Riverton"}', encoding="utf-8")
        (self.e.root / "riverton/mayor.json").write_text('{"format": 1, "notes": [{"id": "n1", "text": "keep me"}]}', encoding="utf-8")
        code, out = self.jp("init")
        self.assertEqual(code, 0, out)
        self.assertIn("Adopting the journal started in game: riverton (Riverton)", out)
        self.assertIn("keep me", (self.e.root / "riverton/mayor.json").read_text(encoding="utf-8"))
        self.assertIn("Welcome", (self.e.root / "riverton/journal.json").read_text(encoding="utf-8"))

    def test_init_follows_the_mayors_own_pick(self):
        (self.e.root / "my-journal").mkdir()
        (self.e.root / "picks.json").write_text('{"picks": {"Riverton": "my-journal"}}', encoding="utf-8")
        code, out = self.jp("init", "Riverton")
        self.assertEqual(code, 0, out)
        self.assertIn("riverton", self.cities()["cities"].get("my-journal", {}).get("name", "").lower())

    def test_init_refuses_what_it_shouldnt_do(self):
        self.jp("init", "Riverton")
        code, out = self.jp("init", "riverton")
        self.assertEqual(code, 1)
        self.assertIn("set up already", out)
        busy = self.e.base / "busy"
        busy.mkdir()
        (busy / "something.txt").write_text("x", encoding="utf-8")
        code, out = self.jp("init", "Elsewhere", "--folder", busy)
        self.assertEqual(code, 1)
        self.assertIn("isn't empty", out)
        code, out = self.jp("init", "X", "--id", "Bad Id")
        self.assertEqual(code, 2)
        code, out = self.jp("init")                                       # no name, nothing to adopt
        self.assertEqual(code, 2)
        self.assertIn("Which city?", out)
        code, out = self.jp("init", "A", "B")
        self.assertEqual(code, 2)


class SampleJournal(unittest.TestCase):
    """docs/sample-journal (the made-up city Riverton, for testers and the docs) builds without problems or warnings."""

    def test_the_sample_journal_builds_cleanly(self):
        e = Env()
        try:
            src = e.base / "sample"
            shutil.copytree(REPO / "docs/sample-journal", src)
            code, out = e.run(JOURNAL, "build", src)
            self.assertEqual(code, 0, out)
            self.assertNotIn("Warning", out)
            j = json.loads((e.root / "riverton/journal.json").read_text(encoding="utf-8"))
            self.assertEqual((j["city"], len(j["briefing"]["tasks"]), len(j["images"])), ("Riverton", 3, 1))
        finally:
            e.close()

