#!/usr/bin/env python3
"""
Analyze JMeter WCS benchmark results and summarize per-coverage latency and throughput.
"""

import argparse
import math
import re
import sys
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd


COVERAGE_ID_RE = re.compile(r"[?&]COVERAGEID=([^&]+)", re.IGNORECASE)


def extract_coverage_id(url: str) -> Optional[str]:
    """Extract COVERAGEID from a JMeter URL field. Harder to anticipate exactly what Jmeter will output in a results file, so there are some failsafes."""
    if not url:
        return None
    s = str(url)
    if not s.strip():
        return None

    try:
        parsed = urlparse(s)
        q = parse_qs(parsed.query)
        for k, v in q.items():
            if k.lower() == "coverageid" and v:
                return v[0]
    except Exception:
        pass

    m = COVERAGE_ID_RE.search(s)
    if m:
        return unquote(m.group(1))

    return None


def to_num(series: pd.Series) -> pd.Series:
    """Coerce a series to numeric values, using NaN for non-numeric entries."""
    return pd.to_numeric(series, errors="coerce")


def p95(series: pd.Series) -> float:
    """Compute 95th percentile for a numeric series."""
    return series.quantile(0.95)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Summarize WCS benchmark results by coverage."
    )
    ap.add_argument(
        "--results",
        default="wcs_benchmark_results.csv",
        help="JMeter CSV results (default: wcs_benchmark_results.csv)",
    )
    ap.add_argument(
        "--coverages",
        default="zeus_coverages.csv",
        help="Coverage metadata CSV",
    )
    ap.add_argument(
        "--out-summary",
        default="wcs_results_summary.csv",
        help="Output CSV for per-coverage summary",
    )
    ap.add_argument(
        "--include-failures",
        action="store_true",
        help="Include failed requests in latency/throughput metrics",
    )
    args = ap.parse_args()

    # Load JMeter results and ensure required columns are present.
    try:
        df = pd.read_csv(args.results)
    except Exception as exc:
        print(f"[ERROR] Failed to read results CSV: {exc}", file=sys.stderr)
        return 2

    if "URL" not in df.columns:
        print("[ERROR] results CSV missing URL column.", file=sys.stderr)
        return 2

    # Parse coverage IDs from the URL query string.
    df["coverageId"] = df["URL"].apply(extract_coverage_id)
    df = df[df["coverageId"].notna()].copy()
    if df.empty:
        print("[ERROR] No coverage IDs could be parsed from results.", file=sys.stderr)
        return 2

    # Normalize success flags (missing column means everything succeeded).
    if "success" in df.columns:
        df["success"] = df["success"].astype(bool)
    else:
        df["success"] = True

    # Convert key numeric fields and compute throughput in bytes/sec.
    df["elapsed_ms"] = to_num(df.get("elapsed"))
    latency_col = "Latency" if "Latency" in df.columns else "elapsed"
    df["latency_ms"] = to_num(df.get(latency_col))
    df["bytes"] = to_num(df.get("bytes"))

    df["throughput_bps"] = df.apply(
        lambda r: (
            (r["bytes"] / (r["elapsed_ms"] / 1000.0))
            if r["elapsed_ms"] and r["elapsed_ms"] > 0
            else math.nan
        ),
        axis=1,
    )

    # Keep counts based on all requests; optionally filter to successes for metrics.
    df_all = df.copy()

    if not args.include_failures:
        df = df[df["success"]].copy()

    if df.empty:
        print("[ERROR] No rows to analyze after filtering.", file=sys.stderr)
        return 2

    # Per-coverage counts and success rate (based on all rows).
    counts = (
        df_all.groupby("coverageId")
        .agg(
            count_total=("coverageId", "size"),
            count_success=("success", "sum"),
            success_rate=("success", "mean"),
        )
        .reset_index()
    )

    # Per-coverage latency and throughput summaries (success-only if filtered).
    summary = (
        df.groupby("coverageId")
        .agg(
            count_used=("coverageId", "size"),
            latency_mean_ms=("latency_ms", "mean"),
            latency_p95_ms=("latency_ms", p95),
            throughput_mean_bps=("throughput_bps", "mean"),
        )
        .reset_index()
    )

    summary = summary.merge(counts, on="coverageId", how="left")

    # Merge in default metadata columns if available.
    default_cov_cols = [
        "coverageId",
        "epsg",
        "size_bytes",
        "num_dimensions",
        "axisList",
    ]
    if args.coverages:
        try:
            cov = pd.read_csv(args.coverages)
            if "coverageId" not in cov.columns:
                raise ValueError("coverageId column missing from coverages CSV")
            cols = [c for c in default_cov_cols if c in cov.columns]
            cov = cov[cols].drop_duplicates(subset=["coverageId"])
            summary = summary.merge(cov, on="coverageId", how="left")
        except Exception as exc:
            print(f"[WARN] Failed to read/merge coverages CSV: {exc}")

    # Round metrics for readable output.
    for col in ["latency_mean_ms", "latency_p95_ms", "throughput_mean_bps"]:
        if col in summary.columns:
            summary[col] = summary[col].round(0).astype("Int64")
    if "success_rate" in summary.columns:
        summary["success_rate"] = summary["success_rate"].round(3)

    summary.to_csv(args.out_summary, index=False)

    print(f"[OK] Wrote summary: {args.out_summary}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
