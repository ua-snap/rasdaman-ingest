#!/usr/bin/env python3
"""
Build WCS 2.1 GetCoverage query strings that subsets each OGC Coverage at specified spatial cooridate pair, such as the centroid.
The script uses a CSV of available coverages as the input and outputs a csv indexed by the coverage ID with a column for the request string.
"""

import argparse
import urllib.parse
from typing import Dict, Optional

import pandas as pd


def build_wcs_query(
    coverage_id: str,
    subsets: Dict[str, float],
    fmt: str = "application/json",
) -> str:
    """Build the query string for a WCS GetCoverage request, kinda like SNAP Data API."""
    params = [
        ("SERVICE", "WCS"),
        ("VERSION", "2.1.0"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", coverage_id),
        ("FORMAT", fmt),
    ]

    # Sort subset strings for consistent output readability
    for axis in sorted(subsets.keys()):
        val = subsets[axis]
        params.append(("SUBSET", f"{axis}({val})"))

    return urllib.parse.urlencode(params, doseq=True, safe="():,/-")


def centroid_subsets_from_row(row: pd.Series) -> Optional[Dict[str, float]]:
    axes = [a.strip() for a in str(row["axisList"]).split(",") if a.strip()]
    axes_set = set(axes)

    # Check if X/Y coordinates exist, expected for all projected CRS
    has_xy = (
        {"X", "Y"}.issubset(axes_set)
        and float(row.get("xy_centroid_x"))
        and float(row.get("xy_centroid_y"))
    )

    # Check if lon/lat coordinates exist, expected for all coverages
    has_lonlat = (
        {"lon", "lat"}.issubset(axes_set)
        and float(row.get("wgs84_centroid_lon"))
        and float(row.get("wgs84_centroid_lat"))
    )

    # prioritize XY, use those coordinates if available
    if has_xy:
        return {"X": float(row["xy_centroid_x"]), "Y": float(row["xy_centroid_y"])}

    if has_lonlat:
        return {
            "lon": float(row["wgs84_centroid_lon"]),
            "lat": float(row["wgs84_centroid_lat"]),
        }

    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate WCS GetCoverage query strings for benchmarking."
    )
    ap.add_argument(
        "--in", dest="in_csv", default="zeus_coverages.csv", help="Input coverages CSV"
    )
    ap.add_argument(
        "--out",
        dest="out_csv",
        default="zeus_wcs_benchmark_requests.csv",
        help="Output CSV with WCS query strings",
    )
    ap.add_argument(
        "--format", dest="fmt", default="application/json", help="WCS output format"
    )
    args = ap.parse_args()

    df = pd.read_csv(args.in_csv)
    # first compare the coverageId values because because in some cases there are "twins" where one has a suffix "_wcs' that indicates it is WCS optimized
    # we want to only retain the version with the wcs suffix in that case

    s = df["coverageId"].astype(str)

    # base id = strip trailing "_wcs" if present
    base = s.str.replace(r"_wcs$", "", regex=True)

    # keep all "_wcs" rows; for non-_wcs rows, drop if a twin "_wcs" exists
    has_wcs_twin = base.map((s.str.endswith("_wcs")).groupby(base).any())
    keep = s.str.endswith("_wcs") | ~has_wcs_twin

    df_filtered = df.loc[keep].copy()

    out_rows = []
    for _, r in df_filtered.iterrows():
        # skip wms coverages because this script is just for WCS benchmarking
        if "wms" in r["coverageId"]:
            continue

        subsets = centroid_subsets_from_row(r)

        if subsets:
            wcs_query = build_wcs_query(
                coverage_id=str(r["coverageId"]),
                subsets=subsets,
                fmt=args.fmt,
            )
            out_rows.append({"coverageId": r["coverageId"], "wcs_query": wcs_query})

    if not out_rows:
        print("Warning: No request strings were generated!")
    else:
        print(f"Generated {len(out_rows)} requests.")

    pd.DataFrame(out_rows).to_csv(args.out_csv, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
