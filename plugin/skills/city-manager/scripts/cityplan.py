#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The City Manager's guide exporter: a simple plan JSON to and from the City Planning Draft mod (pdx 155935, by
nooolan; written against its version 1.2.2, schema 1.0). That mod is the build overlay: its plans are drawn over the city.

  export PLAN.json [--map-id NAME] [--terrain city.json] [--name FILE] [--out-dir DIR]
      Writes ModsData/CityPlanningDraft/Exports/<FILE>.cityplan.json. In game, the user opens the planner panel
      and presses Import, which loads the NEWEST file in Exports. Import replaces the city's plan document
      (undo with Ctrl+Z; the mod also keeps snapshots). --terrain gives the points their ground height: the City
      Manager mod's snapshot (city.json or city-start.json), or a terrain file (resolution, cellSize, worldMin, heights).
  read CITY_OR_MAPID [--plan NAME_OR_ID] [--out plan_edited.json]
      Reads <root>/<city>/planning.cityplan.json (what the user edited and saved in game) back into the simple
      format, so the build stage can use the approved geometry.
  mapid
      Prints the map_id of the most recently saved planner document.
  front "<City> <N>" [--out-dir DIR]
      Makes that guide the newest file in Exports, so the planner's Import picks it: Import loads the newest file,
      whichever city it's for. Run it before each session of a city with a guide, when another city's guide may be
      newer. It writes the same file afresh (same name, same content).

The mod's map_id is the city name from the game's bottom toolbar, set when the planner UI first opens in that
city. Import refuses a file whose map_id differs (case-insensitive), so have the user open the planner once in the
new city, then run `mapid`, or pass --map-id.

Simple PLAN.json:
{
  "name": "Backbone A",
  "roads": [{"name": "Arterial 1", "class": "Highway|Arterial|Collector|Local", "points": [[x, z], ...],
             "smoothing": "None|Light|Strong"}],
  "areas": [{"name": "Harbourside", "type": "Residential|Commercial|Industrial|Office|Custom",
             "polygon": [[x, z], ...], "fill": "#RRGGBB", "border": "#RRGGBB", "opacity": 0.38}],
  "junctions": [{"name": "Sterling", "type": "Normal|Roundabout|Overpass|Underpass|Interchange|CrossingNoConnection|Ignored",
                 "position": [x, z], "road_a": "<road name>", "road_b": "<road name>"}]
}
"plans": [ {...}, {...} ] instead of one plan gives the user alternatives (A/B) in the planner.

Naming (the Mayor's convention since 2026-11-24; export warns when it's broken):
  --name "<City> <N>"         one number that goes up by one per export; nothing else carries a version number
  plan names "<Status> · <Topic>", at most 26 characters, Status in this order top to bottom:
              Now (this session), Next, Later (parked or ideas), Base (the long-term picture), Done (one round, then dropped)
  The topic uses the journal's and the briefing's words. Move older exports to Exports/old/ after an export.
