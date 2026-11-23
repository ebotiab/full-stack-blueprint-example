#!/usr/bin/env bash
# Print the name of this checkout's local database. `make db-up` creates it, and <name>_test for
# pytest, in the PostgreSQL of docker-compose.yml, which every checkout of the repository shares.
#
# The main checkout uses my_project, the app's default (settings.py). A linked git worktree
# (`git worktree add`, which coding agents use to work in parallel) gets its own, wt_<worktree name>,
# so several worktrees can migrate and run their tests at the same time without touching each
# other's data; `make db-up` writes it to the worktree's backend/.env for the app and the CLI.
set -euo pipefail
cd "$(dirname "$0")/.."

# In a linked worktree the git directory is <common dir>/worktrees/<name>; in the main checkout
# both are the same. Outside a git repository: the main checkout's name.
if dirs=$(git rev-parse --path-format=absolute --git-dir --git-common-dir 2>/dev/null); then
  git_dir=${dirs%%$'\n'*}
  common_dir=${dirs#*$'\n'}
  if [ "$git_dir" != "$common_dir" ]; then
    # git keeps worktree names unique in a repository. Lowercase letters, digits and underscores,
    # at most 55 of them, so that wt_<name>_test fits PostgreSQL's 63-byte names.
    name=$(basename "$git_dir" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '_' | cut -c1-55)
    echo "wt_$name"
    exit 0
  fi
fi
echo "my_project"
