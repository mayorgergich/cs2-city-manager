# The session loop in detail

Paths below use `<city>` for the city's folder (from `journal.py where`) and `jp` for
`uv run <this skill's folder>/scripts/journal.py` (or `python3 -I` with it, see SKILL.md).

## Briefing (before the Mayor plays)

1. **Read the state.**
   - Run `jp mayor <city>/journal` (anything since the last report: notes the Mayor wrote after a report, an unfinished wrap-up) and `jp open <city>/journal`.
   - Skim the dossier's watch list.
   - If no report followed the last session (the Mayor played since the last report: the journal shows activity after it, or the facts tool sees a newer save), write that report first: a briefing built on stale facts sends the Mayor after the wrong things.
2. **Choose the list: 3 to 7 tasks, sized to the time.**
   - **Order:** things to do before launching (a launcher change, which save to load) first, then the quick or free win, then the next concrete step of the top-priority project, then decisions (two at most).
   - **The time the Mayor has** ("an hour", "keep it short"): pick what fits, give rough minutes per task and mark them as rough. Zero decisions is fine. Put the rest under a "Not tonight" heading in the body, so it's visibly kept, not dropped.
   - Each task belongs to a project (`project = "<id>"`) unless it's general.
   - Phrase each task as something done in game: "Take the traffic lights off Depot Avenue at Cooper, Lindbergh, Goldenrod and Dale Streets", not "Fix traffic".
   - **Check the facts behind a task** against the latest facts about the city you have (`city.py summary` and `problems`, a facts tool's output, the Mayor's pinned notes, screenshots): street names, which junction is which, the order along a road. A simple rule the Mayor can follow on screen ("going south, every other junction") beats a list of names. Say when something is unchecked.
   - **Building recommendations:** say what a build would knock down when you can check it; otherwise say it's unchecked. Suggest a manual save before a big build.
   - **Build cards:** every task that builds something names the exact pieces and carries a close-up picture, with the same number and words as its plan item (`guides.md`). Re-read street names from the newest snapshot first (`city.py streets`, `city.py street <name>`): the game renames streets when roads are rebuilt. Take the pieces' names from `city.py catalogue`: the game's own menu names, only what the Mayor has unlocked, and what the next milestone brings.
   - **The guide:** point at the newest guide, `<City> <N>`; the task reads "In the planner, Import latest file (<City> <N>)". Keep its plans' statuses in step with the briefing: what tonight's tasks build is **Now**. If that changes, export the guide again (`references/guides.md`). `journal.py build` warns about any page or task that names an older or moved guide, or a plan the guide doesn't have; fix every warning.
3. **Archive and write.**
   - **Revise the current briefing in place, without archiving it, when it hasn't been played:** the Mayor has ticked nothing on it and hasn't played since. That's the usual case, because the report writes the next briefing. Keep its task ids so nothing the Mayor ticks gets lost.
   - **After a session:** run `jp archive <city>/journal` (it moves `briefing.md` to `briefings/<id>.md`), then write the new `briefing.md` with the format in `journal-format.md`.
   - **Ids:** use the date the Mayor will play (`2026-11-24`). A second session on the same date gets `2026-11-24-2`. Archive refuses a duplicate, because the Mayor's ticks are stored by briefing id.
   - The summary is two sentences: where the city stands, and the one thing that matters most tonight.
   - In the body, keep the "Before you launch" steps:
     - close Claude;
     - which save to load;
     - any launcher change, such as a mod to switch off.
4. **Update the projects** that the briefing touches: steps, logs, statuses.
5. **Publish and hand over.** Run `jp build <city>/journal`. Tell the Mayor in a few lines what's on tonight's list, then remind them to close Claude before launching.

## Report (after the Mayor plays)

