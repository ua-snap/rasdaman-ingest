import os
import xarray as xr


def check_dims(varname, fp, checked_fp):
    """Some data files have different dimension orderings (time, lat, lon instead of lon, time, lat (most common in this dataset)). This function will re-order them if appropriate, or create a symlink of the file with the 'replace path' of the rasdaman hook"""
    with xr.open_dataset(fp) as ds:
        if list(ds[varname].dims) != ["lon", "time", "lat"]:
            print(f"Swapping dims on {fp}")
            os.system(f"ncpdq -a lon,time,lat {fp} {checked_fp}")
        else:
            os.symlink(fp, checked_fp)
            
    return
