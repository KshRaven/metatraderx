from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import metatraderx

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def _scripts() -> dict[str, str]:
    text = PYPROJECT.read_text(encoding="utf-8")
    block = re.search(r"\[project\.scripts\]\n(.*?)(?:\n\[|\Z)", text, re.S).group(1)
    return dict(re.findall(r'^(\w+)\s*=\s*"([^"]+)"', block, re.M))


@pytest.mark.skipif(not PYPROJECT.is_file(), reason="source tree only")
def test_both_commands_declared():
    scripts = _scripts()
    assert scripts["mtx"] == scripts["metatraderx"] == "metatraderx.cli:main"


@pytest.mark.skipif(not PYPROJECT.is_file(), reason="source tree only")
def test_package_data_and_version():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "py.typed" in text and "mql/*" in text and "*.pyi" in text
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", metatraderx.__version__)


def test_entry_point_target_exists():
    from metatraderx.cli import main

    assert callable(main)


def test_python_dash_m():
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    r = subprocess.run([sys.executable, "-m", "metatraderx", "-V"], capture_output=True, text=True, env=env, cwd=str(ROOT))
    assert r.returncode == 0
    assert metatraderx.__version__ in (r.stdout + r.stderr)


def test_installed_console_scripts():
    from importlib import metadata

    try:
        eps = {e.name: e.value for e in metadata.entry_points(group="console_scripts") if e.value.startswith("metatraderx")}
    except Exception:  # noqa: BLE001
        pytest.skip("entry points unavailable")
    if not eps:
        pytest.skip("package not installed")
    assert eps.get("mtx") == eps.get("metatraderx") == "metatraderx.cli:main"
