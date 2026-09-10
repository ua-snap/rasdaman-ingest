# piak_collab

The `combine_mean_and_deltas.py` script in this folder is used to produce the `combined_mean_and_deltas.nc` file that is ingested into Rasdaman. The `combine_mean_and_deltas.py` script is resource intensive and should be run on an `analysis` node on Chinook. It takes about 25 minutes to run.

You can use the included `environment.yml` file to install a micromamba environment with the minimal dependencies needed to run `combine_mean_and_deltas.py`.

## Setup and run

```bash
chinook04$ cd rasdaman-ingest/piak_collab
chinook04$ scp -r zeus.snap.uaf.edu:/opt/rasdaman-storage/coverage_data/piak_collab/source_files ./
chinook04$ micromamba create -f environment.yml
chinook04$ srun --partition=analysis --pty /bin/bash

analysis-node$ micromamba activate piak-collab
analysis-node$ python combine_mean_and_deltas.py
```