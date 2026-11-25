# City Manager plugin for Claude Code

The City Manager for Cities: Skylines II: you build the city, and between play sessions Claude plans it with you and
keeps track. It writes a briefing before you play and a report after, keeps your projects, answers your notes, and draws
plans over your city through the City Planning Draft mod. While you play, no AI runs: the City Manager mod shows your
journal in the game.

**Install.** In the Claude desktop app (Code tab): the plugins menu (**+** next to the prompt box), **Add** → **Add
marketplace** → **Add from a repository**, paste `https://github.com/mayorgergich/cs2-city-manager`, press **Sync**, and install **city-manager**. In Claude
Code in a terminal (2.1.275 or later):

```
/plugin install city-manager --marketplace mayorgergich/cs2-city-manager
```

Choose **for you** (your user account) if it asks, so it works in any folder. Then, **required first, in the game:** make or load your
city, press Ctrl+J and *Start a new journal for this city*, press **Take a snapshot** on the journal's City tab, and save.
The City Manager reads your city from that snapshot. Then type `/city-manager:city-manager`: your City Manager asks whether you're
continuing a city or starting a new one, and takes it from there. It needs the City Manager mod in the game and
[uv](https://docs.astral.sh/uv/) to run its scripts. How to use it day to day:
[the guide](https://github.com/mayorgergich/cs2-city-manager/blob/main/docs/guide.md).

Everything else, including what it touches and what it sends where: the repo's
[README](https://github.com/mayorgergich/cs2-city-manager) and
[security report](https://github.com/mayorgergich/cs2-city-manager/blob/main/SECURITY.md).
