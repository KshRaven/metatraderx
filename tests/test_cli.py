from __future__ import annotations

from metatraderx.cli import build_parser


def test_parser():
    p = build_parser()
    a = p.parse_args(["fetch", "rates", "EURUSD", "--tf", "M15", "-o", "x.csv"])
    assert a.kind == "rates" and a.tf == "M15" and a.out == "x.csv"
    assert p.parse_args(["serve", "--auth", "auto"]).token_value == "auto"
    assert p.parse_args(["install", "4"]).version == 4


def test_relative_dates():
    from metatraderx.cli import _join_relative

    assert _join_relative(["fetch", "deals", "--from", "-30d", "-o", "x"]) == ["fetch", "deals", "--from=-30d", "-o", "x"]
    assert build_parser().parse_args(_join_relative(["fetch", "deals", "--from", "-30d"])).start == "-30d"


def test_symbols_and_cache_args():
    p = build_parser()
    a = p.parse_args(["symbols", "--first", "5"])
    assert a.first == 5 and not a.full
    assert p.parse_args(["symbols", "--last", "3", "--full"]).full
    assert p.parse_args(["cache", "clear", "-y"]).yes
