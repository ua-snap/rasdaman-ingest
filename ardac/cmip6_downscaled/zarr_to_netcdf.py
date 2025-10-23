#!/usr/bin/env python3
import xarray as xr
import os
import dask
import cftime
import numpy as np
from xclim.core.units import convert_units_to

import warnings

warnings.filterwarnings("ignore")

zarr_dir = os.environ.get("ADJUSTED_DIR")
netcdf_dir = os.environ.get("NETCDF_DIR")
os.makedirs(netcdf_dir, exist_ok=True)


def fix_time(ds):
    """If days are missing, fix the dataset by adding NaN values for those days.
    Ensures time starts on Jan 1 and ends on Dec 31.
    Dates are in CF-compliant format: units 'days since 1950-01-01', calendar 'noleap'.
    """
    var = list(ds.data_vars)[0]
    src = ds[var].encoding.get("source", "unknown")

    # Get the time variable as cftime objects
    time = ds["time"].values
    if not isinstance(time[0], cftime.DatetimeNoLeap):
        time = xr.cftime_range(
            start=str(ds["time"].values[0]),
            end=str(ds["time"].values[-1]),
            freq="D",
            calendar="noleap",
        )
    else:
        time = ds["time"].values

    # Ensure time starts on Jan 1 and ends on Dec 31, use hour 12 to match input file specs
    start_year = time[0].year
    end_year = time[-1].year
    start = cftime.DatetimeNoLeap(start_year, 1, 1, 12)
    end = cftime.DatetimeNoLeap(end_year, 12, 31, 12)
    all_days = xr.cftime_range(start=start, end=end, freq="D", calendar="noleap")
    missing_days = sorted(set(all_days) - set(time))

    if len(missing_days) == 365 or len(missing_days) == 0:
        # this is a case where the hour is set to 0 instead of 12 (CESM2 model)
        # here we just want to skip the filling of NaN values and assume the time is correct
        # Set CF-compliant encoding and return
        ds["time"].encoding.update(
            {"units": "days since 1950-01-01", "calendar": "noleap"}
        )
        return ds

    if missing_days:
        print(
            f"Missing days ({len(missing_days)}) in {src}: {missing_days[:5]}{'...' if len(missing_days) > 5 else ''} .... attempting to add all NaN array for these days."
        )
        # drop any dtype encoding in the time dimension - some int64 encoding remnants cause issues!
        ds["time"].encoding.pop("dtype", None)
        # Reindex to include all days, fill_value for missing days is NaN
        ds = ds.reindex(time=all_days)

        # Set CF-compliant encoding
        ds["time"].encoding.update(
            {"units": "days since 1950-01-01", "calendar": "noleap"}
        )
        return ds


def fix_CESM2_time(ds):
    """Fix the time variable for CESM2 datasets so that the hour is set to 12 instead of 0."""
    if "time" in ds:
        print("Fixing CESM2 time variable to set hour to 12.")
        time = ds["time"].values
        if isinstance(time[0], cftime.DatetimeNoLeap):
            # Convert to 12:00 noon
            new_time = np.array(
                [cftime.DatetimeNoLeap(t.year, t.month, t.day, 12) for t in time]
            )
            # Create a new DataArray for time
            new_time_da = xr.DataArray(
                new_time,
                dims=ds["time"].dims,
                coords=ds["time"].coords,
                # attrs=ds["time"].attrs,
            )
            # Set encoding for CF compliance
            new_time_da.encoding.update(
                {"units": "days since 1950-01-01", "calendar": "noleap"}
            )
            ds = ds.assign_coords(time=new_time_da)
    return ds


def convert_zarr_to_netcdf(varname, file, output_path):
    with dask.config.set(**{"array.slicing.split_large_chunks": True}):
        ds = xr.open_zarr(file).load()
        ds = ds.drop_vars(["lat", "lon"])

        if varname in ["tasmax", "tasmin"]:
            ds[varname] = convert_units_to(ds[varname], "degC")

        if varname == "pr":
            ds[varname] = convert_units_to(ds[varname], "mm/day")

        # For Rasdaman WMS compatibility.
        ds = ds.transpose("time", "x", "y")
        ds = ds.sortby(ds.y, ascending=False)

        ds = fix_time(ds)

        if "CESM2" in file:
            ds = fix_CESM2_time(ds)

        ds.to_netcdf(output_path, encoding={f"{varname}": {"_FillValue": -9999.0}})


if __name__ == "__main__":
    # Get a list of all *.zarr files in zarr_dir.
    zarr_files = [
        os.path.join(zarr_dir, f) for f in os.listdir(zarr_dir) if f.endswith(".zarr")
    ]

    zarr_files = [f for f in zarr_files if not os.path.basename(f).startswith("dtr")]

    for file in zarr_files:
        basename = os.path.basename(file)
        without_ext = os.path.splitext(basename)[0]
        varname = basename.split("_")[0]

        output_file = f"{without_ext}.nc"
        output_path = os.path.join(netcdf_dir, output_file)
        print(f"Creating: {output_file}")

        try:
            convert_zarr_to_netcdf(varname, file, output_path)
        except Exception as e:
            print(f"Error converting {output_file}: {e}")
