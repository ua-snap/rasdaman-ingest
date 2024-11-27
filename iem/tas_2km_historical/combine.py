import xarray as xr
import glob
import os

# Define the list of possible models and months
months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]

# Directory where the NetCDF files are located
data_dir = "/usr/local/data/torgerso/historicaltemperature/tas"


for month in months:
    # Initialize empty lists for each variable
    tas_list = []
    tasmax_list = []
    tasmin_list = []

    # Find NetCDF files matching the naming convention in the specified directory
    tas_file = os.path.join(data_dir, f"tas_{month}_temperature.nc")
    tasmax_file = os.path.join(data_dir, f"tasmax_{month}_temperature.nc")
    tasmin_file = os.path.join(data_dir, f"tasmin_{month}_temperature.nc")

    # Open and append variables to respective lists if files exist
    if os.path.exists(tas_file):
        tas_list.append(xr.open_dataset(tas_file)["tas"])
    if os.path.exists(tasmax_file):
        tasmax_list.append(xr.open_dataset(tasmax_file)["tasmax"])
    if os.path.exists(tasmin_file):
        tasmin_list.append(xr.open_dataset(tasmin_file)["tasmin"])

    # Concatenate variables along the 'year' dimension in chunks
    combined_tas = xr.concat(tas_list, dim="year")
    combined_tasmax = xr.concat(tasmax_list, dim="year")
    combined_tasmin = xr.concat(tasmin_list, dim="year")

    # Create a new dataset with the modified variables
    combined_dataset = xr.Dataset(
        {"tas": combined_tas, "tasmax": combined_tasmax, "tasmin": combined_tasmin}
    )

    # Save the combined dataset to a new NetCDF file in the specified directory
    output_filename = os.path.join(data_dir, f"combined_{month}_temperature.nc")
    combined_dataset.to_netcdf(output_filename, format="NETCDF4", mode="w")

    print(f"Combined and saved {output_filename}")

print("All files combined successfully.")
