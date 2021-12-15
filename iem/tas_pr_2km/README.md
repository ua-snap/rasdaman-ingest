# Temperature and Precipitation on the 2km IEM domain

This subfolder contains the ingest recipes for the following SNAP datasets:
- 2km monthly-decadal and seasonal-decadal summaries of AR5 projections for [temperature](http://ckan.snap.uaf.edu/dataset/projected-monthly-and-derived-temperature-products-2km-cmip5-ar5) and [precipitation](http://ckan.snap.uaf.edu/dataset/projected-monthly-and-derived-precipitation-products-2km-cmip5-ar5).
- 2km monthly-decadal and seasonal-decadal summaries of CRU TS 3.1 data for [temperature](http://ckan.snap.uaf.edu/dataset/historical-monthly-and-derived-temperature-products-downscaled-from-cru-ts-data-via-the-delta-m) and [precipitation](http://ckan.snap.uaf.edu/dataset/historical-monthly-and-derived-precipitation-products-downscaled-from-cru-ts-data-via-the-delta). 

It's intended use is for the Climate Impact Reports webtool, a.k.a. the "IEM webapp."

**Note** - This ingest strategy has been changed to have a separate ingest / datacube for each of AR5 and CRU TS data, instead of a single ingest for both model sources. This was done because we do not yet know how to specify values **other than zero** (default) to be used for invalid / missing combinations of axis values (e.g. model=CRU and decade=2020-2029).

## Importing

### 1. Data prep

Follow these steps to get the data from CKAN ready for ingest into rasdaman:

1. Follow the `preprocess.ipynb` notebook to extract the zipped CKAN data and clip it to the IEM domain
2. Copy both the temperature and precipitation files to folders on the Rasdaman server named as `<source>_<summary type>_data/`, i.e.:
- `ar5_seasonal_data`
- `ar5_monthly_data`
- `cru_seasonal_data`
-`cru_monthly_data`
3. In the parent directory of the `*_data/` folders, copy the `*_ingest.json` files from this repo, and the place the `luts.py` there as well (for convenience, but can technically be anywhere on the system)

### 2. Env vars

Set the `LUTS_PATH` env var to the absolute path of the `luts.py` file via e.g. `export LUTS_PATH=/home/UA/kmredilla/rasdaman-fs/iem/taspr_2km/luts.py`.

### 3. Running the import

Simply call the `wcst_import.sh` script on each of `ar5_ingest.json` and `cru_ingest.json`.
