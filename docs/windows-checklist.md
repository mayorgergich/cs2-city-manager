# Windows checklist

The in-game checks a tester runs by hand on Windows before each release. The automatic in-game suite only runs on
Linux (a hidden test display under Proton), and GitHub's machines can't run the game. It takes about 30 minutes. Tick
each box, and send back the filled-in list, `Logs\CityManager.log`, `Player.log` and screenshots of anything odd.

The game's user-data folder below is `%USERPROFILE%\AppData\LocalLow\Colossal Order\Cities Skylines II` (paste it into
File Explorer's address bar).

## Setup

- [ ] The game is closed. Unzip `CityManager-<version>.zip` (from `python build.py zip`) into the user-data folder's
      `Mods` folder, so that `Mods\CityManager\CityManager.dll` exists.
- [ ] In the Paradox Launcher, City Planning Draft is in your playset (for the build-overlay checks).
- [ ] For the sample journal: install uv (`winget install astral-sh.uv`), then, from a copy of the repo:
      `uv run plugin\skills\city-manager\scripts\journal.py build docs\sample-journal`. It writes
      `ModsData\CityManager\riverton\`. Without uv, skip the checks marked *(sample)*.

## In game

- [ ] **Start:** the game loads normally. `Logs\CityManager.log` says `City Manager <version> … loading` and
      `Toggle key registered: ToggleJournal, bound True`, with no errors.
- [ ] **Open and close:** Ctrl+J opens and closes the panel; so does the cones button at the top left.
- [ ] **A city with no journal:** load or start a city. The panel says no journal is linked; *Start a new journal for
      this city* makes one, and `ModsData\CityManager\<city>\journal.json` appears.
- [ ] **Notes:** write a note with accents and an emoji (`Café über alles 🏙`), tick *Pin to where the camera is looking*,
      press *Add*. It shows in the list; *Go* flies the camera back; deleting takes two clicks.
- [ ] **Wrap-up:** type an answer, close the panel mid-sentence with Ctrl+J, reopen: the answer is still there. *Done
      for today* marks it done.
- [ ] **Typing doesn't drive the game:** while a text box has focus, letters don't trigger the game's own shortcuts.
- [ ] **Rename the city** (click its name at the bottom): the same journal stays open.
- [ ] **Sample journal** *(sample)*: name a city "Riverton" (or pick *riverton* with *Change journal*). Today shows the
      sample briefing; ticking a box sticks after closing and reopening; *Projects → Main street* shows its picture,
      which opens large on a click.
- [ ] **Live update** *(sample)*: with the game running, edit `docs\sample-journal\briefing.md` (change the summary)
      and build it again. Within a second or two the panel shows the change and the cones button gets an orange dot.
- [ ] **A second city in one session:** go back to the main menu and load a different city. It must not open the first
      city's journal (it starts unlinked, or opens its own).

## Windows file handling

- [ ] **A file held open:** open `ModsData\CityManager\<city>\mayor.json` in Notepad and leave it open. In game, tick a
      box and add a note. Both save (no "Not saved" message), and `mayor.json.bak` exists.
- [ ] **Antivirus:** with Windows Security's real-time protection on (the normal case), the checks above pass. If
      *Controlled folder access* is on, say whether saving still works.
- [ ] **Your user name:** if it has letters beyond A–Z (é, ü, ø…), say so: everything above should still work.
      Either way, `Logs\CityManager.log` must not show `C:\Users\<your name>`; paths show as `CityManager\…`.

## The plugin's scripts (optional, with uv)

- [ ] `uv run plugin\skills\city-manager\scripts\journal.py where` lists Windows folders (`…\AppData\LocalLow\…` for
      the journals, `%LOCALAPPDATA%\CityManager` for the City Manager's data) and no errors.
- [ ] `uv run plugin\skills\city-manager\scripts\cityplan.py mapid` names the planner's city after you have opened City
      Planning Draft once in it.

## Remove it

- [ ] Close the game, delete `Mods\CityManager`, and start the game: it loads normally. Your journals stay in
      `ModsData\CityManager`.
