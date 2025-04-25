import netCDF4
import json
import os
import sys
import numpy as np
import re

def generate_multi_file_recipe(directory_path, coverage_id=None):
    """
    Generates a Rasdaman ingest recipe for multiple netCDF files in a directory.

    Args:
        directory_path (str): The path to the directory containing the netCDF files.
        coverage_id (str, optional): The coverage ID to use in the recipe. If None, defaults to "multi_file_coverage".

    Returns:
        dict or None: A dictionary representing the JSON recipe, or None if an error occurred.
    """
    try:
        nc_files = [f for f in os.listdir(directory_path) if f.endswith(".nc")]
        if not nc_files:
            print(f"Error: No .nc files found in directory '{directory_path}'")
            return None

        # Use the first file to get the structure (assuming all files have the same structure)
        first_nc_file_path = os.path.join(directory_path, nc_files[0])
        with netCDF4.Dataset(first_nc_file_path, 'r') as nc_file:
            # If no coverage_id is provided, use the default
            if coverage_id is None:
                coverage_id = "multi_file_coverage"
                
            recipe = {
                "config": {
                    "service_url": "http://localhost:8080/rasdaman/ows",  # Configurable
                    "tmp_directory": "/tmp/",  # Configurable
                    "mock": False,  # Configurable
                    "automated": True   # Configurable
                },
                "input": {
                    "coverage_id": coverage_id,  # Now uses the provided or default coverage_id
                    "paths": [
                        "data/*.nc"  # Simplified pattern instead of listing all files
                    ]
                },
                "recipe": {
                    "name": "general_coverage",  # Or a more specific name
                    "options": {
                        "wms_import": True,  # Configurable
                        "import_order": "ascending",  # Configurable.  Important for time series!
                        "tiling": "ALIGNED [0:*, 0:*, 0:*] tile size 4194304",  #  Adjust as needed.
                        "coverage": {
                            "crs": "OGC/0/Index1D?axis-label=\"time\"@EPSG/0/4326",  # Default, will be updated
                            "metadata": {
                                "type": "xml",  # Configurable
                                "global": "auto"   # Configurable
                            },
                            "slicer": {
                                "type": "netcdf",
                                "pixelIsPoint": True,  # Configurable
                                "bands": [],
                                "axes": {}
                            }
                        }
                    }
                }
            }

            # Flag to check if we have a projected CRS
            is_projected = False
            
            # Handle CRS from spatial_ref variable in the first file
            if "spatial_ref" in nc_file.variables:
                spatial_ref_var = nc_file.variables["spatial_ref"]
                wkt_string = None
                
                # Try to get the WKT string from attributes
                if hasattr(spatial_ref_var, "crs_wkt"):
                    wkt_string = getattr(spatial_ref_var, "crs_wkt")
                elif hasattr(spatial_ref_var, "spatial_ref"):
                    wkt_string = getattr(spatial_ref_var, "spatial_ref")
                
                # Check if the CRS is projected (contains "PROJCS")
                if wkt_string and "PROJCS" in wkt_string:
                    is_projected = True
                
                if wkt_string:
                    # Use regex to find the last EPSG code in the WKT string
                    epsg_matches = re.findall(r'AUTHORITY\[\"EPSG\",\"(\d+)\"\]', wkt_string)
                    if epsg_matches:
                        epsg_code = epsg_matches[-1]  # Get the last EPSG code
                        
                        # Check for time dimension to construct the proper CRS string
                        if "time" in nc_file.dimensions:
                            crs_string = f"OGC/0/Index1D?axis-label=\"time\"@EPSG/0/{epsg_code}"
                        else:
                            crs_string = f"EPSG/0/{epsg_code}"
                            
                        recipe["recipe"]["options"]["coverage"]["crs"] = crs_string

            for var_name, var in nc_file.variables.items():
                if len(var.dimensions) > 0 and var_name not in nc_file.dimensions:
                    band = {
                        "name": var_name,
                        "identifier": var_name,
                    }
                    if hasattr(var, "_FillValue"):
                        fill_value = getattr(var, "_FillValue")
                        if isinstance(fill_value, float) and np.isnan(fill_value):
                            band["nilValue"] = "nan"
                        else:
                            band["nilValue"] = str(fill_value)
                    recipe["recipe"]["options"]["coverage"]["slicer"]["bands"].append(band)

            # Identify coordinate variables
            x_dim = None
            y_dim = None
            
            # Look for x and y dimensions based on standard attributes
            for dim_name, dim_var in nc_file.variables.items():
                if dim_name in nc_file.dimensions:
                    if hasattr(dim_var, "axis") and getattr(dim_var, "axis") == "X":
                        x_dim = dim_name
                    elif hasattr(dim_var, "axis") and getattr(dim_var, "axis") == "Y":
                        y_dim = dim_name
                    elif hasattr(dim_var, "standard_name") and "longitude" in getattr(dim_var, "standard_name").lower():
                        x_dim = dim_name
                    elif hasattr(dim_var, "standard_name") and "latitude" in getattr(dim_var, "standard_name").lower():
                        y_dim = dim_name
                    elif hasattr(dim_var, "standard_name") and "projection_x_coordinate" in getattr(dim_var, "standard_name").lower():
                        x_dim = dim_name
                    elif hasattr(dim_var, "standard_name") and "projection_y_coordinate" in getattr(dim_var, "standard_name").lower():
                        y_dim = dim_name
            
            # If we couldn't identify by attributes, use common dimension names
            if x_dim is None and "x" in nc_file.dimensions:
                x_dim = "x"
            if y_dim is None and "y" in nc_file.dimensions:
                y_dim = "y"
            if x_dim is None and "lon" in nc_file.dimensions:
                x_dim = "lon"
            if y_dim is None and "lat" in nc_file.dimensions:
                y_dim = "lat"
            
            # Special handling for time dimension (should have highest grid order)
            time_grid_order = None
            if "time" in nc_file.dimensions:
                time_grid_order = len(nc_file.dimensions) - 1  # Time gets the highest grid order
            
            # Process all dimensions to create axes
            for dim_name, dim in nc_file.dimensions.items():
                axis = {
                    "min": "${netcdf:variable:" + dim_name + ":min}",
                    "max": "${netcdf:variable:" + dim_name + ":max}",
                }
                
                if dim_name in nc_file.variables:
                    axis["directPositions"] = "${netcdf:variable:" + dim_name + "}"
                    axis["irregular"] = True
                
                # Determine axis name and grid order
                if is_projected and dim_name == x_dim:
                    axis_name = "X"
                    axis["gridOrder"] = 1  # X gets grid order 1 for projected CRS
                elif is_projected and dim_name == y_dim:
                    axis_name = "Y"
                    axis["gridOrder"] = 0  # Y gets grid order 0 for projected CRS
                elif dim_name == "time":
                    axis_name = "time"
                    axis["gridOrder"] = time_grid_order
                else:
                    # For other dimensions, use standard naming logic
                    axis_name = dim_name
                    if dim_name in nc_file.variables:
                        dim_var = nc_file.variables[dim_name]
                        if hasattr(dim_var, "standard_name"):
                            axis_name = getattr(dim_var, "standard_name")
                        elif hasattr(dim_var, "long_name"):
                            axis_name = getattr(dim_var, "long_name")
                        elif hasattr(dim_var, "axis"):
                            axis_name = getattr(dim_var, "axis")
                    
                    # If it's not X, Y, or time, assign grid order based on position
                    if not is_projected or (dim_name != x_dim and dim_name != y_dim and dim_name != "time"):
                        axis["gridOrder"] = list(nc_file.dimensions).index(dim_name)
                
                recipe["recipe"]["options"]["coverage"]["slicer"]["axes"][axis_name] = axis

            return recipe

    except Exception as e:
        print(f"Error processing directory '{directory_path}': {e}")
        return None

def main():
    """
    Main function to process netCDF files in a directory and generate a single JSON recipe.
    """
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python script_name.py <directory_path> [coverage_id]")
        sys.exit(1)

    directory_path = sys.argv[1]
    
    # Get coverage_id if provided
    coverage_id = None
    if len(sys.argv) == 3:
        coverage_id = sys.argv[2]

    if not os.path.isdir(directory_path):
        print(f"Error: Directory '{directory_path}' not found.")
        sys.exit(1)

    recipe = generate_multi_file_recipe(directory_path, coverage_id)
    if recipe is not None:  # Changed to check for None explicitly
        json_file_path = os.path.join(directory_path, "ingest_recipe.json")
        try:
            with open(json_file_path, 'w') as json_file:
                json.dump(recipe, json_file, indent=2)
            print(f"Successfully created recipe: '{json_file_path}'")
        except Exception as e:
            print(f"Error saving JSON recipe: {e}")
    else:
        print("Recipe generation failed. No JSON file was created.")  # Added message for failure

if __name__ == "__main__":
    main()