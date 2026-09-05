#!/usr/bin/env bash
set -euo pipefail

if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi

trap 'command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock; exit' EXIT INT TERM

TARGET_DIRS=(
    "$HOME/Candyland"
    "$HOME/rockberry-pi"
    "$HOME/.claude/skills/claude-skills"
)

STATE_DIR="$HOME/.kesselflow/state"
LOG_FILE="$HOME/.kesselflow/logs/watcher.log"
mkdir -p "$STATE_DIR" "$(dirname "$LOG_FILE")"

POLL_INTERVAL="${KESSEL_POLL_INTERVAL:-5}"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Kessel Flow Watcher initialized." >> "$LOG_FILE"

get_repo_hash() {
    local dir="$1"
    if [ -d "$dir/.git" ]; then
        git -C "$dir" status --porcelain 2>/dev/null | md5sum | awk '{print $1}'
    else
        find "$dir" -maxdepth 4 -not -path '*/.git*' -type f -printf '%T@ %p\n' 2>/dev/null | md5sum | awk '{print $1}'
    fi
}

declare -A LAST_HASHES
for dir in "${TARGET_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        LAST_HASHES["$dir"]=$(get_repo_hash "$dir")
    fi
done

while true; do
    sleep "$POLL_INTERVAL"
    for dir in "${TARGET_DIRS[@]}"; do
        [ -d "$dir" ] || continue
        
        CURRENT_HASH=$(get_repo_hash "$dir")
        if [ "$CURRENT_HASH" != "${LAST_HASHES["$dir"]}" ]; then
            LAST_HASHES["$dir"]="$CURRENT_HASH"
            TIMESTAMP=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
            echo "[$TIMESTAMP] Change detected in $dir" >> "$LOG_FILE"
            
            if [ -x "$dir/scripts/ci/context_budget.sh" ]; then
                "$dir/scripts/ci/context_budget.sh" >> "$LOG_FILE" 2>&1 || true
            fi
            if [ -x "$dir/scripts/ci/witch_gate.sh" ]; then
                "$dir/scripts/ci/witch_gate.sh" --report "$dir/witch-report.json" --sarif "$dir/witch.sarif" >> "$LOG_FILE" 2>&1 || true
            fi
        fi
    done
done
