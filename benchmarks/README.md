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

