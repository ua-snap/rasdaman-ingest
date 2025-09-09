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
    for var in ds.data_vars:
        ds[var] = ds[var].reindex(model=all_models, scenario=all_scenarios)
        # explicitly rechunk to align dask chunks for all variables
        chunks["model"] = len(all_models)
        chunks["scenario"] = len(all_scenarios)
        ds[var] = ds[var].chunk(chunks)

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
        ds = map_integers(ds, cmip6_models, cmip6_scenarios)
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
    print("Running CF checks on the output file...")

    output_fp = fp.with_suffix(".cfchecks.txt")
    with open(output_fp, "w") as out_file:
        subprocess.run(["cfchecks", str(fp)], stdout=out_file, stderr=subprocess.STDOUT)
    print("CF checks run, output saved to", output_fp)

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
    }


if __name__ == "__main__":

    start_time = datetime.now()
    print("Starting script at: ", start_time.isoformat())

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
        n_workers=8,  # Optimized for 24-28 core system (8 workers × 3-3.5 threads = 24-28 cores)
        threads_per_worker=3,  # 3 threads per worker for optimal CPU utilization
        memory_limit="14GB",  # 8 × 14GB = 112GB (leaves 16GB for OS and overhead)
        #dashboard_address=":8787",  # Dashboard disabled - using terminal progress monitoring
        processes=True,  # Use processes instead of threads for better parallelism
    ) as client:

        all_intermediate_files = []
        total_input_files = 0
        total_input_size = 0
        processing_start_time = time.time()

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
        print(f"FINAL MERGE PHASE")
        print(f"{'='*60}")
        print(f"Merging {len(all_intermediate_files)} intermediate files into final dataset...")
        
        merge_start_time = time.time()
        
        # Final merge of all intermediate files
        ds = xr.open_mfdataset(
            all_intermediate_files,
            parallel=True,
            combine="by_coords",
            engine="h5netcdf",
            decode_cf=True,
            coords="minimal",
            compat="no_conflicts",
            chunks=chunks,
        )

        print("🔄 Applying final processing steps...")
        
        # Final processing steps
        ds = reindex_and_rechunk(ds, chunks)
        ds = compute_ensemble_mean(ds)
        ds = enforce_dtypes_and_precision(ds, cmip6_var_attrs)
        ds = map_integers(ds, cmip6_models, cmip6_scenarios)
        ds = replace_var_attrs(ds, cmip6_var_attrs)
        ds.attrs = global_attrs
        ds = replace_model_scenario_attrs(ds, cmip6_models, cmip6_scenarios)
        ds = replace_lat_lon_attrs(ds)
        ds = transpose_dims(ds)
        ds = add_crs(ds, "EPSG:4326")

        # combine vars as "_" separated string
        var_str = "_".join(sorted(vars))

        out_fp = rasda_dir / f"cmip6_regrid_{frequency}_{var_str}_ensemble.nc"
        print(f"💾 Writing final combined dataset with ensemble mean to {out_fp}...")
        
        write_start_time = time.time()
        # use netcdf4 engine for better performance with complex merge operations
        ds.to_netcdf(out_fp, engine="netcdf4", mode="w", format="NETCDF4")
        write_time = time.time() - write_start_time
        
        # Get final file size
        final_size = out_fp.stat().st_size
        
        ds.close()

        # Calculate total processing time
        total_processing_time = time.time() - processing_start_time
        merge_time = time.time() - merge_start_time
        
        print(f"✅ Final dataset written successfully!")
        print(f"   Write time: {format_duration(write_time)}")
        print(f"   Final size: {format_bytes(final_size)}")

        # Clean up intermediate files
        cleanup_intermediate_files(all_intermediate_files)
        
        # Remove intermediate directory if empty
        try:
            intermediate_dir.rmdir()
            print("🗂️ Intermediate directory removed.")
        except OSError:
            print("⚠️ Intermediate directory not empty, leaving in place.")

        # Final progress summary
        end_time = datetime.now()
        print_final_progress(total_input_files, total_input_size, total_processing_time, final_size)
        
        print(f"\n📅 Started: {start_time.isoformat()}")
        print(f"📅 Finished: {end_time.isoformat()}")
        print(f"📁 Output file: {out_fp}")
        print(f"⏱️ Total elapsed time: {format_duration(total_processing_time)}")
        
        # Memory summary
        final_memory = get_memory_info()
        print(f"🧠 Final memory: {final_memory['used_gb']:.1f}GB used ({final_memory['percent']:.1f}%)")
        print(f"🧠 Memory change: {final_memory['used_gb'] - initial_memory['used_gb']:+.1f}GB")

    # run CF checks on the output file
    run_cf_checks(out_fp)
