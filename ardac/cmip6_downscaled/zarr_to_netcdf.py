#!/usr/bin/env python3
import xarray as xr
import pandas as pd


def convert_zarr_to_netcdf(zarr_files, output_path):
    combined_ds = xr.Dataset()
    for file in zarr_files:
        ds = xr.open_zarr(file)
        scenario = file.split("_")[-2]
        ds.attrs["scenario"] = scenario

        ds = ds.expand_dims({"scenario": [scenario]})
        combined_ds = (
            xr.concat([combined_ds, ds], dim="scenario") if combined_ds else ds
        )

    combined_ds = combined_ds.drop_vars(["lat", "lon"])

    # For Rasdaman WMS compatibility.
    combined_ds = combined_ds.transpose("time", "scenario", "x", "y")
    combined_ds = combined_ds.sortby(combined_ds.y, ascending=False)

    combined_ds.to_netcdf(output_path, encoding={"tasmax": {"_FillValue": -9999.0}})


if __name__ == "__main__":
    zarr_files = [
        "adjusted/tasmax_HadGEM3-GC31-MM_historical_adjusted.zarr",
        "adjusted/tasmax_HadGEM3-GC31-MM_ssp126_adjusted.zarr",
        "adjusted/tasmax_HadGEM3-GC31-MM_ssp585_adjusted.zarr",
    ]

    output_file = "tasmax_HadGEM3-GC31-MM.nc"

    convert_zarr_to_netcdf(zarr_files, output_file)
    print(f"Converted Zarr files to NetCDF: {output_file}")
    print("Conversion complete.")
