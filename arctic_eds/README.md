# Arctic-EDS Temperature - Flavored Ingests

## Mean Annual Temperature
5 models, 3 scenarios, combined historical and projected. 1825 files at 4.1 GB pre-ingest.

## January Min / Max / Mean Temperature
This is 5 model, 3 scenario, combined historical and projected mega-coverage.
5000+ GeoTiffs comprising 14 GB (compressed) and about 250 GB once inflated by Rasdaman.
If you run this ingest and it stalls, don't panic, try again. I had it hiccup one time where it quit about 4/5 the way through. I deleted the coverage per usual, and ran it again without making any changes and the recipe was successful. The actual ingest process could take 30 minutes.


## July Min / Max / Mean Temperature
Same as above.

## Other Notes
The GeoTiffs for the completed coverages live on ATLAS at `atlas_scratch/cparr4/rasdaman_prod`

The TIFFs are too big to hang out in `tmp` on Apollo forever. Ultimately the data can live in the Rasdaman pot-o-gold in a more permanent directory. A pre-import `rysnc` hook could be used to grab the data whenever a re-ingest is required.

