"""Remove MetaTrader terminals, official or from any broker: install folder, shortcuts, optionally data and the Wine prefix."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import config, discovery, wineenv
from .config import IS_LINUX, IS_WIN
from .errors import SetupError
from .installer import ask

__all__ = ["Plan", "plan", "uninstall"]

_PROTECTED = {"program files", "program files (x86)", "windows", "users", "drive_c", "applications", "opt", "usr", "home"}


@dataclass
class Plan:
    """What uninstalling a terminal removes."""

    exe: Path
    """The terminal executable."""
    folder: Path
    """Install folder (the .app bundle on macOS)."""
    prefix: Path | None
    """Wine prefix holding the terminal, or None."""
    uninstaller: Path | None
    """uninstall.exe in the install folder, or None."""
    shortcuts: list[Path] = field(default_factory=list)
    """Start menu, desktop and menu entries of the terminal."""
    data: list[Path] = field(default_factory=list)
    """Data folders of the terminal outside its install folder (only filled with data=True)."""
    remove_prefix: bool = False
    """True when the whole Wine prefix is removed."""

    def paths(self) -> list[Path]:
        """Everything that will be deleted, in order."""
        if self.remove_prefix and self.prefix:
            return [self.prefix]
        return [*self.shortcuts, *self.data, self.folder]


def _bundle(exe: Path) -> Path | None:
    return next((p for p in exe.parents if p.suffix.lower() == ".app"), None)


def _check_folder(folder: Path) -> None:
    home = Path.home().resolve()
    if folder.resolve() in (home, Path(folder.anchor)) or folder.name.lower() in _PROTECTED or len(folder.resolve().parts) < 3:
        raise SetupError(f"refusing to remove {folder}: it is not a terminal folder")


def _shortcut_dirs(prefix: Path | None) -> list[Path]:
    dirs: list[Path] = []
    if IS_WIN:
        for var in ("APPDATA", "ProgramData"):
            if os.environ.get(var):
                dirs.append(Path(os.environ[var]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
        if os.environ.get("USERPROFILE"):
            dirs.append(Path(os.environ["USERPROFILE"]) / "Desktop")
        if os.environ.get("PUBLIC"):
            dirs.append(Path(os.environ["PUBLIC"]) / "Desktop")
    else:
        dirs.append(Path.home() / ".local" / "share" / "applications" / "wine" / "Programs")
        dirs.append(Path.home() / "Desktop")
        if prefix:
            for u in (prefix / "drive_c" / "users").glob("*"):
                dirs += [u / "Start Menu" / "Programs", u / "Desktop"]
            dirs.append(prefix / "drive_c" / "ProgramData" / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return dirs


def _shortcuts(folder: Path, prefix: Path | None) -> list[Path]:
    name = folder.stem if folder.suffix.lower() == ".app" else folder.name
    out: list[Path] = []
    for d in _shortcut_dirs(prefix):
        try:
            out += [p for p in d.glob(f"{name}*") if p.name.lower().startswith(name.lower())]
        except OSError:
            continue
    return out


def _data_dirs(folder: Path, prefix: Path | None) -> list[Path]:
    """Terminal/<id> data folders whose origin.txt points to the install folder."""
    if prefix is None:
        base = os.environ.get("APPDATA")
        bases = [Path(base) / "MetaQuotes" / "Terminal"] if base else []
    else:
        bases = [u / sub / "MetaQuotes" / "Terminal" for u in (prefix / "drive_c" / "users").glob("*") for sub in ("AppData/Roaming", "Application Data")]
    out: list[Path] = []
    for b in bases:
        for f in b.glob("*/origin.txt"):
            d = discovery._host_path(discovery._read_text(f), prefix)
            if d is not None and str(d).rstrip("/\\").lower() == str(folder).rstrip("/\\").lower():
                out.append(f.parent)
    return out


def _resolve(terminal: str | os.PathLike | None) -> Path:
    t = terminal or config.setting("terminal")
    if not t:
        raise SetupError("no terminal given and none selected; see `mtx terminal list`")
    p = Path(str(t)).expanduser()
    if p.is_dir():
        exe = discovery._exe_in(p)
        if exe is None:
            bundle = p if p.suffix.lower() == ".app" else None
            if bundle is not None:
                return bundle
            raise SetupError(f"no terminal executable found in {p}")
        return exe
    if not p.exists():
        raise SetupError(f"{p} does not exist")
    return p


def plan(terminal: str | os.PathLike | None = None, data: bool = False, prefix: bool = False) -> Plan:
    """Work out what removing a terminal deletes, without deleting anything.

    Args:
        terminal: The terminal executable or its install folder; any broker's terminal works. The selected terminal when omitted.
        data: Also include the terminal's data folders kept outside its install folder (MQL files, history, logs).
        prefix: Wine (Linux, macOS): remove the whole Wine prefix the terminal lives in instead of only the terminal.

    Raises:
        SetupError: Nothing was found at the path, or the folder looks too broad to remove safely.
    """
    exe = _resolve(terminal)
    bundle = exe if exe.suffix.lower() == ".app" else _bundle(exe)
    folder = bundle or exe.parent
    _check_folder(folder)
    pre = None if IS_WIN else discovery.prefix_of(exe)
    if prefix and (IS_WIN or pre is None):
        raise SetupError("the terminal is not inside a Wine prefix")
    if prefix and pre is not None and (pre.resolve() == Path.home().resolve() or not (pre / "drive_c").is_dir()):
        raise SetupError(f"refusing to remove {pre}: it is not a Wine prefix")
    un = folder / "uninstall.exe"
    return Plan(
        exe=exe,
        folder=folder,
        prefix=pre,
        uninstaller=un if IS_WIN and un.is_file() else None,
        shortcuts=_shortcuts(folder, pre),
        data=_data_dirs(folder, pre) if data else [],
        remove_prefix=prefix,
    )


def _running(exe: Path) -> bool:
    name = exe.name.lower()
    try:
        if IS_WIN:
            out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe.name}"], capture_output=True, text=True, timeout=30).stdout
            return name in out.lower()
        if IS_LINUX:
            for c in Path("/proc").glob("[0-9]*/cmdline"):
                try:
                    if name in c.read_bytes().decode("utf-8", "ignore").lower():
                        return True
                except OSError:
                    continue
            return False
        return subprocess.run(["pgrep", "-fi", name], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _stop(p: Plan) -> None:
    if IS_WIN:
        subprocess.call(["taskkill", "/F", "/IM", p.exe.name])
    elif p.prefix:
        wineenv.kill_server(p.prefix)
    else:
        subprocess.call(["pkill", "-fi", p.exe.name])


def _rm(path: Path) -> None:
    def fix(func, p, _exc):  # read-only files (common in Wine prefixes)
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        func(p)

    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path, onerror=fix)


def uninstall(
    terminal: str | os.PathLike | None = None,
    yes: bool = False,
    data: bool = False,
    prefix: bool = False,
    stop: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Uninstall a MetaTrader 4 or 5 terminal, including a broker's own build, and return what was removed.

    The install folder and the terminal's shortcuts are removed. On Windows the terminal's own uninstall.exe runs
    first when it has one, so the Windows uninstall entry goes away too. The data folder (MQL files, history) is kept
    unless data is true, and a Wine prefix is kept unless prefix is true. Nothing is deleted without confirmation
    unless yes is true.

    Args:
        terminal: Terminal executable or install folder. The selected terminal when omitted.
        yes: Do not ask for confirmation.
        data: Also remove the terminal's data folders outside its install folder.
        prefix: Wine (Linux, macOS): remove the whole prefix.
        stop: Close the terminal if it is running instead of failing.
        dry_run: Only list what would be removed.

    Raises:
        SetupError: The terminal was not found, is running (without stop), or removal was refused.
    """
    p = plan(terminal, data, prefix)
    todo = p.paths()
    if dry_run:
        return todo
    print("This permanently removes:\n  " + "\n  ".join(map(str, todo)))
    if p.uninstaller:
        print(f"and runs {p.uninstaller} first")
    if prefix and p.prefix:
        others = [t["path"] for t in discovery.find_terminals() if t["prefix"] == str(p.prefix) and Path(t["path"]) != p.exe]
        if others:
            print("The prefix also holds:\n  " + "\n  ".join(others))
    if not ask("Continue?", yes, False):
        raise SetupError("cancelled; nothing was removed")
    if _running(p.exe):
        if not stop:
            raise SetupError(f"{p.exe.name} is running; close it or use --stop")
        _stop(p)
    if p.uninstaller and not prefix:
        subprocess.call([str(p.uninstaller)], cwd=str(p.folder))
    removed: list[Path] = []
    for path in todo:
        if path.exists() or path.is_symlink():
            _rm(path)
            removed.append(path)
    cfg = config.load()
    if cfg.get("terminal") and Path(str(cfg["terminal"])) == p.exe:
        for k in ("terminal", "version"):
            cfg.pop(k, None)
        config.save(cfg)
    discovery._version_cache.pop(str(p.exe), None)
    return removed
