# CMIP5 ALFRESCO relative flammability

This subfolder contains the processing notebook and ingest recipes for a relative flammability dataset. These data are created from outputs of the ALFRESCO runs done with CMIP5 outputs for the SERDP Fish and Fire project, and can be found at `/workspace/Shared/Tech_Projects/SERDP_Fish_Fire/project_files/Calibration/HighCalib/FMO_Calibrated`.

It's intended use is for the Climate Impact Reports webtool, a.k.a. the "IEM webapp."

## Importing

### 1. Data prep

Follow these steps to get the data from CKAN ready for ingest into rasdaman:

1. Follow the `relative_flammability.ipynb` notebook to create the relative flammability tifs for historical and future eras  
2. Copy both the temperature and precipitation files to folders on the Rasdaman server named as `<era group>_relative_flammability/`, i.e.:  
- `future_relative_flammability`  
- `historical_relative_flammability`  
3. In the parent directory of the `*_relative_flammability/` folders, copy the `*_ingest.json` files from this repo, and the place the `luts.py` there as well (for convenience, but can technically be anywhere on the system)  

### 2. Env vars

Set the `LUTS_PATH` env var to the absolute path of the `luts.py` file via e.g. `export LUTS_PATH=/home/UA/kmredilla/rasdaman-fs/alfresco/relative_flammability/luts.py`.

### 3. Running the import

Simply call the `wcst_import.sh` script on each of `historical_ingest.json` and `future_ingest.json`.
