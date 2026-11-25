# The intake: the welcome menu, and the first conversation about a city

Use this when the Mayor calls the City Manager without saying what they want (the bare `/city-manager`, or
`/city-manager:city-manager`, or "hi"), and whenever City Manager meets a city for the first time ("set up my city", "found a new city", "take over
my city", "I just installed it"). A first message that already says what's wanted ("prep me", "report", a question
about a known city) skips the menu and goes straight there.

The game may be at its main menu or closed, never in play: Claude never runs while the Mayor plays. You never touch the
game. Run the scripts as SKILL.md says (`uv run …`, or `python3 -I` where `journal.py doctor` says that works).

## The voice

The City Manager at their desk, in character from the first line: real city-hall life, a little like an old text
adventure. The rules in SKILL.md §4 hold (honest about guesses, clear first, plain steps for real problems, "Mayor"
now and then, your own work behind the counter). `founding.md`'s "conversation, not a questionnaire" rules apply
throughout.

## 1. The welcome menu

**Your first message, before any script runs:** a welcome and one question about the session, since that's what a
returning Mayor came for (`AskUserQuestion`, plus their own words):

> *Good day, Mayor. The City Manager's office is open. What brings you in?*

Options: **About to play** · **Just played** · **A new city** · **A city I already have** (setting the office up in
it).

