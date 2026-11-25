# The journal format

Three files per journal, in the game's `ModsData/CityManager/<journal>/` folder: `journal.json`, the manager's side;
`mayor.json`, the Mayor's side; and `city.json`, the mod's snapshot of the city. The mod reads the first and writes the
other two; a manager writes the first and reads the other two. `merge_cases.json` here holds the merge rule's cases, which the mod's panel tests and the plugin's tests both
run, so the two sides can't disagree.

## journal.json (the manager's side)

`journal.json` is plain JSON. The easiest way to write it is with the plugin's `journal.py` (Python 3.11+ and Pillow),
which compiles Markdown files with TOML front matter, checks them, and copies the pictures; see its docstring. It keeps
the manager's change stamps in `.stamps.json` beside the source, so keep that file with it. Writing `journal.json` by
hand works too:

```json
{
  "format": 1,
  "city": "My City",
  "manager": "Sam",
  "updated": "2026-11-24 18:00",
  "briefing": {
    "id": "2026-11-24", "title": "Tonight", "summary": "Fix the highway exit.",
    "tasks": [{ "id": "exit", "text": "Put a roundabout at the **east exit**", "project": "roads" }],
    "body": "## Before you launch\n- Save first."
  },
  "projects": [{
    "id": "roads", "title": "Roads", "scale": "city", "status": "active", "priority": 1,
    "summary": "The road network.", "where": { "label": "East exit", "x": 120, "z": -400, "zoom": 700 },
    "plans": [{ "kind": "draft", "name": "My City 3", "layers": ["Now · East exit"] }],
    "steps": [{ "id": "exit", "text": "Roundabout at the east exit", "done": false, "changed": "",
                "picture": "card-exit.1a2b3c4d.png", "where": { "label": "East exit", "x": 120, "z": -400, "zoom": 600 } }],
    "log": [{ "date": "2026-11-24 18:00", "text": "Started." }],
    "body": "Markdown: headings, lists, tables, **bold**, > callouts, ![caption](picture.png)"
  }],
  "reports": [], "briefings": [], "replies": {}, "images": {}
}
```

- **Statuses:** `active`, `next`, `idea`, `hold`, `done`.
- **Scales:** `city`, `district`, `street`, `building`, `system`.
- **Ids:** keep them stable. The Mayor's ticks are stored against `p:<project>/<step>` and `b:<briefing>/<task>`.
- **Steps:** `picture` (one of `images`, the step's build card) and `where` (a Show-on-map place) are optional; from mod
  0.9 the panel shows them as Picture and Show on map buttons under the step, and an older mod ignores them.
- **Plans:** `kind` is `draft` (a guide for the City Planning Draft planner: `name` is the guide's file, `layers` its
  plan rows), `doc` (`title`, `url`, shown as text) or `file`.
- **Pictures:** PNG files in the journal's `images` folder, named with letters, digits, `.`, `_` and `-`, and listed in
  `images` (name → `[width, height]`). The mod reads each picture's real size from the file and shows only pictures up
  to 2048 × 4096 pixels and 16 MB, because each one becomes a texture in video memory.
- **Links:** they show as text. Nothing in the panel opens a browser.

## mayor.json (the Mayor's side)

```json
{
  "format": 1,
  "ticks":    { "p:roads/exit": { "done": true, "at": "2026-11-24T19:05:00Z", "gameDate": "March 2026, 09:00" } },
  "status":   { "roads": { "status": "hold", "at": "2026-11-24T19:10:00Z" } },
  "notes":    [{ "id": "n20261124192000-1", "at": "2026-11-24T19:20:00Z", "project": "roads", "text": "jam here",
                 "where": { "x": 120.5, "z": -400.2, "zoom": 600 } }],
  "debriefs": { "2026-11-24": { "answers": { "built": "...", "issues": "...", "next": "...", "ask": "..." }, "done": true } },
  "seen": "2026-11-24T18:00:00Z"
}
```

- **Times:** UTC (`...Z`). The panel shows the Mayor's local time.
- **Ticks and statuses:** a tick or status the Mayor sets wins, unless the manager changes that same step or status
  afterwards (a tie goes to the Mayor). The manager's `changed` / `statusChanged` stamps record when. The cases are in
  `merge_cases.json`.
- **Notes:** each note gets an id. The manager answers a note with
  `"replies": {"<note id>": {"text": "...", "date": "..."}}`, and the answer shows under the note.
- **Wrap-up:** one per briefing, under its id. In a journal without a manager, one per session, under `session-<time>`.
- **Edits from outside:** the mod re-reads `mayor.json` before each change, so a manager's edit (deleting old notes,
  say) isn't overwritten, even while the Mayor plays.

