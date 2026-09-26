#!/usr/bin/env bash
set -euo pipefail

# Only check staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

for f in $STAGED_FILES; do
    if [[ "$f" == *"CLAUDE.md" ]]; then
        if [ -f "$f" ]; then
            LINES=$(wc -l < "$f")
            if [ "$LINES" -gt 300 ]; then
                echo "[REJECTED] $f exceeds 300 lines ($LINES lines)."
                exit 1
            fi
        fi
    fi
done
