"""Wine helpers: locate wine and Windows Python, convert paths, provide a display for headless hosts."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from . import config
from .config import IS_LINUX, IS_MAC
from .discovery import prefix_of
from .errors import SetupError

__all__ = [
    "wine_bin", "base_env", "winedebug", "to_win_path", "wine_python", "wine_pythons", "has_metatrader5", "ensure_display", "run_wine", "kill_server", "setup_problems",
]  # fmt: skip

WINEDEBUG_LEVELS = {"all": "-all", "fixme": "fixme-all", "off": ""}


def wine_bin() -> str | None:
    """Path of the wine binary (MTX_WINE, then PATH, then the macOS app bundles), or None."""
    w = config.setting("wine")
    if w and (shutil.which(str(w)) or Path(str(w)).is_file()):
        return str(w)
    for n in ("wine64", "wine"):
        p = shutil.which(n)
        if p:
            return p
    if IS_MAC:
        pats = [
            "Applications/MetaTrader*.app/Contents/SharedSupport/**/wine64",
            "Applications/MetaTrader*.app/Contents/SharedSupport/**/wine",
            "Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine",
            "opt/homebrew/bin/wine64",
            "usr/local/bin/wine64",
        ]
        for pat in pats:
            for h in sorted(Path("/").glob(pat)):
                if h.is_file():
                    return str(h)
    return None


def winedebug() -> str:
    """The WINEDEBUG value to use: MTX_WINEDEBUG or the saved setting, then WINEDEBUG, else -all (silent).

    The named levels are all (-all, no output), fixme (fixme-all, errors still shown) and off (Wine's own defaults);
    any other value is passed to Wine unchanged.
    """
    v = config.setting("winedebug")
    if v is None:
        v = os.environ.get("WINEDEBUG")
    if v is None:
        return "-all"
    v = str(v).strip()
    return WINEDEBUG_LEVELS.get(v.lower(), v)


def base_env(prefix: str | os.PathLike | None = None) -> dict:
    """A copy of the environment with WINEPREFIX set and Wine debug output set by winedebug()."""
    env = os.environ.copy()
    env["WINEDEBUG"] = winedebug()
    if prefix:
        env["WINEPREFIX"] = str(prefix)
    return env


def to_win_path(wine: str, env: dict, path: str | os.PathLike) -> str:
    """Convert a host path to the Windows path Wine uses for it (through winepath)."""
    r = subprocess.run([_winepath(wine), "-w", str(path)], env=env, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip().splitlines()
    if r.returncode != 0 or not out:
        raise SetupError(f"winepath failed for {path}: {r.stderr.strip()}")
    return out[-1].strip()


def _winepath(wine: str) -> str:
    sib = Path(wine).with_name("winepath")
    return str(sib) if sib.is_file() else (shutil.which("winepath") or "winepath")


_SKIP = {"windows", "lib", "scripts", "dlls", "site-packages", "common files", "include", "libs", "tcl", "doc"}


def wine_pythons(prefix: str | os.PathLike | None) -> list[Path]:
    """Every Windows python.exe in a prefix, wherever it was installed, newest folder name first.

    Looks through the top of drive_c (to three folders deep), Program Files and the per-user Programs\\Python folders.
    """
    if not prefix:
        return []
    c = Path(prefix) / "drive_c"
    found: set[Path] = set()
    for pat in ("users/*/AppData/Local/Programs/Python/*/python.exe", "Program Files*/Python*/python.exe"):
        found.update(c.glob(pat))
    base = len(c.parts)
    for root, dirs, files in os.walk(c):
        dirs[:] = [d for d in dirs if d.lower() not in _SKIP and d.lower() != "users" and not d.lower().startswith("program files")]
        if len(Path(root).parts) - base >= 3:
            dirs[:] = []
        if "python.exe" in files:
            found.add(Path(root) / "python.exe")
    return sorted((p for p in found if p.is_file()), key=lambda p: str(p.parent).lower(), reverse=True)


def has_metatrader5(python: str | os.PathLike) -> bool:
    """True when the MetaTrader5 package is installed for that python.exe."""
    return any((Path(python).parent / "Lib" / "site-packages").glob("MetaTrader5*"))


def wine_python(prefix: str | os.PathLike | None) -> Path | None:
    """python.exe of the Windows Python to use in a prefix, or None when there is none.

    MTX_WINE_PYTHON overrides. Otherwise any Python in the prefix is found; one that already has the MetaTrader5
    package is preferred.
    """
    p = config.setting("wine_python")
    if p and Path(str(p)).is_file():
        return Path(str(p))
    pys = wine_pythons(prefix)
    return next((x for x in pys if has_metatrader5(x)), pys[0] if pys else None)


def ensure_display(force: bool = False) -> tuple[dict, subprocess.Popen | None]:
    """On headless Linux start a virtual X server (Xvfb) and return the env additions plus its process.

    With force true the virtual screen is used even when a real display exists, so nothing opens on the desktop.
    """
    if not IS_LINUX or (not force and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))):
        return {}, None
    xvfb = shutil.which("Xvfb")
    if not xvfb:
        return {}, None
    n = 99
    while Path(f"/tmp/.X11-unix/X{n}").exists():
        n += 1
    proc = subprocess.Popen(
        [xvfb, f":{n}", "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if Path(f"/tmp/.X11-unix/X{n}").exists():
            break
        time.sleep(0.1)
    return {"DISPLAY": f":{n}"}, proc


def run_wine(args: list, prefix: str | os.PathLike | None, check: bool = True, headless: bool = False, stop: bool = False, **kw) -> subprocess.CompletedProcess:
    """Run wine with args in a prefix, on a temporary virtual screen when headless (or when headless is true); extra keywords go to subprocess.run.

    On a virtual screen Wine's leftover processes are waited for (or stopped when stop is true) before the screen is
    closed, so no "X connection broken" messages appear.
    """
    wine = wine_bin()
    if not wine:
        raise SetupError("wine was not found; run: mtx setup")
    env = base_env(prefix)
    extra, proc = ensure_display(headless)
    env.update(extra)
    try:
        return subprocess.run([wine, *map(str, args)], env=env, check=check, **kw)
    finally:
        if proc:
            _settle(env, wine, stop)
            proc.terminate()


def _wineserver(wine: str) -> str | None:
    sib = Path(wine).with_name("wineserver")
    return str(sib) if sib.is_file() else shutil.which("wineserver")


def _settle(env: dict, wine: str, stop: bool) -> None:
    srv = _wineserver(wine)
    if not srv:
        return
    try:
        subprocess.run([srv, "-k" if stop else "-w"], env=env, capture_output=True, timeout=60 if stop else 20, check=False)
    except (subprocess.TimeoutExpired, OSError):
        pass


def kill_server(prefix: str | os.PathLike | None) -> None:
    """Stop every process left running in a prefix (wineserver -k)."""
    wine = wine_bin()
    if not wine:
        return
    srv = _wineserver(wine)
    if srv:
        subprocess.run([srv, "-k"], env=base_env(prefix), capture_output=True, timeout=60, check=False)


def setup_problems(terminal: str | os.PathLike | None = None, prefix: str | os.PathLike | None = None, python: bool = True) -> list[str]:
    """What is missing for the Wine backend of Linux and macOS; empty on Windows or when everything is in place.

    Wine is always checked. With python true the Wine prefix of the terminal and the Windows Python inside it are
    checked as well (MetaTrader 4 does not need them, so pass python=False there).
    """
    if config.IS_WIN:
        return []
    found: list[str] = []
    if not wine_bin():
        found.append("Wine is not installed")
    if not python:
        return found
    pre = Path(prefix) if prefix else (prefix_of(terminal) if terminal else None)
    if pre is None:
        found.append("the terminal is not inside a Wine prefix")
    elif not wine_python(pre):
        found.append(f"Windows Python with the MetaTrader5 package is not installed in {pre}")
    return found
