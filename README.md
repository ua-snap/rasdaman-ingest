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
