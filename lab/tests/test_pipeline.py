import pandas as pd
import pytest

from cafe_atlas.pipeline import clean, main, quality_checks, transform

COLUMNS = ["sale_id", "sold_at", "city", "product", "quantity", "unit_price"]


def raw(*rows, file="sales.csv"):
    """Rows as extract() returns them: everything is text, plus the name of the source file."""
    return pd.DataFrame(list(rows), columns=COLUMNS, dtype=str).assign(source_file=file)


GOOD = ("A1", "2026-10-01 08:15:00", "Rabat", "Nous-nous", "2", "14")


def test_duplicates_are_removed():
    sales, rejected = clean(raw(GOOD, GOOD, GOOD))
    assert len(sales) == 1
    assert len(rejected) == 0


@pytest.mark.parametrize("row, reason", [
    (("B1", "2026-10-01 25:61:00", "Rabat", "Msemen", "1", "8"), "invalid sold_at"),
    (("B2", "", "Rabat", "Msemen", "1", "8"), "invalid sold_at"),
    (("B3", "2026-10-01 09:00:00", "", "Msemen", "1", "8"), "missing city"),
    (("B4", "2026-10-01 09:00:00", "Fes", "Msemen", "0", "8"), "quantity <= 0"),
    (("B5", "2026-10-01 09:00:00", "Fes", "Msemen", "-2", "8"), "quantity <= 0"),
    (("B6", "2026-10-01 09:00:00", "Fes", "Msemen", "1", "8,00"), "invalid unit_price"),
])
def test_broken_rows_go_to_quarantine(row, reason):
    sales, rejected = clean(raw(GOOD, row))
    assert list(sales["sale_id"]) == ["A1"]
    assert list(rejected["reject_reason"]) == [reason]


def test_revenue_is_quantity_times_price():
    sales, _ = clean(raw(GOOD, ("A2", "2026-10-01 18:00:00", "Rabat", "Panini poulet", "3", "35")))
    daily = transform(sales)
    assert daily.loc[0, "revenue"] == 2 * 14 + 3 * 35
    assert daily.loc[0, "items"] == 5


def test_one_row_per_day_and_city():
    rows = raw(
        GOOD,
        ("A2", "2026-10-01 19:00:00", "Rabat", "Msemen", "1", "8"),
        ("A3", "2026-10-01 10:00:00", "Fes", "Msemen", "1", "8"),
        ("A4", "2026-10-02 10:00:00", "Rabat", "Msemen", "1", "8"),
    )
    sales, rejected = clean(rows)
    daily = transform(sales)
    assert len(daily) == 3
    assert quality_checks(rows, daily, rejected) == []


def test_quality_gate_fails_when_a_file_is_too_broken():
    good_file = raw(*[(f"A{i}", "2026-10-01 09:00:00", "Fes", "Msemen", "1", "8") for i in range(97)], file="ok.csv")
    bad_file = raw(("C1", "2026-10-01 09:00:00", "Fes", "Msemen", "1", "8"),
                   *[(f"B{i}", "2026-10-01 09:00:00", "Fes", "Msemen", "1", "8,00") for i in range(2)],
                   file="bad.csv")
    rows = pd.concat([good_file, bad_file], ignore_index=True)
    sales, rejected = clean(rows)
    # 2% broken overall, but 66.7% in bad.csv: the gate must catch it
    assert quality_checks(rows, transform(sales), rejected) == ["bad.csv: 66.7% of the rows are broken (max 5%)"]


def test_end_to_end(tmp_path):
    (tmp_path / "in").mkdir()
    raw(GOOD, GOOD).drop(columns="source_file").to_csv(tmp_path / "in" / "sales.csv", index=False)
    assert main(["--input", str(tmp_path / "in"), "--output", str(tmp_path / "out")]) == 0
    for name in ["daily_revenue.csv", "quarantine.csv", "summary.md", "index.html"]:
        assert (tmp_path / "out" / name).exists()
