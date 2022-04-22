# CMIP5 ALFRESCO relative flammability

This subfolder contains the processing notebook and ingest recipes for a relative flammability dataset. These data are created from outputs of the ALFRESCO runs done with CMIP5 outputs for the IEM project, and can be found at `/workspace/Shared/Tech_Projects/Alaska_IEM/project_data/Final_runs/IEM_AR5`.

It's intended use is for the Climate Impact Reports webtool, a.k.a. the "IEM webapp."
## Importing

### 1. Data prep

Follow these steps to get the data from CKAN ready for ingest into rasdaman:

1. Follow the `relative_flammability.ipynb` notebook to create the relative flammability tifs for historical and future eras  
2. Copy the GeoTIFF outputs to a Rasdaman server to a ingest directory into a subdirectory called `geotiffs`
3. In the parent ingest directory of `geotiffs`, copy the `ingest.json` and the `luts.py` file from this repo (for convenience, but `luts.py` can technically be anywhere on the system)

### 2. Env vars

Set the `LUTS_PATH` env var to the absolute path of the `luts.py` file via e.g. `export LUTS_PATH=/home/UA/kmredilla/rasdaman-fs/alfresco/relative_flammability/luts.py`.

### 3. Running the importt

Run `wcst_import.sh ingest.json`
