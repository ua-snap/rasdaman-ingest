# Temp, Precip datacube for IEM webapp work

## Source data

The temperature and precipitation data used are SNAP's 771m AR5 and CRU TS (v3.1) datasets:

* [AR5 Temperature](http://ckan.snap.uaf.edu/dataset/projected-monthly-and-derived-temperature-products-771m-cmip5-ar5)
* [AR5 Precipitation](http://ckan.snap.uaf.edu/dataset/projected-monthly-and-derived-temperature-products-771m-cmip5-ar5)
* [CRU TS Temperature](http://ckan.snap.uaf.edu/dataset/historical-monthly-and-derived-temperature-products-771m-cru-ts)
* [CRU TS Precipitation](http://ckan.snap.uaf.edu/dataset/historical-monthly-and-derived-precipitation-products-771m-cru-ts)

The data ingest into Rasdaman relies on mean summaries of these data across the four periods of interest:
* 1910-2009 (CRU TS)
* 2040-2070 (AR5)
* 2070-2100 (AR5)

### Preprocessing

These data are summarized for faster querying with the `./preprocess.py` script. That script requires the following env vars to run:
* `BASE_DIR`, path to directory containing the derived precip and temp data (subfolder of GeoTIFFs)
* `AR5_GTIFF_FOLDER`, the name of the above subfolder containing the individual decadal summary GeoTIFFs for the projected data sources and model/scenario/season combinations
* `CRU_GTIFF_FOLDER`, same as above, but for the CRU TS data
* `NCORES`, the number of cores to use for `multiprocessing.Pool`

These data are available on Poseidon under:
* AR5 Temperature: `/workspace/CKAN/CKAN_Data/Base/AK_771m/projected/AR5_CMIP5_models/Projected_Monthy_and_Derived_Temperature_Products_771m_CMIP5_AR5/derived/`
* AR5 Precipitation: `/workspace/CKAN/CKAN_Data/Base/AK_771m/projected/AR5_CMIP5_models/Projected_Monthy_and_Derived_Precipitation_Products_771m_CMIP5_AR5/derived/`
* CRU TS Temperature `/workspace/CKAN/CKAN_Data/Base/AK_771m/historical/CRU_TS/Historical_Monthly_and_Derived_Temperature_Products_771m_CRU_TS/`
* CRU TS Precipitation `/workspace/CKAN/CKAN_Data/Base/AK_771m/historical/CRU_TS/Historical_Monthly_and_Derived_Precipitation_Products_771m_CRU_TS/` 

#### Example steps to run `./preprocess.py`
1. Set the base directory env var:  
`export BASE_DIR=/atlas_scratch/kmredilla/iem-webapp/`   
2. Set the geotiff folder name env vars:  
`export AR5_GTIFF_FOLDER=ar5_tas_pr_decadal_seasonal`  
`export CRU_GTIFF_FOLDER=cru_ts_tas_pr_decadal_seasonal`  
3. Make the geotiff folder env vars for unzipping CKAN data:  
`mkdir $BASE_DIR/$AR5_GTIFF_FOLDER`  
`mkdir $BASE_DIR/$CRU_GTIFF_FOLDER`  
4. Unzip and get the relevant (seasonal) GeoTIFFs into the correct GTIFF folder.  
This seems best done after getting all CKAN `.zip`s in same folder, unzipping them, and moving the seasonal files to the correct GTIFF folder, e.g.:
`cp /workspace/CKAN/CKAN_Data/Base/AK_771m/projected/AR5_CMIP5_models/Projected_Monthy_and_Derived_Temperature_Products_771m_CMIP5_AR5/derived/tas_decadal_summaries_AK_771m_5modelAvg_rcp*.zip $BASE_DIR`
`cd $BASE_DIR`  
`unzip tas_decadal_summaries_AK_771m_5modelAvg_rcp45.zip`  
Repeat  that for all models, scenarios, variables, and run this:  
`mv decadal_mean/*MAM* ar5_tas_pr_decadal_seasonal && mv decadal_mean/*DJF* ar5_tas_pr_decadal_seasonal && mv decadal_mean/*JJA* ar5_tas_pr_decadal_seasonal && mv decadal_mean/*SON* ar5_tas_pr_decadal_seasonal`  
Then do the same for the historical data. 
  
5. `export NCORES=30 # e.g. on atlas`
6. run `pipenv run python iem/tas-pr/preprocess.py` from project root

## Data structure

We only are selecting NCAR-CCSM4 and MRI-CGCM3 from AR5 data, and CRU TS31 historical data.  AR5 data were summarized into two periods: 2040-2070 and 2070-2100.  CRU TS data were summarized into one period: 1910-2009.  For the axis definitions, we're using integer indexes, mapped this way:


```
Period:
0 = 2040-2070
1 = 2070-2100
2 = 1910-2009

Season:
0 = DJF (December January February)
1 = MAM (March April May)
2 = JJA (June July August)
3 = SON (September October November)

Model:
0 = NCAR-CCSM4
1 = MRI-CGCM3
2 = TS31

Scenario:
0 = RCP4.5
1 = RCP6.0
2 = RCP8.5
3 = historical
```

`ncdump -h` output for this file:

```
netcdf ar5_cruts31_tas_pr_decadal_seasonal_aggregated {
dimensions:
    period = 3 ;
    season = 4 ;
    model = 3 ;
    scenario = 4 ;
    y = 2557 ;
    x = 4762 ;
variables:
    float tas(period, season, model, scenario, y, x) ;
        tas:_FillValue = -9999.f ;
    float pr(period, season, model, scenario, y, x) ;
        pr:_FillValue = -9999.f ;
    int64 period(period) ;
    int64 season(season) ;
    int64 model(model) ;
    int64 scenario(scenario) ;
    double y(y) ;
        y:_FillValue = NaN ;
    double x(x) ;
        x:_FillValue = NaN ;

// global attributes:
        :_NCProperties = "version=2,netcdf=4.7.4,hdf5=1.12.0," ;
}
```

Some key pieces of the ingredients file needed for this to work:

Getting the CRS definition right:

```
"recipe": {
    "name": "general_coverage",
	"options": {
        ...
        "coverage": {
			"crs": "OGC/0/Index1D?axis-label=\"period\"@OGC/0/Index1D?axis-label=\"season\"@OGC/0/Index1D?axis-label=\"model\"@OGC/0/Index1D?axis-label=\"scenario\"@EPSG/0/3338",
			...
```

This combined CRS allows us to instruct the recipe to ingest the multidimensional data according to the range of axes we have in our file.  Each individual fragment, `OGC/0/Index1D?axis-label=\"period\"`, creates a mapping between the CRS and individual axis definitions later in the configuration.

The spatial (x/y) axis setup:

```
...
"coverage": {
	...
	"slicer": {
		"type": "netcdf",
		...
		"axes": {
			...
			"X": {
              "min": "${netcdf:variable:x:min}",
              "max": "${netcdf:variable:x:max}",
              "resolution": "${netcdf:variable:x:resolution}",
              "gridOrder": 5
            },
            "Y": {
              "min": "${netcdf:variable:y:min}",
              "max": "${netcdf:variable:y:max}",
              "resolution": "${netcdf:variable:y:resolution}",
              "gridOrder": 4
            }
```

Two items to note:

   1. `"crsOrder": 4` is backwards from the grid order; the grid here refers to the geospatial reference (EPSG:3338) but the source data come in an x/y.  TBD, not sure this is working right yet.
