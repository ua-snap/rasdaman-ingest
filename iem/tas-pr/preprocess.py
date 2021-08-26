"""
Preprocess SNAP's 771m AR5 and CRU TS temperature and precipitation data for ingest in Rasdaman, 
intended for serving in a webapp which exposes IEM inputs and outputs.

Creates a netCDF of mean summaries over period, model, scenario, and season for AR5 data, 
and over the entire historical period for CRU TS data.

The goal is to create a completely inclusive datacube of both historical and projected data. 
It will have the following dimensions for both tas and pr variables:
* period
* season
* model
* scenario
* Y
* X
These variables should be encoded according to ./README.md.

The resulting netCDF is written to $BASE_DIR/ar5_cruts31_tas_pr_decadal_seasonal_aggregated.nc

See ./README.md for help running this script.

Note - this runs in about 20 minutes with 30 cores and ~260GB of RAM.. may be 
substantially slower on less performant hardware...
"""


import itertools
import os
import time
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio as rio
import xarray as xr
from rasterio.warp import transform


def aggregate_gtiffs(fps):
    """Aggregate input geotiffs into a single file
    by taking the mean across axis 0 (decade)

    Args:
        fps (list): filepaths to GeoTIFFs to be aggregated

    Returns:
        dict of aggregated values in 2D array with associated dimension values

    Notes:
        fps will be a list of 3 filepaths for projected data 
        (periods are 3 decades long) and 10 filepaths for historical data
        (10 decades long)
    """
    data = []
    for fp in fps:
        with rio.open(fp) as src:
            data.append(src.read(1))

    # take mean of arrays
    arr = np.array(data)
    # use nodata value to set nans (to be ignored for aggregation)
    #   (although not necessary if individual pixels are all
    #   NaN or not NaN across all group combinations)
    arr[np.isclose(arr, nodata)] = np.nan
    with warnings.catch_warnings():
        # ignore warnings for mean of empty slice
        warnings.simplefilter("ignore", category=RuntimeWarning)
        arr = np.nanmean(arr, axis=0)

    # update nodata values
    arr[np.isnan(arr)] = new_nodata

    # get dimension information from an input filename
    #   about the raster for reference
    fn_components = Path(fps[0]).name.split(".tif")[0].split("_")
    varname, decade_start, season, model, scenario = [
        fn_components[i] for i in [0, -2, 3, -4, -3]
    ]

    if model == "TS31":
        period = "1910_2009"
    else:
        period = f"{decade_start}_{int(decade_start) + 30}"

    out_di = {
        "arr": arr,
        "varname": varname,
        "period": period,
        "season": season,
        "model": model,
        "scenario": scenario,
    }

    return out_di


def run_quality_check():
    """Run brief quality check that the aggregation 
    matches for a single AR5 period subset

    Args:
        None, makes use of global variables defined before

    Returns:
        Bool for whether or not the computed means of the test files match
          what was computed in ar5_aggr_out
    """
    k = 0
    test_fps = args[k]
    first_fp = test_fps[0]
    fp_tags = first_fp.split(".")[-2].split("_")
    # assumes ...<firstyear>_<lastyear>.tif
    first_year = int(fp_tags[-2])
    last_year = first_year + 29

    new_arr = np.zeros((3, src_meta["height"], src_meta["width"]))
    for i in np.arange(3):
        with rio.open(test_fps[i]) as src:
            new_arr[i] = src.read(1)
    # "top left" pixel shoudl be nodata
    new_arr[new_arr == new_arr[0, 0, 0]] = np.nan
    # set test case arr nodata back to -9999 for comparison
    test_arr = aggr_out[k]["arr"].copy()
    test_arr[np.isnan(test_arr)] = new_nodata

    with warnings.catch_warnings():
        # ignore warnings for mean of empty slice
        warnings.simplefilter("ignore", category=RuntimeWarning)
        new_aggr_arr = np.nanmean(new_arr, axis=0)

    new_aggr_arr[np.isnan(new_aggr_arr)] = -9999.0
    # use np.isclose because result of np.nanmean(should have more
    #   (not true precision but just as artifact of processing)(why though?))
    qc_result = np.all(np.isclose(test_arr, new_aggr_arr))

    return qc_result


