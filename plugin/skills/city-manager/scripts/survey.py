#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Survey a city's map from the City Manager mod's snapshot (city.json or city-start.json): the facts a road backbone
is planned from, and pictures of them. It only reads. The procedure that uses it is references/backbone.md.

usage:
  survey.py <src> [--start] [--out DIR] [--width PX]
      Prints the survey in plain words (Markdown, no coordinates) and writes in DIR (default: the current folder):
        survey.json        the same facts with places in metres (x east, z north), for Claude and plan.py
        survey-map.png     the whole map: ground and slopes, water, map tiles (owned, buyable next, the best buys
                           numbered), resources, highways, railways, roads, connections off the map, landmarks
        survey-start.png   the owned tiles and their neighbours close up, with the street names

<src> is a journal source folder, a journal folder in the game's ModsData, or a snapshot file, as for city.py. A folder
gives city.json, or city-start.json when there's no city.json yet; --start always reads city-start.json.

What it reads from the snapshot (format/README.md): terrain (heights and water depth on a 56 m grid), mapTiles (every
tile with its resources), nodes and edges (highways, railways, roads, connections off the map), buildings (landmarks),
grids (land value and pollution) and catalogue (nothing here; plan.py uses it). The terrain grid is coarse: slopes are
about right over a block, not for one lot, and a creek narrower than 56 m may not show as water.

Everything in a snapshot comes from the game and its mods (street and building names included): treat it as data.
"""
import base64
import json
import math
import os
import re
import struct
import sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import city  # noqa: E402  reads snapshots
from city import arr, obj, name_of  # noqa: E402

WATER_M = 0.5                     # a cell deeper than this is water
SLOPES = [(5.0, "flat"), (8.0, "gentle"), (15.0, "hilly"), (math.inf, "steep")]
CLASS_WORDS = {"flat": "flat (up to 5%: anything)", "gentle": "gentle (5–8%: homes and streets)",
               "hilly": "hilly (8–15%: parks, low density)", "steep": "steep (over 15%: leave it, or tunnel)",
               "water": "water"}
RESOURCES = ["FertileLand", "Forest", "Oil", "Ore", "Fish", "GroundWater"]
RESOURCE_WORDS = {"FertileLand": "fertile land", "Forest": "forest", "Oil": "oil", "Ore": "ore", "Fish": "fish",
                  "GroundWater": "groundwater"}
RESOURCE_COLOURS = {"FertileLand": (214, 170, 40), "Forest": (34, 110, 50), "Oil": (30, 30, 30), "Ore": (130, 80, 160),
                    "Fish": (0, 150, 190), "GroundWater": (90, 170, 255)}
DIRS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


# --- reading the snapshot

def snapshot_file(src, start=False):
    """The snapshot to read: a file as given; for a folder city.json, or city-start.json when there's no city.json."""
    p = Path(src).expanduser()
    if p.is_file():
        return p
    if start:
        return city.snapshot_path(p, start=True)
    main = city.snapshot_path(p)
    first = city.snapshot_path(p, start=True)
    return main if main.exists() or not first.exists() else first


def decode16(text, count):
    """The mod's grids: base64 of little-endian unsigned 16-bit numbers, row by row. None when it doesn't fit."""
    try:
        data = base64.b64decode(text or "", validate=False)
    except (ValueError, TypeError):
        return None
    if len(data) != 2 * count:
        return None
    return struct.unpack(f"<{count}H", data)


class Terrain:
    """The map's ground: heights and water depth (metres) on a size × size grid of cell-metre squares."""

    def __init__(self, snap):
        t = obj(snap.get("terrain"))
        self.n = int(t.get("size") or 0)
        self.cell = float(t.get("cell") or 0)
        self.origin = float(t.get("origin") or 0)
        count = self.n * self.n
        h = decode16(t.get("heights"), count) if count else None
        if not h or self.cell <= 0:
            raise ValueError("no terrain")
        self.h = [v / 10 for v in h]
        w = decode16(t.get("water"), count)
        self.w = [v / 10 for v in w] if w else [0.0] * count
        self.extent = (self.origin, self.origin + self.n * self.cell)
        self._slope = None

    def centre(self, r, c):
        return self.origin + (c + 0.5) * self.cell, self.origin + (r + 0.5) * self.cell

    def _sample(self, grid, x, z):
        n = self.n
        fc = (x - self.origin) / self.cell - 0.5
        fr = (z - self.origin) / self.cell - 0.5
        fc = min(max(fc, 0.0), n - 1.0)
        fr = min(max(fr, 0.0), n - 1.0)
        c0, r0 = int(fc), int(fr)
        c1, r1 = min(c0 + 1, n - 1), min(r0 + 1, n - 1)
        tc, tr = fc - c0, fr - r0
        a = grid[r0 * n + c0] * (1 - tc) + grid[r0 * n + c1] * tc
        b = grid[r1 * n + c0] * (1 - tc) + grid[r1 * n + c1] * tc
        return a * (1 - tr) + b * tr

    def height(self, x, z):
        return self._sample(self.h, x, z)

    def depth(self, x, z):
        return self._sample(self.w, x, z)

    def gradient(self, r, c):
        """(dh/dx, dh/dz) in metres per metre at a cell, from its neighbours."""
        n, h = self.n, self.h
        c0, c1 = max(c - 1, 0), min(c + 1, n - 1)
        r0, r1 = max(r - 1, 0), min(r + 1, n - 1)
        gx = (h[r * n + c1] - h[r * n + c0]) / (max(c1 - c0, 1) * self.cell)
        gz = (h[r1 * n + c] - h[r0 * n + c]) / (max(r1 - r0, 1) * self.cell)
        return gx, gz

    def slopes(self):
        """Slope in percent per cell."""
        if self._slope is None:
            n = self.n
            self._slope = [100 * math.hypot(*self.gradient(r, c)) for r in range(n) for c in range(n)]
        return self._slope

    def classes(self):
        """Per cell: "water", or the slope class name."""
        out = []
        for i, s in enumerate(self.slopes()):
            if self.w[i] > WATER_M:
                out.append("water")
            else:
                out.append(next(name for limit, name in SLOPES if s <= limit))
        return out

    def cells_in(self, box):
        """Indices of the cells whose centre lies in box = [minX, maxX, minZ, maxZ]."""
        x0, x1, z0, z1 = box
        c0 = max(int(math.ceil((x0 - self.origin) / self.cell - 0.5)), 0)
        c1 = min(int(math.floor((x1 - self.origin) / self.cell - 0.5)), self.n - 1)
        r0 = max(int(math.ceil((z0 - self.origin) / self.cell - 0.5)), 0)
        r1 = min(int(math.floor((z1 - self.origin) / self.cell - 0.5)), self.n - 1)
        return [r * self.n + c for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


def bezier(p, steps=8):
    """Points along an edge's cubic Bézier (four control points [x, z, y])."""
    if len(p) != 4:
        return [q[:2] for q in p]
    out = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p[0][0] + b * p[1][0] + c * p[2][0] + d * p[3][0], a * p[0][1] + b * p[1][1] + c * p[2][1] + d * p[3][1]))
    return out


class Network:
    """The snapshot's roads, highways and tracks, with names."""

    def __init__(self, snap):
        prefabs, titles, streets = arr(snap.get("prefabs")), arr(snap.get("prefabTitles")), arr(snap.get("streets"))
        self.nodes = {n.get("id"): n for n in arr(snap.get("nodes")) if isinstance(n, dict)}
        self.edges = []
        for e in arr(snap.get("edges")):
            if not isinstance(e, dict) or e.get("owned") or e.get("kind") == "path":
                continue
            pts = arr(e.get("pts"))
            if len(pts) < 2:
                continue
            prefab = name_of(prefabs, e.get("prefab")) or "?"
            self.edges.append(dict(e, prefabName=prefab, title=(name_of(titles, e.get("prefab")) or prefab),
                                   streetName=name_of(streets, e.get("street")), line=bezier(pts)))

    def by_kind(self, *kinds):
        return [e for e in self.edges if e.get("kind") in kinds]

    def incident(self):
        inc = {}
        for e in self.edges:
            for k in ("a", "b"):
                inc.setdefault(e.get(k), []).append(e)
        return inc


