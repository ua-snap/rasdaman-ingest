"""Script to combine regridded CMIP6 data for ingestion into rasdaman.
This will combine all CMIP6 daily files into one netCDF, storing variables as data_vars and computing an ensemble mean for all variables.
It is assumed that the data has already been regridded and is stored in the following
directory structure: <model>/<scenario>/<frequency (table ID)>/<variable ID>/<filename>.
The script uses a cascading merge approach optimized for high-performance compute nodes (24-28 cores, 128GB RAM)
by creating intermediate files in parallel and then merging them, avoiding memory issues with thousands of input files.

example usage:
  python combine_regridded_data_ensemble.py \
    --models 'all' \
    --scenarios 'all' \
    --vars 'pr tasmin tasmax' \
    --frequency 'day' \
    --regrid_dir /beegfs/CMIP6/jdpaul3/cmip6_regrid_timefix \
    --rasda_dir /beegfs/CMIP6/jdpaul3/cmip6_daily_for_rasdaman \
    --batch_size 50 \
    --time_chunk_size 100
"""

import argparse
import sys
import subprocess
import xarray as xr
import rioxarray
from pathlib import Path
from datetime import datetime, timedelta
from dask.distributed import Client
import numpy as np
import gc
import psutil
import time
import dask
import warnings
from luts import (
    cmip6_models,
    cmip6_scenarios,
    cmip6_var_attrs,
    description_fmt_str,
    title_fmt_str,
    global_attrs,
)


def validate_all_args(models, scenarios, vars, frequency, regrid_dir, rasda_dir):
    """Validate all input arguments for the script."""

    # validate dirs
    if not rasda_dir.exists():
        rasda_dir.mkdir()
    if not regrid_dir.exists():
        sys.exit(f"Directory not found: {regrid_dir}")

    # validate models/scenarios/vars
    if models == "all":
        models = list(cmip6_models.keys())
        models.remove("Ensemble")  # drop "Ensemble" from models list
    else:
        models = models.split()
        validate_args_against_dict(models, cmip6_models)

    if scenarios == "all":
        scenarios = list(cmip6_scenarios.keys())
    else:
        scenarios = scenarios.split()
        validate_args_against_dict(scenarios, cmip6_scenarios)

    if vars == "all":
        vars = list(cmip6_var_attrs.keys())
    else:
        vars = vars.split()
        validate_args_against_dict(vars, cmip6_var_attrs)

    # validate frequency
    if frequency not in ["mon", "day"]:
        sys.exit(f"{frequency} not allowed. Must be 'mon' or 'day'.")

    return models, scenarios, vars, frequency, regrid_dir, rasda_dir


def validate_args_against_dict(input_list, cmip6_dict):
    """Validate a list of arguments against a list derived from dictionary keys."""

    for item in input_list:
        if item not in list(cmip6_dict.keys()):
            sys.exit(
                f"Input {item} not allowed. Must be one of {list(cmip6_dict.keys())}"
            )
        else:
            pass


def update_global_attrs(global_attrs, models, scenarios, vars, frequency):
    """Update global attributes for the dataset.
    These will be applied in the preprocess_ds() function."""

    freq_str = (
        "Monthly" if frequency == "mon" else "Daily" if frequency == "day" else None
    )

    title = title_fmt_str.format(
        frequency=freq_str,
        models=", ".join(models),
        scenarios=", ".join(scenarios),
        variables=", ".join(vars),
    )
    description = description_fmt_str.format(
        frequency=freq_str,
        models=", ".join(models),
        number_of_models=len(models),
        scenarios=", ".join(scenarios),
        variables=", ".join(vars),
    )
    global_attrs["title"] = title
    global_attrs["description"] = description

    return global_attrs


def get_files(var_id, model, scenario, frequency, regrid_dir):
    """Get a list of file paths for a given model, scenario, frequency, and variable ID."""

    var_fps = list(regrid_dir.glob(f"{model}/{scenario}/*{frequency}/{var_id}/*.nc"))

    return var_fps


def list_all_files(vars, models, scenarios, frequency, regrid_dir):
    """Get all file paths for a list of models, list of scenarios, frequency, and list of variables."""

    fps = []
    for model in models:
        for scenario in scenarios:
            for var_id in vars:
                fps.extend(get_files(var_id, model, scenario, frequency, regrid_dir))
    print(f"Found {len(fps)} files to combine...")

    return fps


def pull_dims_from_source(ds):
    """Pull dimensions from the source attribute of the dataset.
    If dataset variable id does not match the filename variable id, rename it.
    (This allows for datasets with generic variable names like "data" to be used,
    as long as their filepath starts with the variable id.)
    """

    var = list(ds.data_vars)[0]  # assume first var is the one we want
    src = ds[var].encoding["source"]
    fp_var_id = src.split("/")[-1].split("_")[
        0
    ]  # assumes filename begins with the var id
    if var != fp_var_id:
        ds = ds.rename({var: fp_var_id})

    # get model and scenario from filepath and add these to the dataset as dimensions
    fp_model = src.split("/")[-1].split("_")[
        2
    ]  # assumes filename has model name in third position
    fp_scenario = src.split("/")[-1].split("_")[
        3
    ]  # assumes filename has model name in fourth position

    # add model and scenario to dataset as dimensions using an array with one value each
    ds = ds.expand_dims({"model": [fp_model], "scenario": [fp_scenario]})

    return ds


