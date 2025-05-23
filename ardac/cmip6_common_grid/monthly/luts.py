import json

cmip6_models = {
    "CESM2": 0,
    "CNRM-CM6-1-HR": 1,
    # "E3SM-1-1": 2,
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

cmip6_var_attrs = {
    "clt": {"units": "", "long_name": "", "description": ""},
    "evspsbl": {"units": "", "long_name": "", "description": ""},
    "hfls": {"units": "", "long_name": "", "description": ""},
    "hfss": {"units": "", "long_name": "", "description": ""},
    "pr": {"units": "", "long_name": "", "description": ""},
    "prsn": {"units": "", "long_name": "", "description": ""},
    "psl": {"units": "", "long_name": "", "description": ""},
    "rlds": {"units": "", "long_name": "", "description": ""},
    "rsds": {"units": "", "long_name": "", "description": ""},
    "sfcWind": {"units": "", "long_name": "", "description": ""},
    "siconc": {"units": "", "long_name": "", "description": ""},
    "snw": {"units": "", "long_name": "", "description": ""},
    "tas": {"units": "", "long_name": "", "description": ""},
    "tasmax": {"units": "", "long_name": "", "description": ""},
    "tasmin": {"units": "", "long_name": "", "description": ""},
    "ts": {"units": "", "long_name": "", "description": ""},
    "uas": {"units": "", "long_name": "", "description": ""},
    "vas": {"units": "", "long_name": "", "description": ""},
}


# reverse the dicts for decoding rasdaman returns
rasdaman_encodings = {
    "models": {v: k for k, v in cmip6_models.items()},
    "scenarios": {v: k for k, v in cmip6_scenarios.items()},
}

global_attrs = {
    # "Conventions": "CF-1.8",
    "title": "CMIP6 regridded data",
    "institution": "Scenarios Network for Alaska and Arctic Planning, University of Alaska Fairbanks, International Arctic Research Center",
    "source": "CMIP6 model output",
    "contact": "uaf-snap-data-tools@alaska.edu",
    "url": "https://uaf-snap.org/",
    # convert the rasdaman_encodings to a string
    "encodings": json.dumps(rasdaman_encodings),
}
