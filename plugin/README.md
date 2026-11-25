# City Manager plugin for Claude Code

The City Manager for Cities: Skylines II: you build the city, and between play sessions Claude plans it with you and
keeps track. It writes a briefing before you play and a report after, keeps your projects, answers your notes, and draws
plans over your city through the City Planning Draft mod. While you play, no AI runs: the City Manager mod shows your
journal in the game.

**Install** (Claude Code 2.1.275 or later):

```
/plugin install city-manager --marketplace mayorgergich/cs2-city-manager
```

Choose **for you (user scope)** when it asks, so it works in any folder. Then type `/city-manager:city-manager set up my city`
(or `/city-manager:city-manager found a new city` for a city that doesn't exist yet). It needs the City Manager mod in the game and
[uv](https://docs.astral.sh/uv/) to run its scripts. How to use it day to day:
[the guide](https://github.com/mayorgergich/cs2-city-manager/blob/main/docs/guide.md).

Everything else, including what it touches and what it sends where: the repo's
[README](https://github.com/mayorgergich/cs2-city-manager) and
[security report](https://github.com/mayorgergich/cs2-city-manager/blob/main/SECURITY.md).
