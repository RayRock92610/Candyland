#!/bin/bash
REPORT_FILE="witch_hunter_latest.json"
cat << 'JSON' > "$REPORT_FILE"
{
  "findings": [
    {
      "type": "IDOR",
      "file": "api/users.py",
      "severity": "HIGH",
      "details": "Some details \n with \"quotes\" and \\ backslashes"
    },
    {
      "file": "missing_type.py"
    }
  ]
}
JSON

jq -r '.findings[] | "\(.type // "UNKNOWN")\t\(.file // "UNKNOWN")\t\(.severity // "INFO")\t\(tojson)"' "${REPORT_FILE}" | while IFS=$'\t' read -r issue_type target_file severity finding; do
    echo "TYPE: $issue_type"
    echo "FILE: $target_file"
    echo "SEV: $severity"
    echo "PAYLOAD: $finding"
    echo "---"
done
