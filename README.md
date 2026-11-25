<p align="center"><img src="mod/src/CityManager/Properties/Thumbnail.png" alt="City Manager: colourful cones in a ring" width="180"></p>

# City Manager for Cities: Skylines II

**Build your city, with a City Manager keeping you on track.**

## Why

In an ideal world I'd have hours to play CS2, but honestly, I'm busy. Sometimes I step away from the game for a while,
only to come back to a city full of half-finished projects and no clear path forward.

I tried some of the AI tools and MCP bridges out there, but most of them either need a live connection to the game
while Claude runs, or push to build things for you. I still want to play the game myself. I just wanted a hand along
the way: someone to organize my ideas and guide my long-term projects.

So that's what this is: a mod and a Claude Code plugin that help you plan your city, keep a journal and tick off to-do
lists with the in-game journal mod. It can even draw detailed plans for your whole map if that's what you're looking for. You still get to actually play: be creative and change
things up on the fly, without an AI looking over your shoulder while you play.

## Made with AI with limited human review

Please read this before you install it. **I'm not a coder.** I designed City Manager, decided how it should work, and
tested every version in my own city, but the code was written by Claude (Anthropic's AI) through Claude Code, working
closely with me. **No experienced programmer has reviewed it.** It has a lot of automatic tests, and I've tried to be
careful about safety (the [security report](SECURITY.md) lists exactly what it touches), but treat it as an unreviewed
hobby project.

If you know your way around C#, CS2 modding or Python, I'd genuinely welcome a review: open an issue, or come and say hi
on the Discord.

This is a tool I made for my own games and keep improving as I play. I'm sharing it in case it's useful to someone
else too.

## Features

**In the game (the mod)**
- [x] A journal panel (Ctrl+J, or the button at the top left) with five tabs: Today, Projects, Notes, Wrap-up and City
- [x] Tonight's checklist, with anything left over from last time carried forward
- [x] Projects of any size, from one building to the whole map, with steps to tick, your own status and *Show on map*
- [x] Notes while you play, pinned to where the camera is looking; the City Manager's answers appear under them
- [x] A four-question wrap-up and *Done for today*
- [x] Updates from the City Manager show up while you play (the button gets an orange dot)
- [x] One journal per city, found automatically, and it stays with your city if you rename it
- [x] A snapshot of your city for the City Manager, taken when you finish, whenever the game saves, or when you ask:
      roads with their street names, lanes and traffic; buildings and how full each service is; the budget, demand,
      people and jobs; problems on the map; transit lines; and every road piece you can place right now
- [x] "Since you loaded the city" in the Wrap-up: the roads you built, the buildings that grew, people and money
- [x] A window you can dock, or float, move and resize; it remembers where you left it
- [x] Works on its own as a notebook, without Claude

**Between sessions (the plugin, with Claude Code)**
- [x] A briefing before you play: a short task list and your projects' next steps
- [x] A post-game review after you play: what you built, an answer to every note, what's still open, and the next plan
- [x] Plans drawn over your city with City Planning Draft: numbered build steps with the exact road pieces and
      junctions by their menu names, named so you always know which is which (`Riverton 4`, `Now · Main street`)
- [x] Your own drawings in the planner are kept when the City Manager writes a new plan
- [x] Nothing drops off the list: open tasks carry over, stale ones get asked about, and projects keep their history
- [x] One-line install in Claude Code, and a first-run setup that checks your game and makes your city's journal

**Coming next**
- [ ] Reports straight from the snapshot: your numbers against last session, a fresh map, and steps checked in the city
- [ ] *Show in planner*: open a project's plan in City Planning Draft with one click
- [ ] Notes about the building, road or district you've selected, and notes marked as questions for the City Manager
- [ ] A briefing that fits the time you have ("about an hour tonight")

**Later**
- [ ] Findings that stay tracked from report to report (a road-hierarchy check first), and trends over many sessions
- [ ] Pins on the map, nudges at a game date or milestone, and a short chronicle of your city in each report
- [ ] Other languages

## How

**1. Check in before you play.** Open Claude Code and tell it you're about to play. Your City Manager looks at where your
city stands (the snapshot the mod took when you last played, your notes, everything still open) and gets you set up:
- tonight's briefing in your journal: a short list of tasks to tick off, and your projects with their next steps;
- plans drawn right over your city with City Planning Draft: the roads, zones and junctions to build, numbered in the
  order to build them, each with the exact pieces to use.

**2. Close Claude and play.** Press Ctrl+J in the game and your journal is there. Follow the plan as much or as little
as you like. When something bugs you, jot a note; it gets an answer next time. No AI runs while you play.

**3. Check out when you're done.** Answer the four short wrap-up questions, press *Done for today*, then save and close
the game. Open Claude Code back up and tell it you've just played. You get a full post-game review (what you built
compared with the plan, an answer to every note, what's still open) and an updated plan, ready for your next check-in.

## Oh no-nos

- **It never builds anything.** It plans, explains and keeps track; you decide and you build. Ignore the plan whenever
  you like: it's your city.
- **No AI in the game, and no internet.** The mod never goes online and never talks to an AI. Claude only runs when you
  open it, between sessions.
- **It stays out of your save.** Everything lives in its own folder next to your saves (`ModsData/CityManager`), as
  plain files you can open and read.

## Requirements

- **Cities: Skylines II**, on Windows, or on Linux through Steam's Proton.
- **City Planning Draft** by nooolan (Paradox Mods 155935), which draws the plans over your city. It's a required mod,
  so the launcher installs it along with City Manager.
- **Claude Code**, for the City Manager itself. It comes with a paid Claude plan and runs on your own computer (in the
  Claude desktop app's Code tab, or in a terminal). The plugin's scripts also need [uv](https://docs.astral.sh/uv/),
  which fetches the Python they run on.

No Claude? The mod still works on its own as an in-game notebook for your notes, projects and wrap-ups, and you can
write a journal by hand ([format/README.md](format/README.md)).

## Getting started

1. **The mod.** City Manager isn't on Paradox Mods yet; until it is, build it from this repo with `python build.py
   --install` (see [docs/DEVELOPING.md](docs/DEVELOPING.md)), and subscribe to City Planning Draft in the Paradox
   Launcher.
2. **uv,** which runs the plugin's scripts. On Windows: `winget install astral-sh.uv`. Elsewhere: the one-line install on
   [docs.astral.sh/uv](https://docs.astral.sh/uv/).
3. **The plugin.** In Claude Code (the Claude desktop app's Code tab, or a terminal), type:

   ```
   /plugin install city-manager --marketplace mayorgergich/cs2-city-manager
   ```

   That needs Claude Code 2.1.275 or later. On older versions, use two lines instead:
   `/plugin marketplace add mayorgergich/cs2-city-manager`, then `/plugin install city-manager@cs2-city-manager`.
4. **Your city.** Load your city in the game once with the mod on, then tell Claude: *"Set up City Manager for my city."*
   It checks your setup (the mods, the game's folder, uv), asks a few questions about how you like to play, and makes
   your city's journal. Press Ctrl+J in the game and the welcome briefing is there.

From then on: tell Claude when you're about to play and when you've just played (see "How" above).

## Current progress

Early days. I play with it in my own city every session, and it has a lot of automatic tests, but it isn't on Paradox
Mods yet. I play on Linux. Windows is covered by the
automatic tests but hasn't had a player yet, so if you're on Windows, you'd be a big help. What's planned is in the
Features list above.

## Design principle

I designed City Manager as a player, around the way I actually play, and built it with Claude Code: I described what I
needed, Claude wrote the code and the tests, and I tried every version in my own city. Every change runs automatic
tests on Windows and Linux, and every build I install passes 60 checks inside a hidden copy of the game first. Even so,
it's a hobby project by one player, so please tell me when something's off.

## Questions, ideas and bugs

- **Discord:** <https://discord.gg/Rtea83Gnb9> for questions, ideas, and showing off your city.
- **GitHub:** open an issue on this repo for bugs and suggestions.

For a bug, the mod's log helps a lot: `Logs/CityManager.log` in the game's user-data folder. It never shows your user
name. For a security or privacy problem, please tell me privately first (see [SECURITY.md](SECURITY.md)).

## More detail

| Part | What it is | Folder |
|---|---|---|
| **The mod** | The panel in the game, and the city snapshot it writes for the City Manager | `mod/` |
| **The plugin** | The City Manager for Claude Code: the skill, `journal.py` (writes the journal) and `cityplan.py` (writes the plans for City Planning Draft) | `plugin/` |
| **The formats** | `journal.json`, `mayor.json` and `city.json`: how the two talk to each other. Anyone can write a journal by hand | `format/` |
| **City Planning Draft** | The build overlay, by nooolan (Paradox Mods 155935). Not ours: a required mod | |

- What it touches, and what it sends where (nothing, to me): [SECURITY.md](SECURITY.md)
- How the mod works (its tabs, files, privacy and keys): [docs/the-mod.md](docs/the-mod.md)
- The file formats: [format/README.md](format/README.md)
- Building and testing it yourself: [docs/DEVELOPING.md](docs/DEVELOPING.md)

## Credits

- **City Planning Draft** by nooolan: the build overlay this all leans on.
- **LancerComet's Cities: Skylines II MCP bridge** (Apache-2.0): its code showed how to read the city from inside the
  game.
- And Ben Wyatt, who taught us that it's all about the cones.

## Licence

MIT: see [LICENSE](LICENSE).
