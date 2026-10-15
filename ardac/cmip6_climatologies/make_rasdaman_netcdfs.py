"""Write Rasdaman-ready copies of cmip6_wrf_climatologies_<var>_daily.nc.

Up to two outputs are written in a single pass over the source file:

--rasdaman-out (WCS coverage): the only change from the source file is that the
string coordinates (model, scenario, era, aggregation) are replaced with the
integer codes in luts.py, and each one gets an `encoding` attribute holding the
integer -> name mapping so it is carried into the coverage metadata. Data values,
chunking and compression are unchanged.

--wms-out (WMS coverage): the model dimension is removed by averaging across
the individual CMIP6 models (everything except the CMIP6-Ensemble mean and
WRF-ERA5, which is only populated for the historical scenario), and only the
temporal_mean aggregation is kept, so the aggregation dimension is removed too:
each value is the mean of the models' temporal_mean. Remaining string
coordinates use the same integer codes as above.

The source file is huge (~50 GB compressed, ~200 GB uncompressed), so data is
read block by block, with blocks aligned to the source chunks. Blocks span every
model so the WMS summary can be computed in the same pass; peak memory is roughly
one block (~1 GB for tmax) plus netCDF4's chunk cache. Run it through Slurm (see
make_rasdaman_netcdfs.slurm).

Usage:
    python make_rasdaman_netcdfs.py SRC.nc [--rasdaman-out DST.nc] [--wms-out DST.nc]
"""

import argparse
import itertools
import os
import sys
import warnings

import netCDF4 as nc
import numpy as np

from luts import string_dim_luts

# Source models left out of the WMS summary.
WMS_EXCLUDE = ["CMIP6-Ensemble", "WRF-ERA5"]

# The only aggregation kept in the WMS file (its dimension is dropped).
WMS_AGGREGATION = "temporal_mean"

# Dimensions removed from the WMS file.
WMS_DROP_DIMS = ("model", "aggregation")


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


def summarize_models(members):
    """Mean over axis 0 (models) of `members`, skipping NaNs.

    All-NaN cells stay NaN.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(members.astype("f8"), axis=0)
    return mean.astype(members.dtype)


def create_output(src, path, variable, drop_dims):
    """Create `path`.tmp with the structure of src, minus the dims in `drop_dims`.

    Returns (dataset, data variable). The caller writes the data and then calls
    finish_output().
    """
    sv = src[variable]
    dst = nc.Dataset(path + ".tmp", "w", format="NETCDF4")
    dst.setncatts({k: src.getncattr(k) for k in src.ncattrs()})

    for name, dim in src.dimensions.items():
        if name not in drop_dims:
            dst.createDimension(name, len(dim))

    dims = [d for d in sv.dimensions if d not in drop_dims]
    for name in dims:
        if name in string_dim_luts:
            encode_string_dim(src, dst, name, string_dim_luts[name])
        else:
            copy_small_variable(src, dst, name)
    for name, var in src.variables.items():
        if name == variable or name in dst.variables:
            continue
        if any(d in drop_dims for d in var.dimensions) or name in drop_dims:
            continue
        copy_small_variable(src, dst, name)

    chunks = [c for c, d in zip(sv.chunking(), sv.dimensions) if d not in drop_dims]
    filters = sv.filters()
    fill = sv.getncattr("_FillValue") if "_FillValue" in sv.ncattrs() else None
    dv = dst.createVariable(
        variable,
        sv.dtype,
        dims,
        chunksizes=chunks,
        zlib=filters["zlib"],
        complevel=filters["complevel"],
        shuffle=filters["shuffle"],
        fill_value=fill,
    )
    copy_attrs(sv, dv)
    return dst, dv


def finish_output(dst, path):
    dst.close()
    os.replace(path + ".tmp", path)
    print(f"wrote {path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("src")
    parser.add_argument("--rasdaman-out", help="WCS NetCDF with all models")
    parser.add_argument("--wms-out", help="WMS NetCDF summarized across models")
    parser.add_argument("--variable", default="tmax", help="gridded data variable")
    args = parser.parse_args()
    if not (args.rasdaman_out or args.wms_out):
        parser.error("give at least one of --rasdaman-out and --wms-out")

    src = nc.Dataset(args.src)
    name = args.variable
    sv = src[name]
    chunks = sv.chunking()
    if chunks == "contiguous":
        sys.exit(f"'{name}' is not chunked; refusing to guess a block size.")
    if sv.dimensions[0] != "model":
        sys.exit(f"'{name}' must have model as its first dimension.")
    src_models = [str(v) for v in src["model"][:]]
    wms_models = [m for m in src_models if m not in WMS_EXCLUDE]
    wms_idx = [src_models.index(m) for m in wms_models]
    agg_pos = sv.dimensions.index("aggregation") - 1  # position in a block's rest dims
    agg_names = [str(v) for v in src["aggregation"][:]]
    if args.wms_out and WMS_AGGREGATION not in agg_names:
        sys.exit(f"aggregation '{WMS_AGGREGATION}' not found in the source file")

    ras = wms = None
    if args.rasdaman_out:
        ras, ras_var = create_output(src, args.rasdaman_out, name, ())
    if args.wms_out:
        wms, wms_var = create_output(src, args.wms_out, name, WMS_DROP_DIMS)
        wms.summary = (
            "Temporal mean daily climatologies by day of year (noleap "
            "calendar, 365 days) and climatological era, averaged across "
            f"{len(wms_models)} CMIP6 models (excluding the multi-model ensemble and "
            "the WRF-downscaled ERA5 reference): the mean of the models' "
            "temporal_mean values. Models: " + ", ".join(wms_models) + "."
        )
        wms_var.description = (
            f"{wms_var.description} Across models: the mean of the models' "
            "temporal_mean."
        )

    # Blocks span every model and a full x row, so each source chunk is read once.
    block = list(chunks[1:])
    block[-1] = sv.shape[-1]
    rest_shape = sv.shape[1:]
    total = 1
    for n, c in zip(rest_shape, block):
        total *= -(-n // c)
    for i, sl in enumerate(block_slices(rest_shape, block), 1):
        names = agg_names[sl[agg_pos]]
        mean_pos = names.index(WMS_AGGREGATION) if WMS_AGGREGATION in names else None
        if ras is not None or mean_pos is not None:
            data = sv[(slice(None),) + sl]
            if ras is not None:
                ras_var[(slice(None),) + sl] = data
            if wms is not None and mean_pos is not None:
                data = np.ma.filled(data[wms_idx], np.nan)
                mean = np.take(data, mean_pos, axis=agg_pos + 1)
                wms_var[sl[:agg_pos] + sl[agg_pos + 1 :]] = summarize_models(mean)
        if i % 20 == 0 or i == total:
            print(f"  {name}: {i}/{total} blocks", flush=True)

    src.close()
    if ras is not None:
        finish_output(ras, args.rasdaman_out)
    if wms is not None:
        finish_output(wms, args.wms_out)


if __name__ == "__main__":
    main()
