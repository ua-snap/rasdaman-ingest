#!/usr/bin/env bash
#SBATCH --job-name=rasdaman_nc
#SBATCH --partition=analysis
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=2-00:00:00
#SBATCH --output=%x_%j.out
#
# Usage: sbatch make_rasdaman_netcdfs.slurm SRC.nc [--rasdaman-out DST.nc] [--wms-out DST.nc]
set -euo pipefail

cd "${SLURM_SUBMIT_DIR:?run with sbatch}"
/home/crstephenson/miniconda3/envs/cmip6-utils/bin/python make_rasdaman_netcdfs.py "$@"
