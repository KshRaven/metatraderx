"""Locate MetaTrader terminals (official and broker-branded) and work out their version."""

from __future__ import annotations

import os
from pathlib import Path

from . import config
from .config import IS_LINUX, IS_MAC, IS_WIN

__all__ = ["find_terminals", "terminal_version", "prefix_of", "wine_prefixes"]

_SKIP_DIRS = {
    "windows", "programdata", "common files", "internet explorer", "windowsapps", "python", "windows nt", "$recycle.bin",
    "system volume information", "recovery", "node_modules", "site-packages", "appdata", "proc", "sys", "dev", "run",
}  # fmt: skip
_SKIP_EXE = ("metaeditor", "uninstall", "unins", "setup", "mtx", "crashpad", "update")
_version_cache: dict = {}


def prefix_of(path: str | os.PathLike) -> Path | None:
    """Wine prefix (the directory holding drive_c) that contains the given file, if any."""
    target = Path(path).resolve()
    for p in target.parents:
        if (p / "drive_c").is_dir():
            return p
    for pre in wine_prefixes():
        for d in _wine_drives(pre):
            if d == target or d in target.parents:
                return pre
    return None


def wine_prefixes() -> list[Path]:
    """Wine prefixes (folders holding drive_c) found in the usual places and in MTX_WINEPREFIX / the saved setting."""
    home = Path.home()
    found: list[Path] = []
    cand = [os.environ.get("WINEPREFIX"), config.setting("wineprefix"), home / ".wine", home / ".mt5", home / ".mt4"]
    cand += list(home.glob(".wine*")) + list((home / ".local" / "share" / "wineprefixes").glob("*"))
    cand += list(config.home().glob("prefix*"))
    if IS_MAC:
        cand += list((home / "Library" / "Application Support").glob("*metaquotes*"))
        cand += list((home / "Library" / "Application Support").glob("*MetaTrader*"))
        cand += list((home / "Library" / "Containers").glob("*/Data/.wine"))
    for c in cand:
        if c and (Path(c) / "drive_c").is_dir() and Path(c) not in found:
            found.append(Path(c))
    return found


def _scan_bytes(path: Path) -> int | None:
    pats = {5: [b"MetaTrader 5", "MetaTrader 5".encode("utf-16-le")], 4: [b"MetaTrader 4", "MetaTrader 4".encode("utf-16-le")]}
    hits = {4: 0, 5: 0}
    tail = b""
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(4 << 20)
                if not chunk:
                    break
                data = tail + chunk
                for v, ps in pats.items():
                    hits[v] += sum(data.count(p) for p in ps)
                tail = data[-48:]
    except OSError:
        return None
    if hits[5] == hits[4]:
        return None
    return 5 if hits[5] > hits[4] else 4


def terminal_version(path: str | os.PathLike) -> int | None:
    """5 for MetaTrader 5, 4 for MetaTrader 4, None when it cannot be told."""
    p = Path(path)
    key = str(p)
    if key in _version_cache:
        return _version_cache[key]
    d = p.parent
    names = {x.name.lower() for x in d.iterdir()} if d.is_dir() else set()
    v: int | None = None
    if "mql5" in names:
        v = 5
    elif "mql4" in names:
        v = 4
    elif p.name.lower() == "terminal.exe":
        v = 4
    if v is None and p.is_file():
        v = _scan_bytes(p)
    if v is None:
        if any(n.startswith("metaeditor64") for n in names) or p.name.lower() == "terminal64.exe":
            v = 5
        elif "metaeditor.exe" in names or p.name.lower() == "terminal.exe":
            v = 4
    _version_cache[key] = v
    return v


def _exe_in(d: Path) -> Path | None:
    try:
        files = [x for x in d.iterdir() if x.is_file() and x.suffix.lower() == ".exe"]
    except OSError:
        return None
    by = {x.name.lower(): x for x in files}
    for n in ("terminal64.exe", "terminal.exe"):
        if n in by:
            return by[n]
    if any(n.startswith("metaeditor") for n in by):
        rest = [x for x in files if not any(s in x.name.lower() for s in _SKIP_EXE)]
        if rest:
            return max(rest, key=lambda x: x.stat().st_size)
    return None


def _walk(root: Path, depth: int, seen: set):
    if depth < 0:
        return
    try:
        key = str(root.resolve()).lower()
    except OSError:
        return
    if key in seen:
        return
    seen.add(key)
    yield root
    try:
        subs = [x for x in root.iterdir() if x.is_dir() and not x.is_symlink()]
    except OSError:
        return
    for s in subs:
        n = s.name.lower()
        if n in _SKIP_DIRS or n.startswith(("python", ".", "$")):
            continue
        yield from _walk(s, depth - 1, seen)


