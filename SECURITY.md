# Security and privacy report

What City Manager touches, how, and what it sends where. In short: **nothing in this project sends anything to me, or
to anyone else.** The mod never uses the network. The plugin's scripts never use the network. The only place your city's
details go is Anthropic, when you use Claude Code yourself, as part of your own conversation with Claude.

This was written by Claude, the AI that wrote the code, and checked against the code on 24 Nov 2026 (version 0.7.0). It
has not been checked by an independent reviewer: see the README's note on how this was made. Every claim below can be
checked in the source, and "How to check it yourself" at the end shows how.

## The mod (inside the game)

### What it reads

- **The city, through the game's own data, read only:** roads and their names, buildings, districts, map tiles, the
  budget, demand, people and jobs, services, problems, transit lines, terrain and water, and the build menus. It uses
  the same game functions as the game's own info panels. It never changes a value, places or removes anything, or
  pauses or unpauses the game. The one thing it moves is the camera, when you press *Go* on a note you pinned.
- **Its own folder:** `ModsData/CityManager` in the game's user-data folder:
  - Windows: `%USERPROFILE%\AppData\LocalLow\Colossal Order\Cities Skylines II`
  - Linux: the same folder inside Steam's Proton prefix

  It reads no other file on your computer.
- **The game's language file**, through the game, for names as the game shows them.

### What it writes

Only inside `ModsData/CityManager`:

| File | What | When |
|---|---|---|
| `<journal>/mayor.json` (and `.bak`) | Your ticks, statuses, notes and wrap-up answers | When you change something in the panel |
| `<journal>/journal.json` | An empty journal | Only when you press *Start a new journal* |
| `<journal>/city.json` | The city snapshot | *Done for today*, every game save, *Take a snapshot* |
| `<journal>/city-start.json` | The snapshot at the start of a session | A few seconds after a city loads |
| `cities.json`, `picks.json` | Which journal belongs to which city | When you pick or start a journal |
| `layout.json` | Where you put the panel and its size, per screen shape | When you move, resize, float or dock it |

- Writes are atomic: a crash leaves the old file or the new one, never half of one.
- Once, on the first start of version 0.5 or later, it renames its old folder `ModsData/CityJournal` to
  `ModsData/CityManager`.
- The game writes the mod's log to `Logs/CityManager.log`. The mod names files there only by their place inside its
  folder, so your user name stays out of the log.

### What it adds to the game

- **A panel and a button** in the game's interface, and the key **Ctrl+J**, which you can rebind in Options.
- **A picture address**, `coui://citymanager/`, so the panel can show the pictures in your journals. It serves the files
  of `ModsData/CityManager` to the game's own interface, and only that folder. Like any mod's files, other mods' interface
  code in the same game could read those files.
- **Commands for its panel** (tick, note, pick a journal…). Other mods in the same game can call them too, so the mod
  checks every value again: folder names must be plain names of existing journals, text is capped and cleaned, camera
  moves must stay on the map, and so on.

### What it never does

- **No network:** no web requests, sockets or downloads, and no links opened. A link in a journal shows as plain text.
- **No other programs:** it starts nothing.
- **No data collection:** no telemetry, analytics or crash reports of its own.
- **Your saves:** it doesn't read them or write to them.
- **Code from a journal:** nothing in a journal can run code. Journals are treated as untrusted:
  - files over 4 MB and deeply nested files are refused;
  - pictures must be plain PNG names in the journal's own folder;
  - each page shows at most 40,000 characters and 24 million picture pixels.

  The full list is in [docs/the-mod.md](docs/the-mod.md#privacy-and-safety).

### What a snapshot contains

Your city as the game has it: names the game made up, names you gave to streets, districts and buildings, numbers and
places. It contains no account name, no file path and nothing from outside the game. It stays on your computer unless
you share it.

## The plugin (on your computer, with Claude Code)

The plugin is a Claude Code skill plus three Python scripts. Claude Code runs on your own computer.

| Script | Reads | Writes |
|---|---|---|
| `journal.py` | A journal's source folder; `mayor.json` (it never writes it); its list of cities in its data folder (`%LOCALAPPDATA%\CityManager` or `~/.local/share/city-manager`); for `doctor`, the game's `Mods` folders, to check the mods are installed | `journal.json`, pictures, `cities.json` in `ModsData/CityManager`; its own notes beside the source (`.stamps.json`, `.manager-state.json`); with `init`, a new city's folder (settings, dossier, journal source) and `cities.toml` in its data folder |
| `city.py` | `city.json`, `city-start.json` | Nothing |
| `cityplan.py` | City Planning Draft's documents (to keep your own drawings) | Guides in City Planning Draft's `Exports` folder, and a copy of a plan where you ask |

- **No network, no other programs:** none of the scripts touches the network or starts another program.
- **`uv`:** if you run the scripts with `uv`, uv downloads Python and the Pillow picture library from their usual public
  sources the first time. That is uv's own download, not this project's.
- **Installing the plugin:** Claude Code downloads it from this GitHub repo. The plugin has no hooks, agents or servers
  of its own: just the skill and its three scripts.

### What goes to Anthropic

When you use the City Manager in Claude Code, Claude reads your journal, your snapshot, your notes and your wrap-up
answers to write briefings and reports. That content goes to Anthropic as part of your conversation, under your own
Claude account and Anthropic's terms and privacy policy, exactly like anything else you share with Claude. It does not
go to me. I can't see it, and this project has no server.

The skill tells Claude:
- to treat your notes and mod descriptions as data, not instructions;
- never to write your `mayor.json`, change your city, or start the game;
- to ask before anything is published.

## Things outside this project

- **Cities: Skylines II and Paradox:** the game, its launcher and Paradox Mods have their own telemetry and terms. This
  mod adds nothing to them.
- **City Planning Draft** (by nooolan): a separate mod, required for the build overlay. Its code is not part of this
  project; review it separately if you want to.
- **Claude Code and Anthropic:** see above.
- **GitHub:** the repo's automatic tests run on GitHub's machines. They test the code; they never see your game or your
  data.
- **Discord:** only a link in the README.

## How to check it yourself

- **Search the mod's code for any network use.** On Linux or macOS, from the repo:

  ```
  grep -rn -E "System.Net|HttpClient|WebClient|WebRequest|UnityWebRequest|Socket|Process.Start|OpenURL" mod/src mod/ui
  grep -rn -E "fetch\(|XMLHttpRequest|WebSocket|window.open" mod/ui
  grep -rn -E "urllib|requests|http.client|socket|subprocess|os.system|webbrowser" plugin/skills/city-manager/scripts
  ```

  Each prints nothing. On Windows, use your editor's "find in files" with the same words.
- **Where it writes:** every file write in the mod goes through `JournalStore.WriteText` or happens inside
  `JournalStore`, with paths built from its own folder.
- **Build it yourself:** `python build.py` builds the mod from this source ([docs/DEVELOPING.md](docs/DEVELOPING.md)),
  so you can use your own build instead of a downloaded one.

## Reporting a problem

If you find a security or privacy problem, please tell me privately first. Use GitHub's "Report a vulnerability" on
this repo, or a direct message on the [Discord](https://discord.gg/Rtea83Gnb9), rather than a public post. Anything else
can go in a GitHub issue or on the Discord.
