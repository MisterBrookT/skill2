#!/usr/bin/env bash
set -euo pipefail

SOURCE="${BASH_SOURCE[0]:-}"
if [ -n "$SOURCE" ] && [ -f "$SOURCE" ]; then
  ROOT="$(cd "$(dirname "$SOURCE")" && pwd)"
else
  ROOT="$(pwd)"
fi
TMP_ROOT=""
if [ ! -d "$ROOT/skills" ]; then
  TMP_ROOT="$(mktemp -d)"
  git clone --depth 1 https://github.com/MisterBrookT/skill2.git "$TMP_ROOT" >/dev/null 2>&1
  ROOT="$TMP_ROOT"
fi
trap '[ -n "$TMP_ROOT" ] && rm -rf "$TMP_ROOT"' EXIT
ONLY="${1:-all}"

copy_skills() {
  local dest="$1"
  mkdir -p "$dest"
  for skill in "$ROOT"/skills/*; do
    [ -d "$skill" ] || continue
    cp -R "$skill" "$dest/$(basename "$skill")"
  done
  printf 'installed skills -> %s\n' "$dest"
}

case "$ONLY" in
  all)
    copy_skills "$HOME/.agents/skills"
    [ -d "$HOME/.claude" ] && copy_skills "$HOME/.claude/skills"
    ;;
  codex)
    copy_skills "$HOME/.agents/skills"
    ;;
  claude)
    copy_skills "$HOME/.claude/skills"
    ;;
  *)
    printf 'usage: ./install.sh [all|codex|claude]\n' >&2
    exit 2
    ;;
esac
