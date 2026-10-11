import pandas as pd

from chipcycle.micron import korea_by_quarter, quarters_from_facts


def fact(start, end, val, form="10-Q", filed="2024-01-01"):
    return {"start": start, "end": end, "val": val, "form": form, "filed": filed}


def test_q4_is_derived_from_annual_minus_three_quarters():
    facts = [
        fact("2022-09-02", "2022-12-01", 100),
        fact("2022-12-02", "2023-03-02", 110),
        fact("2023-03-03", "2023-06-01", 120),
        fact("2022-09-02", "2023-08-31", 460, form="10-K"),
    ]
    q = quarters_from_facts(facts)
    assert q["revenue"].tolist() == [100, 110, 120, 130]
    assert q["end"].iloc[-1] == pd.Timestamp("2023-08-31")


def test_restatement_uses_latest_filing():
    facts = [
        fact("2022-09-02", "2022-12-01", 100, filed="2023-01-01"),
        fact("2022-09-02", "2022-12-01", 105, filed="2023-04-01"),
    ]
    assert quarters_from_facts(facts)["revenue"].tolist() == [105]


def test_korea_months_match_micron_quarter():
    monthly = pd.Series(1.0, index=pd.date_range("2022-01-31", "2023-12-31", freq="ME"))
    monthly.loc["2022-12-31"] = 10
    q = pd.DataFrame({"start": [pd.Timestamp("2022-12-02")], "end": [pd.Timestamp("2023-03-02")], "revenue": [1]})
    # Dec, Jan, Feb.
    assert korea_by_quarter(monthly, q).iloc[0] == 12
