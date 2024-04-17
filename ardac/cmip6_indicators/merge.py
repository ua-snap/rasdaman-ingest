import os
import xarray as xr
import rioxarray


def open_and_reproject_dataset(fp):
    ds = xr.open_dataset(fp)
    if "height" in ds:
        ds = ds.drop_vars("height")

    # need to drop model and scenario dims for reprojecting with rioxarray
    #  even though there should only be one of each for the dataset, they are
    #  seen as extra dims
    model = ds.model.values[0]
    scenario = ds.scenario.values[0]
    ds.sel(model=model, scenario=scenario)
    ds = ds.rio.set_spatial_dims("lon", "lat").rio.reproject(3338)
    ds = ds.assign_coords(model=model, scenario=scenario).expand_dims(
        dim=["scenario", "model"]
    )

    return ds


# Specify the directory where the NetCDF files are stored
data_dir = "CMIP6_Indicators/"

# Get a list of all NetCDF files in the directory that contain 'historical' in the file name (historical data)
files = [f for f in os.listdir(data_dir) if f.endswith(".nc") and "historical" in f]

datasets = list()

# Loop over the files, open each one, and add it to the list of datasets
for file in files:
    datasets.append(open_and_reproject_dataset(data_dir + file))

# Merge all the datasets
historical_combined_ds = xr.merge(datasets)

# Close all the datasets
for ds in datasets:
    ds.close()

# Get a list of all NetCDF files in the directory that contain 'ssp' in the file name (projected data)
files = [f for f in os.listdir(data_dir) if f.endswith(".nc") and "ssp" in f]

datasets = list()

# Loop over the files, open each one, and add it to the list of datasets
for file in files:
    datasets.append(open_and_reproject_dataset(data_dir + file))

# Merge all the datasets
projected_combined_ds = xr.merge(datasets)

# Close all the datasets
for ds in datasets:
    ds.close()

# Combine the historical and projected datasets
hp_combined_ds = xr.merge([historical_combined_ds, projected_combined_ds])

# Specify the output file name for the final combined NetCDF file
output_file = "cmip6_indicators_3338.nc"

# Save the combined dataset to a new NetCDF file
hp_combined_ds.to_netcdf(output_file)

# Close the datasets
hp_combined_ds.close()