"""
import base64
import datetime
import glob
import re
import json
import math
import os
import struct
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))  # real folder, also when run through a link
from journal import LOCALLOW  # noqa: E402  the game's user-data folder ($CS2_USERDATA, Windows' own place, or Proton's)

ROOT = str(LOCALLOW / "ModsData/CityPlanningDraft")
ROAD_CLASSES = {"Highway", "Arterial", "Collector", "Local"}
AREA_TYPES = {"Residential", "Commercial", "Industrial", "Office", "Custom"}
AREA_COLOURS = {"Residential": "#22C55E", "Commercial": "#3B82F6", "Industrial": "#F59E0B", "Office": "#8B5CF6", "Custom": "#9CA3AF"}
JUNCTION_TYPES = {"Normal", "Roundabout", "Overpass", "Underpass", "Interchange", "CrossingNoConnection", "Ignored"}
SMOOTHING = {"None", "Light", "Strong"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f0Z")


def newest_map_id():
    docs = [p for p in glob.glob(os.path.join(ROOT, "*", "planning.cityplan.json"))]
    if not docs:
        return None
    p = max(docs, key=os.path.getmtime)
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f).get("map_id"), p


def height_fn(terrain_path):
    """Ground height at (x, z) from --terrain: the City Manager mod's snapshot (city.json, city-start.json), or a terrain
    file with resolution, cellSize, worldMin and a list of heights."""
    if not terrain_path:
        return lambda x, z: 100.0
    with open(terrain_path, encoding="utf-8-sig") as f:
        t = json.load(f)
    if isinstance(t.get("terrain"), dict):   # a snapshot: base64 of little-endian 16-bit decimetres, row by row
        g = t["terrain"]
        R, c, m0 = int(g["size"]), float(g["cell"]), float(g["origin"])
        raw = base64.b64decode(g["heights"])
        H = [v / 10 for v in struct.unpack(f"<{R * R}H", raw[:2 * R * R])]
    else:
        R, c, m0 = t["resolution"], t["cellSize"], t["worldMin"]
        H = t["heights"]

    def h(x, z):
        i = min(max(int((z - m0) / c), 0), R - 1); j = min(max(int((x - m0) / c), 0), R - 1)
        return float(H[i * R + j])
    return h


def pt(p, h):
    x, z = float(p[0]), float(p[1])
    if not (math.isfinite(x) and math.isfinite(z)):
        raise ValueError(f"non-finite point {p}")
    return {"x": x, "y": h(x, z), "z": z}


def _seg_hit(a1, a2, b1, b2):
    d2 = (a2[0] - a1[0], a2[1] - a1[1]); d4 = (b2[0] - b1[0], b2[1] - b1[1])
    den = d2[0] * d4[1] - d2[1] * d4[0]
    if abs(den) < 0.0001:
        return False
    v = (b1[0] - a1[0], b1[1] - a1[1])
    t = (v[0] * d4[1] - v[1] * d4[0]) / den; u = (v[0] * d2[1] - v[1] * d2[0]) / den
    return 0.001 < t < 0.999 and 0.001 < u < 0.999


def self_intersects(poly):
    """The mod's Geometry.HasSelfIntersection (v1.2.2). One crossing area makes Import refuse the WHOLE file, and the
    mod only says so in its panel status, not in its log."""
    n = len(poly)
    if n < 4:
        return False
    for i in range(n):
        i2 = (i + 1) % n
        for j in range(i + 1, n):
            j2 = (j + 1) % n
            if i != j and i2 != j and j2 != i and not (i == 0 and j2 == 0) and _seg_hit(poly[i], poly[i2], poly[j], poly[j2]):
                return True
    return False


def build_plan(src, h):
    errors = []
    plan = {"id": uuid.uuid4().hex, "name": src.get("name", "Backbone"), "read_only": False, "reference_visible": False,
            "created_at": now(), "modified_at": now(), "roads": [], "areas": [], "junctions": []}
    ids = {}
    for r in src.get("roads", []):
        cls = r.get("class", "Local")
        if cls not in ROAD_CLASSES: errors.append(f"road {r.get('name')}: class {cls}")
        if len(r.get("points", [])) < 2: errors.append(f"road {r.get('name')}: needs >= 2 points")
        rid = uuid.uuid4().hex; ids[r.get("name", rid)] = rid
        plan["roads"].append({"object_type": "road", "road_class": cls, "points": [pt(p, h) for p in r["points"]],
                              "smoothing": r.get("smoothing", "Light"), "id": rid, "name": r.get("name", ""),
                              "locked": False, "created_at": now(), "modified_at": now()})
    for a in src.get("areas", []):
        typ = a.get("type", "Custom")
        if typ not in AREA_TYPES: errors.append(f"area {a.get('name')}: type {typ}")
        if len(a.get("polygon", [])) < 3: errors.append(f"area {a.get('name')}: needs >= 3 points")
        elif self_intersects([(float(q[0]), float(q[1])) for q in a["polygon"]]):
            errors.append(f"area {a.get('name')}: outline crosses itself (the mod would refuse the whole import)")
        area = {"object_type": "area", "area_type": typ, "polygon": [pt(p, h) for p in a["polygon"]],
                "smoothing": a.get("smoothing", "None"), "id": uuid.uuid4().hex, "name": a.get("name", ""),
                "locked": False, "created_at": now(), "modified_at": now()}
        # The planner writes all three on every area; these defaults are the zone colours it uses itself.
        area["fill_color"] = a.get("fill", AREA_COLOURS.get(typ, AREA_COLOURS["Custom"]))
        area["border_color"] = a.get("border", area["fill_color"])
        area["opacity"] = a.get("opacity", 0.5)
        plan["areas"].append(area)
    for j in src.get("junctions", []):
        typ = j.get("type", "Normal")
        if typ not in JUNCTION_TYPES: errors.append(f"junction {j.get('name')}: type {typ}")
        if j.get("road_a") not in ids or j.get("road_b") not in ids:
            errors.append(f"junction {j.get('name')}: road_a/road_b must name roads in this plan"); continue
        plan["junctions"].append({"object_type": "junction", "road_a": ids[j["road_a"]], "road_b": ids[j["road_b"]],
                                  "position": pt(j["position"], h), "junction_type": typ, "connected": typ in ("Normal", "Roundabout", "Interchange"),
                                  "candidate": False, "manual_override": True, "id": uuid.uuid4().hex, "name": j.get("name", ""),
                                  "locked": False, "created_at": now(), "modified_at": now()})
    return plan, errors


STATUSES = ["Now", "Next", "Later", "Base", "Done"]
PLAN_NAME = re.compile(r"(%s) · \S.*" % "|".join(STATUSES))


def naming_problems(file_name, plan_names):
    """Where an export breaks the naming convention (see the docstring)."""
    out = []
    if not (file_name and re.fullmatch(r".*\S \d+", file_name)):
        out.append(f"file {file_name!r} should be \"<City> <N>\", like \"Riverton 4\"")
    order = []
    for n in plan_names:
        m = PLAN_NAME.fullmatch(n)
        if not m:
            out.append(f"plan {n!r} should be \"<Status> · <Topic>\" with Status one of {', '.join(STATUSES)}")
            continue
        if len(n) > 26:
            out.append(f"plan {n!r} is {len(n)} characters; the planner cuts it after about 26")
        order.append(STATUSES.index(m.group(1)))
    if order != sorted(order):
        out.append("plans should run Now, Next, Later, Base, Done from the top")
    return out


# --- the Mayor's own drawings: what changed in the planner since the guide it holds

NUDGE = 8.0   # metres: a move under one zoning cell is a nudge (an accidental drag), not a change
KINDS = ("roads", "areas", "junctions")


def read_doc(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) and isinstance(doc.get("plans"), list) else None
    except (OSError, ValueError):
        return None


def planner_doc(map_id):
    """The planner's own document for a map id, as (path, doc), or (None, None): the newest saved one."""
    best = None
    for path in glob.glob(os.path.join(ROOT, "*", "planning.cityplan.json")):
        doc = read_doc(path)
        if doc and str(doc.get("map_id", "")).casefold() == str(map_id).casefold():
            if best is None or os.path.getmtime(path) > best[0]:
                best = (os.path.getmtime(path), path, doc)
    return (best[1], best[2]) if best else (None, None)


