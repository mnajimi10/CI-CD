import html
import os
from datetime import datetime, timezone
from pathlib import Path

CSS = """
body { font-family: system-ui, sans-serif; max-width: 820px; margin: 40px auto; padding: 0 20px; color: #1f2937; }
h1 { color: #0b2454; margin-bottom: 4px; }
.meta { color: #6b7280; font-size: 14px; margin-bottom: 28px; }
.meta code { background: #eef2f7; padding: 2px 6px; border-radius: 4px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 28px; }
th, td { padding: 8px 12px; border-bottom: 1px solid #e5e7eb; text-align: right; }
th:first-child, td:first-child { text-align: left; }
th { background: #0b2454; color: white; }
.fail { background: #fdecec; color: #b91c1c; padding: 12px 16px; border-radius: 8px; }
"""


def _table(df, columns):
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>"
                   for row in df.itertuples(index=False))
    return f"<table><tr>{head}</tr>{rows}</table>"


def _by(daily, key, label):
    out = daily.groupby(key, as_index=False).agg(sales=("sales", "sum"), revenue=("revenue", "sum"))
    out = out.sort_values("revenue", ascending=False) if key == "city" else out.sort_values(key)
    out["sales"] = out["sales"].map("{:,}".format)
    out["revenue"] = out["revenue"].map("{:,.2f}".format)
    return f"<h2>Revenue per {label} (MAD)</h2>" + _table(out, [label.capitalize(), "Sales", "Revenue"])


def write_outputs(output_dir, daily, rejected, stats):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out / "daily_revenue.csv", index=False)
    rejected.to_csv(out / "quarantine.csv", index=False)

    commit = os.getenv("GIT_SHA", "local")[:7]
    built_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
    reasons = rejected["reject_reason"].value_counts()

    # Markdown summary: shown on the GitHub Actions run page
    md = ["## ❌ Quality checks failed" if stats["failures"] else "## ✅ Quality checks passed", ""]
    md += [f"- {f}" for f in stats["failures"]] + ([""] if stats["failures"] else [])
    md += ["| | |", "|---|---:|",
           f"| Files | {', '.join(stats['files'])} |",
           f"| Rows read | {stats['raw_rows']:,} |",
           f"| Duplicates removed | {stats['duplicates']:,} |",
           f"| Rows rejected | {stats['rejected']:,} |",
           f"| Valid sales | {stats['sales']:,} |",
           f"| Revenue (MAD) | {stats['revenue']:,.2f} |", ""]
    if len(reasons):
        md += ["| Reject reason | Rows |", "|---|---:|"] + [f"| {r} | {n} |" for r, n in reasons.items()]
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # HTML report: the "production" page, deployed on GitHub Pages
    daily = daily.assign(month=daily["date"].map(lambda d: f"{d:%Y-%m}"))
    failed = "".join(f'<p class="fail">Quality check failed: {html.escape(f)}</p>' for f in stats["failures"])
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Cafe Atlas · Sales report</title><style>{CSS}</style></head>
<body>
<h1>Café Atlas · Sales report</h1>
<p class="meta">Built from commit <code>{commit}</code> on {built_at} ·
{stats['sales']:,} sales · {stats['revenue']:,.2f} MAD ·
last day: {daily['date'].max() if len(daily) else '-'} ·
{stats['duplicates']} duplicates removed · {stats['rejected']} rows in quarantine</p>
{failed}
{_by(daily, "city", "city")}
{_by(daily, "month", "month")}
</body></html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")