def _drives() -> list[Path]:
    """Every fixed or removable drive on Windows (C:, D:, ...)."""
    import string

    found: list[Path] = []
    try:
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
        for i, letter in enumerate(string.ascii_uppercase):
            root = f"{letter}:\\"
            if mask >> i & 1 and ctypes.windll.kernel32.GetDriveTypeW(root) in (2, 3):  # type: ignore[attr-defined]
                found.append(Path(root))
    except (AttributeError, OSError):
        found = [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
    return found


def _wine_drives(prefix: Path) -> list[Path]:
    """Folders behind the drive letters of a Wine prefix (C: is drive_c, D: and others are links in dosdevices)."""
    out = [prefix / "drive_c"]
    dev = prefix / "dosdevices"
    try:
        links = sorted(dev.iterdir()) if dev.is_dir() else []
    except OSError:
        links = []
    for ln in links:
        name = ln.name.lower()
        if len(name) == 2 and name[1] == ":" and name[0] not in "cz":
            try:
                tgt = ln.resolve()
            except OSError:
                continue
            if tgt.is_dir() and str(tgt) not in ("/", str(Path.home())):
                out.append(tgt)
    return out


def _host_path(win: str, prefix: Path | None) -> Path | None:
    """A path as stored by the terminal (D:\\Apps\\MT5) as a path this system can open."""
    if len(win) < 3 or win[1] != ":":
        return None
    rest = win[2:].replace("\\", "/").strip("/")
    if prefix is None:
        return Path(win)
    letter = win[0].lower()
    if letter == "c":
        base = prefix / "drive_c"
    else:
        base = Path(str(prefix / "dosdevices") + os.sep + f"{letter}:")
    return base / rest if base.exists() else None


def _read_text(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    for enc in ("utf-16", "utf-8-sig"):
        try:
            txt = raw.decode(enc).strip().strip("\x00")
        except UnicodeError:
            continue
        if txt and txt.isprintable():
            return txt
    return ""


def _origin_dirs(prefix: Path | None) -> list[Path]:
    """Install folders the terminals record in their data folders (Terminal/<id>/origin.txt)."""
    if prefix is None:
        base = os.environ.get("APPDATA")
        bases = [Path(base) / "MetaQuotes" / "Terminal"] if base else []
    else:
        users = prefix / "drive_c" / "users"
        try:
            bases = [u / sub / "MetaQuotes" / "Terminal" for u in users.iterdir() for sub in ("AppData/Roaming", "Application Data")]
        except OSError:
            bases = []
    out: list[Path] = []
    for b in bases:
        try:
            files = list(b.glob("*/origin.txt"))
        except OSError:
            continue
        for f in files:
            d = _host_path(_read_text(f), prefix)
            if d is not None and d.is_dir():
                out.append(d)
    return out


def _roots() -> list[tuple[Path, Path | None, int]]:
    """(folder, wine prefix, search depth) for every place a terminal may live."""
    roots: list[tuple[Path, Path | None, int]] = []
    extra = config.setting("search")
    for e in extra.split(os.pathsep) if extra else []:
        if e:
            roots.append((Path(e), prefix_of(e), 5))
    if IS_WIN:
        system = (os.environ.get("SystemDrive") or "C:").upper()
        for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "APPDATA"):
            if os.environ.get(var):
                roots.append((Path(os.environ[var]), None, 3))
        if os.environ.get("USERPROFILE"):
            for sub in ("Desktop", "Downloads", "Documents"):
                roots.append((Path(os.environ["USERPROFILE"]) / sub, None, 3))
        for d in _drives():
            on_system = d.drive.upper() == system
            roots.append((d, None, 2 if on_system else 4))
            if not on_system:
                for sub in ("Program Files", "Program Files (x86)"):
                    roots.append((d / sub, None, 3))
    else:
        for pre in wine_prefixes():
            for d in _wine_drives(pre):
                roots.append((d, pre, 3 if d.name == "drive_c" else 4))
        if IS_MAC:
            roots += [(Path("/Applications"), None, 3), (Path.home() / "Applications", None, 3)]
        if IS_LINUX:
            roots += [(Path("/opt"), None, 3), (Path.home() / ".local" / "share", None, 2)]
    return roots


def _entry(exe: Path, d: Path, pre: Path | None) -> dict:
    return {"path": str(exe), "version": terminal_version(exe), "prefix": str(pre or prefix_of(exe) or "") or None, "name": d.name}


def find_terminals(max_depth: int | None = None) -> list[dict]:
    """Every terminal executable found on every drive: dicts with path, version, prefix and folder name.

    Windows searches all fixed and removable drives; Linux and macOS search each Wine prefix with all of its mapped
    drives. Terminals recorded in the MetaQuotes data folders are found wherever they are installed. Extra folders
    can be given with MTX_SEARCH (separated by ; on Windows, : elsewhere). max_depth caps the folder depth searched.
    """
    out: dict[str, dict] = {}
    seen: set = set()
    prefixes: list[Path | None] = [None] if IS_WIN else list(wine_prefixes())
    for pre in prefixes:
        for d in _origin_dirs(pre):
            exe = _exe_in(d)
            if exe is not None and str(exe) not in out:
                out[str(exe)] = _entry(exe, d, pre)
    for root, pre, depth in _roots():
        if not root.is_dir():
            continue
        for d in _walk(root, depth if max_depth is None else min(depth, max_depth), seen):
            exe = _exe_in(d)
            if exe is not None and str(exe) not in out:
                out[str(exe)] = _entry(exe, d, pre)
    return sorted(out.values(), key=lambda t: (t["version"] or 0, t["path"]), reverse=True)