def guide_docs(map_id):
    """This map id's guides in Exports and Exports/old: [(path, doc)], newest first."""
    out = []
    for path in glob.glob(os.path.join(ROOT, "Exports", "*.cityplan.json")) + glob.glob(os.path.join(ROOT, "Exports", "old", "*.cityplan.json")):
        doc = read_doc(path)
        if doc and str(doc.get("map_id", "")).casefold() == str(map_id).casefold():
            out.append((path, doc))
    return sorted(out, key=lambda pd: os.path.getmtime(pd[0]), reverse=True)


def doc_items(doc):
    """{item id: (plan id, plan name, kind, item)} for a planner document or a guide."""
    out = {}
    for p in doc.get("plans", []):
        if not isinstance(p, dict):
            continue
        for kind in KINDS:
            for it in p.get(kind) or []:
                if isinstance(it, dict) and it.get("id"):
                    out[it["id"]] = (p.get("id"), p.get("name") or "", kind, it)
    return out


def item_xz(kind, it):
    q = it.get("polygon") if kind == "areas" else [it["position"]] if kind == "junctions" and isinstance(it.get("position"), dict) else it.get("points")
    return [(float(v.get("x", 0)), float(v.get("z", 0))) for v in q or [] if isinstance(v, dict)]


def type_of(kind, it):
    return it.get({"roads": "road_class", "areas": "area_type", "junctions": "junction_type"}[kind])


