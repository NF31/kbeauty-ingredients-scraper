#!/usr/bin/env bash
# Installe les git hooks versionnés du repo (scripts/hooks/) dans .git/hooks/.
# A relancer après un clone.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
src="$repo_root/scripts/hooks"
dst="$repo_root/.git/hooks"

for hook in "$src"/*; do
  name="$(basename "$hook")"
  ln -sf "../../scripts/hooks/$name" "$dst/$name"
  chmod +x "$hook"
  echo "hook installé : $name"
done
