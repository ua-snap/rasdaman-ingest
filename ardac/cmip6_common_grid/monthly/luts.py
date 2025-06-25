import numpy as np

cmip6_models = {
    "CESM2": 0,
    "CNRM-CM6-1-HR": 1,
    "E3SM-2-0": 2,
    "EC-Earth3-Veg": 3,
    "GFDL-ESM4": 4,
    "HadGEM3-GC31-LL": 5,
    "HadGEM3-GC31-MM": 6,
    "KACE-1-0-G": 7,
    "MIROC6": 8,
    "MPI-ESM1-2-HR": 9,
    "MRI-ESM2-0": 10,
    "NorESM2-MM": 11,
    "TaiESM1": 12,
    "Ensemble": 13,
}

cmip6_scenarios = {
    "historical": 0,
    "ssp126": 1,
    "ssp245": 2,
    "ssp370": 3,
    "ssp585": 4,
}

# attribute definitions for CMIP6 variables from https://airtable.com/appYNLuWqAgzLbhSq/shrKcLEdssxb8Yvcp/tblL7dJkC3vl5zQLb
cmip6_var_attrs = {
    "clt": {
        "units": "percent",
        "standard_name": "cloud_area_fraction",
        "long_name": "Total Cloud Cover Percentage",
        "description": "Total cloud area fraction (reported as a percentage) for the whole atmospheric column, as seen from the surface or the top of the atmosphere. Includes both large-scale and convective cloud.",
        "_FillValue": -9999,
        "dtype": "int32",
        "precision": 0,
    },
    "evspsbl": {
        "units": "kg m-2 s-1",
        "standard_name": "water_evapotranspiration_flux",
        "long_name": "Evapotranspiration Including Sublimation and Transpiration",
        "description": "Evaporation at surface (also known as evapotranspiration): flux of water into the atmosphere due to conversion of both liquid and solid phases to vapor (from underlying surface and vegetation)",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 15,
    },
    "hfls": {
        "units": "W m-2",
        "standard_name": "surface_upward_latent_heat_flux",
        "long_name": "Surface Upward Latent Heat Flux",
        "description": "The surface called 'surface' means the lower boundary of the atmosphere. 'Upward' indicates a vector component which is positive when directed upward (negative downward). The surface latent heat flux is the exchange of heat between the surface and the air on account of evaporation (including sublimation). In accordance with common usage in geophysical disciplines, 'flux' implies per unit area, called 'flux density' in physics.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 10,
    },
    "hfss": {
        "units": "W m-2",
        "standard_name": "surface_upward_sensible_heat_flux",
        "long_name": "Surface Upward Sensible Heat Flux",
        "description": "The surface sensible heat flux, also called turbulent heat flux, is the exchange of heat between the surface and the air by motion of air.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 10,
    },
    "pr": {
        "units": "mm",  # standard units are "kg m-2 s-1", but we convert these in regridding here: https://github.com/ua-snap/cmip6-utils/blob/d9ee45e1ed9e802896b0ee6e2c9d97eb5db7990d/regridding/regrid.py#L826
        "standard_name": "precipitation_flux",
        "long_name": "Precipitation",
        "description": "Includes both liquid and solid phases.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 1,
    },
    "prsn": {
        "units": "mm",  # standard units are "kg m-2 s-1", but we convert these in regridding here: https://github.com/ua-snap/cmip6-utils/blob/d9ee45e1ed9e802896b0ee6e2c9d97eb5db7990d/regridding/regrid.py#L826
        "standard_name": "snowfall_flux",
        "long_name": "Snowfall Flux",
        "description": "At surface; includes precipitation of all forms of water in the solid phase.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 1,
    },
    "psl": {
        "units": "Pa",
        "standard_name": "air_pressure_at_mean_sea_level",
        "long_name": "Sea Level Pressure",
        "description": "Sea Level Pressure.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 2,
    },
    "rlds": {
        "units": "W m-2",
        "standard_name": "surface_downwelling_longwave_flux_in_air",
        "long_name": "Surface Downwelling Longwave Radiation",
        "description": "The surface called 'surface' means the lower boundary of the atmosphere. 'longwave' means longwave radiation. Downwelling radiation is radiation from above. It does not mean 'net downward'. When thought of as being incident on a surface, a radiative flux is sometimes called 'irradiance'. In addition, it is identical with the quantity measured by a cosine-collector light-meter and sometimes called 'vector irradiance'. In accordance with common usage in geophysical disciplines, 'flux' implies per unit area, called 'flux density' in physics.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 2,
    },
    "rsds": {
        "units": "W m-2",
        "standard_name": "surface_downwelling_shortwave_flux_in_air",
        "long_name": "Surface Downwelling Shortwave Radiation",
        "description": "Surface solar irradiance for UV calculations.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 2,
    },
    "sfcWind": {
        "units": "m s-1",
        "standard_name": "wind_speed",
        "long_name": "Near-Surface Wind Speed",
        "description": "Near-surface (usually, 10 meters) wind speed.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 2,
    },
    "siconc": {
        "units": "percent",
        "standard_name": "sea_ice_area_fraction",
        "long_name": "Sea Ice Area Percentage",
        "description": "Percentage of grid cell covered by sea ice.",
        "_FillValue": -9999,
        "dtype": "int32",
        "precision": 0,
    },
    "snw": {
        "units": "kg m-2",
        "standard_name": "surface_snow_amount",
        "long_name": "Surface Snow Amount",
        "description": "Total water mass of the snowpack (liquid or frozen), averaged over a grid cell and intercepted by the canopy.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 1,
    },
    "tas": {
        "units": "degC",  # standard units are "K", but we convert these in regridding here: https://github.com/ua-snap/cmip6-utils/blob/d9ee45e1ed9e802896b0ee6e2c9d97eb5db7990d/regridding/regrid.py#L826
        "standard_name": "air_temperature",
        "long_name": "Near-Surface Air Temperature",
        "description": "Near-surface (usually, 2 meter) air temperature.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 1,
    },
    "tasmax": {
        "units": "degC",  # standard units are "K", but we convert these in regridding here: https://github.com/ua-snap/cmip6-utils/blob/d9ee45e1ed9e802896b0ee6e2c9d97eb5db7990d/regridding/regrid.py#L826
        "standard_name": "air_temperature",
        "long_name": "Daily Maximum Near-Surface Air Temperature",
        "description": "Maximum near-surface (usually, 2 meter) air temperature.",
        "cell_methods": "time: maximum",  # must be added for CF convention since standard_name is ambiguous
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 1,
    },
    "tasmin": {
        "units": "degC",  # standard units are "K", but we convert these in regridding here: https://github.com/ua-snap/cmip6-utils/blob/d9ee45e1ed9e802896b0ee6e2c9d97eb5db7990d/regridding/regrid.py#L826
        "standard_name": "air_temperature",
        "long_name": "Daily Minimum Near-Surface Air Temperature",
        "description": "Minimum near-surface (usually, 2 meter) air temperature.",
        "cell_methods": "time: minimum",  # must be added for CF convention since standard_name is ambiguous
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 1,
    },
    "ts": {
        "units": "K",
        "standard_name": "surface_temperature",
        "long_name": "Surface Temperature",
        "description": "Temperature of the lower boundary of the atmosphere.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 1,
    },
    "uas": {
        "units": "m s-1",
        "standard_name": "eastward_wind",
        "long_name": "Eastward Near-Surface Wind",
        "description": "Eastward component of the near-surface (usually, 10 meters) wind.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 2,
    },
    "vas": {
        "units": "m s-1",
        "standard_name": "northward_wind",
        "long_name": "Northward Near-Surface Wind",
        "description": "Northward component of the near-surface (usually, 10 meters) wind.",
        "_FillValue": np.nan,
        "dtype": "float32",
        "precision": 2,
    },
}

title_fmt_str = "CMIP6 {frequency} Data on a Common Grid with Multi-Model Ensemble Mean"
description_fmt_str = "{frequency} data from {number_of_models} CMIP6 models on a common grid, including multi-model ensemble mean calculated for each variable. Models include {models}. Scenarios include {scenarios}. Variables include {variables}. Multi-model ensemble mean is calculated for each variable across all available models for each scenario; some variables do not have data for all models or scenarios."

global_attrs = {
    "Conventions": "CF-1.8",
    "title": "",
    "description": "",
    "institution": "Scenarios Network for Alaska and Arctic Planning, University of Alaska Fairbanks, International Arctic Research Center",
    "source": "CMIP6 model output",
    "contact": "uaf-snap-data-tools@alaska.edu",
    "url": "https://uaf-snap.org/",
}
