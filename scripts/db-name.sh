#!/usr/bin/env bash
# The main checkout keeps the package name. Linked worktrees share a PostgreSQL server, so
# include the identity of the Git administrative directory as well as a readable label.
set -euo pipefail
export LC_ALL=C
cd "$(dirname "$0")/.."

if dirs=$(git rev-parse --path-format=absolute --git-dir --git-common-dir 2>/dev/null); then
  git_dir=${dirs%%$'\n'*}
  common_dir=${dirs#*$'\n'}
  if [ "$git_dir" != "$common_dir" ]; then
    # A package name cannot contain a hyphen. The digest distinguishes punctuation, long names
    # and worktrees in different clones. 3 + 22 + 1 + 32 leaves five bytes for "-test".
    label=$(printf '%s' "${git_dir##*/}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '_' | cut -c1-22)
    digest=$(printf '%s' "$git_dir" | git hash-object --stdin)
    printf 'wt-%s-%.32s\n' "$label" "$digest"
    exit 0
  fi
fi
echo "my_project"