def replace_var_attrs(ds, cmip6_var_attrs):
    """Replace the variable attributes in the dataset."""

    for var_id in ds.data_vars:
        if var_id in cmip6_var_attrs.keys():

            # remove existing attributes
            if ds[var_id].attrs is None:
                ds[var_id].attrs = {}
            else:
                # clear existing attributes
                ds[var_id].attrs.clear()

            # remove existing encoding
            ds[var_id].encoding.clear()

            # add new attributes from cmip6_var_attrs
            for k, v in cmip6_var_attrs[var_id].items():
                # skip "dtype" and "precision" as they are handled separately
                if k not in ["dtype", "precision"]:
                    ds[var_id].attrs[k] = v
    return ds


def preprocess_ds(ds):
    """Peforms functions to fix datasets as they are opened."""

    ds = pull_dims_from_source(ds)
    # drop global encoding and attributes that are not needed
    ds.encoding = {}
    ds.attrs = {}

    return ds


def reindex_and_rechunk(ds, chunks):
    """Reindex the dataset to include all models and scenarios, and rechunk it for efficient processing."""

    all_models = ds["model"].values
    all_scenarios = ds["scenario"].values
    
    # Create a copy of chunks and only include dimensions that exist in the data
    for var in ds.data_vars:
        ds[var] = ds[var].reindex(model=all_models, scenario=all_scenarios)
        
        # Create chunks dict with only dimensions that exist in this variable
        var_chunks = {}
        for dim_name, dim_size in chunks.items():
            if dim_name in ds[var].dims:
                var_chunks[dim_name] = dim_size
        
        # Add model and scenario dimensions if they exist
        if "model" in ds[var].dims:
            var_chunks["model"] = len(all_models)
        if "scenario" in ds[var].dims:
            var_chunks["scenario"] = len(all_scenarios)
        
        # Only rechunk if we have valid chunks
        if var_chunks:
            ds[var] = ds[var].chunk(var_chunks)

    #print("Dataset opened and combined successfully with chunks:")
    #print(ds.chunks)

    return ds


def compute_ensemble_mean(ds):
    """Compute the ensemble mean for a dataset."""

    ensemble_mean = ds.mean(dim="model")
    ensemble_mean = ensemble_mean.expand_dims(model=["Ensemble"])
    ds_with_ensemble = xr.concat([ds, ensemble_mean], dim="model")

    return ds_with_ensemble


def enforce_dtypes_and_precision(ds, cmip6_var_attrs):
    """Enforce dtypes and precision for the dataset variables using the attributes in the lookup table."""

    for var in ds.data_vars:
        if var not in ["spatial_ref"]:
            if "dtype" in cmip6_var_attrs[var]:
                # validate that the dtype is OK - if not, skip the conversion but warn the user
                if cmip6_var_attrs[var]["dtype"] not in ["int32", "float32", "float64"]:
                    print(
                        f"Warning: dtype {ds[var].encoding['dtype']} for variable {var} is not supported. Skipping conversion."
                    )
                    pass
                # If converting to integer, set nodata to -9999 before conversion
                if cmip6_var_attrs[var]["dtype"].startswith("int"):
                    nodata_val = cmip6_var_attrs[var]["_FillValue"]
                    ds[var] = ds[var].where(~np.isnan(ds[var]), nodata_val)
                # round before dtype conversion
                ds[var] = ds[var].round(cmip6_var_attrs[var]["precision"])
                ds[var] = ds[var].astype(cmip6_var_attrs[var]["dtype"])

    return ds


def map_integers(ds, cmip6_models, cmip6_scenarios):
    """Map model and scenario strings to integers from luts.py dictionarys for rasdaman ingestion."""

    # check if dataset models and scenarios are in the dictionaries
    if not all([i in cmip6_models.keys() for i in ds["model"].values]):
        sys.exit(
            f"At least one model name in dataset not found in models_dict: {ds['model'].values} must be one of {list(cmip6_models.keys())}"
        )
    if not all([i in cmip6_scenarios.keys() for i in ds["scenario"].values]):
        sys.exit(
            f"At least one scenario name in dataset not found in scenarios_dict: {ds['scenario'].values} must be one of {list(cmip6_scenarios.keys())}"
        )

    ds["model"] = [cmip6_models[i] for i in ds["model"].values]
    ds["scenario"] = [cmip6_scenarios[i] for i in ds["scenario"].values]

    return ds


def replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios):
    """Replace the model and scenario dimensions with integer values for rasdaman ingestion."""

    # remove "bounds", "title", "type" attributes from time, lat, and lon if they exist
    for dim in ["time", "lat", "lon"]:
        ds[dim].attrs.pop("bounds", None)
        ds[dim].attrs.pop("title", None)
        ds[dim].attrs.pop("type", None)

    # reverse the model and scenario dictionaries
    model_dict = {v: k for k, v in cmip6_models.items()}
    scenario_dict = {v: k for k, v in cmip6_scenarios.items()}

    # then drop any keys that are not actually in the dataset
    model_dict = {k: v for k, v in model_dict.items() if k in ds["model"].values}
    scenario_dict = {
        k: v for k, v in scenario_dict.items() if k in ds["scenario"].values
    }

    # then add the encoding dictionaries, units, and name to the attributes
    ds["model"].attrs["long_name"] = "model"
    ds["model"].attrs["units"] = "1"  # denotes dimensionless unit under CF conventions
    ds["model"].attrs["encoding"] = str(model_dict)

    ds["scenario"].attrs["long_name"] = "scenario"
    ds["scenario"].attrs[
        "units"
    ] = "1"  # denotes dimensionless unit under CF conventions
    ds["scenario"].attrs["encoding"] = str(scenario_dict)

    return ds