def simple_item(kind, it, road_names):
    """A planner item in the simple plan format (as `read` writes it)."""
    name = it.get("name") or ""
    xz = [[round(x, 1), round(z, 1)] for x, z in item_xz(kind, it)]
    if kind == "roads":
        out = {"name": name, "class": it.get("road_class", "Local"), "points": xz}
        if it.get("smoothing"):
            out["smoothing"] = it["smoothing"]
    elif kind == "areas":
        out = {"name": name, "type": it.get("area_type", "Custom"), "polygon": xz}
        if it.get("fill_color"):
            out["fill"] = it["fill_color"]
    else:
        out = {"name": name, "type": it.get("junction_type", "Normal"), "position": xz[0] if xz else [0, 0],
               "road_a": road_names.get(it.get("road_a"), it.get("road_a")), "road_b": road_names.get(it.get("road_b"), it.get("road_b"))}
    return out


def displacement(a, b):
    """How far an item moved: the largest move of one of its points, or None when its outline changed shape."""
    if len(a) != len(b):
        return None
    return max((math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(a, b)), default=0.0)


def mayor_changes(map_id):
    """What changed in the planner's document since the guide it holds, or None without a planner document. The guide
    is the export sharing the most item ids with the document (Import keeps the ids; each export makes new ones)."""
    path, doc = planner_doc(map_id)
    if not doc:
        return None
    pi = doc_items(doc)
    held, gi, gdoc, shared = None, {}, None, 0
    for gpath, g in guide_docs(map_id):
        items = doc_items(g)
        n = len(set(pi) & set(items))
        if n > shared:
            held, gi, gdoc, shared = gpath, items, g, n
    names = {i: (v[3].get("name") or "") for i, v in pi.items() if v[2] == "roads"}
    gnames = {i: (v[3].get("name") or "") for i, v in gi.items() if v[2] == "roads"}
    gplans = {p.get("id"): p.get("name") for p in (gdoc or {}).get("plans", []) if isinstance(p, dict)}
    pplans = {p.get("id"): p.get("name") for p in doc.get("plans", []) if isinstance(p, dict)}

    def entry(v, road_names, **kw):
        return dict({"plan": v[1], "kind": v[2], "name": v[3].get("name") or "", "item": simple_item(v[2], v[3], road_names),
                     "modified": v[3].get("modified_at")}, **kw)
    ch = {"planner": path, "guide": held, "shared": shared, "added": [], "deleted": [], "changed": [], "nudged": [],
          "plans_added": [pplans[i] for i in pplans if i not in gplans] if gdoc else [],
          "plans_deleted": [gplans[i] for i in gplans if i not in pplans],
          "plans_renamed": [(gplans[i], pplans[i]) for i in pplans if i in gplans and gplans[i] != pplans[i]]}
    for i, v in pi.items():
        if i not in gi:
            ch["added"].append(entry(v, names))
            continue
        g = gi[i]
        what = []
        if (v[3].get("name") or "") != (g[3].get("name") or ""):
            what.append(f"renamed from {g[3].get('name') or '(no name)'!r}")
        if type_of(v[2], v[3]) != type_of(g[2], g[3]):
            what.append(f"{type_of(g[2], g[3])} → {type_of(v[2], v[3])}")
        if v[0] != g[0]:
            what.append(f"moved from the plan {g[1]!r}")
        d = displacement(item_xz(v[2], v[3]), item_xz(g[2], g[3]))
        if d is None:
            what.append("reshaped")
        elif d > NUDGE:
            what.append(f"moved up to {d:,.0f} m")
        if what:
            ch["changed"].append(entry(v, names, was={"plan": g[1], "name": g[3].get("name") or ""}, what=what))
        elif d and d > 0.5:
            ch["nudged"].append(entry(v, names, metres=round(d, 1)))
    for i, g in gi.items():
        if i not in pi:
            ch["deleted"].append(entry(g, gnames))
    ch["count"] = (len(ch["added"]) + len(ch["deleted"]) + len(ch["changed"]) + len(ch["plans_added"])
                   + len(ch["plans_deleted"]) + len(ch["plans_renamed"]))
    return ch


def a_kind(kind):
    return {"roads": "a road", "areas": "an area", "junctions": "a junction"}.get(kind, kind)


