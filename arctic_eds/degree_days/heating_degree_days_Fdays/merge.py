import os
import glob
import tqdm
import argparse
import rasterio as rio
import xarray as xr
import numpy as np
import pandas as pd


def merge(directory_path):
    output_path = os.path.join(os.getcwd(), "heating_degree_days_Fdays.nc")
    os.chdir(directory_path)

    # list all the files in the directory
    # assumption is they've been unzipped
    data_fps = glob.glob("*.tif")
    data_di = {}

    # read in the data, store it in a dictionary
    for fp in tqdm.tqdm(data_fps):
        fn = fp.split(".tif")[0]
        data_di[fn] = {}
        fn_components = fn.split("_")
        data_di[fn]["model"] = fn_components[2]
        data_di[fn]["scenario"] = fn_components[3]
        data_di[fn]["year"] = fn_components[-2]

        with rio.open(fp) as src:

            arr = src.read(1)
            arr[np.isnan(arr)] = -9999.0
            data_di[fn]["arr"] = arr

    # get x and y dimensions from a single file
    with rio.open(data_fps[0]) as src:
        src_meta = src.meta.copy()
        # get x and y coordinates for axes
        y = np.array([src.xy(i, 0)[1] for i in np.arange(src.height)])
        x = np.array([src.xy(0, j)[0] for j in np.arange(src.width)])
        # get the number of pixels
        ny, nx = src.height, src.width

    # set up a multidimensional array, fill it with nodata values
    # 150 years, 10 models, 3 scenarios (includes daymet 'model' and historical 'scenario'
    arr_shape = (10, 3, 150, ny, nx)
    out_arr = np.full(arr_shape, -9999.0, dtype=np.int32)

    # "null" array for invalid coordinates: a 2D slice of the nodata filled array
    null_arr = out_arr[
        0,
        0,
        0,
    ].copy()

    # convenience - easier to query this than a nested dict
    df = pd.DataFrame.from_dict(data_di).sort_index().T
    years = list(np.unique(df["year"]))
    # these come alphabetically sorted by case and this fine for scenarios
    # but we want the daymet 'model' to be the zeroth axis coordinate
    scenarios = list(np.unique(df["scenario"]))
    models = list(np.unique(df["model"]))
    models.remove("daymet")
    models.insert(0, "daymet")

    # start layering actual data into the correct coordinates of the output array
    # we have to iterate model, then scenario, then year to mimic out_arr's shape
    for model, model_coordinate in zip(models, range(out_arr.shape[0])):
        for scenario, scenario_coordinate in zip(scenarios, range(out_arr.shape[1])):
            for year, year_coordinate in zip(years, range(out_arr.shape[2])):
                query = "year == @year & model == @model & scenario == @scenario"
                try:
                    # get the actual data for this year, model, and scenario
                    sub_arr = df.query(query)["arr"].values[0]
                except IndexError:
                    # if the data doesn't exist, use the null array
                    sub_arr = null_arr.copy()
                out_arr[model_coordinate, scenario_coordinate, year_coordinate] = (
                    sub_arr
                )

    # again just need to make sure order matches how we initialized the array
    dim_names = ["model", "scenario", "year", "y", "x"]

    ds = xr.Dataset(
        data_vars={"heating_degree_days_Fdays": (dim_names, out_arr)},
        coords={
            "model": [x[0] for x in enumerate(models)],
            "scenario": [x[0] for x in enumerate(scenarios)],
            "year": [int(x) for x in years],
            "y": y,
            "x": x,
        },
        attrs={"units": "Fahrenheit Degree Days"},
    )

    # test that data is the same in the xr.dataset and the raster
    test_slice = ds.sel(year=2099, model=3, scenario=2).heating_degree_days_Fdays
    with rio.open(
        f"ncar_12km_{models[3]}_{scenarios[2]}_heating_degree_days_2099_Fdays.tif"
    ) as src:
        test_arr = src.read(1)
    assert (test_slice.data == test_arr).all()

    # Define the CRS as EPSG:3338
    crs_dict = {"crs": "EPSG:3338"}

    # Add the CRS as an attribute to the dataset
    ds.attrs.update(crs_dict)

    ds.to_netcdf(output_path)
    print(f"NetCDF file created at: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process GeoTIFF files to create a combined NetCDF heating_degree_days_Fdays.nc."
    )
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        help="Directory containing the GeoTIFF files",
        default=None,
    )
    args = parser.parse_args()

    # If the user didn't enter the directory as an argument then prompt for it
    directory_path = args.directory or input(
        "Please provide the directory path for the GeoTIFF files: "
    )
    merge(directory_path)
