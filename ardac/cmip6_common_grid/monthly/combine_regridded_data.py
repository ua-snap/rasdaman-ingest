"""Script to combine regridded CMIP6 data for ingestion into rasdaman. 
This is just a simple wrapper for xarray's open_mfdataset function. 
It is assumed that the data has already been regridded and is stored in the following 
directory structure: <model>/<scenario>/<frequency (table ID)>/<variable ID>/<filename>. 
The script will combine all files for all models, scenarios, and the supplied temporal frequency and the supplied variables into a single xarray dataset and write to disk.

example usage:
  python combine_for_rasdaman.py --var_group_id v1_1 --frequency mon --regrid_dir /beegfs/CMIP6/kmredilla/cmip6_regridding/regrid --rasda_dir /beegfs/CMIP6/kmredilla/cmip6_regridding/rasdaman_ready
"""

import argparse
import numpy as np
import xarray as xr
from pathlib import Path
from config import var_group_id_lu


def get_var_ids(var_group_id):
    """Var_group_id is a string that contains the variable group ID, e.g. v1, v2, etc.
    This is just a mapping that will use the config.py file."""

    var_ids = var_group_id_lu[var_group_id]

    return var_ids


def get_models(regrid_dir):
    """Get a list of models from the regridded data directory."""
    return [d.name for d in regrid_dir.glob("*")]


def get_scenarios(regrid_dir, model):
    """Get a list of scenarios for a given model from the regridded model data directory."""
    return [d.name for d in regrid_dir.joinpath(model).glob("*")]


def get_files(var_ids, model, scenario, frequency, regrid_dir):
    """Get a list of file paths for a given model, scenario, frequency, and variable IDs."""
    fps = []
    missing_variables = []

    for var_id in var_ids:
        var_files = list(
            regrid_dir.glob(f"{model}/{scenario}/*{frequency}/{var_id}/*.nc")
        )
        if len(var_files) > 0:
            fps.extend(var_files)
        else:
            missing_variables.append(var_id)

    return fps, missing_variables


def add_missing_variable(ds, var_id):
    """Add a missing variable to the dataset."""
    nan_arr = np.empty((ds["time"].size, ds["lon"].size, ds["lat"].size))
    nan_arr[:] = np.nan
    empty_da = xr.DataArray(
        nan_arr, coords=[ds["time"], ds["lon"], ds["lat"]], dims=["time", "lon", "lat"]
    )
    ds[var_id] = empty_da
    ds[var_id].encoding = {
        "dtype": np.float64,
        "zlib": False,
        "szip": False,
        "zstd": False,
        "bzip2": False,
        "blosc": False,
        "shuffle": False,
        "complevel": 0,
        "fletcher32": False,
        "contiguous": True,
        "chunksizes": None,
        "original_shape": (ds["time"].shape[0], ds["lon"].shape[0], ds["lat"].shape[0]),
        "_FillValue": np.nan,
        "coordinates": "spatial_ref",
    }

    return ds


def add_missing_variables(ds, missing_variables):
    """wrapper for add_missing_variables to add a list of missing variables to the dataset."""
    for var_id in missing_variables:
        ds = add_missing_variable(ds, var_id)

    return ds


def open_and_combine(
    var_group_id, model, scenario, frequency, regrid_dir, rasda_dir, no_clobber
):
    """Rasda_dir is the directory where the combined dataset will be written to disk."""
    var_ids = get_var_ids(var_group_id)

    out_fp = rasda_dir.joinpath(f"{model}_{scenario}_{frequency}_{var_group_id}.nc")

    if no_clobber and out_fp.exists():
        print(f"File {out_fp} already exists and no_clobber was supplied, skipping.")
        return

    fps, missing_variables = get_files(var_ids, model, scenario, frequency, regrid_dir)
    assert len(fps) > 0, f"No files found for {model}, {scenario}, {frequency}."

    ds = xr.open_mfdataset(
        fps,
        coords="all",
        compat="override",
        preprocess=lambda x: x.drop_vars(["spatial_ref", "height"], errors="ignore"),
    )

    ds = add_missing_variables(ds, missing_variables)

    assert all(
        var_id in ds.data_vars for var_id in var_ids
    ), "Missing variables from combined dataset."

    ds.to_netcdf(out_fp)
    print(
        f"Combined data for {var_group_id} variables, {model}, {scenario}, {frequency} temporal resolution written to {out_fp}."
    )


def run_open_and_combine_for_all_groups(
    var_group_id, frequency, regrid_dir, rasda_dir, no_clobber
):
    """Run the open_and_combine function for all model-scenario groups available in the regridded data directory."""
    models = get_models(regrid_dir)

    for model in models:
        for scenario in get_scenarios(regrid_dir, model):
            open_and_combine(
                var_group_id,
                model,
                scenario,
                frequency,
                regrid_dir,
                rasda_dir,
                no_clobber,
            )


def parse_args():

    parser = argparse.ArgumentParser(
        description="Combine regridded CMIP6 data for ingestion into rasdaman."
    )
    parser.add_argument(
        "--var_group_id", type=str, help="Variable group ID, one of v1_1, v1_2."
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
    parser.add_argument(
        "--no_clobber",
        action="store_true",
        default=False,
        help="Do not overwrite existing files in rasda_dir.",
    )

    args = parser.parse_args()

    return (
        args.var_group_id,
        args.frequency,
        Path(args.regrid_dir),
        Path(args.rasda_dir),
        args.no_clobber,
    )


if __name__ == "__main__":

    var_group_id, frequency, regrid_dir, rasda_dir, no_clobber = parse_args()

    run_open_and_combine_for_all_groups(
        var_group_id, frequency, regrid_dir, rasda_dir, no_clobber
    )
