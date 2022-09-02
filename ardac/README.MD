# ARDAC Ingests

Ingest recipes in this directory are for datasets that have been through the ARDAC Data Ingest Pipeline.

As such, there are no pre-processing Jupyter notebooks here. For pre-processing and data QC, head over to the [ARDAC repo]().

The expectation is that each ARDAC dataset / Rasdaman coverage will have a directory that contains the ingest recipe JSON that includes a WMS style and all accompanying files, e.g. a `luts.py` or similar to pass axis encodings or other metadata.

Also - we can pass information about the data to the API and beyond via `DescribeCoverage` requests, so the more rich the metadata block the better. For example, are there invalid dimensions (like "2090-99" and "CRU-TS")? If so, encode those!
