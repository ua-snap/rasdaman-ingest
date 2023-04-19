# AK CORDEX dataset ingest files

This folder contains ingest ingredients files and python scripts for importing parts of the "AK CORDEX" dataset into Rasdaman.

## ingest

In addition to including the (now routine) `luts.py` file for specifying coordinate encodings of irregular axes from filenames, and storing the absolute path to this file in a `LUTS_PATH` environment variable, the ingredients files in here also rely on a `utils.py` file, the path to which needs to be stored in a `UTILS_PATH` variable. This file contains python code that is used to check that each file has a specific dimensional orientation which was hard-coded after determining the most common orientation for this dataset. It would not be needed if we were to preprocess this dataset, but the goal inspiring this particular set of files is to see if we can't work with a dataset as-is.

This directory contains scripts to generate the following coverages:

* `cordex_tas`
* `cordex_tasmax`
* `cordex_tasmin`

The dataset can be found at `/Data/Base_Data/Climate/AK_CORDEX`. We are only using the projected data at this time. This data must be copied to the working directory you plan to ingest from and placed in a `data/<variable>` subdirectory, where `<variable>` is the name of the variable being worked on. 

Store the paths to the helper python scripts in the `LUTS_PATH` and `UTILS_PATH`. E.g., 

```
export LUTS_PATH=`pwd`/luts.py
export UTILS_PATH=`pwd`/utils.py
```

Then, run the import for a single coverage, e.g. `wcst_import.sh ingest_tasmax.json`. This can take a fairly long time to complete.

