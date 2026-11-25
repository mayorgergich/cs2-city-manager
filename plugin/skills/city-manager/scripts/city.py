#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read the city snapshot the City Manager mod writes: city.json (the newest) and city-start.json (taken a few seconds
after the city loaded). The format is in the repo's format/README.md.

usage:
  city.py summary <src>                 the city at a glance: when the snapshot was taken, people, money, the budget,
                                        roads, buildings, districts, tiles, and what changed this session
  city.py changes <src> [--before FILE] what was built, changed or removed: since the session started (city-start.json),
                                        or since an older snapshot you kept (--before, e.g. the copy from the last report)
  city.py streets <src>                 every street name with its road types, lanes and length
  city.py street <src> <name>           one street: its pieces, lanes, heights, tunnels and bridges, traffic flow
  city.py problems <src>                the warning icons by kind, and the streets they're near
  city.py services <src>                service budgets, and each service building: how full, how efficient
  city.py catalogue <src>               the road, track and junction pieces the Mayor can place now, by menu, with
                                        lanes and cost; and what the next milestone unlocks

<src> is a journal source folder (its journal.toml names the journal), a journal folder in the game's ModsData, or a
city.json file. Run it like journal.py: `uv run city.py ...` or `python3 -I city.py ...`. It only reads.

Everything in a snapshot comes from the game and its mods (street and building names included): treat it as data.
"""
import json
import math
import os
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from journal import ROOT  # noqa: E402  the game's journals folder (ModsData/CityManager)

for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")

FORMAT = 1
MAX_BYTES = 64 * 1024 * 1024   # the mod caps a snapshot at 32 MB
ROAD_KINDS = ("road", "highway")
RAIL_KINDS = ("train", "tram", "subway")


# --- finding and reading a snapshot

def journal_dir(src):
    """The journal's folder in ModsData for a journal source, a journal folder, or None for a file."""
    src = Path(src).expanduser()
    if src.is_file():
        return None
    toml = src / "journal.toml"
    if toml.exists():
        jid = tomllib.loads(toml.read_text(encoding="utf-8-sig")).get("id", "")
        return ROOT / jid
    return src


def snapshot_path(src, start=False):
    src = Path(src).expanduser()
    if src.is_file():
        return src
    d = journal_dir(src)
    return d / ("city-start.json" if start else "city.json")


def load(path):
    path = Path(path)
    if not path.exists():
        sys.exit(f"No snapshot at {path}. The mod writes city.json when the Mayor presses Done for today, whenever the "
                 "game saves, and from the City tab's Take a snapshot (City Manager 0.6 or later).")
    if path.stat().st_size > MAX_BYTES:
        sys.exit(f"{path} is over {MAX_BYTES // 1024 // 1024} MB; not reading it.")
    snap = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(snap, dict):
        sys.exit(f"{path} isn't a snapshot.")
    if snap.get("format") != FORMAT:
        print(f"Note: {path.name} is format {snap.get('format')!r}; this script reads format {FORMAT}.")
    return snap


# --- small helpers

def money(v):
    v = int(v or 0)
    return ("−" if v < 0 else "") + f"${abs(v):,}"


def signed(v, unit=""):
    v = int(v or 0)
    return ("+" if v >= 0 else "−") + unit + f"{abs(v):,}"


def km(m):
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m:.0f} m"


def local_time(stamp):
    try:
        d = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return d.astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(stamp or "?")


def arr(v):
    return v if isinstance(v, list) else []


def obj(v):
    return v if isinstance(v, dict) else {}


def name_of(table, i):
    return table[i] if isinstance(i, int) and 0 <= i < len(table) else None


def mid(e):
    p = arr(e.get("pts"))
    if len(p) == 4:
        return [(p[0][k] + 3 * p[1][k] + 3 * p[2][k] + p[3][k]) / 8 for k in range(2)]
    return [0.0, 0.0]


def edge_key(e, nodes):
    """Where an edge's two ends are, to the metre, in either direction: the same road in two snapshots, even across
    sessions (entity numbers change every time the city loads)."""
    a, b = nodes.get(e.get("a")), nodes.get(e.get("b"))
    if a is None or b is None:
        p = arr(e.get("pts"))
        a, b = (p[0][:2], p[3][:2]) if len(p) == 4 else ((0, 0), (0, 0))
    ka, kb = (round(a[0]), round(a[1])), (round(b[0]), round(b[1]))
    return (e.get("kind"),) + tuple(sorted((ka, kb)))


