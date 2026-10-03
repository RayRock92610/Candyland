
### Pipeline Bounded Concurrency
- **Optimization**: Implemented bounded concurrency (max 4 jobs) for clive dispatch in `kessel_pipeline.sh`.
- **Bugfix**: Replaced `| while` pipeline with `< <(jq ...)` process substitution to fix subshell job isolation, ensuring PIDs are tracked properly by the parent shell and `wait` commands function correctly.
- **Robustness**: Guarded `wait -n` with `|| true` to prevent unintended pipeline failures under `set -e`.
