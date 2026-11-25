"""A small made-up city snapshot for the survey and plan tests: Riverton, a 1,792 m map of 5 × 5 tiles.

- Ground: flat at 50 m; a river two cells wide in the west running north to south (it falls to the south); a steep hill
  (30%) in the east, past x 450; a gentle-to-hilly rise (10%) in the north, past z 600.
- Tiles: 358.4 m each; the city owns the middle one and the one west of it (the river runs through that one).
- Network: Ring Highway west to east at z 300 (off the map at both ends), on a bridge between x -400 and 0; Entry Highway
  leaves it at x 0 and ends at z 150, where Main Street carries on south; Old Lane crosses the highway at grade at x 400;
  a railway north to south at x 250, off the map at both ends.
- An Old Mill Ruins landmark, a catalogue with one locked road and one locked interchange, grids of land value (all zero).
"""
import base64
import copy
import struct

N, CELL, ORIGIN = 32, 56.0, -896.0
TILE = 1792.0 / 5


def ground(x, z):
    h = 50.0
    if x > 450:
        h += (x - 450) * 0.30
    if z > 600:
        h += (z - 600) * 0.10
    return h


def river(c):
    return c in (5, 6)


def grid16(values):
    return base64.b64encode(struct.pack(f"<{len(values)}H", *values)).decode()


def terrain():
    heights, water = [], []
    for r in range(N):
        for c in range(N):
            x, z = ORIGIN + (c + 0.5) * CELL, ORIGIN + (r + 0.5) * CELL
            if river(c):
                bed = 46.0 + r * 0.1          # higher in the north: the river flows south
                heights.append(int(round(bed * 10)))
                water.append(30)              # 3 m deep
            else:
                heights.append(int(round(ground(x, z) * 10)))
                water.append(0)
    return {"size": N, "cell": CELL, "origin": ORIGIN, "heights": grid16(heights), "water": grid16(water)}


def tile_box(row, col):
    x0, z0 = ORIGIN + col * TILE, ORIGIN + row * TILE
    return [round(x0, 1), round(x0 + TILE, 1), round(z0, 1), round(z0 + TILE, 1)]


OWNED = {(2, 2), (2, 1)}


def map_tiles(owned=OWNED):
    tiles = []
    for row in range(5):
        for col in range(5):
            res = {"Area": TILE * TILE, "BuildableLand": TILE * TILE * (0.3 if col == 4 else 0.85 if col in (0, 1) else 1.0)}
            if col == 0:
                res["FertileLand"] = 90000.0
            if row == 4:
                res["Forest"] = 50000.0
            if (row, col) == (1, 2):
                res["Oil"] = 400000.0
            if col == 4:
                res["Ore"] = 300000.0
            if col in (0, 1):
                res["Fish"] = 20000.0
            if (row, col) == (3, 2):
                res["GroundWater"] = 80000.0
            tiles.append({"owned": (row, col) in owned, "box": tile_box(row, col), "resources": res})
    return tiles


def bez(x0, z0, x1, z1, y=50.0):
    return [[x0, z0, y], [x0 + (x1 - x0) / 3, z0 + (z1 - z0) / 3, y], [x0 + 2 * (x1 - x0) / 3, z0 + 2 * (z1 - z0) / 3, y], [x1, z1, y]]


PREFABS = ["Highway Twoway - 4 lanes", "Gravel Road", "Medium Road", "Double Train Track", "OldMillRuins"]
TITLES = ["Four-Lane Two-Way Highway", "Gravel Road", "Four-Lane Road", "Double Train Track", "Old Mill Ruins"]
STREETS = ["Ring Highway", "Entry Highway", "Main Street", "Old Lane"]


