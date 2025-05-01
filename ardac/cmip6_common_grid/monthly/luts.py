models = {
    "CESM2": 0,
    "CNRM-CM6-1-HR": 1,
    "E3SM-1-1": 2,
    "E3SM-2-0": 3,
    "EC-Earth3-Veg":4,
    "GFDL-ESM4": 5,
    "HadGEM3-GC31-LL": 6,
    "HadGEM3-GC31-MM": 7,
    "KACE-1-0-G": 8,
    "MIROC6": 9,
    "MPI-ESM1-2-HR": 10,
    "MRI-ESM2-0": 11,
    "NorESM2-MM": 12,
    "TaiESM1": 13,
}

varname = {
    "clt": 0,
    "evspsbl": 1,
    "hfls": 2,
    "hfss": 3,
    "pr": 4,
    "prsn": 5,
    "psl": 6,
    "rlds": 7,
    "rsds": 8,
    "sfcWind": 9,
    "siconc": 10,
    "snw": 11,
    "tas": 12,
    "tasmax": 13,
    "tasmin": 14,
    "ts": 15,
    "uas": 16,
    "vas": 17,
}

var_group_id_lu = {
    "v1_1": ["tas", "tasmax", "tasmin", "pr", "sfcWind", "sfcWindmax"],
    "v1_2": [
        "clt",
        "evspsbl",
        "hfls",
        "hfss",
        "psl",
        "rlds",
        "rsds",
        "ts",
        "uas",
        "vas",
    ],
    "v2": ["siconc", "prsn", "snw"],
}

scenarios = {
    "historical": 0,
    "ssp126": 1,
    "ssp245": 2,
    "ssp370": 3,
    "ssp585": 4,
}

