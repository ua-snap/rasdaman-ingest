#!/usr/bin/env python3
import xarray as xr
import os
import sys
from pprint import pprint

input_dir = os.environ.get("NETCDF_DIR")
output_dir = os.environ.get("MEAN_DIR")
os.makedirs(output_dir, exist_ok=True)

varnames = ["tasmax", "tasmin", "pr"]

# These are the only models that have all possible variables/models/scenarios,
# excluding GFDL-ESM4 which has known issues. Include only models with all
# scenarios present so comparisons between *ModelAvg scenarios is
# apples-to-apples (the mean of the same set of models).
models = [
    "KACE-1-0-G",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MRI-ESM2-0",
    "NorESM2-MM",
    "TaiESM1",
]


def generate_input_file_dict(varname, input_dir):
    # Get a list of all *.nc files in input_dir.
    nc_files = [
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.startswith(f"{varname}_") and f.endswith(".nc")
    ]

    nc_files = [
        f
        for f in nc_files
        if not os.path.basename(f).startswith("dtr")
    ]

    input_dict = {}
    for file in nc_files:
        basename = os.path.basename(file)
        parts = basename.split("_")
        varname = parts[0]
        model = parts[1]
        scenario = parts[2]
        key = f"{varname}_{scenario}"

        if model not in models:
            continue

        # Get list of all files with model as substring in them.
        model_files = [f for f in nc_files if model in f]

        # All models specified in "models" variable should have five scenarios:
        # historical, ssp126, ssp245, ssp370, ssp585. Abort script if any
        # scenarios are missing because this will impact the means.
        if len(model_files) < 5:
            print(f"Files missing for {model} model. Aborting.")
            exit(1)

        if scenario not in input_dict:
            input_dict[scenario] = []
        input_dict[scenario].append(file)

    # Sort the values in input_dict for each scenario.
    for scenario in input_dict:
        input_dict[scenario] = sorted(input_dict[scenario])

    return input_dict


def calculate_and_write_model_means(input_dict, netcdf_dir):
    num_models = len(input_dict["historical"])

    # Example implementation: open each NetCDF file, compute mean, and save to netcdf
    for scenario, files in input_dict.items():
        datasets = [xr.open_dataset(f) for f in files]
        combined = xr.concat(datasets, dim="model")
        mean_ds = combined.mean(dim="model")
        out_path = os.path.join(
            netcdf_dir, f"{varname}_{num_models}ModelAvg_{scenario}_adjusted.nc"
        )
        mean_ds.to_netcdf(out_path)
        print(f"Saved mean for scenario '{scenario}' to {out_path}")


if __name__ == "__main__":
    for varname in varnames:
        input_dict = generate_input_file_dict(varname, input_dir)
        calculate_and_write_model_means(input_dict, output_dir)
