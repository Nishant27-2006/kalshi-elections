import json
from pathlib import Path

from eqr import loader


def test_load_snapshots_reads_jsonl(tmp_path: Path):
    p = tmp_path / "snap.jsonl"
    rows = [
        {"ts": 100, "series": "KXBTCD", "ticker": "KXBTCD-26AUG3101-T87299.99",
         "event_ticker": "KXBTCD-26AUG3101", "yes_bid_c": 40.0,
         "yes_ask_c": 42.0, "spread_c": 2.0, "oi": 10.0, "v24": 5.0},
        {"ts": 200, "series": "KXBTCD", "ticker": "KXBTCD-26AUG3101-T87299.99",
         "event_ticker": "KXBTCD-26AUG3101", "yes_bid_c": 41.0,
         "yes_ask_c": 43.0, "spread_c": 2.0, "oi": 11.0, "v24": 6.0},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    got = loader.load_snapshots(p)
    assert len(got) == 2
    assert got[0]["ts"] == 100


def test_latest_by_ticker_keeps_newest():
    rows = [
        {"ts": 100, "ticker": "A", "yes_bid_c": 1.0},
        {"ts": 200, "ticker": "A", "yes_bid_c": 9.0},
        {"ts": 150, "ticker": "B", "yes_bid_c": 3.0},
    ]
    latest = loader.latest_by_ticker(rows)
    assert latest["A"]["yes_bid_c"] == 9.0
    assert latest["B"]["yes_bid_c"] == 3.0


def test_load_snapshots_skips_malformed_lines(tmp_path: Path):
    p = tmp_path / "snap.jsonl"
    p.write_text('{"ts":1,"ticker":"A"}\nNOT JSON\n{"ts":2,"ticker":"B"}\n')
    got = loader.load_snapshots(p)
    assert [r["ticker"] for r in got] == ["A", "B"]
