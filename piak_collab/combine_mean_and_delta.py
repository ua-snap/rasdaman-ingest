import os
import re
import rasterio
import xarray as xr
import numpy as np
from pathlib import Path


def parse_delta_filename(filename):
    """
    Parse the delta filename to extract model, position, scenario, and season.
    Example: ACCESS-CM2_ANNUAL_delta_pct_END_ssp126.nc
    """
    # Remove the _delta_pct suffix and .nc extension
    name = filename.replace("_delta_pct_", "_DELTAMARKER_").replace(".nc", "")

    # Split by underscore
    parts = name.split("_")

    if len(parts) >= 5:
        model = parts[0]
        season = parts[1]
        # Skip parts[2] which is "DELTAMARKER"
        position = parts[3]
        scenario = parts[4]
        return model, position, scenario, season
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
    else:
        raise ValueError(f"Unexpected mean filename format: {filename}")


def read_netcdf_with_rasterio(filepath):
    """
    Read a NetCDF file using rasterio and return the data and metadata.
    """
    with rasterio.open(filepath) as src:
        # Read all bands
        data = src.read()

        # Get nodata value and mask it
        nodata = src.nodata
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)

        # Get coordinate information
        transform = src.transform
        crs = src.crs

        # Get x and y coordinates from the bounds and resolution
        height, width = src.height, src.width

        # Create coordinate arrays using the affine transform
        # x coordinates for each column
        x_coords = np.array([transform * (col, 0) for col in range(width)])[:, 0]
        # y coordinates for each row
        y_coords = np.array([transform * (0, row) for row in range(height)])[:, 1]

        return data, x_coords, y_coords, crs


def combine_netcdf_files(deltas_dir, means_dir, output_file):
    """
    Combine all delta and mean NetCDF files into a single file with both variables.
    """
    deltas_path = Path(deltas_dir)
    means_path = Path(means_dir)
    
    delta_files = sorted(deltas_path.glob("*_delta_pct_*.nc"))
    mean_files = sorted(means_path.glob("*_mean.nc"))

    if not delta_files:
        raise ValueError(f"No delta NetCDF files found in {deltas_dir}")
    if not mean_files:
        raise ValueError(f"No mean NetCDF files found in {means_dir}")

    print(f"Found {len(delta_files)} delta files and {len(mean_files)} mean files")

    # Hard-code dimension values to ensure correct order
    models = ["ACCESS-CM2"]
    positions = ["MID", "END"]
    scenarios = ["ssp126", "ssp245", "ssp370", "ssp585"]
    seasons = ["ANNUAL", "DRY", "WET"]

    print(f"Models: {models}")
    print(f"Positions: {positions}")
    print(f"Scenarios: {scenarios}")
    print(f"Seasons: {seasons}")

    # Read first file to get spatial dimensions
    first_data, x_coords, y_coords, crs = read_netcdf_with_rasterio(str(delta_files[0]))
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
    
    # Debug: print coordinate info
    print(f"Lon range: {x_coords.min():.6f} to {x_coords.max():.6f}")
    print(f"Lat range: {y_coords.min():.6f} to {y_coords.max():.6f}")

    # Create empty arrays for combined data
    combined_shape = (
        len(models),
        len(positions),
        len(scenarios),
        len(seasons),
        n_y,
        n_x,
    )
    delta_data = np.full(combined_shape, np.nan, dtype=np.float64)
    mean_data = np.full(combined_shape, np.nan, dtype=np.float64)

    # Process delta files
    print("\n=== Processing Delta Files ===")
    for nc_file in delta_files:
        print(f"Processing {nc_file.name}...")
        model, position, scenario, season = parse_delta_filename(nc_file.name)

        # Find indices
        model_idx = models.index(model)
        position_idx = positions.index(position)
        scenario_idx = scenarios.index(scenario)
        season_idx = seasons.index(season)

        # Read data
        data, _, _, _ = read_netcdf_with_rasterio(str(nc_file))
        # Take only the first band if multiple bands exist
        if data.ndim == 3:
            data = data[0]

        # Debug: print data statistics
        print(
            f"  Mean: {np.nanmean(data):.4f}, Min: {np.nanmin(data):.4f}, Max: {np.nanmax(data):.4f}"
        )

        # Store in combined array
        delta_data[model_idx, position_idx, scenario_idx, season_idx, :, :] = data

    # Process mean files
    print("\n=== Processing Mean Files ===")
    for nc_file in mean_files:
        print(f"Processing {nc_file.name}...")
        model, position, scenario, season = parse_mean_filename(nc_file.name)

        # Find indices
        model_idx = models.index(model)
        position_idx = positions.index(position)
        scenario_idx = scenarios.index(scenario)
        season_idx = seasons.index(season)

        # Read data
        data, _, _, _ = read_netcdf_with_rasterio(str(nc_file))
        # Take only the first band if multiple bands exist
        if data.ndim == 3:
            data = data[0]

        # Debug: print data statistics
        print(
            f"  Mean: {np.nanmean(data):.4f}, Min: {np.nanmin(data):.4f}, Max: {np.nanmax(data):.4f}"
        )

        # Store in combined array
        mean_data[model_idx, position_idx, scenario_idx, season_idx, :, :] = data

    # Create xarray Dataset
    print("\n=== Creating xarray Dataset ===")

    # Convert NaN values to -9999 before writing (ensure float type is maintained)
    delta_data = np.where(np.isnan(delta_data), -9999.0, delta_data).astype(np.float64)
    mean_data = np.where(np.isnan(mean_data), -9999.0, mean_data).astype(np.float64)

    # Create the DataArrays
    delta_array = xr.DataArray(
        delta_data,
        dims=["model", "position", "scenario", "season", "Lat", "Lon"],
        coords={
            "model": models,
            "position": positions,
            "scenario": scenarios,
            "season": seasons,
            "Lat": y_coords,
            "Lon": x_coords,
        },
        name="delta",
    )

    mean_array = xr.DataArray(
        mean_data,
        dims=["model", "position", "scenario", "season", "Lat", "Lon"],
        coords={
            "model": models,
            "position": positions,
            "scenario": scenarios,
            "season": seasons,
            "Lat": y_coords,
            "Lon": x_coords,
        },
        name="mean",
    )

    # Create Dataset with both variables
    ds = xr.Dataset({"delta": delta_array, "mean": mean_array})

    # Add CRS as attribute if available
    if crs:
        ds.attrs["crs"] = str(crs)

    # Save to NetCDF
    print(f"\nSaving combined dataset to {output_file}...")
    # Set encoding to ensure proper data types
    # Explicitly set _FillValue to None for coordinates to prevent xarray from adding NaN
    encoding = {
        "delta": {"_FillValue": -9999.0, "dtype": "float64"},
        "mean": {"_FillValue": -9999.0, "dtype": "float64"},
        "Lat": {"dtype": "float64", "_FillValue": None},
        "Lon": {"dtype": "float64", "_FillValue": None}
    }
    ds.to_netcdf(output_file, encoding=encoding)
    
    print(f"\n=== Success ===")
    print(f"Successfully created {output_file}")
    print(f"Dataset shape: {combined_shape}")
    print(
        f"Dimensions: model({len(models)}), position({len(positions)}), "
        f"scenario({len(scenarios)}), season({len(seasons)}), "
        f"Lat({n_y}), Lon({n_x})"
    )
    print(f"Variables: delta, mean")


if __name__ == "__main__":
    # Set paths
    deltas_dir = "deltas"
    means_dir = "means"
    output_file = "combined_mean_and_delta.nc"

    # Combine files
    combine_netcdf_files(deltas_dir, means_dir, output_file)