def replace_lat_lon_attrs(ds):
    """Replace the latitude and longitude attributes with standard CF attributes.
    This function assumes that the latitude and longitude coordinates are named 'lat' and 'lon' respectively.
    It also updates the attributes to include min_value and max_value derived from the data.
    """

    ds["lat"].attrs = {}
    ds["lon"].attrs = {}

    ds["lat"].attrs.update(
        {
            "standard_name": "latitude",
            "long_name": "latitude",
            "units": "degrees_north",
            "axis": "Y",
            "min_value": ds["lat"].min().values,
            "max_value": ds["lat"].max().values,
        }
    )

    ds["lon"].attrs.update(
        {
            "standard_name": "longitude",
            "long_name": "longitude",
            "units": "degrees_east",
            "axis": "X",
            "min_value": ds["lon"].min().values,
            "max_value": ds["lon"].max().values,
        }
    )

    return ds


def transpose_dims(ds):
    """Transpose the dataset dimensions to have the order: model, scenario, time, lat, lon.
    This is necessary for CF conventions."""

    ds = ds.transpose("model", "scenario", "time", "lat", "lon")

    return ds


def add_crs(ds, crs):
    """Add a CRS to the dataset using rioxarray."""

    ds = ds.rio.set_spatial_dims("lon", "lat")
    ds = ds.rio.write_crs(crs)  # this creates the "spatial_ref" coordinate

    return ds


def process_batch(batch, intermediate_fp, var_id, models, scenarios, frequency, 
                 cmip6_var_attrs, cmip6_models, cmip6_scenarios, global_attrs, chunks):
    """Process a single batch of files."""
    batch_start_time = time.time()
    
    try:
        # Open and process this batch
        ds = xr.open_mfdataset(
            batch,
            drop_variables=["spatial_ref", "height", "type"],
            preprocess=preprocess_ds,
            parallel=True,
            combine="by_coords",
            engine="h5netcdf",
            decode_cf=True,
            coords="minimal",
            compat="no_conflicts",
            chunks=chunks,
        )
        
        # Apply processing pipeline
        ds = reindex_and_rechunk(ds, chunks)
        ds = compute_ensemble_mean(ds)
        ds = enforce_dtypes_and_precision(ds, cmip6_var_attrs)
        # Note: Keep model names as strings in intermediate files, convert to integers only in final processing
        ds = replace_var_attrs(ds, cmip6_var_attrs)
        ds.attrs = global_attrs
        ds = replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios)
        ds = replace_lat_lon_attrs(ds)
        ds = transpose_dims(ds)
        ds = add_crs(ds, "EPSG:4326")
        
        # Write intermediate file
        ds.to_netcdf(intermediate_fp, engine="netcdf4", mode="w", format="NETCDF4")
        file_size = intermediate_fp.stat().st_size
        ds.close()
        
        # Force garbage collection
        gc.collect()
        
        batch_time = time.time() - batch_start_time
        return intermediate_fp, file_size, batch_time
        
    except Exception as e:
        # Clean up any partial intermediate files
        if intermediate_fp.exists():
            intermediate_fp.unlink()
        raise Exception(f"Error processing batch: {e}")


def create_empty_netcdf_file(output_file, sample_ds, all_models, all_scenarios, all_times):
    """Create an empty NetCDF file with the correct structure without pre-allocating data arrays."""
    
    import netCDF4 as nc4
    
    # Create NetCDF file with dimensions and variables but no data
    with nc4.Dataset(output_file, 'w', format='NETCDF4') as nc_out:
        # Create dimensions
        nc_out.createDimension('model', len(all_models))
        nc_out.createDimension('scenario', len(all_scenarios))
        nc_out.createDimension('time', len(all_times))
        nc_out.createDimension('lat', len(sample_ds.lat))
        nc_out.createDimension('lon', len(sample_ds.lon))
        
        # Create coordinate variables
        model_var = nc_out.createVariable('model', str, ('model',))
        scenario_var = nc_out.createVariable('scenario', str, ('scenario',))
        time_var = nc_out.createVariable('time', 'f8', ('time',))
        lat_var = nc_out.createVariable('lat', 'f4', ('lat',))
        lon_var = nc_out.createVariable('lon', 'f4', ('lon',))
        
        # Set coordinate values
        # For string variables, assign each element individually
        for i, model in enumerate(all_models):
            model_var[i] = model
        for i, scenario in enumerate(all_scenarios):
            scenario_var[i] = scenario
        
        # Convert time values to numeric format for NetCDF4
        if hasattr(all_times[0], 'toordinal'):
            # Convert cftime objects to ordinal numbers
            time_values = [t.toordinal() for t in all_times]
        elif hasattr(all_times[0], 'timestamp'):
            # Convert datetime objects to timestamps
            time_values = [t.timestamp() for t in all_times]
        else:
            # Try to convert to float directly
            time_values = [float(t) for t in all_times]
        
        time_var[:] = time_values
        lat_var[:] = sample_ds.lat.values
        lon_var[:] = sample_ds.lon.values
        
        # Copy coordinate attributes
        for attr_name, attr_value in sample_ds.lat.attrs.items():
            setattr(lat_var, attr_name, attr_value)
        for attr_name, attr_value in sample_ds.lon.attrs.items():
            setattr(lon_var, attr_name, attr_value)
        for attr_name, attr_value in sample_ds.time.attrs.items():
            setattr(time_var, attr_name, attr_value)
        
        # Create data variables with correct dimensions but no data allocation
        for var_name in sample_ds.data_vars:
            var = sample_ds[var_name]
            
            # Determine appropriate fill value for the data type
            if np.issubdtype(var.dtype, np.integer):
                fill_value = -9999
            elif np.issubdtype(var.dtype, np.bool_):
                fill_value = False
            elif np.issubdtype(var.dtype, np.floating):
                fill_value = np.nan
            else:
                try:
                    fill_value = np.nan
                except:
                    fill_value = 0
            
            # Create variable with dimensions but no data
            nc_var = nc_out.createVariable(
                var_name, 
                var.dtype, 
                ('model', 'scenario', 'time', 'lat', 'lon'),
                fill_value=fill_value
            )
            
            # Copy variable attributes
            for attr_name, attr_value in var.attrs.items():
                setattr(nc_var, attr_name, attr_value)
        
        # Copy global attributes
        for attr_name, attr_value in sample_ds.attrs.items():
            setattr(nc_out, attr_name, attr_value)
    
    print(f"✅ Created empty NetCDF file structure: {output_file}")


