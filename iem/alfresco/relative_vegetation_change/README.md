# CMIP5 ALFRESCO relative vegetation change

This subfolder contains the processing notebook and ingest recipes for a relative vegetation change dataset. These data are created from outputs of the ALFRESCO runs done with CMIP5 outputs for the IEM project, and can be found at `/workspace/Shared/Tech_Projects/Alaska_IEM/project_data/Final_runs/IEM_AR5`.

It's intended use is for the Climate Impact Reports webtool, a.k.a. the "IEM webapp."

## Importing

### 1. Data prep

Follow these steps to get the data from CKAN ready for ingest into rasdaman:

1. Execute the `relative_vegetation_change.ipynb` notebook to create the relative vegetation change tifs for historical and future eras  
2. Copy these files to folders on the Rasdaman server named as `<era group>_relative_vegetation_change/`, i.e.:  
- `future_relative_vegetation_change`  
- `historical_relative_vegetation_change`  
3. In the parent directory of the `*_relative_vegetation_change/` folders, copy the `*_ingest.json` files from this repo, and the place the `luts.py` there as well (for convenience, but can technically be anywhere on the system)  

### 2. Env vars

Set the `LUTS_PATH` env var to the absolute path of the `luts.py` file via e.g. `export LUTS_PATH=/home/UA/kmredilla/rasdaman-fs/alfresco/vegetation_change/luts.py`.

### 3. Running the import

Simply call the `wcst_import.sh` script on each of `historical_ingest.json` and `future_ingest.json`.
