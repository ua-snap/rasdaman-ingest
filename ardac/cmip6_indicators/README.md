# CMIP6 Indicator Rasdaman Ingest

## Clone Github repository

Clone the Github repository in a place with lots of storage. You can perform the processing anywhere, as long as you are able to transfer the output `cmip6_indicators_ensemble.nc` file and `ingest.json` file to your Rasdaman user directory at `/opt/rasdaman/user_data/<your_user_name>`.

## Generate the CMIP6 Indicators NetCDF file

Make a local copy of pre-existing indicator outputs, or compute the indicators using the [cmip6-utils/indicators](https://github.com/ua-snap/cmip6-utils/tree/main/indicators) repo.

Run the `combine_indicators_ensemble.py` script to generate the single NetCDF file containing the historical and projected CMIP6 climate indicators. This generates the `cmip6_indicators_ensemble.nc` file containing all data.

## Transfer to Rasdaman server and ingest

Transfer the output `cmip6_indicators_ensemble.nc` file and `ingest.json` file to your Rasdaman user directory at `/opt/rasdaman/user_data/<your_user_name>`. Run the ingest on the Rasdaman server using the `ingest.json` file.

`add_coverage.sh ingest.json`
