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
      A close-up picture for every numbered item in the Now and Next plans, for its build card, and the journal lines
      to go with each: the picture line and a Show-on-map place.

<src> is a journal source folder, a journal folder in ModsData, or a snapshot file, as for city.py and survey.py.

Keys plan.py reads beyond cityplan.py's (cityplan.py ignores them, so the same file exports as it is):
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
import sys
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
    target = None
    if around:
        for p in plans:
            for kind in ("roads", "areas", "junctions"):
                for it in arr(p.get(kind)):
                    if isinstance(it, dict) and (it.get("name") or "").casefold() == around.casefold():
                        target = (p, kind, it)
        if not target:
            raise SystemExit(f"No road, area or junction named {around!r} in the plans.")
        pts = item_points(target[2])
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
        pts = [q for p in near for kind in ("roads", "areas", "junctions", "markers") for it in arr(p.get(kind)) if isinstance(it, dict) for q in item_points(it)]
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
    if target:
        it = target[2]
        head = title or f"{name}: {it.get('name')}"
        sub = " · ".join(x for x in (target[0].get("name"), piece_of(it) and f"build with: {piece_of(it)}",
                                     "in a tunnel" if it.get("tunnel") else "on a bridge" if it.get("bridge") else "") if x)
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
    if target:
        p, kind, it = target
        pts = item_points(it)
        glow = (255, 0, 200, 110)
        if kind == "roads":
            pic.line(pts, glow, CLASS_STYLE.get(it.get("class"), ((0, 0, 0), 4))[1] * k * 1.4 + 22)
        elif kind == "areas":
            pic.polygon(pts, (255, 0, 200, 50), outline=glow, width=14)
        else:
            pic.marker(*pts[0], "circle", glow, r=34, outline=None)
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
                    if target and it is target[2]:
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
                    if entry not in keys and (not target or it is target[2]):
                        keys.append(entry)
                elif kind == "areas" or (kind == "roads" and status in ("Base", "Later") and zoom < 0.6):
                    pic.label(cx, cz, nm, size=15 if kind == "areas" else 13, colour=(30, 30, 30))
                elif target and it is target[2]:
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


def draw_city_map(snap, out, then=None, view="city", title=None, width=1600, since_label=""):
    """The city now, with what was built since `then` marked."""
    terrain = sv.Terrain(snap)
    net = sv.Network(snap)
    tiles = sv.Tiles(snap)
    facts = sv.survey(snap)
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
    if len(args) < 3 or args[0] not in ("check", "draw", "built", "cards"):
        print(__doc__)
        return 2
    cmd, plan_path, src = args[0], args[1], args[2]
    rest = args[3:]

    def opt(flag, default=None):
        return rest[rest.index(flag) + 1] if flag in rest and rest.index(flag) + 1 < len(rest) else default

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


def main_cards(snap, plans, rest, opt):
    out_dir = opt("--out-dir")
    if not out_dir:
        print("cards needs --out-dir DIR (the journal source's images folder, say)")
        return 2
    only = [rest[i + 1] for i, a in enumerate(rest) if a == "--only" and i + 1 < len(rest)]
    width = min(max(int(opt("--width", 900)), 600), 1600)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        facts = sv.survey(snap)
    except ValueError:
        print("The snapshot has no terrain part, so there's nothing to draw on.")
        return 1
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
