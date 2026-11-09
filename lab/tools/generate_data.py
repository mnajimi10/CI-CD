"""Generates the Cafe Atlas lab dataset (fictional coffee-shop chain in Morocco).

Output (relative to lab/data):
  raw/sales_2026_10.csv                October sales (contains a few dirty rows on purpose)
  new_data/sales_2026_11_week1.csv     "new data arrives": a normal file, a bit dirty
  new_data/sales_2026_11_week2.csv     a broken export: the Fes register writes prices as "28,00"

Deterministic: same seed, same files. Pure Python, no dependencies.
"""
import csv
import os
import random
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
rnd = random.Random(2026)

# city, sales per day (average)
CITIES = [("Casablanca", 34), ("Rabat", 18), ("Marrakech", 22), ("Fes", 15), ("Tanger", 16), ("Agadir", 12)]
PRODUCTS = [
    # name, price (MAD), weight
    ("Nous-nous", 14, 16), ("Cafe noir", 12, 12), ("The a la menthe", 15, 14), ("Cappuccino", 20, 7),
    ("Jus d'orange", 18, 8), ("Msemen", 8, 10), ("Croissant", 9, 7), ("Panini poulet", 35, 6),
]
COLUMNS = ["sale_id", "sold_at", "city", "product", "quantity", "unit_price"]
HOURS = {7: 6, 8: 10, 9: 9, 10: 6, 11: 4, 12: 4, 13: 4, 14: 3, 15: 4, 16: 6, 17: 7, 18: 6,
         19: 5, 20: 5, 21: 4, 22: 2}


def sales_for(day):
    rows = []
    weekend = 1.3 if day.weekday() >= 5 else 1.0
    for city, per_day in CITIES:
        n = max(1, round(rnd.gauss(per_day * weekend, per_day * 0.15)))
        for i in range(n):
            hour = rnd.choices(list(HOURS), weights=list(HOURS.values()))[0]
            sold_at = datetime(day.year, day.month, day.day, hour, rnd.randrange(60), rnd.randrange(60))
            name, price, _ = rnd.choices(PRODUCTS, weights=[p[2] for p in PRODUCTS])[0]
            qty = rnd.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0]
            rows.append([f"{day:%y%m%d}-{city[:3].upper()}-{i + 1:03d}", f"{sold_at:%Y-%m-%d %H:%M:%S}",
                         city, name, qty, price])
    return rows


def days(start, n):
    return [start + timedelta(days=i) for i in range(n)]


def write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(rows)
    print(f"{os.path.relpath(path, DATA)}: {len(rows)} rows")


def main():
    # October: 5 exact duplicates + 4 broken rows
    october = [r for d in days(date(2026, 10, 1), 31) for r in sales_for(d)]
    dirty = [list(r) for r in rnd.sample(october, 5)]
    dirty += [
        ["261012-RAB-901", "2026-10-12 09:14:02", "Rabat", "Nous-nous", 0, 14],         # quantity = 0
        ["261019-MAR-902", "2026-10-19 17:40:51", "Marrakech", "Msemen", -2, 8],        # negative quantity
        ["261023-XXX-903", "2026-10-23 08:05:33", "", "Cafe noir", 1, 12],              # missing city
        ["261027-TAN-904", "2026-10-27 25:61:00", "Tanger", "Cappuccino", 1, 20],       # impossible time
    ]
    october += dirty
    rnd.shuffle(october)
    write(os.path.join(DATA, "raw", "sales_2026_10.csv"), october)

    # November week 1: 2 October rows re-sent (duplicates) + 3 broken rows
    week1 = [r for d in days(date(2026, 11, 1), 7) for r in sales_for(d)]
    week1 += [list(r) for r in rnd.sample(october[:200], 2)]
    week1 += [
        ["261103-CAS-901", "2026-11-03 10:22:10", "Casablanca", "Croissant", 0, 9],     # quantity = 0
        ["261105-AGA-902", "", "Agadir", "The a la menthe", 1, 15],                     # missing date
        ["261106-FES-903", "2026-11-06 18:03:47", "Fes", "Panini poulet", 1, "N/A"],    # price not a number
    ]
    rnd.shuffle(week1)
    write(os.path.join(DATA, "new_data", "sales_2026_11_week1.csv"), week1)

    # November week 2: the Fes register got a "regional settings" update -> prices like "15,00"
    week2 = [r for d in days(date(2026, 11, 8), 7) for r in sales_for(d)]
    for r in week2:
        if r[2] == "Fes":
            r[5] = f"{r[5]},00"
    rnd.shuffle(week2)
    write(os.path.join(DATA, "new_data", "sales_2026_11_week2.csv"), week2)


if __name__ == "__main__":
    main()
