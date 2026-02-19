# Benchmarking Rasdaman Requests with Apache JMeter

## Requirements & Installation

### Java

You'll need some version of java.
Try
```sh
java --version`
```
to see what you have. JMeter runs OK on `openjdk 11.0.28 2025-07-15 LTS` but something newer might do well and shush a few warnings about missing packages.
If you have path issues try
```sh
which java
```
and you may need to export that directory to your `PATH` variable.

### Apache JMeter

#### Installation

On MacOS, try `brew`

```sh
brew install jmeter
# Verify
jmeter -v
```

Alternatively, you can manually download and install Apache JMeter here: [Apache JMeter Downloads](https://jmeter.apache.org/download_jmeter.cgi)

## Benchmarks Overview
This directory includes scripts to build request lists for WCS and WMS benchmarks, run JMeter tests, and summarize results.

### Core Scripts
- `get_zeus_capabilities.py` fetches the WCS GetCapabilities document and writes `zeus_coverages.csv`. The CSV includes spatial bounds, centroids, EPSG, and non-spatial lower bounds for slicing.
- `build_wcs_benchmark_requests.py` generates `zeus_wcs_benchmark_requests.csv` with jittered point requests per coverage.
- `build_wms_benchmark_requests.py` generates `zeus_wms_benchmark_requests.csv` with one WMS GetMap request per coverage using the coverage bounds BBOX and lower non-spatial axis bounds.
- `analyze_wcs_results.py` summarizes latency/throughput per coverage for WCS results.
- `analyze_wms_results.py` summarizes latency/throughput per coverage for WMS results.
- `run_benchmarks.py` is a wrapper that runs the full pipeline and both JMeter test plans.

### Request Generation Details
- WCS request generation:
  - Uses point subsets around the coverage centroid.
  - Defaults to 10 points per coverage.
  - Projected coverages use a 150 km jitter radius; lon/lat coverages use 2 degrees.
- WMS request generation:
  - Uses the coverage bounds for BBOX (no jitter).
  - Uses non-spatial lower bounds for slicing extra axes.
  - Uses `FORMAT=image/png`, `TRANSPARENT=true`, `STYLES=`.

## Usage
You can use JMeter from the terminal (headless) or via the JMeter GUI. The GUI is helpful for developing experiemnts, but the terminal is nice for running them and piping in different parameters.
The atomic "thing" of JMeter is a "Test Plan" and these are written to a `.jmx` file. This seems to basically be a markup format.
Results are by default written to a `.jtl` file.

To run an experiment in headless mode, you can try the following commands
```sh
# save results in a CSV file
jmeter -n -t rate_sweep_template.jmx -l results.csv
```

JMeter also has built in HTML reporting:
```sh
jmeter -n -t rate_sweep_template.jmx -l results.jtl -e -o reports/rate_sweep_html
```

## Running Individual Scripts
Run these from the `benchmarks` directory.

```sh
# Fetch coverage metadata
python get_zeus_capabilities.py

# Build WCS request list
python build_wcs_benchmark_requests.py

# Build WMS request list
python build_wms_benchmark_requests.py

# Run WCS benchmark
jmeter -n -t wcs_benchmarks.jmx -l wcs_benchmark_results.csv

# Run WMS benchmark
jmeter -n -t wms_benchmarks.jmx -l wms_benchmark_results.csv

# Analyze WCS results
python analyze_wcs_results.py --results wcs_benchmark_results.csv

# Analyze WMS results
python analyze_wms_results.py --results wms_benchmark_results.csv
```

## Wrapper Script
The wrapper runs the full pipeline with defaults:

```sh
python run_benchmarks.py
```
