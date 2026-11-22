from __future__ import annotations
import json
import socket
import struct
from collections import namedtuple
from datetime import datetime, timezone

import numpy as np
import pytest

from metatraderx import cache, codec, config, constants as C, export, util


def test_tf_seconds():
    assert util.tf_seconds(C.TIMEFRAME_M1) == 60
    assert util.tf_seconds(C.TIMEFRAME_M15) == 900
    assert util.tf_seconds(C.TIMEFRAME_H4) == 4 * 3600
    assert util.tf_seconds(C.TIMEFRAME_D1) == 86400
    assert util.tf_seconds(C.TIMEFRAME_W1) == 7 * 86400
    assert util.tf_seconds(C.TIMEFRAME_MN1) == 30 * 86400


def test_to_frame_variants():
    assert util.to_frame(None).empty
    arr = np.array([(1700000000, 1.5)], dtype=[("time", "<i8"), ("open", "<f8")])
    df = util.to_frame(arr)
    assert str(df["time"].iloc[0].tz) == "UTC"
    P = namedtuple("P", "time price")
    assert util.to_frame([P(1700000000, 2.0)])["price"].iloc[0] == 2.0
    assert util.to_frame([{"time": 1700000000, "x": 1}])["x"].iloc[0] == 1
    t = np.array([(1700000000, 1700000000123)], dtype=[("time", "<i8"), ("time_msc", "<i8")])
    assert util.to_frame(t)["time_msc"].iloc[0].microsecond == 123000


def test_to_rows_variants():
    P = namedtuple("P", "time price time_msc")
    assert export.to_rows(None) == []
    assert export.to_rows(P(0, 1, 0))[0]["time"] == 0
    r = export.to_rows(P(1700000000, 1, 1700000000500))[0]
    assert r["time"].endswith("Z") and r["time_msc"].endswith("Z")
    assert export.to_rows(P(1700000000, 1, 1), raw_time=True)[0]["time"] == 1700000000
    assert export.to_rows({"a": 1}) == [{"a": 1}]
    assert export.to_rows(5) == [{"value": 5}]
    assert export.to_rows([1, {"a": 2}, P(0, 0, 0)])[:2] == [{"value": 1}, {"a": 2}]
    arr = np.array([(1700000000, 1.5)], dtype=[("time", "<i8"), ("open", "<f8")])
    assert export.to_rows(arr)[0]["open"] == 1.5


def test_parse_dt():
    assert export.parse_dt("now").tzinfo is not None
    delta = datetime.now(timezone.utc) - export.parse_dt("-2h")
    assert 7190 < delta.total_seconds() < 7260
    for unit, secs in (("s", 1), ("m", 60), ("d", 86400), ("w", 604800)):
        d = datetime.now(timezone.utc) - export.parse_dt(f"-3{unit}")
        assert abs(d.total_seconds() - 3 * secs) < 5
    assert export.parse_dt("2024-01-31") == datetime(2024, 1, 31, tzinfo=timezone.utc)
    assert export.parse_dt("2024-01-31T10:30Z").hour == 10
    assert export.parse_dt("2024-01-31T10:30").tzinfo is not None
    with pytest.raises(ValueError):
        export.parse_dt("garbage")


def test_parse_tf():
    assert export.parse_tf("m15") == C.TIMEFRAME_M15
    assert export.parse_tf("H1") == C.TIMEFRAME_H1
    with pytest.raises(ValueError):
        export.parse_tf("X9")


def test_write_rows_formats(tmp_path, capsys):
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    export.write_rows(rows, str(tmp_path / "o.csv"))
    assert (tmp_path / "o.csv").read_text().splitlines() == ["a,b", "1,x", "2,y"]
    export.write_rows(rows, str(tmp_path / "sub" / "o.json"))
    assert json.loads((tmp_path / "sub" / "o.json").read_text()) == rows
    export.write_rows(rows, str(tmp_path / "o.jsonl"))
    assert len((tmp_path / "o.jsonl").read_text().splitlines()) == 2
    export.write_rows(rows, str(tmp_path / "o.txt"), "csv")
    assert (tmp_path / "o.txt").read_text().startswith("a,b")
    capsys.readouterr()
    export.write_rows(rows, None)
    assert json.loads(capsys.readouterr().out) == rows
    export.write_rows([], "-", "csv")
    with pytest.raises(ValueError):
        export.write_rows(rows, None, "xml")


