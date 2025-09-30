#!/usr/bin/env python3
import xarray as xr
import os
import sys
from pprint import pprint

varname = sys.argv[1]

input_dir = "netcdf"
output_dir = "netcdf_means"


def calculate_and_write_model_means(input_dict, netcdf_dir):
    # Example implementation: open each NetCDF file, compute mean, and save to netcdf
    for scenario, files in input_dict.items():
        datasets = [xr.open_dataset(f) for f in files]
        combined = xr.concat(datasets, dim="model")
        mean_ds = combined.mean(dim="model")
        out_path = os.path.join(
            netcdf_dir, f"{varname}_7ModelAvg_{scenario}_adjusted.nc"
        )
        mean_ds.to_netcdf(out_path)
        print(f"Saved mean for scenario '{scenario}' to {out_path}")


if __name__ == "__main__":
    # Get a list of all *.nc files in input_dir.
    nc_files = [
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.startswith(f"{varname}_") and f.endswith(".nc")
    ]

    nc_files = [f for f in nc_files if not os.path.basename(f).startswith("dtr") and not os.path.basename(f).startswith("pr_CESM2")]
    print(nc_files)

    input_dict = {}
    for file in nc_files:
        basename = os.path.basename(file)
        parts = basename.split("_")
        varname = parts[0]
        model = parts[1]
        scenario = parts[2]
        key = f"{varname}_{scenario}"

        # Get list of all files with model as substring in them.
        model_files = [f for f in nc_files if model in f]

        if len(model_files) < 5:
            continue

        if scenario not in input_dict:
            input_dict[scenario] = []
        input_dict[scenario].append(file)

    # Sort the values in input_dict for each scenario.
    for scenario in input_dict:
        input_dict[scenario] = sorted(input_dict[scenario])

    pprint(input_dict)

    calculate_and_write_model_means(input_dict, output_dir)