RB_ID = re.compile(r"r[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(-\d+)?")


def piece_name(title):
    """A road piece's name for the Mayor: the menu name; a Road Builder road's id (which carries its maker's account
    number) becomes "a Road Builder road"."""
    return "a Road Builder road" if RB_ID.fullmatch(title or "") else title


def is_ramp(e):
    """A one-way, one-lane highway piece: a slip road."""
    ln = arr(e.get("lanes"))
    return e.get("kind") == "highway" and ("Oneway - 1 lane" in e["prefabName"] or (len(ln) == 2 and ln[0] + ln[1] == 1))


class Tiles:
    """The map tiles: owned or not, resources, and which ones touch the owned area."""

    def __init__(self, snap):
        items = arr(obj(snap.get("mapTiles")).get("tiles"))
        self.permits = obj(snap.get("mapTiles")).get("permitsLeft")
        self.has_resources = bool(items)
        if not items:   # an older snapshot: only the owned tiles' boxes
            items = [{"owned": True, "box": b, "resources": {}} for b in arr(snap.get("tiles")) if len(arr(b)) == 4]
        self.tiles = []
        for i, t in enumerate(items):
            box = [float(v) for v in arr(t.get("box"))]
            if len(box) != 4:
                continue
            self.tiles.append({"i": len(self.tiles), "box": box, "owned": bool(t.get("owned")),
                               "resources": {k: float(v) for k, v in obj(t.get("resources")).items() if isinstance(v, (int, float))},
                               "centre": ((box[0] + box[1]) / 2, (box[2] + box[3]) / 2)})
        self.size = sum(t["box"][1] - t["box"][0] for t in self.tiles) / len(self.tiles) if self.tiles else 623.3
        self._buckets = {}
        for t in self.tiles:
            for k in self._keys(t["box"]):
                self._buckets.setdefault(k, []).append(t)
        self.neigh = self._neighbours()

    def _keys(self, box):
        s = 500.0
        return [(i, j) for i in range(int(math.floor(box[0] / s)), int(math.floor(box[1] / s)) + 1)
                for j in range(int(math.floor(box[2] / s)), int(math.floor(box[3] / s)) + 1)]

    def at(self, x, z):
        for t in self._buckets.get((int(math.floor(x / 500.0)), int(math.floor(z / 500.0))), []):
            b = t["box"]
            if b[0] - 0.5 <= x <= b[1] + 0.5 and b[2] - 0.5 <= z <= b[3] + 0.5:
                return t
        return None

    def _neighbours(self):
        """Tiles sharing a side (not just a corner)."""
        out = {t["i"]: set() for t in self.tiles}
        tol = 2.0
        for t in self.tiles:
            a = t["box"]
            for k in self._keys([a[0] - tol, a[1] + tol, a[2] - tol, a[3] + tol]):
                for u in self._buckets.get(k, []):
                    if u["i"] <= t["i"]:
                        continue
                    b = u["box"]
                    ox = min(a[1], b[1]) - max(a[0], b[0])
                    oz = min(a[3], b[3]) - max(a[2], b[2])
                    side_x = (abs(a[1] - b[0]) < tol or abs(b[1] - a[0]) < tol) and oz > tol
                    side_z = (abs(a[3] - b[2]) < tol or abs(b[3] - a[2]) < tol) and ox > tol
                    if side_x or side_z:
                        out[t["i"]].add(u["i"])
                        out[u["i"]].add(t["i"])
        return out

    def owned(self):
        return [t for t in self.tiles if t["owned"]]

    def buyable(self):
        own = {t["i"] for t in self.owned()}
        return [t for t in self.tiles if not t["owned"] and self.neigh[t["i"]] & own]


def bounds(boxes):
    return [min(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes), max(b[3] for b in boxes)]


# --- words for places (the Mayor gets words and pictures, never coordinates)

