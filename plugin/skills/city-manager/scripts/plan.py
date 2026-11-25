#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Check a plan against the city and draw it for the Mayor. The plan is the JSON file cityplan.py exports from (see its
docstring); the city is the City Manager mod's snapshot. It only reads. The procedure is references/backbone.md.

usage:
  plan.py check PLAN.json <src> [--name "<City> <N>"] [--start] [--json OUT.json]
      Lists what would go wrong in game, plan by plan:
        ✗ blocks: a street crossing or joining a highway at grade, a road across a railway at grade, a road steeper
          than the game allows (20%), a Now or Next piece on a tile the city doesn't own, a piece still locked, and
          anything cityplan.py export would refuse;
        ! warns: streets that get zoned steeper than 8%, a road over water not marked as a bridge, a piece name the
          snapshot's catalogue doesn't have, a Now or Next road with no piece named, the naming convention;
        · notes: tiles the long-term plans need, junctions close together on an arterial, highways crossed safely.
      Then the length of road per plan and class. Exit status 1 when anything blocks.
  plan.py draw PLAN.json <src> --out FILE.png [--view plan|start|map] [--only "<plan>"]... [--around "<item>"]
                                              [--title TEXT] [--width PX] [--start]
      Draws the plans over the map (ground, water, the city's own roads faint), the Now and Next items numbered.
      --view plan (the default) fits the Now and Next plans, start the owned tiles, map the whole map. --around draws a
      close-up of one road, area or junction, marked, for its build card. --only (repeatable) draws only those plans.

  plan.py built PLAN.json <src> [--all] [--out FILE.png] [--json OUT.json]
      Which plan items the city has now, from the snapshot: each road as built, partly built (how much, and where the
      gap is) or not yet, with the piece and street it was built as and where that differs from its card (another
      piece, no tunnel); each junction (a roundabout, lights, an underpass) and each area (buildings and zoning
      inside). Checks the Now, Next and Done plans (--all: every plan). --out draws them coloured by the answer.
  plan.py map <src> --out FILE.png [--before FILE|kept|start] [--view city|start|map] [--title TEXT] [--width PX]
      A fresh map of the city for the report and the City page: its roads with their names, districts, and what was
      built since the snapshot before (the session start by default; kept: the copy the last report kept), marked,
      with the buildings the Mayor placed.
  plan.py cards PLAN.json <src> --out-dir DIR [--only "<plan>"]... [--width PX]
      A close-up picture for every numbered item in the Now and Next plans (an item whose name starts with its step
      number, like "2 Cedar: ramp down"; others get none), for its build card, and the journal lines to go with each:
      the step's picture and Show-on-map place.

  plan.py frame <src> "<street>" [--part N]
      A street as a frame for places: its parts (one name can cover several roads; each part runs straight on through
      its junctions), which end is 0 and which side is left, and what's along it at how many metres (the streets that
      join or cross, the map's edge, open ends), with its pieces. Places then read "<street>@<m along>[+|-<m left>]",
      "<street>/<part>@…" or "<street> x <street>" (frame.py), instead of x and z.

  plan.py road PLAN.json <src> --plan "<Status> · <Topic>" --name "<N> <words>" [--piece "<menu name>"] [--class C]
               [--tunnel] [--bridge] (--through PLACE PLACE… | --along STREET --from S --to S [--offset T] |
               --off STREET --at S --side left|right --length L [--angle A]) [--to-street STREET]
  plan.py zone PLAN.json <src> --plan … --name … --type Residential|Commercial|Industrial|Office|Custom
               (--along STREET --from S --to S --side left|right [--depth 48] [--gap G] | --polygon PLACE PLACE PLACE…)
  plan.py junction PLAN.json <src> --plan … --name … --type Normal|Roundabout|Interchange|… [--piece …]
               --at "<street> x <street>" | --at PLACE --roads ROAD ROAD
      Write one item into the plan file (replacing one of the same name) from places along streets: a road through
      places, beside a street (--along, --offset metres to its left), or off it at a right angle (or --angle degrees),
      optionally on to the nearest point of another street; a zoning band along a street's side (from 1 m off its
      edge, 48 m = six cells deep by default) or a polygon of places; a junction marker where two streets meet (they
      go into the plan as existing roads). Offsets follow the street's own direction where it is, so on a bend a big
      offset swings with it: say a place from the nearest street. Then `plan.py check`.

  plan.py underpass PLAN.json <src> --plan … --number N --name WORDS --under "<road or railway>"
               (--along STREET [--from S --to S] | --through PLACE PLACE…) [--piece P] [--depth 13] [--ramp 100] [--span W]
  plan.py interchange PLAN.json <src> --plan … --number N --name WORDS --highway "<highway>" --kind diamond
               (--street STREET | --along … | --through …) [--frontage-gap 90] [--frontage-length 260] [--street-piece P]
  plan.py interchange PLAN.json <src> --plan … --number N --name WORDS --highway "<highway>" --kind stem --from PLACE
               [--piece "Four-Lane Road"] [--depth 13] [--ramp 100]
  plan.py tunnel PLAN.json <src> --plan … --number N --name WORDS (--through PLACE PLACE… | --along …) [--depth 13] [--ramp 100]
      interchanges.md's templates, drawn into the plan file from the street frame: a street under a highway, a railway
      or a road (down-ramp, tunnel just past its edges, up-ramp, an Underpass marker); a tunnel diamond (Template A: the
      street under the highway between frontage streets 90 m out, step N; the frontage streets, step N+1; four slip
      roads, off before the crossing and on after it on each direction's traffic side, step N+2); an underground stem
      (Template B: a road ending at the highway, under it to underground junctions 32 m either side, four slip roads
      down to them); a long tunnel along a line (a Seattle-style bored road). Pieces carry their depth, so the build
      card says "13 m down". Ramps default to 12% and are refused over 20%; a gravel street goes under as a paved
      road; left-hand traffic (from the snapshot) mirrors the slip roads.

  plan.py grid PLAN.json <src> --along "<street>" --side left|right --rows N [--start S] [--length L]
               [--piece "Two-Lane Road"] [--ends both|start|end|none] [--block B] [--zone TYPE]
               [--plan "Now · <Topic>"] [--number N] [--name WORDS] [--from X,Z]
      Adds a district's local streets to the plan file: N rows parallel to a street the city has, on its left or right
      (facing from the end nearest --from, or its first end, to the other), spaced by the road-hierarchy rule (half
      each road's width + 96 m: 112 m between Two-Lane Roads, 116 m off a Four-Lane Road), from S metres along it for L
      metres (its length by default); end streets joining the rows, cross streets every B metres, and with --zone a
      zoning area over the grid (Residential, Commercial, Industrial, Office). Every street is a numbered item with its
      piece ("7 Riverside, first street"), so it gets a build card. Items of the same name are replaced, so running it
      again redraws. For a curving or planned street, use --origin X,Z --dir DX,DZ instead (with --length, and
      --spine-piece "<its piece>" for the spacing).

  plan.py ship PLAN.json <city>/journal [--name "<City> <N>"] [--map-id ID] [--force] [--dry-run] [--width PX]
      From the plan file to the game in one run: checks it against the newest snapshot (stops on anything to fix,
      unless --force), exports the guide as the city's next number (`<City> <N+1>`, its map id from the city's last
      guide), moves the city's older guides to Exports/old, and makes one build card per step number of every Now and
      Next plan (`7 West, first street` and `7 Riverside homes` are both step 7): a close-up of all its items, a
      Show-on-map place, and a tick once the snapshot shows all of them built. Each card is a journal step in the
      project that links that plan (or a new one), in a marked block of the page. A step already there for the same
      number, written by hand or by an earlier ship, keeps its id, its words and its tick; a new one takes its words
      from the plan's "cards" (below), else from the item and its pieces. Then it points every project's link to the
      new guide and builds the journal. --dry-run says what it would do and writes nothing.
      First it reads the planner's own document: Import replaces it whole, so if the Mayor drew, moved, renamed or
      deleted anything since the guide it holds, ship stops and lists it (with `plan.py check` on their drawings).
      Ship again with --keep-mayor (their changes go into the plan file, backed up first) or --drop-mayor (the new
      guide replaces them): the Mayor's call. Moves under 8 m are nudges, left as planned.

  plan.py advance PLAN.json <city>/journal [--promote "Next · <Topic>"] [--keep-done N] [--dry-run]
      The move-on step, after a report: a Now plan whose every step number is built (by the newest snapshot) or ticked
      (in the journal, the Mayor's tick or yours) becomes Done; a Done plan the newest guide already showed drops out
      (kept in archive.json beside the plan file); a Next plan becomes Now only with --promote (the Mayor's choice: it
      says so when Now is empty). The projects follow: their plan links take the new names, a project whose steps are
      all done and whose plans are all Done closes with a log line, and one Done for N reports (3) moves to
      projects/archive/ (its id stays known to older briefings), unless the current briefing names it. The plan file is
      backed up first, then the journal is built. Then `plan.py ship` for the next guide.

  plan.py drawings <city>/journal [--map-id ID] [--json FILE]
      What the Mayor drew in the planner since the guide it holds (which guide that is, whether the newest was
      imported), with `plan.py check` on their drawings: for the report, and before planning the next streets.

<src> is a journal source folder, a journal folder in ModsData, or a snapshot file, as for city.py and survey.py.

Keys plan.py reads beyond cityplan.py's (cityplan.py ignores them, so the same file exports as it is):
  cards:     {"7": "7 Riverside streets: five Two-Lane Roads ...", "8": {"text": "...", "note": "..."}} on a plan:
             the journal step's words for a step number, for plan.py ship
  roads:     "piece"     the road piece by the name in the game's menu ("Four-Lane Road"; `city.py catalogue`)
             "tunnel": true, "bridge": true   the whole road is one (split a road into pieces where it changes)
             "existing": true                 already in the city: drawn for context, not checked
  junctions: "piece"     a prebuilt junction from the catalogue ("Trumpet Intersection") or plain words ("a small
                         roundabout"); a catalogue name is checked, words are not
  markers:   [{"name": "A", "position": [x, z], "note": "Braunton: flat, by the estuary"}]  labelled pins for a choice
             the Mayor makes (two starts, two harbour sites); drawn, never checked or exported
A plan's status comes from its name ("<Status> · <Topic>"): Now and Next get built soon, so they must sit on owned tiles
and name pieces the Mayor can build; Later and Base are the long-term picture. The check works on the snapshot's 56 m
terrain grid: grades are about right over 40 m, not exact, and a creek narrower than the grid can be missed.
"""
import json
import math
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import city  # noqa: E402
import cityplan  # noqa: E402
import survey as sv  # noqa: E402
from city import arr, obj  # noqa: E402

GRADE_REFUSED = 20.0        # the game refuses steeper roads
GRADE_ZONED = 8.0           # streets that get zoned
WATER_DEPTH = 1.0           # metres: deeper than this needs a bridge
NEAR_JUNCTION = 80.0        # a grade-separated junction marker this close covers a crossing
SEPARATED = {"Underpass", "Overpass", "Interchange", "CrossingNoConnection"}
CLASS_STYLE = {"Highway": ((220, 40, 40), 7), "Arterial": ((245, 140, 20), 6), "Collector": ((240, 200, 30), 5),
               "Local": ((255, 255, 255), 3)}
STATUS_ORDER = {"Base": 0, "Done": 1, "Later": 2, "Next": 3, "Now": 4, None: 3}


def status_of(name):
    m = cityplan.PLAN_NAME.fullmatch(name or "")
    return m.group(1) if m else None


def soon(status):
    """Plans that get built soon: everything in them must be buildable now."""
    return status in ("Now", "Next", None)


def load_plans(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    plans = doc.get("plans") if isinstance(doc, dict) and "plans" in doc else [doc]
    return [p for p in plans if isinstance(p, dict)]


def piece_of(item):
    return item.get("piece") or item.get("prefab")


def sample(points, step):
    """Points every `step` metres along a polyline, with the distance along it."""
    pts = [(float(p[0]), float(p[1])) for p in points if len(p) >= 2]
    out = []
    if not pts:
        return out
    run = 0.0
    out.append((pts[0][0], pts[0][1], 0.0))
    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a, b)
        k = max(1, int(math.ceil(seg / step)))
        for i in range(1, k + 1):
            t = i / k
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, run + seg * t))
        run += seg
    return out


def length(points):
    return sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:]))


def cross(a1, a2, b1, b2):
    """Where segment a crosses segment b: (t along a, u along b), or None."""
    d1 = (a2[0] - a1[0], a2[1] - a1[1])
    d2 = (b2[0] - b1[0], b2[1] - b1[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    v = (b1[0] - a1[0], b1[1] - a1[1])
    t = (v[0] * d2[1] - v[1] * d2[0]) / den
    u = (v[0] * d1[1] - v[1] * d1[0]) / den
    return (t, u) if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9 else None


def nearest(points, p):
    """(distance, distance along) from p to a polyline."""
    best = (math.inf, 0.0)
    run = 0.0
    for a, b in zip(points, points[1:]):
        dx, dz = b[0] - a[0], b[1] - a[1]
        seg = math.hypot(dx, dz)
        t = 0.0 if seg < 1e-9 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / (seg * seg)))
        q = (a[0] + dx * t, a[1] + dz * t)
        d = math.dist(p, q)
        if d < best[0]:
            best = (d, run + seg * t)
        run += seg
    return best


class Segments:
    """The city's existing network as short segments in a spatial hash, for crossings."""

    CELL = 250.0

    def __init__(self, net):
        self.cells = defaultdict(list)
        for e in net.edges:
            line = e["line"]
            n = len(line) - 1
            for i, (a, b) in enumerate(zip(line, line[1:])):
                rec = (a, b, e, i / n, (i + 1) / n)
                for k in self._keys(a, b):
                    self.cells[k].append(rec)

    def _keys(self, a, b):
        s = self.CELL
        x0, x1 = sorted((a[0], b[0]))
        z0, z1 = sorted((a[1], b[1]))
        return [(i, j) for i in range(int(math.floor(x0 / s)), int(math.floor(x1 / s)) + 1)
                for j in range(int(math.floor(z0 / s)), int(math.floor(z1 / s)) + 1)]

    def hits(self, a, b):
        seen = set()
        for k in self._keys(a, b):
            for rec in self.cells.get(k, []):
                if id(rec) in seen:
                    continue
                seen.add(id(rec))
                h = cross(a, b, rec[0], rec[1])
                if h:
                    yield h, rec


class Check:
    def __init__(self, snap, plans, name=None):
        self.snap = snap
        self.plans = plans
        self.name = name
        self.terrain = sv.Terrain(snap)
        self.tiles = sv.Tiles(snap)
        self.net = sv.Network(snap)
        self.facts = sv.survey(snap)
        st = self.facts["start"]
        self.places = sv.Places([self.tiles.tiles[i]["box"] for i in st["tiles"] if 0 <= i < len(self.tiles.tiles)] or [st["box"]],
                                self.terrain.extent, st["word"])
        self.all_owned = st["allOwned"] or not self.tiles.owned()
        self.segments = Segments(self.net)
        self.inc = self.net.incident()
        self.catalogue = arr(obj(snap.get("catalogue")).get("items"))
        self.results = []

    # --- helpers

    def where(self, x, z):
        return f"{self.places.of(x, z)} [x {x:.0f}, z {z:.0f}]"

    def lookup(self, piece):
        key = (piece or "").casefold().strip()
        for it in self.catalogue:
            if key in (str(it.get("title", "")).casefold(), str(it.get("prefab", "")).casefold()):
                return it
        return None

    def junctions_near(self, plan, x, z, types=SEPARATED):
        for j in arr(plan.get("junctions")):
            pos = arr(j.get("position"))
            if len(pos) >= 2 and j.get("type") in types and math.dist((float(pos[0]), float(pos[1])), (x, z)) <= NEAR_JUNCTION:
                return j
        return None

    def end_node_near(self, e, x, z, radius=30.0):
        for k in ("a", "b"):
            n = self.net.nodes.get(e.get(k))
            if n and math.dist((n.get("x", 0), n.get("z", 0)), (x, z)) <= radius:
                return n, k
        return None

    def highway_ends_at(self, e, x, z):
        """The highway ends here and carries on as a street (the map's own start, or a ramp's end)."""
        hit = self.end_node_near(e, x, z)
        if not hit:
            return False
        node, k = hit
        es = self.inc.get(e.get(k), [])
        return sum(1 for f in es if f["kind"] == "highway" and not sv.is_ramp(f)) <= 1

    def grade_at(self, e, frac):
        """True when an existing edge is off the ground at this point (bridge, tunnel or elevated)."""
        if e.get("bridge") or e.get("tunnel"):
            return True
        el = arr(e.get("elevation"))
        if len(el) == 2:
            return abs(el[0] * (1 - frac) + el[1] * frac) >= 5
        return False

    # --- the checks

    def run(self):
        all_roads = {}
        for p in self.plans:
            for r in arr(p.get("roads")):
                all_roads.setdefault(r.get("name"), r)
        for p in self.plans:
            status = status_of(p.get("name"))
            res = {"name": p.get("name"), "status": status, "problems": [], "km": {}}
            self.results.append(res)

            def add(level, item, text, at=None):
                res["problems"].append({"level": level, "item": item, "text": text, "at": [round(at[0]), round(at[1])] if at else None})

            _, errors = cityplan.build_plan(p, lambda x, z: 0.0)
            for e in errors:
                add("error", "", f"cityplan.py export would refuse this: {e}")
            roads = [r for r in arr(p.get("roads")) if isinstance(r, dict)]
            km = Counter()
            for r in roads:
                if not r.get("existing"):
                    km[r.get("class", "Local")] += length(arr(r.get("points")))
            res["km"] = {k: round(v / 1000, 2) for k, v in km.items()}
            for r in roads:
                if r.get("existing") or len(arr(r.get("points"))) < 2:
                    continue
                self.road(p, status, r, add)
            for a in arr(p.get("areas")):
                if isinstance(a, dict) and soon(status) and not self.all_owned:
                    self.ownership(a.get("name"), [(float(q[0]), float(q[1])) for q in arr(a.get("polygon")) if len(q) >= 2],
                                   status, add, closed=True)
            for j in arr(p.get("junctions")):
                if isinstance(j, dict):
                    self.junction(p, status, j, all_roads, add)
            self.internal(p, roads, add)
            if soon(status):
                self.spacing(p, roads, add)
        names = [p.get("name") or "" for p in self.plans]
        problems = cityplan.naming_problems(self.name, names) if self.name else \
            [w for w in cityplan.naming_problems("X 1", names) if not w.startswith("file ")]
        self.naming = problems
        return self.results

    def road(self, plan, status, r, add):
        name = r.get("name") or "(no name)"
        cls = r.get("class", "Local")
        pts = [(float(q[0]), float(q[1])) for q in arr(r.get("points")) if len(q) >= 2]
        separated = bool(r.get("tunnel") or r.get("bridge"))
        # the piece
        if soon(status):
            piece = piece_of(r)
            if not piece:
                add("warn", name, "no road piece named: its build card needs one from `city.py catalogue` (add \"piece\")")
            elif self.catalogue:
                it = self.lookup(piece)
                if not it:
                    add("warn", name, f"\"{piece}\" isn't in the snapshot's catalogue (the game's own menus): check the name, or say "
                                      "it's a mod's road the Mayor has")
                elif not it.get("unlocked"):
                    add("error", name, f"\"{piece}\" is locked" + (f" until milestone {it['milestone']}" if it.get("milestone") else "") +
                                       ": pick an unlocked piece, or move this to a later plan")
        # ground: steep and water
        if not separated:
            self.ground(name, cls, pts, add)
        # owned tiles
        if not self.all_owned:
            self.ownership(name, pts, status, add)
        # existing networks
        self.crossings(plan, name, cls, pts, separated, add)

    def ground(self, name, cls, pts, add):
        samples = sample(pts, 10.0)
        if len(samples) < 2:
            return
        hs = [self.terrain.height(x, z) for x, z, _ in samples]
        steep, worst, at = 0.0, 0.0, None
        j = 0
        zoned = cls in ("Local", "Collector")
        for i, (x, z, d) in enumerate(samples):
            while j < len(samples) - 1 and samples[j][2] - d < 40.0:
                j += 1
            run = samples[j][2] - d
            if run < 20.0:
                break
            g = 100 * abs(hs[j] - hs[i]) / run
            if g > worst:
                worst, at = g, (x, z)
            if g > (GRADE_ZONED if zoned else GRADE_REFUSED):
                steep += samples[min(i + 1, len(samples) - 1)][2] - d
        if worst > GRADE_REFUSED:
            add("error", name, f"up to about {worst:.0f}% steep, {self.where(*at)}: the game refuses roads over 20%. "
                               "Follow the slope, wind up it, or mark that stretch a tunnel or bridge", at)
        elif zoned and worst > GRADE_ZONED:
            add("warn", name, f"up to about {worst:.0f}% steep for about {steep:.0f} m, {self.where(*at)}: streets that get "
                              "zoned should stay under 8% (buildings struggle on steep lots)", at)
        wet, run_start, longest, at = 0.0, None, 0.0, None
        for (x, z, d) in samples:
            if self.terrain.depth(x, z) > WATER_DEPTH:
                if run_start is None:
                    run_start = d
                    at = at or (x, z)
                longest = max(longest, d - run_start)
            else:
                if run_start is not None:
                    wet += d - run_start
                run_start = None
        if run_start is not None:
            wet += samples[-1][2] - run_start
        if wet >= 30:
            add("warn", name, f"crosses about {wet:.0f} m of water, {self.where(*at)}: mark it \"bridge\" (and say which bridge "
                              "piece), or keep it on the shore", at)

    def ownership(self, name, pts, status, add, closed=False):
        if len(pts) < 2:
            return
        line = pts + [pts[0]] if closed else pts
        outside, tiles, at = 0.0, set(), None
        prev = None
        for x, z, d in sample(line, 20.0):
            t = self.tiles.at(x, z)
            if t is None or not t["owned"]:
                if t is not None:
                    tiles.add(t["i"])
                if prev is not None:
                    outside += d - prev
                at = at or (x, z)
                prev = d
            else:
                prev = None
        if at is None:
            return
        buy = sorted({self.places.of(*self.tiles.tiles[i]["centre"]) for i in tiles})
        if soon(status):
            add("error", name, f"runs onto {len(tiles)} tile(s) the city doesn't own (about {outside:.0f} m), starting "
                               f"{self.where(*at)}: buy them first, or keep this piece for a later plan", at)
        else:
            add("note", name, f"needs {len(tiles)} more tile(s): " + "; ".join(buy[:4]) + ("…" if len(buy) > 4 else ""), at)

    def crossings(self, plan, name, cls, pts, separated, add):
        """Where the road meets the city's highways and railways. Hits within 80 m of each other (a divided highway's two
        carriageways) make one message."""
        total = length(pts)
        run = 0.0
        found = []   # (kind of problem, x, z, label)
        for a, b in zip(pts, pts[1:]):
            seg = math.dist(a, b)
            for (t, u), (ea, eb, e, f0, f1) in self.segments.hits(a, b):
                x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                along = run + seg * t
                at_end = along < 15 or total - along < 15
                frac = f0 + (f1 - f0) * u
                kind = e["kind"]
                label = e["streetName"] or e["title"]
                problem = None
                if kind == "highway":
                    if self.grade_at(e, frac):
                        problem = None if at_end else "passes"
                    elif cls == "Highway":
                        problem = None if (at_end or separated or self.junctions_near(plan, x, z)) else "highway-cross"
                    elif separated or self.junctions_near(plan, x, z):
                        problem = None
                    elif at_end:
                        problem = None if (sv.is_ramp(e) or self.highway_ends_at(e, x, z)) else "joins"
                    else:
                        problem = "crosses"
                elif kind == "train":
                    if not (separated or self.grade_at(e, frac) or self.junctions_near(plan, x, z)):
                        problem = "rail"
                elif kind == "road" and cls == "Highway" and not (separated or at_end or self.grade_at(e, frac)):
                    if not self.junctions_near(plan, x, z):
                        problem = "highway-over-road"
                if problem:
                    for f in found:
                        if f[0] == problem and math.dist((f[1], f[2]), (x, z)) < 80:
                            if label not in f[3]:
                                f[3].append(label)
                            break
                    else:
                        found.append((problem, x, z, [label]))
            run += seg
        for problem, x, z, labels in found:
            what = " and ".join(labels)
            at = self.where(x, z)
            if problem == "passes":
                add("note", name, f"passes {what} where it's on a bridge or in a tunnel, {at}: fine if the heights work out in game", (x, z))
            elif problem == "highway-cross":
                add("error", name, f"crosses {what} with no interchange, {at}: add an Interchange junction there, or take one "
                                   "of them over or under the other", (x, z))
            elif problem == "joins":
                add("error", name, f"joins {what} at grade, {at}: through traffic would stop for it. Join an interchange's "
                                   "ramps instead, or add an Interchange junction there", (x, z))
            elif problem == "crosses":
                add("error", name, f"crosses {what} at grade, {at}: plan an underpass (add an Underpass junction there, or "
                                   "split the road and mark the piece under the highway \"tunnel\")", (x, z))
            elif problem == "rail":
                add("error", name, f"crosses the railway at grade, {at}: the game won't allow it. Take the road under it (a "
                                   "tunnel) or over it", (x, z))
            else:
                add("error", name, f"crosses {what} at grade, {at}: a highway needs it over or under, or an interchange", (x, z))

    def junction(self, plan, status, j, roads, add):
        name = j.get("name") or "(junction)"
        a, b = roads.get(j.get("road_a")), roads.get(j.get("road_b"))
        pos = arr(j.get("position"))
        at = (float(pos[0]), float(pos[1])) if len(pos) >= 2 else None
        if a and b and j.get("type") in ("Normal", "Roundabout"):
            ca, cb = a.get("class"), b.get("class")
            if (ca == "Highway") != (cb == "Highway"):
                ramp = a if ca == "Highway" else b
                if not re.search(r"ramp|slip|1 lane|one-lane", f"{ramp.get('name', '')} {piece_of(ramp) or ''}", re.I):
                    add("error", name, f"a {j.get('type').lower()} joining a highway to a {('street' if (cb if ca == 'Highway' else ca) != 'Arterial' else 'main road')} "
                                       "puts traffic lights or a roundabout on the highway: use an Interchange there", at)
        if soon(status) and at and not self.all_owned:
            t = self.tiles.at(*at)
            if t is not None and not t["owned"]:
                add("error", name, f"sits on a tile the city doesn't own ({self.places.of(*at)})", at)
        piece = piece_of(j)
        if piece and self.catalogue and soon(status):
            it = self.lookup(piece)
            if it and not it.get("unlocked"):
                add("error", name, f"\"{piece}\" is locked" + (f" until milestone {it['milestone']}" if it.get("milestone") else ""), at)

    def internal(self, plan, roads, add):
        """Crossings between the plan's own roads: a highway crossing a street needs a grade-separated junction."""
        lines = [(r, [(float(q[0]), float(q[1])) for q in arr(r.get("points")) if len(q) >= 2]) for r in roads
                 if not r.get("existing")]   # roads already built are checked against the snapshot instead
        for i, (r1, p1) in enumerate(lines):
            for r2, p2 in lines[i + 1:]:
                c1, c2 = r1.get("class"), r2.get("class")
                if (c1 == "Highway") == (c2 == "Highway"):
                    continue
                if r1.get("tunnel") or r1.get("bridge") or r2.get("tunnel") or r2.get("bridge"):
                    continue
                l1, l2 = length(p1), length(p2)
                run1 = 0.0
                for a, b in zip(p1, p1[1:]):
                    run2 = 0.0
                    for c, d in zip(p2, p2[1:]):
                        h = cross(a, b, c, d)
                        if h:
                            t, u = h
                            x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                            s1, s2 = run1 + math.dist(a, b) * t, run2 + math.dist(c, d) * u
                            end1 = s1 < 15 or l1 - s1 < 15
                            end2 = s2 < 15 or l2 - s2 < 15
                            hw, street = (r1, r2) if c1 == "Highway" else (r2, r1)
                            hw_end = end1 if hw is r1 else end2
                            if hw_end:   # a ramp ending on a street: how interchanges work
                                continue
                            if not self.junctions_near(plan, x, z):
                                add("error", street.get("name") or "(road)",
                                    f"meets {hw.get('name')} (a highway in this plan) at grade, {self.where(x, z)}: add an "
                                    "Underpass or Interchange junction there", (x, z))
                        run2 += math.dist(c, d)
                    run1 += math.dist(a, b)

    def spacing(self, plan, roads, add):
        """Junctions close together on an arterial: traffic backs up between them (a guide, not a rule)."""
        for r in roads:
            if r.get("class") != "Arterial" or r.get("existing"):
                continue
            pts = [(float(q[0]), float(q[1])) for q in arr(r.get("points")) if len(q) >= 2]
            total = length(pts)
            stops = []
            for o in roads:
                if o is r:
                    continue
                op = [(float(q[0]), float(q[1])) for q in arr(o.get("points")) if len(q) >= 2]
                for p in (op[0], op[-1]) if len(op) >= 2 else ():
                    d, along = nearest(pts, p)
                    if d < 10 and 15 < along < total - 15:
                        stops.append((along, o.get("name")))
                for a, b in zip(op, op[1:]):
                    run = 0.0
                    for c, dd in zip(pts, pts[1:]):
                        h = cross(c, dd, a, b)
                        if h and 0.001 < h[1] < 0.999:
                            stops.append((run + math.dist(c, dd) * h[0], o.get("name")))
                        run += math.dist(c, dd)
            stops.sort()
            for (s1, n1), (s2, n2) in zip(stops, stops[1:]):
                if 1 < s2 - s1 < 150:
                    add("note", r.get("name"), f"junctions with {n1} and {n2} are only about {s2 - s1:.0f} m apart: on a main road, "
                                               "200 m or more keeps traffic moving (a guide, not a rule)")
                    break

    # --- output

    def markdown(self, src_name):
        out = [f"# Plan check against {src_name}\n"]
        icon = {"error": "✗", "warn": "!", "note": "·"}
        for res in self.results:
            km = ", ".join(f"{k} {v} km" for k, v in sorted(res["km"].items(), key=lambda kv: list(CLASS_STYLE).index(kv[0]) if kv[0] in CLASS_STYLE else 9))
            out.append(f"## {res['name']}" + (f" ({km})" if km else "") + "\n")
            if not res["problems"]:
                out.append("Nothing to fix.\n")
                continue
            for pr in sorted(res["problems"], key=lambda p: ("error", "warn", "note").index(p["level"])):
                out.append(f"- {icon[pr['level']]} " + (f"**{pr['item']}**: " if pr["item"] else "") + pr["text"])
            out.append("")
        if self.naming:
            out.append("## Naming\n")
            out += [f"- ! {w}" for w in self.naming]
            out.append("")
        n = Counter(p["level"] for r in self.results for p in r["problems"])
        out.append(f"**{n['error']} to fix before the Mayor builds, {n['warn'] + len(self.naming)} warnings, {n['note']} notes.** "
                   "This list is for you (it has coordinates); the Mayor gets words and the picture from `plan.py draw`.")
        return "\n".join(out)

    def errors(self):
        return sum(1 for r in self.results for p in r["problems"] if p["level"] == "error")


# --- drawing

def item_points(item):
    if "points" in item:
        return [(float(q[0]), float(q[1])) for q in arr(item.get("points")) if len(q) >= 2]
    if "polygon" in item:
        return [(float(q[0]), float(q[1])) for q in arr(item.get("polygon")) if len(q) >= 2]
    pos = arr(item.get("position"))
    return [(float(pos[0]), float(pos[1]))] if len(pos) >= 2 else []


def step_number(name):
    m = re.match(r"\s*(\d+[a-z]?)\b", name or "")
    return m.group(1) if m else None


def hex_colour(text, default):
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(text or ""))
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else default


JUNCTION_MARKS = {"Interchange": ("diamond", (220, 40, 40)), "Roundabout": ("ring", (30, 30, 30)), "Underpass": ("square", (60, 60, 200)),
                  "Overpass": ("square", (150, 150, 230)), "CrossingNoConnection": ("cross", (60, 60, 60)), "Normal": ("circle", (250, 250, 250)),
                  "Ignored": ("circle", (180, 180, 180))}


def draw(snap, plans, out, view="plan", only=(), around=None, title=None, width=1600, facts=None):
    terrain = sv.Terrain(snap)
    tiles = sv.Tiles(snap)
    net = sv.Network(snap)
    facts = facts or sv.survey(snap)
    st = facts["start"]
    if only:
        plans = [p for p in plans if p.get("name") in only]
        if not plans:
            raise SystemExit(f"No plan named {', '.join(only)!r} in the file.")
    targets = []   # the card's items: one, or every item of a step number
    if around:
        wanted = {n.casefold() for n in ([around] if isinstance(around, str) else around)}
        for p in plans:
            for kind in ("roads", "areas", "junctions"):
                for it in arr(p.get(kind)):
                    if isinstance(it, dict) and (it.get("name") or "").casefold() in wanted:
                        targets.append((p, kind, it))
        if not targets:
            raise SystemExit(f"No road, area or junction named {around!r} in the plans.")
        pts = [q for t in targets for q in item_points(t[2])]
        b = sv.bounds([[x, x, z, z] for x, z in pts])
        pad = max(250.0, 0.25 * max(b[1] - b[0], b[3] - b[2]))
        box = [b[0] - pad, b[1] + pad, b[2] - pad, b[3] + pad]
    elif view == "map":
        box = [*terrain.extent, *terrain.extent]
    elif view == "start":
        b = st["box"]
        pad = 0.4 * tiles.size
        box = [b[0] - pad, b[1] + pad, b[2] - pad, b[3] + pad]
    else:
        near = [p for p in plans if STATUS_ORDER.get(status_of(p.get("name")), 3) >= 3] or plans
        pts = [q for p in near for kind in ("roads", "areas", "junctions", "markers") for it in arr(p.get(kind))
               if isinstance(it, dict) and not it.get("existing") for q in item_points(it)]   # roads already there don't set the zoom
        if not pts:
            b = st["box"]
        else:
            b = sv.bounds([[x, x, z, z] for x, z in pts])
        pad = max(200.0, 0.12 * max(b[1] - b[0], b[3] - b[2]))
        box = [b[0] - pad, b[1] + pad, b[2] - pad, b[3] + pad]
    side = max(box[1] - box[0], box[3] - box[2])
    if side < 600:
        cx, cz = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2
        box = [cx - 300, cx + 300, cz - 300, cz + 300]
    name = facts.get("city") or "The city"
    plan_names = ", ".join(p.get("name") or "?" for p in plans)
    tids = {id(t[2]) for t in targets}
    if len(targets) == 1:
        it = targets[0][2]
        head = title or f"{name}: {it.get('name')}"
        sub = " · ".join(x for x in (targets[0][0].get("name"), piece_of(it) and f"build with: {piece_of(it)}",
                                     "in a tunnel" if it.get("tunnel") else "on a bridge" if it.get("bridge") else "") if x)
    elif targets:
        head = title or f"{name}: {targets[0][2].get('name')}"
        pieces = sorted({piece_of(t[2]) for t in targets if piece_of(t[2])})
        sub = " · ".join(x for x in (targets[0][0].get("name"), pieces and "build with: " + ", ".join(pieces)) if x)
    else:
        head = title or f"{name}: the plan"
        sub = plan_names
    pic = sv.MapPicture(terrain, box, width, head, sub)
    zoom = pic.scale
    k = 1.0 if zoom >= 0.6 else 0.8 if zoom >= 0.25 else 0.55

    for t in tiles.owned() if not st["allOwned"] else []:
        pic.rect(t["box"], (30, 30, 30, 150), 2)
    pic.flush()
    sv.draw_network(pic, net, faint=True, names=zoom >= 0.25)
    pic.flush()

    ordered = sorted(plans, key=lambda p: STATUS_ORDER.get(status_of(p.get("name")), 3))
    used_classes, used_marks, used_status, keys = set(), set(), set(), []
    # areas first, then roads, then junctions, each from the long-term plans up to Now
    for p in ordered:
        status = status_of(p.get("name"))
        alpha = {"Base": 55, "Later": 40, "Done": 30}.get(status, 80)
        for a in arr(p.get("areas")):
            if not isinstance(a, dict):
                continue
            pts = item_points(a)
            colour = hex_colour(a.get("fill"), hex_colour(cityplan.AREA_COLOURS.get(a.get("type"), "#9CA3AF"), (156, 163, 175)))
            pic.polygon(pts, colour + (alpha,), outline=colour + (210,), width=2 if status in ("Base", "Later") else 3)
    pic.flush()
    for p, kind, it in targets:
        pts = item_points(it)
        glow = (255, 0, 200, 110)
        if kind == "roads":
            pic.line(pts, glow, CLASS_STYLE.get(it.get("class"), ((0, 0, 0), 4))[1] * k * 1.4 + 22)
        elif kind == "areas":
            pic.polygon(pts, (255, 0, 200, 50), outline=glow, width=14)
        else:
            pic.marker(*pts[0], "circle", glow, r=34, outline=None)
    if targets:
        pic.flush()
    for p in ordered:
        status = status_of(p.get("name"))
        used_status.add(status)
        for r in arr(p.get("roads")):
            if not isinstance(r, dict):
                continue
            cls = r.get("class", "Local")
            colour, w = CLASS_STYLE.get(cls, CLASS_STYLE["Local"])
            used_classes.add(cls)
            pts = item_points(r)
            w = w * k * (0.6 if status in ("Base", "Later", "Done") else 1.0)
            dash = (8, 7) if r.get("tunnel") else (18, 10) if status == "Next" else (5, 9) if status == "Later" else None
            if status == "Done":
                colour = (150, 150, 150)
            if status in ("Base", "Later"):
                pic.line(pts, colour + (200,), w, dash=dash, casing=(60, 60, 60, 150) if cls == "Local" else None)
            else:
                if r.get("bridge"):
                    pic.line(pts, (255, 255, 255), w + 8)
                pic.line(pts, colour, w, dash=dash, casing=(40, 40, 40) if not r.get("tunnel") else (255, 255, 255))
    pic.flush()
    for p in ordered:
        for j in arr(p.get("junctions")):
            if isinstance(j, dict) and item_points(j):
                shape, colour = JUNCTION_MARKS.get(j.get("type"), ("circle", (200, 200, 200)))
                used_marks.add(j.get("type"))
                pic.marker(*item_points(j)[0], shape, colour, r=max(6, int(11 * k)), outline=(20, 20, 20))
    pic.flush()
    # labels: numbers for Now and Next items, names for the long-term areas
    for p in reversed(ordered):
        status = status_of(p.get("name"))
        for kind in ("junctions", "roads", "areas"):
            for it in arr(p.get(kind)):
                if not isinstance(it, dict) or it.get("existing"):
                    continue
                pts = item_points(it)
                if not pts:
                    continue
                nm = it.get("name") or ""
                if kind == "areas":
                    cx, cz = sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)
                elif kind == "roads":
                    samples = sample(pts, 10.0)
                    half = samples[-1][2] / 2
                    cx, cz, _ = min(samples, key=lambda s_: abs(s_[2] - half))
                else:
                    cx, cz = pts[0]
                num = step_number(nm)
                if status in ("Now", "Next", None) and num:
                    fill = (20, 20, 20) if status != "Next" else (90, 90, 90)
                    if id(it) in tids:
                        fill = (200, 0, 160)
                    spots = [(cx, cz)]
                    if kind == "roads":
                        spots = [min(samples, key=lambda s_, f=f: abs(s_[2] - f * samples[-1][2]))[:2] for f in (0.5, 0.35, 0.65, 0.2, 0.8)]
                    elif kind == "junctions":
                        spots = [(cx + dx / pic.scale, cz + dz / pic.scale) for dx, dz in ((0, 24), (24, 0), (0, -24), (-24, 0))]
                    else:
                        spots += [(cx + dx / pic.scale, cz + dz / pic.scale) for dx, dz in ((40, 0), (-40, 0), (0, 40), (0, -40))]
                    free = next((q for q in spots if pic.free(*q, 17)), spots[0])
                    pic.badge(*free, num, fill=fill, r=15)
                    entry = f"{nm}" + (f" ({piece_of(it)})" if piece_of(it) else "")
                    if entry not in keys and (not targets or id(it) in tids):
                        keys.append(entry)
                elif kind == "areas" or (kind == "roads" and status in ("Base", "Later") and zoom < 0.6):
                    pic.label(cx, cz, nm, size=15 if kind == "areas" else 13, colour=(30, 30, 30))
                elif id(it) in tids:
                    pic.label(cx, cz, nm, size=17, colour=(150, 0, 120))
    for p in plans:
        for m in arr(p.get("markers")):
            pts = item_points(m) if isinstance(m, dict) else []
            if pts:
                tag = str(m.get("name") or "?")[:3]
                pic.badge(*pts[0], tag, fill=(200, 0, 120), r=18)
                if m.get("note"):
                    keys.append(f"{tag}: {str(m['note'])[:80]}")
    legend = [("line", CLASS_STYLE[c][0], c.lower() if c != "Local" else "local street") for c in CLASS_STYLE if c in used_classes]
    if "Next" in used_status:
        legend.append(("dash", (90, 90, 90), "next (dashed)"))
    if any(r.get("tunnel") for p in plans for r in arr(p.get("roads")) if isinstance(r, dict)):
        legend.append(("dash", (40, 40, 40), "tunnel"))
    words = {"Interchange": "interchange", "Roundabout": "roundabout", "Underpass": "underpass", "Overpass": "overpass",
             "CrossingNoConnection": "crossing, no junction", "Normal": "junction", "Ignored": "junction (ignored)"}
    legend += [(JUNCTION_MARKS[m][0], JUNCTION_MARKS[m][1], words[m]) for m in JUNCTION_MARKS if m in used_marks]
    legend += [("line", (90, 90, 90), "the city's roads"), ("line", (205, 40, 40), "its highways")]
    if not st["allOwned"]:
        legend.append(("outline", (30, 30, 30), "owned tiles"))
    keys.sort(key=lambda k_: (int(re.match(r"\d+", k_).group()) if re.match(r"\d+", k_) else 10 ** 6, k_))
    notes = keys[:14] + ([f"… and {len(keys) - 14} more"] if len(keys) > 14 else [])
    image = pic.finish(legend, notes)
    image.save(out, optimize=True)
    return out


# --- what's built: the plan against the city

BUILT_NEAR = 20.0        # metres: a city road this close to a planned line, and running the same way, counts as built
BUILT_FULL = 0.85        # a road with this share of its length built is built
BUILT_PART = 0.15        # below this share it's not built yet (a crossing street touches a few metres of any line)
JUNCTION_NEAR = 45.0     # metres from a planned junction to the city's junction that answers it
ROUNDABOUT_NEAR = 80.0   # a roundabout's nodes sit on its ring
RESULT = {"built": ((30, 150, 60), "✓ built"), "partly": ((235, 150, 0), "◐ partly"), "not yet": ((120, 120, 132), "✗ not yet"),
          "different": ((130, 60, 200), "≠ built differently")}
ZONE_KINDS = {"Residential": {"residential"}, "Commercial": {"commercial"}, "Industrial": {"industrial"}, "Office": {"office"}}


class NearIndex:
    """The city's roads as short segments in a grid of 60 m cells, for "the nearest road to this point"."""

    CELL = 60.0

    def __init__(self, edges):
        self.cells = defaultdict(list)
        for e in edges:
            line = e["line"]
            for a, b in zip(line, line[1:]):
                for k in self._keys(a, b):
                    self.cells[k].append((a, b, e))

    def _keys(self, a, b):
        s = self.CELL
        x0, x1 = sorted((a[0], b[0]))
        z0, z1 = sorted((a[1], b[1]))
        return [(i, j) for i in range(int(math.floor(x0 / s)), int(math.floor(x1 / s)) + 1)
                for j in range(int(math.floor(z0 / s)), int(math.floor(z1 / s)) + 1)]

    def near(self, x, z, radius, heading=None):
        """(distance, edge) of the nearest segment within radius; with a heading (dx, dz), only segments running
        roughly the same way (within about 35 degrees), so a street crossing the line doesn't count."""
        best, s = None, self.CELL
        for i in range(int(math.floor((x - radius) / s)), int(math.floor((x + radius) / s)) + 1):
            for j in range(int(math.floor((z - radius) / s)), int(math.floor((z + radius) / s)) + 1):
                for a, b, e in self.cells.get((i, j), []):
                    d = nearest([a, b], (x, z))[0]
                    if d > radius or (best and d >= best[0]):
                        continue
                    if heading:
                        sx, sz = b[0] - a[0], b[1] - a[1]
                        n = math.hypot(sx, sz) * math.hypot(*heading)
                        if n > 1e-9 and abs(sx * heading[0] + sz * heading[1]) / n < 0.82:
                            continue
                    best = (d, e)
        return best


def inside(poly, x, z):
    hit = False
    for (x1, z1), (x2, z2) in zip(poly, poly[1:] + poly[:1]):
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            hit = not hit
    return hit


def centre_of(kind, pts):
    if kind == "roads":
        samples = sample(pts, 10.0)
        half = samples[-1][2] / 2
        x, z, _ = min(samples, key=lambda q: abs(q[2] - half))
        return x, z
    return sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)


