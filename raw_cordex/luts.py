# order is based on import order. Since some of these models don't have RCP 4.5, they are imported after all of those that do (since scenario comes first in filename) and Rasdaman will try and insert in between coordinates which is not allowed. 
models = {
    "CCCma-CanESM2_CCCma-CanRCM4": 0,
    "CCCma-CanESM2_SMHI-RCA4": 1,
    "CCCma-CanESM2_UQAM-CRCM5": 6,
    "ICHEC-EC-EARTH_DMI-HIRHAM5": 2,
    "ICHEC-EC-EARTH_SMHI-RCA4": 3,
    "ICHEC-EC-EARTH_SMHI-RCA4-SN": 7,
    "MPI-M-MPI-ESM-LR_MGO-RRCM": 8,
    "MPI-M-MPI-ESM-LR_SMHI-RCA4": 4,
    "MPI-M-MPI-ESM-LR_SMHI-RCA4-SN": 9,
    "MPI-M-MPI-ESM-MR_UQAM-CRCM5": 10,
    "NCC-NorESM1-M_SMHI-RCA4": 5,
}

scenarios = {
    "rcp45": 0,
    "rcp85": 1,
}