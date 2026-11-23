#!/usr/bin/env bash
# Check that every library skill linked in .agents/skills/ resolves to a skill (`make check`).
#
# The libraries the project uses ship agent skills inside their packages; .agents/skills/ links
# to them in backend/.venv, so an agent reads the guidance of the installed version. A link stops
# resolving when the package moves or drops its skill, or when the Python version in the path
# changes. The project's own skills (plain directories) are not checked here.
set -euo pipefail

cd "$(dirname "$0")/.."
broken=()
# The Python version in the links' paths (python3.14) must be the project's (backend/.python-version).
python=$(cat backend/.python-version 2>/dev/null || true)
linked=""
for link in .agents/skills/*; do
  [ -L "$link" ] || continue
  if [ ! -f "$link/SKILL.md" ]; then
    target=$(readlink "$link")
    broken+=("$link -> $target")
    if [[ $target =~ /python(3\.[0-9]+)/ ]] && [ "${BASH_REMATCH[1]}" != "$python" ]; then
      linked=${BASH_REMATCH[1]}
    fi
  fi
done

if [ ${#broken[@]} -eq 0 ]; then
  exit 0
fi

echo "These library skills do not resolve to a SKILL.md:"
printf '  %s\n' "${broken[@]}"
if [ -n "$linked" ]; then
  echo "Their paths name python$linked, but backend/.python-version says $python: change the version"
  echo "in each link's path (ln -sfn <new target> <link>), then run this again."
  exit 1
fi
cat <<'EOF'
They point into backend/.venv: run `make setup` (uv sync) first. If they still fail, the package
moved or dropped the skill; this lists where the installed packages keep their skills now:
  find backend/.venv -path '*/.agents/skills/*' -name SKILL.md
Point the link there (a relative symlink) or delete it.
EOF
exit 1
