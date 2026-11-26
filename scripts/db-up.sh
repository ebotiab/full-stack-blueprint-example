#!/usr/bin/env bash
# Start this project's shared containers, provision this checkout's databases and point a
# linked worktree's backend/.env at its development database.
set -euo pipefail
cd "$(dirname "$0")/.."
dev=$1
local_postgres=$2
test_db=$dev-test
pg=(docker compose exec -T postgres)
user=my_project

docker compose up -d --wait postgres \
  || docker compose up -d --wait postgres

database_exists() {
  "${pg[@]}" psql -XAt -v ON_ERROR_STOP=1 -U "$user" -d "$user" -v db="$1" <<'SQL'
SELECT 1 FROM pg_database WHERE datname = :'db';
SQL
}

for db in "$dev" "$test_db"; do
  exists=$(database_exists "$db")
  if [ "$exists" != 1 ]; then
    args=("$db")
    # createdb's optional description marks only a newly created disposable database.
    if [ "$db" = "$test_db" ]; then args+=("MY_PROJECT_TEST_DATABASE_URL"); fi
    "${pg[@]}" createdb -U "$user" --maintenance-db="$user" "${args[@]}" \
      || [ "$(database_exists "$db")" = 1 ]
  fi
done

if [ "$dev" = "$user" ]; then exit 0; fi

env_file=backend/.env
# A symlink is an explicit choice to share settings between checkouts.
if [ -L "$env_file" ]; then exit 0; fi
key=MY_PROJECT_DATABASE_URL
marker="# This git worktree's own database (make db-up, scripts/db-name.sh)."
git_dir=$(git rev-parse --absolute-git-dir)
legacy=$(basename "$git_dir" | LC_ALL=C tr '[:upper:]' '[:lower:]' | LC_ALL=C tr -c 'a-z0-9\n' '_' | cut -c1-55)
old_line="$key=$local_postgres/wt_$legacy"
new_line="$key=$local_postgres/$dev"

if [ -f "$env_file" ] && awk -v marker="$marker" -v old="$old_line" \
    'previous == marker && $0 == old { found = 1 } { previous = $0 } END { exit !found }' "$env_file"; then
  # Upgrade just the value the previous template wrote. Leave the old database available for
  # pg_dump. Replace the file atomically, preserving its permissions.
  temp=$(mktemp "$env_file.XXXXXX")
  trap 'rm -f "$temp"' EXIT
  cp -p "$env_file" "$temp"
  awk -v marker="$marker" -v old="$old_line" -v new="$new_line" \
    'previous == marker && $0 == old { $0 = new } { previous = $0; print }' "$env_file" > "$temp"
  mv "$temp" "$env_file"
  echo "$env_file now uses $dev. Previous database wt_$legacy is available for pg_dump."
elif ! grep -qsE '^[[:space:]]*(export[[:space:]]+)?(MY_PROJECT_)?DATABASE_URL[[:space:]]*=' "$env_file"; then
  { if [ -s "$env_file" ]; then echo; fi
    echo "$marker"
    echo "$new_line"; } >> "$env_file"
  echo "$env_file: $key now points at $dev."
fi
