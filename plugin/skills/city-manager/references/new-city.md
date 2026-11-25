# Setting up the City Manager for a new city

Do this once per city. It takes about ten minutes.

1. **Mods in the game.** The City Manager mod and City Planning Draft (the build overlay) must be enabled in the
   Paradox Launcher's playset (the launcher installs City Planning Draft with City Manager). Add mods in the launcher,
   never from inside the game.
2. **City folder.** Run `journal.py where` to see the data folder. Make `<data>/<city-slug>/` (lowercase letters,
   digits and dashes), add the city to `<data>/cities.toml`, and make it `active` if the Mayor is switching:

   ```toml
   active = "riverton"

   [cities.riverton]
   name = "Riverton"
   dir = "<data>/riverton"          # any folder works; ~ is expanded
   ```
3. **Manager settings.** Write `<city>/manager/manager.toml`:
   - `city`: the Mayor's name for it;
   - `save_names`: every name the city has had in game (renames included);
   - `journal = "../journal"`;
   - optionally a `[tools]` table naming extra tools for this city, run as written: `facts` (after play) and `mods`
     (after the playset changes).
4. **Dossier.** Write `<city>/manager/dossier.md` with these sections, about a page in all:
   - Identity
   - How the city makes its living
   - The Mayor (how they like to play and be briefed)
   - The plan (and the current guide)
   - Street names and places
   - Watch list
   - Tools for this city
5. **Journal source.** Create `<city>/journal/` with:
   - `journal.toml`, whose `id` is the journal folder name and whose `aliases` are the in-game city names;
   - `city.md`;
   - a first `briefing.md`;
   - one project per real piece of work.

   Run `journal.py build`. It writes the journal into the game's journals folder and maps the city names to it in
   `cities.json`, so the mod opens it for that city.
6. **First guide** (if there's a plan to build from): `references/guides.md`. The planner needs to have been opened once
   in the city first, so its map id exists.
7. **Baseline.** If the city has a facts tool, run it once, so the first report has numbers to compare against.
