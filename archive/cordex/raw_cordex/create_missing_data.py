"""Create missing data to help with operations on null values from missing slices that are currently interpreted as 0's in WCPS etc"""

import os
from pathlib import Path
from itertools import product
import xarray as xr
import numpy as np
import luts


def create_missing_data(models, scenarios, temp_fp, example_fp):
    """This function writes a file conatining only null values and creates a symlink for any coordinate combinations that don't exist as if they were real data."""

    # create a list of all missing files using temp_fp and all possible models/scenarios
    groups = product(scenarios, models)
    missing_files = []
    for group in groups:
        test_fp = Path(temp_fp.format(*group))
        if not test_fp.exists():
            print(f"{test_fp} missing")
            missing_files.append(test_fp)
            
    # abort if no missing filews (likely if it has been run once)        
    if len(missing_files) == 0:
        return
    
    # clone the example dataset on disk but with nan values
    ds = xr.open_dataset(example_fp)
    arr = ds[list(ds.data_vars)[0]].data
    arr = np.empty_like(arr)
    arr[:] = np.nan
    ds[list(ds.data_vars)[0]].data = arr
    fake_fp = missing_files.pop()
    print("Writing fake data to ", fake_fp)
    ds.to_netcdf(fake_fp)
    
    # then create symlinks referencing the fake_fp for all other missing files
    for miss_fp in missing_files:
        print(f"creating reference to {miss_fp}")
        os.symlink(fake_fp.resolve(), miss_fp.resolve())
    
    return


if __name__ == "__main__":
    create_missing_data(luts.models, luts.scenarios, 'data/tasmax/ARC44_{}_tasmax_{}_ERA5bc.nc', 'data/tasmax/ARC44_rcp85_tasmax_CCCma-CanESM2_CCCma-CanRCM4_ERA5bc.nc')