def changes_markdown(ch, newest_guide=None, limit=40):
    """The Mayor's planner changes as Markdown for the chat."""
    if ch is None:
        return "No planner document for this city yet (the Mayor hasn't opened City Planning Draft in it)."
    held = os.path.basename(ch["guide"])[: -len(".cityplan.json")] if ch["guide"] else None
    lines = []
    if held:
        lines.append(f"The planner holds the guide **{held}**" + (f" ({newest_guide}, the newest, isn't imported yet)" if newest_guide and newest_guide != held else "") + ".")
    else:
        lines.append("The planner holds none of this city's guides: everything in it is the Mayor's own (or from a guide no longer in Exports).")
    if not ch["count"]:
        lines.append("Nothing drawn, moved or deleted since" + (f" ({len(ch['nudged'])} item{'s' if len(ch['nudged']) != 1 else ''} nudged a few metres, left as planned)" if ch["nudged"] else "") + ".")
        return "\n\n".join(lines) + "\n"
    rows = []
    for old, new in ch["plans_renamed"]:
        rows.append(("plan renamed", new, f"was {old!r}"))
    for p in ch["plans_added"]:
        rows.append(("new plan", p, ""))
    for p in ch["plans_deleted"]:
        rows.append(("plan deleted", p, ""))
    for e in ch["added"]:
        rows.append((f"drew {a_kind(e['kind'])}", e["plan"], (e["name"] or "(no name)") + f" ({e['item'].get('class') or e['item'].get('type')})"))
    for e in ch["changed"]:
        rows.append((f"changed {a_kind(e['kind'])}", e["plan"], (e["name"] or "(no name)") + ": " + "; ".join(e["what"])))
    for e in ch["deleted"]:
        rows.append((f"deleted {a_kind(e['kind'])}", e["plan"], e["name"] or "(no name)"))
    lines.append(f"Since then the Mayor made {ch['count']} change{'s' if ch['count'] != 1 else ''} in the planner"
                 + (f" (and nudged {len(ch['nudged'])} item{'s' if len(ch['nudged']) != 1 else ''} a few metres, left as planned)" if ch["nudged"] else "") + ":")
    table = ["| What | Plan | Item |", "|---|---|---|"] + [f"| {a} | {b} | {c} |" for a, b, c in rows[:limit]]
    if len(rows) > limit:
        table.append(f"| … | | and {len(rows) - limit} more |")
    return "\n\n".join(lines) + "\n\n" + "\n".join(table) + "\n"


def pending(ch, plan_doc):
    """The changes the plan file doesn't have yet (after --keep-mayor, the planner still holds the old guide until the
    Mayor imports the new one): a copy of ch with those left, and "kept" counting the ones already in."""
    plans = plan_doc["plans"] if isinstance(plan_doc.get("plans"), list) else [plan_doc]
    by = {q.get("name"): q for q in plans if isinstance(q, dict)}

    def xz(it):
        q = it.get("points") or it.get("polygon") or ([it["position"]] if it.get("position") else [])
        return [(float(v[0]), float(v[1])) for v in q if isinstance(v, (list, tuple)) and len(v) >= 2]

    def has(plan, kind, name, item=None):
        p = by.get(plan)
        it = next((x for x in (p or {}).get(kind) or [] if isinstance(x, dict) and x.get("name") == name), None)
        if it is None or item is None:
            return it is not None
        d = displacement(xz(it), xz(item))
        return d is not None and d <= NUDGE

    out = dict(ch)
    out["added"] = [e for e in ch["added"] if not has(e["plan"], e["kind"], e["item"]["name"] or e["name"], e["item"])]
    out["changed"] = [e for e in ch["changed"] if not has(e["plan"], e["kind"], e["item"]["name"] or e["name"], e["item"])]
    out["deleted"] = [e for e in ch["deleted"] if has(e["plan"], e["kind"], e["name"])]
    out["plans_added"] = [n for n in ch["plans_added"] if n not in by]
    out["plans_deleted"] = [n for n in ch["plans_deleted"] if n in by]
    out["plans_renamed"] = [(a, b) for a, b in ch["plans_renamed"] if not (b in by and a not in by)]
    out["count"] = sum(len(out[k]) for k in ("added", "deleted", "changed", "plans_added", "plans_deleted", "plans_renamed"))
    out["kept"] = ch["count"] - out["count"]
    return out


