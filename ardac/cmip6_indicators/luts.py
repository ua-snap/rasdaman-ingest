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

cmip6_indicator_attrs = {
    "dw": {
        "units": "",
        "standard_name": "",
        "long_name": "",
        "description": "",
    },
    # TODO: add all the indicator attributes here
}


title_fmt_str = (
    "CMIP6 Climate Indicator Data on a Common Grid with Multi-Model Ensemble Mean"
)
description_fmt_str = "Climate Indicator data from {number_of_models} CMIP6 models on a common grid, including multi-model ensemble mean calculated for each indicator. Models include {models}. Scenarios include {scenarios}. Indicators include {variables}. Multi-model ensemble mean is calculated for each indicator across all available models for each scenario; some indicators do not have data for all models or scenarios."

global_attrs = {
    "Conventions": "CF-1.8",
    "title": "",
    "description": "",
    "institution": "Scenarios Network for Alaska and Arctic Planning, University of Alaska Fairbanks, International Arctic Research Center",
    "source": "CMIP6 model output",
    "contact": "uaf-snap-data-tools@alaska.edu",
    "url": "https://uaf-snap.org/",
}
