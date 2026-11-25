#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Everything the report needs from the city, in one go: the numbers against the last report (a table, and the
report's [[numbers]] entries), what was built, changed and removed, how far the plan has got (built, partly, not yet,
built differently), a fresh map and a picture of the plan's progress in the journal's images folder, and the open road
ends the next plan can start from. Run it beside `journal.py mayor` (the Mayor's side: ticks, notes, the wrap-up); the
two together are the report's facts. It only reads the city, and writes nothing but the two pictures.

usage:
  report.py <src> [--before kept|start|FILE] [--plan PLAN.json] [--images DIR] [--date YYYY-MM-DD]
      The debrief's facts: the Mayor's side (`journal.py mayor` and what's still open) and the city's side.
  report.py <src> --draft [--before …] [--plan …]
      The same, and writes reports/<date>.md as a draft: the numbers, what got built (by street, against the cards), the
      pictures, a [[replies]] entry for every note still unanswered and the wrap-up's answers, with TODO: where the
      City Manager's own words go. `journal.py build` refuses a page with a TODO: left in it.
  report.py <src> --prep [--plan PLAN.json]
      The briefing's facts: what the Mayor added since the last report, what's still open, whether the city was played
      since, the plan checked against the newest snapshot (locked pieces, steep grades, crossings), and whether the
      city's newest guide is the one the planner's Import will load.

<src> is the city's journal source folder (<city>/journal), as for city.py; a snapshot file works too, with --images.
Defaults: --before kept (the copy the last report kept; the session start when there's none), --plan
<city>/manager/plan/plan.json when it's there, --images <src>/images, --date the snapshot's own date.
After writing the report: `city.py keep <src>`, so the next report compares with this one.
"""
import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import city  # noqa: E402
import cityplan  # noqa: E402
import journal  # noqa: E402
import plan  # noqa: E402
import survey as sv  # noqa: E402
from city import arr, obj  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")


def captured(fn, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = fn(*args)
    return code, out.getvalue().strip()


def strip_heading(text):
    """A command's output without its own first heading line."""
    lines = text.splitlines()
    return "\n".join(lines[1:]).strip() if lines and lines[0].startswith("# ") else text


def mayor_side(src):
    """The Mayor's side of the journal: what they did since the last acknowledgement, and what's still open."""
    print("## The Mayor's side\n")
    _, mine = captured(journal.cmd_mayor, src)
    print(strip_heading(mine) + "\n")
    _, still = captured(journal.cmd_open, src)
    print("### Still open\n")
    print(strip_heading(still) + "\n")


def guide_status(city_name):
    """Whether this city's newest guide is the newest file in the planner's Exports (Import loads the newest, whichever
    city it's for)."""
    import json
    exports = Path(cityplan.ROOT) / "Exports"
    files = sorted(exports.glob("*.cityplan.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:12] if exports.is_dir() else []
    if not files:
        return "No guides in City Planning Draft's Exports folder yet."

    def map_of(f):
        try:
            return str(json.loads(f.read_text(encoding="utf-8-sig")).get("map_id") or "")
        except (OSError, ValueError, AttributeError):
            return ""
    stem = lambda f: f.name[: -len(".cityplan.json")]
    want = city_name.casefold()
    mine = [f for f in files if stem(f).casefold().startswith(want + " ") or map_of(f).casefold() == want]
    newest = files[0]
    if not mine:
        return f"No guide for {city_name} among the newest exports (the newest is {stem(newest)})."
    if mine[0] == newest:
        return f"{stem(newest)} is the newest guide: the planner's Import latest file loads it."
    return (f"The newest export is {stem(newest)}, not {city_name}'s: before the Mayor plays, run "
            f"`cityplan.py front \"{stem(mine[0])}\"`.")


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    src = args[0]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else default

    srcp = Path(src).expanduser()
    is_source = srcp.is_dir() and (srcp / "journal.toml").exists()
    before = opt("--before", "kept")
    plan_path = opt("--plan")
    if plan_path is None and is_source and (srcp.parent / "manager/plan/plan.json").exists():
        plan_path = str(srcp.parent / "manager/plan/plan.json")
    images = Path(opt("--images")) if opt("--images") else (srcp / "images" if is_source else None)

    now_path = city.snapshot_path(src)
    snap = city.load(now_path)
    then_path = city.before_path(src, before, snap)
    date = opt("--date") or city.local_time(snap.get("taken"))[:10]
    name = obj(snap.get("city")).get("name") or "?"
    if "--prep" in args:
        return prep(src, is_source, snap, now_path, then_path, plan_path, name)
    print(f"# Report facts: {name}\n")
    print(f"Now: {now_path.name}, taken {city.local_time(snap.get('taken'))}; before: {then_path.name}. After the report is "
          "written: `city.py keep`.\n")
    if is_source:
        mayor_side(src)

    # the numbers, as a table and as the report's entries
    _, table = captured(city.cmd_numbers, src, before, False)
    print("## The numbers\n")
    print(strip_heading(table) + "\n")
    _, toml = captured(city.cmd_numbers, src, before, True)
    print("For the report's front matter (keep the five to seven that matter):\n")
    print("```toml\n" + toml.strip() + "\n```\n")

    # what changed
    code, changes = captured(city.cmd_changes, src, before)
    built_results = None
    print("## What changed\n")
    print(strip_heading(changes) + "\n")

    # the plan, built so far
    built_md = None
    plans = []
    if plan_path and Path(plan_path).exists() and arr(snap.get("edges")):
        plans = plan.load_plans(plan_path)
        results = plan.Built(snap).run(plans)
        built_results = results
        built_md = plan.built_markdown(results, now_path, snap)
        print("## The plan, built so far\n")
        print(f"From {Path(plan_path).name}.\n")
        print(strip_heading(built_md).split("\n", 1)[-1].strip() + "\n")
    elif plan_path:
        print("## The plan\n\nNo plan file to check, or a snapshot without roads.\n")

    # pictures
    pictures = []
    if images is not None:
        try:
            facts = sv.survey(snap)
        except ValueError:
            facts = None
        if facts is None:
            print("## Pictures\n\nThe snapshot has no terrain part, so there are no pictures.\n")
        else:
            images.mkdir(parents=True, exist_ok=True)
            then = None
            if then_path.exists() and then_path.resolve() != now_path.resolve():
                then = city.load(then_path)
                if (then.get("taken") or "") == (snap.get("taken") or ""):
                    then = None
            label = (obj(obj(then.get("city")).get("date")).get("text") or city.local_time(then.get("taken"))) if then else ""
            map_file = images / f"map-{date}.png"
            res = plan.draw_city_map(snap, map_file, then, since_label=label, facts=facts)
            pictures.append((map_file.name, f"{name} on {obj(obj(snap.get('city')).get('date')).get('text') or date}",
                             f"the city now; {res['new']} new pieces of road and track since {label} in blue, "
                             f"{res['placed']} buildings placed" if then else "the city now (nothing to compare with)"))
            if plans:
                built_file = images / f"built-{date}.png"
                plan.draw_built(snap, plans, plan.Built(snap).run(plans), built_file, facts=facts)
                pictures.append((built_file.name, "The plan, built so far", "each plan item coloured by how far it's built"))
            print("## Pictures (in the journal's images folder)\n")
            for file, caption, what in pictures:
                print(f"- `![{caption}]({file})`: {what}")
            print()

    # where the next plan can start
    ends = city.road_ends(snap)
    print(f"## Open road ends: {len(ends)}\n")
    if ends:
        print("Where a road stops without joining another: where the next streets can start. The place is for plan files.\n")
        print("| Street | End | Points | Piece | Place (x, z) |\n|---|---|---|---|---|")
        for r in ends[:30]:
            print(f"| {r['street'] or '(unnamed)'} | {r['end'] or '-'} | {r['heading'] or '-'} | {r['piece']} | {r['x']}, {r['z']} |")
        if len(ends) > 30:
            print(f"\n… and {len(ends) - 30} more: `city.py ends`.")
    if "--draft" in args:
        if not is_source:
            print("\n--draft needs the city's journal source folder (<city>/journal).")
            return 1
        then = city.load(then_path) if then_path.exists() and then_path.resolve() != now_path.resolve() else None
        write_draft(src, date, then, snap, changes, built_results, pictures)
    return 0


def toml_str(v):
    import json
    return json.dumps(str(v), ensure_ascii=False)


def write_draft(src, date, then, snap, changes_md, built_results, pictures):
    """reports/<date>.md as a draft, from the facts; never over an existing report."""
    import datetime
    path = Path(src) / "reports" / f"{date}.md"
    if path.exists():
        print(f"\n{path.name} is there already: the draft wasn't written.")
        return None
    _, j, m = journal.load_both(src)
    notes = [n for n in (m.get("notes") if isinstance(m.get("notes"), list) else []) if isinstance(n, dict)
             and n.get("id") and not journal.as_dict(j.get("replies")).get(n.get("id"))]
    wraps = [(bid, journal.as_dict(d)) for bid, d in journal.as_dict(m.get("debriefs")).items()]
    try:
        day = datetime.date.fromisoformat(date[:10])
        title, shown = f"Report: {day.day} {day.strftime('%B')}", f"{day.day} {day.strftime('%b %Y')}"
    except ValueError:
        title, shown = f"Report: {date}", date
    out = ["+++", f"id = {toml_str(date)}", f"title = {toml_str(title)}", f"date = {toml_str(shown)}",
           'summary = "TODO: two or three sentences: what happened, where the city stands, and the one thing that matters next."', "",
           "# The numbers: keep the five to seven that matter, delete the rest."]
    for r in city.number_rows(then, snap) if then else []:
        out += ["[[numbers]]"] + [f"{k} = {toml_str(r[k])}" for k in ("label", "before", "after", "change")] + [""]
    for n in notes:
        out += ["[[replies]]", f"note = {toml_str(n['id'])}", f"text = {toml_str('TODO: the answer to: ' + str(n.get('text', ''))[:200])}", ""]
    out += ["+++", "## What got built", ""]
    built_lines = [ln for ln in changes_md.splitlines() if ln.startswith("- ")]
    out += built_lines or ["Nothing new on the roads."]
    if built_results:
        done = [it["name"] for r in built_results for it in r["items"] if it["status"] == "built"]
        diff = [f"{it['name']}: {'; '.join(it.get('notes', []))}" for r in built_results for it in r["items"] if it["status"] == "different"]
        part = [f"{it['name']} ({it.get('share', 0)}%)" for r in built_results for it in r["items"] if it["status"] == "partly"]
        out.append("")
        if done:
            out.append("**Built as planned:** " + ", ".join(done) + ".")
        if part:
            out.append("**Partly built:** " + ", ".join(part) + ".")
        if diff:
            out.append("**Built differently from the card** (TODO: say whether it matters, and ask if it was on purpose):")
            out += [f"- {d}" for d in diff]
    for file, caption, _ in pictures:
        out += ["", f"![{caption}]({file})"]
    out += ["", "## What you told me", ""]
    for n in notes:
        out.append(f"- **{str(n.get('text', '')).strip()[:200]}**: TODO: the answer (also in its [[replies]] entry)")
    for bid, d in wraps:
        for k, v in journal.as_dict(d.get("answers")).items():
            if str(v).strip():
                out.append(f"- **Wrap-up, {k}:** {str(v).strip()[:300]}: TODO: the answer")
    if not notes and not wraps:
        out.append("Nothing new in the journal this time.")
    out += ["", "## What I see", "", "TODO: the problems that matter, by street, with a picture where it helps.", "",
            "## Decisions for next time", "", "TODO: at most two, as questions with options.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"\nDraft written: {path} (fill every TODO:, then `journal.py build`).")
    return path


def prep(src, is_source, snap, now_path, then_path, plan_path, name):
    print(f"# Prep facts: {name}\n")
    print(f"Newest snapshot: {now_path.name}, taken {city.local_time(snap.get('taken'))}"
          f" (in game {obj(obj(snap.get('city')).get('date')).get('text') or '?'}).\n")
    if is_source:
        mayor_side(src)
    # played since the last report?
    print("## The city since the last report\n")
    kept = city.latest_kept(src) if is_source else None
    if kept and kept[1] >= (snap.get("taken") or ""):
        print(f"Not played since the last report ({kept[0].name} is this snapshot): the briefing it wrote still fits, "
              "unless the Mayor wants changes.\n")
        then_path = now_path
    then = city.load(then_path) if then_path.exists() and then_path.resolve() != now_path.resolve() else None
    if kept and kept[1] >= (snap.get("taken") or ""):
        pass
    elif then is None:
        print("No earlier snapshot to compare with.\n")
    elif (then.get("taken") or "") >= (snap.get("taken") or ""):
        print(f"Not played since the last report ({then_path.name}): the briefing it wrote still fits, unless the Mayor "
              "wants changes.\n")
    else:
        _, table = captured(city.cmd_numbers, src, "kept", False)
        print(strip_heading(table) + "\n")
        print("The city was played since the last report: write that report first (session-loop.md).\n")
    # the plan, checked
    if plan_path and Path(plan_path).exists():
        plans = plan.load_plans(plan_path)
        try:
            chk = plan.Check(snap, plans, None)
            chk.run()
            print("## The plan, checked against the newest snapshot\n")
            print(f"From {Path(plan_path).name}: {chk.errors()} to fix before the Mayor builds.\n")
            print(strip_heading(chk.markdown(now_path.name)) + "\n")
        except ValueError:
            print("## The plan\n\nThe snapshot has no terrain part, so the plan can't be checked.\n")
    # the guide
    print("## The guide\n")
    print(guide_status(name) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