def keep_changes(plan_doc, ch):
    """Puts the Mayor's planner changes into a simple plan document (in place). The guide's plan and item names find
    the plan file's own; returns (applied lines, lines that couldn't be placed)."""
    plans = plan_doc["plans"] if isinstance(plan_doc.get("plans"), list) else [plan_doc]
    done, missed = [], []

    def find_plan(name):
        p = next((q for q in plans if q.get("name") == name), None)
        if p is None and " · " in (name or ""):
            topic = name.split(" · ", 1)[1]
            p = next((q for q in plans if str(q.get("name", "")).split(" · ", 1)[-1] == topic), None)
        return p

    def plan_for(name):
        p = find_plan(name)
        if p is None:
            p = {"name": name, "roads": [], "areas": [], "junctions": []}
            plans.append(p)
            done.append(f"new plan {name!r}")
        for kind in KINDS:
            p.setdefault(kind, [])
        return p

    def find_item(plan_name, kind, name):
        p = find_plan(plan_name)
        if p is None:
            return None, None
        it = next((x for x in p.get(kind) or [] if isinstance(x, dict) and x.get("name") == name), None)
        return p, it

    def unique(p, kind, name, fallback):
        name = name or fallback
        have = {x.get("name") for x in p.get(kind) or [] if isinstance(x, dict)}
        base, n = name, 2
        while name in have:
            name, n = f"{base} ({n})", n + 1
        return name

    for old, new in ch["plans_renamed"]:
        p = find_plan(old)
        if p is not None:
            p["name"] = new
            done.append(f"plan {old!r} renamed {new!r}")
        else:
            missed.append(f"plan {old!r} renamed {new!r}: no such plan in the plan file")
    for e in ch["deleted"]:
        p, it = find_item(e["plan"], e["kind"], e["name"])
        if it is not None:
            p[e["kind"]].remove(it)
            done.append(f"{e['name']!r} deleted from {p.get('name')!r}")
        else:
            missed.append(f"{e['name']!r} deleted in {e['plan']!r}: not in the plan file any more")
    for e in ch["changed"]:
        p, it = find_item(e["was"]["plan"], e["kind"], e["was"]["name"])
        if it is None:
            missed.append(f"{e['was']['name']!r} in {e['was']['plan']!r} ({'; '.join(e['what'])}): not in the plan file any more")
            continue
        new = dict(it)
        for k in ("points", "polygon", "position", "class", "type", "road_a", "road_b"):
            if k in e["item"]:
                new[k] = e["item"][k]
        new["name"] = e["item"]["name"] or it.get("name")
        target = plan_for(e["plan"]) if e["plan"] != e["was"]["plan"] else p
        p[e["kind"]].remove(it)
        target[e["kind"]].append(new)
        done.append(f"{new['name']!r} in {target.get('name')!r}: " + "; ".join(e["what"]))
    for e in ch["added"]:
        p = plan_for(e["plan"])
        it = dict(e["item"], name=unique(p, e["kind"], e["item"]["name"], f"Mayor's {e['kind'][:-1]}"))
        p[e["kind"]].append(it)
        done.append(f"{it['name']!r} added to {p.get('name')!r}")
    for name in ch["plans_deleted"]:
        p = find_plan(name)
        if p is not None:
            plans.remove(p)
            done.append(f"plan {name!r} deleted")
    if not isinstance(plan_doc.get("plans"), list) and plans:
        plan_doc.clear()
        plan_doc["plans"] = plans
    return done, missed