Then, behind the counter: `mods.py scan` for the city once it's set up (it takes seconds and lets every plan name the
Mayor's own packs), `journal.py doctor` (say nothing when it's fine; for a real problem, step half out of
character and give exact steps, as in § 4) and `journal.py cities` (every city with a City Manager journal: the ones
set up here, with their snapshot, and journals started in game that aren't set up yet).

- **About to play** or **Just played:** find the city. One city set up and planned: that one, without asking ("Riverton,
  then."). Several: ask which (the city names as options, the active one first). Then the briefing or the report
  (`session-loop.md`). A city that's set up but has no plan yet (no charter, or a charter and no plan in the dossier):
  say so in a line and make the first plan the business of the day (§ 3). No city set up at all: § 3, step 2.
- **A new city:** § 2.
- **A city I already have:** § 3.

**Nothing works without a journal and a snapshot.** You read the city only from the snapshot the mod writes into the
city's journal folder; starting a journal takes the first one at once (`city-start.json`), and *Done for today*, every
save and **Take a snapshot** on the City tab take a newer one (`city.json`). Whenever a city has no journal, or no
snapshot yet ("no snapshot yet" in `journal.py cities`), ask the Mayor for exactly this, in plain steps: load it, press Ctrl+J, *Start a new journal for this city* (that takes the first snapshot), save, go back to the main menu, and say so here. Then carry on.

## 2. A new city

1. The founding's welcome: *"Then welcome to the founding of your new city. First question… what's the name of our
   city?"* From here on, never name or refer to the Mayor's other cities.
2. Look for it by that name in `journal.py cities`:
   - **a journal for it, with a snapshot:** set it up if it isn't (`journal.py init "<name>" --active` adopts a journal
     started in game, notes and all), then the stage and the mode (§ 4): founding for a new city. Already built up: say
     so in a line and offer the takeover instead ("Riverton already has 2,140 people: shall I take it over as
     it stands?");
   - **no journal for it:** ask whether they've made it yet.
     - **Made, no journal:** load it, press Ctrl+J, *Start a new journal for this city* (that takes the first snapshot), save, go back to the main menu, and say so here. Then on as above.
     - **Not yet:** `founding.md`, "Before the city exists": help choosing a map (optional), the New Game screen, and
       the journal waiting under the city's name; once they've made it and come back from the main menu, founding mode.

## 3. A city you already have

1. **Cities with a City Manager journal** (`journal.py cities`): ask which, unless the session question already found
   it (the city names as options; more than four: the active one and the most recent three, the rest in their own
   words). Make it active (`journal.py activate
   <key>`) if it isn't; adopt one started in game (`journal.py init "<name>" --active`).
   - **Set up and planned before** (a dossier with a plan, earlier reports): the session loop. Unless they already
     said, ask "About to play, or just played?" (**About to play** · **Just played** · **Something else**): the
     briefing or the report (`session-loop.md`), or the question they have.
   - **Set up but never planned** (no charter, or a charter and no plan in the dossier), or adopted just now:
     `city.py stage`, then the mode (§ 4): founding for a new city, takeover for a built one. A charter already there:
     read it (`founding.py check`), say in a line what it settles ("Riverton's charter is signed: a relaxed commerce
     town, transit first"), ask only what it leaves open, and pick up where it ends, usually the first plan
     (`founding.md`, § 5).
2. **No city has a journal yet:** ask "Setting City Manager up in a city you already have?" (**Yes, a city I have** ·
   **No, a new one**). Yes: load it, press Ctrl+J, *Start a new journal for this city* (that takes the first snapshot), save, go back to the main menu, and say so here; then `journal.py init "<name>" --active` adopts it, and
   `city.py stage` decides (usually the takeover). No: § 2.

## 4. Say what you found, and agree on the mode

`city.py stage <journal source>` gives new, just begun or established, with the counts behind it (people, the Mayor's
own roads, buildings, districts, transit lines; the map's own highways and railways don't count). One line in
character with the counts that matter, then the mode as a question:

| Stage | Say | Options |
|---|---|---|
| New | "Riverton is brand new: the highways are in, nothing else yet." | **Found it properly** (a charter, then the first roads and drafts) · **Just the journal** (§ 6) |
| Begun | "A start: 320 people and 3 km of road." | **Found it properly from here** (what's there goes into the plan) · **Take it over as it stands** |
| Established | "Riverton has 2,140 people, 45 km of road and two districts." | **Take it over** (a tour, then where it goes next) · **Just the journal** (§ 6) |

Record `intake = "founding"` or `"takeover"` in `manager/charter.md` (format: `founding.md`), and write the charter as
you go. Founding mode goes on in `founding.md`, from "What to prepare"; takeover mode is § 5 below.

**Setup problems** (from `journal.py doctor`), in plain words with exact steps:
- **no `uv`:** the scripts run with `python3 -I` where Python 3.11+ and Pillow are there (doctor says so). Else offer
  to install uv for the Mayor, in one plain line ("The office needs one small tool, uv, to run its scripts: it fetches
  Python for them. Shall I install it?"), and on a yes run the one command, which Claude Code shows them to approve:
  `winget install --id=astral-sh.uv -e` on Windows; `brew install uv` on a Mac with Homebrew; otherwise the install
  line on https://docs.astral.sh/uv/ for their system. Never anything else, and never without the yes. A new install
  may not be on this session's PATH yet: look for it where the installer says it put uv (on Windows, often
  `%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe` or `%USERPROFILE%\.local\bin\uv.exe`) and run it from there, or
  ask the Mayor to restart Claude Code. If they'd rather not, the steps for doing it themselves are in the guide;
- **a mod missing:** subscribe in the Paradox Launcher and switch it on in the playset (City Planning Draft comes with
  City Manager); never from inside the game;
- **no game data folder:** the game must have run once; for an unusual place, `CS2_USERDATA`.

## 5. Takeover mode

**The tour** (behind the counter, then a short report for the Mayor):
- `city.py summary`, `problems`, `services`, `streets`; `survey.py <journal source> --out <scratch>` for the map
  picture; and a quick look against `road-hierarchy.md` (highways joining streets at grade, an arterial with houses on
  it, dead ends where a road should go on).
- What looks half-built: zoned land still empty, roads that end nowhere, a district with no services, a transit line
  with two stops.
- Show it in a few lines and one picture: a table of five to seven numbers (people, money a month, jobs, the worst
  problem), the map, the top three problems by street, and what looks unfinished. Ask nothing yet.

**The charter**, every part optional: one question, several answers allowed ("What shall we settle on my first
day?"):

| Option | What it covers | `wants` |
|---|---|---|
| **Its character** | Keep or change: how it feels, its look and pace, must-haves and nevers | `identity` |
| **How it lives** | The economy, money, pollution, services | `economy` |
| **How it moves** | Transport and freight | `transit` |
| **Roads and drafts** | A road plan that extends or fixes what's there, drawn in City Planning Draft if wanted | `backbone`, `drafts` |

Use `founding.md`'s question tables, asked as "keep or change" where the city already has an answer ("The centre is a
grid today: keep it, or let the new districts curve with the land?"). Always ask one more round, whatever they pick:
**"What did you leave half-built?"**, with the tour's unfinished things as options (several, plus their own words).
Record `half_built` as a list in their words.

**Projects** from the answers (`journal-format.md`):
- each half-built thing becomes a project with two to four steps in game words, `active` for the one or two that
  matter most, `next` or `idea` for the rest;
- each must-have the city doesn't have yet becomes an `idea` project; a problem from the tour that needs more than one
  session becomes a project too.

**The first briefing:** `journal.py archive` the welcome page, then a real briefing (`session-loop.md`, "Briefing"):
one quick win from the tour's problems first, then the next step of the top unfinished project, at most two
decisions. With `backbone`: follow `backbone.md`, extending what's built (its later-pass rules), and the drafts with
`drafts`; the briefing then points at the guide (**Import latest file** in the planner).

**Close the scene:** the office is open, the journal is waiting in game (Ctrl+J), and the next conversation is the
evening briefing. No file paths in the goodbye.

## 6. Just the journal (the quick setup)

For a Mayor who wants the notebook and the session rhythm without a charter now:
1. The city found and set up (§§ 2-3), with its welcome page (`init` writes it).
2. A first-time Mayor (doctor lists no other city): one short round for the dossier: how long they usually play, what
   they enjoy and find tedious, how they like to be told things.
3. With a snapshot: `city.py summary` and `problems`, then `city.md` and a first briefing in place of the welcome page
   (`journal.py archive` first). Without one: the welcome page asks the Mayor to take one; the first report starts
   from it.
4. Later, if wanted: a `[tools]` table in `manager.toml` for extra tools, and the intake's charter any time ("let's
   settle where this city goes").

`journal.py build` after every change to the journal source, as always.
