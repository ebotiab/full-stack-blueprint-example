#!/usr/bin/env bash
# Run named steps, keep going after a failure, and end with a short summary and a reliable exit
# code (0 only if every step passed). Used by the Makefile; usable on its own:
#
#   scripts/steps.sh "Ruff format::cd backend && uv run ruff format --check ." "Vitest::cd frontend && npm test"
#
# Each argument is "label::command". The output of each step is shown as it runs.
set -uo pipefail

results=()
failed=0
for step in "$@"; do
  label="${step%%::*}"
  command="${step#*::}"
  printf '\n\033[1m==> %s\033[0m\n' "$label"
  start=$SECONDS
  if bash -euo pipefail -c "$command"; then
    results+=("ok    $label ($((SECONDS - start))s)")
  else
    results+=("FAIL  $label ($((SECONDS - start))s)")
    failed=$((failed + 1))
  fi
done

printf '\n\033[1mSummary\033[0m\n'
printf '  %s\n' "${results[@]}"
if [ "$failed" -gt 0 ]; then
  printf '%d of %d steps failed.\n' "$failed" "$#"
  exit 1
fi
printf 'All %d steps passed.\n' "$#"
