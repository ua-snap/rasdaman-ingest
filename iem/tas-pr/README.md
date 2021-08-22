# Temp, Precip datacube for IEM webapp work

## Data structure

Temperature data are taken from (HERE TBD).  We only are selecting NCAR-CCSM4 and MRI-CGCM3.  Data were summarized into two periods: 2040-2070 and 2070-2100.  For the axis definitions, we're using integer indexes, mapped this way:


```
Season:
0 = DJF (December January February)
1 = MAM (March April May)
2 = JJA (June July August)
3 = SON (September October November)

Model:
0 = NCAR-CCSM4
1 = MRI-CGCM3

Scenario:
0 = RCP4.5
1 = RCP6.0
2 = RCP8.5

Period:
0 = 2040-2070
1 = 2070-2100
```

`ncdump -c` output for this file:

```
netcdf ar5_tas_pr_decadal_seasonal_aggregated_encoded {
dimensions:
	period = 2 ;
	season = 4 ;
	model = 2 ;
	scenario = 2 ;
	y = 2557 ;
	x = 4762 ;
variables:
	float tas(period, season, model, scenario, y, x) ;
		tas:_FillValue = NaNf ;
		tas:coordinates = "lat lon" ;
	float pr(period, season, model, scenario, y, x) ;
		pr:_FillValue = NaNf ;
		pr:coordinates = "lat lon" ;
	int64 period(period) ;
	int64 season(season) ;
	int64 model(model) ;
	int64 scenario(scenario) ;
	float lon(y, x) ;
		lon:_FillValue = NaNf ;
	float lat(y, x) ;
		lat:_FillValue = NaNf ;

// global attributes:
		:_NCProperties = "version=2,netcdf=4.7.4,hdf5=1.10.6" ;
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
			"x": {
				"min": "${netcdf:variable:x:min}",
				"max": "${netcdf:variable:x:max} + 1",
				"pixelIsPoint": true,
				"crsOrder": 4,
				"gridOrder": 5
			},
			"y": {
				"min": "${netcdf:variable:y:min}",
				"max": "${netcdf:variable:y:max} + 1",
				"pixelIsPoint": true,
				"crsOrder": 5,
				"gridOrder": 4
			}
```

Two items to note:

   1. `"max": "${netcdf:variable:x:max} + 1"` is because the extent of the data weren't matching the calculated max range for the x/y axes, so we can manually instruct the coverage to be one cell bigger.
   2. `"crsOrder": 4` is backwards from the grid order; the grid here refers to the geospatial reference (EPSG:3338) but the source data come in an x/y.  TBD, not sure this is working right yet.


### Style definitions

(These are only baselines and not very good/useful):


Temp:

```
{
"type": "intervals",
	"colorTable": {
		"-37": [215, 48, 39, 0],
		"-30": [69, 117, 180, 255],
		"-25": [116, 173, 209, 255],
		"-10": [171, 217, 233, 255],  
		"-5": [224, 243, 248, 255], 
		"5": [254, 224,144, 255],
		"10": [253, 174, 97, 255],
		"15": [244, 109, 67, 255],
		"22": [215, 48, 39, 255]
	}
}
```

Precip:

```
{
"type": "ramp",
	"colorTable": {
		"17":[255,247,251,0],
		"18":[255,247,251,255],
		"125":[236,231,242,255],
		"250":[208,209,230,255],
		"500":[166,189,219,255],
		"1000":[116,169,207,255],
		"2000":[54,144,192,255],
		"4000":[5,112,176,255],
		"6240":[3,78,123,255]
	}
}
```