"""Parsing tests run against small hand-made fixtures, not real data."""

from pathlib import Path

import pandas as pd
import pytest

from chipcycle.ingest.fred import parse_fred_csv
from chipcycle.ingest.manual import load_manual

FIXTURES = Path(__file__).parent / "fixtures"


def test_fred_parses_new_header_and_drops_missing():
    s = parse_fred_csv((FIXTURES / "INDPRO_sample.csv").read_text())
    assert list(s.index) == [pd.Timestamp(d) for d in ["2024-01-01", "2024-02-01", "2024-04-01"]]
    assert s.iloc[-1] == pytest.approx(102.4)
    assert s.dtype == float


def test_fred_parses_old_header():
    s = parse_fred_csv("DATE,X\n2020-01-01,1.5\n2020-02-01,2.5\n")
    assert s.tolist() == [1.5, 2.5]


def test_manual_csv_roundtrip(tmp_path):
    (tmp_path / "x.csv").write_text("date,value\n2024-02-01,20\n2024-01-01,10\n")
    s = load_manual("x.csv", directory=tmp_path)
    assert s.tolist() == [10.0, 20.0]  # sorted


def test_manual_csv_rejects_duplicates(tmp_path):
    (tmp_path / "x.csv").write_text("date,value\n2024-01-01,1\n2024-01-01,2\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_manual("x.csv", directory=tmp_path)


def test_manual_csv_missing_file_points_to_readme(tmp_path):
    with pytest.raises(FileNotFoundError, match="README"):
        load_manual("nope.csv", directory=tmp_path)


def test_comtrade_keeps_only_national_totals():
    import json

    from chipcycle.ingest.comtrade import parse_comtrade

    df = parse_comtrade(json.loads((FIXTURES / "comtrade_sample.json").read_text()))
    # The transport-mode breakdown and the China-only row are dropped.
    assert list(df["date"]) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
    assert df["value"].tolist() == [7e9, 8e9]
    assert set(df["cmd"]) == {"8542"}


def test_comtrade_empty_response_is_empty_frame():
    from chipcycle.ingest.comtrade import parse_comtrade

    assert parse_comtrade({"data": []}).empty
