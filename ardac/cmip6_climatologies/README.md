# CMIP6 + WRF-ERA5 daily climatologies (tmax) Rasdaman ingest

Source: `cmip6_wrf_climatologies_tmax_daily.nc`, `tmax(model, scenario, era, dayofyear, aggregation, y, x)`, float32, EPSG:3338.

## 1. Encode the string dimensions as integers

wcst_import can't build numeric axes from string coordinates, so `model`, `scenario`, `era`, and `aggregation` are mapped to integers using [luts.py](luts.py). The reverse mapping is written to each coordinate's `encoding` attribute and ends up in the coverage metadata (`DescribeCoverage`). Data, chunking, and compression are unchanged.

[make_rasdaman_netcdfs.py](make_rasdaman_netcdfs.py) also writes a second, much smaller NetCDF for a WMS coverage (see [WMS coverage](#wms-coverage)). Both are produced in one pass over the source, in blocks aligned to the source chunks (~1 GB in memory at a time). The source is ~50 GB, so submit it as a Slurm job rather than running it on the head node, and expect it to take a while. `--rasdaman-out` and `--wms-out` are each optional, but give at least one:

```
sbatch make_rasdaman_netcdfs.slurm cmip6_wrf_climatologies_tmax_daily.nc \
    --rasdaman-out cmip6_wrf_climatologies_tmax_daily_wcs.nc \
    --wms-out cmip6_wrf_climatologies_tmax_daily_wms.nc
```

## 2. Split into y-slabs

Ingesting the whole file fails with `Cannot allocate 200.8 GB of memory ... exceed the memory limit set to 400.0 GB`, because wcst_import decodes each input file in a single rasql `UPDATE`. Split the file into 20-row y-slabs (23 files, ~9 GB decoded each) so each update stays small. Tiles are 1 pixel in x/y, so the split does not fragment tiles. Each slab takes a few minutes; arguments are `SRC OUT_DIR [ROWS_PER_FILE] [PARALLEL_JOBS]`:

```
./split_rasdaman_netcdf.sh cmip6_wrf_climatologies_tmax_daily_wcs.nc split 20 6
```

The recipe's `paths` glob (`split/..._y*.nc`) picks up all slabs. If the files are moved to `/opt/rasdaman-storage/coverage_data/cmip6_wrf_climatologies/`, update `paths` accordingly.

## 3. Ingest

```
add_coverage.sh tmax_daily_wcs_ingest.json
```

## Tiling

`ALIGNED [0:14, 0:4, 0:2, 0:364, 0:2, 0:0, 0:0] tile size 1048576`. The bracket is in `gridOrder` order (model, scenario, era, dayofyear, aggregation, Y, X). Every non-spatial axis is whole inside a tile and the spatial footprint is a single pixel, so a point query reads exactly one tile (985,500 B) and small-polygon queries read few tiles. This is poorly suited to full-map requests; use a separate WMS coverage for those. The audit repo's `recommend_tiling.py` produced this scheme (it also suggests a 2x2 footprint at 4 MiB, if fewer, larger tiles are preferred).

## WMS coverage

The WCS coverage above is tiled for point queries, so full-map WMS requests would read hundreds of thousands of tiles. `make_rasdaman_netcdfs.py --wms-out` therefore writes a separate, much smaller file, `tmax(scenario, era, dayofyear, y, x)`, with the `model` dimension removed by averaging across the 13 individual CMIP6 models (`CMIP6-Ensemble` and `WRF-ERA5` are excluded). Only the `temporal_mean` aggregation is kept, so the `aggregation` dimension is removed too: each value is the mean of the models' `temporal_mean`.

NaNs are skipped, so a cell is NaN only if no model has data. The other coordinates use the same integer codes as the WCS file. Ingest it with [tmax_daily_wms_ingest.json](tmax_daily_wms_ingest.json) (`wms_import: true`; the file is ~4.4 GB decoded, so it does not need splitting):

```
add_coverage.sh tmax_daily_wms_ingest.json
```

Tiling is `ALIGNED [0:0, 0:0, 0:364, 0:52, 0:52] tile size 4194304`: each tile is one scenario, one era, all 365 days, and a 53 x 53 pixel spatial block (4,101,140 B). The style's WCPS fragment condenses over every day of year, so a GetMap request reads all days for the one selected scenario/era, and keeping `dayofyear` whole in a tile means that is ~81 tiles (9 x 9 spatial blocks) instead of 365 per-day tiles. Smaller viewports read proportionally fewer tiles. Individual days are never requested on their own, so there is no reason to split `dayofyear`.

The ingest recipe's `after_import` hooks add five-bucket `intervals` styles (RdYlBu palette, values in degC; each bucket starts at its threshold). Thresholds come from the distribution of the WMS file's values (about -58 to 55 degC; ~45% of cells are NaN and render transparent):

| Style | Use | Bucket thresholds (degC) |
|---|---|---|
| `ardac_tmax_daily` | temporal mean | -20, 0, 10, 20 |

The lowest bucket starts at -100, and `-9999` maps to transparent.

## After ingest

Run `DescribeCoverage` and confirm the `dayofyear` axis reports 1–365 (it is a regular `Index1D` axis, modeled on the `doy` axis in the hydroviz recipes) and that `model`/`scenario`/`era`/`aggregation` are 0–14 / 0–4 / 0–2 / 0–2 for the WCS coverage and `scenario`/`era` are 0–4 / 0–2 for the WMS coverage (which has no `model` or `aggregation` axis).
