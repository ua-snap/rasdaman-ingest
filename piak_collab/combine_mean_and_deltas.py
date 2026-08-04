import xarray as xr
import numpy as np
from pathlib import Path


def parse_delta_filename(filename):
    """
    Parse the delta filename to extract model, position, scenario, and season.
    Example: ACCESS-CM2_ANNUAL_delta_pct_END_ssp126.nc
    """
    # Remove the _delta_pct suffix and .nc extension
    name = filename.replace(".nc", "")

    # Split by underscore
    parts = name.split("_")

    if len(parts) >= 5:
        model = parts[0]
        season = parts[1]
        # Skip parts[2] which is "delta"
        type  = parts[3]  # "pct" or "abs"
        position = parts[4]
        scenario = parts[5]
        return model, season, type, position, scenario
    else:
        raise ValueError(f"Unexpected delta filename format: {filename}")


def parse_mean_filename(filename):
    """
    Parse the mean filename to extract model, position, scenario, and season.
    Example: ACCESS-CM2_END_ssp126_DRY_mean.nc
    """
    # Remove the _mean.nc suffix
    name = filename.replace("_mean.nc", "")

    # Split by underscore
    parts = name.split("_")

    if len(parts) >= 4:
        model = parts[0]
        position = parts[1]
        scenario = parts[2]
        season = parts[3]
        return model, position, scenario, season
    elif len(parts) == 3:
        model = parts[0]
        position = parts[1] # HIST
        scenario = parts[1] # HIST
        season = parts[2]
        return model, position, scenario, season
    else:
        raise ValueError(f"Unexpected mean filename format: {filename}")


def read_netcdf_with_xarray(filepath):
    """
    Read a NetCDF file using xarray and return the data and metadata.
    """
    ds = xr.open_dataset(filepath)

    # Get the first data variable (assuming there's one main variable)
    var_names = list(ds.data_vars)
    if not var_names:
        raise ValueError(f"No data variables found in {filepath}")

    var_name = var_names[1]
    data_array = ds[var_name]

    # Convert to numpy array
    data = data_array.values

    # Squeeze out any extra dimensions (like time=1)
    if data.ndim > 2:
        data = np.squeeze(data)

    # Get coordinate information - look for spatial coordinates
    x_coord_name = None
    y_coord_name = None

    # First try to find coordinates by name
    for coord in ds.coords:
        coord_lower = coord.lower()
        coord_data = ds[coord]
        # Skip datetime coordinates
        if np.issubdtype(coord_data.dtype, np.datetime64):
            continue
        if coord_lower in ['lon', 'longitude', 'x']:
            x_coord_name = coord
        elif coord_lower in ['lat', 'latitude', 'y']:
            y_coord_name = coord

    # If not found, look at the data variable's coordinates
    if x_coord_name is None or y_coord_name is None:
        for coord in data_array.coords:
            coord_lower = coord.lower()
            coord_data = ds[coord]
            if np.issubdtype(coord_data.dtype, np.datetime64):
                continue
            if coord_lower in ['lon', 'longitude', 'x'] and x_coord_name is None:
                x_coord_name = coord
            elif coord_lower in ['lat', 'latitude', 'y'] and y_coord_name is None:
                y_coord_name = coord

    # If still not found, use dimensions as a last resort
    if x_coord_name is None or y_coord_name is None:
        dims = list(data_array.dims)
        # Filter out time dimensions
        spatial_dims = []
        for dim in dims:
            if dim in ds.coords:
                dim_data = ds[dim]
                if not np.issubdtype(dim_data.dtype, np.datetime64):
                    spatial_dims.append(dim)
            else:
                spatial_dims.append(dim)

        if len(spatial_dims) >= 2:
            y_coord_name = spatial_dims[-2]
            x_coord_name = spatial_dims[-1]

    if x_coord_name is None or y_coord_name is None:
        raise ValueError(
            f"Could not find valid spatial coordinates in {filepath}. "
            f"Available coords: {list(ds.coords)}, dims: {list(data_array.dims)}"
        )

    x_coords = ds[x_coord_name].values
    y_coords = ds[y_coord_name].values

    # Ensure coordinates are numeric
    if not np.issubdtype(x_coords.dtype, np.number):
        raise ValueError(f"X coordinate '{x_coord_name}' is not numeric: {x_coords.dtype}")
    if not np.issubdtype(y_coords.dtype, np.number):
        raise ValueError(f"Y coordinate '{y_coord_name}' is not numeric: {y_coords.dtype}")

    # Get CRS if available
    crs = None
    if 'crs' in ds.attrs:
        crs = ds.attrs['crs']
    elif 'spatial_ref' in ds:
        crs = ds['spatial_ref'].attrs.get('spatial_ref', None)

    ds.close()

    return data, x_coords, y_coords, crs


