"""Script to combine CMIP6 indicators data for ingestion into rasdaman.
This will combine all CMIP6 indicator files into one netCDF, storing variables as data_vars and computing an ensemble mean for all variables.
It is assumed that the indicators have already been computed and stored in the following
directory structure: <model>/<scenario>/<indicator ID>/<filename>.
The script will combine all files for supplied models, scenarios, and indicators into a single xarray dataset and write to disk.

example usage:
  python combine_indicators_ensemble.py --models 'all' --scenarios 'all' --indicators 'all' --indicators_dir /path/to/input/files --rasda_dir /path/to/output/files
"""

import argparse
import sys
import subprocess
import xarray as xr
import rioxarray
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from dask.distributed import Client
from luts import (
    cmip6_models,
    cmip6_scenarios,
    cmip6_indicator_attrs,
    description_fmt_str,
    title_fmt_str,
    global_attrs,
)


def validate_all_args(models, scenarios, indicators, indicators_dir, rasda_dir):
    """Validate all input arguments for the script."""

    # validate dirs
    if not rasda_dir.exists():
        rasda_dir.mkdir()
    if not indicators_dir.exists():
        sys.exit(f"Directory not found: {indicators_dir}")

    # validate models/scenarios/vars
    if models == "all":
        models = list(cmip6_models.keys())
        models.remove("Ensemble")  # drop "Ensemble" from models list
    else:
        models = models.split()
        validate_args_against_dict(models, cmip6_models)

    if scenarios == "all":
        scenarios = list(cmip6_scenarios.keys())
    else:
        scenarios = scenarios.split()
        validate_args_against_dict(scenarios, cmip6_scenarios)

    if indicators == "all":
        indicators = list(cmip6_indicator_attrs.keys())
    else:
        indicators = indicators.split()
        validate_args_against_dict(indicators, cmip6_indicator_attrs)

    return models, scenarios, indicators, indicators_dir, rasda_dir


def validate_args_against_dict(input_list, cmip6_dict):
    """Validate a list of arguments against a list derived from dictionary keys."""

    for item in input_list:
        if item not in list(cmip6_dict.keys()):
            sys.exit(
                f"Input {item} not allowed. Must be one of {list(cmip6_dict.keys())}"
            )
        else:
            pass


def update_global_attrs(global_attrs, models, scenarios, indicators):
    """Update global attributes for the dataset."""

    title = title_fmt_str.format(
        models=", ".join(models),
        scenarios=", ".join(scenarios),
        indicators=", ".join(indicators),
    )
    description = description_fmt_str.format(
        models=", ".join(models),
        number_of_models=len(models),
        scenarios=", ".join(scenarios),
        indicators=", ".join(indicators),
    )
    global_attrs["title"] = title
    global_attrs["description"] = description

    return global_attrs


def get_files(indicator, model, scenario, indicators_dir):
    """Get a list of file paths for a given model, scenario, and indicator."""

    var_fps = list(indicators_dir.glob(f"{model}/{scenario}/{indicator}/*.nc"))

    return var_fps


def list_all_files(indicators, models, scenarios, indicators_dir):
    """Get all file paths for a list of models, list of scenarios, and list of indicators."""

    fps = []
    for model in models:
        for scenario in scenarios:
            for indicator in indicators:
                fps.extend(get_files(indicator, model, scenario, indicators_dir))
    print(f"Found {len(fps)} files to combine...")

    return fps


def replace_indicator_attrs(ds, cmip6_indicator_attrs):
    """Replace the indicator attributes in the dataset."""

    for var_id in ds.data_vars:
        if var_id in cmip6_indicator_attrs.keys():

            # remove existing attributes
            if ds[var_id].attrs is None:
                ds[var_id].attrs = {}
            else:
                # clear existing attributes
                ds[var_id].attrs.clear()

            # remove existing encoding
            ds[var_id].encoding.clear()

            # add new attributes from cmip6_var_attrs
            for k, v in cmip6_indicator_attrs[var_id].items():
                # skip "dtype" and "precision" as they are handled separately
                if k not in ["dtype", "precision"]:
                    ds[var_id].attrs[k] = v
    return ds


def open_and_combine(fps):
    """Open and combine a list of file paths into a single xarray dataset. To avoid indexing errors with the time dimension,
    we will separate historical and projected data, open them separately, and then combine them.
    """

    print(f"Combining files ... started at: {datetime.now().isoformat()}")
    hist_files = [file for file in fps if "historical" in file.name]
    proj_files = [file for file in fps if "ssp" in file.name]
    with Client(n_workers=4, threads_per_worker=6) as client:
        hist_ds = xr.open_mfdataset(hist_files)
        hist_ds = hist_ds.load()

        proj_ds = xr.open_mfdataset(proj_files)
        proj_ds = proj_ds.load()

    ds = xr.merge([hist_ds, proj_ds], combine_attrs="drop_conflicts")

    return ds