def level(e):
    el = [v for v in arr(e.get("elevation")) if isinstance(v, (int, float))]
    if e.get("tunnel") or (el and min(el) < -3):
        return "under"
    if e.get("bridge") or (el and max(el) > 3):
        return "over"
    return "ground"


class Built:
    def __init__(self, snap):
        self.snap = snap
        self.net = sv.Network(snap)
        self.roads = self.net.by_kind(*city.ROAD_KINDS)
        self.index = NearIndex(self.roads)
        self.by_class = {"highway": NearIndex(self.net.by_kind("highway")), "road": NearIndex(self.net.by_kind("road"))}
        inc = self.net.incident()
        self.degree = {nid: sum(1 for e in es if e.get("kind") in city.ROAD_KINDS) for nid, es in inc.items()}
        prefabs = arr(snap.get("prefabs"))
        self.buildings = [dict(b, prefabName=city.name_of(prefabs, b.get("prefab"))) for b in arr(snap.get("buildings")) if isinstance(b, dict)]
        self.districts = [d for d in arr(snap.get("districts")) if isinstance(d, dict)]

    def road(self, r):
        pts = item_points(r)
        samples = sample(pts, 10.0)
        if len(samples) < 2 or samples[-1][2] < 1:
            return None
        hits = []
        index = self.by_class["highway" if r.get("class") == "Highway" else "road"]   # a street along a highway isn't built
        for i, (x, z, _) in enumerate(samples):
            a, b = samples[max(i - 1, 0)], samples[min(i + 1, len(samples) - 1)]
            hits.append(index.near(x, z, BUILT_NEAR, (b[0] - a[0], b[1] - a[1])))
        share = sum(1 for h in hits if h) / len(hits)
        status = "built" if share >= BUILT_FULL else "partly" if share >= BUILT_PART else "not yet"
        res = {"status": status, "share": round(share * 100), "length": round(samples[-1][2])}
        found = [h[1] for h in hits if h]
        notes = []
        if found:
            pieces = Counter(sv.piece_name(e["title"]) for e in found)
            streets = Counter(e["streetName"] for e in found if e["streetName"])
            levels = Counter(level(e) for e in found)
            res["piece"] = pieces.most_common(1)[0][0]
            res["street"] = streets.most_common(1)[0][0] if streets else ""
            want = piece_of(r)
            if want and want.casefold() != res["piece"].casefold() and res["piece"] != "a Road Builder road":
                notes.append(f"the card said {want}")
            if r.get("tunnel") and levels["under"] < len(found) / 2:
                notes.append("not in a tunnel: the card said a tunnel")
            elif r.get("bridge") and levels["over"] < len(found) / 2:
                notes.append("not on a bridge: the card said a bridge")
            elif not r.get("tunnel") and not r.get("bridge") and levels["under"] > len(found) / 2:
                notes.append("built as a tunnel")
        if status == "partly":
            gap = [(x, z) for (x, z, _), h in zip(samples, hits) if not h]
            cx, cz = centre_of("roads", pts)
            gx, gz = sum(q[0] for q in gap) / len(gap), sum(q[1] for q in gap) / len(gap)
            if math.hypot(gx - cx, gz - cz) < 0.15 * samples[-1][2]:
                notes.insert(0, "a gap in the middle")
            else:
                notes.insert(0, f"missing toward the {sv.direction(gx - cx, gz - cz)}")
        if notes and status == "built":
            status = res["status"] = "different" if any(n.startswith(("the card said", "not in", "not on")) for n in notes) else status
        res["notes"] = notes
        return res

    def nodes_near(self, x, z, radius):
        out = []
        for nid, n in self.net.nodes.items():
            d = math.hypot((n.get("x") or 0) - x, (n.get("z") or 0) - z)
            if d <= radius:
                out.append((d, nid, n))
        return sorted(out, key=lambda q: q[0])

    def junction(self, j):
        pos = arr(j.get("position"))
        if len(pos) < 2:
            return None
        x, z = float(pos[0]), float(pos[1])
        typ = j.get("type") or "Normal"
        joins = [(d, n) for d, nid, n in self.nodes_near(x, z, JUNCTION_NEAR) if self.degree.get(nid, 0) >= 3]
        notes = []
        if typ == "Roundabout":
            ring = [n for d, nid, n in self.nodes_near(x, z, ROUNDABOUT_NEAR) if n.get("roundabout")]
            if ring:
                status = "built"
            elif joins:
                status = "different"
                notes.append("a plain junction" + (" with traffic lights" if any(n.get("lights") for _, n in joins) else "") +
                             ": the card said a roundabout")
            else:
                status = "not yet"
        elif typ in ("Underpass", "Overpass", "CrossingNoConnection"):
            levels = set()
            for (d, e) in [self.index.near(x + dx, z + dz, JUNCTION_NEAR) or (None, None) for dx, dz in ((0, 0), (25, 0), (-25, 0), (0, 25), (0, -25))]:
                if e:
                    levels.add(level(e))
            close = [p for p in self.roads if any(math.hypot(q[0] - x, q[1] - z) <= JUNCTION_NEAR for q in p["line"])]
            levels |= {level(e) for e in close}
            if len(levels) >= 2 and not [1 for d, n in joins if d < 20]:
                status = "built"
            elif joins and joins[0][0] < 20:
                status = "different"
                notes.append(f"the roads meet at a junction: the card said {('an ' + typ.lower()) if typ != 'CrossingNoConnection' else 'a crossing without a junction'}")
            elif close:
                status = "partly"
                notes.append("one road is there, the crossing isn't yet")
            else:
                status = "not yet"
        elif typ == "Interchange":
            ramps = [e for e in self.roads if sv.is_ramp(e) and any(math.hypot(q[0] - x, q[1] - z) <= 300 for q in e["line"])]
            status = "built" if len(ramps) >= 2 else "partly" if ramps else "not yet"
            if ramps:
                notes.append(f"{len(ramps)} ramp pieces")
        else:
            status = "built" if joins else "not yet"
        if status in ("built", "different") and joins:
            lights = any(n.get("lights") for _, n in joins)
            want = (piece_of(j) or "").casefold()
            if "light" in want and not lights:
                notes.append("no traffic lights: the card said lights")
                status = "different"
            elif lights and typ != "Roundabout" and "light" not in want:
                notes.append("with traffic lights")
        return {"status": status, "notes": notes}

    def area(self, a):
        poly = item_points(a)
        if len(poly) < 3:
            return None
        here = [b for b in self.buildings if inside(poly, b.get("x") or 0, b.get("z") or 0)]
        kinds = Counter(b.get("kind") for b in here)
        want = ZONE_KINDS.get(a.get("type"))
        cells = built_cells = 0
        for e in self.roads:
            zc = arr(e.get("zoned"))
            if len(zc) == 2 and inside(poly, *e["line"][len(e["line"]) // 2]):
                cells += zc[0] or 0
                built_cells += zc[1] or 0
        match = sum(v for k, v in kinds.items() if (k in want if want else k != "other"))
        districts = [d.get("name") for d in self.districts if len(arr(d.get("outline"))) >= 3 and
                     inside([(q[0], q[1]) for q in d["outline"]], *centre_of("areas", poly))]
        notes = []
        if here:
            notes.append(f"{len(here):,} buildings ({', '.join(f'{k} {v:,}' for k, v in kinds.most_common(3))})")
        if cells:
            notes.append(f"{cells:,} zoned cells, {built_cells:,} with a building")
        if districts:
            notes.append("in the district " + ", ".join(districts))
        status = "built" if match else "partly" if cells or here or districts else "not yet"
        if not here and not cells:
            notes.append("nothing zoned or built inside yet")
        return {"status": status, "notes": notes}

    def run(self, plans, every=False):
        out = []
        for p in plans:
            status = status_of(p.get("name"))
            if not every and status in ("Base", "Later"):
                continue
            items = []
            for kind in ("roads", "junctions", "areas"):
                for it in arr(p.get(kind)):
                    if not isinstance(it, dict) or it.get("existing") or not item_points(it):
                        continue
                    res = {"roads": self.road, "junctions": self.junction, "areas": self.area}[kind](it)
                    if res:
                        items.append(dict(res, name=it.get("name") or f"(a {kind[:-1]})", kind=kind[:-1],
                                          at=[round(v) for v in centre_of(kind, item_points(it))]))
            items.sort(key=lambda it: (int(re.match(r"\d+", step_number(it["name"]) or "").group()) if step_number(it["name"]) else 10 ** 6, it["name"]))
            out.append({"plan": p.get("name") or "?", "status": status, "items": items})
        return out


def built_markdown(results, path, snap):
    c = obj(snap.get("city"))
    lines = [f"# Built so far: {c.get('name') or '?'}\n",
             f"From {path.name}, taken {city.local_time(snap.get('taken'))} (in game {obj(c.get('date')).get('text') or '?'}). "
             "Roads count as built where a city road runs along the planned line (within 20 m).\n"]
    done = []
    for r in results:
        if not r["items"]:
            continue
        lines += [f"## {r['plan']}\n", "| Item | Built? | What's there |", "|---|---|---|"]
        for it in r["items"]:
            what = []
            if it["kind"] == "road" and it.get("piece"):
                what.append(it["piece"] + (f" on {it['street']}" if it.get("street") else "") + f" ({it['length']:,} m planned)")
            what += it.get("notes", [])
            mark = RESULT[it["status"]][1] + (f", {it['share']}%" if it["status"] == "partly" and "share" in it else "")
            lines.append(f"| {it['name']} | {mark} | {'; '.join(what)} |")
            if it["status"] == "built" and step_number(it["name"]):
                done.append(it["name"])
        lines.append("")
    if done:
        lines.append(f"**Built as planned** (the journal steps with the same number and words): {', '.join(done)}. Tick those "
                     "the Mayor hasn't; where their tick and this disagree, keep their tick and say why in a log line.")
    else:
        lines.append("Nothing in these plans is built as planned yet.")
    return "\n".join(lines)


def draw_built(snap, plans, results, out, width=1600, facts=None):
    terrain = sv.Terrain(snap)
    net = sv.Network(snap)
    facts = facts or sv.survey(snap)
    by_name = {(r["plan"], it["name"]): it for r in results for it in r["items"]}
    shown = [(p, kind, it) for p in plans for kind in ("areas", "roads", "junctions") for it in arr(p.get(kind))
             if isinstance(it, dict) and (p.get("name") or "?", it.get("name") or "") in by_name]
    pts = [q for _, _, it in shown for q in item_points(it)]
    b = sv.bounds([[x, x, z, z] for x, z in pts]) if pts else facts["start"]["box"]
    pad = max(200.0, 0.12 * max(b[1] - b[0], b[3] - b[2]))
    box = [b[0] - pad, b[1] + pad, b[2] - pad, b[3] + pad]
    c = obj(snap.get("city"))
    pic = sv.MapPicture(terrain, box, width, f"{c.get('name') or 'The city'}: built so far",
                        f"the plan against the city, {obj(c.get('date')).get('text') or ''}")
    sv.draw_network(pic, net, faint=True, names=pic.scale >= 0.25)
    pic.flush()
    used, notes = set(), []
    for p, kind, it in shown:
        res = by_name[(p.get("name") or "?", it.get("name") or "")]
        colour = RESULT[res["status"]][0]
        used.add(res["status"])
        q = item_points(it)
        if kind == "areas":
            pic.polygon(q, colour + (45,), outline=colour + (230,), width=4)
        elif kind == "roads":
            pic.line(q, colour, 7, dash=(10, 6) if res["status"] == "not yet" else None, casing=(30, 30, 30))
        else:
            pic.marker(*q[0], "circle", colour, r=12, outline=(20, 20, 20))
    pic.flush()
    for p, kind, it in shown:
        res = by_name[(p.get("name") or "?", it.get("name") or "")]
        num = step_number(it.get("name"))
        if num:
            x, z = centre_of(kind, item_points(it))
            pic.badge(x, z, num, fill=RESULT[res["status"]][0], r=15)
            notes.append(f"{it.get('name')}: {RESULT[res['status']][1].split(' ', 1)[1]}")
    legend = [("line", RESULT[k][0], RESULT[k][1].split(" ", 1)[1]) for k in RESULT if k in used]
    legend.append(("line", (90, 90, 90), "the city's roads"))
    notes.sort(key=lambda k_: (int(re.match(r"\d+", k_).group()) if re.match(r"\d+", k_) else 10 ** 6, k_))
    pic.finish(legend, notes[:14] + ([f"… and {len(notes) - 14} more"] if len(notes) > 14 else [])).save(out, optimize=True)
    return out


def draw_city_map(snap, out, then=None, view="city", title=None, width=1600, since_label="", facts=None):
    """The city now, with what was built since `then` marked."""
    terrain = sv.Terrain(snap)
    net = sv.Network(snap)
    tiles = sv.Tiles(snap)
    facts = facts or sv.survey(snap)
    st = facts["start"]
    c = obj(snap.get("city"))
    own = [e for e in net.by_kind("road") if not any(net.nodes.get(e.get(k), {}).get("outside") for k in ("a", "b"))]
    if view == "map":
        box = [*terrain.extent, *terrain.extent]
    elif view == "start" or not own:
        b = st["box"]
        pad = 0.25 * tiles.size
        box = [b[0] - pad, b[1] + pad, b[2] - pad, b[3] + pad]
    else:
        b = sv.bounds([[q[0], q[0], q[1], q[1]] for e in own for q in e["line"]])
        pad = max(250.0, 0.1 * max(b[1] - b[0], b[3] - b[2]))
        box = [b[0] - pad, b[1] + pad, b[2] - pad, b[3] + pad]
    new_edges, gone, placed = [], [], []
    if then is not None:
        nodes_now, nodes_then = city.node_places(snap), city.node_places(then)
        before = {city.edge_key(e, nodes_then): e for e in arr(then.get("edges")) if isinstance(e, dict) and not e.get("owned")
                  and e.get("kind") in city.ROAD_KINDS + city.RAIL_KINDS}
        now_keys = set()
        for e in net.edges:
            k = city.edge_key(e, nodes_now)
            now_keys.add(k)
            if k not in before and e.get("kind") in city.ROAD_KINDS + city.RAIL_KINDS:
                new_edges.append(e)
        gone = [sv.bezier(arr(e.get("pts"))) for k, e in before.items() if k not in now_keys and len(arr(e.get("pts"))) >= 2]
        prefabs = arr(snap.get("prefabs"))
        old_b = {(round(b.get("x", 0)), round(b.get("z", 0))) for b in arr(then.get("buildings")) if isinstance(b, dict)}
        zoned = ("residential", "commercial", "industrial", "office")
        placed = [b for b in arr(snap.get("buildings")) if isinstance(b, dict) and b.get("kind") not in zoned
                  and (round(b.get("x", 0)), round(b.get("z", 0))) not in old_b]
        for b in placed:
            b.setdefault("name", city.name_of(prefabs, b.get("prefab")))
    head = title or f"{c.get('name') or 'The city'}: {obj(c.get('date')).get('text') or 'now'}"
    sub = (f"built since {since_label}: blue" if new_edges else f"nothing new since {since_label}" if then is not None else "")
    pic = sv.MapPicture(terrain, box, width, head, sub)
    for t in tiles.owned() if not st["allOwned"] else []:
        pic.rect(t["box"], (30, 30, 30, 120), 2)
    for d in arr(snap.get("districts")):
        q = [(v[0], v[1]) for v in arr(obj(d).get("outline")) if len(v) >= 2]
        if len(q) >= 3:
            pic.polygon(q, (120, 90, 200, 30), outline=(120, 90, 200, 200), width=3)
    pic.flush()
    for line in gone:
        pic.line(line, (200, 40, 40, 200), 3, dash=(6, 6))
    sv.draw_network(pic, net, faint=False, names=False)
    pic.flush()
    for e in new_edges:
        pic.line(e["line"], (0, 140, 255), 7, casing=(10, 40, 90))
    pic.flush()
    for d in arr(snap.get("districts")):
        q = [(v[0], v[1]) for v in arr(obj(d).get("outline")) if len(v) >= 2]
        if len(q) >= 3 and obj(d).get("name"):
            pic.label(*centre_of("areas", q), d["name"], size=18, colour=(80, 50, 150))
    for b in placed[:40]:
        pic.marker(b.get("x", 0), b.get("z", 0), "square", (0, 140, 255), r=8)
    if pic.scale >= 0.2:
        done = set()
        for e in sorted(net.by_kind("road", "highway"), key=lambda e: -(e.get("length", 0) or 0)):
            name = e["streetName"]
            if name and name not in done and pic.visible(e["line"], margin=-40):
                m = e["line"][len(e["line"]) // 2]
                if pic.label(m[0], m[1], name, size=14, colour=(40, 40, 40)):
                    done.add(name)
    legend = [("line", (90, 90, 90), "roads"), ("line", (205, 40, 40), "highways")]
    if new_edges:
        legend.append(("line", (0, 140, 255), f"built since {since_label}"))
    if gone:
        legend.append(("dash", (200, 40, 40), "removed"))
    if placed:
        legend.append(("box", (0, 140, 255), "placed since"))
    if arr(snap.get("districts")):
        legend.append(("outline", (120, 90, 200), "districts"))
    notes = []
    if new_edges:
        notes.append(f"New: {city.km(sum(e.get('length', 0) or 0 for e in new_edges))} of road and track" +
                     (f", removed {len(gone)} pieces" if gone else "") + ".")
    named = [b.get("name") for b in placed if b.get("name")]
    if named:
        notes.append("Placed: " + ", ".join(f"{n} ×{k}" if k > 1 else n for n, k in Counter(named).most_common(8)) + ".")
    pic.finish(legend, notes).save(out, optimize=True)
    return {"new": len(new_edges), "gone": len(gone), "placed": len(placed)}


def slug(name):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (name or "item").casefold())).strip("-")[:48] or "item"


def main(argv):
    args = argv[1:]
    if len(args) >= 2 and args[0] == "map":
        return main_map(args[1], args[2:])
    if len(args) >= 2 and args[0] == "drawings":
        rest_ = args[2:]
        return main_drawings(args[1], rest_, lambda flag, default=None: rest_[rest_.index(flag) + 1]
                             if flag in rest_ and rest_.index(flag) + 1 < len(rest_) else default)
    if len(args) >= 3 and args[0] == "frame":
        rest_ = args[3:]
        return main_frame(args[1], args[2], rest_, lambda flag, default=None: rest_[rest_.index(flag) + 1]
                          if flag in rest_ and rest_.index(flag) + 1 < len(rest_) else default)
    if len(args) < 3 or args[0] not in ("check", "draw", "built", "cards", "grid", "ship", "road", "zone", "junction", "advance",
                                        "tunnel", "underpass", "interchange"):
        print(__doc__)
        return 2
    cmd, plan_path, src = args[0], args[1], args[2]
    rest = args[3:]

    def opt(flag, default=None):
        return rest[rest.index(flag) + 1] if flag in rest and rest.index(flag) + 1 < len(rest) else default

    if cmd == "ship":
        return main_ship(plan_path, src, rest, opt)
    if cmd == "advance":
        return main_advance(plan_path, src, rest, opt)
    if cmd == "grid":
        return main_grid(plan_path, city.load(sv.snapshot_file(src)), rest, opt)
    if cmd in ("road", "zone", "junction", "tunnel", "underpass", "interchange"):
        return {"road": main_road, "zone": main_zone, "junction": main_junction, "tunnel": main_tunnel, "underpass": main_underpass,
                "interchange": main_interchange}[cmd](plan_path, city.load(sv.snapshot_file(src)), rest, opt)
    if cmd in ("built", "cards"):
        path = sv.snapshot_file(src, "--start" in rest)
        snap = city.load(path)
        plans = load_plans(plan_path)
        if not arr(snap.get("edges")):
            print(f"{path.name} has no roads (cut for size, or an older snapshot), so nothing can be checked.")
            return 1
        if cmd == "built":
            results = Built(snap).run(plans, every="--all" in rest)
            print(built_markdown(results, path, snap))
            if opt("--json"):
                Path(opt("--json")).write_text(json.dumps({"snapshot": path.name, "taken": snap.get("taken"), "plans": results},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
            if opt("--out"):
                try:
                    draw_built(snap, plans, results, opt("--out"), width=min(max(int(opt("--width", 1600)), 600), 1600))
                    print(f"\nwrote {opt('--out')}")
                except ValueError:
                    print(f"\n{path.name} has no terrain part, so there's no picture.")
            return 0
        return main_cards(snap, plans, rest, opt)

    path = sv.snapshot_file(src, "--start" in rest)
    snap = city.load(path)
    plans = load_plans(plan_path)
    if cmd == "check":
        try:
            chk = Check(snap, plans, opt("--name"))
        except ValueError:
            print(f"{path.name} has no terrain part (City Manager 0.6 or later writes it), so the plan can't be checked.")
            return 1
        chk.run()
        print(chk.markdown(path.name))
        if opt("--json"):
            Path(opt("--json")).write_text(json.dumps({"plans": chk.results, "naming": chk.naming, "errors": chk.errors()},
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
        return 1 if chk.errors() else 0
    out = opt("--out")
    if not out:
        print("draw needs --out FILE.png")
        return 2
    only = [rest[i + 1] for i, a in enumerate(rest) if a == "--only" and i + 1 < len(rest)]
    width = min(max(int(opt("--width", 1600)), 600), 1600)
    try:
        draw(snap, plans, out, view=opt("--view", "plan"), only=only, around=opt("--around"), title=opt("--title"), width=width)
    except ValueError:
        print(f"{path.name} has no terrain part (City Manager 0.6 or later writes it), so there's nothing to draw on.")
        return 1
    print(f"wrote {out}")
    return 0


# --- a district's local streets, generated from a street the city has

ROAD_WIDTH = {2: 16.0, 4: 24.0, 6: 32.0}   # road-hierarchy.md: Two-Lane 16 m, Four-Lane 24 m, Six-Lane 32 m
LOT_DEPTHS = 96.0                          # two full-depth lots back to back
ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh",
            "twelfth"]


def width_of(title, lanes=None):
    """A road's width for spacing: from its lanes, or the lane word in its menu name."""
    if lanes:
        return ROAD_WIDTH.get(sum(lanes), 16.0 if sum(lanes) <= 2 else 24.0 if sum(lanes) <= 4 else 32.0)
    t = (title or "").casefold()
    for word, w in (("six-lane", 32.0), ("four-lane", 24.0), ("two-lane", 16.0)):
        if word in t:
            return w
    return 16.0


def spine_of(snap, street, near=None):
    """A street's straight line: (origin, unit along, length, width), from its two farthest-apart points, facing from
    the end nearest `near` (or its first end) to the other."""
    groups = city.street_groups(snap)
    names = [n for n in groups if n.casefold() == street.casefold()] or [n for n in groups if street.casefold() in n.casefold()]
    if not names:
        raise SystemExit(f"No street named {street!r} in the snapshot (`city.py streets` lists them).")
    es = groups[names[0]]
    pts = [tuple(q[:2]) for e in es for q in arr(e.get("pts"))]
    a, b = max(((p, q) for p in pts for q in pts), key=lambda pq: math.dist(*pq))
    if near is not None and math.dist(b, near) < math.dist(a, near):
        a, b = b, a
    L = math.dist(a, b)
    if L < 1:
        raise SystemExit(f"{names[0]} is too short to build along.")
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    lanes = Counter(tuple(arr(e.get("lanes"))) for e in es if len(arr(e.get("lanes"))) == 2).most_common(1)
    title = Counter(e["prefabName"] for e in es).most_common(1)[0][0]
    return a, u, L, width_of(title, lanes[0][0] if lanes else None), names[0]


def make_grid(origin, u, length, spine_w, side, rows, start=0.0, along=None, piece="Two-Lane Road", ends="both",
              block=None, number=None, name="New streets", zone=None):
    """The streets of a grid beside a straight spine. Returns (roads, area or None)."""
    n = (-u[1], u[0]) if side == "left" else (u[1], -u[0])
    w = width_of(piece)
    at = lambda s_, t_: [round(origin[0] + s_ * u[0] + t_ * n[0]), round(origin[1] + s_ * u[1] + t_ * n[1])]
    s0, s1 = start, start + (along if along else length - start)
    offsets = [spine_w / 2 + LOT_DEPTHS + w / 2 + i * (w + LOT_DEPTHS) for i in range(rows)]
    tag = (f"{number} " if number is not None else "") + name
    item = lambda label, pts: {"name": f"{tag}, {label}" if label[0].islower() else f"{tag} {label}", "class": "Local",
                               "piece": piece, "points": pts}
    roads = [item(f"{ORDINALS[i] if i < len(ORDINALS) else str(i + 1) + 'th'} street", [at(s0, t), at(s1, t)])
             for i, t in enumerate(offsets)]
    word = lambda s_: sv.direction(*((u[0], u[1]) if s_ > (s0 + s1) / 2 else (-u[0], -u[1])))
    if ends in ("both", "start"):
        roads.append(item(f"{word(s0)} end street", [at(s0, 0), at(s0, offsets[-1])]))
    if ends in ("both", "end"):
        roads.append(item(f"{word(s1)} end street", [at(s1, 0), at(s1, offsets[-1])]))
    if block:
        k, s_ = 1, s0 + block
        while s_ < s1 - block / 2:
            roads.append(item(f"cross street {k}", [at(s_, 0), at(s_, offsets[-1])]))
            k, s_ = k + 1, s_ + block
    area = None
    if zone:
        edge = spine_w / 2 + 2
        far = offsets[-1] + w / 2 + LOT_DEPTHS / 2
        area = {"name": tag, "type": zone, "polygon": [at(s0, edge), at(s1, edge), at(s1, far), at(s0, far)]}
    return roads, area


def add_to_plan(path, plan_name, roads, area=None):
    """Puts items into a plan of the file (made if missing), replacing items of the same name."""
    return add_items(path, plan_name, roads=roads, areas=[area] if area else [])


def add_items(path, plan_name, roads=(), areas=(), junctions=()):
    """Puts roads, areas and junctions into a plan of the file (made if missing, on top), replacing items of the same
    name; atomic."""
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {"plans": []}
    if not isinstance(doc, dict) or not isinstance(doc.get("plans"), list):
        raise SystemExit(f"{p.name} isn't a plan file with a plans list.")
    target = next((q for q in doc["plans"] if isinstance(q, dict) and q.get("name") == plan_name), None)
    if target is None:
        target = {"name": plan_name, "roads": [], "areas": [], "junctions": []}
        doc["plans"].insert(0, target)
    for kind, items in (("roads", list(roads)), ("areas", list(areas)), ("junctions", list(junctions))):
        names = {it["name"] for it in items}
        target[kind] = [x for x in arr(target.get(kind)) if not (isinstance(x, dict) and x.get("name") in names)] + items
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return target


# --- the street frame: places said along streets (frame.py), and builders that write plan items from them

def values(rest, flag):
    """The values after a flag, up to the next --flag."""
    if flag not in rest:
        return []
    out = []
    for a in rest[rest.index(flag) + 1:]:
        if a.startswith("--"):
            break
        out.append(a)
    return out


def road_class_of(edges):
    if any(e.get("kind") == "highway" for e in edges):
        return "Highway"
    lanes = max((sum(arr(e.get("lanes"))) for e in edges if len(arr(e.get("lanes"))) == 2), default=2)
    return "Arterial" if lanes >= 6 else "Collector" if lanes >= 4 else "Local"


def main_frame(src, street, rest, opt):
    """plan.py frame <src> "<street>": the street as a frame for places, with what's along it."""
    import frame
    snap = city.load(sv.snapshot_file(src))
    st = frame.Streets(snap)
    name = st.find(street)
    parts = st.parts(name)
    only = int(opt("--part")) if opt("--part") else None
    part_of = {e.get("id"): p.index for p in parts for e in p.edges}
    inc = st.net.incident()
    print(f"# {name}: {len(parts)} part{'s' if len(parts) != 1 else ''}\n")
    print("A street name can cover several roads; each part runs straight on through its junctions. Places on a part:\n"
          f"`{name}@<metres along>` (negative: from the far end; `start`, `mid`, `end`), then `+<metres>` to its left or "
          f"`-<metres>` to its right; `{name}/2@…` for part 2; `{name} x <street>` where two streets meet.\n")
    for p in parts:
        if only and p.index != only:
            continue
        ref = name if p.index == 1 else f"{name}/{p.index}"
        x0, z0 = p.pts[0]
        print(f"## Part {p.index} (`{ref}@…`): {city.km(p.length)}, {p.heading_word()}\n")
        print(f"Starts at its {p.start_word()} end (x {x0:.0f}, z {z0:.0f}); left is {p.left_word()}.\n")
        print("| Along | What's there |\n|---|---|")
        mine = {e.get("id") for e in p.edges}
        for s, node in p.joints:
            n = st.net.nodes.get(node) or {}
            others = defaultdict(set)
            for e in inc.get(node, []):
                if e.get("id") in mine or e.get("kind") not in ("road", "highway", "train", "tram", "subway"):
                    continue
                line = e.get("line") or []
                if len(line) < 2:
                    continue
                away = line[min(2, len(line) - 1)] if e.get("a") == node else line[max(-3, -len(line))]
                _, t, _ = p.project(*away)
                side = "left" if t > 2 else "right" if t < -2 else "ahead"
                label = e.get("streetName") or e.get("title") or e.get("kind")
                if e.get("streetName") == name and part_of.get(e.get("id")):
                    label = f"{name} (part {part_of[e['id']]})"
                elif e.get("kind") in ("train", "tram", "subway"):
                    label = f"{label} ({e['kind']})"
                others[label].add(side)
            what = []
            for label, sides in sorted(others.items()):
                if sides >= {"left", "right"}:
                    where = "across"
                else:
                    sd = next(iter(sides))
                    where = f"to the {sd} ({p.left_word(s) if sd == 'left' else sv.direction(*[-v for v in sv_left(p, s)])})" if sd != "ahead" else "straight on"
                what.append(f"{label}, {where}")
            is_end = s in (p.joints[0][0], p.joints[-1][0])
            if n.get("outside"):
                what.insert(0, "leaves the map")
            elif is_end and not what:
                what.append("the end: open (nothing joins)")
            elif is_end:
                what[0] = "the end: " + what[0]
            if what:
                print(f"| {s:,.0f} | {'; '.join(what)} |")
        print()
        runs = []
        for i, e in enumerate(p.edges):
            a, b = p.joints[i][0], p.joints[i + 1][0] if i + 1 < len(p.joints) else p.length
            key = (e.get("title") or "?", city.lanes_text(e), "tunnel" if e.get("tunnel") else "bridge" if e.get("bridge") else "")
            if runs and runs[-1][0] == key:
                runs[-1][2] = b
            else:
                runs.append([key, a, b])
        print("Pieces: " + "; ".join(f"{a:,.0f}–{b:,.0f} {k[0]} ({k[1]})" + (f", {k[2]}" if k[2] else "") for k, a, b in runs) + ".\n")
    return 0


def sv_left(p, s):
    _, _, ux, uz = p.at(min(max(s, 0.0), p.length))
    return (-uz, ux)


def builder_common(rest, opt):
    plan_name, name = opt("--plan"), opt("--name")
    if not plan_name or not name:
        raise SystemExit("needs --plan \"<Status> · <Topic>\" and --name \"<number> <words>\"")
    if status_of(plan_name) in ("Now", "Next") and not step_number(name):
        print(f"Note: {name!r} has no step number, so it gets no build card (`<number> <words>`, guides.md).")
    return plan_name, name


def main_road(plan_path, snap, rest, opt):
    """plan.py road: one road from places along streets."""
    import frame
    plan_name, name = builder_common(rest, opt)
    st = frame.Streets(snap)
    if opt("--along"):
        p = st.part(*split_part(opt("--along")))
        pts = p.line(p.s_of(opt("--from", "start")), p.s_of(opt("--to", "end")), float(opt("--offset", 0)))
        how = f"along {opt('--along')} from {opt('--from', 'start')} to {opt('--to', 'end')}, {opt('--offset', 0)} m to its left"
    elif opt("--off"):
        p = st.part(*split_part(opt("--off")))
        s0 = p.s_of(opt("--at", "start"))
        side = opt("--side", "left")
        if side not in ("left", "right"):
            raise SystemExit("--side is left or right")
        L, ang = float(opt("--length", 200)), math.radians(float(opt("--angle", 90)))
        x, z, ux, uz = p.at(s0)
        nx, nz = (-uz, ux) if side == "left" else (uz, -ux)
        dx, dz = math.cos(ang) * ux + math.sin(ang) * nx, math.cos(ang) * uz + math.sin(ang) * nz
        pts = [(x, z), (x + L * dx, z + L * dz)]
        how = f"off {opt('--off')} at {opt('--at', 'start')} m to its {side}, {L:,.0f} m"
    else:
        specs = values(rest, "--through")
        if len(specs) < 2 and not (specs and opt("--to-street")):
            raise SystemExit("a road needs --through PLACE PLACE…, --along STREET --from S --to S [--offset T], or "
                             "--off STREET --at S --side left|right --length L (places: frame.py)")
        pts = [st.place(x) for x in specs]
        how = "through " + ", ".join(specs)
    if opt("--to-street"):
        last = pts[-1]
        best = min(((q.project(*last), q) for q in st.parts(opt("--to-street"))), key=lambda t: t[0][2])
        (s1, _, d), q = best
        pts = pts + [q.point(s1)] if d > 1 else pts
        how += f", then on to {opt('--to-street')} ({d:,.0f} m)"
    road = {"name": name, "class": opt("--class", "Local"), "points": [[round(x, 1), round(z, 1)] for x, z in pts]}
    if opt("--piece"):
        road["piece"] = opt("--piece")
    for flag in ("--tunnel", "--bridge"):
        if flag in rest:
            road[flag[2:]] = True
    add_items(plan_path, plan_name, roads=[road])
    print(f"Added to {plan_name!r} in {Path(plan_path).name}: road {name!r} ({road.get('piece') or road['class']}, "
          f"{length(pts):,.0f} m), {how}.\nCheck it: plan.py check {Path(plan_path).name} <src>.")
    return 0


def split_part(text):
    m = re.match(r"^(.*?)(?:\s*/\s*(\d+))?\s*$", text)
    return m.group(1), m.group(2)


def main_zone(plan_path, snap, rest, opt):
    """plan.py zone: an area, as a band along a street or a polygon of places."""
    import frame
    plan_name, name = builder_common(rest, opt)
    typ = opt("--type", "Custom")
    if typ not in cityplan.AREA_TYPES:
        raise SystemExit(f"--type is one of {', '.join(sorted(cityplan.AREA_TYPES))}")
    st = frame.Streets(snap)
    if opt("--along"):
        p = st.part(*split_part(opt("--along")))
        side = opt("--side", "left")
        if side not in ("left", "right"):
            raise SystemExit("--side is left or right")
        sign = 1.0 if side == "left" else -1.0
        inner = float(opt("--gap", p.width() / 2 + 1))
        depth = float(opt("--depth", 48))
        s0, s1 = p.s_of(opt("--from", "start")), p.s_of(opt("--to", "end"))
        poly = p.line(s0, s1, sign * inner, step=40.0) + p.line(s1, s0, sign * (inner + depth), step=40.0)
        how = f"along {opt('--along')} from {opt('--from', 'start')} to {opt('--to', 'end')}, its {side} side, {depth:,.0f} m deep"
    else:
        specs = values(rest, "--polygon")
        if len(specs) < 3:
            raise SystemExit("an area needs --along STREET --from S --to S --side left|right [--depth 48] or --polygon PLACE PLACE PLACE…")
        poly = [st.place(x) for x in specs]
        how = "through " + ", ".join(specs)
    area = {"name": name, "type": typ, "polygon": [[round(x, 1), round(z, 1)] for x, z in poly]}
    add_items(plan_path, plan_name, areas=[area])
    print(f"Added to {plan_name!r} in {Path(plan_path).name}: area {name!r} ({typ}), {how}.\n"
          f"Check it: plan.py check {Path(plan_path).name} <src>.")
    return 0


def main_junction(plan_path, snap, rest, opt):
    """plan.py junction: a junction marker where two streets meet, or at a place between two of the plan's roads."""
    import frame
    plan_name, name = builder_common(rest, opt)
    typ = opt("--type", "Normal")
    if typ not in cityplan.JUNCTION_TYPES:
        raise SystemExit(f"--type is one of {', '.join(sorted(cityplan.JUNCTION_TYPES))}")
    st = frame.Streets(snap)
    at = opt("--at")
    if not at:
        raise SystemExit("a junction needs --at \"<street> x <street>\", or --at PLACE --roads ROAD ROAD (two roads of its plan)")
    x, z = st.place(at)
    roads = []
    pair = values(rest, "--roads")
    if frame.CROSS.search(at) and "@" not in at and not pair:
        pair = []
        for street in (q.strip() for q in frame.CROSS.split(at, maxsplit=1)):
            nm = st.find(street)
            part = min(st.parts(nm), key=lambda q: q.project(x, z)[2])
            roads.append({"name": nm, "class": road_class_of(part.edges), "existing": True,
                          "points": [[round(a, 1), round(b, 1)] for a, b in part.line(0, part.length, step=60.0)]})
            pair.append(nm)
    if len(pair) != 2:
        raise SystemExit("--roads names two roads of the plan (the junction's own)")
    doc = json.loads(Path(plan_path).read_text(encoding="utf-8-sig")) if Path(plan_path).exists() else {"plans": []}
    target = next((q for q in arr(doc.get("plans")) if isinstance(q, dict) and q.get("name") == plan_name), {})
    have = {r.get("name") for r in arr(target.get("roads")) if isinstance(r, dict)}
    roads = [r for r in roads if r["name"] not in have]
    missing = [n for n in pair if n not in have and n not in {r["name"] for r in roads}]
    if missing:
        raise SystemExit(f"{', '.join(map(repr, missing))} isn't a road of {plan_name!r}: add it first, or use --at \"<street> x <street>\".")
    j = {"name": name, "type": typ, "position": [round(x, 1), round(z, 1)], "road_a": pair[0], "road_b": pair[1]}
    if opt("--piece"):
        j["piece"] = opt("--piece")
    add_items(plan_path, plan_name, roads=roads, junctions=[j])
    print(f"Added to {plan_name!r} in {Path(plan_path).name}: junction {name!r} ({j.get('piece') or typ}) at {at}"
          + (f", with {' and '.join(r['name'] for r in roads)} drawn as existing roads" if roads else "")
          + f".\nCheck it: plan.py check {Path(plan_path).name} <src>.")
    return 0


# --- templates: tunnels, underpasses and interchanges (interchanges.md), built on the street frame

SLIP = "One-Lane One-Way Highway"
MAX_GRADE = 0.20      # the game refuses steeper ramps
RAMP_GRADE = 0.12     # a ramp's default slope


def clear_half(width):
    """How far either side of a crossed road's centre line the tunnel runs: just past its edge (interchanges.md: about
    15 m from a highway's centre), so the ramps' open cuts stop short of it."""
    return max(15.0, width / 2 + 4)


def under_piece(edges, given, fallback, notes):
    """The road piece for a street going underground: the one given, else the street's own, unless that's a gravel
    road (the game builds those on the ground only)."""
    if given:
        return given
    title = Counter(e.get("title") for e in edges).most_common(1)[0][0] if edges else None
    if title and "gravel" in title.casefold():
        notes.append(f"the street is a {title}, which can't go underground: the underpass uses a {fallback} (change it with the piece option)")
        return fallback
    return title or fallback


def line_part(pts, name="new road"):
    import frame
    return frame.Part(name, pts, [], [(0, None), (len(pts) - 1, None)])


def crossing_on(line, other):
    """Where a line first crosses another (frame parts): (s on the line, s on the other, x, z) or None."""
    import frame
    for i, (a, b) in enumerate(zip(line.pts, line.pts[1:])):
        for k, (c, d) in enumerate(zip(other.pts, other.pts[1:])):
            hit = frame.seg_cross(a, b, c, d)
            if hit:
                return (line.cum[i] + math.dist(a, hit), other.cum[k] + math.dist(c, hit), hit[0], hit[1])
    return None


def under_items(line, s_c, half, ramp, depth, piece, cls, tag, under_name=None):
    """A road going under something at s_c on its line: down-ramp, tunnel (2 x half long), up-ramp. Returns (roads,
    the tunnel's name, notes)."""
    end = depth - 1 if depth >= 12 else depth
    a, b, c, d = s_c - half - ramp, s_c - half, s_c + half, s_c + half + ramp
    if a < -1 or d > line.length + 1:
        raise SystemExit(f"The road is too short for this: it needs {2 * (half + ramp):,.0f} m around the crossing "
                         f"({line.length:,.0f} m from {max(0.0, s_c):,.0f}); give a longer line or a shorter --ramp.")
    grade = end / ramp
    notes = [f"ramps of {ramp:,.0f} m at {grade:.0%}"]
    if grade > MAX_GRADE:
        raise SystemExit(f"{ramp:,.0f} m ramps to {end:g} m down are {grade:.0%}: the game refuses over 20%. Longer --ramp, or a shallower --depth.")
    if grade > 0.17:
        notes.append("steep: build the ramp first and read its slope in game")
    under = f" under {under_name}" if under_name else ""
    mk = lambda role, s0, s1, extra: dict({"name": f"{tag}, {role}", "class": cls, "piece": piece,
                                           "points": [[round(x, 1), round(z, 1)] for x, z in line.line(s0, s1, step=30.0)]}, **extra)
    roads = [mk("down-ramp", a, b, {"depth": [0, end]}), mk("tunnel" + under, b, c, {"tunnel": True, "depth": depth}),
             mk("up-ramp", c, d, {"depth": [end, 0]})]
    return roads, roads[1]["name"], notes


def existing_item(st, name, near):
    part = min(st.parts(name), key=lambda q: q.project(*near)[2])
    return {"name": st.find(name), "class": road_class_of(part.edges), "existing": True,
            "points": [[round(a, 1), round(b, 1)] for a, b in part.line(0, part.length, step=60.0)]}, part


def template_line(st, rest, opt):
    """The new road's line: --along STREET [--from S --to S] or --through PLACE PLACE…"""
    if opt("--along"):
        p = st.part(*split_part(opt("--along")))
        s0, s1 = p.s_of(opt("--from", "start")), p.s_of(opt("--to", "end"))
        return line_part(p.line(s0, s1, step=20.0), p.name), p.edges
    specs = values(rest, "--through")
    if len(specs) < 2:
        raise SystemExit("give the road's line: --along STREET [--from S --to S] or --through PLACE PLACE…")
    return line_part([st.place(x) for x in specs]), []


def tag_of(opt):
    number, name = opt("--number"), opt("--name")
    if not number or not name:
        raise SystemExit("needs --number N (its step number) and --name WORDS")
    return number, name


def main_tunnel(plan_path, snap, rest, opt):
    """plan.py tunnel: a long tunnel along a line (a Seattle-style bored road): ramp down, tunnel, ramp up."""
    import frame
    plan_name = opt("--plan")
    if not plan_name:
        raise SystemExit("needs --plan \"<Status> · <Topic>\"")
    number, name = tag_of(opt)
    st = frame.Streets(snap)
    line, _ = template_line(st, rest, opt)
    depth, ramp = float(opt("--depth", 13)), float(opt("--ramp", round(12 / RAMP_GRADE, -1)))
    half = (line.length - 2 * ramp) / 2
    if half < 10:
        raise SystemExit(f"{line.length:,.0f} m is too short for a tunnel with {ramp:,.0f} m ramps.")
    roads, tunnel, notes = under_items(line, line.length / 2, half, ramp, depth, opt("--piece", "Four-Lane Road"), opt("--class", "Arterial"), f"{number} {name}")
    add_items(plan_path, plan_name, roads=roads)
    print(f"Added to {plan_name!r}: {name} as step {number}: down-ramp, a {2 * half:,.0f} m tunnel about {depth:g} m down, up-ramp "
          f"({'; '.join(notes)}).\nCheck it: plan.py check {Path(plan_path).name} <src>.")
    return 0


def main_underpass(plan_path, snap, rest, opt):
    """plan.py underpass: a street under a highway, a railway or another road, no access (interchanges.md)."""
    import frame
    plan_name = opt("--plan")
    if not plan_name or not opt("--under"):
        raise SystemExit("needs --plan \"<Status> · <Topic>\" and --under \"<road or railway>\"")
    number, name = tag_of(opt)
    st = frame.Streets(snap)
    line, edges = template_line(st, rest, opt)
    under = opt("--under")
    rails = [e for e in st.net.by_kind("train", "tram", "subway") if under.casefold() in (e.get("streetName") or e.get("title") or "").casefold()]
    if rails:
        other = line_part([q for e in rails for q in e["line"]], under)
        hit, ex = None, None
        for e in rails:
            hit = crossing_on(line, line_part(e["line"]))
            if hit:
                break
        width = 16.0
    else:
        ex, other = existing_item(st, under, line.point(line.length / 2))
        hit = crossing_on(line, other)
        width = other.width() + (8.0 if ex["class"] == "Highway" else 0.0)
        under = ex["name"]
    if not hit:
        raise SystemExit(f"The line doesn't cross {under}: give a line that does (`plan.py frame` shows where streets run).")
    half = float(opt("--span", 0)) / 2 or clear_half(width)
    ramp = float(opt("--ramp", round(12 / RAMP_GRADE, -1)))
    pre = []
    piece = under_piece(edges, opt("--piece"), "Two-Lane Road", pre)
    roads, tunnel, notes = under_items(line, hit[0], half, ramp, float(opt("--depth", 13)), piece,
                                       road_class_of(edges) if edges else opt("--class", "Collector"), f"{number} {name}", under)
    notes = pre + notes
    juncs = []
    if ex:
        roads.append(ex)
        juncs.append({"name": f"{number} {name}, under {under}", "type": "Underpass", "position": [round(hit[2], 1), round(hit[3], 1)],
                      "road_a": tunnel, "road_b": under})
    add_items(plan_path, plan_name, roads=roads, junctions=juncs)
    print(f"Added to {plan_name!r}: {name} as step {number}: {piece} under {under}, a {2 * half:,.0f} m tunnel about "
          f"{opt('--depth', 13)} m down with {'; '.join(notes)}.\nCheck it: plan.py check {Path(plan_path).name} <src>.")
    return 0


def main_interchange(plan_path, snap, rest, opt):
    """plan.py interchange --kind diamond|stem: interchanges.md's Template A (a tunnel diamond) or B (an underground
    stem), drawn from the highway's own frame. Right-hand traffic unless the snapshot says left."""
    import frame
    plan_name, kind = opt("--plan"), opt("--kind", "diamond")
    if not plan_name or not opt("--highway"):
        raise SystemExit("needs --plan \"<Status> · <Topic>\" and --highway \"<highway>\"")
    if kind not in ("diamond", "stem"):
        raise SystemExit("--kind is diamond (a street crossing with access) or stem (a road ending at the highway)")
    number, name = tag_of(opt)
    n = int(re.match(r"\d+", number).group()) if re.match(r"\d+", number) else None
    nb = lambda k: str(n + k) if n is not None else f"{number}{'abc'[k]}"
    st = frame.Streets(snap)
    left = bool(obj(snap.get("map")).get("leftHandTraffic"))
    R = 1.0 if left else -1.0          # the side of the highway (t sign) that traffic going +s drives on
    depth, piece = float(opt("--depth", 13)), opt("--piece", "Four-Lane Road")
    roads, juncs, notes = [], [], []
    if kind == "diamond":
        line, edges = template_line(st, rest, opt) if (opt("--along") or values(rest, "--through")) else (None, [])
        if line is None and opt("--street"):
            sp = st.part(*split_part(opt("--street")))
            line, edges = line_part(sp.pts, sp.name), sp.edges
        if line is None:
            raise SystemExit("a diamond needs the crossing street: --street STREET, --along STREET [--from --to] or --through PLACE PLACE")
        ex, hw = existing_item(st, opt("--highway"), line.point(line.length / 2))
        hit = crossing_on(line, hw)
        if not hit:
            raise SystemExit(f"That street doesn't cross {ex['name']}.")
        s_c = hit[1]
        F, half = float(opt("--frontage-gap", 90)), clear_half(hw.width() + 8)
        # where the street is F metres from the highway on each side: the frontage junctions
        ts = [(s, hw.project(*line.point(s))[1]) for s in [hit[0] + k for k in range(-400, 401, 5)] if 0 <= s <= line.length]
        near = [s for s, t in ts if s < hit[0] and abs(t) >= F]
        far = [s for s, t in ts if s > hit[0] and abs(t) >= F]
        if not near or not far:
            raise SystemExit(f"The street must run at least {F:,.0f} m on both sides of {ex['name']} for the frontage streets.")
        sa, sb = max(near), min(far)
        ramp = min(hit[0] - half - sa, sb - hit[0] - half)
        tag = f"{number} {name}"
        street_piece = under_piece(edges, opt("--street-piece"), piece, notes)
        under, tunnel, un = under_items(line, hit[0], half, ramp, depth, street_piece, road_class_of(edges) if edges else "Arterial", tag, ex["name"])
        roads += under + [ex]
        notes += un
        juncs.append({"name": f"{tag}, interchange", "type": "Interchange", "position": [round(hit[2], 1), round(hit[3], 1)],
                      "road_a": tunnel, "road_b": ex["name"]})
        Lf = float(opt("--frontage-length", 260))
        fr_piece = opt("--frontage-piece", "Two-Lane Road")
        for side in (1.0, -1.0):
            word = hw.left_word(s_c) if side > 0 else sv.direction(*[-v for v in sv_left(hw, s_c)])
            roads.append({"name": f"{nb(1)} {name}, {word} frontage street", "class": "Collector", "piece": fr_piece,
                          "points": [[round(x, 1), round(z, 1)] for x, z in hw.line(s_c - Lf, s_c + Lf, side * F, step=40.0)]})
        # slip roads, in the direction they're driven: off before the crossing, on after it, each on its traffic side
        P = lambda s_, t_: [round(v, 1) for v in hw.point(s_c + s_, t_)]
        plus, minus = hw.heading_word(), sv.direction(*[-(hw.pts[-1][i] - hw.pts[0][i]) for i in (0, 1)])
        for direction, word in ((1.0, plus), (-1.0, minus)):
            t = R * direction
            g = lambda s_: s_ * direction
            roads.append({"name": f"{nb(2)} {name}, {word}-bound off-ramp", "class": "Highway", "piece": SLIP,
                          "points": [P(g(-320), t * 8), P(g(-170), t * 30), P(g(-110), t * F)]})
            roads.append({"name": f"{nb(2)} {name}, {word}-bound on-ramp", "class": "Highway", "piece": SLIP,
                          "points": [P(g(110), t * F), P(g(170), t * 30), P(g(320), t * 8)]})
        summary = (f"{name}: the street under {ex['name']} (step {number}), frontage streets {F:,.0f} m out (step {nb(1)}), "
                   f"four slip roads (step {nb(2)})")
    else:
        if not opt("--from"):
            raise SystemExit("a stem needs --from PLACE: where the road comes from, on one side of the highway")
        start = st.place(opt("--from"))
        ex, hw = existing_item(st, opt("--highway"), start)
        s_c, t0, _ = hw.project(*start)
        side = 1.0 if t0 > 0 else -1.0
        J, ramp = 32.0, float(opt("--ramp", round(12 / RAMP_GRADE, -1)))
        if abs(t0) < J + ramp:
            raise SystemExit(f"--from is {abs(t0):,.0f} m from the highway: the stem needs {J + ramp:,.0f} m on its side.")
        stem = line_part([hw.point(s_c, t0), hw.point(s_c, -side * J)])
        tag = f"{number} {name}"
        L = stem.length
        end = depth - 1
        mk = lambda role, s0, s1, extra: dict({"name": f"{tag}, {role}", "class": "Arterial", "piece": piece,
                                               "points": [[round(x, 1), round(z, 1)] for x, z in stem.line(s0, s1, step=30.0)]}, **extra)
        a = L - 2 * J - ramp
        if a > 1:
            roads.append(mk("approach", 0, a, {}))
        roads += [mk("down-ramp", a, L - 2 * J, {"depth": [0, end]}), mk(f"tunnel under {ex['name']}", L - 2 * J, L, {"tunnel": True, "depth": depth})]
        notes.append(f"ramp of {ramp:,.0f} m at {end / ramp:.0%}")
        jn, jf = hw.point(s_c, side * J), hw.point(s_c, -side * J)
        roads.append(ex)
        for label, pt in (("near", jn), ("far", jf)):
            juncs.append({"name": f"{tag}, {label} underground junction", "type": "Normal", "position": [round(pt[0], 1), round(pt[1], 1)],
                          "road_a": roads[-2]["name"], "road_b": ex["name"], "piece": "stop signs or none (take the game's lights off)"})
        P = lambda s_, t_: [round(v, 1) for v in hw.point(s_c + s_, t_)]
        plus, minus = hw.heading_word(), sv.direction(*[-(hw.pts[-1][i] - hw.pts[0][i]) for i in (0, 1)])
        for direction, word in ((1.0, plus), (-1.0, minus)):
            t = R * direction
            g = lambda s_: s_ * direction
            roads.append({"name": f"{nb(1)} {name}, {word}-bound off-ramp", "class": "Highway", "piece": SLIP, "depth": [0, depth],
                          "points": [P(g(-260), t * 8), P(g(-120), t * 22), P(g(-35), t * J), P(0, t * J)]})
            roads.append({"name": f"{nb(1)} {name}, {word}-bound on-ramp", "class": "Highway", "piece": SLIP, "depth": [depth, 0],
                          "points": [P(0, t * J), P(g(35), t * J), P(g(120), t * 22), P(g(260), t * 8)]})
        summary = f"{name}: the stem under {ex['name']} (step {number}), four slip roads down to its underground junctions (step {nb(1)})"
    add_items(plan_path, plan_name, roads=roads, junctions=juncs)
    print(f"Added to {plan_name!r}: {summary}; {'; '.join(notes)}; {'left' if left else 'right'}-hand traffic.\n"
          f"Check it: plan.py check {Path(plan_path).name} <src>, then look at it: plan.py draw … --around \"{roads[0]['name']}\".")
    return 0


def main_grid(plan_path, snap, rest, opt):
    def pair(text, what):
        try:
            a, b = (float(v) for v in text.split(","))
            return a, b
        except (ValueError, AttributeError):
            raise SystemExit(f"{what} takes two numbers, like 120,-340")
    side, rows = opt("--side"), opt("--rows")
    if side not in ("left", "right") or not (rows or "").isdigit() or not 1 <= int(rows) <= 12:
        raise SystemExit("grid needs --side left|right and --rows 1 to 12")
    near = pair(opt("--from"), "--from") if opt("--from") else None
    if opt("--along"):
        origin, u, L, spine_w, spine = spine_of(snap, opt("--along"), near)
    elif opt("--origin") and opt("--dir"):
        origin, d = pair(opt("--origin"), "--origin"), pair(opt("--dir"), "--dir")
        m = math.hypot(*d) or 1.0
        u, L, spine_w, spine = (d[0] / m, d[1] / m), float(opt("--length", 400)), width_of(opt("--spine-piece", "")), "the line given"
    else:
        raise SystemExit("grid needs --along \"<street>\", or --origin X,Z with --dir DX,DZ")
    start = float(opt("--start", 0))
    along = float(opt("--length")) if opt("--length") else None
    if start < 0 or start >= L and not opt("--origin"):
        raise SystemExit(f"--start must be between 0 and the street's length ({L:.0f} m)")
    roads, area = make_grid(origin, u, L, spine_w, side, int(rows), start, along, opt("--piece", "Two-Lane Road"),
                            opt("--ends", "both"), float(opt("--block")) if opt("--block") else None,
                            opt("--number"), opt("--name", "New streets"), opt("--zone"))
    plan_name = opt("--plan", "Now · New streets")
    add_to_plan(plan_path, plan_name, roads, area)
    first = roads[0]["points"]
    print(f"Added to {Path(plan_path).name}, plan {plan_name!r}: {len(roads)} streets beside {spine} (spine {spine_w:.0f} m wide), "
          f"rows {spine_w / 2 + LOT_DEPTHS + width_of(opt('--piece', 'Two-Lane Road')) / 2:.0f} m from it and "
          f"{width_of(opt('--piece', 'Two-Lane Road')) + LOT_DEPTHS:.0f} m apart, {math.dist(*first):.0f} m long"
          + (f", and the {area['type']} area {area['name']!r}" if area else "") + ".")
    for r in roads:
        print(f"- {r['name']} ({r['piece']}): {r['points'][0]} → {r['points'][-1]}")
    print("\nNext: `plan.py check` (and `draw`), as for any plan.")
    return 0


def make_cards(snap, plans, out, width=900, facts=None, only=()):
    """A close-up for every numbered item in the Now and Next plans (or the plans in `only`): rows of
    (name, plan name, file, x, z, zoom)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    facts = facts or sv.survey(snap)
    rows, seen = [], set()
    for p in plans:
        status = status_of(p.get("name"))
        if (only and p.get("name") not in only) or (not only and status not in ("Now", "Next", None)):
            continue
        for kind in ("roads", "junctions", "areas"):
            for it in arr(p.get(kind)):
                if not isinstance(it, dict) or it.get("existing") or not step_number(it.get("name")) or not item_points(it):
                    continue
                name = it["name"]
                if name.casefold() in seen:
                    continue
                seen.add(name.casefold())
                file = f"card-{slug(name)}.png"
                draw(snap, plans, out / file, around=name, width=width, facts=facts)
                q = item_points(it)
                x, z = centre_of(kind, q)
                b = sv.bounds([[a, a, c, c] for a, c in q])
                zoom = round(min(max(1.4 * max(b[1] - b[0], b[3] - b[2], 300.0), 400.0), 4000.0), -1)
                rows.append((name, p.get("name"), file, x, z, zoom))
    return rows


# --- ship: the plan file to the game in one run

REGION_START = "# >>> build cards from plan.py ship"
REGION_END = "# <<< build cards"
JUNCTION_WORDS = {"Roundabout": "roundabout", "Interchange": "interchange", "Underpass": "underpass", "Overpass": "overpass",
                  "CrossingNoConnection": "crossing with no junction", "Normal": "junction"}


def card_groups(plans, names):
    """The numbered items of the plans named, one group per step number (`7 West, first street` and `7 Riverside homes`
    are both step 7), in build order: [(plan, number, [(kind, item)])]."""
    groups = {}
    for p in plans:
        if p.get("name") not in names:
            continue
        for kind in ("roads", "junctions", "areas"):
            for it in arr(p.get(kind)):
                if not isinstance(it, dict) or it.get("existing") or not item_points(it):
                    continue
                n = step_number(it.get("name"))
                if n:
                    groups.setdefault((p.get("name"), n.casefold()), (p, n, []))[2].append((kind, it))

    def order(g):
        m = re.match(r"(\d+)(.*)", g[1])
        return (names.index(g[0].get("name")), int(m.group(1)), m.group(2))
    return sorted(groups.values(), key=order)


def depth_words(d):
    if isinstance(d, (int, float)):
        return f"about {d:g} m down"
    if isinstance(d, list) and len(d) == 2 and all(isinstance(v, (int, float)) for v in d):
        a, b = d
        return f"down to {b:g} m" if a == 0 else f"up from {a:g} m" if b == 0 else f"from {a:g} to {b:g} m down"
    return ""


def a_word(word):
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def card_note(items):
    """A build card's note when the plan gives none: the pieces and how to build them. Pieces with a depth (tunnels,
    ramps) are said one by one, in order: "down-ramp: Four-Lane Road, about 110 m, down to 12 m"."""
    roads, bits = Counter(), []
    metres = Counter()
    for kind, it in items:
        if kind == "roads" and it.get("depth") is not None:
            role = str(it.get("name") or "").split(", ", 1)[-1] if ", " in str(it.get("name") or "") else ""
            L = length(item_points(it))
            what = ", ".join(x for x in ((piece_of(it) or "road") + (" in a tunnel" if it.get("tunnel") else ""),
                                         f"about {round(L, -1) if L >= 100 else round(L):,.0f} m", depth_words(it.get("depth"))) if x)
            bits.append(f"{role}: {what}" if role else what)
            continue
        if kind == "roads":
            key = (piece_of(it) or f"{it.get('class', 'Local').lower()} road") + (" in a tunnel" if it.get("tunnel") else " on a bridge" if it.get("bridge") else "")
            roads[key] += 1
            metres[key] += length(item_points(it))
    for key, n in roads.items():
        L = metres[key]
        about = f"about {L:,.0f} m" if L < 100 else f"about {round(L, -1):,.0f} m" if L < 1000 else f"about {L / 1000:.1f} km"
        bits.append(f"{key} ×{n} ({about} in all)" if n > 1 else f"{key}, {about}")
    for kind, it in items:
        if kind == "junctions":
            bits.append(piece_of(it) or a_word(JUNCTION_WORDS.get(it.get("type"), "junction")))
    zones = sorted({it.get("type") for kind, it in items if kind == "areas" and it.get("type") in ZONE_KINDS})
    if zones:
        bits.append("zone " + " and ".join(zones))
    note = "; ".join(bits)
    return note[:1].upper() + note[1:]


def guides_of(city_name, exports):
    pat = re.compile(r"^" + re.escape(city_name) + r" (\d+)\.cityplan\.json$", re.I)
    found = []
    for d in (exports, exports / "old"):
        for f in d.glob("*.cityplan.json") if d.is_dir() else []:
            m = pat.match(f.name)
            if m:
                found.append((int(m.group(1)), f))
    return found


def map_id_for(city_name, aliases, guides):
    """The city's map id: from its newest guide, else from a planner folder named like the city. Never another city's."""
    for _, f in sorted(guides, key=lambda g: g[1].stat().st_mtime, reverse=True):
        try:
            mid = json.loads(f.read_text(encoding="utf-8-sig")).get("map_id")
        except (OSError, ValueError, AttributeError):
            continue
        if mid:
            return mid
    root = Path(cityplan.ROOT)
    for name in [city_name] + list(aliases):
        doc = root / str(name) / "planning.cityplan.json"
        if doc.exists():
            try:
                return json.loads(doc.read_text(encoding="utf-8-sig")).get("map_id") or str(name)
            except (OSError, ValueError, AttributeError):
                return str(name)
    return None


def split_page(text):
    if not text.startswith("+++\n"):
        raise SystemExit("a project page must start with a +++ front matter block")
    end = text.find("\n+++", 3)
    if end < 0:
        raise SystemExit("a project page's front matter has no closing +++")
    return text[4:end], text[end:]


def steps_blocks(front):
    """The [[steps]] tables of a front matter: [(first line, end line, id)]."""
    lines = front.split("\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i].strip() == "[[steps]]":
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(("[", REGION_START, REGION_END)):
                j += 1
            m = re.search(r'^\s*id\s*=\s*"([^"]*)"', "\n".join(lines[i + 1:j]), re.M)
            out.append((i, j, m.group(1) if m else ""))
            i = j
        else:
            i += 1
    return out


def number_key(n):
    m = re.match(r"(\d+)(.*)", n or "")
    return (int(m.group(1)), m.group(2)) if m else (10 ** 6, n or "")


def ship_project(path, guide, city_name, plan_name, cards, status="active", dry=False):
    """Writes the plan's build cards into the project page (made if it doesn't exist), keeping everything else. A step
    already there for the same step number (by an earlier ship or by hand) keeps its id, its words and its tick; ship
    gives it the fresh picture and place, and ticks it once the snapshot shows everything in it built. Two steps for one
    number are left as they are. The cards go in one marked block, in number order, where the first of them was.
    Returns (created, numbers left alone, the steps written)."""
    import tomllib
    created = not path.exists()
    if created:
        topic = re.sub(r"^\w+\s*·\s*", "", plan_name)
        text = (f"+++\nid = {json.dumps(path.stem)}\ntitle = {json.dumps(topic, ensure_ascii=False)}\nscale = \"district\"\n"
                f"status = \"{status}\"\npriority = 2\n"
                f"summary = {json.dumps('Building ' + topic + ' from the guide ' + guide + '.', ensure_ascii=False)}\n+++\n")
    else:
        text = path.read_text(encoding="utf-8")
    front, body = split_page(text)
    try:
        before = [st for st in tomllib.loads(front).get("steps", []) if isinstance(st, dict)]
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{path.name}: its front matter doesn't read ({e}); fix it first")
    by_number = defaultdict(list)
    for st in before:
        n = step_number(str(st.get("text", "")))
        if n and st.get("id"):
            by_number[n.casefold()].append(st)
    lines = front.split("\n")
    raw = {sid: "\n".join(lines[a_:b_]).strip("\n") for (a_, b_, sid) in steps_blocks(front) if sid}
    adopted, shared, steps, kept = set(), [], [], []
    for c in cards:
        old = by_number.get(c["number"].casefold(), [])
        if len(old) > 1:   # two steps for one number: kept word for word, in their place in the order
            shared.append(c["number"])
            kept += [(number_key(c["number"]), str(o["id"]), raw.get(str(o["id"]))) for o in old if raw.get(str(o["id"]))]
            continue
        st = dict(c)
        if old:
            o = old[0]
            w = obj(o.get("where"))
            st.update(id=str(o["id"]), text=str(o.get("text") or c["text"]), note=str(o.get("note") or ""),
                      done=c["done"] or bool(o.get("done")))
            if w.get("label"):
                st["where"] = dict(st["where"], label=str(w["label"])[:60])
            adopted.add(st["id"])
        steps.append(st)
    moving = adopted | {k[1] for k in kept}
    # what goes: the old block and the steps moving into the new one; the new block goes where the first of them was
    drop = set()
    start = next((i for i, l in enumerate(lines) if l.startswith(REGION_START)), None)
    if start is not None:
        end = next((i for i in range(start, len(lines)) if lines[i].startswith(REGION_END)), len(lines) - 1)
        drop.update(range(start, end + 1))
    blocks = steps_blocks(front)
    for (a_, b_, sid) in blocks:
        if sid in moving:
            drop.update(range(a_, b_))
    at = min(drop) if drop else (blocks[-1][1] if blocks else len(lines))
    link = re.compile(r'^(\s*name\s*=\s*)"' + re.escape(city_name) + r' \d+"', re.I)
    has_link = any(link.match(l) for i, l in enumerate(lines) if i not in drop)
    region = [f"{REGION_START}: {guide}. Each ship redraws these steps' pictures and places and ticks what's built;",
              "# their words are yours to change (or give them in the plan's \"cards\")."]
    if not has_link:
        region += ["[[plans]]", 'kind = "draft"', f"name = {json.dumps(guide, ensure_ascii=False)}",
                   f"layers = [{json.dumps(plan_name, ensure_ascii=False)}]", ""]
    entries = [(number_key(st["number"]), st["id"], None) for st in steps] + kept
    by_id = {st["id"]: st for st in steps}
    for _, sid, verbatim in sorted(entries, key=lambda e: e[0]):
        if verbatim is not None:
            region += [verbatim, ""]
            continue
        st = by_id[sid]
        region += ["[[steps]]", f"id = {json.dumps(st['id'])}", f"text = {json.dumps(st['text'], ensure_ascii=False)}"]
        if st.get("note"):
            region.append(f"note = {json.dumps(st['note'], ensure_ascii=False)}")
        if st.get("done"):
            region.append("done = true")
        if st.get("picture"):
            region.append(f"picture = {json.dumps(st['picture'])}")
        w = st.get("where")
        if w:
            region.append(f"where = {{ label = {json.dumps(w['label'], ensure_ascii=False)}, x = {w['x']}, z = {w['z']}, zoom = {w['zoom']} }}")
        region.append("")
    region.append(REGION_END)
    out = []
    for i, l in enumerate(lines + [""]):
        if i == at:
            if out and out[-1].strip():
                out.append("")
            out += region + [""]
        if i < len(lines) and i not in drop:
            out.append(link.sub(lambda m: m.group(1) + json.dumps(guide, ensure_ascii=False), l))
    front = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).rstrip("\n") + "\n"
    try:
        tomllib.loads(front)
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{path.name}: the new front matter wouldn't read ({e}); nothing written")
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text("+++\n" + front + body, encoding="utf-8")
        os.replace(tmp, path)
    return created, shared, steps


def project_linking(src, plan_name):
    import tomllib
    for f in sorted((src / "projects").glob("*.md")):
        try:
            meta = tomllib.loads(split_page(f.read_text(encoding="utf-8"))[0])
        except (SystemExit, Exception):
            continue
        for pl in meta.get("plans", []) if isinstance(meta.get("plans"), list) else []:
            if isinstance(pl, dict) and pl.get("kind", "draft") == "draft" and plan_name in (pl.get("layers") or []):
                return f
    return None


def drawings_summary(ch, newest=None):
    if ch is None:
        return "no planner document for this city yet"
    held = Path(ch["guide"]).name[: -len(".cityplan.json")] if ch["guide"] else None
    where = f"it held {held}" if held else "it held none of this city's guides"
    if held and newest and held != newest:
        where += f" ({newest} not imported yet)"
    if not ch["count"]:
        if ch.get("kept"):
            return where + f"; the Mayor's {ch['kept']} change{'s' if ch['kept'] != 1 else ''} since are in the plan file already"
        return where + ", with nothing drawn, moved or deleted since" + (f" ({len(ch['nudged'])} nudged a few metres, left as planned)" if ch["nudged"] else "")
    return where + f", with {ch['count']} change{'s' if ch['count'] != 1 else ''} by the Mayor"


def planner_as_plans(doc):
    """The planner's whole document in the simple plan format, every plan."""
    out = []
    for p in doc.get("plans", []):
        if not isinstance(p, dict):
            continue
        names = {r.get("id"): r.get("name") or "" for r in p.get("roads") or [] if isinstance(r, dict)}
        sp = {"name": p.get("name") or "", "roads": [], "areas": [], "junctions": []}
        for kind in cityplan.KINDS:
            sp[kind] = [cityplan.simple_item(kind, it, names) for it in p.get(kind) or [] if isinstance(it, dict)]
        out.append(sp)
    return out


def drawings_check(snap, ch):
    """plan.py check on the Mayor's own drawings: the problems of the items they drew or changed (Markdown lines). A
    missing road piece isn't one: the Manager names it when the drawing becomes a build card."""
    if not ch or not (ch["added"] or ch["changed"]):
        return []
    doc = cityplan.read_doc(ch["planner"])
    if not doc:
        return []
    wanted = {(e["plan"], e["item"]["name"] or e["name"]) for e in ch["added"] + ch["changed"]}
    try:
        chk = Check(snap, planner_as_plans(doc), None)
        chk.run()
    except ValueError:
        return ["- (the snapshot has no terrain part, so the drawings can't be checked)"]
    icon = {"error": "✗", "warn": "!", "note": "·"}
    lines = []
    for r in chk.results:
        for pr in sorted(r["problems"], key=lambda q: ("error", "warn", "note").index(q["level"])):
            if (r["name"], pr["item"]) in wanted and not pr["text"].startswith("no road piece named"):
                lines.append(f"- {icon[pr['level']]} **{pr['item']}** ({r['name']}): {pr['text']}")
    return lines


def main_drawings(src, rest, opt):
    """plan.py drawings <city>/journal: what the Mayor drew in the planner since the guide it holds, checked."""
    import tomllib
    srcp = Path(src).expanduser()
    if not (srcp / "journal.toml").exists():
        raise SystemExit("drawings needs the city's journal source folder (<city>/journal, with its journal.toml)")
    cfg = tomllib.loads((srcp / "journal.toml").read_text(encoding="utf-8-sig"))
    city_name = str(cfg.get("city") or "")
    guides = guides_of(city_name, Path(cityplan.ROOT) / "Exports")
    map_id = opt("--map-id") or map_id_for(city_name, cfg.get("aliases") or [], guides)
    if not map_id:
        print(f"No map id for {city_name} yet: no guide exported and no planner document named like the city.")
        return 0
    ch = cityplan.mayor_changes(map_id)
    newest = f"{city_name} {max(n for n, _ in guides)}" if guides else None
    print(f"# The Mayor's planner drawings: {city_name} (map id {map_id!r})\n")
    print(cityplan.changes_markdown(ch, newest))
    lines = drawings_check(city.load(city.snapshot_path(srcp)), ch) if ch and ch["count"] else []
    if lines:
        print("How they fit (`plan.py check` on them):\n\n" + "\n".join(lines))
    if opt("--json") and ch:
        Path(opt("--json")).write_text(json.dumps(ch, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main_ship(plan_path, src, rest, opt):
    import tomllib
    import contextlib
    import io
    srcp = Path(src).expanduser()
    if not (srcp / "journal.toml").exists():
        raise SystemExit("ship needs the city's journal source folder (<city>/journal, with its journal.toml)")
    cfg = tomllib.loads((srcp / "journal.toml").read_text(encoding="utf-8-sig"))
    city_name = str(cfg.get("city") or "")
    snap_path = city.snapshot_path(srcp)
    snap = city.load(snap_path)
    plans = load_plans(plan_path)
    dry = "--dry-run" in rest
    # 1. the guide's name and map id
    exports = Path(cityplan.ROOT) / "Exports"
    guides = guides_of(city_name, exports)
    guide = opt("--name") or f"{city_name} {max((n for n, _ in guides), default=0) + 1}"
    map_id = opt("--map-id") or map_id_for(city_name, cfg.get("aliases") or [], guides)
    if not map_id:
        raise SystemExit(f"No map id for {city_name}: open City Planning Draft once in the city, or pass --map-id.")
    # 1b. the Mayor's own drawings: Import replaces the planner's whole document, so they come first
    ch = cityplan.mayor_changes(map_id)
    if ch:
        ch = cityplan.pending(ch, json.loads(Path(plan_path).read_text(encoding="utf-8-sig")))
    newest = f"{city_name} {max(n for n, _ in guides)}" if guides else None
    drawings_line = drawings_summary(ch, newest)
    if ch and ch["count"]:
        if "--keep-mayor" in rest:
            raw = json.loads(Path(plan_path).read_text(encoding="utf-8-sig"))
            applied, missed = cityplan.keep_changes(raw, ch)
            if not dry:
                backup = Path(plan_path).with_name(Path(plan_path).name + time.strftime(".bak-%Y%m%d-%H%M%S"))
                shutil.copy2(plan_path, backup)
                tmp = Path(plan_path).with_suffix(".json.tmp")
                tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
                os.replace(tmp, plan_path)
            plans = [q for q in (raw["plans"] if isinstance(raw.get("plans"), list) else [raw]) if isinstance(q, dict)]
            drawings_line = (f"the Mayor's {ch['count']} planner change{'s' if ch['count'] != 1 else ''} "
                             + ("would go" if dry else "went") + " into the plan file (--keep-mayor"
                             + ("" if dry else f"; the old file is {backup.name}") + "): " + "; ".join(applied[:8])
                             + (f" and {len(applied) - 8} more" if len(applied) > 8 else "")
                             + (". Not placed: " + "; ".join(missed) if missed else ""))
        elif "--drop-mayor" in rest:
            drawings_line = f"the new guide replaces the Mayor's {ch['count']} planner change{'s' if ch['count'] != 1 else ''} (--drop-mayor)"
        else:
            print(f"# Not shipped: the Mayor's planner drawings come first\n")
            print(cityplan.changes_markdown(ch, newest))
            lines = drawings_check(snap, ch)
            if lines:
                print("How their drawings fit (`plan.py check` on them):\n\n" + "\n".join(lines) + "\n")
            print("Importing a new guide replaces the planner's whole document, so all of this would go. Ask the Mayor "
                  "what to keep, then ship again with **--keep-mayor** (their changes go into the plan file: what they "
                  "drew is added, what they moved or renamed takes their version, what they deleted goes; the plan file "
                  "is backed up first) or **--drop-mayor** (the new guide replaces them).")
            return 1
    soon = [p.get("name") for p in plans if status_of(p.get("name")) in ("Now", "Next")]
    if not soon:
        raise SystemExit("No Now or Next plan in the file: nothing to ship (`<Status> · <Topic>`, guides.md).")
    # 2. check
    chk = Check(snap, plans, guide)
    chk.run()
    soon_problems = [pr for r in chk.results if r.get("status") in ("Now", "Next") for pr in r["problems"]]
    errors = [pr for pr in soon_problems if pr["level"] == "error"]
    if errors and "--force" not in rest:
        print(chk.markdown(snap_path.name))
        print("\nNot shipped: fix what's marked ✗ in the Now and Next plans first (or --force).")
        return 1
    # 3. one build card per step number
    width = min(max(int(opt("--width", 900)), 600), 1600)
    built = {it["name"]: it["status"] for r in Built(snap).run(plans) for it in r["items"]}
    facts = None if dry else sv.survey(snap)
    if not dry:
        (srcp / "images").mkdir(parents=True, exist_ok=True)
    by_plan = defaultdict(list)
    for p, n, items in card_groups(plans, soon):
        given = obj(p.get("cards")).get(n) or obj(p.get("cards")).get(n.casefold())
        given = {"text": given} if isinstance(given, str) else obj(given)
        names = [it.get("name") for _, it in items]
        areas = [it.get("name") for kind, it in items if kind == "areas"]
        text = str(given.get("text") or (names[0] if len(names) == 1 else areas[0] if len(areas) == 1 else names[0]))
        if not step_number(text):
            text = f"{n} {text}"
        topic = re.sub(r"^\w+\s*·\s*", "", p.get("name"))
        file = f"card-{slug(n)}-{slug(topic)}.png"
        pts = [q for _, it in items for q in item_points(it)]
        bx = sv.bounds([[x, x, z, z] for x, z in pts])
        x, z = (centre_of(items[0][0], item_points(items[0][1])) if len(items) == 1 else ((bx[0] + bx[1]) / 2, (bx[2] + bx[3]) / 2))
        zoom = round(min(max(1.4 * max(bx[1] - bx[0], bx[3] - bx[2], 300.0), 400.0), 4000.0), -1)
        done = all(built.get(nm) == "built" for nm in names)
        by_plan[p.get("name")].append({"number": n, "id": f"c-{slug(n)}", "text": text, "note": str(given.get("note") or card_note(items)),
                                       "done": done, "picture": file, "items": names,
                                       "where": {"label": text[:60], "x": round(x), "z": round(z), "zoom": int(zoom)}})
    # 4. export the guide, then put this city's older guides away
    if not dry:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cityplan.cmd_export([str(plan_path), "--name", guide, "--map-id", str(map_id), "--terrain", str(snap_path)])
        new = exports / f"{guide}.cityplan.json"
        for _, f in guides:
            if f.parent == exports and f != new:
                dest = exports / "old" / f.name
                dest.parent.mkdir(exist_ok=True)
                if dest.exists():
                    dest = dest.with_name(f.name.replace(".cityplan.json", f" ({int(time.time())}).cityplan.json"))
                os.replace(f, dest)
    # 5. the projects, then every other project's link to the city's guide
    touched, left, drawn = [], [], 0
    for name in soon:
        cards = by_plan.get(name, [])
        if not cards:
            continue
        f = project_linking(srcp, name) or srcp / "projects" / f"{slug(re.sub(r'^\w+\s*·\s*', '', name))}.md"
        state = "active" if status_of(name) == "Now" else "next"
        created, shared, steps = ship_project(f, guide, city_name, name, cards, state, dry=True)
        if not dry:
            for st in steps:   # the pictures first, so the page never names one that isn't there
                draw(snap, plans, srcp / "images" / st["picture"], around=st["items"],
                     title=f"{facts.get('city') or city_name}: {st['where']['label']}", width=width, facts=facts)
                drawn += 1
            ship_project(f, guide, city_name, name, cards, state)
        touched.append((f, name, len(steps), sum(1 for st in steps if st["done"]), created))
        left += [(f.name, n) for n in shared]
    relinked = 0
    link = re.compile(r'^(\s*name\s*=\s*)"' + re.escape(city_name) + r' \d+"', re.M | re.I)
    for f in sorted((srcp / "projects").glob("*.md")):
        if f in [t[0] for t in touched]:
            continue
        text = f.read_text(encoding="utf-8")
        new_text = link.sub(lambda m: m.group(1) + json.dumps(guide, ensure_ascii=False), text)
        if new_text != text:
            relinked += 1
            if not dry:
                f.write_text(new_text, encoding="utf-8")
    # 6. build the journal
    built_ok, build_out = True, ""
    if not dry:
        import journal  # noqa: PLC0415
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = journal.cmd_build(srcp)
        built_ok, build_out = code == 0, out.getvalue().strip()
    looks = sum(1 for pr in soon_problems if pr["level"] == "warn")
    print(f"# {'Would ship' if dry else 'Shipped'}: {guide} (map id {map_id!r})\n")
    print(f"- In the planner: {drawings_line}.")
    print(f"- Checked against {snap_path.name}: {len(errors)} to fix in Now and Next" + (" (shipped anyway: --force)" if errors else "")
          + (f", {looks} to look at (`plan.py check` lists them)" if looks else "") + ".")
    if not dry:
        print(f"- Guide: {exports / (guide + '.cityplan.json')}; this city's older guides are in Exports/old.")
        print(f"- Build cards: {drawn} pictures in {srcp / 'images'}.")
    for f, name, n, done, created in touched:
        print(f"- {'New project' if created else 'Project'} {f.name}: {n} build-card step{'s' if n != 1 else ''} for {name!r}"
              + (f", {done} built already (ticked)" if done else "") + ".")
    for fname, n in left:
        print(f"- {fname}: two steps start with {n}, so ship left them as they are (number them {n}a, {n}b to give each a card).")
    if relinked:
        print(f"- {relinked} other project{'s' if relinked != 1 else ''} now link{'s' if relinked == 1 else ''} to {guide}.")
    if not dry:
        print("- Journal: " + ("built." if built_ok else "NOT built:\n" + build_out))
    print(f"\nFor the briefing: \"In the planner, Import latest file ({guide})\", then build from the Now plans.")
    return 0 if built_ok else 1


# --- advance: the move-on step after a report

EMPTIED = "layers = []  # every layer dropped"


def layer_rewrite(front, renames, dropped):
    """A project's front matter with its [[plans]] layers following plan renames and drops; a link whose layers all
    dropped out goes (a guide link with nothing to show)."""
    def fix(m):
        names = [json.loads('"' + x + '"') for x in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(2))]
        new = [renames.get(n, n) for n in names if n not in dropped]
        if names and not new:
            return EMPTIED
        return m.group(1) + "[" + ", ".join(json.dumps(n, ensure_ascii=False) for n in new) + "]"
    front = re.sub(r'^(\s*layers\s*=\s*)\[(.*?)\]', fix, front, flags=re.M | re.S)
    if EMPTIED not in front:
        return front
    lines, out, i = front.split("\n"), [], 0
    while i < len(lines):
        if lines[i].strip() == "[[plans]]":
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("["):
                j += 1
            if any(EMPTIED in l for l in lines[i:j]):
                while j < len(lines) and not lines[j].strip() and j > i:
                    j += 1
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def close_front(front, log_text, date):
    """A project's front matter set to done, with a log line saying why."""
    if re.search(r'^status\s*=', front, re.M):
        front = re.sub(r'^status\s*=\s*"[^"]*"', 'status = "done"', front, count=1, flags=re.M)
    else:
        front = 'status = "done"\n' + front
    return front.rstrip("\n") + f'\n\n[[log]]\ndate = "{date}"\ntext = {json.dumps(log_text, ensure_ascii=False)}\n'


def main_advance(plan_path, src, rest, opt):
    """plan.py advance PLAN.json <city>/journal: after a report, move the plan and the projects on."""
    import tomllib
    import contextlib
    import io
    import journal  # noqa: PLC0415
    srcp = Path(src).expanduser()
    if not (srcp / "journal.toml").exists():
        raise SystemExit("advance needs the city's journal source folder (<city>/journal, with its journal.toml)")
    cfg = tomllib.loads((srcp / "journal.toml").read_text(encoding="utf-8-sig"))
    city_name = str(cfg.get("city") or "")
    dry = "--dry-run" in rest
    keep_done = int(opt("--keep-done", 3))
    snap = city.load(city.snapshot_path(srcp))
    raw = json.loads(Path(plan_path).read_text(encoding="utf-8-sig"))
    plans = [q for q in (raw["plans"] if isinstance(raw.get("plans"), list) else [raw]) if isinstance(q, dict)]
    exports = Path(cityplan.ROOT) / "Exports"
    guides = guides_of(city_name, exports)
    newest = max(guides, default=None, key=lambda g: g[0])
    shown = set()
    if newest:
        try:
            shown = {q.get("name") for q in json.loads(newest[1].read_text(encoding="utf-8-sig")).get("plans", []) if isinstance(q, dict)}
        except (OSError, ValueError):
            pass
    _, j, m = journal.load_both(srcp)
    ticks, stat = arr_dict(m.get("ticks")), arr_dict(m.get("status"))
    built_j = {str(q.get("id")): q for q in arr(j.get("projects")) if isinstance(q, dict)}

    def pages():
        out = []
        for f in sorted((srcp / "projects").glob("*.md")):
            text = f.read_text(encoding="utf-8")
            try:
                front, body = split_page(text)
                meta = tomllib.loads(front)
            except (SystemExit, tomllib.TOMLDecodeError):
                continue
            out.append([f, front, body, meta])
        return out

    def steps_done(meta):
        """(done, total) of a project's steps: the Mayor's tick or the manager's newer change, as the panel shows it."""
        pid = str(meta.get("id") or "")
        compiled = {str(st.get("id")): st for st in arr(built_j.get(pid, {}).get("steps")) if isinstance(st, dict)}
        out = {}
        for st in arr(meta.get("steps")):
            if not isinstance(st, dict) or not st.get("id"):
                continue
            sid, mine = str(st["id"]), bool(st.get("done"))
            c = compiled.get(sid)
            out[sid] = (mine if c is None or bool(c.get("done")) != mine else journal.mayor_done(ticks, f"p:{pid}/{sid}", c), str(st.get("text", "")))
        return out

    pp = pages()
    lines_plans, lines_projects = [], []
    renames, dropped = {}, set()
    built = {it["name"]: it["status"] for r in Built(snap).run(plans, every=True) for it in r["items"]}
    # 1. Now plans whose every step is built (by the snapshot) or ticked (in the journal) become Done
    for q in plans:
        name = q.get("name") or ""
        if status_of(name) != "Now":
            continue
        project = next((pg for pg in pp if any(isinstance(pl, dict) and name in (pl.get("layers") or []) for pl in arr(pg[3].get("plans")))), None)
        ticked = {}
        if project:
            for sid, (done, text) in steps_done(project[3]).items():
                n = step_number(text)
                if n:
                    ticked[n.casefold()] = ticked.get(n.casefold(), True) and done
        groups = card_groups(plans, [name])
        left = []
        for _, n, items in groups:
            by_city = all(built.get(it.get("name")) == "built" for _, it in items)
            if not (by_city or ticked.get(n.casefold())):
                left.append(n)
        loose = [it.get("name") for kind in ("roads", "junctions", "areas") for it in arr(q.get(kind))
                 if isinstance(it, dict) and not it.get("existing") and item_points(it) and not step_number(it.get("name"))]
        if not groups and not loose:
            continue
        if not groups:
            left = [x for x in loose if built.get(x) != "built"]
        if left:
            lines_plans.append(f"{name} stays Now: step{'s' if len(left) != 1 else ''} {', '.join(left)} left"
                               + (f" ({len(groups) - len(left)} done)" if groups and len(groups) > len(left) else "") + ".")
            continue
        new = "Done · " + name.split(" · ", 1)[1]
        renames[name] = new
        q["name"] = new
        lines_plans.append(f"{name} → {new}: every step built or ticked" + (f" ({', '.join(n for _, n, _ in groups)})" if groups else "") + ".")
    # 2. Done plans a shipped guide already showed as Done drop out (kept in archive.json)
    archive = []
    for q in list(plans):
        name = q.get("name") or ""
        if status_of(name) == "Done" and name not in renames.values() and name in shown:
            plans.remove(q)
            dropped.add(name)
            archive.append(q)
            lines_plans.append(f"{name} dropped: {newest[1].name[:-len('.cityplan.json')]} showed it as Done (kept in archive.json beside the plan file).")
    # 3. Next becomes Now only on the Mayor's word
    promote = opt("--promote")
    if promote:
        q = next((x for x in plans if x.get("name") == promote), None)
        if q is None or status_of(promote) != "Next":
            raise SystemExit(f"--promote names a Next plan of the file: {', '.join(x.get('name') for x in plans if status_of(x.get('name')) == 'Next') or 'there is none'}")
        q["name"] = "Now · " + promote.split(" · ", 1)[1]
        renames[promote] = q["name"]
        lines_plans.append(f"{promote} → {q['name']} (--promote).")
    elif not any(status_of(x.get("name")) == "Now" for x in plans):
        nxt = [x.get("name") for x in plans if status_of(x.get("name")) == "Next"]
        if nxt:
            lines_plans.append("Nothing is Now any more: ask the Mayor which comes next, then `--promote` it: "
                               + ", ".join(f'"{n}"' for n in nxt) + ".")
    # 4. the projects: links follow the renames, finished ones close, old closed ones go to projects/archive/
    date = time.strftime("%Y-%m-%d %H:%M")
    reports = sorted(f.stem for f in (srcp / "reports").glob("*.md")) if (srcp / "reports").is_dir() else []
    current = (srcp / "briefing.md").read_text(encoding="utf-8") if (srcp / "briefing.md").exists() else ""
    writes, moves = [], []
    for pg in pp:
        f, front, body, meta = pg
        pid = str(meta.get("id") or f.stem)
        new_front = layer_rewrite(front, renames, dropped) if (renames or dropped) else front
        status, by_mayor = journal.mayor_status(stat, built_j.get(pid) or {"status": meta.get("status")})
        done = steps_done(meta)
        links = [n for pl in arr(meta.get("plans")) if isinstance(pl, dict) for n in (pl.get("layers") or [])]
        live = [n for n in links if status_of(renames.get(n, n)) in ("Now", "Next") and n not in dropped]
        if status in ("active", "next") and done and all(d for d, _ in done.values()) and not live:
            why = f"All {len(done)} steps done" + (f"; its plan {', '.join(renames.get(n, n) for n in links if n not in dropped)} is Done" if links else "")
            new_front = close_front(new_front, why + ". Closed by the move-on step (plan.py advance).", date)
            lines_projects.append(f"{f.name}: all {len(done)} steps done → Done, with a log line.")
        elif new_front != front:
            gone = [n for n in links if n in dropped]
            lines_projects.append(f"{f.name}: " + (f"its link to {', '.join(gone)} (dropped) is gone" if gone and not any(n in renames for n in links)
                                                   else "its plan links follow the renames") + ".")
        if new_front != front:
            writes.append((f, "+++\n" + new_front + body))
        if status == "done":
            since = str((built_j.get(pid) or {}).get("statusChanged") or "")[:10]
            if by_mayor:
                since = str(arr_dict(stat.get(pid)).get("at") or since)[:10]
            if not since:   # done from its first build: its newest log line, else the file's date
                logs = [str(x.get("date") or "") for x in arr(meta.get("log")) if isinstance(x, dict)]
                since = max(logs, default="")[:10] or time.strftime("%Y-%m-%d", time.localtime(f.stat().st_mtime))
            after = [r for r in reports if since and r[:10] > since]
            if len(after) >= keep_done and not re.search(r'^\s*project\s*=\s*"' + re.escape(pid) + '"', current, re.M):
                moves.append(f)
                lines_projects.append(f"{f.name} → projects/archive/: Done since {since}, {len(after)} reports since "
                                      "(its id stays known, so older briefings still build).")
    # write
    if not dry:
        if renames or dropped:
            backup = Path(plan_path).with_name(Path(plan_path).name + time.strftime(".bak-%Y%m%d-%H%M%S"))
            shutil.copy2(plan_path, backup)
            if isinstance(raw.get("plans"), list):
                raw["plans"] = plans
            tmp = Path(plan_path).with_suffix(".json.tmp")
            tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, plan_path)
        if archive:
            ap = Path(plan_path).with_name("archive.json")
            old = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else {"plans": []}
            old.setdefault("plans", [])
            old["plans"] += [dict(q, archived=date) for q in archive]
            ap.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
        for f, text in writes:
            tmp = f.with_suffix(".md.tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, f)
        for f in moves:
            (srcp / "projects" / "archive").mkdir(exist_ok=True)
            os.replace(f, srcp / "projects" / "archive" / f.name)
    built_ok, build_out = True, ""
    if not dry and (writes or moves):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = journal.cmd_build(srcp)
        built_ok, build_out = code == 0, out.getvalue().strip()
    print(f"# {'Would move on' if dry else 'Moved on'}: {city_name} ({Path(plan_path).name})\n")
    print("## Plans\n")
    print("\n".join(f"- {x}" for x in lines_plans) if lines_plans else "Nothing to move: no Now plan is finished and no Done plan has had its round.")
    print("\n## Projects\n")
    print("\n".join(f"- {x}" for x in lines_projects) if lines_projects else "Nothing to change.")
    if not dry and (writes or moves):
        print("\nJournal: " + ("built." if built_ok else "NOT built:\n" + build_out))
    if renames or dropped:
        print(f"\nNext: `plan.py ship {Path(plan_path).name} <city>/journal` for the next guide (its Done plans for the Mayor to compare).")
    return 0 if built_ok else 1


def arr_dict(v):
    return v if isinstance(v, dict) else {}


def main_cards(snap, plans, rest, opt):
    out_dir = opt("--out-dir")
    if not out_dir:
        print("cards needs --out-dir DIR (the journal source's images folder, say)")
        return 2
    only = [rest[i + 1] for i, a in enumerate(rest) if a == "--only" and i + 1 < len(rest)]
    width = min(max(int(opt("--width", 900)), 600), 1600)
    out = Path(out_dir)
    try:
        rows = make_cards(snap, plans, out, width, only=only)
    except ValueError:
        print("The snapshot has no terrain part, so there's nothing to draw on.")
        return 1
    if not rows:
        print("No numbered items in the Now and Next plans (or the plans named with --only), so no cards.")
        return 1
    print(f"# Build cards: {len(rows)} pictures in {out}\n")
    print("For each item's journal step (the same number and words): `picture` and `where`, which City Manager 0.9 "
          "shows as Picture and Show on map under the step. For an older mod, put the picture line in the project page.\n")
    for name, plan_name, file, x, z, zoom in rows:
        label = name.replace('"', "'")
        print(f"- **{name}** ({plan_name})")
        print(f"  - step: `picture = \"{file}\"` and `where = {{ label = \"{label}\", x = {round(x)}, z = {round(z)}, zoom = {int(zoom)} }}`")
        print(f"  - picture line (older mods): `![{label}]({file})`")
    return 0


def main_map(src, rest):
    def opt(flag, default=None):
        return rest[rest.index(flag) + 1] if flag in rest and rest.index(flag) + 1 < len(rest) else default

    out = opt("--out")
    if not out:
        print("map needs --out FILE.png")
        return 2
    now_path = sv.snapshot_file(src)
    snap = city.load(now_path)
    before = opt("--before")
    then, label = None, ""
    then_path = city.before_path(src, before, snap)
    if then_path.exists() and then_path.resolve() != now_path.resolve():
        then = city.load(then_path)
        label = obj(obj(then.get("city")).get("date")).get("text") or city.local_time(then.get("taken"))
        if (then.get("taken") or "") == (snap.get("taken") or ""):
            then = None
    try:
        res = draw_city_map(snap, out, then, view=opt("--view", "city"), title=opt("--title"),
                            width=min(max(int(opt("--width", 1600)), 600), 1600), since_label=label)
    except ValueError:
        print(f"{now_path.name} has no terrain part (City Manager 0.6 or later writes it), so there's nothing to draw on.")
        return 1
    n, b = res["new"], res["placed"]
    print(f"wrote {out}" + (f": {n} new piece{'' if n == 1 else 's'} of road and track since {label}, "
                            f"{b} building{'' if b == 1 else 's'} placed" if then is not None else " (nothing to compare with)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
