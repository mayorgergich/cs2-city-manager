# Developing City Manager


## Layout

| Path | What |
|---|---|
| `mod/src/CityManager/Mod.cs` | Entry point: settings, the toggle key, the UI system |
| `mod/src/CityManager/JournalStore.cs` | All file handling (plain .NET + Json.NET, unit-tested), including the one-time move from `ModsData/CityJournal` |
| `mod/src/CityManager/JournalSystem.cs` | Bindings and triggers for the panel, polling, camera moves |
| `mod/src/CityManager/Setting.cs` | Options page: the key binding |
| `mod/src/CityManager/CitySnapshot.cs` | The city snapshot's data and its JSON (`city.json`), offline-tested |
| `mod/src/CityManager/CityReader.cs`, `CityReader.Parts.cs` | Reads the city from the game for a snapshot, one part per frame, read only |
| `mod/ui/CityManager.mjs` | The panel: a hand-written UI module (no bundler). React and `cs2/*` come from the game |
| `mod/tests/` | The mod's tests: C# (`CityManager.Tests`) and the panel (`ui.test.mjs`) |
| `plugin/` | The Claude Code plugin (`.claude-plugin/plugin.json`); the repo root's `.claude-plugin/marketplace.json` lists it |
| `plugin/skills/city-manager/` | The City Manager skill: `SKILL.md`, `references/`, and `scripts/journal.py` (journals), `scripts/city.py` (reads the city snapshot), `scripts/founding.py` (a new city's maps, playset and New Game screen), `scripts/cityplan.py` (guides for City Planning Draft), `scripts/survey.py` (surveys the map from a snapshot, with pictures) and `scripts/plan.py` (checks a plan against the snapshot and draws it) |
| `plugin/tests/` | The scripts' tests, `cityplan_format_1.2.2.json` (City Planning Draft's own format) and `made_up_map.py` (a small made-up snapshot for the survey and plan tests) |
| `format/` | The journal format and `merge_cases.json`, the merge rule's cases, run by both the panel's and the plugin's tests |
| `docs/` | This file, how the mod works (`the-mod.md`), the Windows checklist and a sample journal |
| `art/` | The cones: the master artwork for the icons |

## Build

```
python build.py                       build into dist/CityManager
python build.py test                  run every offline test (no game needed: Json.NET then comes from NuGet)
python build.py check                 run every offline test, then build
python build.py zip                   build, then pack dist/CityManager-<version>.zip (for a tester)
python build.py --install             build and install into the game's Mods folder (game closed; removes an old CityJournal)
python build.py --install-to <Mods>   install into another Mods folder (a test profile)
python build.py --uninstall           remove it from the game's Mods folder (game closed)
```

`build.py` runs on Windows and Linux with Python 3.11+, the .NET SDK and Node.js. It finds the game through Steam (its
registry entry on Windows, its default folders, and every library in `libraryfolders.vdf`), or `CS2_GAME_DIR`. The C#
is a plain `netstandard2.1` project against the game's own DLLs in `Cities2_Data/Managed`: no Unity project, no Burst,
no source generators, and no other mod's DLL.

**Continuous integration** (`.github/workflows/tests.yml`): on every push, GitHub runs `python build.py test` on Linux and
Windows, then runs both plugin scripts through `uv` to check their package lists. It can't build the mod (no game), so
builds happen on the maintainer's machine. The in-game checks on Windows are manual: [windows-checklist.md](windows-checklist.md).

**Sample journal** (`docs/sample-journal`): a made-up city, Riverton, for testers and the docs; a test keeps it building.

## Tests

