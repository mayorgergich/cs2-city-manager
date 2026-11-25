# Road hierarchy: which road goes where

Choosing road types is where most players struggle: which road should be four lanes, where a four-lane road may become
a two-lane one, how to keep traffic flowing and the city still looking good. Explain every choice both ways: what
traffic it carries, and how it looks. Use pictures of the Mayor's own city, with the lanes coloured and the spots
numbered.

**The idea:** traffic steps up and down the hierarchy one level at a time. Homes sit on quiet local streets, local
streets feed collectors, collectors feed arterials, and arterials feed the highway's ramps. Through traffic stays off
homes, local trips stay off the highway, and junctions stay far enough apart that the game's traffic doesn't stall.

**It's a guide, not a rule.** The Mayor may break it for a good-looking street, a feature tunnel or a tram main street.
Don't block that. Say where it strays and what it will cost in traffic, then follow their choice (§ When the Mayor
breaks the rules).

## The four levels

| Level | What it's for | Pieces (menu names; check `city.py catalogue`) | Spacing | Junctions on it |
|---|---|---|---|---|
| **Highway** | Through traffic and the connections off the map | the map's own highways; ramps: One-Lane One-Way Highway | interchanges about 1 km apart or more | **never at grade**: interchanges only (`interchanges.md`) |
| **Arterial** | Joins districts to each other and to the interchanges | Six-Lane Road, Six-Lane Divided Road; Four-Lane Road or Four-Lane Divided Road in a small town | 500–800 m apart | 200–250 m apart or more; traffic lights or a roundabout where arterials cross |
| **Collector** | Gathers a neighbourhood's traffic onto the arterials | Four-Lane Road, Two-Lane Road | 250–400 m apart | 100 m apart or more; T-junctions onto arterials; stop signs rather than lights |
| **Local** | Reaches the lots | Two-Lane Road, the parking roads, alleys, pedestrian streets | blocks of 112 m (below) | 40 m apart or more; T-junctions, loops, cul-de-sacs on hills |

Widths, for spacing: Two-Lane Road 16 m, Four-Lane Road 24 m, Six-Lane Road 32 m. Footpaths and promenades sit outside
the hierarchy and join roads anywhere.

In the plan file a road's `class` is its level (`Highway`, `Arterial`, `Collector`, `Local`), the same four the
planner draws in red, orange, yellow and white, and its `piece` is the menu name the Mayor builds it with.

## The rules

1. **One level at a time.** Locals join collectors, collectors join arterials, arterials join interchange ramps. A
   local street never meets a highway, and rarely an arterial.
2. **Highways:**
   - No street crosses or joins a highway at grade: the game puts traffic lights on the highway and through traffic
     stops. Don't leave a "temporary" flat junction either; it gets lights and has to be rebuilt later.
   - Ramps leave and join on the traffic side (right-hand traffic: on the right of each direction).
   - A map's own highway may be thin (Two-Lane Two-Way Highway is one lane each way). Leave room to widen it, and keep
     short city trips off it.
3. **Frontage streets near a future interchange** sit **at least 90 m** from the highway's centre line. At 75 m the
   ramps of an underpass came out at 19.9% against the game's 20% limit.
4. **Arterials** carry shops and offices rather than houses where possible, and no side streets between their
   junctions. Driveways and zoned houses on an arterial slow everything behind them.
5. **Lots and blocks:**
   - Zone cells are 8 m; a lot is up to 6 cells (48 m) deep.
   - Parallel streets: half the first road's width + 96 m + half the second's. Two Two-Lane Roads: 8 + 96 + 8 = 112 m,
     two full-depth lots back to back. A Four-Lane Road beside a Two-Lane Road: 12 + 96 + 8 = 116 m. Four-Lane beside
     Four-Lane: 120 m.
   - Blocks 160–240 m long.
   - **Superblocks** with 150–250 m between streets wherever big buildings, industry, utilities, services, rail or a
     port will go. A 112 m grid fits none of them.
6. **Ground** (the survey's slope classes):
   - zoned streets at 8% or less;
   - the game refuses roads steeper than 20%;
   - on hills, follow the contours; use tunnels where they free useful land.
7. **Crossing a railway or a highway:** never at grade. Prefer a **tunnel** (an underpass) over a plain road bridge: a
   flat road bridge over a highway looks bad. Bridges go over water and valleys, or stand as a landmark on purpose
   (`interchanges.md`). Keep junctions out of the narrow strip beside a railway.
8. **Room to grow.** Arterials follow the whole-map plan's corridors, so each new tile extends them instead of starting
   a new pattern. Run arterial and collector stubs to the tile edges in the directions the city grows; reserve corridors
   for future arterials, interchanges and highway widening.
9. **Build in stages.** The highway link, arterials and collectors first; local streets only in the district being
   zoned now; the rest stays as lines in the plan. Roads cost upkeep from the day they're built.

## Where four lanes become two

A road that narrows is a bottleneck if the traffic doesn't drop at the same place. So:
- change lanes **at a junction** where traffic really splits off (after the arterial junction that takes most of it),
  never in the middle of a block and never just before a busy junction;
- keep a collector the same size along its whole length if it feeds an arterial at both ends;
- when the Mayor replaces a road with a custom one (a Road Builder road, say), keep the width the same, so the lots along
  it stay exact.

## Density and style (from founding.md)

| | Arterials | Collectors | Locals | Blocks |
|---|---|---|---|---|
| `density = "low"` | Four-Lane Road | Two-Lane Road | Two-Lane Road, cul-de-sacs | 112 m, curving on hills |
| `density = "mixed"` | Six-Lane or Four-Lane Divided Road | Four-Lane Road | Two-Lane Road | 112–120 m |
| `density = "high"` | Six-Lane Divided Road, transit corridors kept free | Four-Lane Road (bus lanes where they exist) | Two-Lane Road, pedestrian streets | 120 m, short blocks downtown |

- `style = "grid"`: straight blocks aligned with the main arterial (or the highway, or the shore), stretched to fit the
  ground.
- `style = "organic"`: collectors follow contours and the shore; locals curve, with loops and cul-de-sacs; the hierarchy
  stays the same underneath.
- `style = "mixed"`: a grid downtown, organic in the neighbourhoods around it.

Transit from `transit`: keep a corridor on an arterial or collector wide enough for it, stations about 400–600 m apart
on the busy line, and land for depots. A tram main street is a fine creative break from the hierarchy if it's fed from
the side streets.

## When the Mayor breaks the rules

In every report after a build round, add a short "strayed from the hierarchy" note: where, how far, and what it means
in game, measured where you can (the snapshot's traffic `flow` per road, traffic lights on nodes, zoned lots along an
arterial). Keep measured problems apart from style choices. The usual ones:

| What happened | What it means in game |
|---|---|
| Houses zoned along an arterial | cars turning in and out slow the whole road; fine on a quiet stretch |
| Four-way junctions between local streets | more conflicts; T-junctions keep locals calm |
| Traffic lights nose to tail | queues back through the junction behind; keep 200 m between lights on arterials |
| A district reached by one road or one bridge | everything queues there; give it a second way in |
| A diagonal that cuts across the grid | odd-shaped lots and junctions with more than four arms |
| A local street joining a highway | traffic lights on the highway: needs an interchange or an underpass |
