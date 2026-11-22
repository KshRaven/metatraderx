from __future__ import annotations

import pytest

from metatraderx import cli, config, discovery, uninstall as un
from metatraderx.errors import SetupError


@pytest.fixture
def term(monkeypatch, tmp_path):
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(un, "IS_WIN", False)
    monkeypatch.setattr(un, "IS_LINUX", True)
    pre = tmp_path / "pre"
    folder = pre / "drive_c" / "Program Files" / "Broker MetaTrader 5"
    folder.mkdir(parents=True)
    exe = folder / "terminal64.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(un.discovery, "prefix_of", lambda p: pre)
    monkeypatch.setattr(un.wineenv, "kill_server", lambda p: None)
    monkeypatch.setattr(un, "_running", lambda e: False)
    return pre, folder, exe


def test_plan_accepts_any_broker_folder(term):
    pre, folder, exe = term
    assert un.plan(folder).folder == folder
    assert un.plan(exe).exe == exe


def test_plan_refuses_broad_folders(term, tmp_path):
    pre, folder, exe = term
    with pytest.raises(SetupError):
        un.plan(pre / "drive_c" / "Program Files" / "x")
    (pre / "drive_c" / "Program Files" / "terminal64.exe").write_bytes(b"x")
    with pytest.raises(SetupError):
        un.plan(pre / "drive_c" / "Program Files" / "terminal64.exe")


def test_dry_run_removes_nothing(term):
    pre, folder, exe = term
    assert folder in un.uninstall(exe, dry_run=True)
    assert exe.exists()


def test_uninstall_removes_folder_and_clears_selection(term):
    pre, folder, exe = term
    config.save({"terminal": str(exe), "version": 5})
    assert folder in un.uninstall(exe, yes=True)
    assert not folder.exists() and pre.exists()
    assert "terminal" not in config.load()


def test_uninstall_prefix(term):
    pre, folder, exe = term
    un.uninstall(exe, yes=True, prefix=True)
    assert not pre.exists()


def test_uninstall_cancelled(term, monkeypatch):
    pre, folder, exe = term
    monkeypatch.setattr(un, "ask", lambda *a, **k: False)
    with pytest.raises(SetupError):
        un.uninstall(exe)
    assert exe.exists()


def test_running_needs_stop(term, monkeypatch):
    pre, folder, exe = term
    monkeypatch.setattr(un, "_running", lambda e: True)
    with pytest.raises(SetupError):
        un.uninstall(exe, yes=True)
    assert un.uninstall(exe, yes=True, stop=True)


def test_cli_uninstall_by_number(term, monkeypatch, capsys):
    pre, folder, exe = term
    monkeypatch.setattr(discovery, "find_terminals", lambda *a, **k: [{"path": str(exe), "prefix": str(pre)}])
    assert cli.main(["uninstall", "0", "--dry-run"]) == 0
    assert "would remove" in capsys.readouterr().out
    assert cli.main(["uninstall", "5", "-y"]) != 0
    assert cli.main(["uninstall", "0", "-y"]) == 0
    assert not folder.exists()
