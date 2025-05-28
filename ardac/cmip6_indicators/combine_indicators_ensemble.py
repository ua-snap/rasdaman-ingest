"""Script to combine CMIP6 indicators data for ingestion into rasdaman.
This will combine all CMIP6 indicator files into one netCDF, storing variables as data_vars and computing an ensemble mean for all variables.
It is assumed that the indicators have already been computed and stored in the following
directory structure: <model>/<scenario>/<indicator ID>/<filename>.
The script will combine all files for supplied models, scenarios, and indicators into a single xarray dataset and write to disk.

example usage:
  python combine_indicators_ensemble.py --models 'all' --scenarios 'all' --indicators 'all' --indicators_dir /beegfs/CMIP6/jdpaul3/cmip6_indicators_test/cmip6_indicators/netcdf --rasda_dir /beegfs/CMIP6/jdpaul3/cmip6_indicators_for_rasdaman
"""

import argparse
import sys
import subprocess
import xarray as xr
import rioxarray
from pathlib import Path
from datetime import datetime
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

    if vars == "all":
        vars = list(cmip6_indicator_attrs.keys())
    else:
        vars = vars.split()
        validate_args_against_dict(vars, cmip6_indicator_attrs)

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
    """Update global attributes for the dataset.
    These will be applied in the preprocess_ds() function."""

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


# TODO flesh out the functions


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
