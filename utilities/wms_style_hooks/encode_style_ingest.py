#!/usr/bin/env python3
import json
import sys
from urllib.parse import quote

if len(sys.argv) < 2:
    print('Usage: encode_style_ingest.py <json-file>')
    sys.exit(1)
with open(sys.argv[1]) as f:
    items = json.load(f)

for item in items:
    encoded = {}
    for key, value in item.items():
        if key == "wcps":
            encoded[key] = quote(value, safe='')
        elif key == "abstract":
            encoded[key] = quote(value, safe='')
        elif key == "colormap":
            encoded[key] = value.replace(" ", "").replace('"', '\\\\\\"')
        else:
            encoded[key] = value

    cmd_string = """{{
      \"description\": \"{cmd_description}\",
      \"when\": \"after_import\",
      \"cmd\": \". /etc/default/rasdaman; curl --user $RASCURL \\"https://datacubes.earthmaps.io/rasdaman/admin/layer/style/add?COVERAGEID={coverage}&STYLEID={name}&ABSTRACT={abstract}&WCPSQUERYFRAGMENT={wcps}&COLORTABLETYPE=ColorMap&\\" --data-urlencode \\"COLORTABLEDEFINITION={colormap}\\"",
      \"abort_on_error\": true
}},"""
    print(cmd_string.format(**encoded))