def append_to_netcdf(output_file, intermediate_file, all_models, all_scenarios, all_times):
    """Append data from an intermediate file to the output NetCDF file using direct NetCDF4 access."""
    
    import netCDF4 as nc4
    
    # Open intermediate file
    intermediate_ds = xr.open_dataset(intermediate_file, engine="h5netcdf")
    
    # Open output file for writing using NetCDF4 directly
    with nc4.Dataset(output_file, 'a') as nc_out:
        # For each variable in the intermediate file
        for var_name in intermediate_ds.data_vars:
            if var_name in nc_out.variables:
                # Get the data from intermediate file
                var_data = intermediate_ds[var_name]
                
                # Find the indices where this data should go in the output
                # Access model/scenario/time values from the dataset coordinates, not the DataArray
                model_indices = [all_models.index(model) for model in intermediate_ds.model.values]
                scenario_indices = [all_scenarios.index(scenario) for scenario in intermediate_ds.scenario.values]
                time_indices = [all_times.index(time) for time in intermediate_ds.time.values]
                
                # Create index arrays for NetCDF4
                model_idx = np.array(model_indices)
                scenario_idx = np.array(scenario_indices)
                time_idx = np.array(time_indices)
                
                # Write the data using NetCDF4's direct array access (memory efficient)
                nc_out.variables[var_name][model_idx, scenario_idx, time_idx] = var_data.values
    
    intermediate_ds.close()


def cascade_merge_files_sequential(fps, intermediate_dir, var_id, models, scenarios, frequency, 
                                 cmip6_var_attrs, cmip6_models, cmip6_scenarios, global_attrs, 
                                 batch_size=50, chunks=None):
    """Sequential cascade merge approach using Dask's built-in parallelization."""
    
    if chunks is None:
        chunks = {"time": 100}  # Smaller chunks for better memory management
    
    # Create intermediate directory
    intermediate_dir.mkdir(exist_ok=True)
    
    # Split files into batches
    file_batches = [fps[i:i+batch_size] for i in range(0, len(fps), batch_size)]
    print(f"Processing {len(fps)} files in {len(file_batches)} batches of ~{batch_size} files each...")
    print(f"Using Dask's built-in parallelization for batch processing...")
    
    # Process batches sequentially (but each batch uses Dask parallelization internally)
    completed_files = []
    total_intermediate_size = 0
    var_start_time = time.time()
    
    print(f"\n🚀 Starting sequential batch processing for {var_id}")
    print(f"   Total files: {len(fps):,}")
    print(f"   Batches: {len(file_batches)}")
    
    for batch_idx, batch in enumerate(file_batches):
        intermediate_fp = intermediate_dir / f"intermediate_{var_id}_{batch_idx:03d}.nc"
        
        print(f"\n📦 Processing batch {batch_idx+1}/{len(file_batches)} for {var_id}")
        print(f"   Files in batch: {len(batch)}")
        
        try:
            # Process this batch
            result_fp, file_size, batch_time = process_batch(
                batch, intermediate_fp, var_id, models, scenarios, frequency,
                cmip6_var_attrs, cmip6_models, cmip6_scenarios, global_attrs, chunks
            )
            
            completed_files.append(result_fp)
            total_intermediate_size += file_size
            
            # Print progress
            elapsed = time.time() - var_start_time
            files_processed = (batch_idx + 1) * batch_size
            if files_processed > len(fps):
                files_processed = len(fps)
            
            print(f"✅ Batch {batch_idx+1}/{len(file_batches)} completed for {var_id}")
            print(f"   Files processed: {files_processed:,}/{len(fps):,}")
            print(f"   Intermediate file: {intermediate_fp}")
            print(f"   Batch size: {format_bytes(file_size)}")
            print(f"   Batch time: {format_duration(batch_time)}")
            print(f"   Total intermediate: {format_bytes(total_intermediate_size)}")
            print(f"   Elapsed: {format_duration(elapsed)}")
            
            # Calculate ETA
            if batch_idx > 0:
                avg_time_per_batch = elapsed / (batch_idx + 1)
                remaining_batches = len(file_batches) - (batch_idx + 1)
                eta = remaining_batches * avg_time_per_batch
                print(f"   ETA: {format_duration(eta)}")
            
            # Memory info
            memory_info = get_memory_info()
            print(f"   Memory: {memory_info['used_gb']:.1f}GB ({memory_info['percent']:.1f}%)")
            
        except Exception as e:
            print(f"❌ Error processing batch {batch_idx+1} for {var_id}: {e}")
            raise
    
    var_total_time = time.time() - var_start_time
    print(f"\n🎉 Completed {var_id}: {len(completed_files)} batches in {format_duration(var_total_time)}")
    print(f"   Total intermediate size: {format_bytes(total_intermediate_size)}")
    print(f"   Processing speed: {len(fps)/var_total_time:.1f} files/second")
    
    return completed_files


