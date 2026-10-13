#!/usr/bin/env bash
# Split the Rasdaman-ready NetCDF into y-slabs so wcst_import never decodes the
# whole ~200 GB array in a single rasql UPDATE (which exceeds rasdaman's memory limit).
#
# Usage: ./split_rasdaman_netcdf.sh SRC.nc OUT_DIR [ROWS_PER_FILE] [PARALLEL_JOBS]
set -euo pipefail

src=${1:?usage: $0 SRC.nc OUT_DIR [ROWS_PER_FILE] [PARALLEL_JOBS]}
out=${2:?usage: $0 SRC.nc OUT_DIR [ROWS_PER_FILE] [PARALLEL_JOBS]}
rows=${3:-20}
max_jobs=${4:-4}

mkdir -p "$out"
ny=$(ncks -m "$src" | sed -n 's/^ *y = \([0-9]*\) ;.*/\1/p' | head -n1)
[ -n "$ny" ] || { echo "could not determine size of y" >&2; exit 1; }

base=$(basename "$src" .nc)

split_slab() {
    local start=$1 end=$2 f
    f=$(printf '%s/%s_y%04d-%04d.nc' "$out" "$base" "$start" "$end")
    ncks -O -d y,"$start","$end" "$src" "$f.tmp"
    mv "$f.tmp" "$f"
    echo "wrote $f"
}

for ((start = 0; start < ny; start += rows)); do
    end=$((start + rows - 1))
    ((end >= ny)) && end=$((ny - 1))
    while (($(jobs -rp | wc -l) >= max_jobs)); do wait -n; done
    split_slab "$start" "$end" &
done
wait
