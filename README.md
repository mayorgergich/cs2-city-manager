<p align="center"><img src="mod/src/CityManager/Properties/Thumbnail.png" alt="City Manager: colourful cones in a ring" width="180"></p>

# City Manager for Cities: Skylines II

**You build the city. Your City Manager keeps the plans.**

## Why I made this

My biggest problem with CS2 was never the building. It was the planning. As my city grew, so did the list of things I
meant to get to, and I'd end up leaving projects half-done, giving up on the city and starting a new one, only for the
same thing to happen all over again.

I tried mods and AI tools that build things for you, but that just wasn't fun for me. I still wanted to *play* the
game. What I actually needed was someone to keep my ideas organized and keep me on track from one session to the next.

So I made City Manager, modeled after the greatest City Manager of all time, Ben Wyatt. It's two things:

- **A mod:** a journal inside the game with tonight's plan, your projects, your notes and a quick wrap-up when you're
  done.
- **A Claude Code plugin:** Claude plays your City Manager between sessions. Before you play, it writes the plan. After
  you play, it looks at what you built and gets the next plan ready. It can even draw the plans right over your city
  with City Planning Draft.

Claude never runs while you play, and you're free to ignore the plan, change your mind and build whatever you want.
It's your city.

## Heads up: this is made with AI