def convert_time(ds):
    """Convert the 'year' coordinate to a CF-compliant 'time' coordinate."""

    years = ds["year"].values.astype(int)
    # Reference date for CF time
    ref_date = pd.Timestamp("1950-01-01")
    # Create datetime index for January 1st of each year
    times = pd.to_datetime(years, format="%Y")
    # Calculate days since reference date
    days_since_ref = (times - ref_date).days
    # Assign new coordinate values and rename 'year' to 'time'
    ds = ds.assign_coords(year=("year", days_since_ref))
    ds = ds.rename({"year": "time"})
    ds["time"].attrs["units"] = "days since 1950-01-01 00:00:00"
    ds["time"].attrs["calendar"] = "standard"
    ds["time"].attrs["long_name"] = "time"
    ds["time"].attrs["standard_name"] = "time"
    ds["time"].attrs["min_value"] = ds["time"].min().values
    ds["time"].attrs["max_value"] = ds["time"].max().values

    return ds


def compute_ensemble_mean(ds):
    """Compute the ensemble mean for a dataset."""

    print("Computing ensemble mean...started at: ", datetime.now().isoformat())
    # Compute ensemble mean and ensure it does not share memory with ds
    ensemble_mean = ds.mean(dim="model", skipna=True)
    # Set the model coordinate for the ensemble mean
    ensemble_mean = ensemble_mean.expand_dims(model=["Ensemble"])
    # Concatenate along the model dimension
    ds_with_ensemble = xr.concat([ds, ensemble_mean], dim="model")

    return ds_with_ensemble


def enforce_dtypes_and_precision(ds, cmip6_indicator_attrs):
    """Enforce dtypes and precision for the dataset variables using the attributes in the lookup table."""

    for var in ds.data_vars:
        if var not in ["spatial_ref"]:
            if "dtype" in cmip6_indicator_attrs[var]:
                # validate that the dtype is OK - if not, skip the conversion but warn the user
                if cmip6_indicator_attrs[var]["dtype"] not in [
                    "int32",
                    "float32",
                    "float64",
                ]:
                    print(
                        f"Warning: dtype {ds[var].encoding['dtype']} for variable {var} is not supported. Skipping conversion."
                    )
                    pass
                # If converting to integer, set nodata to -9999 before conversion
                if cmip6_indicator_attrs[var]["dtype"].startswith("int"):
                    nodata_val = cmip6_indicator_attrs[var]["_FillValue"]
                    ds[var] = ds[var].where(~np.isnan(ds[var]), nodata_val)
                # round before dtype conversion
                ds[var] = ds[var].round(cmip6_indicator_attrs[var]["precision"])
                ds[var] = ds[var].astype(cmip6_indicator_attrs[var]["dtype"])

    return ds


def map_integers(ds, cmip6_models, cmip6_scenarios):
    """Map model and scenario strings to integers from luts.py dictionarys for rasdaman ingestion."""

    # check if dataset models and scenarios are in the dictionaries
    if not all([i in cmip6_models.keys() for i in ds["model"].values]):
        sys.exit(
            f"At least one model name in dataset not found in models_dict: {ds['model'].values} must be one of {list(cmip6_models.keys())}"
        )
    if not all([i in cmip6_scenarios.keys() for i in ds["scenario"].values]):
        sys.exit(
            f"At least one scenario name in dataset not found in scenarios_dict: {ds['scenario'].values} must be one of {list(cmip6_scenarios.keys())}"
        )

    ds["model"] = [cmip6_models[i] for i in ds["model"].values]
    ds["scenario"] = [cmip6_scenarios[i] for i in ds["scenario"].values]

    return ds


def replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios):
    """Replace the model and scenario dimensions with integer values for rasdaman ingestion."""

    # remove "bounds", "title", "type" attributes from time, lat, and lon if they exist
    for dim in ["time", "lat", "lon"]:
        ds[dim].attrs.pop("bounds", None)
        ds[dim].attrs.pop("title", None)
        ds[dim].attrs.pop("type", None)

    # reverse the model and scenario dictionaries
    model_dict = {v: k for k, v in cmip6_models.items()}
    scenario_dict = {v: k for k, v in cmip6_scenarios.items()}

    # then drop any keys that are not actually in the dataset
    model_dict = {k: v for k, v in model_dict.items() if k in ds["model"].values}
    scenario_dict = {
        k: v for k, v in scenario_dict.items() if k in ds["scenario"].values
    }

    # then add the encoding dictionaries, units, and name to the attributes
    ds["model"].attrs["long_name"] = "model"
    ds["model"].attrs["units"] = "1"  # denotes dimensionless unit under CF conventions
    ds["model"].attrs["encoding"] = str(model_dict)

    ds["scenario"].attrs["long_name"] = "scenario"
    ds["scenario"].attrs[
        "units"
    ] = "1"  # denotes dimensionless unit under CF conventions
    ds["scenario"].attrs["encoding"] = str(scenario_dict)

    return ds


