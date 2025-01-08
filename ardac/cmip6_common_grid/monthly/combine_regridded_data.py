"""Script to combine regridded CMIP6 data for ingestion into rasdaman. 
This is just a simple wrapper for xarray's open_mfdataset function to just group all yearly files into single years. 
It is assumed that the data has already been regridded and is stored in the following 
directory structure: <model>/<scenario>/<frequency (table ID)>/<variable ID>/<filename>. 
The script will combine all files for all models, scenarios, and the supplied temporal frequency and the supplied variables into a single xarray dataset and write to disk.

example usage:
  python combine_regridded_data.py --var_group_id v1_1 --frequency mon --regrid_dir /beegfs/CMIP6/kmredilla/cmip6_regridding/regrid --rasda_dir /beegfs/CMIP6/kmredilla/cmip6_regridding/rasdaman_ready
"""

import argparse
import numpy as np
import xarray as xr
from pathlib import Path
from luts import var_group_id_lu


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


def get_files(var_id, model, scenario, frequency, regrid_dir):
    """Get a list of file paths for a given model, scenario, frequency, and variable ID."""
    var_fps = list(regrid_dir.glob(f"{model}/{scenario}/*{frequency}/{var_id}/*.nc"))

    return var_fps


def get_var_ids(var_group_id):
    """Var_group_id is a string that contains the variable group ID, e.g. v1, v2, etc.
    This is just a mapping that will use the config.py file."""

    var_ids = var_group_id_lu[var_group_id]

    return var_ids


def open_and_combine(
    var_id, model, scenario, frequency, regrid_dir, rasda_dir, no_clobber
):
    """Rasda_dir is the directory where the combined dataset will be written to disk."""
    out_fp = rasda_dir.joinpath(f"{var_id}_{model}_{scenario}_{frequency}.nc")

    if no_clobber and out_fp.exists():
        print(f"File {out_fp} already exists and no_clobber was supplied, skipping.")
        return

    fps = get_files(var_id, model, scenario, frequency, regrid_dir)
    if not len(fps) > 0:
        print(
            f"No files found for {var_id}, {model}, {scenario}, {frequency}. Skipping."
        )
        return

    ds = xr.open_mfdataset(
        fps,
        coords="all",
        compat="override",
        preprocess=lambda x: x.drop_vars(["spatial_ref", "height"], errors="ignore"),
    )

    assert var_id in ds.data_vars

    # all files should have same data variable name for ingestion into rasdaman
    ds = ds.rename({var_id: "data"})

    # ensure it is float type for consistency
    ds["data"] = ds["data"].astype(np.float32)

    ds.to_netcdf(out_fp)
    print(
        f"Combined data for {var_id}, {model}, {scenario}, {frequency} temporal resolution written to {out_fp}."
    )


def run_open_and_combine_for_all_groups(
    var_group_id, frequency, regrid_dir, rasda_dir, no_clobber
):
    """Run the open_and_combine function for all model-scenario groups available in the regridded data directory."""
    models = get_models(regrid_dir)

    for model in models:
        for scenario in get_scenarios(regrid_dir, model):
            for var_id in get_var_ids(var_group_id):
                open_and_combine(
                    var_id,
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

    if not rasda_dir.exists():
        rasda_dir.mkdir()

    run_open_and_combine_for_all_groups(
        var_group_id, frequency, regrid_dir, rasda_dir, no_clobber
    )
