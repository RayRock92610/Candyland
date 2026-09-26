#!/bin/bash
REPORT_FILE="fake_report.json"
start_time=$(date +%s%3N)

jq -c '.findings[]' "${REPORT_FILE}" | while read -r finding; do
    issue_type=$(echo "${finding}" | jq -r '.type // "UNKNOWN"')
    target_file=$(echo "${finding}" | jq -r '.file // "UNKNOWN"')
    severity=$(echo "${finding}" | jq -r '.severity // "INFO"')
done

end_time=$(date +%s%3N)
echo "Old approach: $((end_time - start_time)) ms"

start_time=$(date +%s%3N)
jq -c -r '.findings[] | "\(.type // "UNKNOWN")\t\(.file // "UNKNOWN")\t\(.severity // "INFO")\t\(.)"' "${REPORT_FILE}" | while IFS=$'\t' read -r issue_type target_file severity finding; do
    :
done
end_time=$(date +%s%3N)
echo "New approach: $((end_time - start_time)) ms"
