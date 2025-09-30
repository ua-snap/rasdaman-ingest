#!/usr/bin/env python3
import xarray as xr
import os
import sys

input_dir = "netcdf"
output_dir = "wms_netcdf"

layers = {
    "tasmax": [
        {"model": "7ModelAvg", "scenario": "historical", "start_date": "2000-07-01", "end_date": "2000-07-31"},
        {"model": "7ModelAvg", "scenario": "ssp585", "start_date": "2100-07-01", "end_date": "2100-07-31"},
    ],
    "tasmin": [
        {"model": "7ModelAvg", "scenario": "historical", "start_date": "2000-01-01", "end_date": "2000-01-31"},
        {"model": "7ModelAvg", "scenario": "ssp585", "start_date": "2100-01-01", "end_date": "2100-01-31"},
    ],
    "pr": [
        {"model": "7ModelAvg", "scenario": "historical", "start_date": "2000-08-01", "end_date": "2000-08-31"},
        {"model": "7ModelAvg", "scenario": "ssp585", "start_date": "2100-08-01", "end_date": "2100-08-31"},
    ],
}


for varname, configs in layers.items():
    for config in configs:
        model = config["model"]
        scenario = config["scenario"]
        start_date = config["start_date"]
        end_date = config["end_date"]

        # Construct the filename based on the variable, model, and scenario
        filename = f"{varname}_{model}_{scenario}_adjusted.nc"
        filepath = os.path.join(input_dir, filename)

        if not os.path.exists(filepath):
            print(f"File {filepath} does not exist. Skipping.")
            continue

        # Open the dataset
        ds = xr.open_dataset(filepath)

        # Select the time range
        ds_selected = ds.sel(time=slice(start_date, end_date))

        # Calculate the mean over the selected time range
        ds_mean = ds_selected.mean(dim="time")

        if start_date[:7] == end_date[:7]:
            date_range = start_date[:7]
        else:
            date_range = f"{start_date[:7]}-{end_date[:7]}"

        # Construct output filename
        output_filename = f"{varname}_{model}_{scenario}_mean_{date_range}.nc"
        output_filepath = os.path.join(output_dir, output_filename)

        # Save the mean dataset to a new NetCDF file
        ds_mean.to_netcdf(output_filepath)
        print(f"Saved mean dataset to {output_filepath}")