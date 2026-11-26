# Journal source format

The journal source is a folder of Markdown files, each starting with TOML front matter between `+++` lines.
`journal.py build <folder>` compiles it to `<journals>/<id>/journal.json` (the game's journals folder, from `journal.py where`) and copies the pictures.
It refuses to write when something is wrong, and it lists the problems. The full field list is in the docstring of
`scripts/journal.py`.

**Rules (since 0.3):**
- **Ids:** every step and task needs an `id`. Briefing and report ids are dates (`2026-11-24`, or `2026-11-24-2`), unique within their kind.
- **Pictures:** each one stands on its own line, PNG only, at most 1600 × 3200 after scaling.
- **Stamps:** UTC (`2026-11-24T19:05:00Z`).

```
<city>/journal/
  journal.toml        id (journal folder), city, aliases (in-game city names that open it), manager
  briefing.md         the current briefing
  briefings/*.md      earlier briefings (moved here by `journal.py archive`)
  projects/*.md       one file per project
  projects/archive/   finished projects moved out of the panel by `plan.py advance` (their ids stay known)
  reports/*.md        one file per report (newest first in game, sorted by date)
  city.md             the City tab: facts table, map, street names, what's where
  images/*.png        pictures, referenced as ![caption](name.png) on a line of its own; names of letters, digits,
                      . _ - only; over 1600 x 3200 px gets scaled down
  .stamps.json        written by journal.py: when the manager last changed each tick and status. Keep it; never edit it
```

## Project

```toml
+++
id = "roads"                       # stable: the Mayor's ticks are keyed by it
title = "City roads & road hierarchy"
scale = "city"                     # city | district | street | building | system
status = "active"                  # active | next | idea | hold | done (force_status = true overrules the Mayor's status once)
                                   # the panel shows Now, Next, Later, On hold, Done: the planner's row words
priority = 1                       # 1 = most important; sorts lists and "On your plate"
summary = "Two or three plain sentences."
where = { label = "The Gateway", x = -70, z = -420, zoom = 700 }   # for "Show on map"

[[plans]]
kind = "draft"                     # a City Planning Draft file
name = "Riverton 4"                # the guide file: "<City> <N>"
layers = ["Now · Road fixes"]      # its plan rows: "<Status> · <Topic>" (guides.md)
note = "optional"

[[plans]]
kind = "doc"                       # shown as "On your phone: claude.ai/…"
title = "Riverton road hierarchy review"
url = "https://claude.ai/artifact/…"

[[steps]]
id = "lights"                      # required, stable within the project
text = "What to do, in game words"
done = false
note = "optional small print"
force = false                      # true for one build: the manager's done value overrules the Mayor's tick
picture = "card-2-cedar-ramp-down.png"   # optional: the build card's close-up (an images/ file), opened from a Picture button
where = { label = "2 Cedar", x = 120, z = -340, zoom = 600 }   # optional: Show on map for this step (mod 0.9)

[[log]]
date = "2026-11-23 23:30"
text = "What happened and why."
+++
Markdown body: headings, lists, tables, > callouts, **bold**, pictures. Keep it to what the Mayor reads in game.
```

**Ids and ticks:**
- Ids are what the Mayor's ticks attach to. Renaming a step's id loses its tick; changing its text is fine.
- To show a manager change over a Mayor's tick, change `done`: journal.py stamps the change, so the newer side wins.
- The Mayor's status choice works the same way.

## Briefing

```toml
+++
id = "2026-11-24"
title = "Briefing for Monday evening"
date = "Written 23 Nov, late evening"
summary = "Where the city stands, and the one thing that matters most tonight."

[[tasks]]
id = "lights"
text = "Take the traffic lights off Depot Avenue at Cooper, Lindbergh, Goldenrod and Dale Streets"
project = "roads"                  # optional; must be an existing project id
note = "optional small print"      # shown under the task, before the project name
from = "2026-11-23/lights"         # optional: this task carries on an earlier briefing's task (shown once)
+++
## Before you launch
- Close Claude …
```

## Report

```toml
+++
id = "2026-11-24"
title = "Report: 24 November"
date = "24 Nov 2026"
summary = "Two or three sentences."

[[numbers]]
label = "Population"
before = "3,746"
after = "4,310"                    # "no save yet" when there's nothing measured
change = "+564"

[[replies]]                        # answers a Mayor's note; shows under it in game
note = "n20261124193500-1"         # the id from `journal.py mayor`
text = "On the list for next session: the Gateway roundabout."
+++
## What got built
## What you told me
## What I see
## Decisions for next time
```

## City page (`city.md`)

The front matter has `title`, `date`, `summary` and `[[facts]]` entries (`label`, `value`, `note`). Put the map,
"Street names", "What's where", "What works" and "The big problems" in the body.

## Rendering limits in game

- **Markdown:** single-level `#`, `##` and `###` headings, lists (indent two spaces to nest), tables, `>` callouts, `**bold**`, `` `code` ``, pictures on their own line, and `[text](url)`. Links show as text: nothing is clickable in game.
- **Italic:** shows as a colour, because the game font has no italic.
- **Pictures:** PNG only, from `images/`. Each one is a texture in video memory while it shows, so use a few good ones, not dozens. A page draws at most 24 million picture pixels (about five full-size maps); the rest show as "(picture not shown)".
- **Page size:** each tab draws at most 40,000 characters of journal text, then says the rest is cut off. A real briefing or project page is 2,000–5,000, so this only matters if a page grows huge: split it into projects or reports.
- **Wrap-up:** one per briefing id. A new briefing published mid-session starts a fresh wrap-up (the old answers stay under the old id), so read `jp mayor` for both ids after such a session.