- **Mod store** (`mod/tests/CityManager.Tests`, xUnit, using the game's Json.NET):
  - folder safety against path traversal;
  - following the city: a second city loaded in the same session, a rename, a journal that appears while playing;
  - picking and starting journals, including a pick that can't be saved;
  - reading journals: half-written, too large, deeply nested, missing;
  - pictures: names, sizes, file sizes, the images folder changing;
  - every Mayor action, and keys the panel couldn't find again;
  - caps and cleaning of the player's text, odd format numbers, notes that aren't objects;
  - `mayor.json` never growing past what the mod can read back;
  - edits from outside: half-written files, edits between polls, backup restore;
  - no user-data path in any message;
  - the journals' folder moving from `ModsData/CityJournal` once;
  - the window's `layout.json`: checked keys and numbers, read back on the next start, junk ignored;
  - the city snapshot's format (`CitySnapshotTests`): every documented field, fields left out when false or zero,
    numbers that don't follow the machine's language (a German decimal comma), NaN and infinity, the terrain's byte
    order, the list limits and the file-size fallback; the city-wide sections and the new road and building fields; the
    comparison with the session's start snapshot (only within one session, not when a list was cut).
- **Panel** (`mod/tests/ui.test.mjs`, `node --test`; React is stubbed):
  - Markdown, including pathological input, tables and a time bound;
  - the page budget: every tab drawn from a hostile journal stays within its characters, elements and picture pixels;
  - the picture-name filter and picture layout;
  - the merge rule (`format/merge_cases.json`), the Wrap-up's key, built-in property names as ids, the error boundary;
  - the City tab's snapshot section and its button; the Wrap-up's "Since you loaded the city" lines;
  - the window: docked by default, floating windows kept on screen and clear of the game's bars (16:9 and 4:3),
    moving, resizing from each edge and corner (resizing stops at the edges instead of moving the window).
- **Plugin scripts** (`plugin/tests`, unittest, a fake user-data folder):
  - build and validation;
  - change stamps, including after `journal.json` is lost, and touched but unchanged pages;
  - pictures, including names the mod would refuse (the mod's two filters are compared with each other);
  - replies;
  - planner-guide warnings;
  - mayor, ack, open and archive, and the command line;
  - the merge rule (`format/merge_cases.json`);
  - `journal.py where`, `doctor` (what's missing, then what's there) and `init` (one city, a second one with an
    accented name and its own folder, adopting a journal started in game with the Mayor's notes kept, the Mayor's own
    pick, and what it refuses);
  - the guide exporter: City Planning Draft's format (`cityplan_format_1.2.2.json`), the naming warnings, junctions
    naming their own roads, the map id from the planner's document, reading the Mayor's drawings back;
  - `founding.py` on a made-up game install: the maps (the game's, a map mod, the player's own; an asset pack isn't
    a map), resources rated against the other maps, one map's needs and playset state, the playset check, the
    founding answers' check, and the New Game steps;
  - `city.py` on a made-up city: the summary, changes across sessions matched by where roads are, streets, problems,
    services, the catalogue, and older snapshots without the newer parts;
  - `survey.py` on a made-up map (`made_up_map.py`: a river, a steep hill, a highway with a bridge and a lane crossing
    it at grade, a railway, 5 × 5 tiles with two owned): the tiles to buy next (sides, not corners), slopes, which way
    the river flows, connections off the map, where a highway ends or meets a street at grade, a map where every tile is
    owned, words without coordinates, the pictures' sizes, older snapshots and one without terrain;
  - `plan.py` on the same map: crossings and joins at grade (highways, the railway), underpasses, tunnels, bridges and a
    highway already on a bridge, steep ground and water, Now and Next pieces on tiles the city doesn't own, pieces from
    the catalogue (locked, unknown, missing), highways inside the plan, what the exporter would refuse, naming,
    junctions close together, every drawing view, the exit status; and `cityplan.py export --terrain` reading ground
    heights from a snapshot.
- **In game:** before installing a build, the maintainer runs a suite of checks inside a hidden copy of the game (it
  needs a private test harness, so it isn't in this repo). It checks:
  - the first start moving `ModsData/CityJournal` to `ModsData/CityManager`;
  - picking a journal, including traversal attempts;
  - every Mayor action;
  - hostile trigger calls (caps, control characters, NaN camera moves);
  - broken, oversized, deeply nested, huge (under the cap, so it's drawn) and malformed journals;
  - hostile and oversized pictures;
  - replies;
  - live updates and the new-update dot;
  - switching and starting journals;
  - loading a second city in the same session (it must not take over the first city's journal);
  - the city snapshot: on *Done for today*, from the button and on a game save (named after the save); its contents
    (city, date, budget, roads with lanes and street names, nodes, outside connections, terrain); two snapshots in a
    row of the paused city are the same (it only reads); the City tab's time; the log's timings; the start snapshot when a
    journal is linked, later snapshots in the same session, every city-wide part present with none failed, menu names,
    the catalogue, map tiles and grids, the Wrap-up's "Since you loaded the city", and no snapshot frame over 50 ms;
  - the window: Float, dragging by the title, resizing from a corner grip, both saved in `layout.json`, the game staying
    clickable around it, Dock, and floating again where it was left;
  - the key registration;
  - the mod's and the game's UI logs.

- **Counts as of 0.8.0:** 92 mod store (on Windows run twice: .NET 10 and .NET Framework 4.8), 28 panel, 101 plugin scripts (one Windows-only), 77 in game. CI runs the offline ones on Linux and Windows, from a temporary folder named "Zoë Ørsted". The second-city check fails on 0.3.0 (checked 2026-11-24: it linked the second city to the first one's journal).
- **Windows file handling** (no tester yet, so in CI): saving while another program holds the file (shared for writing,
  or only for reading), `journal.py` replacing `journal.json` while the game reads it, and paths with accents. The C#
  tests also run on .NET Framework 4.8, which, like the game's Mono on Windows, saves through Windows' own functions.
  Learned on the way: a folder's change time is unreliable there, so pictures are re-checked every ten polls.
- **Not covered:** the game's own Mono on real Windows, and the panel in the Windows game; the in-game suite under Proton
  and the manual checklist cover those.


## Gameface notes (measured in game, 2026-11-23)

- Text mixed with styled spans is laid out as separate blocks, so a bold phrase lands on its own line. Inline markup is rendered as one wrapping flex item per word, with the following space as a hard space inside the word, because Gameface drops a leading space in a text item.
- The game font has no italic face, and Gameface falls back to a monospace font. Italic is drawn as a colour instead.
- `flex: n` sizes items from their content, so table columns don't line up. Use `flexGrow` with `flexBasis: 0`.
- Pictures from ModsData are served through `UIManager.defaultUISystem.AddHostLocation("cityjournal", root, false)`, which gives `coui://cityjournal/...`. Give each picture an explicit height.
- `<textarea>` and `<input>` work. The game blocks its own keys while any text box has focus (`OnTextInputTypeChanged` sets `InputManager.hasInputFieldFocus`).
- The game's year has 12 days, and the clock shows day N as month N.
- A React error in a mod's module unmounts the game's whole UI, because the game has no error boundary. The panel and button sit inside `Guard`, and every component treats journal data as untrusted (`str()`, `objs()`).
- Json.NET turns date-like strings into dates by default and writes them back differently. `JournalStore.Parse` uses `DateParseHandling.None`, so the stamps round-trip exactly.
- The UI engine passes strings to C# as C strings, so a NUL character ends a string.
- `coui://ui-mods/` is shared by every mod's UI folder, so the icon names carry the mod's name.