def network():
    nodes = [
        {"id": 1, "x": -895.0, "z": 300.0, "y": 50.0, "outside": True},
        {"id": 2, "x": -400.0, "z": 300.0, "y": 50.0},
        {"id": 3, "x": 0.0, "z": 300.0, "y": 50.0},
        {"id": 4, "x": 400.0, "z": 300.0, "y": 50.0, "lights": True},
        {"id": 5, "x": 895.0, "z": 300.0, "y": 50.0, "outside": True},
        {"id": 6, "x": 0.0, "z": 150.0, "y": 50.0},
        {"id": 7, "x": 0.0, "z": -150.0, "y": 50.0},
        {"id": 8, "x": 400.0, "z": 100.0, "y": 50.0},
        {"id": 9, "x": 400.0, "z": 600.0, "y": 50.0},
        {"id": 10, "x": 250.0, "z": -895.0, "y": 50.0, "outside": True},
        {"id": 11, "x": 250.0, "z": 895.0, "y": 50.0, "outside": True},
    ]
    nd = {n["id"]: n for n in nodes}

    def edge(i, a, b, prefab, kind, street=None, **kw):
        e = {"id": 100 + i, "prefab": prefab, "kind": kind, "a": a, "b": b,
             "length": round(((nd[a]["x"] - nd[b]["x"]) ** 2 + (nd[a]["z"] - nd[b]["z"]) ** 2) ** 0.5, 1),
             "pts": bez(nd[a]["x"], nd[a]["z"], nd[b]["x"], nd[b]["z"])}
        if street is not None:
            e["street"] = street
        e.update(kw)
        return e

    edges = [
        edge(1, 1, 2, 0, "highway", 0, lanes=[2, 2]),
        edge(2, 2, 3, 0, "highway", 0, lanes=[2, 2], bridge=True, elevation=[8.0, 8.0]),
        edge(3, 3, 4, 0, "highway", 0, lanes=[2, 2]),
        edge(4, 4, 5, 0, "highway", 0, lanes=[2, 2]),
        edge(5, 3, 6, 0, "highway", 1, lanes=[2, 2]),
        edge(6, 6, 7, 2, "road", 2, lanes=[2, 2]),
        edge(7, 8, 4, 1, "road", 3, lanes=[1, 1]),
        edge(8, 4, 9, 1, "road", 3, lanes=[1, 1]),
        edge(9, 10, 11, 3, "train"),
    ]
    return nodes, edges


CATALOGUE = {"milestone": 3, "items": [
    {"prefab": "Small Road", "title": "Two-Lane Road", "kind": "road", "unlocked": True, "menu": "Small Roads", "costPerKm": 4000, "upkeepPerKm": 487.0, "lanes": [1, 1]},
    {"prefab": "Medium Road", "title": "Four-Lane Road", "kind": "road", "unlocked": True, "menu": "Medium Roads", "costPerKm": 5500, "upkeepPerKm": 713.0, "lanes": [2, 2]},
    {"prefab": "Large Road", "title": "Six-Lane Road", "kind": "road", "unlocked": False, "milestone": 6, "menu": "Large Roads", "costPerKm": 7000, "upkeepPerKm": 938.0},
    {"prefab": "Highway Oneway - 1 lane", "title": "One-Lane One-Way Highway", "kind": "highway", "unlocked": True, "menu": "Highways", "costPerKm": 1000, "upkeepPerKm": 150.0, "lanes": [1, 0]},
    {"prefab": "Intersection 10 Trumpet", "title": "Trumpet Intersection", "kind": "junction", "unlocked": False, "milestone": 8, "menu": "Intersections", "upkeep": 975},
]}


def snapshot(owned=OWNED, parts=True):
    """The made-up city. parts=False leaves out what older snapshots lack (map tiles, grids, catalogue)."""
    nodes, edges = network()
    owned_tiles = [t for t in map_tiles(owned) if t["owned"]]
    snap = {
        "format": 1, "mod": "0.8.0", "taken": "2026-11-24T20:00:00Z", "why": "start", "session": {"start": "2026-11-24T19:59:55Z"},
        "city": {"name": "Riverton", "population": 0, "happiness": 50, "money": 500000, "unlimitedMoney": False, "xp": 0,
                 "milestone": 3, "tiles": len(owned_tiles), "date": {"year": 2026, "month": 1, "hour": 8, "minute": 0, "text": "January 2026, 08:00"}},
        "budget": {"income": {}, "expenses": {}, "totalIncome": 0, "totalExpenses": 0, "balance": 0},
        "prefabs": PREFABS, "prefabTitles": TITLES, "streets": STREETS,
        "nodes": nodes, "edges": edges,
        "buildings": [{"id": 50, "prefab": 4, "kind": "other", "name": "Old Mill Ruins", "lot": [2, 2], "x": -300.0, "z": -100.0, "y": 50.0, "angle": 0}],
        "districts": [], "tiles": [t["box"] for t in owned_tiles],
        "terrain": terrain(), "truncated": [],
    }
    if parts:
        snap["mapTiles"] = {"permitsLeft": 3, "tiles": map_tiles(owned)}
        snap["grids"] = {"size": 8, "cell": 224.0, "origin": ORIGIN, **{k: grid16([0] * 64) for k in
                         ("landValue", "groundPollution", "airPollution", "noisePollution")}}
        snap["catalogue"] = copy.deepcopy(CATALOGUE)
    return snap