## city.json (the city snapshot)

The mod writes `city.json` when the Mayor presses *Done for today*, after every save the game makes (the Mayor's and
the autosaves), and from *Take a snapshot* on the City tab. About five seconds after a city loads, it also writes
`city-start.json`, the same snapshot at the start of the session. Together they describe the city as the game has it, so
a manager can write a report, see what was built this session, draw a map and fit guides to the real roads without
reading the save. Only a city with a linked journal gets them. A new snapshot replaces the old one; keep copies if you
want history. The plugin's `city.py` reads them.

```json
{
  "format": 1, "mod": "0.6.0", "taken": "2026-11-24T21:05:00Z", "why": "save", "save": "Riverton",
  "city": { "name": "Riverton", "population": 12345, "happiness": 62, "money": 2034000, "unlimitedMoney": false,
            "xp": 12000, "milestone": 5, "tiles": 12,
            "date": { "year": 2026, "month": 6, "hour": 14, "minute": 0, "text": "June 2026, 14:00" } },
  "budget": { "income": { "TaxResidential": 41000 }, "expenses": { "ServiceUpkeep": 38000 },
              "totalIncome": 92000, "totalExpenses": 88000, "balance": 4000 },
  "counts": { "edges": 3012, "nodes": 2410, "buildings": 9876, "residential": 7000 },
  "prefabs": ["Small Road", "Medium Road"],
  "streets": ["Emerson Street"],
  "nodes": [{ "id": 812, "x": 120.5, "z": -400.2, "y": 31.0, "lights": true }],
  "edges": [{ "id": 901, "prefab": 1, "kind": "road", "a": 812, "b": 815, "street": 0, "length": 84.2,
              "pts": [[120.5, -400.2, 31.0], [130.1, -395.0, 31.0], [140.2, -390.1, 31.0], [150.0, -385.3, 31.0]],
              "lanes": [2, 2], "flow": 92 }],
  "buildings": [{ "prefab": 7, "kind": "residential", "level": 2, "lot": [2, 3], "x": 140.0, "z": -420.0, "y": 31.0, "angle": 90 }],
  "districts": [{ "name": "Mill Row", "outline": [[100.0, -500.0], [300.0, -500.0], [300.0, -300.0]] }],
  "tiles": [[-937.0, -313.0, -937.0, -313.0]],
  "terrain": { "size": 256, "cell": 56, "origin": -7168, "heights": "<base64>", "water": "<base64>" },
  "truncated": []
}
```

