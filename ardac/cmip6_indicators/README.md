# CMIP6 Indicator Rasdaman Ingest

## Clone Github repository onto your user directory on Rasdaman server

Clone the Github repository in a place with lots of storage.

`cd /opt/rasdaman/user_data/<your_username> && git clone https://github.com/ua-snap/rasdaman-ingest.git`

## Generating the CMIP6 Indicators NetCDF file

All of the data needed to generate the single NetCDF file exists on Poseidon at: `/workspace/Shared/Tech_Projects/CMIP_Indicators/`. Move the data into a faster storage medium such as your storage space in the user_data in `/opt/rasdaman/` using the collect.sh file.

`bash ./collect.sh /workspace/Shared/Tech_Projects/CMIP6_Indicators /opt/rasdaman/user_data/<your_username>/rasdaman-ingest/ardac/cmip6_indicators/`

Once the data is in place, we will run the merge script to generate the single NetCDF file containing the historical and projected CMIP6 climate indicators. The folder containing the individual indicator files should be named `CMIP6_Indicators`.

`python merge.py`

This generates a `cmip6_indicators.nc` file containing all data.

## Running the ingest

Now we can run the ingest on the Rasdaman server using the ingest.json file.

First, we need to set a environment variable for LUTS_PATH:

`export LUTS_PATH=/opt/rasdaman/user_data/<your_username>/rasdaman-ingest/ardac/cmip6_indicators/luts.py`

Finally, ingest the data:

`/opt/rasdaman/bin/wcst_import.sh -c 0 ingest.json`
