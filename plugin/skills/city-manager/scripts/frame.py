"""Streets as frames for plan files: a place said as "so many metres along a street, so many to its left", the way a
planner thinks, instead of x and z. A library for plan.py (its frame, road, zone and junction commands); it only reads
the snapshot.

A street name can cover several roads (the game names a whole chain, and a T-junction's stem often keeps the name), so
a street is split into parts: each part runs straight on through its junctions (turning less than TURN degrees), and
the longest is part 1. A part runs from its west end east, or, when it runs more north-south than east-west, from its
south end north; "left" is to the left looking that way.

Places (`place()`):
  X,Z                          a point on the map
  <street>@<s>[+|-<t>]         s metres along the street's part 1 (negative: from its far end; or start, mid, end),
                               t metres to its left (+) or right (-): "Ivy Street@398+116"
  <street>/<n>@<s>[+|-<t>]     the same on part n: "Ivy Street/2@40-30"
  <street A> x <street B>      where the two meet or come closest: "Ivy Street x Amberwood Street"
"""
import difflib
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import city  # noqa: E402
import survey as sv  # noqa: E402

TURN = 40.0     # degrees: a street goes straight on through a junction when it turns less than this
STEP = 20.0     # metres between the points of a line along a street
SPEC = re.compile(r"^\s*(?P<street>.+?)(?:\s*/\s*(?P<part>\d+))?\s*@\s*(?P<s>start|mid|end|-?\d+(?:\.\d+)?)"
                  r"\s*(?P<t>[+-]\s*\d+(?:\.\d+)?)?\s*$", re.I)
XZ = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
CROSS = re.compile(r"\s+x\s+", re.I)


def unit(dx, dz):
    L = math.hypot(dx, dz)
    return (dx / L, dz / L) if L > 1e-9 else (0.0, 0.0)


class Part:
    """One straight-on run of a street: a line from its start, with the junctions along it."""

    def __init__(self, name, pts, edges, joints):
        """pts: the joined line; joints: [(index into pts, node id)] where its pieces meet, its two ends included."""
        out, where = [], {}
        for i, p in enumerate(pts):
            if not out or math.dist(out[-1], p) > 0.05:
                out.append((float(p[0]), float(p[1])))
            where[i] = len(out) - 1
        self.name, self.pts, self.edges, self.index = name, out, edges, 0
        self.cum = [0.0]
        for a, b in zip(out, out[1:]):
            self.cum.append(self.cum[-1] + math.dist(a, b))
        self.length = self.cum[-1]
        self.joints = [(self.cum[where[i]], n) for i, n in joints]   # [(s, node id)]

    def flip(self):
        self.pts.reverse()
        self.joints = sorted((self.length - s, n) for s, n in self.joints)
        self.edges = list(reversed(self.edges))
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.dist(a, b))

    def s_of(self, word):
        if isinstance(word, str):
            w = word.casefold()
            if w == "start":
                return 0.0
            if w == "end":
                return self.length
            if w == "mid":
                return self.length / 2
            word = float(word)
        return self.length + word if word < 0 else word

    def at(self, s):
        """(x, z, ux, uz) at s metres along (beyond the ends, the line goes straight on)."""
        if len(self.pts) < 2:
            return self.pts[0][0], self.pts[0][1], 0.0, 0.0
        i = 0
        while i < len(self.cum) - 2 and self.cum[i + 1] < s:
            i += 1
        a, b = self.pts[i], self.pts[i + 1]
        seg = self.cum[i + 1] - self.cum[i] or 1.0
        f = (s - self.cum[i]) / seg
        ux, uz = unit(b[0] - a[0], b[1] - a[1])
        return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, ux, uz

    def point(self, s, t=0.0):
        x, z, ux, uz = self.at(s)
        return (x - t * uz, z + t * ux)   # left of the way it runs: (-uz, ux)

    def line(self, s0, s1, t=0.0, step=STEP):
        """Points from s0 to s1 (either way) at t metres to the left, every `step` metres and at its bends."""
        lo, hi = sorted((s0, s1))
        marks = {lo, hi} | {c for c in self.bends() if lo < c < hi}
        k = max(1, int(math.ceil((hi - lo) / step)))
        marks |= {lo + (hi - lo) * i / k for i in range(k + 1)}
        ss = sorted(marks, reverse=s0 > s1)
        out = []
        for s in ss:
            p = self.point(s, t)
            if not out or math.dist(out[-1], p) > 0.5:
                out.append(p)
        return out

    def bends(self):
        """Where the line turns by more than a degree and a half (straight runs need no points between)."""
        if not hasattr(self, "_bends"):
            out = []
            for i in range(1, len(self.pts) - 1):
                a, b, c = self.pts[i - 1], self.pts[i], self.pts[i + 1]
                u, v = unit(b[0] - a[0], b[1] - a[1]), unit(c[0] - b[0], c[1] - b[1])
                if math.degrees(math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))) > 1.5:
                    out.append(self.cum[i])
            self._bends = out
        return self._bends

    def project(self, x, z):
        """(s, t, distance) of the nearest point of the part to (x, z): t positive to the left."""
        best = None
        for i, (a, b) in enumerate(zip(self.pts, self.pts[1:])):
            dx, dz = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dz * dz or 1e-9
            f = max(0.0, min(1.0, ((x - a[0]) * dx + (z - a[1]) * dz) / L2))
            px, pz = a[0] + dx * f, a[1] + dz * f
            d = math.hypot(x - px, z - pz)
            if best is None or d < best[2]:
                ux, uz = unit(dx, dz)
                t = (x - px) * -uz + (z - pz) * ux
                best = (self.cum[i] + f * math.sqrt(L2), t, d)
        return best

    def start_word(self):
        return sv.direction(self.pts[0][0] - self.pts[-1][0], self.pts[0][1] - self.pts[-1][1])

    def heading_word(self):
        return sv.direction(self.pts[-1][0] - self.pts[0][0], self.pts[-1][1] - self.pts[0][1])

    def left_word(self, s=0.0):
        _, _, ux, uz = self.at(min(max(s, 0.0), self.length))
        return sv.direction(-uz, ux)

    def width(self):
        """The road's width for spacing, from its commonest piece."""
        lanes = Counter(tuple(city.arr(e.get("lanes"))) for e in self.edges if len(city.arr(e.get("lanes"))) == 2).most_common(1)
        title = Counter(e.get("title") for e in self.edges).most_common(1)
        import plan  # noqa: PLC0415  (plan imports this module)
        return plan.width_of(title[0][0] if title else "", lanes[0][0] if lanes else None)


