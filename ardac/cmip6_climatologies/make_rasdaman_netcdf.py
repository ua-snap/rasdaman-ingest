"""Write a Rasdaman-ready copy of cmip6_wrf_climatologies_<var>_daily.nc.

The only change from the source file is that the string coordinates (model,
scenario, era, aggregation) are replaced with the integer codes in luts.py, and
each one gets an `encoding` attribute holding the integer -> name mapping so it
is carried into the coverage metadata. Data values, chunking and compression
are unchanged.

The source file is huge (~50 GB compressed, ~200 GB uncompressed), so data is
copied block by block, with blocks aligned to the source chunks. Peak memory is
roughly one block (~60 MB for tmax) plus netCDF4's chunk cache.

Usage:
    python make_rasdaman_netcdf.py SRC.nc DST.nc
"""

import argparse
import itertools
import sys

import netCDF4 as nc

from luts import string_dim_luts


def copy_attrs(src_var, dst_var, skip=("_FillValue",)):
    for name in src_var.ncattrs():
        if name not in skip:
            dst_var.setncattr(name, src_var.getncattr(name))


def encode_string_dim(src, dst, name, lut):
    """Create integer coordinate `name` in dst from the string coordinate in src."""
    names = [str(v) for v in src[name][:]]
    missing = [n for n in names if n not in lut]
    if missing:
        sys.exit(f"'{name}' values not found in luts.py: {missing}")

    var = dst.createVariable(name, "i4", (name,))
    copy_attrs(src[name], var)
    var.units = "1"  # dimensionless under CF conventions
    var.encoding = str({lut[n]: n for n in names})
    var[:] = [lut[n] for n in names]


def copy_small_variable(src, dst, name):
    sv = src[name]
    fill = sv.getncattr("_FillValue") if "_FillValue" in sv.ncattrs() else None
    dv = dst.createVariable(name, sv.dtype, sv.dimensions, fill_value=fill)
    copy_attrs(sv, dv)
    dv[...] = sv[...]


def block_slices(shape, chunks):
    """Yield tuples of slices that tile `shape` in steps of `chunks`."""
    ranges = [
        [slice(i, min(i + c, n)) for i in range(0, n, c)]
        for n, c in zip(shape, chunks)
    ]
    return itertools.product(*ranges)


def copy_data_variable(src, dst, name):
    sv = src[name]
    chunks = sv.chunking()
    if chunks == "contiguous":
        sys.exit(f"'{name}' is not chunked; refusing to guess a block size.")
    filters = sv.filters()
    fill = sv.getncattr("_FillValue") if "_FillValue" in sv.ncattrs() else None

    dv = dst.createVariable(
        name,
        sv.dtype,
        sv.dimensions,
        chunksizes=chunks,
        zlib=filters["zlib"],
        complevel=filters["complevel"],
        shuffle=filters["shuffle"],
        fill_value=fill,
    )
    copy_attrs(sv, dv)

    # Spatial blocks span a full x chunk row so each source chunk is read once.
    block = list(chunks)
    block[-1] = sv.shape[-1]
    total = 1
    for n, c in zip(sv.shape, block):
        total *= -(-n // c)
    for i, sl in enumerate(block_slices(sv.shape, block), 1):
        dv[sl] = sv[sl]
        if i % 100 == 0 or i == total:
            print(f"  {name}: {i}/{total} blocks", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--variable", default="tmax", help="gridded data variable")
    args = parser.parse_args()

    src = nc.Dataset(args.src)
    dst = nc.Dataset(args.dst, "w", format="NETCDF4")

    dst.setncatts({k: src.getncattr(k) for k in src.ncattrs()})
    for name, dim in src.dimensions.items():
        dst.createDimension(name, len(dim))

    for name in src[args.variable].dimensions:
        if name in string_dim_luts:
            encode_string_dim(src, dst, name, string_dim_luts[name])
        else:
            copy_small_variable(src, dst, name)

    for name in src.variables:
        if name != args.variable and name not in dst.variables:
            copy_small_variable(src, dst, name)

    copy_data_variable(src, dst, args.variable)

    src.close()
    dst.close()
    print(f"wrote {args.dst}")


if __name__ == "__main__":
    main()
