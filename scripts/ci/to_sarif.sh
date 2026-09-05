#!/usr/bin/env bash
set -euo pipefail

INPUT_JSON="${1:-witch-report.json}"
OUTPUT_SARIF="${2:-witch.sarif}"
TOOL_VERSION="${KESSEL_TOOL_VERSION:-1.0.0}"

if [ ! -f "$INPUT_JSON" ]; then
    echo "::error::Input JSON report $INPUT_JSON does not exist."
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "::error::jq is required to generate SARIF output."
    exit 1
fi

jq -n --arg version "$TOOL_VERSION" --slurpfile src "$INPUT_JSON" '
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "Witch Hunter",
          "version": $version,
          "informationUri": "https://github.com/RayRock92610/kesselflow",
          "rules": [
            ($src[0].findings[]? | {
              "id": (.rule_id // .id // "WH001"),
              "name": (.rule_name // "VulnerabilityScan"),
              "shortDescription": { "text": (.title // .description // "Security Vulnerability Detected") },
              "defaultConfiguration": {
                "level": (
                  if (.severity | ascii_downcase) == "critical" or (.severity | ascii_downcase) == "high" then "error"
                  elif (.severity | ascii_downcase) == "medium" then "warning"
                  else "note"
                  end
                )
              }
            })
          ] | unique_by(.id)
        }
      },
      "results": [
        ($src[0].findings[]? | {
          "ruleId": (.rule_id // .id // "WH001"),
          "level": (
            if (.severity | ascii_downcase) == "critical" or (.severity | ascii_downcase) == "high" then "error"
            elif (.severity | ascii_downcase) == "medium" then "warning"
            else "note"
            end
          ),
          "message": { "text": (.description // .message // "Potential security finding detected.") },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {
                  "uri": (.file // .path // "kessel.py")
                },
                "region": {
                  "startLine": ((.line // .start_line // 1) | tonumber)
                }
              }
            }
          ]
        })
      ]
    }
  ]
}
' > "$OUTPUT_SARIF"

echo "[SUCCESS] Generated SARIF report at $OUTPUT_SARIF"
