models = {
    "CESM2": 0,
    "CNRM-CM6-1-HR": 12,
    "E3SM-1-1": 1,
    "E3SM-2-0": 13,
    "EC-Earth3-Veg": 2,
    "GFDL-ESM4": 3,
    "HadGEM3-GC31-LL": 4,
    "HadGEM3-GC31-MM": 5,
    "KACE-1-0-G": 6,
    "MIROC6": 7,
    "MPI-ESM1-2-HR": 8,
    "MRI-ESM2-0": 9,
    "NorESM2-MM": 10,
    "TaiESM1": 11,
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

