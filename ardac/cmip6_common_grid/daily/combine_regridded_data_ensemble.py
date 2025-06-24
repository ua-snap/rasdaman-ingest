"""Script to combine regridded CMIP6 data for ingestion into rasdaman.
This will combine all CMIP6 daily files into one netCDF, storing variables as data_vars and computing an ensemble mean for all variables.
It is assumed that the data has already been regridded and is stored in the following
directory structure: <model>/<scenario>/<frequency (table ID)>/<variable ID>/<filename>.
The script will combine all files for supplied models, scenarios, temporal frequency, variables into a single xarray dataset and write to disk.

example usage:
  python combine_regridded_data_ensemble.py --models 'all' --scenarios 'all' --vars 'pr tasmin tasmax' --frequency 'day' --regrid_dir /beegfs/CMIP6/jdpaul3/cmip6_regrid_timefix --rasda_dir /beegfs/CMIP6/jdpaul3/cmip6_regrid_for_rasdaman
"""

import argparse
import sys
import subprocess
import xarray as xr
import rioxarray
from pathlib import Path
from datetime import datetime
from dask.distributed import Client
import numpy as np
from luts import (
    cmip6_models,
    cmip6_scenarios,
    cmip6_var_attrs,
    description_fmt_str,
    title_fmt_str,
    global_attrs,
)


def validate_all_args(models, scenarios, vars, frequency, regrid_dir, rasda_dir):
    """Validate all input arguments for the script."""

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
        validate_args_against_dict(models, cmip6_models)

    if scenarios == "all":
        scenarios = list(cmip6_scenarios.keys())
    else:
        scenarios = scenarios.split()
        validate_args_against_dict(scenarios, cmip6_scenarios)

    if vars == "all":
        vars = list(cmip6_var_attrs.keys())
    else:
        vars = vars.split()
        validate_args_against_dict(vars, cmip6_var_attrs)

    # validate frequency
    if frequency not in ["mon", "day"]:
        sys.exit(f"{frequency} not allowed. Must be 'mon' or 'day'.")

    return models, scenarios, vars, frequency, regrid_dir, rasda_dir


def validate_args_against_dict(input_list, cmip6_dict):
    """Validate a list of arguments against a list derived from dictionary keys."""

    for item in input_list:
        if item not in list(cmip6_dict.keys()):
            sys.exit(
                f"Input {item} not allowed. Must be one of {list(cmip6_dict.keys())}"
            )
        else:
            pass


def update_global_attrs(global_attrs, models, scenarios, vars, frequency):
    """Update global attributes for the dataset.
    These will be applied in the preprocess_ds() function."""

    freq_str = (
        "Monthly" if frequency == "mon" else "Daily" if frequency == "day" else None
    )

    title = title_fmt_str.format(
        frequency=freq_str,
        models=", ".join(models),
        scenarios=", ".join(scenarios),
        variables=", ".join(vars),
    )
    description = description_fmt_str.format(
        frequency=freq_str,
        models=", ".join(models),
        number_of_models=len(models),
        scenarios=", ".join(scenarios),
        variables=", ".join(vars),
    )
    global_attrs["title"] = title
    global_attrs["description"] = description

    return global_attrs


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


def pull_dims_from_source(ds):
    """Pull dimensions from the source attribute of the dataset.
    If dataset variable id does not match the filename variable id, rename it.
    (This allows for datasets with generic variable names like "data" to be used,
    as long as their filepath starts with the variable id.)
    """

    var = list(ds.data_vars)[0]  # assume first var is the one we want
    src = ds[var].encoding["source"]
    fp_var_id = src.split("/")[-1].split("_")[
        0
    ]  # assumes filename begins with the var id
    if var != fp_var_id:
        ds = ds.rename({var: fp_var_id})

    # get model and scenario from filepath and add these to the dataset as dimensions
    fp_model = src.split("/")[-1].split("_")[
        2
    ]  # assumes filename has model name in third position
    fp_scenario = src.split("/")[-1].split("_")[
        3
    ]  # assumes filename has model name in fourth position

    # add model and scenario to dataset as dimensions using an array with one value each
    ds = ds.expand_dims({"model": [fp_model], "scenario": [fp_scenario]})

    return ds


def replace_var_attrs(ds, cmip6_var_attrs):
    """Replace the variable attributes in the dataset."""

    for var_id in ds.data_vars:
        if var_id in cmip6_var_attrs.keys():

            # remove existing attributes
            if ds[var_id].attrs is None:
                ds[var_id].attrs = {}
            else:
                # clear existing attributes
                ds[var_id].attrs.clear()

            # remove existing encoding
            ds[var_id].encoding.clear()

            # add new attributes from cmip6_var_attrs
            for k, v in cmip6_var_attrs[var_id].items():
                # skip "dtype" and "precision" as they are handled separately
                if k not in ["dtype", "precision"]:
                    ds[var_id].attrs[k] = v
    return ds


def preprocess_ds(ds):
    """Peforms functions to fix datasets as they are opened."""

    ds = pull_dims_from_source(ds)
    # drop global encoding and attributes that are not needed
    ds.encoding = {}
    ds.attrs = {}

    return ds