def cascade_merge_files(fps, intermediate_dir, var_id, models, scenarios, frequency, 
                       cmip6_var_attrs, cmip6_models, cmip6_scenarios, global_attrs, 
                       batch_size=50, chunks=None, parallel=True):
    """Cascade merge approach for large datasets using Dask's built-in parallelization."""
    
    # Always use sequential batch processing (but each batch uses Dask parallelization internally)
    return cascade_merge_files_sequential(fps, intermediate_dir, var_id, models, scenarios, frequency,
                                        cmip6_var_attrs, cmip6_models, cmip6_scenarios, global_attrs,
                                        batch_size, chunks)


def format_bytes(bytes_value):
    """Format bytes into human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_duration(seconds):
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"


def get_memory_info():
    """Get current memory usage information."""
    memory = psutil.virtual_memory()
    return {
        'used_gb': memory.used / (1024**3),
        'available_gb': memory.available / (1024**3),
        'total_gb': memory.total / (1024**3),
        'percent': memory.percent
    }


def print_progress_header():
    """Print a header for progress monitoring."""
    print("=" * 80)
    print("CMIP6 DATA COMBINATION PROGRESS MONITOR")
    print("=" * 80)


def print_batch_progress(var_id, batch_num, total_batches, batch_size, start_time, 
                        files_processed=0, intermediate_size=0):
    """Print progress for batch processing."""
    elapsed = time.time() - start_time
    memory_info = get_memory_info()
    
    print(f"\n📁 VARIABLE: {var_id}")
    print(f"   Batch {batch_num}/{total_batches} ({batch_size} files)")
    print(f"   Files processed: {files_processed}")
    print(f"   Intermediate size: {format_bytes(intermediate_size)}")
    print(f"   Elapsed time: {format_duration(elapsed)}")
    print(f"   Memory: {memory_info['used_gb']:.1f}GB used ({memory_info['percent']:.1f}%)")
    
    if batch_num > 1:
        avg_time = elapsed / batch_num
        remaining_batches = total_batches - batch_num
        eta = remaining_batches * avg_time
        print(f"   ETA: {format_duration(eta)}")


def print_final_progress(total_files, total_size, total_time, output_size):
    """Print final processing summary."""
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Total files processed: {total_files:,}")
    print(f"Total input size: {format_bytes(total_size)}")
    print(f"Final output size: {format_bytes(output_size)}")
    print(f"Total processing time: {format_duration(total_time)}")
    print(f"Processing speed: {total_files/total_time:.1f} files/second")
    print(f"Compression ratio: {total_size/output_size:.1f}x")
    print("=" * 80)


def cleanup_intermediate_files(intermediate_files):
    """Clean up intermediate files after successful merge."""
    print("\n🧹 Cleaning up intermediate files...")
    total_size = 0
    for fp in intermediate_files:
        if fp.exists():
            total_size += fp.stat().st_size
            fp.unlink()
    print(f"✅ Cleaned up {len(intermediate_files)} intermediate files ({format_bytes(total_size)})")


def run_cf_checks(fp):
    """Run CF checks on the dataset, and print output to a text file."""
    print("🔎 Running CF checks on the output file...")

    output_fp = fp.with_suffix(".cfchecks.txt")
    with open(output_fp, "w") as out_file:
        subprocess.run(["cfchecks", str(fp)], stdout=out_file, stderr=subprocess.STDOUT)
    print("✅ CF checks run, output saved to", output_fp)

    return None


def parse_args():

    parser = argparse.ArgumentParser(
        description="Combine regridded CMIP6 data for ingestion into rasdaman."
    )
    parser.add_argument(
        "--models",
        type=str,
        help="[ ]-separated string of model names (e.g. 'CESM2 GFDL-ESM4'), or 'all' for all models.",
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        help="[ ]-separated list of scenario names (e.g. 'historical ssp585'), or 'all' for all scenarios.",
    )
    parser.add_argument(
        "--vars",
        type=str,
        help="[ ]-separated list of variable names (e.g. 'pr tas'), or 'all' for all variables.",
    )
    parser.add_argument(
        "--frequency",
        type=str,
        help="Temporal resolution / frequency of data, either 'mon' or 'day'.",
    )
    parser.add_argument(
        "--regrid_dir", type=str, help="Directory where regridded data is stored."
    )
    parser.add_argument(
        "--rasda_dir",
        type=str,
        help="Directory where combined data will be written to disk.",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=50,
        help="Number of files to process in each intermediate batch (default: 50).",
    )
    parser.add_argument(
        "--time_chunk_size",
        type=int,
        default=100,
        help="Time dimension chunk size for dask arrays (default: 100).",
    )
    parser.add_argument(
        "--skip_intermediate_generation",
        action="store_true",
        help="Skip intermediate file generation and start from merge step (for testing).",
    )
    # Note: Parallel processing now uses Dask's built-in parallelization
    # No additional command line arguments needed for batch processing

    args = parser.parse_args()

    return {
        "models": args.models,
        "scenarios": args.scenarios,
        "vars": args.vars,
        "frequency": args.frequency,
        "regrid_dir": Path(args.regrid_dir),
        "rasda_dir": Path(args.rasda_dir),
        "batch_size": args.batch_size,
        "time_chunk_size": args.time_chunk_size,
        "skip_intermediate_generation": args.skip_intermediate_generation,
    }


if __name__ == "__main__":

    start_time = datetime.now()
    print("Starting script at: ", start_time.isoformat())
    
    # Configure Dask to silence large chunk warnings
    dask.config.set({'array.slicing.split_large_chunks': False})
    
    # Silence specific xarray performance warnings
    warnings.filterwarnings('ignore', message='.*Slicing is producing a large chunk.*')
    warnings.filterwarnings('ignore', message='.*PerformanceWarning.*')
    
    # Silence future warnings
    warnings.filterwarnings('ignore', category=FutureWarning)

    # Parse command line arguments
    args = parse_args()
    
    # Optimized chunk sizes for high-performance compute node
    chunks = {"time": args["time_chunk_size"]}  # Configurable time chunk size
    batch_size = args["batch_size"]  # Configurable file batch size
    
    print_progress_header()
    print(f"Hardware optimization: Using {8} workers with {3} threads each")
    print(f"Total memory allocation: {8 * 14}GB out of 128GB available")
    print(f"File batch size: {batch_size} files per intermediate batch")
    print(f"Time chunk size: {args['time_chunk_size']} time steps per dask chunk")
    print(f"Batch processing: Sequential batches with Dask parallelization")
    
    # Get initial memory info
    initial_memory = get_memory_info()
    print(f"Initial memory: {initial_memory['used_gb']:.1f}GB used ({initial_memory['percent']:.1f}%)")
    print("=" * 80)

    models, scenarios, vars, frequency, regrid_dir, rasda_dir = validate_all_args(
        models=args["models"],
        scenarios=args["scenarios"],
        vars=args["vars"],
        frequency=args["frequency"],
        regrid_dir=args["regrid_dir"],
        rasda_dir=args["rasda_dir"]
    )

    global_attrs = update_global_attrs(global_attrs, models, scenarios, vars, frequency)

    # Create intermediate directory for cascade processing
    intermediate_dir = rasda_dir / "intermediate_files"
    intermediate_dir.mkdir(exist_ok=True)

    with Client(
        n_workers=12,  # Optimized for 24-28 core system (8 workers × 3-3.5 threads = 24-28 cores)
        threads_per_worker=2,  # 3 threads per worker for optimal CPU utilization
        memory_limit="14GB",  # 8 × 14GB = 112GB (leaves 16GB for OS and overhead)
        #dashboard_address=":8787",  # Dashboard disabled - using terminal progress monitoring
        processes=True,  # Use processes instead of threads for better parallelism
    ) as client:

        all_intermediate_files = []
        total_input_files = 0
        total_input_size = 0
        processing_start_time = time.time()

        if args["skip_intermediate_generation"]:
            print(f"\n{'='*60}")
            print(f"SKIPPING INTERMEDIATE GENERATION - STARTING FROM MERGE STEP")
            print(f"{'='*60}")
            print("Looking for existing intermediate files...")
            
            # Find existing intermediate files for each variable
            for var_idx, var in enumerate(vars):
                print(f"\nLooking for intermediate files for {var}...")
                var_intermediate_files = list(intermediate_dir.glob(f"intermediate_{var}_*.nc"))
                
                if not var_intermediate_files:
                    print(f"❌ No intermediate files found for {var}!")
                    print(f"   Expected files like: intermediate_{var}_000.nc, intermediate_{var}_001.nc, etc.")
                    print(f"   Please run without --skip_intermediate_generation first.")
                    exit(1)
                
                print(f"✅ Found {len(var_intermediate_files)} intermediate files for {var}")
                all_intermediate_files.extend(var_intermediate_files)
            
            print(f"\n✅ Total intermediate files found: {len(all_intermediate_files)}")
            
            # Process each variable's intermediate files for merging
            for var_idx, var in enumerate(vars):
                print(f"\n{'='*60}")
                print(f"FINAL MERGE PHASE FOR {var.upper()}")
                print(f"{'='*60}")
                
                # Get intermediate files for this variable
                var_intermediate_files = list(intermediate_dir.glob(f"intermediate_{var}_*.nc"))
                print(f"Merging {len(var_intermediate_files)} intermediate files for {var}...")
                
                merge_start_time = time.time()
                
                # Create empty NetCDF file with correct structure and append data from intermediate files
                print("📂 Creating empty output file with correct structure...")
                
                # First, load one intermediate file to get the structure and dimensions
                sample_ds = xr.open_dataset(var_intermediate_files[0], engine="h5netcdf")
                
                # Get all unique models, scenarios, and time steps from this variable's intermediate files
                all_models = set()
                all_scenarios = set()
                all_times = set()
                
                print("🔍 Scanning intermediate files to determine final dimensions...")
                for i, file_path in enumerate(var_intermediate_files):
                    print(f"   Scanning file {i+1}/{len(var_intermediate_files)}: {file_path.name}")
                    temp_ds = xr.open_dataset(file_path, engine="h5netcdf")
                    all_models.update(temp_ds.model.values)
                    all_scenarios.update(temp_ds.scenario.values)
                    all_times.update(temp_ds.time.values)
                    temp_ds.close()
                
                # Sort the coordinates
                all_models = sorted(list(all_models))
                all_scenarios = sorted(list(all_scenarios))
                all_times = sorted(list(all_times))
                
                print(f"   Final dimensions: {len(all_models)} models (includes Ensemble), {len(all_scenarios)} scenarios, {len(all_times)} time steps")
                
                # Create empty NetCDF file with correct structure (no data allocation)
                output_file = rasda_dir / f"{var}_{frequency}_ensemble.nc"
                print(f"📝 Creating empty output file: {output_file}")
                create_empty_netcdf_file(output_file, sample_ds, all_models, all_scenarios, all_times)
                sample_ds.close()
                
                # Now append data from each intermediate file
                print("📝 Appending data from intermediate files (this may take a while)...")
                for i, file_path in enumerate(var_intermediate_files):
                    print(f"   Appending file {i+1}/{len(var_intermediate_files)}: {file_path.name}")
                    append_to_netcdf(output_file, file_path, all_models, all_scenarios, all_times)
                
                # Load the final dataset for this variable
                print("📂 Loading final dataset...")
                ds = xr.open_dataset(output_file, engine="h5netcdf", chunks=chunks)
                
                print(f"✅ Final dataset shape: {dict(ds.sizes)}")
                print(f"   Models: {len(ds.model)} (including 1 ensemble)")
                print(f"   Scenarios: {len(ds.scenario)}")
                print(f"   Time steps: {len(ds.time)}")

                print("🔄 Applying final processing steps...")
                
                # Final processing steps (no duplicate - this is the only place it happens now)
                ds = reindex_and_rechunk(ds, chunks)
                ds = compute_ensemble_mean(ds)
                ds = enforce_dtypes_and_precision(ds, cmip6_var_attrs)
                # Note: map_integers moved to after replace_var_attrs to keep model names as strings longer
                ds = replace_var_attrs(ds, cmip6_var_attrs)
                ds.attrs = global_attrs
                ds = map_integers(ds, cmip6_models, cmip6_scenarios)  # Convert to integers last
                ds = replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios)
                ds = replace_lat_lon_attrs(ds)
                ds = transpose_dims(ds)
                ds = add_crs(ds, "EPSG:4326")

                # Create final output filename for this variable
                final_output_file = rasda_dir / f"cmip6_regrid_{frequency}_{var}_ensemble.nc"
                print(f"💾 Writing final dataset for {var} to {final_output_file}...")
                
                write_start_time = time.time()
                
                # Set up compression encoding for all data variables
                encoding = {}
                for var_name in ds.data_vars:
                    var = ds[var_name]
                    # Determine optimal chunk sizes based on variable dimensions
                    var_chunks = {}
                    for dim_name, dim_size in ds[var_name].dims.items():
                        if dim_name == 'time':
                            var_chunks[dim_name] = min(1000, dim_size)  # Smaller time chunks
                        elif dim_name in ['lat', 'lon']:
                            var_chunks[dim_name] = dim_size  # Full spatial dimensions
                        else:
                            var_chunks[dim_name] = min(10, dim_size)  # Small chunks for other dims
                    
                    encoding[var_name] = {
                        'zlib': True,           # Enable compression
                        'complevel': 6,         # Compression level (1-9, 6 is good balance)
                        'shuffle': True,        # Enable byte shuffling for better compression
                        'chunksizes': tuple(var_chunks.get(dim, 1) for dim in var.dims),
                        'fletcher32': True,     # Enable checksum for data integrity
                    }
                
                # use netcdf4 engine with compression for better performance and smaller files
                ds.to_netcdf(final_output_file, engine="netcdf4", mode="w", format="NETCDF4", encoding=encoding)
                write_time = time.time() - write_start_time
                
                # Get final file size
                final_size = final_output_file.stat().st_size
                
                ds.close()

                print(f"✅ Final dataset for {var} written successfully!")
                print(f"   Write time: {format_duration(write_time)}")
                print(f"   Final size: {format_bytes(final_size)}")

                # Clean up intermediate files for this variable
                cleanup_intermediate_files(var_intermediate_files)
                
                # Run CF checks on this variable's output file
                print(f"🔍 Running CF compliance checks on {final_output_file}...")
                run_cf_checks(final_output_file)
                
        else:
            # Process each variable with cascading approach
            for var_idx, var in enumerate(vars):
                print(f"\n{'='*60}")
                print(f"PROCESSING VARIABLE {var_idx+1}/{len(vars)}: {var}")
                print(f"{'='*60}")
                
                fps = list_all_files([var], models, scenarios, frequency, regrid_dir)
                total_input_files += len(fps)
                
                # Calculate total input size for this variable
                var_input_size = sum(fp.stat().st_size for fp in fps if fp.exists())
                total_input_size += var_input_size
                
                print(f"📊 Variable {var} statistics:")
                print(f"   Files: {len(fps):,}")
                print(f"   Input size: {format_bytes(var_input_size)}")
                print(f"   Estimated batches: {(len(fps) + batch_size - 1) // batch_size}")
                
                # Use cascading merge for this variable
                var_intermediate_files = cascade_merge_files(
                    fps, intermediate_dir, var, models, scenarios, frequency,
                    cmip6_var_attrs, cmip6_models, cmip6_scenarios, global_attrs,
                    batch_size=batch_size, chunks=chunks
                )
                
                all_intermediate_files.extend(var_intermediate_files)
                
                # Progress summary
                elapsed = time.time() - processing_start_time
                vars_completed = var_idx + 1
                vars_remaining = len(vars) - vars_completed
                
                print(f"\n📈 Overall Progress:")
                print(f"   Variables completed: {vars_completed}/{len(vars)}")
                print(f"   Variables remaining: {vars_remaining}")
                print(f"   Total files processed: {total_input_files:,}")
                print(f"   Total input size: {format_bytes(total_input_size)}")
                print(f"   Elapsed time: {format_duration(elapsed)}")
                
                if vars_remaining > 0:
                    avg_time_per_var = elapsed / vars_completed
                    eta = avg_time_per_var * vars_remaining
                    print(f"   ETA: {format_duration(eta)}")

                print(f"\n{'='*60}")
                print(f"FINAL MERGE PHASE FOR {var.upper()}")
                print(f"{'='*60}")
                print(f"Merging {len(var_intermediate_files)} intermediate files for {var}...")
                
                merge_start_time = time.time()
                
                # Create empty NetCDF file with correct structure and append data from intermediate files
                print("📂 Creating empty output file with correct structure...")
                
                # First, load one intermediate file to get the structure and dimensions
                sample_ds = xr.open_dataset(var_intermediate_files[0], engine="h5netcdf")
                
                # Get all unique models, scenarios, and time steps from this variable's intermediate files
                all_models = set()
                all_scenarios = set()
                all_times = set()
                
                print("🔍 Scanning intermediate files to determine final dimensions...")
                for i, file_path in enumerate(var_intermediate_files):
                    print(f"   Scanning file {i+1}/{len(var_intermediate_files)}: {file_path.name}")
                    temp_ds = xr.open_dataset(file_path, engine="h5netcdf")
                    all_models.update(temp_ds.model.values)
                    all_scenarios.update(temp_ds.scenario.values)
                    all_times.update(temp_ds.time.values)
                    temp_ds.close()
                
                # Sort the coordinates
                all_models = sorted(list(all_models))
                all_scenarios = sorted(list(all_scenarios))
                all_times = sorted(list(all_times))
                
                print(f"   Final dimensions: {len(all_models)} models (includes Ensemble), {len(all_scenarios)} scenarios, {len(all_times)} time steps")
                
                # Create empty NetCDF file with correct structure (no data allocation)
                output_file = rasda_dir / f"{var}_{frequency}_ensemble.nc"
                print(f"📝 Creating empty output file: {output_file}")
                create_empty_netcdf_file(output_file, sample_ds, all_models, all_scenarios, all_times)
                sample_ds.close()
                
                # Now append data from each intermediate file
                print("📝 Appending data from intermediate files (this may take a while)...")
                for i, file_path in enumerate(var_intermediate_files):
                    print(f"   Appending file {i+1}/{len(var_intermediate_files)}: {file_path.name}")
                    append_to_netcdf(output_file, file_path, all_models, all_scenarios, all_times)

            
            # Load the final dataset for this variable
            print("📂 Loading final dataset...")
            ds = xr.open_dataset(output_file, engine="h5netcdf", chunks=chunks)
            
            print(f"✅ Final dataset shape: {dict(ds.sizes)}")
            print(f"   Models: {len(ds.model)} (including 1 ensemble)")
            print(f"   Scenarios: {len(ds.scenario)}")
            print(f"   Time steps: {len(ds.time)}")

            print("🔄 Applying final processing steps...")
            
            # Final processing steps (no duplicate - this is the only place it happens now)
            ds = reindex_and_rechunk(ds, chunks)
            ds = compute_ensemble_mean(ds)
            ds = enforce_dtypes_and_precision(ds, cmip6_var_attrs)
            # Note: map_integers moved to after replace_var_attrs to keep model names as strings longer
            ds = replace_var_attrs(ds, cmip6_var_attrs)
            ds.attrs = global_attrs
            ds = map_integers(ds, cmip6_models, cmip6_scenarios)  # Convert to integers last
            ds = replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios)
            ds = replace_lat_lon_attrs(ds)
            ds = transpose_dims(ds)
            ds = add_crs(ds, "EPSG:4326")

            # Create final output filename for this variable
            final_output_file = rasda_dir / f"cmip6_regrid_{frequency}_{var}_ensemble.nc"
            print(f"💾 Writing final dataset for {var} to {final_output_file}...")
            
            write_start_time = time.time()
            
            # Set up compression encoding for all data variables
            encoding = {}
            for var_name in ds.data_vars:
                var = ds[var_name]
                # Determine optimal chunk sizes based on variable dimensions
                var_chunks = {}
                for dim_name, dim_size in ds[var_name].dims.items():
                    if dim_name == 'time':
                        var_chunks[dim_name] = min(1000, dim_size)  # Smaller time chunks
                    elif dim_name in ['lat', 'lon']:
                        var_chunks[dim_name] = dim_size  # Full spatial dimensions
                    else:
                        var_chunks[dim_name] = min(10, dim_size)  # Small chunks for other dims
                
                encoding[var_name] = {
                    'zlib': True,           # Enable compression
                    'complevel': 6,         # Compression level (1-9, 6 is good balance)
                    'shuffle': True,        # Enable byte shuffling for better compression
                    'chunksizes': tuple(var_chunks.get(dim, 1) for dim in var.dims),
                    'fletcher32': True,     # Enable checksum for data integrity
                }
            
            # use netcdf4 engine with compression for better performance and smaller files
            ds.to_netcdf(final_output_file, engine="netcdf4", mode="w", format="NETCDF4", encoding=encoding)
            write_time = time.time() - write_start_time
            
            # Get final file size
            final_size = final_output_file.stat().st_size
            
            ds.close()

            print(f"✅ Final dataset for {var} written successfully!")
            print(f"   Write time: {format_duration(write_time)}")
            print(f"   Final size: {format_bytes(final_size)}")

            # Clean up intermediate files for this variable
            cleanup_intermediate_files(var_intermediate_files)
            
            # Run CF checks on this variable's output file
            print(f"🔍 Running CF compliance checks on {final_output_file}...")
            run_cf_checks(final_output_file)

        # Remove intermediate directory if empty (only if not skipping generation)
        if not args["skip_intermediate_generation"]:
            try:
                intermediate_dir.rmdir()
                print("🗂️ Intermediate directory removed.")
            except OSError:
                print("⚠️ Intermediate directory not empty, leaving in place.")

    # Final progress summary
    end_time = datetime.now()
    total_processing_time = time.time() - processing_start_time
    print_final_progress(total_input_files, total_input_size, total_processing_time, 0)  # Size will vary by variable
    
    print(f"\n📅 Started: {start_time.isoformat()}")
    print(f"📅 Finished: {end_time.isoformat()}")
    print(f"⏱️ Total elapsed time: {format_duration(total_processing_time)}")
    
    # Memory summary
    final_memory = get_memory_info()
    print(f"🧠 Final memory: {final_memory['used_gb']:.1f}GB used ({final_memory['percent']:.1f}%)")
    print(f"🧠 Memory change: {final_memory['used_gb'] - initial_memory['used_gb']:+.1f}GB")
