#!/bin/bash

directory="$1"
dd_name="$2"
zip_directory="$3"

zip_file="${zip_directory}/${dd_name}.zip"

echo "Creating ${zip_file}"
# delete zip archive if it exists already
rm -f "${zip_file}"

# create a zip file for the variable and add all tiffs with this string in their filename to the zip
find "${directory}/${dd_name}" -name "*${dd_name}*.tif" -print0 | xargs -0 zip -j "${zip_file}"
