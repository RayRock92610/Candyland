# Kessel Flow Repository Context

## Core Execution Rules
- Maintain context budget cap strictly under 300 lines.
- Run Witch Hunter security scans before staging changes.
- Pre-commit gates execute kessel_pipeline.sh automatically.

## Operations
- Logging target: ~/.kesselflow/logs/
- Execution binaries: ~/bin/
- Execution environment: Termux / Linux ARM64
