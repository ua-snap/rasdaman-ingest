#!/usr/bin/env python3
"""
Fetch Zeus WCS 2.1.0 GetCapabilities document and write a coverage metadata CSV that will be used to build some requests.
Most of this script is ugly XML parsing. The best way to verify the behavior of this script is to compare the output CSV file to what you see on Petascope.
"""

import argparse
import csv
import json
import re
import sys
from typing import Dict, List, Optional, Tuple

import requests
import xml.etree.ElementTree as ET


ZEUS_CAPABILITIES_URL = "https://zeus.snap.uaf.edu/rasdaman/ows?SERVICE=WCS&ACCEPTVERSIONS=2.1.0&REQUEST=GetCapabilities"

# just some shorthand for jumping around the XML namespace
NS: Dict[str, str] = {
    "wcs": "http://www.opengis.net/wcs/2.0",
    "ows": "http://www.opengis.net/ows/2.0",
}

CSV_HEADERS = [
    "coverageId",
    "axisList",
    "num_dimensions",
    "size_bytes",
    "epsg",
    "xy_lower",
    "xy_upper",
    "xy_centroid_x",
    "xy_centroid_y",
    "wgs84_lower",
    "wgs84_upper",
    "wgs84_centroid_lon",
    "wgs84_centroid_lat",
    "non_spatial_lower_bounds",
]

EPSG_RE = re.compile(r"/crs/EPSG/0/(\d{4})(?:\b|$)")
FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def fmt_num(x: float) -> str:
    """
    Format coordinate precision to 4 decimal places, removing trailing decimal point, and return as a string.
    """
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def fetch_capabilities_xml() -> ET.Element:
    """
    Fetch the Rasdaman GetCapabilities document from Zeus.
    """
    r = requests.get(ZEUS_CAPABILITIES_URL, timeout=30)
    r.raise_for_status()
    return ET.fromstring(r.content.strip())


def simplify_epsg(native_crs: str) -> str:
    """For our readability, we just need the 4 digit EPSG code. There **are** EPSGs with more than 4 digits out there, but we don't use them."""
    m = EPSG_RE.findall(native_crs or "")
    return m[-1] if m else "NOT_FOUND"


def split_corner_indices(text: str) -> List[str]:
    """
    The corner indices, both spatial and non-spatial, get parsed as a big ugly string that can sub-quotes like in timestamps.
    This splits the input string into a list of strings, one list item per index.
    """
    if not text:
        return []
    s = " ".join(text.strip().split())
    raw = re.findall(r'"([^"]*)"|(\S+)', s)
    return [(q if q else w) for q, w in raw]


def parse_corners(el: Optional[ET.Element]) -> Tuple[str, List[str], List[str]]:
    """
    Isolate the lower and upper corner coordinates for each spatial axis and return alongside the CRS attribute.
    """
    if el is None:
        return "", [], []
    crs = el.attrib.get("crs", "") or ""
    lower_corner = (
        el.findtext("ows:LowerCorner", default="", namespaces=NS) or ""
    ).strip()
    upper_corner = (
        el.findtext("ows:UpperCorner", default="", namespaces=NS) or ""
    ).strip()
    return crs, split_corner_indices(lower_corner), split_corner_indices(upper_corner)


def extract_additional_params(cs: ET.Element) -> Dict[str, str]:
    """
    Extract the additional parameters from the coverage summary.
    Right now these are just the names of all axes and as well as the size of the coverage in bytes.
    """
    ap = cs.find("ows:AdditionalParameters", NS)
    if ap is None:
        return {}
    out: Dict[str, str] = {}
    for p in ap.findall("ows:AdditionalParameter", NS):
        name = (p.findtext("ows:Name", default="", namespaces=NS) or "").strip()
        val = (p.findtext("ows:Value", default="", namespaces=NS) or "").strip()
        if name:
            out[name] = val
    return out


def get_spatial_indices(axis_list: List[str]) -> Optional[Tuple[int, int]]:
    """
    Returns the indices of the spatial axes in the axis list, or None if not found.
    These should almost always be the last two axes in the list, but the names of these axes could vary a bit.
    """
    norms = [a.strip().lower() for a in axis_list]
    x_like = {"x", "lon", "longitude"}
    y_like = {"y", "lat", "latitude"}

    xi = next((i for i, a in enumerate(norms) if a in x_like), None)
    yi = next((i for i, a in enumerate(norms) if a in y_like), None)
    if xi is not None and yi is not None and xi != yi:
        return xi, yi
    return None


def non_spatial_lower_bounds(axis_list: List[str], lower_bounds: List[str]) -> str:
    """
    Return a JSON string of non-spatial axis lower bounds keyed by axis name.
    Uses axisList ordering and skips spatial axes.
    """
    idx = get_spatial_indices(axis_list)
    spatial = set(idx) if idx else set()
    out: Dict[str, str] = {}
    for i, axis in enumerate(axis_list):
        if i in spatial:
            continue
        if i < len(lower_bounds):
            out[axis] = lower_bounds[i]
    return json.dumps(out, ensure_ascii=False) if out else ""


