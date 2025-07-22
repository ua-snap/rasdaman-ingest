import xarray as xr
import glob
import os
import sys
from dask.distributed import Client, LocalCluster


def merge_netcdfs_final(variable_name):
    """
    Merges yearly NetCDF files to create a single NetCDF file before ingesting into rasdaman.
    """
    input_dir = variable_name
    output_file = f"{variable_name}_merged.nc"

    print(f"Starting final preprocessing script for {variable_name}...")

    try:
        search_pattern = os.path.join(input_dir, "*.nc")
        file_list = sorted(glob.glob(search_pattern))

        if not file_list:
            print(f"Error: No NetCDF files found. Aborting.", file=sys.stderr)
            sys.exit(1)

        print(
            f"Found {len(file_list)} files. Opening sequentially to create lazy dataset..."
        )

        if os.path.exists(output_file):
            print(f"Removing existing merged file: {output_file}")
            os.remove(output_file)

        # Open all files sequentially in a single thread.
        with xr.open_mfdataset(file_list, combine="by_coords", engine="netcdf4") as ds:
            print(
                "Lazy dataset created successfully. Now starting Dask cluster for parallel write."
            )

            # Fire up the Dask cluster to handle the I/O-heavy write operation in a fully parallel manner.
            cluster = LocalCluster(
                n_workers=36, threads_per_worker=36, memory_limit="8GB"
            )
            client = Client(cluster)
            print(f"--> Dask dashboard available at: {client.dashboard_link} <--")

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
                            )  # CP note: huge speedup with this
                        }
                    },
                    compute=False,
                )
                print("Executing parallel write.")
                write_job.compute()
            finally:
                # Always ensure the cluster is shut down
                print("Shutting down Dask client and cluster.")
                client.close()
                cluster.close()

        print("Preprocessing complete. Merged file created successfully.")

    except Exception as e:
        print(f"An error occurred during processing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python combine_netcdfs.py <variable_name>")
        sys.exit(1)
    merge_netcdfs_final(sys.argv[1])
