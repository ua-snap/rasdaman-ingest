models = {
    "CESM2": 0,
    "CNRM-CM6-1-HR": 1,
    "EC-Earth3-Veg": 2,
    "GFDL-ESM4": 3,
    "HadGEM3-GC31-LL": 4,
    "HadGEM3-GC31-MM": 5,
    "KACE-1-0-G": 6,
    "MIROC6": 7,
    "MRI-ESM2-0": 8,
    "NorESM2-MM": 9,
    "TaiESM1": 10,
    # MPI is the last model to be added
    #  because it has no historical data
    #  (currently as of 10/8/24, perhaps bug in processing)
    "MPI-ESM1-2-HR": 11,
}

varname = {
    "clt": 0,
    "evspsbl": 1,
    "hfls": 2,
    "hfss": 3,
    "pr": 4,
    "psl": 5,
    "rlds": 6,
    "rsds": 7,
    "sfcWind": 8,
    "tas": 9,
    "tasmax": 10,
    "tasmin": 11,
    "ts": 12,
    "uas": 13,
    "vas": 14,
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
}

scenarios = {
    "historical": 0,
    "ssp126": 1,
    "ssp245": 2,
    "ssp370": 3,
    "ssp585": 4,
}

