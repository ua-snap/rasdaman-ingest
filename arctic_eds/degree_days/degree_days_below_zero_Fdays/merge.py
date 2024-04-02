import os
import glob
import numpy as np
import tqdm
import xarray as xr
import rasterio as rio
import re

# Set the working directory to the new path
# assume data were previously unzipped here by prefect
os.chdir("/tmp/degree_days/degree_days_below_zero_Fdays")

# Create a list of all the files in the directory
files = glob.glob("*.tif")

# Regular expression pattern to match model, scenario, and year
model_scenario_year_pattern = re.compile(
    r"ncar_12km_(.*?)_(.*?)_degree_days_below_zero_(.*?)_Fdays.*$"
)

# Get the projected x and y coordinates from a single geotiff
with rio.open(files[0]) as src:
    cols, rows = np.meshgrid(np.arange(src.width), np.arange(src.height))
    xarr, yarr = rio.transform.xy(src.transform, rows, cols)
    xcoords = xarr[0]
    ycoords = np.array([a[0] for a in yarr])

data_arrays = []
for i, file in enumerate(tqdm.tqdm(files)):
    # Use regular expression to extract the relevant info
    match = model_scenario_year_pattern.match(file)
  
    with rio.open(file) as src:
        data = src.read(1, masked=True)
        data = np.where(data.mask, -9999, data)

    data_array = xr.DataArray(
        data=np.expand_dims(data, axis=(0, 1, 2)),
        dims=["model", "scenario", "year", "y", "x"],
        coords=dict(
            model=(["model"], [match.group(1)]),
            scenario=(["scenario"], [match.group(2)]),
            year=(["year"], [match.group(3)]),
            y=(["y"], ycoords),
            x=(["x"], xcoords),
        ),
        name="degree_days_below_zero_Fdays",
    )

    data_arrays.append(data_array)

# merge into a single Dataset
ds = xr.combine_by_coords(data_arrays)
# Define the CRS as EPSG:3338
crs_dict = {"crs": "EPSG:3338"}

# Add the CRS as an attribute to the dataset
ds.attrs.update(crs_dict)

ds.to_netcdf("degree_days_below_zero_Fdays.nc")