def xy_and_centroid(
    axis_list: List[str], lower_bounds: List[str], upper_bounds: List[str]
) -> Tuple[str, str, str, str]:
    """
    Produce "x y" lower/upper strings and centroid x/y strings.
    Uses axisList indices if aligned; else falls back to last two numeric values.
    """
    idx = get_spatial_indices(axis_list)
    if (
        idx
        and len(lower_bounds) >= len(axis_list)
        and len(upper_bounds) >= len(axis_list)
    ):
        xi, yi = idx
        try:
            lx, ly = float(lower_bounds[xi]), float(lower_bounds[yi])
            ux, uy = float(upper_bounds[xi]), float(upper_bounds[yi])
            return (
                f"{fmt_num(lx)} {fmt_num(ly)}",
                f"{fmt_num(ux)} {fmt_num(uy)}",
                fmt_num((lx + ux) / 2.0),
                fmt_num((ly + uy) / 2.0),
            )
        except Exception:
            pass

    lo_nums = [float(m.group(0)) for m in FLOAT_RE.finditer(" ".join(lower_bounds))]
    hi_nums = [float(m.group(0)) for m in FLOAT_RE.finditer(" ".join(upper_bounds))]
    if len(lo_nums) >= 2 and len(hi_nums) >= 2:
        lx, ly = lo_nums[-2], lo_nums[-1]
        ux, uy = hi_nums[-2], hi_nums[-1]
        return (
            f"{fmt_num(lx)} {fmt_num(ly)}",
            f"{fmt_num(ux)} {fmt_num(uy)}",
            fmt_num((lx + ux) / 2.0),
            fmt_num((ly + uy) / 2.0),
        )

    return "", "", "", ""


def iter_rows(caps_root: ET.Element):
    for cs in caps_root.findall(".//wcs:CoverageSummary", NS):
        cov_id = (
            cs.findtext("wcs:CoverageId", default="", namespaces=NS) or ""
        ).strip()
        if not cov_id:
            continue

        # declutter the benchmarks by avoiding in-flight test coverages
        if "test" in cov_id:
            continue

        add = extract_additional_params(cs)
        axis_list = [
            a.strip() for a in (add.get("axisList", "")).split(",") if a.strip()
        ]
        size_bytes = add.get("sizeInBytes", "")
        ndim = str(len(axis_list)) if axis_list else ""

        native_crs, n_lo, n_hi = parse_corners(cs.find("ows:BoundingBox", NS))
        epsg = simplify_epsg(native_crs)

        _, w_lo, w_hi = parse_corners(cs.find("ows:WGS84BoundingBox", NS))
        w_lower, w_upper, w_clon, w_clat = xy_and_centroid(["lon", "lat"], w_lo, w_hi)

        # xy bounds and centroid
        xy_lower, xy_upper, xy_cx, xy_cy = xy_and_centroid(axis_list, n_lo, n_hi)
        non_spatial_lower = non_spatial_lower_bounds(axis_list, n_lo)

        # some heuristics to simplify things
        if epsg == "NOT_FOUND":
            # if there is no CRS, we don't need to consider geospatial coordinates
            # not a common case, but hydroviz and such are in this category
            xy_lower = xy_upper = xy_cx = xy_cy = "NOT_FOUND"
            w_lower = w_upper = w_clon = w_clat = "NOT_FOUND"
            non_spatial_lower = "NOT_FOUND"
        elif epsg == "4326":
            # if the CRS is 4326, we don't need to consider projected XY coordinates
            # less common for data to be unprojected 4326
            xy_lower = xy_upper = xy_cx = xy_cy = ""
        elif epsg == "3338" and (xy_lower.strip() or xy_upper.strip()):
            # most common: projected data, and here we don't need the geographic lat-lon bounds for benchmarking
            w_lower = w_upper = w_clon = w_clat = ""

        # skip coverages without some type or orthodox spatial axes (i.e. those with stream segments, etc.)

        if all(
            val == "NOT_FOUND"
            for val in [
                xy_lower,
                xy_upper,
                xy_cx,
                xy_cy,
                w_lower,
                w_upper,
                w_clon,
                w_clat,
            ]
        ):
            continue

        yield [
            cov_id,
            ",".join(axis_list),
            ndim,
            size_bytes,
            epsg,
            xy_lower,
            xy_upper,
            xy_cx,
            xy_cy,
            w_lower,
            w_upper,
            w_clon,
            w_clat,
            non_spatial_lower,
        ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="zeus_coverages.csv")
    args = ap.parse_args()

    try:
        capabilities_root = fetch_capabilities_xml()
    except Exception as e:
        print(f"[ERROR] Failed to fetch/parse GetCapabilities: {e}", file=sys.stderr)
        return 2

    count = 0
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADERS)
        for row in iter_rows(capabilities_root):
            w.writerow(row)
            count += 1

    print(f"[OK] Wrote {count} coverages to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