def combine_netcdf_files(deltas_dir, means_dir):
    """
    Combine all delta and mean NetCDF files into a single file with both variables.
    """
    deltas_path = Path(deltas_dir)
    means_path = Path(means_dir)

    delta_files = sorted(deltas_path.glob("*_delta_*_*.nc"))
    mean_files = sorted(means_path.glob("*_mean.nc"))

    if not delta_files:
        raise ValueError(f"No delta NetCDF files found in {deltas_dir}")
    if not mean_files:
        raise ValueError(f"No mean NetCDF files found in {means_dir}")

    # Hard-code dimension values to ensure correct order
    models = [
        "ACCESS-CM2",
        "ACCESS-ESM1-5",
        "BCC-CSM2-MR",
        "CanESM5",
        "CMCC-ESM2",
        "CNRM-CM6-1",
        "CNRM-ESM2-1",
        "EC-Earth3",
        "EC-Earth3-Veg-LR",
        "FGOALS-g3",
        "GFDL-CM4",
        "GFDL-ESM4",
        "GISS-E2-1-G",
        "HadGEM3-GC31-LL",
        "HadGEM3-GC31-MM",
        "INM-CM4-8",
        "INM-CM5-0",
        "IPSL-CM6A-LR",
        "KACE-1-0-G",
        "KIOST-ESM",
        "MIROC6",
        "MIROC-ES2L",
        "MPI-ESM1-2-HR",
        "MPI-ESM1-2-LR",
        "MRI-ESM2-0",
        "NESM3",
        "NorESM2-LM",
        "NorESM2-MM",
        "TaiESM1",
        "UKESM1-0-LL"
    ]
    positions = ["HIST", "MID", "END"]
    mean_scenarios = ["HIST", "ssp126", "ssp245", "ssp370", "ssp585"]
    delta_types = ["pct", "abs"]
    delta_scenarios = ["ssp126", "ssp245", "ssp370", "ssp585"]
    seasons = ["ANNUAL", "DRY", "WET"]

    # Read first file to get spatial dimensions
    first_data, x_coords, y_coords, crs = read_netcdf_with_xarray(str(delta_files[0]))
    # Take only the first band if multiple bands exist
    if first_data.ndim == 3:
        first_data = first_data[0]
    n_y, n_x = first_data.shape

    # Ensure coordinates are clean (no NaN/Inf) and proper float type
    x_coords = x_coords.astype(np.float64)
    y_coords = y_coords.astype(np.float64)

    # Check for invalid values in coordinates
    if np.any(np.isnan(x_coords)) or np.any(np.isinf(x_coords)):
        raise ValueError(f"Lon coordinates contain invalid values (NaN or Inf)")
    if np.any(np.isnan(y_coords)) or np.any(np.isinf(y_coords)):
        raise ValueError(f"Lat coordinates contain invalid values (NaN or Inf)")

    # Create empty arrays for combined data
    delta_shape = (
        len(models),
        len(positions),
        len(delta_types),
        len(delta_scenarios),
        len(seasons),
        n_y,
        n_x,
    )
    mean_shape = (
        len(models),
        len(positions),
        len(mean_scenarios),
        len(seasons),
        n_y,
        n_x,
    )
    delta_data = np.full(delta_shape, np.nan, dtype=np.float64)
    mean_data = np.full(mean_shape, np.nan, dtype=np.float64)

    # Process delta files
    print("\n=== Processing Delta Files ===")
    for nc_file in delta_files:
        print(f"Processing {nc_file.name}...")
        model, season, type, position, scenario = parse_delta_filename(nc_file.name)

        # Find indices
        model_idx = models.index(model)
        position_idx = positions.index(position)
        type_idx = delta_types.index(type)
        scenario_idx = delta_scenarios.index(scenario)
        season_idx = seasons.index(season)

        # Read data
        data, _, _, _ = read_netcdf_with_xarray(str(nc_file))

        # Take only the first band if multiple bands exist
        if data.ndim == 3:
            data = data[0]

        # Store in combined array
        delta_data[model_idx, position_idx, type_idx, scenario_idx, season_idx, :, :] = data

    # Process mean files
    print("\n=== Processing Mean Files ===")
    for nc_file in mean_files:
        print(f"Processing {nc_file.name}...")
        model, position, scenario, season = parse_mean_filename(nc_file.name)

        # Find indices
        model_idx = models.index(model)
        position_idx = positions.index(position)
        scenario_idx = mean_scenarios.index(scenario)
        season_idx = seasons.index(season)

        # Read data
        data, _, _, _ = read_netcdf_with_xarray(str(nc_file))

        # Take only the first band if multiple bands exist
        if data.ndim == 3:
            data = data[0]

        # Store in combined array
        mean_data[model_idx, position_idx, scenario_idx, season_idx, :, :] = data

    # Create xarray Dataset
    print("\n=== Creating xarray Dataset ===")

    # Shift longitudes from 0-360 to -180-180 and reorder data along Lon axis.
    lon_shifted = np.where(x_coords > 180.0, x_coords - 360.0, x_coords).astype(np.float64)
    lon_sort_idx = np.argsort(lon_shifted)
    x_coords = lon_shifted[lon_sort_idx]
    delta_data = delta_data[..., lon_sort_idx]
    mean_data = mean_data[..., lon_sort_idx]

    # Convert NaN values to -9999 before writing (ensure float type is maintained)
    delta_data = np.where(np.isnan(delta_data), -9999.0, delta_data).astype(np.float64)
    mean_data = np.where(np.isnan(mean_data), -9999.0, mean_data).astype(np.float64)

    # Split delta data by type dimension (pct=0, abs=1)
    delta_pct_data = delta_data[:, :, 0, :, :, :, :]  # type index 0 = "pct"
    delta_abs_data = delta_data[:, :, 1, :, :, :, :]  # type index 1 = "abs"

    # Create the DataArrays
    delta_pct_array = xr.DataArray(
        delta_pct_data,
        dims=["model", "position", "scenario", "season", "Lat", "Lon"],
        coords={
            "model": models,
            "position": positions,
            "scenario": delta_scenarios,
            "season": seasons,
            "Lat": y_coords,
            "Lon": x_coords,
        },
        name="delta_pct",
    )

    delta_abs_array = xr.DataArray(
        delta_abs_data,
        dims=["model", "position", "scenario", "season", "Lat", "Lon"],
        coords={
            "model": models,
            "position": positions,
            "scenario": delta_scenarios,
            "season": seasons,
            "Lat": y_coords,
            "Lon": x_coords,
        },
        name="delta_abs",
    )

    mean_array = xr.DataArray(
        mean_data,
        dims=["model", "position", "scenario", "season", "Lat", "Lon"],
        coords={
            "model": models,
            "position": positions,
            "scenario": mean_scenarios,
            "season": seasons,
            "Lat": y_coords,
            "Lon": x_coords,
        },
        name="mean",
    )

    # Create combined Dataset with all three variables
    output_file = "combined_mean_and_deltas.nc"
    print(f"Saving combined dataset to {output_file}...")
    combined_ds = xr.Dataset({
        "mean": mean_array,
        "delta_pct": delta_pct_array,
        "delta_abs": delta_abs_array
    })

    if crs:
        combined_ds.attrs["crs"] = str(crs)

    combined_ds = combined_ds.sortby("Lat", ascending=False)

    encoding = {
        "mean": {"_FillValue": -9999.0, "dtype": "float64", "zlib": True, "complevel": 4},
        "delta_pct": {"_FillValue": -9999.0, "dtype": "float64", "zlib": True, "complevel": 4},
        "delta_abs": {"_FillValue": -9999.0, "dtype": "float64", "zlib": True, "complevel": 4},
        "Lat": {"dtype": "float64", "_FillValue": None},
        "Lon": {"dtype": "float64", "_FillValue": None}
    }
    combined_ds.to_netcdf(output_file, encoding=encoding)
    print(f"Successfully created {output_file}")

if __name__ == "__main__":
    # Set paths
    deltas_dir = "deltas"
    means_dir = "means"

    # Combine files
    combine_netcdf_files(deltas_dir, means_dir)
