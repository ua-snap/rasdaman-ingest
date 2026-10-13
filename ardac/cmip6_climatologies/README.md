# CMIP6 + WRF-ERA5 daily climatologies (tmax) Rasdaman ingest

Source: `cmip6_wrf_climatologies_tmax_daily.nc`, `tmax(model, scenario, era, dayofyear, aggregation, y, x)`, float32, EPSG:3338.

## 1. Encode the string dimensions as integers

wcst_import can't build numeric axes from string coordinates, so `model`, `scenario`, `era`, and `aggregation` are mapped to integers using [luts.py](luts.py). The reverse mapping is written to each coordinate's `encoding` attribute and ends up in the coverage metadata (`DescribeCoverage`). Data, chunking, and compression are unchanged.

The script copies the data in blocks aligned to the source chunks (~60 MB in memory at a time), but the file is ~50 GB, so run it on a compute node rather than a login node and expect it to take a while:

```
python make_rasdaman_netcdf.py cmip6_wrf_climatologies_tmax_daily.nc cmip6_wrf_climatologies_tmax_daily_rasdaman.nc
```

## 2. Split into y-slabs

Ingesting the whole file fails with `Cannot allocate 200.8 GB of memory ... exceed the memory limit set to 400.0 GB`, because wcst_import decodes each input file in a single rasql `UPDATE`. Split the file into 20-row y-slabs (23 files, ~9 GB decoded each) so each update stays small. Tiles are 1 pixel in x/y, so the split does not fragment tiles. Each slab takes a few minutes; arguments are `SRC OUT_DIR [ROWS_PER_FILE] [PARALLEL_JOBS]`:

```
./split_rasdaman_netcdf.sh cmip6_wrf_climatologies_tmax_daily_rasdaman.nc split 20 6
```

The recipe's `paths` glob (`split/..._y*.nc`) picks up all slabs. If the files are moved to `/opt/rasdaman-storage/coverage_data/cmip6_wrf_climatologies/`, update `paths` accordingly.

## 3. Ingest

```
add_coverage.sh tmax_daily_wcs_ingest.json
```

## Tiling

`ALIGNED [0:14, 0:4, 0:2, 0:364, 0:2, 0:0, 0:0] tile size 1048576`. The bracket is in `gridOrder` order (model, scenario, era, dayofyear, aggregation, Y, X). Every non-spatial axis is whole inside a tile and the spatial footprint is a single pixel, so a point query reads exactly one tile (985,500 B) and small-polygon queries read few tiles. This is poorly suited to full-map requests; use a separate WMS coverage for those. The audit repo's `recommend_tiling.py` produced this scheme (it also suggests a 2x2 footprint at 4 MiB, if fewer, larger tiles are preferred).

## After ingest

Run `DescribeCoverage` and confirm the `dayofyear` axis reports 1–365 (it is a regular `Index1D` axis, modeled on the `doy` axis in the hydroviz recipes) and that `model`/`scenario`/`era`/`aggregation` are 0–14 / 0–4 / 0–2 / 0–2.
