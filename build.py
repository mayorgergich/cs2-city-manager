#!/usr/bin/env python3
"""Builds, tests and installs the City Manager mod, on Windows and Linux.

  python build.py                       build into dist/CityManager
  python build.py test                  run every offline test (no game needed: the C# tests then take Json.NET from NuGet)
  python build.py check                 run every offline test, then build
  python build.py zip                   build, then pack dist/CityManager-<version>.zip (for a tester)
  python build.py --install             build, then install into the game's own Mods folder (game closed)
  python build.py --install-to <Mods>   build, then install into another Mods folder (a test profile)
  python build.py --uninstall           remove it from the game's Mods folder (game closed)

The game is found through Steam (its default folder and the libraries in libraryfolders.vdf), or set CS2_GAME_DIR.
The game's user-data folder (Mods, ModsData) comes from CS2_USERDATA, else Windows' own place, else Steam's Proton
prefix on Linux. Needs Python 3.11+, the .NET SDK and Node.js.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "0.9.3"
DIST = ROOT / "dist/CityManager"
CSPROJ = ROOT / "mod/src/CityManager/CityManager.csproj"
PANEL = ROOT / "mod/ui/CityManager.mjs"
WINDOWS = os.name == "nt"

sys.path.insert(0, str(ROOT / "plugin/skills/city-manager/scripts"))
from journal import LOCALLOW  # noqa: E402  the game's user-data folder, found the same way as the plugin finds it

for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOTNET_CLI_TELEMETRY_OPTOUT", "1")
os.environ.setdefault("DOTNET_NOLOGO", "1")


def steam_roots():
    if not WINDOWS:
        return [Path.home() / ".local/share/Steam", Path.home() / ".steam/steam"]
    roots = []
    try:   # where Steam says it is installed
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            roots.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
    except OSError:
        pass
    return roots + [Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam"]


def game_dir():
    """The game's install folder, or None."""
    if os.environ.get("CS2_GAME_DIR"):
        return Path(os.environ["CS2_GAME_DIR"])
    libraries = []
    for steam in steam_roots():
        libraries.append(steam)
        vdf = steam / "steamapps/libraryfolders.vdf"
        if vdf.exists():
            libraries += [Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace"))]
    for lib in libraries:
        game = lib / "steamapps/common/Cities Skylines II"
        if (game / "Cities2_Data/Managed/Game.dll").exists():
            return game
    return None


def game_running():
    """The player's own game is running (hidden test games in ~/.local/share/*-test profiles don't count)."""
    if WINDOWS:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Cities2.exe", "/NH"], capture_output=True, text=True).stdout
        return "Cities2.exe" in out
    pids = subprocess.run(["pgrep", "-x", "Cities2.exe"], capture_output=True, text=True).stdout.split()
    for pid in pids:
        try:
            env = Path(f"/proc/{pid}/environ").read_bytes().decode(errors="replace")
        except OSError:
            continue
        if not re.search(r"/\.local/share/[a-z]+-test/compatdata", env):
            return True
    return False


def run_suite(name, cmd):
    """Runs one test suite; prints its summary line, or its last lines when it fails. True when it passed."""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    out = r.stdout + r.stderr
    if r.returncode == 0:
        summary = [ln for ln in out.splitlines() if re.match(r"(Passed!|ℹ pass|Ran \d+ tests)", ln.strip())]
        print(f"   {name}: ok ({summary[-1].strip() if summary else 'passed'})")
        return True
    print(f"   {name}: FAILED")
    # Each failing test with its details (node: "not ok", unittest: FAIL/ERROR, dotnet: "Failed "), then the summary.
    lines = out.splitlines()
    keep = set(range(max(0, len(lines) - 15), len(lines)))
    for i, ln in enumerate(lines):
        if re.match(r"\s*(not ok \d|✖ |FAIL:|ERROR:|Failed )", ln):
            keep.update(range(max(0, i - 1), min(len(lines), i + 30)))
    print("\n".join(lines[i] for i in sorted(keep)))
    return False


def test():
    print("== Offline tests")
    game = game_dir()
    dotnet = ["dotnet", "test", str(ROOT / "mod/tests/CityManager.Tests"), "-nologo"] + ([f"-p:GamePath={game}"] if game else [])
    suites = [
        ("mod store", dotnet),
        ("panel", ["node", "--test", str(ROOT / "mod/tests/ui.test.mjs")]),
        ("plugin scripts", [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "plugin/tests"), "-p", "test_*.py"]),
    ]
    if (ROOT / "owner/tests").is_dir():   # the maintainer's own tools: only in the development copy, Linux only
        if WINDOWS:
            print("   owner tools: skipped (Linux only)")
        else:
            suites.append(("owner tools", [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "owner/tests"), "-p", "test_*.py"]))
    results = [run_suite(name, cmd) for name, cmd in suites]
    if not all(results):
        sys.exit("Offline tests failed")