def test_config_home_and_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "h"))
    assert config.home(create=False) == tmp_path / "h"
    assert not (tmp_path / "h").exists()
    assert config.load() == {}
    config.save({"cache": "1", "x": 5})
    assert config.config_file().is_file()
    assert config.load()["x"] == 5
    monkeypatch.delenv("MTX_CACHE", raising=False)
    assert config.setting("cache") == "1"
    monkeypatch.setenv("MTX_CACHE", "0")
    assert config.setting("cache") == "0"
    assert config.setting("missing", "d") == "d"
    config.config_file().write_text("{bad")
    assert config.load() == {}


def test_config_home_platform_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("MTX_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(config, "IS_WIN", False)
    monkeypatch.setattr(config, "IS_MAC", False)
    assert config.home(create=False) == tmp_path / "metatraderx"
    monkeypatch.setattr(config, "IS_MAC", True)
    assert config.home(create=False).parts[-2:] == ("Application Support", "metatraderx")
    monkeypatch.setattr(config, "IS_MAC", False)
    monkeypatch.setattr(config, "IS_WIN", True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "L"))
    assert config.home(create=False) == tmp_path / "L" / "metatraderx"


@pytest.mark.parametrize(
    "v,d,out",
    [(None, True, True), (True, False, True), ("YES", False, True), ("on", False, True), ("0", True, False),
     ("off", True, False), ("", True, False), ("maybe", True, True), ("maybe", False, False)],
)
def test_env_bool(v, d, out):
    assert config.env_bool(v, d) is out


def test_codec_types():
    P = namedtuple("P", "a b")
    arr = np.arange(6, dtype="<f8").reshape(2, 3)
    st = np.array([(1, 2.5)], dtype=[("i", "<i8"), ("f", "<f8")])
    obj = {
        "n": None, "b": True, "f": 1.5, "s": "x", "l": [1, 2], "t": (1, "a"), "set": {1},
        "dt": datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc), "by": b"\x00\x01", "np": np.int64(7),
        "arr": arr, "st": st, "empty": np.empty((0,), dtype="<f8"), "rec": P(1, [2]), "kd": {1: "a", (2, 3): "b"},
    }
    out = codec.unpack(codec.pack(obj))
    assert out["n"] is None and out["t"] == (1, "a") and out["np"] == 7
    assert out["dt"] == obj["dt"] and out["by"] == b"\x00\x01" and out["set"] == [1]
    assert (out["arr"] == arr).all() and out["st"].dtype == st.dtype and out["st"]["f"][0] == 2.5
    assert out["empty"].shape == (0,)
    assert out["rec"].a == 1 and out["rec"]._fields == ("a", "b")
    assert out["kd"] == {1: "a", (2, 3): "b"}
    assert codec.unpack(codec.pack(P(1, 2)), {"P": P}).__class__ is P
    with pytest.raises(TypeError):
        codec.pack(object())


def test_codec_object_array_and_nested_dtype():
    o = np.array([1, "a"], dtype=object)
    assert codec.unpack(codec.pack(o)) == [1, "a"]
    nest = np.zeros(2, dtype=[("a", "<i4"), ("b", [("c", "<f4")])])
    assert codec.unpack(codec.pack(nest)).dtype == nest.dtype


def test_frames_roundtrip_and_limits():
    a, b = socket.socketpair()
    codec.send_frame(a, b"hello")
    assert codec.recv_frame(b) == b"hello"
    a.sendall(struct.pack("<Q", codec.MAX_FRAME + 1))
    with pytest.raises(ConnectionError):
        codec.recv_frame(b)
    a.close()
    with pytest.raises(ConnectionError):
        codec.recv_frame(b)
    b.close()


def test_cache_behaviour(tmp_path):
    k = cache.make_key("s", "m", (1,), {"b": 2, "a": 1})
    assert k == cache.make_key("s", "m", (1,), {"a": 1, "b": 2})
    assert k != cache.make_key("s2", "m", (1,), {"a": 1, "b": 2})
    c = cache.Cache(tmp_path, "t")
    assert c.get("x") is None
    c.put("x", "rates", [1, 2])
    c.put("y", "ticks", (3,))
    val, ts = c.get("x")
    assert val == [1, 2] and ts > 0
    assert c.get("x", max_age=-1) is None
    st = c.stats()
    assert st["entries"]["rates"]["count"] == 1 and st["path"].endswith("t.sqlite3")
    assert c.clear("rates") == 1
    assert c.clear() == 1
    c.close()
