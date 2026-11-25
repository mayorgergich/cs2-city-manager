# Interchanges, underpasses and crossings

Where a street meets a highway or a railway, it goes over or under it, with ramps if it needs to join it. Never at
grade: at a flat junction the game puts traffic lights on the highway, and a road can't cross a railway at grade at all.
These are designs for the Mayor to build; your job is to pick one, draw it in the plan and write its build card.

Everything here is for **right-hand traffic**. For left-hand traffic (`traffic = "left"` in the charter), mirror every
ramp: off-ramps leave on the left of each direction, and on-ramps join on the left.

## Choosing one

| Where | First choice | Plan junction type |
|---|---|---|
| A street crosses a highway, no access needed | **Underpass**: the street in a short tunnel under the highway | `Underpass` |
| An arterial meets a highway, with access | a **tunnel diamond** (built by hand, below) or a prebuilt one: Single-point Interchange, Dumbbell Interchange, Partial Cloverleaf, Roundabout Interchange | `Interchange` |
| A highway ends and becomes the city's main street | a T: Trumpet Intersection, Trumpet Roundabout or Teardrop Roundabout, or a hand-built underground stem (below) | `Interchange` |
| Two highways meet | Cloverleaf, Four-level Stack Interchange, Directional T Intersection | `Interchange` |
| A street crosses a railway | a tunnel under it (or a bridge over it where the ground falls away) | `Underpass` / `Overpass` |
| A street over water or a valley | a bridge (a landmark bridge where it's seen from far) | road with `"bridge": true` |

The prebuilt ones are in the game's Intersections menu; `city.py catalogue` lists them with their monthly upkeep and
whether they're unlocked. Their size isn't in the snapshot: say "check it fits in game" on the card, and leave room
(they're often several hundred metres across). Hand-built ones are cheaper, fit tight spots and teach the Mayor how
the game's elevations work.

**Tunnels over plain bridges across highways:** a flat road bridge over a highway looks bad in this game. Plan a tunnel
for every street that crosses a highway, unless the ground already rises (a cutting) or the bridge is meant as a
landmark.

## How the game decides it's a tunnel (game 1.6, read from its code)

- A road is a **tunnel** only if every point (start, middle, end) is at least **8 m** below the ground, and at least one
  end is **12 m** or more below. **13 m down** is safe.
- 10 m everywhere gives an **open cut** with retaining walls, not a tunnel.
- The two ends of a tunnel can sit at different depths (12 m at one end, 9 m at the other) to ease a steep side.
- A tunnel only collides with other underground things (pipes, subway, other tunnels). A road or highway on the ground
  above gives it no clearance problem. An open cut does collide with roads on the ground, so it must stop short of the
  highway's edge.
- The game refuses ramps steeper than **20%**. The terrain in the snapshot is a 56 m grid, so a ramp's grade can't be
  predicted closely: build the steepest piece first and read its slope in game.

## Template A: tunnel diamond (an arterial crossing a highway, with access)

Through traffic on the highway never stops. Right-hand traffic.

1. **The underpass:** three pieces of the street's own road, measured across the highway from its centre line:
   - the down-ramp, from the frontage junction on the near side to about 15 m from the centre (13 m for a Two-Lane
     Road), ending about 12 m down;
   - the tunnel, to about 15 m past the centre on the far side, about 12–13 m down (9 m if the far side is too steep);
   - the up-ramp, to the frontage junction on the far side.
2. **Four slip roads** (One-Lane One-Way Highway) between the highway and the frontage streets:
   - off-ramps leave the highway **before** the crossing and on-ramps join **after** it, each on its own direction's
     traffic side;
   - they leave or join the highway at a shallow angle (8–9°) and meet the frontage street at 45–75°;
   - merge and split points on the highway at least 50 m apart; each slip road at least 9 m clear of highway pieces
     it doesn't join;
   - end a slip road on a plain two-way joint of the frontage street, not on an existing four-way junction.
3. **Frontage streets** at least 90 m from the highway's centre line (`road-hierarchy.md` rule 3), so the ramps stay
   under 20%.

On the build card, number the pieces in build order: `1 Down-ramp`, `2 Tunnel`, `3 Up-ramp`, `4–7 Slip roads`
(north-east, north-west, …), each with its road piece and depth. In the plan, draw the underpass road with
`"tunnel": true` and an `Interchange` junction where it crosses the highway line.

## Template B: underground stem (a T to a highway, a freight road)

For a road that ends at the highway (a port or freight road, or the city's entry):
1. Run the stem (Four-Lane Road) about 13 m down under the highway, square to it.
2. Put an underground junction about 32 m either side of the highway's centre line.
3. Four slip roads (One-Lane One-Way Highway) each leave the highway on a curve, then go down in an open cut to the
   underground junctions.
4. The stem carries on from one junction.
5. Take the traffic lights off the underground junctions (the game adds them by itself): stop signs or nothing.

## A plain underpass (a street under a highway or railway, no access)

The street goes down to about 13 m under the highway or the tracks and comes back up: the first half of Template A
without the slip roads. Under a railway corridor the tunnel can run several hundred metres. Draw it as a road piece
with `"tunnel": true` (split the road where the tunnel starts and ends) and an `Underpass` junction marker.

## Over a railway

Where the ground falls away, a bridge is fine: ramp up so the deck sits about 8 m above the track, span it, and come
back down. Two worked examples: a street that crossed a double track about 7 m above it, and a deck 8.5 m up over about
125 m with ramps of about 105 m on each side. A road can't end on a track, and a road on the ground next to a track
sits too close to it: keep junctions out of the strip beside the rail.

## Roundabouts and traffic control

- Roundabouts aren't in the snapshot's catalogue: say the size in words ("a small roundabout", "the large one") on the
  card and mark it a suggestion.
- A roundabout works best with three or four roads, roughly at right angles, and similar traffic on each.
- Collectors meeting locals: stop signs. Arterials crossing arterials: traffic lights or a roundabout, 200 m or more
  from the next set of lights.
- The game adds traffic lights at big junctions by itself; say on the card when to take them off (underground junctions
  of Template B, a ramp's end on a quiet street).

## Deep tunnels

Map makers sometimes bury power cables and pipes along the highways, down to about 30 m. A tunnel that meets one fails
to build: if a deep tunnel is refused in game, go a few metres shallower or deeper there.
