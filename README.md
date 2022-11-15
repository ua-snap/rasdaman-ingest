# Pre-processing and ingest files for SNAP Rasdaman coverages

This repo tracks ingest scripts and pre-processing code for rasdaman coverages. It currently has ingest scripts for a superset of the coverages that are actually in the production Rasdaman server.

Below are some useful bits of info for performing the ingests on our Rasdaman servers. More details can be found in SNAP's internal documents for working with Rasdaman. 

### Rasdaman servers

**Apollo**: dev server! Try new things here.

You can check the existing coverages and services for Apollo at:
https://apollo.snap.uaf.edu/rasdaman/ows#/services
 
**Zeus**: production server.

https://zeus.snap.uaf.edu/rasdaman/ows

Note that Apollo and Zeus may run slightly different versions of Rasdaman.

### Running an ingest

Assumes logged in to server!

#### 1. Delete the existing coverage if one already exists with the same `coverage_id`

This can be done with an http request using `curl` or `wget` to `"http://localhost:8080/rasdaman/ows?SERVICE=WCS&VERSION=2.0.1&REQUEST=DeleteCoverage&COVERAGEID=<coverage_id>"`, e.g.

```
wget "http://localhost:8080/rasdaman/ows?SERVICE=WCS&VERSION=2.0.1&REQUEST=DeleteCoverage&COVERAGEID=relative_vegetation_change_future"
```

You may also need to delete a `collection` that was left behind by a failed ingest. If your ingest is not working, try deleting the collection as well. If there is no collection found, that's OK.
This is done using `rasql`, e.g. 

```
sudo rasql -q "drop collection test_iem_gipl_magt_alt_4km" --user rasadmin --passwd <pw>
```

#### 2. Move the data and ingest scripts into a directory with the right permissions

On Apollo, running from `/tmp` works. Make subdirs as desired.  
On Zeus, running from `/rasdaman/<username>` works. It can be symlinked as well, e.g. `~/rasdaman-fs -> /rasdaman/kmredilla`.  

Move the ingest files, lookup files (e.g. `luts.py`) and data into a subdirectory of such a directory. Ingest scripts can either be copied using a terminal editor or pulled in directly from a cloned repo. The former option is probably faster if you are developing these scripts on another machine.  

A useful thing to do is create a subdirectory for an ingest or group of related ingests. Here is an example workflow:

```
# login
INGEST_DIR=rasdaman-fs/alfresco/relative_flammability
mkdir -p $INGEST_DIR
unzip data.zip -d $INGEST_DIR
GH_DIR=rasdaman-ingest/iem/alfresco/relative_flammability
cp $GH_DIR/future_ingest.json $INGEST_DIR
cp $GH_DIR/luts.py $INGEST_DIR
```

#### 3. Set other environment variables as needed

One common (potentially only) example of this is setting the path to the `luts.py` if `LUTS_PATH` is required in the ingest file. This is usually provided as a mapping for integer axis values to meaningful categories, since the latter are not permitted in Rasdaman axes.

Example: 
```
export LUTS_PATH=$INGEST_DIR/luts.py
# or if repo is on system:
export LUTS_PATH=$GH_DIR/luts.py
```

#### 4. Execute `wcst_import.sh` from that directory

Example: 

```
cd $INGEST_DIR
wcst_import.sh future_ingest.json
```

Or if `wcst_import.sh` is not on path, it should be usable like so:

```
/opt/rasdaman/bin/wcst_import.sh ingest.json
```

**Note** - it may be the case that not all python packages made it in for certain utilities such as `wcst_import.sh`. The `ingest_env.yml` file provided here contains the packages for an environment that should have everything needed to carry out a `wcst_import.sh` ingest. This is not intended to be an environment for the many processing pipelines herein.  

Create a new env with `conda env create -f ingest_env.yml` and activate with `conda activate rasdaman` prior to attempting the ingest.

#### 5. Set a Style (optional)

Your `ingest.json` may have included a post-import hook that created the WMS style for the layer via a `curl` command executed after the coverage was created successfully. If it didn't, or if you want to add another style, you can do this from the terminal like so:

For styles where a ColorMap is used:

