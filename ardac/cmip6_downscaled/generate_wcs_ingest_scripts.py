#!/usr/bin/env python3
import json
import os

netcdf_dir = "netcdf"
output_dir = "wcs_ingest_scripts"

ensemble_models = [
    "KACE-1-0-G",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MRI-ESM2-0",
    "NorESM2-MM",
    "TaiESM1",
]

def generate_script(varname, model, scenario):
    kwargs = {
        "varname": varname,
        "model": model,
        "scenario": scenario
    }

    with open("wcs_ingest_template.json", "r") as file:
        data = json.load(file)

    coverage_id = data["input"]["coverage_id"].format(**kwargs).replace("-", "_")
    data["input"]["coverage_id"] = coverage_id

    data["input"]["paths"][0] = data["input"]["paths"][0].format(**kwargs)

    band_name = data["recipe"]["options"]["coverage"]["slicer"]["bands"][0]["name"].format(**kwargs)
    data["recipe"]["options"]["coverage"]["slicer"]["bands"][0]["name"] = band_name

    band_identifier = data["recipe"]["options"]["coverage"]["slicer"]["bands"][0]["identifier"].format(**kwargs)
    data["recipe"]["options"]["coverage"]["slicer"]["bands"][0]["identifier"] = band_identifier

    title = data["recipe"]["options"]["coverage"]["metadata"]["global"]["Title"].format(**kwargs)
    data["recipe"]["options"]["coverage"]["metadata"]["global"]["Title"] = title

    if model == "6ModelAvg":
        abstract = "6ModelAvg is an equal-weighted mean of: "
        abstract += ", ".join(ensemble_models)
        data["recipe"]["options"]["coverage"]["metadata"]["global"]["Abstract"] = abstract

    output_file = "{varname}_{model}_{scenario}_adjusted.json".format(**kwargs)
    output_path = output_dir + "/" + output_file

    with open(output_path, "w") as file:
        json.dump(data, file, indent=4)

os.makedirs(output_dir, exist_ok=True)

varnames = [
    "tasmax",
    "tasmin",
    "pr",
]

models = [
    "6ModelAvg",
    "CESM2",
    "CNRM-CM6-1-HR",
    "E3SM-2-0",
    "EC-Earth3-Veg",
    "HadGEM3-GC31-LL",
    "HadGEM3-GC31-MM",
    "KACE-1-0-G",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MRI-ESM2-0",
    "NorESM2-MM",
    "TaiESM1",
]

scenarios = [
    "historical",
    "ssp126",
    "ssp245",
    "ssp370",
    "ssp585",
]

for varname in varnames:
    for model in models:
        for scenario in scenarios:
            netcdf_path = f"netcdf/{varname}_{model}_{scenario}_adjusted.nc"
            if os.path.exists(netcdf_path):
                generate_script(varname, model, scenario)