def replace_lat_lon_attrs(ds):
    """Replace the latitude and longitude attributes with standard CF attributes.
    This function assumes that the latitude and longitude coordinates are named 'lat' and 'lon' respectively.
    It also updates the attributes to include min_value and max_value derived from the data.
    """

    ds["lat"].attrs = {}
    ds["lon"].attrs = {}

    ds["lat"].attrs.update(
        {
            "standard_name": "latitude",
            "long_name": "latitude",
            "units": "degrees_north",
            "axis": "Y",
            "min_value": ds["lat"].min().values,
            "max_value": ds["lat"].max().values,
        }
    )

    ds["lon"].attrs.update(
        {
            "standard_name": "longitude",
            "long_name": "longitude",
            "units": "degrees_east",
            "axis": "X",
            "min_value": ds["lon"].min().values,
            "max_value": ds["lon"].max().values,
        }
    )

    return ds


def transpose_dims(ds):
    """Transpose the dataset dimensions to have the order: model, scenario, time, lon, lat.
    Lon, lat order is necessary Rasdaman WMS styles to work. Also sort latitude in descending order.
    """

    ds = ds.transpose("model", "scenario", "time", "lon", "lat")
    ds = ds.sortby(ds.lat, ascending=False)

    return ds


def add_crs(ds, crs):
    """Add a CRS to the dataset using rioxarray."""

    ds = ds.rio.set_spatial_dims("lon", "lat")
    ds = ds.rio.write_crs(crs)  # this creates the "spatial_ref" coordinate

    return ds


def run_cf_checks(fp):
    """Run CF checks on the dataset, and print output to a text file."""
    print("Running CF checks on the output file...")

    output_fp = fp.with_suffix(".cfchecks.txt")
    with open(output_fp, "w") as out_file:
        subprocess.run(["cfchecks", str(fp)], stdout=out_file, stderr=subprocess.STDOUT)
    print("CF checks run, output saved to", output_fp)

    return None


def parse_args():

    parser = argparse.ArgumentParser(
        description="Combine CMIP6 indicators for ingestion into rasdaman."
    )
    parser.add_argument(
        "--models",
        type=str,
        help="[ ]-separated string of model names (e.g. 'CESM2 GFDL-ESM4'), or 'all' for all models.",
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        help="[ ]-separated list of scenario names (e.g. 'historical ssp585'), or 'all' for all scenarios.",
    )
    parser.add_argument(
        "--indicators",
        type=str,
        help="[ ]-separated list of indicator names (e.g. 'dw su'), or 'all' for all indicators.",
    )
    parser.add_argument(
        "--indicators_dir", type=str, help="Directory where indicators data is stored."
    )
    parser.add_argument(
        "--rasda_dir",
        type=str,
        help="Directory where combined data will be written to disk.",
    )

    args = parser.parse_args()

    return {
        "models": args.models,
        "scenarios": args.scenarios,
        "indicators": args.indicators,
        "indicators_dir": Path(args.indicators_dir),
        "rasda_dir": Path(args.rasda_dir),
    }


if __name__ == "__main__":

    models, scenarios, indicators, indicators_dir, rasda_dir = validate_all_args(
        **parse_args()
    )

    global_attrs = update_global_attrs(global_attrs, models, scenarios, indicators)

    fps = list_all_files(indicators, models, scenarios, indicators_dir)
    ds = open_and_combine(fps)
    ds = convert_time(ds)
    ds = compute_ensemble_mean(ds)
    ds = enforce_dtypes_and_precision(ds, cmip6_indicator_attrs)
    ds = map_integers(ds, cmip6_models, cmip6_scenarios)
    ds = replace_indicator_attrs(ds, cmip6_indicator_attrs)
    ds.attrs = global_attrs  # replace any global attributes with our own
    ds = replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios)
    ds = replace_lat_lon_attrs(ds)
    ds = transpose_dims(ds)
    ds = add_crs(ds, "EPSG:4326")

    out_fp = rasda_dir / f"cmip6_indicators_ensemble.nc"
    print(
        f"Writing combined dataset with ensemble mean to {out_fp}... started at: {datetime.now().isoformat()}"
    )

    ds.to_netcdf(out_fp, engine="netcdf4", format="NETCDF4")

    print("Done ... ended at : ", datetime.now().isoformat())
    print("Dataset written to disk at: ", out_fp)

    ds.close()

    # run CF checks on the output file
    run_cf_checks(out_fp)
