#!/usr/bin/env bash
# Weekly refresh: rebuild the whole intelligence layer from the raw data files
# and regenerate the dashboard. Data pull (Metricool MCP) happens BEFORE this,
# writing fresh rows into data/raw/*. This script does everything after that.
#
# Usage:  bash refresh.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/7 ingest Instagram ==";        python3 src/ingest.py
echo "== 2/7 analyze Instagram ==";        python3 src/analyze.py
echo "== 3/7 merge multi-platform ==";     python3 src/ingest_multi.py
echo "== 4/7 cross-platform ==";           python3 src/cross_platform.py
echo "== 5/7 platform baselines ==";       python3 src/platform_model.py
echo "== 6/7 back-test + report ==";       python3 src/validate.py && python3 src/build_report.py
echo "== 7/7 rebuild dashboard ==";        python3 src/build_dashboard.py

echo "Refresh complete. Review 'git status', then commit + push main to deploy."
