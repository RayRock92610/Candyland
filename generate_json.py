import json
findings = []
for i in range(100):
    findings.append({
        "type": "XSS",
        "file": f"file_{i}.txt",
        "severity": "CRITICAL"
    })
print(json.dumps({"findings": findings}))
