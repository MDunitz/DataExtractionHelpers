"""Offline (no-network) tests for the registry, cache resolver, cache-name
selection, and the values->DataFrame round-trip."""

import os

import pandas as pd
import pytest

from labdata import register_sheet, resolve_sheet, get_latest_filename
from labdata import sheets


def test_registry():
    register_sheet("pressure_data", "SPREAD123", gid=42)
    assert resolve_sheet("pressure_data") == ("SPREAD123", 42)
    with pytest.raises(KeyError):
        resolve_sheet("nope")


def test_resolve_cache_dir_precedence(monkeypatch):
    monkeypatch.delenv("LABDATA_CACHE_DIR", raising=False)
    assert sheets._resolve_cache_dir("/explicit") == "/explicit"
    monkeypatch.setenv("LABDATA_CACHE_DIR", "/from/env")
    assert sheets._resolve_cache_dir() == "/from/env"
    assert sheets._resolve_cache_dir("/explicit") == "/explicit"  # arg wins


def test_get_latest_filename_matches_name_and_id_and_picks_newest(tmp_path):
    # cache-name scheme: name___epoch___id.csv
    (tmp_path / "pressure___100___SP1.csv").write_text("")
    (tmp_path / "pressure___300___SP1.csv").write_text("")   # newest for SP1
    (tmp_path / "pressure___999___SP2.csv").write_text("")   # different id
    (tmp_path / "batch___500___SP1.csv").write_text("")      # different name
    got = get_latest_filename("SP1", "pressure", cache_dir=str(tmp_path))
    assert got == "pressure___300___SP1.csv"


def test_get_latest_filename_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_latest_filename("SPX", "nothing", cache_dir=str(tmp_path))


def test_values_to_df_applies_kwargs():
    rows = [["ts", "raw"], ["2026-06-01T00:00:00Z", "240000"], ["", "12345"]]
    df = sheets._values_to_df(rows, parse_dates=["ts"])
    assert pd.api.types.is_datetime64_any_dtype(df["ts"])
    assert df["raw"].tolist() == [240000, 12345]


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["pytest", "-q", __file__]))