`curl "http://localhost:8080/rasdaman/admin/layer/style/add?COVERAGEID=foo&STYLEID=foo_colormap&COLORTABLETYPE=ColorMap&" --data-urlencode "COLORTABLEDEFINITION={\"type\": \"ramp\", \"colorTable\": {  \"-9999\": [0, 0, 0, 0], \"0\": [255, 255, 255, 255], \"0.03\": [255, 0, 0, 255] } }"`

The above command will add the style `foo_colormap` to the coverage called `foo` and this style is of the ramp type and defined by the ColorMap JSON object. The nested ColorArrays are interpreted as RGBA by default.

For styles where a StyleLayerDescription (SLD) XML document is used (this type of styling may be necessary to include labels):

`curl "http://localhost:8080/rasdaman/admin/layer/style/add?COVERAGEID=foo&STYLEID=foo_xml&COLORTABLETYPE=SLD&COLORTABLEDEFINITION=%3CStyledLayerDescriptor%20xmlns%3D%22http%3A%2F%2Fwww.opengis.net%2Fsld%22%20xmlns%3Agml%3D%22http%3A%2F%2Fwww.opengis.net%2Fgml%22%20xmlns%3Aogc%3D%22http%3A%2F%2Fwww.opengis.net%2Fogc%22%20xmlns%3Asld%3D%22http%3A%2F%2Fwww.opengis.net%2Fsld%22%20version%3D%221.0.0%22%3E%0A%20%20%3CUserLayer%3E%0A%20%20%20%20%3Csld%3ALayerFeatureConstraints%3E%0A%20%20%20%20%20%20%3Csld%3AFeatureTypeConstraint%20%2F%3E%0A%20%20%20%20%3C%2Fsld%3ALayerFeatureConstraints%3E%0A%20%20%20%20%3Csld%3AUserStyle%3E%0A%20%20%20%20%20%20%3Csld%3AName%3Epermafrost_beta%3Amagt_cruts31_historical_era1995_1986to2005%3C%2Fsld%3AName%3E%0A%20%20%20%20%20%20%3Csld%3AFeatureTypeStyle%3E%0A%20%20%20%20%20%20%20%20%3Csld%3ARule%3E%0A%20%20%20%20%20%20%20%20%20%20%3Csld%3ARasterSymbolizer%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AChannelSelection%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AGrayChannel%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3ASourceChannelName%3E1%3C%2Fsld%3ASourceChannelName%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3C%2Fsld%3AGrayChannel%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%3C%2Fsld%3AChannelSelection%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AColorMap%20type%3D%22intervals%22%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AColorMapEntry%20quantity%3D%22-9999%22%20color%3D%22%23ffffff%22%20label%3D%22-9999%22%20%2F%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AColorMapEntry%20quantity%3D%220.000%22%20color%3D%22%23fef0d9%22%20label%3D%220.000%22%20%2F%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AColorMapEntry%20quantity%3D%220.002%22%20color%3D%22%23fdcc8a%22%20label%3D%220.002%22%20%2F%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AColorMapEntry%20quantity%3D%220.005%22%20color%3D%22%23fc8d59%22%20label%3D%220.005%22%20%2F%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AColorMapEntry%20quantity%3D%220.010%22%20color%3D%22%23e34a33%22%20label%3D%220.010%22%20%2F%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%3Csld%3AColorMapEntry%20quantity%3D%220.020%22%20color%3D%22%23b30000%22%20label%3D%220.020%22%20%2F%3E%0A%20%20%20%20%20%20%20%20%20%20%20%20%3C%2Fsld%3AColorMap%3E%0A%20%20%20%20%20%20%20%20%20%20%3C%2Fsld%3ARasterSymbolizer%3E%0A%20%20%20%20%20%20%20%20%3C%2Fsld%3ARule%3E%0A%20%20%20%20%20%20%3C%2Fsld%3AFeatureTypeStyle%3E%0A%20%20%20%20%3C%2Fsld%3AUserStyle%3E%0A%20%20%3C%2FUserLayer%3E%0A%3C%2FStyledLayerDescriptor%3E"`

That lengthy URL will add the style `foo_xml` to the coverage called `foo`.

See the [Rasdaman Style Management Docs](https://doc.rasdaman.org/05_geo-services-guide.html#style-management) for details.

If you get misfire these requests it is possible to get the coverage into a state where it seems stuck - in that case just delete the coverage and re-ingest.



