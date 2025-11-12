#!/usr/bin/env python3
import json
import sys

if len(sys.argv) < 2:
    print('Usage: encode_style_ingest.py <json-file>')
    sys.exit(1)
with open(sys.argv[1]) as f:
    items = json.load(f)

for item in items:
    encoded = {}
    for key, value in item.items():
        if key == "wcps":
            encoded[key] = (
                value.replace(" ", "%20")
                .replace("$", "%24")
                .replace("(", "%28")
                .replace(")", "%29")
                .replace("+", "%2B")
                .replace(",", "%2C")
                .replace("/", "%2F")
                .replace(":", "%3A")
                .replace("[", "%5B")
                .replace("]", "%5D")
                .replace('"', "%22")
            )
        elif key == "abstract":
            encoded[key] = value.replace(" ", "%20")
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
