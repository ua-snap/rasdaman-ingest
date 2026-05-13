import os
import re
import rasterio
import xarray as xr
import numpy as np
from pathlib import Path


def parse_filename(filename):
    """
    Parse the filename to extract model, position, scenario, and season.
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
        raise ValueError(f"Unexpected filename format: {filename}")


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


def combine_netcdf_files(input_dir, output_file):
    """
    Combine all NetCDF files in the input directory into a single file.
    """
    input_path = Path(input_dir)
    nc_files = sorted(input_path.glob("*_delta_pct_*.nc"))

    if not nc_files:
        raise ValueError(f"No NetCDF files found in {input_dir}")

    print(f"Found {len(nc_files)} NetCDF files to combine")

    # First pass: collect all unique dimension values and read first file for structure
    models = set()
    positions = set()
    scenarios = set()
    seasons = set()

    for nc_file in nc_files:
        model, position, scenario, season = parse_filename(nc_file.name)
        models.add(model)
        positions.add(position)
        scenarios.add(scenario)
        seasons.add(season)

    # Hard-code dimension values so we are sure they are in the correct order
    models = ["ACCESS-CM2"]
    positions = ["MID", "END"]
    scenarios = ["ssp126", "ssp245", "ssp370", "ssp585"]
    seasons = ["ANNUAL", "DRY", "WET"]

    print(f"Models: {models}")
    print(f"Positions: {positions}")
    print(f"Scenarios: {scenarios}")
    print(f"Seasons: {seasons}")

    # Read first file to get spatial dimensions
    first_data, x_coords, y_coords, crs = read_netcdf_with_rasterio(str(nc_files[0]))
    # Take only the first band if multiple bands exist
    if first_data.ndim == 3:
        first_data = first_data[0]
    n_y, n_x = first_data.shape

    # Ensure coordinates are clean (no NaN/Inf) and proper float type
    x_coords = x_coords.astype(np.float64)
    y_coords = y_coords.astype(np.float64)
    
    # Check for invalid values in coordinates
    if np.any(np.isnan(x_coords)) or np.any(np.isinf(x_coords)):
        raise ValueError(f"Lon coordinates contain invalid values (NaN or Inf): {x_coords}")
    if np.any(np.isnan(y_coords)) or np.any(np.isinf(y_coords)):
        raise ValueError(f"Lat coordinates contain invalid values (NaN or Inf): {y_coords}")
    
    # Debug: print coordinate info
    print(f"Lon range: {x_coords.min():.6f} to {x_coords.max():.6f}")
    print(f"Lat range: {y_coords.min():.6f} to {y_coords.max():.6f}")
    print(f"Lon dtype: {x_coords.dtype}, Lat dtype: {y_coords.dtype}")

    # Create empty array for combined data
    combined_shape = (
        len(models),
        len(positions),
        len(scenarios),
        len(seasons),
        n_y,
        n_x,
    )
    # Ensure we use float64 dtype
    combined_data = np.full(combined_shape, np.nan, dtype=np.float64)

    # Second pass: read all files and populate the array
    for nc_file in nc_files:
        print(f"Processing {nc_file.name}...")
        model, position, scenario, season = parse_filename(nc_file.name)

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
        combined_data[model_idx, position_idx, scenario_idx, season_idx, :, :] = data

    # Create xarray Dataset
    print("Creating xarray Dataset...")

    # Convert NaN values to -9999 before writing (ensure float type is maintained)
    combined_data = np.where(np.isnan(combined_data), -9999.0, combined_data).astype(np.float64)

    # Create the DataArray
    data_array = xr.DataArray(
        combined_data,
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

    # Create Dataset
    ds = xr.Dataset({"delta": data_array})

    # Add CRS as attribute if available
    if crs:
        ds.attrs["crs"] = str(crs)

    # Save to NetCDF
    print(f"Saving combined dataset to {output_file}...")
    # Set encoding to ensure proper data types
    # Explicitly set _FillValue to None for coordinates to prevent xarray from adding NaN
    encoding = {
        "delta": {"_FillValue": -9999.0, "dtype": "float64"},
        "Lat": {"dtype": "float64", "_FillValue": None},
        "Lon": {"dtype": "float64", "_FillValue": None}
    }
    ds.to_netcdf(output_file, encoding=encoding)
    print(f"Successfully created {output_file}")
    print(f"Dataset shape: {combined_data.shape}")
    print(
        f"Dimensions: model({len(models)}), position({len(positions)}), "
        f"scenario({len(scenarios)}), season({len(seasons)}), "
        f"y({n_y}), x({n_x})"
    )


if __name__ == "__main__":
    # Set paths
    deltas_dir = "deltas"
    output_file = "combined_deltas.nc"

    # Combine files
    combine_netcdf_files(deltas_dir, output_file)
