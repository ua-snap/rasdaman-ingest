from pathlib import Path
import numpy as np
import xarray as xr

# Specify the directory where the NetCDF files are stored
data_dir = Path("CMIP6_Indicators/")

# merging historical and projected separately might have big efficiency gain?

# Get a list of all NetCDF files in the directory that contain 'historical' in the file name (historical data)
hist_files = list(data_dir.glob("*historical*.nc"))

datasets = list()

# Loop over the files, open each one, and add it to the list of datasets
for file in hist_files:
    ds = xr.open_dataset(file)
    datasets.append(ds)

# Merge all the datasets
historical_combined_ds = xr.merge(datasets)

# Close all the datasets
for ds in datasets:
    ds.close()

# Get a list of all NetCDF files in the directory that contain 'ssp' in the file name (projected data)
proj_files = list(data_dir.glob("*ssp*.nc"))

datasets = list()

# Loop over the files, open each one, and add it to the list of datasets
for file in proj_files:
    ds = xr.open_dataset(file)
    datasets.append(ds)

# Merge all the datasets
projected_combined_ds = xr.merge(datasets)

# Combine the historical and projected datasets
hp_combined_ds = xr.merge([historical_combined_ds, projected_combined_ds])

# latitude axis coordinates must decrease from north to south for rasdaman
hp_combined_ds = hp_combined_ds.reindex(lat=list(reversed(hp_combined_ds.lat)))
# longitude axis must come before latitude in dimension ordering
hp_combined_ds = hp_combined_ds.transpose("scenario", "model", "year", "lon", "lat")

for var_id in ["year", "ftc", "dw", "su"]:
    # change type to int32
    hp_combined_ds[var_id].data[np.isnan(hp_combined_ds[var_id])] = -9999
    hp_combined_ds[var_id] = hp_combined_ds[var_id].astype("int32") 

# Specify the output file name for the final combined NetCDF file
output_file = "cmip6_indicators.nc"

# Save the combined dataset to a new NetCDF file
hp_combined_ds.to_netcdf(output_file)
