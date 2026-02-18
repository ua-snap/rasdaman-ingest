#!/usr/bin/env python3
"""
Build WCS 2.1 GetCoverage query strings that subset each OGC Coverage at one or more
spatial coordinate pairs in a bounding box around the centroid. The script uses a CSV of available
coverages as the input and outputs a csv indexed by the coverage ID with a column
for the request string.
"""

import argparse
import random
import urllib.parse
from typing import Dict, Optional, Tuple, List

import pandas as pd


def build_wcs_query(
    coverage_id: str,
    subsets: Dict[str, str],
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


def spatial_spec_from_row(row: pd.Series) -> Optional[Dict[str, object]]:
    """Derive spatial axes and centroid; prefer projected XY when available."""
    axes = [a.strip() for a in str(row["axisList"]).split(",") if a.strip()]
    if not axes:
        return None

    axes_lower = {a.lower() for a in axes}

    # Prioritize projected XY coordinates when present.
    if "x" in axes_lower and "y" in axes_lower:
        return {
            "axis_x": "X",
            "axis_y": "Y",
            "center_x": float(row["xy_centroid_x"]),
            "center_y": float(row["xy_centroid_y"]),
            "is_projected": True,
        }

    if "lon" in axes_lower and "lat" in axes_lower:
        return {
            "axis_x": "lon",
            "axis_y": "lat",
            "center_x": float(row["wgs84_centroid_lon"]),
            "center_y": float(row["wgs84_centroid_lat"]),
            "is_projected": False,
        }

    return None


def jitter_points(
    center_x: float,
    center_y: float,
    radius: float,
    count: int,
    rng: random.Random,
) -> List[Tuple[float, float]]:
    """Generate random points within a centered bbox."""
    points: List[Tuple[float, float]] = []
    minx = center_x - radius
    maxx = center_x + radius
    miny = center_y - radius
    maxy = center_y + radius

    for _ in range(count):
        # Pick x/y uniformly within the centered bbox:
        # [center_x - radius, center_x + radius] x [center_y - radius, center_y + radius].
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        points.append((x, y))
    return points


def format_coord(val: float, decimals: int) -> str:
    """Helper to format coordinates to avoid excessive precision."""
    return f"{val:.{decimals}f}"


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
    ap.add_argument(
        "--num-locations",
        dest="num_locations",
        type=int,
        default=10,
        help="Number of jittered locations to generate per coverage",
    )
    ap.add_argument(
        "--radius-xy-km",
        dest="radius_xy_km",
        type=float,
        default=150.0,
        help="Jitter radius (km) for projected X/Y coverages",
    )
    ap.add_argument(
        "--radius-lonlat-deg",
        dest="radius_lonlat_deg",
        type=float,
        default=2.0,
        help="Jitter radius (degrees) for lon/lat coverages",
    )
    ap.add_argument(
        "--seed",
        dest="seed",
        type=int,
        default=None,
        help="Random seed for reproducible jitter locations",
    )
    args = ap.parse_args()

    rng = random.Random(args.seed)

    df = pd.read_csv(args.in_csv)

    # only retain the "_wcs" twin when both base and optimized coverage IDs exist.
    s = df["coverageId"].astype(str)
    # base id = strip trailing "_wcs" if present
    base = s.str.replace(r"_wcs$", "", regex=True)
    # keep all "_wcs" rows; for non-_wcs rows, drop if a twin "_wcs" exists
    has_wcs_twin = base.map((s.str.endswith("_wcs")).groupby(base).any())
    keep = s.str.endswith("_wcs") | ~has_wcs_twin
    df_filtered = df.loc[keep].copy()

    out_rows = []
    for _, r in df_filtered.iterrows():
        # Skip WMS coverages because this script is just for WCS benchmarking.
        if "wms" in r["coverageId"]:
            continue

        spec = spatial_spec_from_row(r)
        if not spec:
            continue

        # meters for projected XY, degrees for lon/lat
        radius = (
            args.radius_xy_km * 1000.0
            if spec["is_projected"]
            else args.radius_lonlat_deg
        )
        points = jitter_points(
            center_x=float(spec["center_x"]),
            center_y=float(spec["center_y"]),
            radius=radius,
            count=args.num_locations,
            rng=rng,
        )

        axis_x = str(spec["axis_x"])
        axis_y = str(spec["axis_y"])
        # Coarser precision for meters; 4-decimal precision for lat/lon.
        decimals = 0 if spec["is_projected"] else 4
        for x, y in points:
            subsets = {
                axis_x: format_coord(x, decimals),
                axis_y: format_coord(y, decimals),
            }
            wcs_query = build_wcs_query(
                coverage_id=str(r["coverageId"]),
                subsets=subsets,
                fmt=args.fmt,
            )
            out_rows.append({"coverageId": r["coverageId"], "wcs_query": wcs_query})

    if not out_rows:
        print("Warning: No request strings were generated.")
    else:
        cov_count = len({row["coverageId"] for row in out_rows})
        print(f"Generated {len(out_rows)} requests across {cov_count} coverages.")

    # shuffle to avoid pinging same coverage over and over.
    rng.shuffle(out_rows)
    pd.DataFrame(out_rows).to_csv(args.out_csv, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