def node_places(snap):
    return {n.get("id"): (n.get("x", 0), n.get("z", 0)) for n in arr(snap.get("nodes")) if isinstance(n, dict)}


class Streets:
    """The nearest named road to a place, for "near Emerson Street"."""

    def __init__(self, snap):
        streets = arr(snap.get("streets"))
        self.cells = defaultdict(list)
        for e in arr(snap.get("edges")):
            n = name_of(streets, e.get("street"))
            if n and e.get("kind") in ROAD_KINDS:
                x, z = mid(e)
                self.cells[(int(x // 200), int(z // 200))].append((x, z, n))

    def near(self, x, z):
        best = None
        cx, cz = int(x // 200), int(z // 200)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for ex, ez, n in self.cells.get((cx + dx, cz + dz), []):
                    d = math.hypot(ex - x, ez - z)
                    if best is None or d < best[0]:
                        best = (d, n)
        return best[1] if best else None


# --- commands

def cmd_summary(src):
    snap = load(snapshot_path(src))
    c = obj(snap.get("city"))
    b = obj(snap.get("budget"))
    prefabs, streets = arr(snap.get("prefabs")), arr(snap.get("streets"))
    why = {"done": "Done for today", "save": f"the save {snap.get('save')!r}", "button": "Take a snapshot",
           "start": "loading the city"}.get(snap.get("why"), snap.get("why"))
    print(f"# {c.get('name') or '?'}: city snapshot\n")
    print(f"Taken {local_time(snap.get('taken'))} on {why}; in game {obj(c.get('date')).get('text') or '?'}; "
          f"mod {snap.get('mod', '?')}.\n")
    print("| | |\n|---|---|")
    print(f"| People | {c.get('population', 0):,} (happiness {c.get('happiness', '?')}) |")
    print(f"| Money | {money(c.get('money'))}{' (unlimited)' if c.get('unlimitedMoney') else ''} |")
    print(f"| Budget a month | income {money(b.get('totalIncome'))}, expenses {money(b.get('totalExpenses'))}, "
          f"balance {signed(b.get('balance'), '$')} |")
    print(f"| Experience, milestone | {c.get('xp', 0):,}, {c.get('milestone', '?')} |")
    print(f"| Map tiles owned | {c.get('tiles', '?')} |")
    lines = lambda d: ", ".join(f"{k} {money(v)}" for k, v in sorted(obj(d).items(), key=lambda kv: -abs(kv[1] or 0)) if v)
    if lines(b.get("income")):
        print(f"\nIncome: {lines(b.get('income'))}.")
    if lines(b.get("expenses")):
        print(f"Expenses: {lines(b.get('expenses'))}.")

    length = Counter()
    under = over = 0.0
    for e in arr(snap.get("edges")):
        if e.get("owned"):
            continue
        length[e.get("kind")] += e.get("length", 0)
        if e.get("tunnel"):
            under += e.get("length", 0)
        elif e.get("bridge"):
            over += e.get("length", 0)
    if length:
        print("\nNetworks: " + ", ".join(f"{k} {km(v)}" for k, v in length.most_common()) +
              f"; tunnels {km(under)}, bridges {km(over)}; {len(streets):,} street names.")
    kinds = Counter(x.get("kind") for x in arr(snap.get("buildings")))
    if kinds:
        print("Buildings: " + ", ".join(f"{k} {v:,}" for k, v in kinds.most_common()) + ".")
    districts = [d.get("name") for d in arr(snap.get("districts")) if isinstance(d, dict)]
    if districts:
        print("Districts: " + ", ".join(districts) + ".")
    if arr(snap.get("truncated")):
        print("Cut from this snapshot (too large): " + ", ".join(snap["truncated"]) + ".")

    d = obj(snap.get("demand"))
    if d:
        print("\nDemand (0 to 100): " + ", ".join(f"{k} {d[k]}" for k in ("residentialLow", "residentialMedium", "residentialHigh",
              "commercial", "industrial", "office") if k in d) + ".")
    pe, jo = obj(snap.get("people")), obj(snap.get("jobs"))
    if pe:
        print(f"People: {pe.get('households', 0):,} households, {pe.get('workers', 0):,} working of {pe.get('workable', 0):,} who could, "
              f"unemployment {pe.get('unemploymentPercent', '?')}%, homeless {pe.get('homeless', 0):,}.")
    if jo:
        print(f"Jobs: {jo.get('total', 0):,} workplaces, {jo.get('free', 0):,} free.")
    ha = obj(snap.get("happiness"))
    if arr(ha.get("factors")):
        print(f"Happiness {ha.get('average', '?')}: " + ", ".join(f"{f.get('factor')} {f.get('points'):+d}" for f in ha["factors"][:6]) + ".")
    ut = obj(snap.get("utilities"))
    el, wa = obj(ut.get("electricity")), obj(ut.get("water"))
    if el:
        print(f"Electricity: makes {power(el.get('production'))}, uses {power(el.get('consumption'))}, imports {power(el.get('import'))}.")
    if wa and (wa.get("freshCapacity") or wa.get("freshConsumption")):
        print(f"Water: pumps {wa.get('freshCapacity', 0):,} m³, uses {wa.get('freshConsumption', 0):,} m³; sewage {wa.get('sewageCapacity', 0):,} m³ "
              f"for {wa.get('sewageConsumption', 0):,} m³.")
    pr = obj(snap.get("problems"))
    if arr(pr.get("kinds")):
        print("Problems: " + ", ".join(f"{k.get('title')} {k.get('count', 0)}" for k in sorted(pr["kinds"], key=lambda k: -k.get("count", 0))[:8]) + ".")
    tr = arr(snap.get("transit"))
    if tr:
        print("Transit: " + "; ".join(f"{l.get('name')} ({l.get('kind')}, {len(arr(l.get('stops')))} stops, {l.get('vehicles')} vehicles, "
                                       f"{l.get('usagePercent')}% full)" for l in tr[:12]) + ".")
    hi = obj(snap.get("history"))
    if len(arr(hi.get("population"))) > 1:
        print(f"Over {len(hi['population'])} months: people {int(hi['population'][0]):,} → {int(hi['population'][-1]):,}, "
              f"money {money(hi['money'][0] if arr(hi.get('money')) else 0)} → {money(hi['money'][-1] if arr(hi.get('money')) else 0)}.")

    ch = obj(obj(snap.get("session")).get("changes"))
    if ch:
        print(f"\n## This session (since the city loaded, {local_time(ch.get('since'))}, in game {ch.get('sinceDate') or '?'})\n")
        for line in session_lines(ch):
            print(f"- {line}")
    return 0


def session_lines(ch):
    out = []
    for what, a, r in (("road", ch.get("roadsAddedKm"), ch.get("roadsRemovedKm")), ("track", ch.get("railAddedKm"), ch.get("railRemovedKm"))):
        if a or r:
            out.append(f"{a or 0:.1f} km of new {what}, {r or 0:.1f} km removed")
    if any(ch.get(k) for k in ("grew", "placed", "removed")):
        out.append(f"{ch.get('grew', 0):,} buildings grew, {ch.get('placed', 0):,} placed by the Mayor, {ch.get('removed', 0):,} removed")
    out.append(f"{signed(ch.get('population'))} people, money {signed(ch.get('money'), '$')}, {signed(ch.get('tiles'))} map tiles")
    return out


def power(v):
    """The game's electricity unit (tenths of a kilowatt) as it shows it."""
    v = (v or 0) / 10
    return f"{v / 1000:.1f} MW" if abs(v) >= 1000 else f"{v:.0f} kW"


def cmd_problems(src):
    snap = load(snapshot_path(src))
    pr = obj(snap.get("problems"))
    kinds = arr(pr.get("kinds"))
    if not kinds:
        print("No problem icons in this snapshot." if "problems" in snap else "This snapshot has no problems part (City Manager 0.7 or later).")
        return 0
    near = Streets(snap)
    prefabs, titles, streets = arr(snap.get("prefabs")), arr(snap.get("prefabTitles")), arr(snap.get("streets"))
    by_kind = defaultdict(list)
    for it in arr(pr.get("items")):
        by_kind[it.get("kind")].append(it)
    print(f"# Problems in {obj(snap.get('city')).get('name') or '?'} ({local_time(snap.get('taken'))})\n")
    for i, k in sorted(enumerate(kinds), key=lambda ik: -ik[1].get("count", 0)):
        items = by_kind.get(i, [])
        places = Counter()
        for it in items:
            if it.get("on") == "road" and name_of(streets, it.get("street")):
                places[name_of(streets, it.get("street"))] += 1
            else:
                places[near.near(it.get("x", 0), it.get("z", 0)) or "(no street near)"] += 1
        what = Counter((it.get("on"), (name_of(titles, it.get("prefab")) or name_of(prefabs, it.get("prefab")))) for it in items if it.get("on") == "building")
        print(f"## {k.get('title')} ×{k.get('count', 0)}\n")
        print("Near: " + ", ".join(f"{n} {c}" if c > 1 else n for n, c in places.most_common(10)) + ".")
        if what:
            print("On: " + ", ".join(f"{b} {c}" if c > 1 else b for (_, b), c in what.most_common(6)) + ".")
        print()
    return 0


def cmd_services(src):
    snap = load(snapshot_path(src))
    print(f"# Services in {obj(snap.get('city')).get('name') or '?'} ({local_time(snap.get('taken'))})\n")
    sv = arr(snap.get("services"))
    if sv:
        print("| Service | Budget | Efficiency | Upkeep a month |\n|---|---|---|---|")
        for x in sv:
            print(f"| {x.get('title')} | {x.get('budget')}% | {x.get('efficiency')}% | {money(x.get('upkeep'))} |")
        print()
    near = Streets(snap)
    rows = []
    for b in arr(snap.get("buildings")):
        use = obj(b.get("use"))
        if b.get("kind") != "service" and not use:
            continue
        full = use.get("now", 0) / use["max"] if use.get("max") else None
        rows.append((full if full is not None else -1, b, use))
    if rows:
        print("| Building | Near | How full | Efficiency |\n|---|---|---|---|")
        for full, b, use in sorted(rows, key=lambda r: -r[0]):
            fill = f"{use.get('now', 0):,} of {use.get('max', 0):,} {use.get('what')} ({full:.0%})" if full >= 0 else "–"
            print(f"| {b.get('name') or '?'} | {near.near(b.get('x', 0), b.get('z', 0)) or '–'} | {fill} | "
                  f"{str(b['efficiency']) + '%' if 'efficiency' in b else '–'} |")
    return 0


def cmd_catalogue(src):
    snap = load(snapshot_path(src))
    cat = obj(snap.get("catalogue"))
    items = arr(cat.get("items"))
    if not items:
        print("This snapshot has no catalogue part (City Manager 0.7 or later).")
        return 1
    level = cat.get("milestone", 0)
    print(f"# What {obj(snap.get('city')).get('name') or 'the Mayor'} can build (milestone {level}), "
          f"from the snapshot of {local_time(snap.get('taken'))}\n")
    print("Names are as the game's menus show them; use them in build cards.\n")
    menus = defaultdict(list)
    for it in items:
        if it.get("unlocked"):
            menus[it.get("menu") or it.get("kind")].append(it)
    for menu, its in sorted(menus.items(), key=lambda kv: str(kv[0])):
        print(f"## {menu}\n")
        for it in sorted(its, key=lambda i: str(i.get("title"))):
            ln = arr(it.get("lanes"))
            bits = []
            if len(ln) == 2:
                bits.append(f"lanes {ln[0]}+{ln[1]}" if ln[1] else f"{ln[0]} lane{'s' if ln[0] != 1 else ''} one-way")
            if it.get("costPerKm"):
                bits.append(f"{money(it['costPerKm'])}/km, upkeep {money(it.get('upkeepPerKm'))}/km a month")
            elif it.get("upkeep"):
                bits.append(f"upkeep {money(it['upkeep'])} a month")
            print(f"- {it.get('title')}" + (f" ({'; '.join(bits)})" if bits else ""))
        print()
    nxt = [it for it in items if not it.get("unlocked") and it.get("milestone") == level + 1]
    if nxt:
        print(f"## Milestone {level + 1} unlocks\n")
        for it in sorted(nxt, key=lambda i: str(i.get("title"))):
            print(f"- {it.get('title')} ({it.get('menu') or it.get('kind')})")
    return 0


def cmd_changes(src, before=None):
    now_path = snapshot_path(src)
    then_path = Path(before).expanduser() if before else snapshot_path(src, start=True)
    now, then = load(now_path), load(then_path)
    print(f"# What changed in {obj(now.get('city')).get('name') or '?'}\n")
    print(f"From {then_path.name} ({local_time(then.get('taken'))}, in game {obj(obj(then.get('city')).get('date')).get('text') or '?'}) "
          f"to {now_path.name} ({local_time(now.get('taken'))}, in game {obj(obj(now.get('city')).get('date')).get('text') or '?'}).\n")
    for snap, label in ((then, "before"), (now, "now")):
        if any(t.startswith("edges") for t in arr(snap.get("truncated"))):
            print(f"The {label} snapshot has no roads (cut for size), so roads can't be compared.")
            return 1

    def index(snap):
        nodes, prefabs, streets = node_places(snap), arr(snap.get("prefabs")), arr(snap.get("streets"))
        out = {}
        for e in arr(snap.get("edges")):
            if e.get("owned") or e.get("kind") not in ROAD_KINDS + RAIL_KINDS:
                continue
            out[edge_key(e, nodes)] = dict(prefab=name_of(prefabs, e.get("prefab")) or "?", street=name_of(streets, e.get("street")),
                                          length=e.get("length", 0), lanes=e.get("lanes"), kind=e.get("kind"),
                                          tunnel=e.get("tunnel", False), bridge=e.get("bridge", False))
        return out

    a, b = index(then), index(now)
    added = [b[k] for k in b.keys() - a.keys()]
    removed = [a[k] for k in a.keys() - b.keys()]
    changed = [(a[k], b[k]) for k in a.keys() & b.keys() if (a[k]["prefab"], a[k]["street"]) != (b[k]["prefab"], b[k]["street"])]

    def by_street(items, title):
        if not items:
            return
        groups = defaultdict(lambda: [0.0, Counter()])
        for x in items:
            g = groups[x["street"] or f"(unnamed {x['kind']})"]
            g[0] += x["length"]
            g[1][x["prefab"] + (" tunnel" if x["tunnel"] else " bridge" if x["bridge"] else "")] += 1
        print(f"## {title}: {km(sum(x['length'] for x in items))}\n")
        for name, (length, pf) in sorted(groups.items(), key=lambda kv: -kv[1][0]):
            print(f"- {name}: {km(length)} ({', '.join(f'{p} ×{n}' if n > 1 else p for p, n in pf.most_common())})")
        print()

    by_street(added, "Built")
    by_street(removed, "Removed")
    if changed:
        print(f"## Changed in place: {len(changed)} pieces\n")
        moves = Counter()
        for x, y in changed:
            if x["street"] != y["street"]:
                moves[f"renamed {x['street'] or '(unnamed)'} → {y['street'] or '(unnamed)'}"] += 1
            if x["prefab"] != y["prefab"]:
                moves[f"{y['street'] or '(unnamed)'}: {x['prefab']} → {y['prefab']}"] += 1
        for line, n in moves.most_common():
            print(f"- {line}" + (f" ({n} pieces)" if n > 1 else ""))
        print()

    near = Streets(now)

    def bindex(snap):
        prefabs = arr(snap.get("prefabs"))
        out = {}
        for x in arr(snap.get("buildings")):
            out[(x.get("prefab") is not None and name_of(prefabs, x.get("prefab")), round(x.get("x", 0)), round(x.get("z", 0)))] = x
        return out

    if not any(t.startswith("buildings") for s in (then, now) for t in arr(s.get("truncated"))):
        ba, bb = bindex(then), bindex(now)
        new = [bb[k] for k in bb.keys() - ba.keys()]
        gone = [ba[k] for k in ba.keys() - bb.keys()]
        zoned = lambda x: x.get("kind") in ("residential", "commercial", "industrial", "office")
        grew = Counter(x.get("kind") for x in new if zoned(x))
        print(f"## Buildings: {len(new):,} new, {len(gone):,} gone\n")
        if grew:
            print("- Grew from zoning: " + ", ".join(f"{k} {v:,}" for k, v in grew.most_common()))
        for x in [x for x in new if not zoned(x)][:60]:
            street = near.near(x.get("x", 0), x.get("z", 0))
            print(f"- Placed: {x.get('name') or name_of(arr(now.get('prefabs')), x.get('prefab'))} ({x.get('kind')})" + (f", near {street}" if street else ""))
        lost = Counter(x.get("kind") for x in gone)
        if lost:
            print("- Gone: " + ", ".join(f"{k} {v:,}" for k, v in lost.most_common()))
        print()
    c0, c1 = obj(then.get("city")), obj(now.get("city"))
    print(f"People {signed((c1.get('population') or 0) - (c0.get('population') or 0))}, "
          f"money {signed((c1.get('money') or 0) - (c0.get('money') or 0), '$')}, "
          f"map tiles {signed((c1.get('tiles') or 0) - (c0.get('tiles') or 0))}.")
    return 0


def street_groups(snap):
    prefabs, streets = arr(snap.get("prefabs")), arr(snap.get("streets"))
    groups = defaultdict(list)
    for e in arr(snap.get("edges")):
        n = name_of(streets, e.get("street"))
        if n and e.get("kind") in ROAD_KINDS and not e.get("owned"):
            groups[n].append(dict(e, prefabName=name_of(prefabs, e.get("prefab")) or "?"))
    return groups


def lanes_text(e):
    ln = arr(e.get("lanes"))
    if len(ln) != 2:
        return "?"
    if not sum(ln):
        return "no car lanes"
    text = f"{ln[0]}+{ln[1]}" if ln[1] else f"{ln[0]} one-way"
    bus = arr(e.get("bus"))
    return text + (f" (bus {bus[0]}+{bus[1]})" if len(bus) == 2 and sum(bus) else "")


def cmd_streets(src):
    snap = load(snapshot_path(src))
    groups = street_groups(snap)
    print(f"# Streets of {obj(snap.get('city')).get('name') or '?'} ({len(groups):,}), from the snapshot of {local_time(snap.get('taken'))}\n")
    print("| Street | Length | Road types | Lanes |\n|---|---|---|---|")
    for name, es in sorted(groups.items(), key=lambda kv: kv[0].casefold()):
        pf = Counter(e["prefabName"] for e in es)
        ln = Counter(lanes_text(e) for e in es)
        print(f"| {name} | {km(sum(e.get('length', 0) for e in es))} | {', '.join(p for p, _ in pf.most_common())} | {', '.join(l for l, _ in ln.most_common())} |")
    return 0


def cmd_street(src, name):
    snap = load(snapshot_path(src))
    groups = street_groups(snap)
    matches = [n for n in groups if n.casefold() == name.casefold()] or [n for n in groups if name.casefold() in n.casefold()]
    if not matches:
        print(f"No street named {name!r} in the snapshot of {local_time(snap.get('taken'))}. Street names change when roads "
              "are rebuilt; `city.py streets` lists them all.")
        return 1
    for n in matches[:5]:
        es = groups[n]
        flows = [e["flow"] for e in es if isinstance(e.get("flow"), (int, float))]
        xs = [mid(e) for e in es]
        cx, cz = sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs)
        print(f"# {n}: {km(sum(e.get('length', 0) for e in es))} in {len(es)} pieces (middle near x {cx:.0f}, z {cz:.0f})\n")
        print("| Road type | Lanes | Pieces | Length | Height | Traffic flow |\n|---|---|---|---|---|---|")
        rows = defaultdict(list)
        for e in es:
            h = "tunnel" if e.get("tunnel") else "bridge" if e.get("bridge") else "ground"
            el = arr(e.get("elevation"))
            if el and h != "ground":
                h += f" ({min(el):.0f} to {max(el):.0f} m)"
            rows[(e["prefabName"], lanes_text(e), h)].append(e)
        for (pf, ln, h), group in sorted(rows.items(), key=lambda kv: -sum(e.get("length", 0) for e in kv[1])):
            fl = [e["flow"] for e in group if isinstance(e.get("flow"), (int, float))]
            print(f"| {pf} | {ln} | {len(group)} | {km(sum(e.get('length', 0) for e in group))} | {h} | "
                  f"{(f'{min(fl)}–{max(fl)}%' if fl and min(fl) != max(fl) else f'{fl[0]}%') if fl else '–'} |")
        if flows:
            print(f"\nSlowest piece: {min(flows)}% of free flow.")
        print()
    return 0


def main(argv):
    args = argv[1:]
    if len(args) >= 2 and args[0] == "summary":
        return cmd_summary(args[1])
    if len(args) >= 2 and args[0] == "changes":
        before = args[args.index("--before") + 1] if "--before" in args and args.index("--before") + 1 < len(args) else None
        return cmd_changes(args[1], before)
    if len(args) == 2 and args[0] == "streets":
        return cmd_streets(args[1])
    if len(args) >= 3 and args[0] == "street":
        return cmd_street(args[1], " ".join(args[2:]))
    if len(args) == 2 and args[0] in ("problems", "services", "catalogue"):
        return {"problems": cmd_problems, "services": cmd_services, "catalogue": cmd_catalogue}[args[0]](args[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
