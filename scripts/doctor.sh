#!/usr/bin/env bash
# Check the tools this project needs, and say how to fix whatever is missing. `make doctor`.
set -uo pipefail

problems=0
ok() { printf '  ok    %s\n' "$1"; }
bad() { printf '  FAIL  %s\n        fix: %s\n' "$1" "$2"; problems=$((problems + 1)); }

# version_at_least <found> <wanted>: true if found >= wanted (dotted numbers).
version_at_least() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }

echo "Checking tools for My Project"

if command -v git >/dev/null 2>&1; then ok "git $(git --version | awk '{print $3}')"
else bad "git is not installed" "install it from https://git-scm.com/downloads"; fi

if command -v uv >/dev/null 2>&1; then
  uv_version=$(uv --version | awk '{print $2}')
  # 0.9.17 reads the relative `exclude-newer = "7 days"` of backend/pyproject.toml.
  if version_at_least "$uv_version" "0.9.17"; then ok "uv $uv_version (installs the project's Python by itself when needed)"
  else bad "uv $uv_version is too old (0.9.17 or newer is needed)" "uv self update  (or: brew upgrade uv)"; fi
else
  bad "uv is not installed" "curl -LsSf https://astral.sh/uv/install.sh | sh  (or: brew install uv)"
fi

if command -v node >/dev/null 2>&1; then
  node_version=$(node --version | sed 's/^v//')
  if version_at_least "$node_version" "22.12.0"; then ok "node $node_version"
  else bad "node $node_version is too old (22.12 or newer is needed)" "install Node 24 LTS: https://nodejs.org (or: nvm install 24 / brew install node@24)"; fi
else
  bad "node is not installed" "install Node 24 LTS: https://nodejs.org (or: nvm install 24 / brew install node@24)"
fi
if command -v npm >/dev/null 2>&1; then
  npm_version=$(npm --version)
  # 11.10 applies `min-release-age` (frontend/.npmrc); older versions ignore it with a warning.
  if version_at_least "$npm_version" "11.10.0"; then ok "npm $npm_version"
  else bad "npm $npm_version is too old (11.10 or newer applies the 7-day wait in frontend/.npmrc)" "npm install -g npm@11  (or install Node 24 LTS: https://nodejs.org)"; fi
else
  bad "npm is not installed" "it comes with Node: reinstall Node 24 LTS from https://nodejs.org"
fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    ok "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null) (daemon running)"
    if docker compose version >/dev/null 2>&1; then ok "docker compose $(docker compose version --short)"
    else bad "docker compose is missing" "update Docker Desktop, or install the compose plugin: https://docs.docker.com/compose/install/"; fi
    # The local PostgreSQL port must be free, or already ours.
    owner=$(docker ps --filter "publish=5434" --format '{{.Names}}' | head -n1)
    if [ -n "$owner" ] && [ "$owner" != "my-project-postgres" ]; then
      bad "port 5434 is used by the container $owner" "stop it, or change the port in docker-compose.yml, backend/src/my_project/settings.py and the Makefile (POSTGRES_PORT)"
    elif [ -z "$owner" ] && (exec 3<>/dev/tcp/127.0.0.1/5434) 2>/dev/null; then
      bad "port 5434 is used by another program" "stop it, or change the port in docker-compose.yml, backend/src/my_project/settings.py and the Makefile (POSTGRES_PORT)"
    else
      ok "port 5434 is available for PostgreSQL"
    fi
  else
    bad "docker is installed but its daemon is not running" "start Docker Desktop (or: sudo systemctl start docker)"
  fi
else
  bad "docker is not installed (needed for the local PostgreSQL)" "install Docker Desktop: https://docs.docker.com/get-docker/"
fi

if [ "$problems" -gt 0 ]; then
  printf '\n%d problem(s) found. Fix them and run `make doctor` again.\n' "$problems"
  exit 1
fi
printf '\nAll tools are ready. Next: `make setup`.\n'
