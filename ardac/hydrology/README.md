# Hydrology Rasdaman coverage ingests

To successfully run this data ingest process, it's necessary to adjust the file naming scheme. This adjustment is essential for Rasdaman to accurately process the files. Failure to update the files to have an alphabetical ordering will result in encountering an error with code number 7 during the ingest. This error occurs because the distribution of "mean," "max," and "total" components is uneven within the dataset when the file names are not properly ordered.

## Rename files to allow for Rasdaman ingest

```bash
# Add "a_" to filenames containing "mean_"
find . -type f -name "*mean_*" -exec bash -c 'mv "$1" "$(dirname "$1")/a_$(basename "$1")"' _ {} \;

### Add "b_" to filenames containing "max_" but not starting with "tmax_"
find . -type f -name "*max_*" ! -name "tmax_*" -exec bash -c 'mv "$1" "$(dirname "$1")/b_$(basename "$1")"' _ {} \;

### Add "c_" to filenames containing "total_"
find . -type f -name "*total_*" -exec bash -c 'mv "$1" "$(dirname "$1")/c_$(basename "$1")"' _ {} \;
```
