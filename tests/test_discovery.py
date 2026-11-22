from __future__ import annotations

import os
import sys

import pytest

from metatraderx import discovery as D


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    D._version_cache.clear()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "mtx"))
    for k in ("WINEPREFIX", "MTX_WINEPREFIX", "MTX_SEARCH"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "home").mkdir()
    monkeypatch.setattr(D, "IS_WIN", False)
    monkeypatch.setattr(D, "IS_MAC", False)
    monkeypatch.setattr(D, "IS_LINUX", True)
    return tmp_path


def make_prefix(root):
    (root / "drive_c").mkdir(parents=True)
    return root


def test_terminal_version_by_folder(tmp_path):
    a = tmp_path / "a"
    (a / "MQL5").mkdir(parents=True)
    (a / "terminal64.exe").write_bytes(b"")
    assert D.terminal_version(a / "terminal64.exe") == 5
    b = tmp_path / "b"
    (b / "MQL4").mkdir(parents=True)
    (b / "x.exe").write_bytes(b"")
    assert D.terminal_version(b / "x.exe") == 4


def test_terminal_version_by_bytes_and_names(tmp_path):
    c = tmp_path / "c"
    c.mkdir()
    f = c / "broker.exe"
    f.write_bytes(b"xx MetaTrader 4 yy MetaTrader 4 MetaTrader 5")
    assert D.terminal_version(f) == 4
    g = c / "w.exe"
    g.write_bytes("MetaTrader 5".encode("utf-16-le"))
    assert D.terminal_version(g) == 5
    h = tmp_path / "h"
    h.mkdir()
    (h / "terminal64.exe").write_bytes(b"")
    assert D.terminal_version(h / "terminal64.exe") == 5
    i = tmp_path / "i"
    i.mkdir()
    (i / "terminal.exe").write_bytes(b"")
    assert D.terminal_version(i / "terminal.exe") == 4
    j = tmp_path / "j"
    j.mkdir()
    (j / "metaeditor.exe").write_bytes(b"")
    (j / "custom.exe").write_bytes(b"")
    assert D.terminal_version(j / "custom.exe") == 4
    k = tmp_path / "k"
    k.mkdir()
    (k / "unknown.exe").write_bytes(b"nothing")
    assert D.terminal_version(k / "unknown.exe") is None
    assert D.terminal_version(tmp_path / "ghost" / "z.exe") is None


def test_scan_bytes_unreadable(tmp_path):
    assert D._scan_bytes(tmp_path / "nope") is None


def test_exe_in(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    assert D._exe_in(d) is None
    (d / "terminal64.exe").write_bytes(b"1")
    assert D._exe_in(d).name == "terminal64.exe"
    e = tmp_path / "e"
    e.mkdir()
    (e / "metaeditor64.exe").write_bytes(b"1")
    assert D._exe_in(e) is None
    (e / "broker.exe").write_bytes(b"12345")
    (e / "unins000.exe").write_bytes(b"1234567890")
    (e / "big.exe").write_bytes(b"123456")
    assert D._exe_in(e).name == "big.exe"
    assert D._exe_in(tmp_path / "missing") is None


def test_walk_skips_and_depth(tmp_path):
    tmp_path = tmp_path / "w"
    for n in ("a/b/c", "windows/x", ".hidden/y", "python3/z", "$x/y"):
        (tmp_path / n).mkdir(parents=True)
    seen: set = set()
    names = {p.name for p in D._walk(tmp_path, 1, seen)}
    assert names == {tmp_path.name, "a"}
    assert list(D._walk(tmp_path, -1, set())) == []
    assert list(D._walk(tmp_path, 3, seen)) == []
    names = {p.name for p in D._walk(tmp_path, 3, set())}
    assert {"a", "b", "c"} <= names and not names & {"windows", ".hidden", "python3", "$x"}


def test_wine_prefixes(tmp_path, monkeypatch):
    home = tmp_path / "home"
    make_prefix(home / ".wine")
    make_prefix(home / ".mt5")
    make_prefix(home / ".wine-other")
    make_prefix(home / ".local" / "share" / "wineprefixes" / "p1")
    make_prefix(tmp_path / "mtx" / "prefix5")
    make_prefix(tmp_path / "custom")
    monkeypatch.setenv("WINEPREFIX", str(tmp_path / "custom"))
    found = {p.name for p in D.wine_prefixes()}
    assert {".wine", ".mt5", ".wine-other", "p1", "prefix5", "custom"} <= found
    assert len(D.wine_prefixes()) == len(set(D.wine_prefixes()))


def test_wine_prefixes_mac(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "IS_MAC", True)
    make_prefix(tmp_path / "home" / "Library" / "Application Support" / "net.metaquotes.wine.metatrader5")
    assert any("metaquotes" in p.name for p in D.wine_prefixes())


def test_prefix_of_direct_and_mapped(tmp_path):
    pre = make_prefix(tmp_path / "home" / ".wine")
    exe = pre / "drive_c" / "Program Files" / "MT5" / "terminal64.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert D.prefix_of(exe) == pre
    other = tmp_path / "elsewhere" / "terminal64.exe"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"")
    assert D.prefix_of(other) is None
    try:
        (pre / "dosdevices").mkdir()
        (pre / "dosdevices" / "d:").symlink_to(tmp_path / "elsewhere")
    except OSError:
        pytest.skip("symlinks unavailable")
    assert D.prefix_of(other) == pre
    assert tmp_path / "elsewhere" in D._wine_drives(pre)


