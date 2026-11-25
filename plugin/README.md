# City Manager for Cities: Skylines II

**You build the city. Your City Manager keeps the plans.**

My biggest problem with CS2 was never the building, it was the planning. As my city grew I'd leave projects half-done,
give up on the city and start a new one. I didn't want something that builds for me, though: I still wanted to *play*.
So this plugin turns Claude into my City Manager (modeled after the greatest City Manager of all time, Ben Wyatt), and it
pairs with a small mod that puts a journal inside the game.

- **Before you play,** type `/city-manager`. It checks where your city's at, writes tonight's plan into
  the journal, and draws the plan over your city with City Planning Draft, step by step, with the exact road pieces.
- **While you play,** Claude is closed. Press Ctrl+J in the game for your plan, tick things off and jot down notes.
- **After you play,** type the same command. It looks at what you built compared with the plan, answers your notes,
  and gets the next plan ready.

It works for a brand-new city (it helps you pick a map and plan the first roads) or one you already have (a tour of
what's there, and your half-finished plans turned into projects). It never builds anything: you decide and you build.

## What you need

- **Cities: Skylines II** and the **City Manager** mod from Paradox Mods (City Planning Draft installs with it):
  <https://mods.paradoxplaza.com/mods/169373/Windows>
- **Claude Code** (it comes with a paid Claude plan), in the Claude desktop app or a terminal.
- **[uv](https://docs.astral.sh/uv/)** to run the scripts. Don't have it? Your City Manager offers to install it, with
  one command you approve.

**Install.** In the Claude desktop app (Code tab): the plugins menu (**+** next to the prompt box), **Add** → **Add
marketplace** → **Add from a repository**, paste `https://github.com/mayorgergich/cs2-city-manager`, press **Sync**,
and install **city-manager**. In Claude Code in a terminal (2.1.275 or later):

```
/plugin install city-manager --marketplace mayorgergich/cs2-city-manager
```

Choose **for you** (your user account) if it asks, so it works in any folder. Then, **in the game first:** load your
city (or make a new one), press Ctrl+J and pick *Start a new journal for this city* (that takes the snapshot your City
Manager reads), and save. Then type `/city-manager`. The
[guide](https://github.com/mayorgergich/cs2-city-manager/blob/main/docs/guide.md) walks through all of it.

## What it reads, writes and sends

Everything stays on your computer except what you share with Claude itself:

- **It reads** the game's own files on your computer: City Manager's journal folder and the city snapshots the mod
  writes (roads, buildings, the budget and so on), the game's map files and the launcher's mod list (to help pick a
  map, check your mods and name the assets your packs add), and City Planning Draft's plans.
- **It writes** your journal (`ModsData/CityManager`), plan guides for City Planning Draft (its `Exports` folder),
  pictures, and its own notes about your city in its data folder (`%LOCALAPPDATA%\CityManager` or
  `~/.local/share/city-manager`).
- **It sends nothing anywhere by itself:** the scripts make no network calls and start no other programs. When you use
  Claude, what it reads goes to Anthropic under your own Claude account, like any Claude Code chat. `uv` downloads
  Python and its picture library the first time.
- **No hooks, servers or agents:** just the skill and its scripts.

The full report: [SECURITY.md](https://github.com/mayorgergich/cs2-city-manager/blob/main/SECURITY.md).

## Heads up

This is made with AI. I do have minor coding experience, but Claude wrote the code, working closely with me, and no
experienced programmer has reviewed it yet. It's a hobby project, so results may vary! Questions and ideas:
[Discord](https://discord.gg/Rtea83Gnb9) or [GitHub](https://github.com/mayorgergich/cs2-city-manager/issues).
