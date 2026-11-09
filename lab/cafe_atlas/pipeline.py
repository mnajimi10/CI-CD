
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from cafe_atlas.report import write_outputs

MAX_REJECT_RATE = 0.05  # quality gate: a file with more than 5% of broken rows is suspicious, stop


def extract(input_dir):
    """Read every CSV file of the folder, as text, and remember which file each row came from."""
    files = sorted(Path(input_dir).glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"no CSV file in {input_dir}")
    return pd.concat([pd.read_csv(f, dtype=str).assign(source_file=f.name) for f in files], ignore_index=True)


def clean(raw):
    """Remove duplicates, set the types, split valid rows from broken ones.

    Returns (sales, rejected). Rejected rows keep their original values + a reject_reason.
    """
    df = raw.drop_duplicates(subset="sale_id").copy()
    sold_at = pd.to_datetime(df["sold_at"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    quantity = pd.to_numeric(df["quantity"], errors="coerce")
    unit_price = pd.to_numeric(df["unit_price"], errors="coerce")

    rules = [  # the first rule that matches gives the reason
        (sold_at.isna(), "invalid sold_at"),
        (df["city"].isna() | (df["city"].str.strip() == ""), "missing city"),
        (~(quantity > 0), "quantity <= 0"),
        (unit_price.isna() | (unit_price < 0), "invalid unit_price"),
    ]
    reason = pd.Series(np.select([m for m, _ in rules], [r for _, r in rules], default=""), index=df.index)

    rejected = df[reason != ""].assign(reject_reason=reason[reason != ""])
    sales = df[reason == ""].assign(sold_at=sold_at, quantity=quantity.astype("int64"), unit_price=unit_price)
    return sales.reset_index(drop=True), rejected.reset_index(drop=True)


def transform(sales):
    """One row per day and city: number of sales, items sold, revenue (MAD)."""
    df = sales.assign(date=sales["sold_at"].dt.date, revenue=sales["quantity"] * sales["unit_price"])
    daily = (df.groupby(["date", "city"], as_index=False)
               .agg(sales=("sale_id", "count"), items=("quantity", "sum"), revenue=("revenue", "sum")))
    daily["revenue"] = daily["revenue"].round(2)
    return daily


def quality_checks(raw, daily, rejected):
    """Data tests: return the list of failed checks (empty list = all good)."""
    failures = []
    # checked file by file: one bad file must not hide behind the good ones
    reject_rate = (rejected["source_file"].value_counts() / raw["source_file"].value_counts()).fillna(0)
    for file, rate in reject_rate.sort_index().items():
        if rate > MAX_REJECT_RATE:
            failures.append(f"{file}: {rate:.1%} of the rows are broken (max {MAX_REJECT_RATE:.0%})")
    if daily.empty:
        failures.append("no valid sale at all")
    if (daily["revenue"] < 0).any():
        failures.append("negative revenue")
    if daily.duplicated(["date", "city"]).any():
        failures.append("more than one row per day and city")
    return failures


def run(input_dir="data/raw", output_dir="output"):
    raw = extract(input_dir)
    sales, rejected = clean(raw)
    daily = transform(sales)
    failures = quality_checks(raw, daily, rejected)
    stats = {
        "files": sorted(raw["source_file"].unique()),
        "raw_rows": len(raw),
        "duplicates": len(raw) - len(sales) - len(rejected),
        "rejected": len(rejected),
        "sales": len(sales),
        "revenue": float(daily["revenue"].sum()),
        "failures": failures,
    }
    write_outputs(output_dir, daily, rejected, stats)
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cafe Atlas sales pipeline")
    parser.add_argument("--input", default="data/raw", help="folder with the raw CSV files")
    parser.add_argument("--output", default="output", help="where to write the results")
    args = parser.parse_args(argv)

    stats = run(args.input, args.output)
    print(f"{stats['raw_rows']} rows read from {len(stats['files'])} file(s): {stats['sales']} valid sales, "
          f"{stats['duplicates']} duplicates, {stats['rejected']} rejected, revenue {stats['revenue']:,.2f} MAD")
    for failure in stats["failures"]:
        print(f"QUALITY CHECK FAILED: {failure}", file=sys.stderr)
    return 1 if stats["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
