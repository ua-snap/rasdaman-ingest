import os
import glob
import numpy as np
import tqdm
import xarray as xr
import rasterio as rio
import re

# Set the working directory to the new path
os.chdir("/tmp/hydrology/zipped/total")

# Create a list of all the files in the directory
files = glob.glob("*.tif")

# Regular expression pattern to match variable names followed by "degC" or "mm"
variable_pattern = re.compile(
    r"^(.*?)_(degC|mm)_(.*?)_(.*?)_(.*?)_(mean|max|total)_(.*?)_.*$"
)

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
        variable_name = match.group(1)

    with rio.open(file) as src:
        data = src.read(1, masked=True)
        data = np.where(data.mask, -9999, data)

    data_array = xr.DataArray(
        data=np.expand_dims(data, axis=(0, 1, 2, 3)),
        dims=["model", "scenario", "year", "y", "x"],
        coords=dict(
            model=(["model"], [match.group(3)]),
            scenario=(["scenario"], [match.group(4)]),
            era=(["year"], [match.group(7)]),
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

# Define the CRS as EPSG:3338
crs_dict = {"crs": "EPSG:3338"}

# Add the CRS as an attribute to the dataset
ds.attrs.update(crs_dict)

ds.to_netcdf("hydrology.nc")