def cmd_export(args):
    with open(args.pop(0), encoding="utf-8-sig") as f:
        src = json.load(f)
    map_id = name = out_dir = terrain = None
    while args:
        a = args.pop(0)
        if a == "--map-id": map_id = args.pop(0)
        elif a == "--terrain": terrain = args.pop(0)
        elif a == "--name": name = args.pop(0)
        elif a == "--out-dir": out_dir = args.pop(0)
    if not map_id:
        found = newest_map_id()
        if not found:
            sys.exit("no planner document found; have the user open the planner in the city, or pass --map-id")
        map_id, path = found
        print(f"map_id from the newest planner document: {map_id!r} ({path})")
    h = height_fn(terrain)
    plans, errors = [], []
    for p in src.get("plans", [src]):
        plan, e = build_plan(p, h); plans.append(plan); errors += e
    if errors:
        sys.exit("not written:\n  " + "\n  ".join(errors))
    for w in naming_problems(name, [p["name"] for p in plans]):
        print("naming:", w)
    doc = {"schema_version": "1.0", "map_id": map_id, "active_plan_id": plans[0]["id"], "plans": plans}
    out_dir = out_dir or os.path.join(ROOT, "Exports")
    os.makedirs(out_dir, exist_ok=True)
    name = name or f"{map_id} draft {datetime.datetime.now():%Y%m%d-%H%M%S}"
    path = os.path.join(out_dir, name + ".cityplan.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    n = sum(len(p["roads"]) for p in plans), sum(len(p["areas"]) for p in plans), sum(len(p["junctions"]) for p in plans)
    print(f"wrote {path}: {len(plans)} plan(s), {n[0]} roads, {n[1]} areas, {n[2]} junctions")
    print("In game: open the City Planning Draft panel and press Import (it loads the newest file in Exports).")


def cmd_front(args):
    name = args.pop(0)
    out_dir = None
    while args:
        a = args.pop(0)
        if a == "--out-dir": out_dir = args.pop(0)
    out_dir = out_dir or os.path.join(ROOT, "Exports")
    path = os.path.join(out_dir, name if name.endswith(".cityplan.json") else name + ".cityplan.json")
    if not os.path.isfile(path):
        have = sorted(f[:-len(".cityplan.json")] for f in os.listdir(out_dir) if f.endswith(".cityplan.json")) if os.path.isdir(out_dir) else []
        sys.exit(f"no guide {os.path.basename(path)!r} in {out_dir}" + (f"; there are: {', '.join(have)}" if have else ""))
    with open(path, "rb") as f:
        data = f.read()
    json.loads(data.decode("utf-8-sig"))      # a guide, not something else
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)                     # a fresh file: newest by every clock a file has
    others = [f for f in os.listdir(out_dir) if f.endswith(".cityplan.json") and os.path.join(out_dir, f) != path]
    newer = [f for f in others if os.path.getmtime(os.path.join(out_dir, f)) > os.path.getmtime(path)]
    print(f"{os.path.basename(path)} is now the newest guide in {out_dir}" + (f" (still newer: {', '.join(newer)})" if newer else "") +
          ". In game: open City Planning Draft and press Import latest file.")


def cmd_read(args):
    city = args.pop(0); plan_sel = out = None
    while args:
        a = args.pop(0)
        if a == "--plan": plan_sel = args.pop(0)
        elif a == "--out": out = args.pop(0)
    path = os.path.join(ROOT, city, "planning.cityplan.json")
    with open(path, encoding="utf-8-sig") as f:
        doc = json.load(f)
    plans = doc["plans"]
    plan = next((p for p in plans if plan_sel in (p["id"], p["name"])), None) if plan_sel else \
        next((p for p in plans if p["id"] == doc.get("active_plan_id")), plans[0])
    by_id = {r["id"]: r.get("name") or r["id"] for r in plan["roads"]}
    simple = {"name": plan["name"], "map_id": doc["map_id"], "source": path,
              "roads": [{"name": r.get("name") or r["id"], "class": r["road_class"], "smoothing": r.get("smoothing"),
                         "points": [[p["x"], p["z"]] for p in r["points"]]} for r in plan["roads"]],
              "areas": [{"name": a.get("name") or a["id"], "type": a["area_type"], "polygon": [[p["x"], p["z"]] for p in a["polygon"]]}
                        for a in plan["areas"]],
              "junctions": [{"name": j.get("name") or j["id"], "type": j["junction_type"], "position": [j["position"]["x"], j["position"]["z"]],
                             "road_a": by_id.get(j["road_a"], j["road_a"]), "road_b": by_id.get(j["road_b"], j["road_b"]),
                             "connected": j.get("connected")} for j in plan["junctions"]]}
    text = json.dumps(simple, ensure_ascii=False, indent=1)
    if out:
        Path(out).write_text(text, encoding="utf-8"); print(f"wrote {out}: {len(simple['roads'])} roads, {len(simple['areas'])} areas, {len(simple['junctions'])} junctions (plan {plan['name']!r}, of {len(plans)})")
    else:
        print(text)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):   # UTF-8 out, whatever the console (plan names hold a "·")
        stream.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    rest = sys.argv[2:]
    if cmd == "export": cmd_export(rest)
    elif cmd == "read": cmd_read(rest)
    elif cmd == "front" and rest: cmd_front(rest)
    elif cmd == "mapid":
        found = newest_map_id(); print(found if found else "none")
    else:
        sys.exit(__doc__)
