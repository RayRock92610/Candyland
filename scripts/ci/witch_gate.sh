#!/usr/bin/env bash
set -euo pipefail

REPORT_FILE="witch-report.json"
SCANNER_BIN="${WITCH_HUNT_BIN:-}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --report) REPORT_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "=== Kessel Flow: Witch Hunter Security Gate ==="

if [ -z "$SCANNER_BIN" ]; then
    if [ -x "./tools/witch-hunt" ]; then
        SCANNER_BIN="./tools/witch-hunt"
    elif [ -x "$HOME/bin/witch-hunt" ]; then
        SCANNER_BIN="$HOME/bin/witch-hunt"
    elif command -v witch-hunt >/dev/null 2>&1; then
        SCANNER_BIN=$(command -v witch-hunt)
    else
        echo "::error::Witch Hunter binary not found."
        exit 1
    fi
fi

"$SCANNER_BIN" scan --json --out "$REPORT_FILE" . || true

if [ ! -f "$REPORT_FILE" ]; then
    echo "::error::Scan report file $REPORT_FILE was not generated."
    exit 1
fi

if command -v jq >/dev/null 2>&1; then
    CRITICAL_COUNT=$(jq '[.findings[]? | select(.severity == "CRITICAL" or .severity == "critical")] | length' "$REPORT_FILE" 2>/dev/null || echo "0")
    HIGH_COUNT=$(jq '[.findings[]? | select(.severity == "HIGH" or .severity == "high")] | length' "$REPORT_FILE" 2>/dev/null || echo "0")
    
    echo "Scan Results: Critical=$CRITICAL_COUNT, High=$HIGH_COUNT"
    if [ "$CRITICAL_COUNT" -gt 0 ] || [ "$HIGH_COUNT" -gt 0 ]; then
        echo "::error::Witch Hunter gate failed. Critical: $CRITICAL_COUNT, High: $HIGH_COUNT detected."
        exit 1
    fi
fi

echo "[SUCCESS] Witch Hunter security gate passed."
