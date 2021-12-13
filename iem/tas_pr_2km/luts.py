varnames = {
    "pr": 0,
    "tas": 1,
}

decades = {
    "2010_2019": 0,
    "2020_2029": 1,
    "2030_2039": 2,
    "2040_2049": 3,
    "2050_2059": 4,
    "2060_2069": 5,
    "2070_2079": 6,
    "2080_2089": 7,
    "2090_2099": 8,
    "1910_1919": 0,
    "1920_1929": 1,
    "1930_1939": 2,
    "1940_1949": 3,
    "1950_1959": 4,
    "1960_1969": 5,
    "1970_1979": 6,
    "1980_1989": 7,
    "1990_1999": 8,
    "2000_2009": 9,
}

models = {
    "5modelAvg": 0,
    "CCSM4": 1,
    "MRI-CGCM3": 2,
}

scenarios = {
    "rcp45": 0,
    "rcp60": 1,
    "rcp85": 2,
}

seasons = {
    "DJF": 0,
    "JJA": 1,
    "MAM": 2,
    "SON": 3,
}

stats = {
    "min": 5,
    "lo_std": 1,
    "q1": 6,
    "mean": 3,
    "median": 4,
    "q3": 7,
    "hi_std": 0,
    "max": 2,
}

# separate mappings for deltas 
# because some levels not used
d_models = {
    "MRI-CGCM3": 0,
    "NCAR-CCSM4": 1,
}

d_scenarios = {
    "rcp45": 0,
    "rcp85": 1,
}

d_periods = {
    "2040-2069": 0,
    "2070-2099": 1,
}
