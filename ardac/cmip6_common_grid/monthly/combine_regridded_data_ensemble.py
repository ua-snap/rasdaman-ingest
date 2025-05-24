"""Script to combine regridded CMIP6 data for ingestion into rasdaman.
This will combine all CMIP6 monthly files into one netCDF, storing variables as data_vars and computing an ensemble mean for all variables.
It is assumed that the data has already been regridded and is stored in the following
directory structure: <model>/<scenario>/<frequency (table ID)>/<variable ID>/<filename>.
The script will combine all files for supplied models, scenarios, temporal frequency, variables into a single xarray dataset and write to disk.

example usage:
  python combine_regridded_data_ensemble.py --models 'all' --scenarios 'all' --vars 'all' --frequency 'mon' --regrid_dir /beegfs/CMIP6/jdpaul3/CMIP6_common_regrid/regrid --rasda_dir /beegfs/CMIP6/jdpaul3/cmip6_regrid_for_rasdaman
"""

import argparse
import sys
import xarray as xr
from pathlib import Path
from datetime import datetime
from luts import cmip6_models, cmip6_scenarios, cmip6_var_attrs, global_attrs


def validate_args(input_list, cmip6_dict):
    """Validate a list of arguments against a list derived from dictionary keys."""
    for item in input_list:
        if item not in list(cmip6_dict.keys()):
            sys.exit(
                f"Input {item} not allowed. Must be one of {list(cmip6_dict.keys())}"
            )
        else:
            pass


def get_files(var_id, model, scenario, frequency, regrid_dir):
    """Get a list of file paths for a given model, scenario, frequency, and variable ID."""
    var_fps = list(regrid_dir.glob(f"{model}/{scenario}/*{frequency}/{var_id}/*.nc"))
    return var_fps


def list_all_files(vars, models, scenarios, frequency, regrid_dir):
    """Get all file paths for a list of models, list of scenarios, frequency, and list of variables."""
    fps = []
    for model in models:
        for scenario in scenarios:
            for var_id in vars:
                fps.extend(get_files(var_id, model, scenario, frequency, regrid_dir))
    print(f"Found {len(fps)} files to combine...")
    return fps


def fix_ds(ds):
    """Peforms a number of functions to fix datasets as they are merged."""

    # ensure dtype and sort by time, trying to avoid monotonic indexing errors
    ds["time"] = ds["time"].astype("datetime64[ns]")
    ds = ds.sortby("time")

    # drop any unnecessary vars, if they exist
    ds = ds.drop_vars(["spatial_ref", "height"], errors="ignore")

    # if dataset var id does not match the filename var id, rename it
    # this allows for datasets with generic var names (like "data") to be used
    # as long as their filepath contains the var id
    var = list(ds.data_vars)[0]  # assume first var is the one we want
    src = ds[var].encoding["source"]
    fp_var_id = src.split("/")[-1].split("_")[
        0
    ]  # assumes filename begins with the var id
    if var != fp_var_id:
        ds = ds.rename({var: fp_var_id})

    # get model and scenario from filepath as well
    # and add these to the dataset as dimensions
    fp_model = src.split("/")[-1].split("_")[
        2
    ]  # assumes filename has model name in third position
    fp_scenario = src.split("/")[-1].split("_")[
        3
    ]  # assumes filename has model name in fourth position

    # add model and scenario to dataset as dimensions using an array with one value each
    ds = ds.expand_dims({"model": [fp_model], "scenario": [fp_scenario]})

    # wipe existing global attributes and replace with new ones
    ds.attrs = {}
    for k, v in global_attrs.items():
        ds.attrs[k] = v

    # wipe variable attributes and replace with new ones
    for var_id in ds.data_vars:
        if var_id in cmip6_var_attrs.keys():
            ds[var_id].attrs = {}
            for k, v in cmip6_var_attrs[var_id].items():
                ds[var_id].attrs[k] = v
    return ds


def open_and_combine(fps):
    """Open and combine a list of file paths into a single xarray dataset."""
    print(f"Combining files ... started at: {datetime.now().isoformat()}")
    ds = xr.open_mfdataset(
        fps,
        preprocess=fix_ds,
        chunks={"time": 12},
        parallel=True,
        combine="by_coords",
        engine="netcdf4",
        decode_cf=True,
        # data_vars="minimal",
        # coords="minimal",
        compat="override",
    )
    return ds