class Streets:
    """Every street of a snapshot as parts, and places said in their words."""

    def __init__(self, snap):
        self.net = sv.Network(snap)
        self.roads = [e for e in self.net.by_kind(*city.ROAD_KINDS) if len(e.get("line") or []) >= 2]
        self.by_name = defaultdict(list)
        for e in self.roads:
            if e.get("streetName"):
                self.by_name[e["streetName"]].append(e)
        self.cache = {}

    def find(self, name):
        """The street's name as the snapshot spells it."""
        if name in self.by_name:
            return name
        low = {n.casefold(): n for n in self.by_name}
        if name.casefold() in low:
            return low[name.casefold()]
        some = [n for n in self.by_name if name.casefold() in n.casefold()]
        if len(some) == 1:
            return some[0]
        near = some or difflib.get_close_matches(name, list(self.by_name), n=5, cutoff=0.6)
        raise SystemExit(f"No street named {name!r} in the snapshot" + (f"; did you mean {', '.join(map(repr, near))}?" if near else
                         " (`city.py streets` lists them; names come from the newest snapshot)."))

    def parts(self, name):
        name = self.find(name)
        if name not in self.cache:
            self.cache[name] = make_parts(name, self.by_name[name])
        return self.cache[name]

    def part(self, name, n=None):
        ps = self.parts(name)
        n = int(n or 1)
        if not 1 <= n <= len(ps):
            raise SystemExit(f"{self.find(name)} has {len(ps)} part{'s' if len(ps) != 1 else ''} (`plan.py frame` lists them), not {n}.")
        return ps[n - 1]

    def place(self, spec):
        """A place from its words (see the module's docstring): (x, z)."""
        spec = str(spec)
        m = XZ.match(spec)
        if m:
            return float(m.group(1)), float(m.group(2))
        if CROSS.search(spec) and "@" not in spec:
            a, b = CROSS.split(spec, maxsplit=1)
            return self.crossing(a.strip(), b.strip())
        m = SPEC.match(spec)
        if not m:
            raise SystemExit(f"Can't read the place {spec!r}: use X,Z, \"<street>@<metres along>[+|-<metres left>]\" "
                             "or \"<street> x <street>\".")
        p = self.part(m.group("street"), m.group("part"))
        t = float(m.group("t").replace(" ", "")) if m.group("t") else 0.0
        return p.point(p.s_of(m.group("s")), t)

    def crossing(self, a, b):
        """Where two streets meet (a junction they share), cross, or come closest."""
        ea, eb = self.by_name[self.find(a)], self.by_name[self.find(b)]
        na = {e.get(k) for e in ea for k in ("a", "b")}
        shared = [n for e in eb for n in (e.get("a"), e.get("b")) if n in na and n in self.net.nodes]
        if shared:
            n = self.net.nodes[shared[0]]
            return float(n.get("x", 0)), float(n.get("z", 0))
        best = None
        for e in ea:
            for f in eb:
                for p, q in zip(e["line"], e["line"][1:]):
                    for r, s in zip(f["line"], f["line"][1:]):
                        hit = seg_cross(p, q, r, s)
                        if hit:
                            return hit
                for p in e["line"]:
                    for r in f["line"]:
                        d = math.dist(p, r)
                        if best is None or d < best[0]:
                            best = (d, ((p[0] + r[0]) / 2, (p[1] + r[1]) / 2))
        return best[1]


