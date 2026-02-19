#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    run(sys.executable, "get_zeus_capabilities.py")
    run(sys.executable, "build_wcs_benchmark_requests.py")
    run(sys.executable, "build_wms_benchmark_requests.py")

    run("jmeter", "-n", "-t", "wcs_benchmarks.jmx", "-l", "wcs_benchmark_results.csv")
    run("jmeter", "-n", "-t", "wms_benchmarks.jmx", "-l", "wms_benchmark_results.csv")

    run(sys.executable, "analyze_wcs_results.py", "--results", "wcs_benchmark_results.csv")
    run(sys.executable, "analyze_wms_results.py", "--results", "wms_benchmark_results.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