def direction(dx, dz):
    ang = math.degrees(math.atan2(dx, dz)) % 360   # 0 = north (+z), 90 = east (+x)
    return DIRS[int((ang + 22.5) // 45) % 8]


def distance_words(d):
    if d < 950:
        return f"about {int(round(d / 100.0)) * 100} m"
    return f"{d / 1000:.1f} km".replace(".0 km", " km")


class Places:
    """Plain words for a place: where it is from the start (the owned tiles), or on which edge of the map."""

    def __init__(self, boxes, extent, word="the start"):
        self.boxes = boxes
        self.box = bounds(boxes)
        area = sum((b[1] - b[0]) * (b[3] - b[2]) for b in boxes) or 1
        self.ref = (sum((b[0] + b[1]) / 2 * (b[1] - b[0]) * (b[3] - b[2]) for b in boxes) / area,
                    sum((b[2] + b[3]) / 2 * (b[1] - b[0]) * (b[3] - b[2]) for b in boxes) / area)
        self.extent = extent
        self.word = word

    def inside(self, x, z, margin=0.0):
        return any(b[0] - margin <= x <= b[1] + margin and b[2] - margin <= z <= b[3] + margin for b in self.boxes)

    def gap(self, x, z):
        """Metres from the nearest start tile (0 inside one)."""
        return min(math.hypot(max(b[0] - x, 0, x - b[1]), max(b[2] - z, 0, z - b[3])) for b in self.boxes)

    def of(self, x, z):
        dx, dz = x - self.ref[0], z - self.ref[1]
        if self.inside(x, z):
            if math.hypot(dx, dz) < 0.2 * max(self.box[1] - self.box[0], self.box[3] - self.box[2]):
                return f"in the middle of {self.word}"
            return f"in the {direction(dx, dz)} of {self.word}"
        d = self.gap(x, z)
        if d < 150:
            return f"just {direction(dx, dz)} of {self.word}"
        return f"{distance_words(d)} {direction(dx, dz)} of {self.word}"

    def edge(self, x, z):
        """Which side of the map a connection leaves by, and where along it."""
        lo, hi = self.extent
        mid = (lo + hi) / 2
        sides = {"west": x - lo, "east": hi - x, "south": z - lo, "north": hi - z}
        side = min(sides, key=sides.get)
        along = z if side in ("west", "east") else x
        third = (hi - lo) / 3
        if side in ("west", "east"):
            part = "south part" if along < lo + third else "north part" if along > hi - third else "middle"
        else:
            part = "west part" if along < lo + third else "east part" if along > hi - third else "middle"
        return f"{side} edge, {part}" if part != "middle" else f"{side} edge, near the middle"


# --- the survey

def survey(snap, start=False):
    """All the facts, places in metres. Raises ValueError when the snapshot has no terrain."""
    terrain = Terrain(snap)
    tiles = Tiles(snap)
    net = Network(snap)
    c = obj(snap.get("city"))
    owned = tiles.owned()
    all_owned = bool(owned) and len(owned) == len(tiles.tiles) and len(owned) > 9
    roads = [e for e in net.by_kind("road")]
    if all_owned or not owned:
        # Every tile owned (the game's unlock-all-tiles option) or none known: the start is the 3 × 3 tiles around the
        # map's own starter road, else around the middle tile.
        if roads:
            pts = [p for e in roads for p in e["line"]]
            seed = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        else:
            seed = (sum(terrain.extent) / 2, sum(terrain.extent) / 2)
        t0 = tiles.at(*seed) or min(tiles.tiles, key=lambda t: math.dist(t["centre"], seed)) if tiles.tiles else None
        start_tiles = [t0] + [tiles.tiles[i] for i in tiles.neigh[t0["i"]]] if t0 else []
        if t0:   # add the corners: the neighbours' neighbours that touch two of them
            ring = {i for i in tiles.neigh[t0["i"]]}
            corners = {j for i in ring for j in tiles.neigh[i] if j != t0["i"] and j not in ring and
                       len(tiles.neigh[j] & ring) >= 2}
            start_tiles += [tiles.tiles[j] for j in corners]
        start_box = bounds([t["box"] for t in start_tiles]) if start_tiles else [*terrain.extent, *terrain.extent]
        if not start_tiles:
            start_tiles = [{"i": -1, "box": start_box, "resources": {}}]
        n = len(start_tiles)
        which = "the 3 × 3 tiles" if n == 9 else f"the {n} tile{'s' if n != 1 else ''}"
        grid = "" if n == 9 else " (this map's tiles aren't a regular grid)"
        start_note = (f"Every tile is already owned (the game's option to unlock all map tiles), so the start is taken as "
                      f"{which} around {'the map' + chr(39) + 's own starter road' if roads else 'the middle of the map'}{grid}. "
                      "That's only a stand-in: where the city starts is the Mayor's choice (founding.md's start_hint, or "
                      "ask; a custom map's own description often names its intended starts)." if all_owned else
                      "The snapshot lists no owned tiles; the start is taken as the middle of the map.")
    else:
        start_tiles = owned
        start_box = bounds([t["box"] for t in owned])
        start_note = ""
    word = "the start" if all_owned or len(owned) <= 9 else "the owned tiles"
    places = Places([t["box"] for t in start_tiles], terrain.extent, word)

    classes = terrain.classes()
    slopes = terrain.slopes()

    def ground(indices):
        cnt = Counter(classes[i] for i in indices)
        total = sum(cnt.values()) or 1
        return {k: round(100 * cnt.get(k, 0) / total, 1) for k in ("flat", "gentle", "hilly", "steep", "water")}

    all_cells = range(terrain.n * terrain.n)
    start_cells = [i for t in start_tiles for i in terrain.cells_in(t["box"])]

    # per tile: ground, network through it
    for t in tiles.tiles:
        cells = terrain.cells_in(t["box"])
        g = ground(cells) if cells else {}
        t["ground"] = g
        t["heights"] = [round(min(terrain.h[i] for i in cells), 1), round(max(terrain.h[i] for i in cells), 1)] if cells else None
        t["networks"] = set()
    for e in net.edges:
        for p in e["line"][::2]:
            t = tiles.at(*p)
            if t is not None:
                t["networks"].add("highway" if e["kind"] == "highway" else "rail" if e["kind"] == "train" else e["kind"])

    maxima = {k: max((t["resources"].get(k, 0) for t in tiles.tiles), default=0) for k in RESOURCES}

    def amount(t, k):
        top = maxima.get(k) or 0
        v = t["resources"].get(k, 0)
        if not top or v <= 0:
            return ""
        share = v / top
        return "lots" if share >= 0.5 else "some" if share >= 0.15 else "a little"

    def tile_row(t, rank=None):
        area = t["resources"].get("Area") or (t["box"][1] - t["box"][0]) * (t["box"][3] - t["box"][2])
        build = t["resources"].get("BuildableLand")
        cx, cz = t["centre"]
        side = f"{direction(cx - places.ref[0], cz - places.ref[1])} side" if places.gap(cx, cz) < 0.75 * tiles.size else places.of(cx, cz)
        return {"rank": rank, "tile": t["i"], "box": [round(v, 1) for v in t["box"]], "where": side,
                "buildableHa": round(build / 10000, 1) if build is not None else None,
                "buildableShare": round(100 * build / area) if build is not None and area else None,
                "ground": t["ground"], "resources": {k: amount(t, k) for k in RESOURCES if amount(t, k)},
                "networks": sorted(t["networks"])}

    def buy_score(t):
        g = t["ground"]
        area = t["resources"].get("Area") or 1
        build = t["resources"].get("BuildableLand", area * (100 - g.get("water", 0) - g.get("steep", 0)) / 100)
        return (build / area) * (0.5 + (g.get("flat", 0) + 0.5 * g.get("gentle", 0)) / 100)

    buyable = sorted(tiles.buyable(), key=lambda t: -buy_score(t))
    buys = [tile_row(t, i + 1) for i, t in enumerate(buyable)]

    # flat land: patches and the biggest flat square
    def patches(ok, limit_cells, region=None):
        seen = set()
        out = []
        n = terrain.n
        allowed = set(region) if region is not None else None
        for i in (region if region is not None else all_cells):
            if i in seen or not ok(i):
                continue
            q, comp = deque([i]), []
            seen.add(i)
            while q:
                j = q.popleft()
                comp.append(j)
                r, cc = divmod(j, n)
                for k in ((r - 1) * n + cc if r else None, (r + 1) * n + cc if r < n - 1 else None,
                          j - 1 if cc else None, j + 1 if cc < n - 1 else None):
                    if k is not None and k not in seen and ok(k) and (allowed is None or k in allowed):
                        seen.add(k)
                        q.append(k)
            if len(comp) >= limit_cells:
                out.append(comp)
        return sorted(out, key=len, reverse=True)

    cell_ha = terrain.cell * terrain.cell / 10000

    def patch_info(comp):
        xs = [terrain.centre(*divmod(j, terrain.n)) for j in comp]
        cx, cz = sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs)
        return {"ha": round(len(comp) * cell_ha), "centre": [round(cx), round(cz)], "where": places.of(cx, cz)}

    flat_ok = lambda i: classes[i] == "flat"
    start_patches = [patch_info(p) for p in patches(flat_ok, max(4, int(10 / cell_ha)), start_cells)[:4]]

    def biggest_square(ok):
        n = terrain.n
        best, at = 0, None
        prev = [0] * n
        for r in range(n):
            cur = [0] * n
            for cc in range(n):
                if ok(r * n + cc):
                    cur[cc] = 1 + (min(prev[cc], cur[cc - 1], prev[cc - 1]) if r and cc else 0)
                    if cur[cc] > best:
                        best, at = cur[cc], (r, cc)
            prev = cur
        if not at:
            return None
        r, cc = at
        x, z = terrain.centre(r - (best - 1) / 2, cc - (best - 1) / 2)
        return {"metres": round(best * terrain.cell), "centre": [round(x), round(z)], "where": places.of(x, z)}

    square_flat = biggest_square(flat_ok)
    square_gentle = biggest_square(lambda i: classes[i] in ("flat", "gentle"))

    # water bodies
    water_ok = lambda i: classes[i] == "water"
    bodies = []
    lo, hi = terrain.extent
    for comp in patches(water_ok, 6):
        n = terrain.n
        rows = [j // n for j in comp]
        cols = [j % n for j in comp]
        span = max(max(rows) - min(rows), max(cols) - min(cols)) + 1
        width = len(comp) / span
        edge = any(r in (0, n - 1) for r in rows) or any(cc in (0, n - 1) for cc in cols)
        kind = "river or creek" if width < 4 else "sea or large lake" if (edge and len(comp) > 0.01 * n * n) else "lake"
        info = patch_info(comp)
        info.update(kind=kind, cells=len(comp))
        if kind == "river or creek":
            surface = lambda j: terrain.h[j] + terrain.w[j]
            up, down = max(comp, key=surface), min(comp, key=surface)
            ux, uz = terrain.centre(*divmod(up, n))
            dx, dz = terrain.centre(*divmod(down, n))
            info["from"], info["to"] = [round(ux), round(uz)], [round(dx), round(dz)]
            a, b = places.of(ux, uz), places.of(dx, dz)
            info["flows"] = f"from {a} to {b}" if math.dist((ux, uz), (dx, dz)) > 300 and a != b else ""
        bodies.append(info)
    shore = 0
    n = terrain.n
    start_set = set(start_cells)
    for i in start_cells:
        if classes[i] == "water":
            continue
        r, cc = divmod(i, n)
        if any(0 <= rr < n and 0 <= c2 < n and classes[rr * n + c2] == "water" for rr, c2 in ((r - 1, cc), (r + 1, cc), (r, cc - 1), (r, cc + 1))):
            shore += 1

    # connections off the map
    inc = net.incident()
    outside = []
    for nid, node in net.nodes.items():
        if not node.get("outside"):
            continue
        kinds = Counter(e["kind"] for e in inc.get(nid, []))
        kind = kinds.most_common(1)[0][0] if kinds else "?"
        x, z = node.get("x", 0), node.get("z", 0)
        for o in outside:
            if o["kind"] == kind and math.dist((x, z), o["centre"]) < 400:
                o["nodes"] += 1
                o["types"].update(e["title"] for e in inc.get(nid, []))
                break
        else:
            outside.append({"kind": kind, "centre": (x, z), "nodes": 1, "types": Counter(e["title"] for e in inc.get(nid, []))})
    connections = []
    for o in outside:
        edge = places.edge(*o["centre"])
        row = next((r for r in connections if r["kind"] == o["kind"] and r["edge"] == edge), None)
        if row is None:
            row = {"kind": o["kind"], "edge": edge, "places": [], "fromStart": distance_words(places.gap(*o["centre"])), "types": []}
            connections.append(row)
        row["places"].append([round(o["centre"][0]), round(o["centre"][1])])
        row["types"] = sorted(set(row["types"]) | {piece_name(t) for t in o["types"]})
    connections.sort(key=lambda r: (r["kind"] != "highway", r["kind"], r["edge"]))

    # highways and railways
    def length_by(edges, key):
        out = Counter()
        for e in edges:
            out[key(e)] += e.get("length", 0) or 0
        return out

    hw = net.by_kind("highway")
    rail = net.by_kind("train")
    at_grade, highway_ends = [], []
    for nid, es in inc.items():
        kinds = Counter(e["kind"] for e in es)
        if not kinds["highway"] or not (kinds["road"]):
            continue
        node = net.nodes.get(nid, {})
        x, z = node.get("x", 0), node.get("z", 0)
        through = [e for e in es if e["kind"] == "highway" and not is_ramp(e)]
        names = sorted({e["streetName"] for e in through if e["streetName"]})
        roads_here = sorted({e["streetName"] or e["title"] for e in es if e["kind"] == "road"})
        rec = {"centre": [round(x), round(z)], "where": places.of(x, z), "highway": names, "roads": roads_here,
               "lights": bool(node.get("lights"))}
        if len(through) >= 2:
            at_grade.append(rec)
        elif len(through) == 1:
            highway_ends.append(rec)

    def in_start_len(edges):
        return sum((e.get("length", 0) or 0) for e in edges if places.inside(*e["line"][len(e["line"]) // 2]))

    streets = Counter()
    for e in roads:
        if places.inside(*e["line"][len(e["line"]) // 2], margin=tiles.size):
            streets[(e["streetName"] or "(no name)", piece_name(e["title"]))] += e.get("length", 0) or 0

    landmarks = []
    for b in arr(snap.get("buildings")):
        if isinstance(b, dict) and b.get("kind") in ("other", "signature") and b.get("name"):
            landmarks.append({"name": b["name"], "centre": [round(b.get("x", 0)), round(b.get("z", 0))],
                              "where": places.of(b.get("x", 0), b.get("z", 0))})

    # resources across the map
    res_summary = {}
    for k in RESOURCES:
        total = sum(t["resources"].get(k, 0) for t in tiles.tiles)
        if not total:
            continue
        ranked = sorted(tiles.tiles, key=lambda t: -t["resources"].get(k, 0))
        acc, top = 0.0, []
        for t in ranked:
            if acc >= 0.5 * total or len(top) >= 40:
                break
            acc += t["resources"].get(k, 0)
            top.append(t)
        cx = sum(t["centre"][0] * t["resources"].get(k, 0) for t in top) / max(acc, 1e-9)
        cz = sum(t["centre"][1] * t["resources"].get(k, 0) for t in top) / max(acc, 1e-9)
        spread = max(math.dist(t["centre"], (cx, cz)) for t in top) if top else 0
        start_share = sum(t["resources"].get(k, 0) for t in start_tiles) / total
        best = []
        for t in ranked:
            if t["resources"].get(k, 0) <= 0 or len(best) >= 3:
                break
            if all(b["where"] != places.of(*t["centre"]) for b in best):
                best.append({"tile": t["i"], "where": places.of(*t["centre"])})
        res_summary[k] = {"centre": [round(cx), round(cz)], "where": places.of(cx, cz), "tiles": len(top),
                          "spread": distance_words(spread), "startShare": round(100 * start_share, 1), "best": best}

    # land value and pollution
    grids = {}
    g = obj(snap.get("grids"))
    gn = int(g.get("size") or 0)
    for k in ("landValue", "noisePollution", "airPollution", "groundPollution"):
        vals = decode16(g.get(k), gn * gn) if gn else None
        if not vals:
            continue
        top = max(vals)
        if not top:
            grids[k] = {"max": 0}
            continue
        hot = [i for i, v in enumerate(vals) if v >= 0.6 * top]
        cell = float(g.get("cell") or 0)
        origin = float(g.get("origin") or 0)
        pts = [(origin + (i % gn + 0.5) * cell, origin + (i // gn + 0.5) * cell) for i in hot]
        cx, cz = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        in_start = [v for i, v in enumerate(vals) if places.inside(origin + (i % gn + 0.5) * cell, origin + (i // gn + 0.5) * cell)]
        grids[k] = {"max": top, "hotCentre": [round(cx), round(cz)], "hotWhere": places.of(cx, cz), "hotCells": len(hot),
                    "startAverage": round(sum(in_start) / len(in_start)) if in_start else None}

    km = lambda m: round(m / 1000, 1)
    return {
        "format": 1, "city": c.get("name"), "taken": snap.get("taken"), "why": snap.get("why"),
        "gameDate": obj(c.get("date")).get("text"), "milestone": c.get("milestone"), "money": c.get("money"),
        "unlimitedMoney": bool(c.get("unlimitedMoney")), "population": c.get("population"),
        "map": {"extent": [terrain.extent[0], terrain.extent[1]], "cell": terrain.cell, "tiles": len(tiles.tiles),
                "tileSize": round(tiles.size, 1), "ground": ground(all_cells),
                "heights": [round(min(terrain.h)), round(max(terrain.h))]},
        "start": {"word": word, "box": [round(v, 1) for v in start_box], "centre": [round(places.ref[0]), round(places.ref[1])],
                  "tiles": [t["i"] for t in start_tiles], "allOwned": all_owned, "note": start_note,
                  "ground": ground(start_cells), "flatPatches": start_patches, "shoreKm": km(shore * terrain.cell),
                  "highwayKm": km(in_start_len(hw)), "railKm": km(in_start_len(rail)), "roadKm": km(in_start_len(roads)),
                  "streets": [{"name": s, "piece": p, "km": km(m)} for (s, p), m in streets.most_common(12)],
                  "resources": {k: v["startShare"] for k, v in res_summary.items()},
                  "heights": [round(min((terrain.h[i] for i in start_cells), default=0)), round(max((terrain.h[i] for i in start_cells), default=0))]},
        "tiles": {"owned": len(owned), "permitsLeft": tiles.permits, "resourcesKnown": tiles.has_resources, "buyable": buys},
        "flatSquare": square_flat, "gentleSquare": square_gentle,
        "water": {"bodies": bodies},
        "connections": connections,
        "highways": {"km": km(sum(length_by(hw, lambda e: e["title"]).values())),
                     "types": {k: km(v) for k, v in length_by(hw, lambda e: piece_name(e["title"])).most_common()},
                     "names": sorted({e["streetName"] for e in hw if e["streetName"]}),
                     "atGrade": at_grade, "ends": highway_ends,
                     "bridgesKm": km(sum(e.get("length", 0) or 0 for e in hw if e.get("bridge"))),
                     "tunnelsKm": km(sum(e.get("length", 0) or 0 for e in hw if e.get("tunnel")))},
        "rail": {"km": km(sum(e.get("length", 0) or 0 for e in rail)),
                 "tramKm": km(sum(e.get("length", 0) or 0 for e in net.by_kind("tram")))},
        "roads": {"km": km(sum(e.get("length", 0) or 0 for e in roads))},
        "landmarks": landmarks[:30],
        "resources": res_summary,
        "grids": grids,
    }


# --- the survey in words

def pct(v):
    return f"{v:.0f}%" if v >= 1 or v == 0 else "under 1%"


def ground_words(g):
    parts = [f"{CLASS_WORDS[k]} {pct(g.get(k, 0))}" for k in ("flat", "gentle", "hilly", "steep", "water") if g.get(k, 0)]
    return "; ".join(parts) if parts else "unknown"


def founding_facts(src):
    """What the founding chat recorded beside the journal source (manager/founding.md), and the map's own file's
    connections, which the snapshot can't show (it holds road and rail links only): {"map", "startHint",
    "mapConnections"}, or {} when there's no founding.md (a snapshot file, a journal folder in ModsData)."""
    p = Path(src).expanduser()
    if p.is_file():
        return {}
    try:
        import founding   # noqa: PLC0415  the founding chat's helper, beside this script
        _, meta, _ = founding.read_founding(p)
    except Exception:     # a missing or broken founding.md never stops a survey
        return {}
    if not isinstance(meta, dict):
        return {}
    out = {}
    if isinstance(meta.get("start_hint"), str) and meta["start_hint"].strip():
        out["startHint"] = meta["start_hint"].strip()[:300]
    name = meta.get("map")
    if isinstance(name, str) and name.strip():
        out["map"] = name.strip()[:120]
        try:
            hit = next((m for m in founding.all_maps() if str(m[0].get("displayName", "")).casefold() == name.strip().casefold()), None)
        except Exception:
            hit = None
        if hit:
            con = hit[0].get("connections") or {}
            out["mapConnections"] = [k for k in founding.CONNECTIONS if isinstance(con, dict) and con.get(k)]
    return out


def report(s, pictures=()):
    out = []
    w = out.append
    w(f"# Survey of {s['city'] or 'the city'}\n")
    st, tl = s["start"], s["tiles"]
    why = {"start": "loading the city", "done": "Done for today", "save": "a save", "button": "Take a snapshot"}.get(s.get("why"), s.get("why"))
    w(f"From the snapshot taken {city.local_time(s.get('taken'))} on {why}; in game {s.get('gameDate') or '?'}. "
      f"The map is {(s['map']['extent'][1] - s['map']['extent'][0]) / 1000:.1f} km across" +
      (f", with {s['map']['tiles']} map tiles; " if tl["resourcesKnown"] else "; ") +
      f"heights from {s['map']['heights'][0]:,} to {s['map']['heights'][1]:,} m.\n")
    w("## Settings that change the plan\n")
    w("| | |\n|---|---|")
    w(f"| Money | {city.money(s.get('money'))}{' (unlimited money)' if s.get('unlimitedMoney') else ''} |")
    w(f"| Milestone | {s.get('milestone', '?')} (what it unlocks: `city.py catalogue`) |")
    w(f"| Map tiles | {tl['owned']} owned" + (f" of {s['map']['tiles']}" if tl["resourcesKnown"] else " (this snapshot doesn't list the others)") +
      (f", {tl['permitsLeft']} permits left" if tl.get("permitsLeft") is not None else "") + " |")
    w("| Traffic side | not in the snapshot: take it from founding.md (`traffic`), or ask; it decides which side every ramp leaves |")
    if st.get("note"):
        w(f"| Start | {st['note']} |")
    w("")

    w(f"## {st['word'][0].upper() + st['word'][1:]}\n")
    b = st["box"]
    w(f"- **Size:** {(b[1] - b[0]) / 1000:.1f} × {(b[3] - b[2]) / 1000:.1f} km, heights {st['heights'][0]:,} to {st['heights'][1]:,} m.")
    w(f"- **Ground:** {ground_words(st['ground'])}.")
    if st["flatPatches"]:
        w("- **Biggest flat patches:** " + "; ".join(f"{p['ha']} ha {p['where']}" for p in st["flatPatches"]) + ".")
    if st["shoreKm"]:
        w(f"- **Shore:** about {st['shoreKm']} km of land next to water.")
    nets = [f"{v} km of {k}" for k, v in (("highway", st["highwayKm"]), ("railway", st["railKm"]), ("road", st["roadKm"])) if v]
    w(f"- **Already built:** {', '.join(nets) if nets else 'nothing yet'}.")
    if st["streets"]:
        w("- **Streets in and around it:** " + "; ".join(f"{x['name']} ({x['piece']}, {x['km']} km)" for x in st["streets"]) + ".")
    fd = s.get("founding") or {}
    if fd.get("startHint"):
        w(f"- **Where the Mayor wants to start** (founding.md): {fd['startHint']}")
    res = [f"{RESOURCE_WORDS[k]} {v:.0f}% of the map's" for k, v in st["resources"].items() if v >= 0.5]
    if res:
        w("- **Resources under it:** " + "; ".join(res) + ". Say so if a district would sit on top of oil or ore.")
    w("")

    kinds_seen = {o["kind"] for o in s["connections"]}
    from_file = [k for k in (fd.get("mapConnections") or []) if k in ("ship", "air") or (k == "train" and "train" not in kinds_seen)]
    if s["connections"] or from_file:
        w("## Connections off the map\n")
    if s["connections"]:
        w(f"| What | Where it leaves the map | How many | From {st['word']} | Pieces |\n|---|---|---|---|---|")
        for o in s["connections"]:
            what = {"highway": "Highway", "train": "Railway", "road": "Road"}.get(o["kind"], o["kind"].capitalize())
            w(f"| {what} | {o['edge']} | {len(o['places'])} | {o['fromStart']} | {', '.join(o['types'])} |")
    if from_file:
        words = {"ship": "a **ship** link", "air": "an **air** link", "train": "a **railway** link"}
        w(("\n" if s["connections"] else "") + f"- **From the map's own file** ({fd['map']}): also "
          + " and ".join(words[k] for k in from_file) + ". The snapshot holds road and rail links only, so where they "
          "leave the map isn't known here: find them in game before placing a harbour or an airport.")
    if s["connections"] or from_file:
        w("")

    hw = s["highways"]
    w("## Highways and railways\n")
    if hw["km"]:
        w(f"- **Highways:** {hw['km']} km ({', '.join(f'{k} {v} km' for k, v in hw['types'].items())})" +
          (f"; on bridges {hw['bridgesKm']} km, in tunnels {hw['tunnelsKm']} km" if hw["bridgesKm"] or hw["tunnelsKm"] else "") +
          (f". Names: {', '.join(hw['names'][:10])}" + (f" and {len(hw['names']) - 10} more" if len(hw["names"]) > 10 else "") + "." if hw["names"] else "."))
    else:
        w("- **Highways:** none on the map.")
    for e in hw["ends"][:5]:
        w(f"- **Where a highway becomes a street:** {', '.join(e['highway']) or 'a highway'} ends on {', '.join(e['roads'])} {e['where']}. "
          "Fine for a start; plan the city's first interchange near it for when traffic grows.")
    if len(hw["ends"]) > 5:
        w(f"- {len(hw['ends']) - 5} more places where a highway becomes a street: survey.json.")
    for e in hw["atGrade"][:6]:
        w(f"- **A street joins a highway at grade:** {', '.join(e['roads'])} on {', '.join(e['highway']) or 'a highway'} {e['where']}"
          + (" (traffic lights on the highway)" if e["lights"] else "") + ". Through traffic stops here: plan an interchange or an underpass.")
    if len(hw["atGrade"]) > 6:
        w(f"- {len(hw['atGrade']) - 6} more streets joining a highway at grade: survey.json.")
    rl = s["rail"]
    w(f"- **Railways:** {rl['km']} km" + (f"; tram track {rl['tramKm']} km" if rl["tramKm"] else "") + ". A road can't cross a railway at grade in this game: tunnel or bridge.")
    w("")

    w("## Next tiles to buy\n")
    if not tl["buyable"]:
        w("Nothing to buy listed: the snapshot has no map tiles part (City Manager 0.7 or later).\n" if not tl["resourcesKnown"] else
          "Nothing to buy: every tile is already owned.\n" if st.get("allOwned") or tl["owned"] == s["map"]["tiles"] else
          "No unowned tile shares a side with the owned ones.\n")
    else:
        w("Tiles next to the owned ones (sharing a side), best first: ranked by how much of the tile is buildable and how flat "
          "it is. Resources and connections are shown, not scored: weigh them against the plan.\n")
        w("| # | Where | Buildable | Ground | Resources | Through it |\n|---|---|---|---|---|---|")
        for t in tl["buyable"][:12]:
            g = t["ground"]
            build = f"{t['buildableHa']} ha ({t['buildableShare']}%)" if t["buildableHa"] is not None else "?"
            gw = ", ".join(f"{k} {pct(g.get(k, 0))}" for k in ("flat", "gentle", "steep", "water") if g.get(k, 0) >= 5)
            rw = ", ".join(f"{RESOURCE_WORDS[k]} {v}" for k, v in t["resources"].items())
            w(f"| {t['rank']} | {t['where']} | {build} | {gw or '–'} | {rw or '–'} | {', '.join(t['networks']) or '–'} |")
        if len(tl["buyable"]) > 12:
            w(f"\n{len(tl['buyable']) - 12} more in survey.json.")
        w("")

    w("## The whole map\n")
    w(f"- **Ground:** {ground_words(s['map']['ground'])}.")
    if s["flatSquare"]:
        f = s["flatSquare"]
        w(f"- **Biggest flat square:** {distance_words(f['metres'])} across, {f['where']}" +
          (" (room for an airport, about 1.4 × 1.3 km)." if f["metres"] >= 1400 else "."))
    if s["gentleSquare"] and (not s["flatSquare"] or s["gentleSquare"]["metres"] > s["flatSquare"]["metres"]):
        f = s["gentleSquare"]
        w(f"- **Biggest flat-or-gentle square:** {distance_words(f['metres'])} across, {f['where']}.")
    big = [b for b in s["water"]["bodies"] if b["ha"] >= 10][:5]
    for body in big:
        w(f"- **Water:** a {body['kind']} of about {body['ha']:,} ha, {body['where']}" +
          (f"; it probably flows {body['flows']} (water intake upstream, sewage downstream)" if body.get("flows") else "") + ".")
    small = len(s["water"]["bodies"]) - len(big)
    if small > 0:
        w(f"- **Smaller water:** {small} more creeks and ponds (survey.json).")
    if not s["water"]["bodies"]:
        w("- **Water:** none deeper than half a metre on the 56 m grid.")
    if s["resources"]:
        for k, r in s["resources"].items():
            best = "; best tiles " + ", ".join(b["where"] for b in r["best"]) if r["best"] else ""
            w(f"- **{RESOURCE_WORDS[k].capitalize()}:** half of it in {r['tiles']} tiles, centred {r['where']}{best}.")
    elif not tl["resourcesKnown"]:
        w("- **Resources:** not in this snapshot (City Manager 0.7 or later writes the map tiles with their resources).")
    if s["landmarks"]:
        w("- **Landmarks and other placed buildings:** " + "; ".join(f"{l['name']} {l['where']}" for l in s["landmarks"][:12]) +
          (f"; and {len(s['landmarks']) - 12} more" if len(s["landmarks"]) > 12 else "") + ".")
    w("- **Wind:** not in the snapshot. Air pollution drifts with it; if heavy industry matters, ask the Mayor to watch the "
      "air pollution view once the first factories run.")
    w("")

    w("## Land value and pollution\n")
    gr = s["grids"]
    if not gr:
        w("Not in this snapshot (City Manager 0.7 or later).\n")
    elif all(not v.get("max") for v in gr.values()):
        w("All zero: a new city has no land value or pollution yet.\n")
    else:
        words = {"landValue": "Land value", "noisePollution": "Noise", "airPollution": "Air pollution", "groundPollution": "Ground pollution"}
        for k, v in gr.items():
            if v.get("max"):
                w(f"- **{words[k]}:** highest {v['hotWhere']}" + (f"; across {st['word']} it averages {100 * v['startAverage'] / v['max']:.0f}% of the top" if v.get("startAverage") is not None else "") + ".")
            else:
                w(f"- **{words[k]}:** none yet.")
        w("")
    if pictures:
        w("## Pictures\n")
        for p in pictures:
            w(f"- {p}")
        w("")
    return "\n".join(out)


# --- pictures

def font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except (TypeError, AttributeError, OSError):
        return ImageFont.load_default()


def ground_colour(cls, depth, shade, height_share):
    if cls == "water":
        d = min(depth / 12.0, 1.0)
        return (int(160 - 90 * d), int(205 - 75 * d), int(235 - 40 * d))
    base = {"flat": (206, 226, 186), "gentle": (236, 228, 168), "hilly": (238, 196, 150), "steep": (176, 172, 168)}[cls]
    lift = 0.94 + 0.12 * height_share
    return tuple(max(0, min(255, int(v * shade * lift))) for v in base)


def draw_marker(d, u, v, shape, colour, r=9, outline=(20, 20, 20)):
    if shape == "diamond":
        d.polygon([(u, v - r), (u + r, v), (u, v + r), (u - r, v)], fill=colour, outline=outline)
    elif shape == "circle":
        d.ellipse([u - r, v - r, u + r, v + r], fill=colour, outline=outline, width=2)
    elif shape == "ring":
        d.ellipse([u - r, v - r, u + r, v + r], outline=colour, width=4)
    elif shape == "square":
        d.rectangle([u - r, v - r, u + r, v + r], fill=colour, outline=outline)
    elif shape == "cross":
        d.line([(u - r, v - r), (u + r, v + r)], fill=colour, width=4)
        d.line([(u - r, v + r), (u + r, v - r)], fill=colour, width=4)
    elif shape == "star":
        pts = []
        for k in range(10):
            a = math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.45
            pts.append((u + rr * math.cos(a), v - rr * math.sin(a)))
        d.polygon(pts, fill=colour, outline=outline)
    else:
        d.ellipse([u - r / 2, v - r / 2, u + r / 2, v + r / 2], fill=colour, outline=outline)


class MapPicture:
    """A top-down picture of part of the map: north up, no coordinates, a scale bar and a north arrow."""

    def __init__(self, terrain, box, width=1600, title="", subtitle=""):
        from PIL import Image, ImageDraw
        x0, x1, z0, z1 = box
        side = max(x1 - x0, z1 - z0)
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        lo, hi = terrain.extent
        half = min(side / 2, (hi - lo) / 2)
        cx = min(max(cx, lo + half), hi - half)
        cz = min(max(cz, lo + half), hi - half)
        self.box = (cx - half, cx + half, cz - half, cz + half)
        self.w = self.h = int(width)
        self.scale = self.w / (2 * half)
        self.terrain = terrain
        self.title, self.subtitle = title, subtitle
        n = terrain.n
        classes = terrain.classes()
        hmin, hmax = min(terrain.h), max(terrain.h)
        span = max(hmax - hmin, 1.0)
        # one pixel per cell, north up
        base = Image.new("RGB", (n, n))
        px = base.load()
        for r in range(n):
            for c in range(n):
                i = r * n + c
                gx, gz = terrain.gradient(r, c)
                shade = min(max(1 + 3.0 * (gx - gz) / math.sqrt(2), 0.72), 1.18)
                px[c, n - 1 - r] = ground_colour(classes[i], terrain.w[i], shade, (terrain.h[i] - hmin) / span)
        left = (self.box[0] - terrain.origin) / terrain.cell
        right = (self.box[1] - terrain.origin) / terrain.cell
        top = n - (self.box[3] - terrain.origin) / terrain.cell
        bottom = n - (self.box[2] - terrain.origin) / terrain.cell
        self.img = base.resize((self.w, self.h), Image.BILINEAR, box=(left, top, right, bottom)).convert("RGBA")
        self.layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.layer)
        self.labels = []

    def flush(self):
        """Put what's drawn so far onto the picture (so later lines go on top of earlier fills)."""
        from PIL import Image, ImageDraw
        self.img = Image.alpha_composite(self.img, self.layer)
        self.layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.layer)

    def px(self, x, z):
        return ((x - self.box[0]) * self.scale, (self.box[3] - z) * self.scale)

    def visible(self, pts, margin=50):
        return any(-margin <= u <= self.w + margin and -margin <= v <= self.h + margin for u, v in (self.px(*p) for p in pts))

    def line(self, pts, colour, width, dash=None, casing=None):
        if len(pts) < 2 or not self.visible(pts):
            return
        xy = [self.px(*p) for p in pts]
        width = max(1, int(round(width)))
        if casing:
            self._polyline(xy, casing, width + 4, dash)
        self._polyline(xy, colour, width, dash)

    def _polyline(self, xy, colour, width, dash):
        if not dash:
            self.draw.line(xy, fill=colour, width=width, joint="curve")
            return
        on, off = dash
        carry, drawing = 0.0, True
        for (ax, ay), (bx, by) in zip(xy, xy[1:]):
            seg = math.hypot(bx - ax, by - ay)
            pos = 0.0
            while pos < seg:
                step = min((on if drawing else off) - carry, seg - pos)
                if drawing and step > 0:
                    t0, t1 = pos / seg, (pos + step) / seg
                    self.draw.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)], fill=colour, width=width)
                pos += step
                carry += step
                if carry >= (on if drawing else off) - 1e-6:
                    carry, drawing = 0.0, not drawing

    def polygon(self, pts, fill, outline=None, width=2):
        if len(pts) < 3 or not self.visible(pts, margin=self.w):
            return
        xy = [self.px(*p) for p in pts]
        self.draw.polygon(xy, fill=fill)
        if outline:
            self.draw.line(xy + [xy[0]], fill=outline, width=width)

    def rect(self, box, outline, width=2, fill=None, dash=None):
        x0, x1, z0, z1 = box
        pts = [(x0, z0), (x1, z0), (x1, z1), (x0, z1), (x0, z0)]
        if fill:
            self.polygon(pts[:4], fill)
        self.line(pts, outline, width, dash=dash)

    def label(self, x, z, text, size=18, colour=(20, 20, 20), halo=(255, 255, 255, 230), anchor="mm", force=False):
        u, v = self.px(x, z)
        if not (0 <= u <= self.w and 0 <= v <= self.h):
            return False
        f = font(size)
        try:
            box = self.draw.textbbox((u, v), text, font=f, anchor=anchor, stroke_width=3)
        except (TypeError, ValueError):
            box = (u - 4 * len(text), v - size / 2, u + 4 * len(text), v + size / 2)
        if box[0] < 2 or box[2] > self.w - 2 or box[1] < 2 or box[3] > self.h - 2:
            if not force:
                return False
        if not force and any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in self.labels):
            return False
        self.labels.append(box)
        try:
            self.draw.text((u, v), text, fill=colour, font=f, anchor=anchor, stroke_width=3, stroke_fill=halo)
        except (TypeError, ValueError):
            self.draw.text((u, v), text, fill=colour, font=f)
        return True

    def free(self, x, z, r):
        """No label or badge drawn yet within r pixels of this place."""
        u, v = self.px(x, z)
        return all(u + r < b[0] or u - r > b[2] or v + r < b[1] or v - r > b[3] for b in self.labels)

    def badge(self, x, z, text, fill=(20, 20, 20), colour=(255, 255, 255), r=15):
        u, v = self.px(x, z)
        if not (0 <= u <= self.w and 0 <= v <= self.h):
            return
        self.draw.ellipse([u - r, v - r, u + r, v + r], fill=fill, outline=(255, 255, 255), width=2)
        try:
            self.draw.text((u, v), text, fill=colour, font=font(int(r * 1.15)), anchor="mm")
        except (TypeError, ValueError):
            self.draw.text((u - 4, v - 6), text, fill=colour)
        self.labels.append((u - r, v - r, u + r, v + r))

    def marker(self, x, z, shape, colour, r=9, outline=(20, 20, 20)):
        u, v = self.px(x, z)
        if -r <= u <= self.w + r and -r <= v <= self.h + r:
            draw_marker(self.draw, u, v, shape, colour, r, outline)

    def finish(self, legend=(), notes=()):
        """The picture with a title band, the map, a north arrow, a scale bar and the legend underneath."""
        from PIL import Image, ImageDraw
        self.flush()
        d = ImageDraw.Draw(self.img)
        # north arrow
        u, v = self.w - 46, 40
        d.polygon([(u, v - 26), (u + 13, v + 12), (u, v + 4), (u - 13, v + 12)], fill=(30, 30, 30), outline=(255, 255, 255))
        d.text((u, v + 26), "N", fill=(30, 30, 30), font=font(20), anchor="mm", stroke_width=3, stroke_fill=(255, 255, 255))
        # scale bar
        metres = (self.box[1] - self.box[0]) * 0.18
        nice = max(n for n in (50, 100, 200, 250, 500, 1000, 2000, 2500, 5000) if n <= max(metres, 50))
        bar = nice * self.scale
        x0, y0 = 24, self.h - 34
        d.rectangle([x0 - 8, y0 - 26, x0 + bar + 70, y0 + 16], fill=(255, 255, 255, 210))
        d.rectangle([x0, y0, x0 + bar, y0 + 8], fill=(30, 30, 30))
        d.rectangle([x0 + bar / 2, y0, x0 + bar, y0 + 8], fill=(255, 255, 255), outline=(30, 30, 30))
        d.text((x0, y0 - 4), "0", fill=(30, 30, 30), font=font(15), anchor="ls")
        d.text((x0 + bar, y0 - 4), f"{nice // 1000} km" if nice >= 1000 and nice % 1000 == 0 else f"{nice} m", fill=(30, 30, 30), font=font(15), anchor="ms")
        # title and legend bands
        title_h = 64 if self.subtitle else 44
        rows = []
        f = font(16)
        per_row, x = [], 16
        for item in legend:
            width = 46 + int(d.textlength(item[2], font=f)) + 22
            if x + width > self.w - 16 and per_row:
                rows.append(per_row)
                per_row, x = [], 16
            per_row.append((x, item))
            x += width
        if per_row:
            rows.append(per_row)
        legend_h = 16 + 28 * len(rows) + 22 * len(notes) + (10 if rows or notes else 0)
        out = Image.new("RGB", (self.w, title_h + self.h + legend_h), (250, 250, 247))
        out.paste(self.img.convert("RGB"), (0, title_h))
        od = ImageDraw.Draw(out)
        od.text((16, 12), self.title, fill=(20, 20, 20), font=font(24))
        if self.subtitle:
            od.text((16, 40), self.subtitle, fill=(80, 80, 80), font=font(16))
        y = title_h + self.h + 12
        for row in rows:
            for x, (kind, colour, text) in row:
                cy = y + 10
                if kind == "line":
                    od.line([(x, cy), (x + 34, cy)], fill=colour, width=5)
                elif kind == "dash":
                    od.line([(x, cy), (x + 12, cy)], fill=colour, width=5)
                    od.line([(x + 20, cy), (x + 34, cy)], fill=colour, width=5)
                elif kind == "box":
                    od.rectangle([x + 4, cy - 9, x + 30, cy + 9], fill=colour, outline=(60, 60, 60))
                elif kind == "outline":
                    od.rectangle([x + 4, cy - 9, x + 30, cy + 9], outline=colour, width=3)
                else:
                    draw_marker(od, x + 17, cy, kind, colour, 9, (20, 20, 20))
                od.text((x + 42, cy), text, fill=(30, 30, 30), font=f, anchor="lm")
            y += 28
        for note in notes:
            od.text((16, y + 4), note, fill=(70, 70, 70), font=font(15))
            y += 22
        return out


ROAD_STYLE = {"highway": ((205, 40, 40), 5), "road": ((90, 90, 90), 3), "train": ((25, 25, 25), 3),
              "tram": ((30, 140, 70), 2), "subway": ((120, 60, 160), 2)}


def draw_network(pic, net, faint=False, names=False):
    """The snapshot's roads, highways and tracks."""
    for kind in ("subway", "road", "tram", "train", "highway"):
        colour, width = ROAD_STYLE[kind]
        if faint:
            colour = colour + (150,)
        scale = 1.0 if pic.scale > 0.25 else 0.7
        for e in net.by_kind(kind):
            dash = (10, 7) if kind == "subway" or e.get("tunnel") else (14, 6) if kind == "train" and pic.scale > 0.4 else None
            if kind == "highway" and e.get("bridge") and not faint:
                pic.line(e["line"], (255, 255, 255), width * scale + 4)
            pic.line(e["line"], colour, max(1, width * scale * (0.6 if is_ramp(e) else 1)), dash=dash)
    if names:
        done = set()
        for e in sorted(net.by_kind("road", "highway"), key=lambda e: -(e.get("length", 0) or 0)):
            name = e["streetName"]
            if name and name not in done and pic.visible(e["line"], margin=-40):
                mid = e["line"][len(e["line"]) // 2]
                if pic.label(mid[0], mid[1], name, size=15, colour=(40, 40, 40)):
                    done.add(name)


def draw_survey(snap, s, path_map, path_start, width=1600):
    terrain = Terrain(snap)
    tiles = Tiles(snap)
    net = Network(snap)
    name = s.get("city") or "The city"
    lo, hi = terrain.extent
    owned = {t["i"] for t in tiles.owned()}
    start = set(s["start"]["tiles"])
    ranks = {b["tile"]: b["rank"] for b in s["tiles"]["buyable"]}
    resources_on = s["tiles"]["resourcesKnown"]

    def tiles_layer(pic, close):
        for t in tiles.tiles:
            if not s["start"]["allOwned"] and t["i"] in owned:
                continue
            pic.rect(t["box"], (90, 90, 90, 70 if not close else 110), 1)
        for t in tiles.tiles:
            if t["i"] in ranks and not s["start"]["allOwned"]:
                pic.rect(t["box"], (240, 150, 0, 230), 3, fill=(255, 220, 120, 40 if close else 30), dash=(12, 8))
        for t in tiles.tiles:
            if t["i"] in start:
                pic.rect(t["box"], (20, 20, 20, 255), 4 if close else 3)

    def resources_layer(pic, close):
        if not resources_on:
            return
        maxima = {k: max((t["resources"].get(k, 0) for t in tiles.tiles), default=0) for k in RESOURCES}
        top = {k: {t["i"] for t in sorted(tiles.tiles, key=lambda t: -t["resources"].get(k, 0))[:30]} for k in RESOURCES}
        size = 7 if not close else 11
        for t in tiles.tiles:
            k_on = [k for k in RESOURCES if maxima[k] and t["i"] in top[k] and t["resources"].get(k, 0) >= 0.5 * maxima[k]]
            u, v = t["box"][0], t["box"][3]
            for j, k in enumerate(k_on):
                pu, pv = pic.px(u, v)
                pu += 6 + j * (size * 2 + 3)
                pv += 6
                pic.draw.rectangle([pu, pv, pu + size * 2, pv + size * 2], fill=RESOURCE_COLOURS[k] + (230,), outline=(255, 255, 255, 230))

    def connections_layer(pic):
        for o in s["connections"]:
            colour = ROAD_STYLE.get(o["kind"], ((90, 90, 90), 3))[0]
            word = {"highway": "Highway", "train": "Railway", "road": "Road"}.get(o["kind"], o["kind"])
            for x, z in o["places"]:
                pic.marker(x, z, "diamond", colour, r=14, outline=(255, 255, 255))
                u, v = pic.px(x, z)
                dx = 22 if u < pic.w / 2 else -22
                pic.label(x + dx / pic.scale, z, word + " off the map", size=16, colour=colour, anchor="lm" if dx > 0 else "rm")

    legend = [("box", (206, 226, 186), "flat"), ("box", (236, 228, 168), "gentle"), ("box", (238, 196, 150), "hilly"),
              ("box", (176, 172, 168), "steep"), ("box", (110, 160, 215), "water"),
              ("line", (205, 40, 40), "highway"), ("dash", (25, 25, 25), "railway"), ("line", (90, 90, 90), "road"),
              ("outline", (20, 20, 20), s["start"]["word"]), ("outline", (240, 150, 0), "can buy next (best numbered)"),
              ("diamond", (205, 40, 40), "connection off the map"), ("star", (230, 90, 170), "landmark")]
    if resources_on:
        legend += [("box", RESOURCE_COLOURS[k], RESOURCE_WORDS[k]) for k in RESOURCES]
    notes = ["Slopes and water come from the snapshot's 56 m grid: right over a block, not for a single lot."]

    whole = MapPicture(terrain, [lo, hi, lo, hi], width, f"{name}: the whole map",
                       "What the land is like, what's owned, what can be bought next, and how the map connects")
    tiles_layer(whole, False)
    whole.flush()
    draw_network(whole, net)
    resources_layer(whole, False)
    for l in s["landmarks"]:
        whole.marker(*l["centre"], "star", (230, 90, 170), r=8)
    for b in s["tiles"]["buyable"][:3]:
        if not s["start"]["allOwned"]:
            whole.badge(*tiles.tiles[b["tile"]]["centre"], str(b["rank"]), fill=(200, 110, 0), r=13)
    connections_layer(whole)
    whole.finish(legend, notes).save(path_map, optimize=True)

    b = s["start"]["box"]
    margin = tiles.size * 0.9
    close = MapPicture(terrain, [b[0] - margin, b[1] + margin, b[2] - margin, b[3] + margin], width,
                       f"{name}: {s['start']['word']}, close up", "The tiles and their neighbours, with the streets' names as the game shows them")
    tiles_layer(close, True)
    close.flush()
    draw_network(close, net, names=True)
    resources_layer(close, True)
    for l in s["landmarks"]:
        if close.visible([l["centre"]], margin=-10):
            close.marker(*l["centre"], "star", (230, 90, 170), r=11)
            close.label(l["centre"][0], l["centre"][1] - 26 / close.scale, l["name"], size=14, colour=(150, 40, 110))
    for bb in s["tiles"]["buyable"][:12]:
        if not s["start"]["allOwned"]:
            close.badge(*tiles.tiles[bb["tile"]]["centre"], str(bb["rank"]), fill=(200, 110, 0), r=16)
    connections_layer(close)
    close.finish(legend, notes).save(path_start, optimize=True)


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    src = args[0]
    start = "--start" in args
    out = Path(args[args.index("--out") + 1]) if "--out" in args and args.index("--out") + 1 < len(args) else Path(".")
    width = int(args[args.index("--width") + 1]) if "--width" in args and args.index("--width") + 1 < len(args) else 1600
    width = min(max(width, 600), 1600)   # the journal shows pictures up to 1600 px wide
    path = snapshot_file(src, start)
    snap = city.load(path)
    try:
        s = survey(snap)
    except ValueError:
        print(f"{path.name} has no terrain part, so there's nothing to survey (City Manager 0.6 or later writes it).")
        return 1
    s["snapshot"] = str(path)
    s["founding"] = founding_facts(src)
    out.mkdir(parents=True, exist_ok=True)
    pictures = [out / "survey-map.png", out / "survey-start.png"]
    draw_survey(snap, s, *pictures, width=width)
    (out / "survey.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report(s, [str(p) for p in pictures] + [str(out / "survey.json")]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