def rm_var(di):
    """Helper to remove the varname key from 
    aggregation output dict

    Args:
        di (dict): dict from *aggr_out results

    Returns:
        dict without the "varname" key
    """
    del di["varname"]
    return di


def make_arr_from_aggr(aggr, dimnames):
    """Make the array structured according to the various axes
    to create an xarray.DataArray from
    
    Args:
        aggr (dict): dict returned from aggregating GeoTIFFs data subset
        dimnames (list): list of dimension names

    Returns:
        Datacube organized according to the correct dimension order

    Notes:

    We need an array shaped exactly according to the dimensions 
      to be used in the xarray.DataArrays/.DataSet
    Not sure the best way to do this, but here we start with an 
      empty array of correct shape to then populate
    """
    #
    # create empty array
    ny, nx = aggr[0]["arr"].shape
    arr_shape = (
        len(list(periods_lu.keys())),
        len(seasons),
        len(models),
        len(scenarios),
        ny,
        nx,
    )
    out_arr = np.full(arr_shape, -9999, dtype=np.float32)
    null_arr = out_arr[0, 0, 0, 0].copy()

    # restructure data for indexing by dimension names
    df = pd.DataFrame(aggr).set_index(dimnames).sort_index()

    # run nested loop to correctly populate empty array
    for period, pn in zip(periods, range(arr_shape[0])):
        for season, sn in zip(seasons, range(arr_shape[1])):
            for model, mn in zip(models, range(arr_shape[2])):
                for scenario, cn in zip(scenarios, range(arr_shape[3])):
                    try:
                        sub_arr = df.loc[(period, season, model, scenario)]["arr"]
                    except KeyError:
                        # this should occur for invalid dim combinations
                        #   (e.g. model=CCSM4 and scenario=historical) and
                        #   thus needs an array of null values
                        sub_arr = null_arr.copy()
                    out_arr[pn, sn, mn, cn] = sub_arr

    return out_arr