def compute_ensemble_mean(ds):
    """Compute the ensemble mean for a dataset."""
    print("Computing ensemble mean...started at: ", datetime.now().isoformat())
    ensemble_mean = ds.mean(dim="model")
    ensemble_mean = ensemble_mean.expand_dims(model=["Ensemble"])
    ds_with_ensemble = xr.concat([ds, ensemble_mean], dim="model")
    return ds_with_ensemble


def map_integers(ds, models_dict, scenarios_dict):
    """Map model and scenario strings to integers from luts.py dictionarys for rasdaman ingestion."""
    # check if dataset models and scenarios are in the dictionaries
    if not all([i in models_dict.keys() for i in ds["model"].values]):
        sys.exit(
            f"At least one model name in dataset not found in models_dict: {ds['model'].values} must be one of {list(models_dict.keys())}"
        )
    if not all([i in scenarios_dict.keys() for i in ds["scenario"].values]):
        sys.exit(
            f"At least one scenario name in dataset not found in scenarios_dict: {ds['scenario'].values} must be one of {list(scenarios_dict.keys())}"
        )

    ds_with_ensemble["model"] = [
        models_dict[i] for i in ds_with_ensemble["model"].values
    ]
    ds_with_ensemble["scenario"] = [
        scenarios_dict[i] for i in ds_with_ensemble["scenario"].values
    ]
    return ds_with_ensemble


def parse_args():

    parser = argparse.ArgumentParser(
        description="Combine regridded CMIP6 data for ingestion into rasdaman."
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
        "--vars",
        type=str,
        help="[ ]-separated list of variable names (e.g. 'pr tas'), or 'all' for all variables.",
    )
    parser.add_argument(
        "--frequency",
        type=str,
        help="Temporal resolution / frequency of data, either 'mon' or 'day'.",
    )
    parser.add_argument(
        "--regrid_dir", type=str, help="Directory where regridded data is stored."
    )
    parser.add_argument(
        "--rasda_dir",
        type=str,
        help="Directory where combined data will be written to disk.",
    )

    args = parser.parse_args()

    return (
        args.models,
        args.scenarios,
        args.vars,
        args.frequency,
        Path(args.regrid_dir),
        Path(args.rasda_dir),
    )


if __name__ == "__main__":

    # parse args
    models, scenarios, vars, frequency, regrid_dir, rasda_dir = parse_args()

    # validate dirs
    if not rasda_dir.exists():
        rasda_dir.mkdir()
    if not regrid_dir.exists():
        sys.exit(f"Directory not found: {regrid_dir}")

    # validate models/scenarios/vars
    if models == "all":
        models = list(cmip6_models.keys())
        models.remove("Ensemble")  # drop "Ensemble" from models list
    else:
        models = models.split()
        validate_args(models, cmip6_models)

    if scenarios == "all":
        scenarios = list(cmip6_scenarios.keys())
    else:
        scenarios = scenarios.split()
        validate_args(scenarios, cmip6_scenarios)

    if vars == "all":
        vars = list(cmip6_var_attrs.keys())
    else:
        vars = vars.split()
        validate_args(vars, cmip6_var_attrs)

    # validate frequency
    if frequency not in ["mon", "day"]:
        sys.exit(f"{frequency} not allowed. Must be 'mon' or 'day'.")

    # find files + combine + compute ensemble mean
    fps = list_all_files(vars, models, scenarios, frequency, regrid_dir)
    ds = open_and_combine(fps)
    ds_with_ensemble = compute_ensemble_mean(ds)

    ds_with_ensemble = map_integers(ds_with_ensemble, cmip6_models, cmip6_scenarios)

    out_fp = rasda_dir / f"cmip6_regrid_{frequency}_ensemble.nc"
    print(
        f"Writing combined dataset with ensemble mean to {out_fp}... started at: {datetime.now().isoformat()}"
    )

    ds_with_ensemble.to_netcdf(out_fp)
    print("Done ... ended at : ", datetime.now().isoformat())

    ds.close()
    ds_with_ensemble.close()
