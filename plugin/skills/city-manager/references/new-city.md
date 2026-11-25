# Setting up the City Manager: a new player or a new city

The first time, a few minutes. Run the scripts as SKILL.md says (`uv run <this skill's folder>/scripts/journal.py ...`).

1. **Check the setup:** `journal.py doctor`. It checks Python and Pillow, the game's data folder, the City Manager mod,
   City Planning Draft (the build overlay), the journals and their snapshots, and the cities already set up. Help the
   Mayor fix what it flags, one thing at a time:
   - **No `uv`:** the Mayor installs it themselves: on Windows `winget install astral-sh.uv`, elsewhere the install
     line on https://docs.astral.sh/uv/. Then the scripts run with `uv run`.
   - **A mod missing:** subscribe to it in the Paradox Launcher and enable it in the playset. City Planning Draft comes
     with City Manager. Add mods in the launcher, never from inside the game.
   - **No game data folder:** the game must have run once. If it lives somewhere unusual, set `CS2_USERDATA`.
2. **The city's name:** ask the Mayor for their city's name exactly as the game shows it (bottom of the screen). If they
   already started a journal in game (the panel's *Start a new journal for this city*), `doctor` lists it and
   `journal.py init` with no name adopts it, keeping their notes.
3. **Set it up:** `journal.py init "<name>"`. In one go it makes the city's folder, `manager/manager.toml`, a dossier to
   fill in, a journal source with a welcome briefing, and the journal in the game's folder, mapped to the city's name.
   It registers the city in `cities.toml` (the first one becomes `active`). `--folder` puts the city's folder elsewhere;
   `--id` picks the journal's folder name.
4. **Get to know the Mayor:** ask four or five short questions and write `manager/dossier.md` from the answers:
   - what they want this city to become;
   - how long they usually play;
   - what they enjoy, and what they find tedious;
   - how they like to be told things (short lists, pictures, detail);
   - anything they never want the manager to do.
5. **The first look at the city:** if `doctor` shows a snapshot, read it (`city.py summary`, `city.py problems`) and
   write `city.md` and a first real briefing in place of the welcome one (`journal.py archive` first). If there's no
   snapshot yet, the welcome briefing asks the Mayor to take one; the first report starts from it.
6. **Later, if wanted:** a `[tools]` table in `manager.toml` for extra tools the Mayor has (run as written: `facts` after
   play, `mods` after the playset changes), and the first guide once there's a plan to build from
   (`references/guides.md`; the planner must have been opened once in the city first, so its map id exists).

Run `journal.py build` after every change to the journal source, as always.