if __name__ == "__main__":
    # get env vars and set up file structure
    base_dir = Path(os.getenv("BASE_DIR"))
    ar5_in_fn = os.getenv("AR5_GTIFF_FOLDER")
    cru_in_fn = os.getenv("CRU_GTIFF_FOLDER")
    ar5_in_dir = base_dir.joinpath(ar5_in_fn)
    cru_in_dir = base_dir.joinpath(cru_in_fn)
    ar5_in_fp = ar5_in_dir.joinpath("{0}_decadal_mean_{1}_{4}_{2}_{3}_{5}.tif")
    cru_in_fp = cru_in_dir.joinpath(
        "{0}_decadal_mean_{1}_{2}_cru_TS31_historical_{3}.tif"
    )

    ncores = int(os.getenv("NCORES"))
    # Specify all group combinations to generate file paths,
    #   and run the aggregation in parallel.
    ar5_decades = [
        f"{decade_start}_{decade_start + 9}"
        for decade_start in np.arange(2010, 2091, 10)
    ]
    cru_decades = [
        f"{decade_start}_{decade_start + 9}"
        for decade_start in np.arange(1910, 2001, 10)
    ]
    periods = ["2040_2070", "2070_2100", "1910_2009"]
    periods_lu = {
        periods[0]: ar5_decades[3:6],
        periods[1]: ar5_decades[-3:],
        periods[2]: cru_decades,
    }
    models = ["CCSM4", "MRI-CGCM3", "TS31"]
    scenarios = ["rcp45", "rcp60", "rcp85", "historical"]
    seasons = ["DJF", "MAM", "JJA", "SON"]
    varnames = ["tas", "pr"]
    units_lu = {varnames[0]: "mean_c", varnames[1]: "total_mm"}

    # get metadata and set warping params from a file for
    #   reprojecting and writing individual rasters
    temp_fp = str(ar5_in_fp).format(
        varnames[0],
        seasons[0],
        models[0],
        scenarios[0],
        units_lu[varnames[0]],
        ar5_decades[0],
    )
    with rio.open(temp_fp) as src:
        src_meta = src.meta.copy()
        # get x and y coordinates for axes
        y = np.array([src.xy(i, 0)[1] for i in np.arange(src.height)])
        x = np.array([src.xy(0, j)[0] for j in np.arange(src.width)])
        # will set nodata to -9999 instead of current,
        # need to save current nodata though
        nodata = src_meta["nodata"]

    # set new nodata value of -9999 for later use
    new_nodata = -9999.0

    dim_encodings = {
        "tas": 0,
        "pr": 1,
        "2040_2070": 0,
        "2070_2100": 1,
        "1910_2009": 2,
        "DJF": 0,
        "MAM": 1,
        "JJA": 2,
        "SON": 3,
        "CCSM4": 0,
        "MRI-CGCM3": 1,
        "TS31": 2,
        "rcp45": 0,
        "rcp60": 1,
        "rcp85": 2,
        "historical": 3,
    }

    args = []
    # create filepaths from the different dimension options
    ar5_dim_opts = list(
        # subset the above lists to be only valid AR5 combinations
        itertools.product(varnames, periods[:2], seasons, models[:2], scenarios[:3])
    )
    for dim_tpl in ar5_dim_opts:
        run_decades = periods_lu[dim_tpl[1]]
        varname = dim_tpl[0]
        fps = [
            str(ar5_in_fp).format(varname, *dim_tpl[2:], units_lu[varname], decade)
            for decade in run_decades
        ]
        args.append(fps)

    # create args for aggregating historical data
    cru_dim_opts = list(itertools.product(varnames, seasons))
    for dim_tpl in cru_dim_opts:
        run_decades = periods_lu["1910_2009"]
        fps = [
            str(cru_in_fp).format(dim_tpl[0], dim_tpl[1], units_lu[dim_tpl[0]], decade)
            for decade in run_decades
        ]
        args.append(fps)

    print(f"Aggregating decadal means using {ncores} cores...")
    start_tic = time.perf_counter()
    with Pool(ncores) as p:
        tic = time.perf_counter()
        aggr_out = p.map(aggregate_gtiffs, args)
    print(f"Aggregation done, elapsed time: {round(time.perf_counter() - tic, 1)}s")

    # Do a quick quality control check that output for
    #   a single variable-period-model-scenario-season
    #   matches mean of expected input rasters
    print("Conducting a brief QC on the aggregates", sep="...")
    tic = time.perf_counter()
    qc_result = run_quality_check()
    print(f"QC complete, {round(time.perf_counter() - tic, 1)}s.")
    print("Test array matches subject array: ", qc_result)

    # Create an xarray.DataSet from the aggregated array result dicts
    print("Creating xarray.DataSet from aggregated arrays")
    tic = time.perf_counter()

    # separate out tas and pr arrays
    tas_aggr = [rm_var(di.copy()) for di in aggr_out if di["varname"] == "tas"]
    pr_aggr = [rm_var(di.copy()) for di in aggr_out if di["varname"] == "pr"]
    # then reshape the cubes according to dimension
    dimnames = ["period", "season", "model", "scenario"]
    tas_arr = make_arr_from_aggr(tas_aggr, dimnames)
    pr_arr = make_arr_from_aggr(pr_aggr, dimnames)

    print(f"done, {round(time.perf_counter() - tic, 1)}s.")
    tic = time.perf_counter()

    xy_dimnames = ["y", "x"]
    dimnames.extend(xy_dimnames)
    ds = xr.Dataset(
        data_vars={"tas": (dimnames, tas_arr), "pr": (dimnames, pr_arr),},
        coords={
            "period": [dim_encodings[period] for period in periods],
            "season": [dim_encodings[season] for season in seasons],
            "model": [dim_encodings[model] for model in models],
            "scenario": [dim_encodings[scenario] for scenario in scenarios],
            "y": y,
            "x": x,
        },
        attrs={},
    )

    print("Writing to netCDF", sep="...")
    tic = time.perf_counter()
    # specify encoding to compress
    encoding = {
        "tas": {"zlib": True, "complevel": 9, "_FillValue": -9999.0},
        "pr": {"zlib": True, "complevel": 9, "_FillValue": -9999.0},
    }

    out_fp = base_dir.joinpath("ar5_cruts31_tas_pr_decadal_seasonal_aggregated.nc")
    ds.to_netcdf(out_fp, encoding=encoding)

    print(
        f"NetCDF created, written to {out_fp}, {round(time.perf_counter() - tic, 1)}s."
    )
    print(f"Elapsed time preprocessing: {round(time.perf_counter() - start_tic, 1)}s.")
