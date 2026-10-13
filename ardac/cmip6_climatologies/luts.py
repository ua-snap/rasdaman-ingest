"""Lookup tables for encoding the string dimensions of the CMIP6/WRF climatologies
NetCDF as integers for Rasdaman. wcst_import can only build numeric Index1D axes,
so each string coordinate is replaced with the integer below and the reverse
mapping is stored in the coordinate's `encoding` attribute (see make_rasdaman_netcdf.py).

Integer values are permanent: never renumber an existing entry, only append.
"""

models = {
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
    "CMIP6-Ensemble": 13,
    "WRF-ERA5": 14,
}

scenarios = {
    "historical": 0,
    "ssp126": 1,
    "ssp245": 2,
    "ssp370": 3,
    "ssp585": 4,
}

eras = {
    "1965-2014": 0,
    "2041-2070": 1,
    "2071-2100": 2,
}

aggregations = {
    "temporal_min": 0,
    "temporal_mean": 1,
    "temporal_max": 2,
}

# NetCDF coordinate name -> encoding dictionary
string_dim_luts = {
    "model": models,
    "scenario": scenarios,
    "era": eras,
    "aggregation": aggregations,
}