def test_wine_drives_skips_c_z_and_root(tmp_path):
    pre = make_prefix(tmp_path / "p")
    dev = pre / "dosdevices"
    dev.mkdir()
    try:
        (dev / "c:").symlink_to(pre / "drive_c")
        (dev / "z:").symlink_to("/")
        (dev / "e:").symlink_to("/")
        (dev / "f:").symlink_to(tmp_path / "gone")
        (dev / "g:").symlink_to(tmp_path)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert D._wine_drives(pre) == [pre / "drive_c", tmp_path]


def test_host_path(tmp_path):
    pre = make_prefix(tmp_path / "p")
    assert D._host_path("x", pre) is None
    assert D._host_path("C:\\Apps\\MT5", None).as_posix().endswith("MT5")
    assert D._host_path("C:\\Apps\\MT5", pre) == pre / "drive_c" / "Apps" / "MT5"
    assert D._host_path("D:\\Apps", pre) is None
    if os.name == "nt":
        return
    (pre / "dosdevices" / "d:").mkdir(parents=True)
    assert D._host_path("D:\\Apps", pre) == pre / "dosdevices" / "d:" / "Apps"


def test_read_text(tmp_path):
    f = tmp_path / "o.txt"
    f.write_bytes("C:\\Apps\\MT5".encode("utf-16"))
    assert D._read_text(f) == "C:\\Apps\\MT5"
    f.write_bytes(b"\xef\xbb\xbfC:\\X")
    assert D._read_text(f) == "C:\\X"
    assert D._read_text(tmp_path / "none") == ""
    f.write_bytes(b"\xff\xfe\x00\x01\x02")
    assert D._read_text(f) == ""


def test_origin_dirs_in_prefix(tmp_path):
    pre = make_prefix(tmp_path / "p")
    inst = pre / "drive_c" / "Apps" / "MT5"
    inst.mkdir(parents=True)
    od = pre / "drive_c" / "users" / "u" / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "ABC"
    od.mkdir(parents=True)
    (od / "origin.txt").write_bytes("C:\\Apps\\MT5".encode("utf-16"))
    assert D._origin_dirs(pre) == [inst]
    assert D._origin_dirs(make_prefix(tmp_path / "empty")) == []


def test_origin_dirs_windows_appdata(tmp_path, monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    assert D._origin_dirs(None) == []
    monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
    od = tmp_path / "ad" / "MetaQuotes" / "Terminal" / "X"
    od.mkdir(parents=True)
    (od / "origin.txt").write_bytes("D:\\gone".encode("utf-16"))
    assert D._origin_dirs(None) == []


def test_find_terminals_in_prefix_and_search(tmp_path, monkeypatch):
    pre = make_prefix(tmp_path / "home" / ".wine")
    t5 = pre / "drive_c" / "Program Files" / "MetaTrader 5"
    (t5 / "MQL5").mkdir(parents=True)
    (t5 / "terminal64.exe").write_bytes(b"1")
    t4 = pre / "drive_c" / "Program Files" / "Broker MT4"
    (t4 / "MQL4").mkdir(parents=True)
    (t4 / "terminal.exe").write_bytes(b"1")
    extra = tmp_path / "custom" / "Acme"
    (extra / "MQL5").mkdir(parents=True)
    (extra / "terminal64.exe").write_bytes(b"1")
    monkeypatch.setenv("MTX_SEARCH", str(tmp_path / "custom"))
    found = D.find_terminals()
    paths = [t["path"] for t in found]
    assert str(t5 / "terminal64.exe") in paths and str(t4 / "terminal.exe") in paths and str(extra / "terminal64.exe") in paths
    assert [t["version"] for t in found][:3] == [5, 5, 4]
    t = next(x for x in found if x["path"] == str(t5 / "terminal64.exe"))
    assert t["prefix"] == str(pre) and t["name"] == "MetaTrader 5"
    assert D.find_terminals(max_depth=0) is not None


def test_find_terminals_via_origin(tmp_path):
    pre = make_prefix(tmp_path / "home" / ".wine")
    inst = pre / "drive_c" / "Deep" / "a" / "b" / "c" / "d" / "e" / "MT5"
    (inst / "MQL5").mkdir(parents=True)
    (inst / "terminal64.exe").write_bytes(b"1")
    od = pre / "drive_c" / "users" / "u" / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "H"
    od.mkdir(parents=True)
    (od / "origin.txt").write_bytes("C:\\Deep\\a\\b\\c\\d\\e\\MT5".encode("utf-16"))
    assert any(t["path"] == str(inst / "terminal64.exe") for t in D.find_terminals())


def test_roots_by_platform(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_SEARCH", str(tmp_path / "s"))
    roots = [r[0] for r in D._roots()]
    assert tmp_path / "s" in roots and D.Path("/opt") in roots
    monkeypatch.setattr(D, "IS_MAC", True)
    monkeypatch.setattr(D, "IS_LINUX", False)
    assert D.Path("/Applications") in [r[0] for r in D._roots()]
    monkeypatch.setattr(D, "IS_WIN", True)
    monkeypatch.setenv("SystemDrive", "C:")
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "la"))
    monkeypatch.setattr(D, "_drives", lambda: [D.Path("C:\\"), D.Path("D:\\")] if sys.platform == "win32" else [tmp_path / "d1"])
    roots = D._roots()
    assert any(r[0] == tmp_path / "pf" for r in roots)
    assert any(r[0] == tmp_path / "home" / "Desktop" for r in roots)


def test_drives_non_windows():
    assert isinstance(D._drives(), list)


def test_terminal_exe_is_mt4_even_when_text_mentions_mt5(tmp_path):
    d = tmp_path / "MetaTrader 4"
    d.mkdir()
    f = d / "terminal.exe"
    f.write_bytes(b"MetaTrader 5 MetaTrader 5 MetaTrader 4")
    assert D.terminal_version(f) == 4