def seg_cross(p, q, r, s):
    d1 = (q[0] - p[0], q[1] - p[1])
    d2 = (s[0] - r[0], s[1] - r[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    t = ((r[0] - p[0]) * d2[1] - (r[1] - p[1]) * d2[0]) / den
    u = ((r[0] - p[0]) * d1[1] - (r[1] - p[1]) * d1[0]) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        return p[0] + d1[0] * t, p[1] + d1[1] * t
    return None


def make_parts(name, edges):
    """A street's edges as parts: at each junction, the two pieces that run straightest on are joined (turning less
    than TURN degrees); longest part first, each running west to east (or south to north)."""
    inc = defaultdict(list)
    for i, e in enumerate(edges):
        inc[e.get("a")].append((i, 0))
        inc[e.get("b")].append((i, 1))

    def out_dir(i, end):
        L = edges[i]["line"]
        p, q = (L[0], L[1]) if end == 0 else (L[-1], L[-2])
        return unit(q[0] - p[0], q[1] - p[1])

    partner = {}
    for node, ends in inc.items():
        pairs = []
        for x in range(len(ends)):
            for y in range(x + 1, len(ends)):
                if ends[x][0] == ends[y][0]:
                    continue
                a, b = out_dir(*ends[x]), out_dir(*ends[y])
                dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
                pairs.append((180.0 - math.degrees(math.acos(dot)), ends[x], ends[y]))
        for turn, a, b in sorted(pairs):
            if turn <= TURN and a not in partner and b not in partner:
                partner[a], partner[b] = b, a
    seen, parts = set(), []

    def walk(i, enter):
        pts, es, joints = [], [], []
        while i not in seen:
            seen.add(i)
            e = edges[i]
            line = e["line"] if enter == 0 else list(reversed(e["line"]))
            first, last = (e.get("a"), e.get("b")) if enter == 0 else (e.get("b"), e.get("a"))
            if not joints:
                joints.append((0, first))
            pts += line if not pts else line[1:]
            joints.append((len(pts) - 1, last))
            es.append(e)
            nxt = partner.get((i, 1 - enter))
            if nxt is None:
                break
            i, enter = nxt
        return Part(name, pts, es, joints)

    for i in range(len(edges)):
        for end in (0, 1):
            if i not in seen and (i, end) not in partner:
                parts.append(walk(i, end))
    for i in range(len(edges)):
        if i not in seen:
            parts.append(walk(i, 0))   # a loop
    for p in parts:
        dx, dz = p.pts[-1][0] - p.pts[0][0], p.pts[-1][1] - p.pts[0][1]
        if (abs(dx) >= abs(dz) and dx < 0) or (abs(dz) > abs(dx) and dz < 0):
            p.flip()
    parts.sort(key=lambda p: -p.length)
    for k, p in enumerate(parts, 1):
        p.index = k
    return parts

