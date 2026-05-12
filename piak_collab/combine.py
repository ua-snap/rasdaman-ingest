import os
import re
import rasterio
import xarray as xr
import numpy as np
from pathlib import Path


def parse_filename(filename):
    """
    Parse the filename to extract model, position, scenario, and season.
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
    nc_files = sorted(input_path.glob("*_mean.nc"))

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

    # Sort dimension values
    # models = sorted(list(models))
    # positions = list(positions)
    # scenarios = sorted(list(scenarios))
    # seasons = sorted(list(seasons))

    # Hard-code dimension values so we are sure they are in the correct order
    models = ["ACCESS-CM2"]
    positions = ["MID", "END"]
    scenarios = ["ssp126", "ssp245", "ssp370", "ssp585"]
    seasons = ["ANNUAL", "DRY", "WET"]

    print(f"Models: {models}")
    print(f"Positions: {positions}")
    print(f"Scenarios: {scenarios}")
    print(f"Seasons: {seasons}")

    # Read first file to get spatial dimensions and band count
    first_data, x_coords, y_coords, crs = read_netcdf_with_rasterio(str(nc_files[0]))
    n_bands, n_y, n_x = first_data.shape

    # Create empty array for combined data
    combined_shape = (
        len(models),
        len(positions),
        len(scenarios),
        len(seasons),
        n_bands,
        n_y,
        n_x,
    )
    combined_data = np.full(combined_shape, np.nan, dtype=first_data.dtype)

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

        # Debug: print data statistics
        print(
            f"  Mean: {np.nanmean(data):.4f}, Min: {np.nanmin(data):.4f}, Max: {np.nanmax(data):.4f}"
        )

        # Store in combined array
        combined_data[model_idx, position_idx, scenario_idx, season_idx, :, :, :] = data

    # Create xarray Dataset
    print("Creating xarray Dataset...")

    # Create band dimension (if there are multiple bands)
    band_coords = np.arange(1, n_bands + 1)

    # Create the DataArray
    data_array = xr.DataArray(
        combined_data,
        dims=["model", "position", "scenario", "season", "band", "y", "x"],
        coords={
            "model": models,
            "position": positions,
            "scenario": scenarios,
            "season": seasons,
            "band": band_coords,
            "y": y_coords,
            "x": x_coords,
        },
        name="data",
    )

    # Create Dataset
    ds = xr.Dataset({"data": data_array})

    # Add CRS as attribute if available
    if crs:
        ds.attrs["crs"] = str(crs)

    # Save to NetCDF
    print(f"Saving combined dataset to {output_file}...")
    ds.to_netcdf(output_file)
    print(f"Successfully created {output_file}")
    print(f"Dataset shape: {combined_data.shape}")
    print(
        f"Dimensions: model({len(models)}), position({len(positions)}), "
        f"scenario({len(scenarios)}), season({len(seasons)}), "
        f"band({n_bands}), y({n_y}), x({n_x})"
    )


if __name__ == "__main__":
    # Set paths
    means_dir = "means"
    output_file = "combined_means.nc"

    # Combine files
    combine_netcdf_files(means_dir, output_file)
