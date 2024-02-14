import os
import xarray as xr

# Specify the directory where the NetCDF files are stored
data_dir = "CMIP6_Indicators/"

# Get a list of all NetCDF files in the directory that contain 'historical' in the file name (historical data)
files = [f for f in os.listdir(data_dir) if f.endswith(".nc") and "historical" in f]

datasets = list()

# Loop over the files, open each one, and add it to the list of datasets
for file in files:
    ds = xr.open_dataset(data_dir + file)
    datasets.append(ds)

# Merge all the datasets
historical_combined_ds = xr.merge(datasets)

# Specify the output file name for the combined NetCDF file
output_file = "cmip6_indicators_historical.nc"

# Save the combined dataset to a new NetCDF file
historical_combined_ds.to_netcdf(output_file)

# Close all the datasets
for ds in datasets:
    ds.close()

# Close the datasets
historical_combined_ds.close()

# Get a list of all NetCDF files in the directory that contain 'ssp' in the file name (projected data)
files = [f for f in os.listdir(data_dir) if f.endswith(".nc") and "ssp" in f]

datasets = list()

# Loop over the files, open each one, and add it to the list of datasets
for file in files:
    ds = xr.open_dataset(data_dir + file)
    datasets.append(ds)

# Merge all the datasets
projected_combined_ds = xr.merge(datasets)

# Specify the output file name for the combined NetCDF file
output_file = "cmip6_indicators_projected.nc"

# Save the combined dataset to a new NetCDF file
projected_combined_ds.to_netcdf(output_file)

# Close all the datasets
for ds in datasets:
    ds.close()

# Close the datasets
projected_combined_ds.close()

# Combine the historical and projected datasets
hp_combined_ds = xr.merge(
    [
        xr.open_dataset("cmip6_indicators_historical.nc"),
        xr.open_dataset("cmip6_indicators_projected.nc"),
    ]
)

# Specify the output file name for the final combined NetCDF file
output_file = "cmip6_indicators.nc"

# Save the combined dataset to a new NetCDF file
hp_combined_ds.to_netcdf(output_file)

# Close the datasets
hp_combined_ds.close()
