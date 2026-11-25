# City Manager: how the mod works

The details behind the [README](../README.md): the panel's tabs, where its files live, what it will and won't touch,
and the Claude Code plugin. The journal's file format is in [format/README.md](../format/README.md).

## The panel

Press **Ctrl+J** (or the cones button at the top left) in a city.

| Tab | What it holds |
|---|---|
| **Today** | The briefing for this session with its checklist, anything still open from the last briefing, and the next step of your top projects in progress |
| **Projects** | Every project at any scale: a summary, links to plans and docs, steps to tick, *Show on map*, your own status, the manager's log and your notes |
| **Notes** | Quick notes while you play, optionally pinned to where the camera is looking; the manager's replies appear under them |
| **Wrap-up** | What you ticked and noted this session, what changed in the city since you loaded it (roads, buildings, people, money), four short questions, and *Done for today* |
| **City** | The manager's notes on the whole city (numbers, a map, street names, what's where), the city snapshot (when it was last taken, and *Take a snapshot*), and every report |

## Files

Everything lives in the game's user-data folder, under `ModsData/CityManager`:
- **Windows:** `%USERPROFILE%\AppData\LocalLow\Colossal Order\Cities Skylines II`
- **Linux with Proton:** the same path inside Steam's `compatdata/949230` prefix

```
ModsData/CityManager/
  cities.json               in-game city names -> journal folder   {"aliases": {"My City": "mycity"}}
  picks.json                the mod's memory of your own choices: a journal picked or started by hand, a renamed city
  <journal>/journal.json    the manager's side (the mod only reads it, except to start an empty journal)
  <journal>/images/*.png    pictures the pages show
  <journal>/mayor.json      your side: ticks, statuses, notes, wrap-up answers (the mod writes it; keep a copy if it matters)
  <journal>/mayor.json.bak  the previous version, restored automatically if mayor.json is ever damaged
  <journal>/city.json       the city snapshot: roads, buildings, budget, demand, people, services, problems, transit,
                            the build catalogue, terrain (written on Done for today, on every save, and from Take a snapshot)
  <journal>/city-start.json the same, taken a few seconds after the city loaded: what the session started from
```

Until 0.5 the mod was called City Journal: its `ModsData/CityJournal` folder moves to `ModsData/CityManager` by itself
the first time the renamed mod starts.

Writes are atomic: a crash while saving leaves the old or the new file, never half of one.

When a city loads, the mod picks the journal in this order: your own pick, then an alias in `cities.json`, then a
folder named after the city in lower case with dashes (`New City 1` → `new-city-1`). If none matches, the panel
lists the journals to pick from, or starts an empty one for the city: Notes and Wrap-up work without any manager.
**Change journal** in the panel's header switches, or goes back to the automatic choice. Renaming the city in game
keeps its journal.

`journal.json` is re-read about a second after it changes, so a manager can update it while you play; a journal
written for the city while you play turns up the same way. The cones button then gets an orange dot.

To write a journal yourself, see [format/README.md](../format/README.md); `city.json` is described there too.

## Privacy and safety

- **No network, ever:** the mod never uses the network and sends nothing anywhere. Links in a journal are shown as text only.
- **Files:** it reads and writes only inside `ModsData/CityManager`, and it treats journals as untrusted:
  - folder names must be plain names of existing journals;
  - pictures must be plain PNG names in the journal's own `images` folder, checked again whenever `journal.json` changes and every ten seconds;
  - nothing in a journal can run code or open links;
  - a journal the panel can't draw shows a message instead of disturbing the game's own interface;
  - JSON files over 4 MB and deeply nested JSON are refused;
  - each page of the panel draws at most 40,000 characters of journal text and 24 million picture pixels, with a notice where it cuts; lists stop at 300 items.
- **Text you type** is capped (2,000 characters per note, 4,000 per wrap-up answer) and cleaned of control characters before it's saved. If `mayor.json` would grow past 4 MB, the change isn't saved and the panel says so.
- **Messages and the mod's log** name files only by their place inside `ModsData/CityManager`, so your user name stays out of bug reports.

## Known limits

- **Same-named cities:** two cities with the same name open the same journal unless you pick one by hand.
- **Language:** the panel is in English only.

## Keys

**Ctrl+J** opens and closes the journal; change it in Options → City Manager. While you type in a text box, the game's
own keys are paused, as with any text box in the game.

## The plugin

The City Manager runs in Claude Code (the Claude desktop app's Code tab, or the terminal), on your own PC, between
sessions. Its skill (`plugin/skills/city-manager/SKILL.md`) holds the session loop; its scripts run with `uv run` (which fetches
Python 3.11+ and Pillow), or with Python 3.11+ and Pillow installed. Installing it as a Claude Code plugin from this repo is release 2 on the roadmap.