def reindex_and_rechunk(ds, chunks):
    """Reindex the dataset to include all models and scenarios, and rechunk it for efficient processing."""

    all_models = ds["model"].values
    all_scenarios = ds["scenario"].values
    for var in ds.data_vars:
        ds[var] = ds[var].reindex(model=all_models, scenario=all_scenarios)
        # explicitly rechunk to align dask chunks for all variables
        chunks["model"] = len(all_models)
        chunks["scenario"] = len(all_scenarios)
        ds[var] = ds[var].chunk(chunks)

    print("Dataset opened and combined successfully with chunks:")
    print(ds.chunks)

    return ds


def compute_ensemble_mean(ds):
    """Compute the ensemble mean for a dataset."""

    ensemble_mean = ds.mean(dim="model")
    ensemble_mean = ensemble_mean.expand_dims(model=["Ensemble"])
    ds_with_ensemble = xr.concat([ds, ensemble_mean], dim="model")

    return ds_with_ensemble


def enforce_dtypes_and_precision(ds, cmip6_var_attrs):
    """Enforce dtypes and precision for the dataset variables using the attributes in the lookup table."""

    for var in ds.data_vars:
        if var not in ["spatial_ref"]:
            if "dtype" in cmip6_var_attrs[var]:
                # validate that the dtype is OK - if not, skip the conversion but warn the user
                if cmip6_var_attrs[var]["dtype"] not in ["int32", "float32", "float64"]:
                    print(
                        f"Warning: dtype {ds[var].encoding['dtype']} for variable {var} is not supported. Skipping conversion."
                    )
                    pass
                # If converting to integer, set nodata to -9999 before conversion
                if cmip6_var_attrs[var]["dtype"].startswith("int"):
                    nodata_val = cmip6_var_attrs[var]["_FillValue"]
                    ds[var] = ds[var].where(~np.isnan(ds[var]), nodata_val)
                # round before dtype conversion
                ds[var] = ds[var].round(cmip6_var_attrs[var]["precision"])
                ds[var] = ds[var].astype(cmip6_var_attrs[var]["dtype"])

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
    """Transpose the dataset dimensions to have the order: model, scenario, time, lat, lon.
    This is necessary for CF conventions."""

    ds = ds.transpose("model", "scenario", "time", "lat", "lon")

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

    return {
        "models": args.models,
        "scenarios": args.scenarios,
        "vars": args.vars,
        "frequency": args.frequency,
        "regrid_dir": Path(args.regrid_dir),
        "rasda_dir": Path(args.rasda_dir),
    }


if __name__ == "__main__":

    start_time = datetime.now()
    print("Starting script at: ", start_time.isoformat())

    chunks = {"time": 120}

    models, scenarios, vars, frequency, regrid_dir, rasda_dir = validate_all_args(
        **parse_args()
    )

    global_attrs = update_global_attrs(global_attrs, models, scenarios, vars, frequency)

    with Client(
        n_workers=7,  # 7 workers × 4 threads = 28 cores (28 cores available on the node)
        threads_per_worker=4,
        memory_limit="17GB",  # 7 × 17GB = 119GB (128GB available), leaves some headroom for OS/other processes
        dashboard_address=":8787",
    ) as client:

        var_datasets = []

        for var in vars:
            print(f"Combining files for {var} ...")
            fps = list_all_files([var], models, scenarios, frequency, regrid_dir)

            var_ds = xr.open_mfdataset(
                fps,
                drop_variables=["spatial_ref", "height", "type"],
                preprocess=preprocess_ds,
                parallel=True,
                combine="by_coords",
                engine="h5netcdf",  # use h5netcdf for better performance with reading large datasets
                decode_cf=True,
                coords="minimal",
                compat="no_conflicts",
                chunks=chunks,
            )

            var_datasets.append(var_ds)

        print("Merging variable datasets...")
        ds = xr.merge(var_datasets, compat="no_conflicts", combine_attrs="override")

        ds = reindex_and_rechunk(ds, chunks)
        ds = compute_ensemble_mean(ds)
        ds = enforce_dtypes_and_precision(ds, cmip6_var_attrs)
        ds = map_integers(ds, cmip6_models, cmip6_scenarios)
        ds = replace_var_attrs(ds, cmip6_var_attrs)
        ds.attrs = global_attrs
        ds = replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios)
        ds = replace_lat_lon_attrs(ds)
        ds = transpose_dims(ds)
        ds = add_crs(ds, "EPSG:4326")

        #combine vars as "_" separated string
        var_str = "_".join(sorted(vars)) 

        out_fp = rasda_dir / f"cmip6_regrid_{frequency}_{var_str}_ensemble.nc"
        print(f"Writing combined dataset with ensemble mean to {out_fp}...")
        # use netcdf4 engine for better performance with complex merge operations
        # h5netcdf engine is not as performant for writing large datasets, tends to duplicate dims
        ds.to_netcdf(out_fp, engine="netcdf4", mode="w", format="NETCDF4")

        end_time = datetime.now()
        print("Done ... ended at : ", end_time.isoformat())
        print("Elapsed time: ", str(end_time - start_time))
        print("Dataset written to disk at: ", out_fp)

        ds.close()

    # run CF checks on the output file
    run_cf_checks(out_fp)
