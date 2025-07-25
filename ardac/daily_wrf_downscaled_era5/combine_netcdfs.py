import glob
import time
import os
import sys

import xarray as xr
from dask.distributed import Client, LocalCluster


def merge_netcdfs(variable_name):
    """
    Merges yearly NetCDF files to create a single NetCDF file before ingesting into rasdaman.
    """
    input_dir = variable_name
    output_file = f"{variable_name}_merged.nc"

    print(f"Starting netCDF merge script for {variable_name}...")

    try:
        search_pattern = os.path.join(input_dir, "*.nc")
        file_list = sorted(glob.glob(search_pattern))

        if not file_list:
            print(f"Error: No NetCDF files found. Aborting.", file=sys.stderr)
            sys.exit(1)

        print(
            f"Found {len(file_list)} files. Opening sequentially..."
        )

        if os.path.exists(output_file):
            print(f"Removing existing merged file: {output_file}")
            os.remove(output_file)

        # Open all files sequentially in a single thread.
        with xr.open_mfdataset(file_list, combine="by_coords", engine="netcdf4") as ds:
            print(
                "Dataset created successfully. Now starting Dask cluster for parallel write."
            )

            # CP note: cluster config seems good on Zeus with 96 cores for the I/O-heavy write operation.
            cluster = LocalCluster(
                n_workers=44, threads_per_worker=2, memory_limit="8GB"
            )
            client = Client(cluster)
            print(f"Dask dashboard available at: {client.dashboard_link}")

            try:
                print("Preparing parallel write operation...")
                write_job = ds.to_netcdf(
                    output_file,
                    encoding={
                        variable_name: {
                            "chunksizes": (
                                366,
                                128,
                                128,
                            )  # CP note: huge speedup with chunk scheme
                        }
                    },
                    compute=False,
                )
                print("Executing parallel write.")
                write_job.compute()
            finally:
                time.sleep(5)
                # Always ensure the cluster is shut down
                print("Shutting down Dask client and cluster.")
                client.close()
                cluster.close()
                time.sleep(10) # CP note: yeah I'm just sprinkling random sleeps in here for stability

        print("Preprocessing complete. Merged file created successfully.")

    except Exception as e:
        print(f"An error occurred during processing: {e}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python combine_netcdfs.py <variable_name>")
        sys.exit(1)
    merge_netcdfs(sys.argv[1])
    time.sleep(10)
