#!/usr/bin/env python3
import xarray as xr
import os
import sys

input_dir = "netcdf"
output_dir = "wms_netcdf"

layers = {
    "tasmax": [
        {"model": "7ModelAvg", "scenario": "historical", "start_date": "2000-07-01", "end_date": "2000-07-31", "method": "mean"},
        {"model": "7ModelAvg", "scenario": "ssp585", "start_date": "2100-07-01", "end_date": "2100-07-31", "method": "mean"},
    ],
    "tasmin": [
        {"model": "7ModelAvg", "scenario": "historical", "start_date": "2000-01-01", "end_date": "2000-01-31", "method": "mean"},
        {"model": "7ModelAvg", "scenario": "ssp585", "start_date": "2100-01-01", "end_date": "2100-01-31", "method": "mean"},
    ],
    "pr": [
        {"model": "7ModelAvg", "scenario": "historical", "start_date": "2000-08-01", "end_date": "2000-08-31", "method": "sum"},
        {"model": "7ModelAvg", "scenario": "ssp585", "start_date": "2100-08-01", "end_date": "2100-08-31", "method": "sum"},
    ],
}


for varname, configs in layers.items():
    for config in configs:
        model = config["model"]
        scenario = config["scenario"]
        start_date = config["start_date"]
        end_date = config["end_date"]
        method = config["method"]

        filename = f"{varname}_{model}_{scenario}_adjusted.nc"
        filepath = os.path.join(input_dir, filename)

        if not os.path.exists(filepath):
            print(f"File {filepath} does not exist. Skipping.")
            continue

        ds = xr.open_dataset(filepath)

        # Select the time range
        ds_selected = ds.sel(time=slice(start_date, end_date))

        # Calculate mean of selected time range (temperature, etc.)
        if method == "mean":
            ds_aggr = ds_selected.mean(dim="time", skipna=True)

        # Calculate sum of selected time range (precipitation)
        if method == "sum":
            ds_aggr = ds_selected.sum(dim="time", skipna=True)

        if start_date[:7] == end_date[:7]:
            date_range = start_date[:7]
        else:
            date_range = f"{start_date[:7]}-{end_date[:7]}"

        output_filename = f"{varname}_{model}_{scenario}_{date_range}.nc"
        output_filepath = os.path.join(output_dir, output_filename)

        ds_aggr.to_netcdf(output_filepath)
        print(f"Saved mean dataset to {output_filepath}")
