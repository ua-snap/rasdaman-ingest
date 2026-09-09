#!/usr/bin/env python3
"""
Build WMS 1.3.0 GetMap query strings for benchmarking.
Generates one request per coverage and writes them to a CSV
with coverageId and wms_query columns.
"""

import argparse
import json
import urllib.parse
from typing import Dict, Optional, Tuple, List

import pandas as pd


def build_wms_query(
    coverage_id: str,
    bbox: str,
    crs: str,
    axis_params: Dict[str, str],
) -> str:
    """Build the query string for a WMS GetMap request."""
    params = [
        ("SERVICE", "WMS"),
        ("VERSION", "1.3.0"),
        ("REQUEST", "GetMap"),
        ("LAYERS", coverage_id),
        ("BBOX", bbox),
        ("CRS", crs),
        ("WIDTH", 800),
        ("HEIGHT", 600),
        ("FORMAT", "image/png"),
        ("TRANSPARENT", "true"),
        ("STYLES", ""),
    ]
    for name, value in axis_params.items():
        params.append((name, value))

    return urllib.parse.urlencode(params, doseq=True)


def spatial_spec_from_row(row: pd.Series) -> Optional[Dict[str, object]]:
    """Derive spatial axes type and CRS; prefer projected XY when available."""
    axes = [a.strip() for a in str(row["axisList"]).split(",") if a.strip()]
    if not axes:
        return None

    axes_lower = {a.lower() for a in axes}

    # Prioritize projected XY coordinates when present.
    if "x" in axes_lower and "y" in axes_lower:
        return {
            "is_projected": True,
            "epsg": str(row["epsg"]),
        }

    if "lon" in axes_lower and "lat" in axes_lower:
        return {
            "is_projected": False,
            "epsg": "4326",
        }

    return None


def format_coord(val: float, decimals: int) -> str:
    """Helper to format coordinates to avoid excessive precision."""
    return f"{val:.{decimals}f}"


def parse_pair(val: str) -> Tuple[float, float]:
    """Parse a space-delimited numeric pair like 'x y' into a (x, y) tuple."""
    parts = str(val).split()
    return float(parts[0]), float(parts[1])


def bbox_from_bounds(
    lower: str,
    upper: str,
    decimals: int,
    axis_order: str,
) -> str:
    """Build a BBOX string from coverage bounds."""
    minx, miny = parse_pair(lower)
    maxx, maxy = parse_pair(upper)

    if axis_order == "yx":
        coords = (miny, minx, maxy, maxx)
    else:
        coords = (minx, miny, maxx, maxy)

    return ",".join(format_coord(c, decimals) for c in coords)


def non_spatial_axis_names(axis_list: str) -> List[str]:
    """Return non-spatial axis names in axisList order."""
    axes = [a.strip() for a in str(axis_list).split(",") if a.strip()]
    spatial = {"x", "y", "lon", "lat"}
    return [a for a in axes if a.lower() not in spatial]


def non_spatial_lower_bounds_from_row(row: pd.Series) -> Dict[str, str]:
    """Load non-spatial axis lower bounds from the coverage metadata CSV."""
    lower_raw = row.get("non_spatial_lower_bounds")
    if lower_raw is None or pd.isna(lower_raw):
        return {}
    return json.loads(str(lower_raw))


def non_spatial_param_set(row: pd.Series) -> Dict[str, str]:
    """Return a single parameter set using lower bounds for all non-spatial axes."""
    axes = non_spatial_axis_names(row.get("axisList", ""))
    if not axes:
        return {}

    lower = non_spatial_lower_bounds_from_row(row)
    return {axis: lower[axis] for axis in axes}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate WMS GetMap query strings for benchmarking."
    )
    ap.add_argument(
        "--in", dest="in_csv", default="zeus_coverages.csv", help="Input coverages CSV"
    )
    ap.add_argument(
        "--out",
        dest="out_csv",
        default="zeus_wms_benchmark_requests.csv",
        help="Output CSV with WMS query strings",
    )
    args = ap.parse_args()

    df = pd.read_csv(args.in_csv)

    # Only retain the "_wms" twin when both base and optimized coverage IDs exist.
    s = df["coverageId"].astype(str)
    base = s.str.replace(r"_wms$", "", regex=True)
    has_wms_twin = base.map((s.str.endswith("_wms")).groupby(base).any())
    keep = s.str.endswith("_wms") | ~has_wms_twin
    df_filtered = df.loc[keep].copy()

    out_rows = []
    for _, r in df_filtered.iterrows():
        # Skip WCS optimized coverages for WMS benchmarking.
        if "wcs" in r["coverageId"]:
            continue

        spec = spatial_spec_from_row(r)
        if not spec:
            continue

        decimals = 0 if spec["is_projected"] else 4
        axis_order = "yx" if str(spec["epsg"]) == "4326" else "xy"
        crs = f"EPSG:{spec['epsg']}"
        axis_params = non_spatial_param_set(r)

        lower = r["xy_lower"] if spec["is_projected"] else r["wgs84_lower"]
        upper = r["xy_upper"] if spec["is_projected"] else r["wgs84_upper"]
        bbox = bbox_from_bounds(
            lower=lower,
            upper=upper,
            decimals=decimals,
            axis_order=axis_order,
        )
        wms_query = build_wms_query(
            coverage_id=str(r["coverageId"]),
            bbox=bbox,
            crs=crs,
            axis_params=axis_params,
        )
        out_rows.append({"coverageId": r["coverageId"], "wms_query": wms_query})

    if not out_rows:
        print("Warning: No request strings were generated.")
    else:
        cov_count = len({row["coverageId"] for row in out_rows})
        print(f"Generated {len(out_rows)} requests across {cov_count} coverages.")

    pd.DataFrame(out_rows).to_csv(args.out_csv, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
