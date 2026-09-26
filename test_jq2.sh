#!/bin/bash
REPORT_FILE="fake_report.json"
start_time=$(date +%s%3N)

# ⚡ Bolt Optimization: Extract properties in a single jq pass to avoid spawning jq multiple times per finding.
jq -c -r '.findings[] | "\(.type // "UNKNOWN")\t\(.file // "UNKNOWN")\t\(.severity // "INFO")\t\(. | tostring)"' "${REPORT_FILE}" | while IFS=$'\t' read -r issue_type target_file severity finding; do
    #echo "$issue_type - $target_file - $severity"
    :
done
end_time=$(date +%s%3N)
echo "New approach: $((end_time - start_time)) ms"
