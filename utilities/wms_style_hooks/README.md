# WMS style hook encoder

This script was developed to make it easier to produce WMS style hooks for rasdaman ingest scripts with correct URL-style encoding. It was thrown together quickly so probably has a lot of room for improvement, but it's already been used extensively with good results.

## Usage

Create a new JSON file similar to the provided `example.json`. After creating the desired WMS styles manually through the rasdaman web interface, copy the name/abstract/query/colormap/etc. fields into your JSON file (adding backslashes as needed, similar to `example.json`). Then run the script like so:

```
python encode_style_ingest.py <json-file>
```

This will print the URL-encoded style hooks to the console, which you can then copy into your rasdaman ingest script.