I want to be upfront about this. I do have minor coding experience, but I could never have built something like this
without the help of AI. Claude (Anthropic's AI) wrote the code through Claude Code, working closely with me: I designed it, decided how it should work
and tested every version in my own cities. **No experienced programmer has reviewed it yet.**

There are a lot of automatic tests (they run on Windows and Linux with every change, and every build passes 86 checks
inside a hidden copy of the game before I install it), and the [security report](SECURITY.md) lists exactly what it
touches. Still, please treat it as a hobby project. Results may vary!

If you know C#, CS2 modding or Python and feel like taking a look, I'd really appreciate it. Open an issue or come say
hi on the Discord.

## What it does

**In the game**
- Press **Ctrl+J** (or click the cones) to open your journal: Today, Projects, Notes, Wrap-up and City
- Tonight's to-do list, with anything you didn't get to carried over
- Projects of any size, from one building to the whole map, with steps to tick off and *Show on map*
- Build cards: a step can come with its own close-up picture and a button that takes the camera right to the spot
- Notes while you play, pinned to wherever you're looking. Your City Manager answers them next time
- A quick wrap-up when you're done, plus what changed since you loaded the city
- A snapshot of your city for your City Manager: roads and street names, buildings, the budget, services, problems,
  transit, the map itself and every road piece you can build right now
- A window you can dock or float wherever you like, with text that follows the game's text size setting
- Works fine on its own as a notebook, no Claude needed

**Between sessions (with Claude Code)**
- A pre-game briefing: a short to-do list, sized to however much time you've got
- A post-game report: what you built compared with the plan, the numbers since last time, and an answer to every note
- Plans drawn over your city in City Planning Draft, with numbered steps and the exact road pieces to use
- A founding chat for a brand-new city: help picking a map, what kind of city you want, and its first roads
- Taking over a city you already have: a tour of what's there, and your half-finished plans turned into projects
- Nothing falls off the list: open tasks carry over and projects keep their history

**Coming next**
- [ ] *Show in planner*: open a project's plan in City Planning Draft with one click
- [ ] Notes about the building, road or district you've selected, and notes that are questions for your City Manager
- [ ] Fewer setup steps (I know there are a lot right now)
- [ ] Other languages, eventually

## How it works

1. **Before you play,** open Claude Code and type `/city-manager:city-manager`, then tell it you're about to play. It
   checks where your city's at and puts tonight's plan in your journal.
2. **Close Claude and play.** Press Ctrl+J in the game and your plan is there. Follow it as much or as little as you
   want, and jot down a note whenever something bugs you.
3. **When you're done,** answer the wrap-up questions, press *Done for today*, then save and close the game. Type the
   same command and tell it you just played. You get a report on your session and the next plan.

## The rules it plays by

- **It never builds anything.** It plans and keeps track. You decide and you build.
- **No AI in the game, and no internet.** The mod never goes online. Claude only runs when you open it, between
  sessions.
- **It stays out of your save.** Everything lives in its own folder next to your saves (`ModsData/CityManager`), as
  plain files you can open and read.

## What you need

- **Cities: Skylines II,** on Windows, or on Linux through Steam's Proton.
- **City Planning Draft** by nooolan, which draws the plans over your city. It installs automatically with City Manager.
- **Claude Code,** which comes with a paid Claude plan. It runs on your own computer, in the Claude desktop app's Code
  tab or in a terminal. The plugin's scripts also need [uv](https://docs.astral.sh/uv/), which grabs the Python they
  run on.

No Claude? The mod still works on its own as a notebook for your notes, projects and wrap-ups, and you can even write a
journal by hand ([format/README.md](format/README.md)).

## Getting started

1. **Get the mod.** Subscribe to [City Manager on Paradox Mods](https://mods.paradoxplaza.com/mods/169373/Windows) in the
   Paradox Launcher or on the website. City Planning Draft comes with it. Add mods in the launcher, not from inside the
   game. (Want to build it yourself? See [docs/DEVELOPING.md](docs/DEVELOPING.md).)
2. **Install uv.** On Windows: `winget install astral-sh.uv`. Anywhere else: the one-line install on
   [docs.astral.sh/uv](https://docs.astral.sh/uv/).
3. **Install the plugin.**
   - **In the Claude desktop app** (Code tab): open the plugins menu (**+** next to the prompt box), then **Add** →
     **Add marketplace** → **Add from a repository**, paste `https://github.com/mayorgergich/cs2-city-manager`, press
     **Sync**, and install **city-manager**.
   - **In Claude Code in a terminal:** `/plugin install city-manager --marketplace mayorgergich/cs2-city-manager`
     (Claude Code 2.1.275 or later; on older versions, `/plugin marketplace add mayorgergich/cs2-city-manager`, then
     `/plugin install city-manager@cs2-city-manager`).

   If it asks where to install it, pick **for you** so it works in any folder.
4. **Start a journal in the game.** Load your city (or make a new one), press **Ctrl+J** and pick *Start a new journal
   for this city*. That's it: the mod takes the snapshot your City Manager reads from right away. Save, then close the
   game or go back to the main menu.
5. **Meet your City Manager.** In Claude Code, type `/city-manager:city-manager`. It asks whether you're continuing a
   city or starting a new one, and takes it from there. A new city gets founded properly: what kind of city you want,
   its first roads and planner drafts. A city you already have gets a tour, a plan for what's next, and your
   half-finished plans turned into projects. Haven't made the city yet? Just say so, and it'll help you pick a map
   first.

Use the same folder each time: Claude Code remembers what you've allowed it to do per folder. The
[guide](docs/guide.md) walks through all of it with a flowchart, and from then on it's the same command before and after
every session.

## Where it's at

It's early days. The beta has been on [Paradox Mods](https://mods.paradoxplaza.com/mods/169373/Windows) since
25 November 2026, and I play with it every session. I play on Linux, so Windows hasn't had a real player yet. If you're
on Windows, you'd be a huge help.

## Questions, ideas and bugs

- **Discord:** <https://discord.gg/Rtea83Gnb9> for questions, ideas, and showing off your city.
- **GitHub:** open an issue here for bugs and suggestions.

If you hit a bug, the mod's log helps a lot: `Logs/CityManager.log` in the game's user-data folder (it never shows your
user name). For a security or privacy problem, please tell me privately first ([SECURITY.md](SECURITY.md)).

## More detail

| Part | What it is | Folder |
|---|---|---|
| **The mod** | The panel in the game, and the city snapshot it writes for the City Manager | `mod/` |
| **The plugin** | The City Manager for Claude Code: the skill, `journal.py` (writes the journal) and `cityplan.py` (writes the plans for City Planning Draft) | `plugin/` |
| **The formats** | `journal.json`, `mayor.json` and `city.json`: how the two talk to each other. Anyone can write a journal by hand | `format/` |
| **City Planning Draft** | The build overlay, by nooolan (Paradox Mods 155935). Not ours: a required mod | |

- How to use it, step by step, with flowcharts of the founding chat and of starting the city: [docs/guide.md](docs/guide.md)
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
