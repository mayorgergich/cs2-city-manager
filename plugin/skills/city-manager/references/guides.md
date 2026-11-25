# Guides: the build overlay

A guide is a plan drawn over the Mayor's city by the **City Planning Draft** mod (by nooolan; written against its
version 1.2.2): roads, areas and junction markers, one plan per topic. The Mayor imports it in the planner and builds
from it; its *Construct with Draft* mode keeps a plan visible while they use the game's normal tools. You design the
guide; the Mayor builds. Nothing in a guide changes the city.

## Naming (keep it; the exporter and `journal.py build` warn when it's broken)

- **File:** `<City> <N>`, like `Riverton 4`. One number, up by one with every export. Every guide holds all the plans,
  and the planner's *Import latest file* loads the newest export, so the newest is always the one to import. After
  exporting, move older exports to `Exports/old/` (`journal.py where` shows the folder).
- **Plan rows:** `<Status> · <Topic>`, at most 26 characters (the planner cuts longer names with "…"). Status, top to
  bottom:
  - **Now**: what tonight's briefing builds;
  - **Next**: after that;
  - **Later**: parked, or ideas;
  - **Base**: the long-term picture (roads, zoning, services, transit);
  - **Done**: kept for one round so the Mayor can compare, then dropped.

  The topic uses the same words as the journal's project and the briefing's task ("Port Gate", "Road fixes").
- **Items inside a Now or Next plan:** plain step numbers in build order, `1 South circle`, `2 Ramp down`.
- **No codes** anywhere the Mayor reads (no "A12", "D2", "R"), and no coordinates.

## Build cards: every Now and Next item says exactly what to build

The Mayor builds from the guide without Claude, so an item must not leave them guessing which road type, roundabout
or junction to use. For every item in a Now or Next plan, the journal step gives:

- **the exact piece, by the name the Mayor sees in the game's menu**: the road ("Small Road Oneway with Trees", a Road
  Builder road by its own name), how many lanes, one-way or two-way, and for a junction its kind (roundabout and its
  size or asset, traffic lights, stop signs, an interchange piece). Take names from `city.py catalogue` (the game's
  menu names, Road Builder roads included, with lanes and cost; locked pieces are left out) or, for a building, park,
  prop or surface from the Mayor's packs, `mods.py find` (its menu name, pack, lot and cost),
  never from memory, and say when a choice is a suggestion rather than a must;
- **a close-up picture** of that spot (the plan drawn over the city, the step's items marked) and a Show-on-map place:
  `plan.py ship` (§ Making one) draws one per step number and writes it into the step as `picture = "…"` and
  `where = {…}`. City Manager 0.9 shows them as Picture and Show on map buttons under the step (an older mod ignores
  them, so for an older mod put the picture on its own line in the project page as well);
- **the same number and words as the plan items**: plan item `2 Cedar: ramp down` and journal step
  "2 Cedar: ramp down (Highway Oneway - 1 lane, about 20 m down)". The Mayor matches them on screen. One job of several
  pieces is one step: `7 West, first street` to `7 West end street` and the area `7 Riverside homes` are all step 7,
  one card. Two journal steps for one number (west and east) need `7a` and `7b` in the plan and the journal, or
  ship leaves them as they are.

**Street names go stale.** The game renames streets when roads are rebuilt: after one evening of rebuilding, three
streets of a test city had new names.
Re-read the names from the newest snapshot (`city.py streets`) before every guide and briefing, and never reuse names
from an older one unchecked.

**After the Mayor builds:** in the report, compare what was built with what the card asked (`plan.py built` does it
item by item): "Gateway: built as a four-way junction with traffic lights, the card said a small roundabout". Ask whether it was on purpose; the Mayor's
choice wins, and the next guide follows what's really there.

## Making one

1. **The Mayor's own drawings come first.** Importing replaces the planner's whole document, so anything the Mayor drew
   since the last guide is lost unless it's in the new one. `plan.py drawings <city>/journal` lists what they drew,
   moved, renamed or deleted since the guide the planner holds (and whether the newest guide was imported at all),
   with `plan.py check` on their drawings; `report.py` shows the same under "In the planner". `plan.py ship` checks it
   too and stops while anything is left: ask the Mayor, then ship with `--keep-mayor` (their changes go into the plan
   file, backed up first: drawn items added, moved or renamed ones take their version, deleted ones go) or
   `--drop-mayor`. Treat their drawings as their ideas: say how they fit the hierarchy and what they'd cost in game,
   never redraw them unasked (`road-hierarchy.md` § When the Mayor breaks the rules). A move under 8 m is a nudge and
   stays as planned.
2. **Write a simple plan file** (see `cityplan.py`'s docstring): `{"plans": [{"name": "Now · Road fixes", "roads":
   [...], "areas": [...], "junctions": [...]}, ...]}`, in the order above. Roads need two or more points, areas three or
   more, and a junction names two roads of its own plan.
3. **Ship it, in one run:** `plan.py ship plan.json <city>/journal`. It checks the plan against the newest snapshot and
   stops on anything to fix (`--force` ships anyway), exports the guide as `<City> <N+1>` with the map id of the
   city's last guide (never another city's), puts the city's older guides in Exports/old, and writes one build-card
   step per step number into the project that links each Now and Next plan (a new project if none does): the picture,
   the place, and a tick once the snapshot shows the step built. A step already there for that number keeps its id,
   its words and its tick, so write the words once, in the journal or in the plan (`"cards": {"7": {"text": "...",
   "note": "..."}}` on the plan), and ship again after any change to the plan. Then it points every project's guide
   link at the new guide and builds the journal. `--dry-run` says what it would do. The cards sit in a marked block of
   the project page; pass `--map-id` for a city whose planner was never opened (founding: the city's name).
4. **By hand, when ship can't:** `cityplan.py export plan.json --name "<City> <N>" --terrain <snapshot>` (the map id
   from the planner's own document; `--map-id` if there are several; fix every `naming:` warning), then in each project
   `[[plans]] kind = "draft"`, `name = "<City> <N>"`, `layers = [the plan rows it uses]`, and `journal.py build`.
5. **Tell the Mayor** in the briefing: "In the planner, Import latest file (<City> <N>)", and which plan to build from.
   Import takes the newest file in Exports **whichever city it's for**: with more than one city, run `cityplan.py
   front "<City> <N>"` before each session so tonight's city's guide is the newest.

## When statuses change

When the Mayor builds a Now plan, it becomes Done in the next guide (one round), a Next plan may become Now, and the
number goes up. Rename only the status and keep the topic, so the journal's words stay the same.