- **Places:** metres, with `x` east, `z` north and `y` the height, as in the game. Points are `[x, z, y]`.
- **Why:** `start` (the city loaded), `done` (*Done for today*), `save` (the game saved; `save` is the save's name) or
  `button`.
- **Session:** `session.start` is when the city loaded; a session's `city-start.json` and `city.json` share it. In
  `city.json`, `session.changes` compares with the start: `roadsAddedKm`, `roadsRemovedKm`, `railAddedKm`,
  `railRemovedKm` (the city's own roads and tracks, not a building's), `grew` (zoned buildings that appeared), `placed`
  (other buildings that appeared: the Mayor's), `removed`, and the change in `population`, `money` and `tiles`. The
  Wrap-up tab shows the same.
- **Date:** the game's own clock: its year has 12 days, and day N shows as month N.
- **Budget:** per in-game month, as the game's budget panel shows it. Income and expense lines use the game's own names
  (`TaxResidential`, `ServiceUpkeep`, …); expenses, and their total, are positive numbers. `balance` is income minus
  expenses.
- **Tables:** `prefabs` and `streets` hold each name once; edges and buildings refer to them by position.
  `prefabTitles[i]` is the name of `prefabs[i]` as the game's menus show it ("Medium Road" is "Four-Lane Road"), or ""
  when the game has none.
- **Nodes:** the ends of the edges. `lights`, `roundabout` and `outside` (a connection off the map) appear only when true.
- **Edges:** the network pieces between two nodes: roads, rail and paths, not pipes or power lines.
  - `kind`: `road`, `highway` (a road that uses highway rules), `train`, `tram`, `subway` or `path`.
  - `id`, `a` and `b` are the game's entity numbers for this session only: they change when the city is loaded again.
  - `pts`: the curve's four control points (a cubic Bézier), end points first and last.
  - `street`: the street's name as the Mayor sees it on the map, in the game's language, custom names included.
  - `lanes`: car lanes `[forward, backward]`, forward being from `a` to `b`; `bus`: bus-only lanes, the same way.
  - `elevation`: height above the ground at `[a, b]` (negative below it), only when not zero; `tunnel` and `bridge`
    only when true.
  - `flow`: how freely traffic moves, 0 to 100, as in the game's traffic view (roads only); `volume`: the road
    panel's traffic volume, averaged over the day.
  - `speed`: the speed limit in km/h; `upgrades`: what the Mayor added (`lighting`, `grass`, `trees`,
    `wide sidewalk`, `sound barrier`, `parking`, `median grass`, `median trees`); `zoned`: `[cells, built]`, the zoned
    8 m cells along this road and how many have a building.
  - `owned`: part of a building or an asset (a station's tracks, an interchange asset), only when true. A building's
    own footpaths are left out.
- **Buildings:** every building on its own lot (not the extensions and parts of another).
  - `kind`: `residential`, `commercial`, `industrial`, `office` (with their `level`), `service` (with the game's
    `service` name), `signature`, or `other`.
  - `lot`: width and depth in cells of 8 m; `angle`: which way it faces, in degrees (0 is north, 90 east).
  - `name`: the building's name as the game shows it, for buildings that aren't zoned growables.
  - `abandoned` and `condemned` only when true; `district`: its place in `districts`.
  - Service buildings: `efficiency` (percent, as its panel shows; over 100 with bonuses) and `use`: `{what, now, max}`,
    how full it is: `pupils`, `patients`, `prisoners`, `jail`, `garbage`, `bodies`, `sheltered`, `power`, `water`,
    `sewage` or `maintenance` (a park). Fire stations, depots and offices have no `use`.
  - Zoned buildings: `homes`: `[households, homes]`; `jobs`: `[workers, workplaces]` of the companies in it.
- **Districts:** the name, the active `policies` and the outline of each district.
- **Tiles:** the map tiles the city owns, as `[minX, maxX, minZ, maxZ]`.
- **Terrain:** the whole map as a grid of `size` × `size` cells of `cell` metres, starting at `origin` (x and z). Row
  `r`, column `c` is at x = origin + (c + 0.5) × cell, z = origin + (r + 0.5) × cell. `heights` and `water` (the water
  depth) are base64 of little-endian 16-bit numbers in decimetres, row by row.
- **Limits:** at most 100,000 edges and 100,000 buildings, 20,000 problems and 32 MB in all; a list that was cut is
  named in `truncated`. A part the mod couldn't read (after a game update, say) is named there too, as
  `"<part> (failed: …)"`, and the rest of the snapshot is still written.

### The city-wide parts

Between `budget` and `counts`, in this order (`map` from mod 0.9; a snapshot from an older mod doesn't have it). Names in the game's language are as the Mayor sees them; ids are the
game's own (enum or prefab names). Checked against the game's own panels on 24 Nov 2026 (game 1.6.2).

| Part | What it holds |
|---|---|
| `map` | The map and the New Game choices: `name` (the map's name as the main menu showed it), `theme` (the theme prefab: `European`, `North American`…), `leftHandTraffic`, `mode` (the game mode's prefab name: `NormalMode`, or another mode's), `options` (`naturalDisasters`, `unlimitedMoney`, `unlockAll`, `unlockMapTiles`), and `links`: every link off the map, `kind` (`road`, `train`, `air`, `ship`, `power`, `water`) with its `x` and `z`, as the game's own map panel finds them |
| `demand` | The demand bars, 0 to 100: `residentialLow`, `residentialMedium`, `residentialHigh`, `commercial`, `industrial`, `storage`, `office`; `factors`: what pushes each up or down (the game's `DemandFactor` names) |
| `taxes` | Percent for `residential`, `commercial`, `industrial`, `office`; `residentialByEducation` (5 levels) |
| `fees` | Per service (`Electricity`, `Water`, `Healthcare`, `BasicEducation`…): `fee`, and `percent` as the slider shows it (100 is the default) |
| `services` | Per city service, in the budget panel's order: `title`, `budget` (percent), `efficiency` (percent the budget gives), `upkeep` (a month) |
| `loan` | `amount`, `interestPercent`, `monthlyCost`, `limit` (the most the city can borrow) |
| `policies` | The city-wide policies that are on: `title`, and `value` for a slider |
| `history` | The game's own monthly statistics, oldest first, the last value now (up to 24 months): `population`, `money`, `income`, `expenses`, `households`, `workers`, `unemployed`, `happiness`, `health`, `tourists`, `crimeRate`, and passengers by bus, tram, train and subway |
| `people` | `households`, `residents`, `children`, `teens`, `adults`, `seniors`, `students`, `education` (5 levels, uneducated first), `workable`, `workers`, `unemploymentPercent` (as the population panel shows it; residents who work outside the city count as unemployed), `homelessHouseholds`, `homeless`, `health` |
| `jobs` | `total`, `free`, `filled`, and `totalByEducation` / `freeByEducation` (5 levels) |
| `happiness` | `average` (0 to 100) and `factors`: `{factor, points}`, biggest first, as the happiness panel lists them |
| `utilities` | `electricity`: `production`, `consumption`, `fulfilled`, `batteryCharge`, `batteryCapacity`, `import`, `export`, in tenths of a kilowatt (the game shows 77,367 as 7.7 MW); `water`: `freshCapacity`, `freshConsumption`, `sewageCapacity`, `sewageConsumption`, in cubic metres. These are 0 until the simulation has run a moment after loading |
| `problems` | The warning icons: `kinds` (`id`, `title`, `count`) and `items`: `kind` (its place in `kinds`), `x`, `z`, `level` (`Problem`, `Warning`, `MajorProblem`, `Error`, `FatalProblem`), `on` (`building`, `road`, `junction`, `vehicle`, `citizen`, `other`), and the building's `prefab` or the road's `street` |
| `zoning` | Per zone type: `zone`, `title`, `cells` (8 m cells zoned), `built` (with a building) |
| `catalogue` | Every road, track and prebuilt junction in the game's menus: `prefab`, `title`, `kind`, `menu`, `unlocked`, `milestone` (the one that unlocks it), `costPerKm` and `upkeepPerKm` (a month), `lanes` (when the city has one built); `milestone` at the top is the city's. Kinds: `road`, `highway`, `train`, `tram`, `subway`, `junction` (a prebuilt intersection), `roundabout` (the road menu's roundabouts, placed on a junction) and `junction control` (traffic lights, removing them, all-way stops). A Road Builder road has `mod`: `Road Builder`, and `menu` `Road Builder` when it's placed from Road Builder's own list |
| `transit` | Each line: `kind`, `name`, `number`, `color`, `vehicles`, `passengers` (on board now), `usagePercent`, `length`, `active`, and its `stops` in order (`x`, `z`, `name`, `waiting`) |
| `mapTiles` | `permitsLeft`, and every map tile: `owned`, `box` (`[minX, maxX, minZ, maxZ]`), `resources` (`Area`, `BuildableLand`, `FertileLand`, `Forest`, `Oil`, `Ore`, `SurfaceWater`, `GroundWater`, `Fish`, in the game's own units). No prices yet |
| `grids` | `landValue`, `groundPollution`, `airPollution`, `noisePollution` on a `size` × `size` grid (64 × 64, 224 m cells), encoded like the terrain |
- **The planner:** the snapshot doesn't name City Planning Draft's map id. The mod reads only its own folder, so the
  plugin's `cityplan.py mapid` finds it in the planner's documents.
