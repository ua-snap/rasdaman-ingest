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
    "rx1day": {
        "units": "mm",
        "long_name": "Yearly Maxmimum 1-day Precipitation",
        "description": "Maxmimum 1-day Precipitation, calculated over a yearly frequency using xclim.indices.max_n_day_precipitation_amount().",
    },
    "rx5day": {
        "units": "mm",
        "long_name": "Yearly Maximum 5-day Precipitation",
        "description": "Maximum 5-day Precipitation, calculated over a yearly frequency using xclim.indices.max_n_day_precipitation_amount().",
    },
    "r10mm": {
        "units": "days",
        "long_name": "Yearly Number of Days with Precipitation >= 10mm",
        "description": "Number of Days with Precipitation >= 10mm, calculated over a yearly frequency using xclim.indices._threshold.tg_days_above().",
    },
    "cdd": {
        "units": "days",
        "long_name": "Yearly Number of Consecutive Days with Precipitation < 1mm",
        "description": "Number of Consecutive Days with Precipitation < 1mm, calculated over a yearly frequency using xclim.indices.maximum_consecutive_dry_days().",
    },
    "cwd": {
        "units": "days",
        "long_name": "Yearly Number of Consecutive Days with Precipitation > 1mm",
        "description": "Number of Consecutive Days with Precipitation > 1mm, calculated over a yearly frequency using xclim.indices.maximum_consecutive_wet_days().",
    },
    "dw": {
        "units": "days",
        "long_name": "Yearly Number of Deep Winter Days (-30C threshold)",
        "description": "Number of Deep Winter Days, calculated over a yearly frequency with a daily minimum temperature threshold of -30C using xclim.indices.tn_days_below().",
    },
    "su": {
        "units": "days",
        "long_name": "Yearly Number of Summer Days (25C threshold)",
        "description": "Number of Summer Days, calculated over a yearly frequency with a daily maximum temperature threshold of 25C using xclim.indices.tx_days_above().",
    },
    "ftc": {
        "units": "1",
        "long_name": "Yearly Number of Freeze-Thaw Cycles",
        "description": "Number of Freeze Thaw Cycles, calculated over a yearly frequency using xclim.indicators.atmos.daily_freezethaw_cycles().",
    },
    "hd": {
        "units": "degC",
        "long_name": "Hot Day Threshold",
        "description": "the highest observed daily maximum 2m air temperature such that there are 5 other observations equal to or greater than this value.",
    },
    "cd": {
        "units": "degC",
        "long_name": "Cold Day Threshold",
        "description": "the lowest observed daily minimum 2m air temperature such that there are 5 other observations equal to or less than this value.",
    },
    "wsdi": {
        "units": "1",
        "long_name": "Warm Spell Duration Index",
        "description": "Annual count of occurrences of at least 5 consecutive days with daily maximum temperature above 90th percentile of historical values for the date, calculated over a yearly frequency using xclim.indices.warm_spell_duration_index().",
    },
    "csdi": {
        "units": "1",
        "long_name": "Cold Spell Duration Index",
        "description": "Annual count of occurrences of at least 5 consecutive days with daily minimum temperature below 10th percentile of historical values for the date, calculated over a yearly frequency using xclim.indices.cold_spell_duration_index().",
    },
}

title_fmt_str = (
    "CMIP6 Climate Indicator Data on a Common Grid with Multi-Model Ensemble Mean"
)
description_fmt_str = "Climate Indicator data from {number_of_models} CMIP6 models on a common grid, including multi-model ensemble mean calculated for each indicator. Models include {models}. Scenarios include {scenarios}. Indicators include {indicators}. Multi-model ensemble mean is calculated for each indicator across all available models for each scenario; some indicators do not have data for all models or scenarios."

global_attrs = {
    "Conventions": "CF-1.8",
    "title": "",
    "description": "",
    "institution": "Scenarios Network for Alaska and Arctic Planning, University of Alaska Fairbanks, International Arctic Research Center",
    "source": "CMIP6 model output",
    "contact": "uaf-snap-data-tools@alaska.edu",
    "url": "https://uaf-snap.org/",
}
