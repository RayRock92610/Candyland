#!/usr/bin/env bash
set -euo pipefail

MAX_LINES="${KESSEL_CONTEXT_BUDGET:-300}"
ERRORS=0

echo "=== Kessel Flow: Context Budget Check ==="
echo "Max allowable budget: ${MAX_LINES} lines"

while IFS= read -r file; do
    if [ -f "$file" ]; then
        LINES=$(wc -l < "$file" | tr -d ' ')
        if [ "$LINES" -gt "$MAX_LINES" ]; then
            echo "[FAIL] $file exceeds budget: $LINES / $MAX_LINES lines"
            ERRORS=$((ERRORS + 1))
        else
            echo "[PASS] $file within budget: $LINES / $MAX_LINES lines"
        fi
    fi
done < <(find . -type f -name "CLAUDE.md" -not -path "*/.git/*")

if [ "$ERRORS" -gt 0 ]; then
    echo "::error::Context budget violation ($ERRORS file(s) exceed $MAX_LINES lines)."
    exit 1
fi

echo "[SUCCESS] All scanned context files are within the $MAX_LINES line budget."