def commit():
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    if head.returncode:
        return "uncommitted"
    dirty = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD"]).returncode
    return head.stdout.strip() + ("+changes" if dirty else "")


def build():
    game = game_dir()
    if not game:
        sys.exit("Cities: Skylines II not found through Steam; set CS2_GAME_DIR to the game's folder.")
    stamp = commit()
    shutil.rmtree(ROOT / "bin", ignore_errors=True)
    r = subprocess.run(["dotnet", "build", str(CSPROJ), "-c", "Release", "-nologo", "-v", "q", f"-p:GamePath={game}",
                        f"-p:Version={VERSION}", f"-p:InformationalVersion={VERSION}+{stamp}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    issues = sorted({ln.replace(str(ROOT) + os.sep, "") for ln in r.stdout.splitlines() if re.search(r" (error|warning) ", ln)})
    if issues:
        print("\n".join(issues))
    if r.returncode:
        sys.exit("C# build failed")
    if subprocess.run(["node", "--check", str(PANEL)]).returncode:   # the panel is hand-written: check its syntax
        sys.exit("The panel has a syntax error")
    shutil.rmtree(DIST, ignore_errors=True)
    (DIST / "images").mkdir(parents=True)
    shutil.copy2(ROOT / "bin/CityManager.dll", DIST)
    panel = re.sub(r"^ \* Version: .*$", f" * Version: {VERSION}", PANEL.read_text(encoding="utf-8"), count=1, flags=re.M)
    (DIST / "CityManager.mjs").write_text(panel, encoding="utf-8", newline="\n")
    home = str(Path.home())
    for f in (DIST / "CityManager.dll", DIST / "CityManager.mjs"):   # a shipped file must not carry the builder's home folder
        data = f.read_bytes()
        if home.encode() in data or home.encode("utf-16-le") in data:
            sys.exit(f"{f.name} contains a home-folder path; refusing to ship it.")
    for img in (ROOT / "mod/ui/images").iterdir():
        shutil.copy2(img, DIST / "images")
    (DIST / "BUILD.txt").write_text(f"City Manager {VERSION} (build {stamp})\n", encoding="utf-8")
    print(f"== Built {DIST} ({VERSION}+{stamp})")


def install_to(mods, own_game=False):
    if own_game and game_running():
        sys.exit("Cities: Skylines II is running; close it first.")
    mods.mkdir(parents=True, exist_ok=True)
    dest, new, old = mods / "CityManager", mods / "CityManager.new", mods / "CityManager.old"
    for d in (new, old):
        shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(DIST, new)
    if dest.exists():
        dest.rename(old)
    new.rename(dest)
    shutil.rmtree(old, ignore_errors=True)
    print(f"== Installed to {dest}")
    legacy = mods / "CityJournal"   # the mod's name before 0.5: two copies would both load
    if legacy.exists():
        shutil.rmtree(legacy)
        print(f"== Removed the old CityJournal mod from {mods}")


def main(argv):
    args = argv[1:]
    own_mods = LOCALLOW / "Mods"
    if args == ["test"]:
        test()
    elif args == ["check"]:
        test()
        build()
    elif args in ([], ["zip"]):
        build()
        if args:
            print("== Packed", shutil.make_archive(str(ROOT / f"dist/CityManager-{VERSION}"), "zip", DIST.parent, "CityManager"))
    elif args == ["--install"]:
        build()
        install_to(own_mods, own_game=True)
    elif len(args) == 2 and args[0] == "--install-to":
        build()
        install_to(Path(args[1]))
    elif args == ["--uninstall"]:
        if game_running():
            sys.exit("Cities: Skylines II is running; close it first.")
        for name in ("CityManager", "CityJournal"):
            shutil.rmtree(own_mods / name, ignore_errors=True)
        print(f"== Removed City Manager from {own_mods}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