1. **Make sure the game is closed** and that the Mayor saved. Autosaves count, but a manual save is clearer.
2. **Gather the facts.**
   - `jp mayor <city>/journal` lists everything the Mayor did in the journal: ticks, statuses, notes (with pinned places) and the wrap-up answers. `jp open` lists what's still open.
   - **The city snapshot** (City Manager mod 0.6 or later): the mod writes `city.json` when the Mayor presses *Done for
     today* and whenever the game saves, and `city-start.json` when the city loads. Read it with `city.py` (run like
     `journal.py`):
     - `city.py summary <city>/journal`: people, money, the budget, demand, jobs, happiness, power, problems, transit,
       and what changed this session; check its "Taken" time is after the Mayor's play (if not, they didn't save);
     - `city.py changes <city>/journal`: what was built, upgraded and removed this session, by street (or since the last
       report: `--before` the copy you kept in step 8);
     - `city.py problems` (warning icons by kind and street), `city.py services` (budgets; schools, clinics and pumps by
       how full they are), `city.py streets` / `city.py street <name>`.
   - If the city has a facts tool (`[tools] facts` in `manager/manager.toml`), run it too. Such a tool reads the city: population, money and the in-game date against the last report, the budget lines, often a fresh overview map for `<city>/journal/images/`. Follow what it prints, including its warnings:
     - **no save after the Mayor's session:** report from the journal, mark every claim as not checked (`after = "no save yet"` in `[[numbers]]`), and make "load your newest save and check X stuck" the first task of the next briefing;
     - **the same save as last time:** say so; there's nothing new to measure.
   - Without a snapshot or a facts tool, work from the journal, the Mayor's notes and screenshots, and ask for the two or three numbers that matter.
3. **Look closer where it matters.** Check what the Mayor said they built, and what the wrap-up flags, against whatever shows the city. Compare each build with its card (`guides.md`, "Build cards"): the pieces used, and any street the game renamed. Say when something is a guess.
4. **Write `reports/<date>.md`** (format in `journal-format.md`):
   - a summary of two or three sentences;
   - `[[numbers]]` from the facts;
   - **What got built** (by whom);
   - **What you told me** (answer every note and wrap-up answer; each note also gets a `[[replies]]` entry so the answer shows under it in game);
   - **What I see** (problems found, with pictures where they help);
   - **Decisions for next time**.
5. **Refresh `city.md`:**
   - the facts table (population, money, the worst problem);
   - the summary line;
   - "What works" and the big problems;
   - the street-name table, if names changed;
   - the map, if a new one was drawn.
6. **Update the projects:**
   - tick steps the evidence proves done (`done = true`);
   - add a `[[log]]` line for anything that happened;
   - change statuses;
   - add new projects the Mayor started.

   Where the Mayor's tick and the evidence disagree, keep the Mayor's tick visible and explain it in a log line. Overrule it only with `force = true` on that step for one build (SKILL.md §8), never silently.
7. **Write the next briefing** (§ Briefing, steps 2 to 4), and the next guide if plans changed status. Run `jp archive` first. The Today tab's "Still open from…" shows the last briefing's unticked tasks:
   - a task you carry into the new list gets `from = "<old briefing id>/<task id>"`, so it shows once, in the new list;
   - a task the Mayor answered without ticking (a decision settled in the wrap-up) gets `done = true` and a `note` saying how it was settled, in the archived briefing's file;
   - anything else stays visible under "Still open from…" until it's done or carried.
8. **Publish and acknowledge.** Run `jp build <city>/journal`, then `jp ack <city>/journal`. Keep a copy of the
   snapshot the report used as `<city>/manager/snapshots/<date>.json` (the mod replaces `city.json` every save), so the
   next report can compare with it: `city.py changes <city>/journal --before <that copy>`.
9. **Update the dossier** (plan table, watch list, places).

## Check-ins between sessions

- **"Where are we?"** Answer from `jp status` and the City page. Give a table of projects, each with its status and next step. Keep it short.
- **A new idea or goal:** make it a project (`journal-format.md`) with a one-paragraph summary, its scale, its first two or three steps, and the guide plans or docs it links to. If it needs a plan on the map (roads, a district, an interchange), design it as a guide (`guides.md`) and link it.
- **The Mayor changed course:** update the affected projects with a log line saying what changed and why. That's the project's history.
- **On hold:** a held project disappears from "On your plate" and from the steps in `jp open` (which lists only a count). Before putting one on hold, move any step that shouldn't wait (a quick fix, a safety step) into an active project, with a log line on both.

## Ids and dates

- A briefing's id is the date the Mayor will play (`2026-11-25`). A report's id is the date of the session it reports on.
- In-game lists sort by id, newest first, so always use ISO dates. The `date` field is free text for display ("Written 24 Nov, evening").
- Log lines carry the real time you wrote them.
