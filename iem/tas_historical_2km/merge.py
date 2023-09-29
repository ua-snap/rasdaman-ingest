import os
import glob
import numpy as np
import tqdm
import xarray as xr
import rasterio as rio
import re

# Set the working directory to the new path
os.chdir("/tmp/historical-temp/temperature/tas/")

# Create a list of all the files in the directory
files = glob.glob("*.tif")

for var_name in ["tas", "tasmax", "tasmin"]:
    for month_num in range(1, 13):
        formatted_month = f"{month_num:02}"

        # Regular expression pattern to match variable names followed by "degC" or "mm"
        variable_pattern = re.compile(
            rf"^{var_name}_mean_C_(.*?)_(.*?)_{formatted_month}_(.*?).tif$"
        )

        # No data value
        nodata_value = -9999

        # Get the projected x and y coordinates from a single geotiff
        with rio.open(files[0]) as src:
            cols, rows = np.meshgrid(np.arange(src.width), np.arange(src.height))
            xarr, yarr = rio.transform.xy(src.transform, rows, cols)
            xcoords = xarr[0]
            ycoords = np.array([a[0] for a in yarr])

        data_arrays = []
        for i, file in enumerate(tqdm.tqdm(files)):
            # Use regular expression to extract the variable name without units
            match = variable_pattern.match(file)
            if match:
                variable_name = var_name

                with rio.open(file) as src:
                    data = src.read(1, masked=True)
                    data = np.where(data.mask, -9999, data)

                data_array = xr.DataArray(
                    data=np.expand_dims(data, axis=(0)),
                    dims=["year", "y", "x"],
                    coords=dict(
                        year=(["year"], [match.group(3)]),
                        y=(["y"], ycoords),
                        x=(["x"], xcoords),
                    ),
                    name=variable_name,
                )

                data_arrays.append(data_array)

        # first combine by coordinates to create a dataset for each variable. I think this saves time when the combining dataarrays with different names (variables).
        var_datasets = []
        varnames = np.unique([da.name for da in data_arrays])
        for name in tqdm.tqdm(varnames):
            var_datasets.append(
                xr.combine_by_coords([da for da in data_arrays if da.name == name])
            )

        # then, merge the variable datasets into one single Dataset
        ds = xr.merge(var_datasets)

        # Define the CRS as EPSG:4269 or NAD83
        crs_dict = {"crs": "EPSG:3338"}

        # Add the CRS as an attribute to the dataset
        ds.attrs.update(crs_dict)

        ds.to_netcdf(f"{var_name}_{formatted_month}_temperature.nc")
