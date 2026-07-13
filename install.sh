#!/usr/bin/env bash
# shellcheck shell=bash
set -eu

REPOSITORY_URL="https://github.com/MisterBrookT/skill2.git"
MODE="all"
MODE_SET=0
DRY_RUN=0
FORCE=0
CONFLICTS=0
TMP_ROOT=""
STAGING=""
# Newline-separated: list_target/install_target run with IFS=newline for TARGETS.
RETIRED_SKILLS="skill2-build
skill2-prune"

usage() {
  printf 'usage: ./install.sh [all|codex|claude] [--dry-run] [--force]\n' >&2
}

cleanup() {
  [ -z "$STAGING" ] || rm -rf "$STAGING"
  [ -z "$TMP_ROOT" ] || rm -rf "$TMP_ROOT"
}
trap cleanup EXIT HUP INT TERM

for arg in "$@"; do
  case "$arg" in
    all|codex|claude)
      if [ "$MODE_SET" -eq 1 ]; then
        usage
        exit 2
      fi
      MODE="$arg"
      MODE_SET=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --force)
      FORCE=1
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

SOURCE="${BASH_SOURCE[0]:-}"
if [ -n "$SOURCE" ] && [ -f "$SOURCE" ]; then
  ROOT="$(cd "$(dirname "$SOURCE")" && pwd)"
else
  ROOT="$(pwd)"
fi

SOURCE_URL="unknown"
SOURCE_REF="unknown"
SOURCE_TREE="unknown"

if [ ! -d "$ROOT/skills" ]; then
  TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/skill2.XXXXXX")"
  if ! git clone --depth 1 "$REPOSITORY_URL" "$TMP_ROOT" >/dev/null 2>&1; then
    printf 'error: could not clone Skill2 repository\n' >&2
    exit 1
  fi
  ROOT="$TMP_ROOT"
  SOURCE_URL="$REPOSITORY_URL"
fi

if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  remote_url="$(git -C "$ROOT" config --get remote.origin.url 2>/dev/null || true)"
  case "$remote_url" in
    http://*|https://*)
      # Drop credentials, query strings, and fragments before persisting provenance.
      SOURCE_URL="$(printf '%s' "$remote_url" | sed -e 's#://[^/@]*@#://#' -e 's/[?#].*$//')"
      ;;
  esac
  source_ref="$(git -C "$ROOT" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -n "$source_ref" ]; then
    SOURCE_REF="$source_ref"
  else
    SOURCE_REF="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf 'unknown')"
  fi
  SOURCE_TREE="$(git -C "$ROOT" rev-parse 'HEAD^{tree}' 2>/dev/null || printf 'unknown')"
fi

skill_status() {
  source_skill="$1"
  destination_skill="$2"
  if [ ! -e "$destination_skill" ]; then
    printf 'new'
  elif diff -qr "$source_skill" "$destination_skill" >/dev/null 2>&1; then
    printf 'unchanged'
  else
    printf 'replace'
  fi
}

list_target() {
  destination="$1"
  printf 'target: %s\n' "$destination"
  for skill in "$ROOT"/skills/*; do
    [ -d "$skill" ] || continue
    name="$(basename "$skill")"
    status="$(skill_status "$skill" "$destination/$name")"
    [ "$status" != "replace" ] || CONFLICTS=1
    printf '  %s: %s\n' "$name" "$status"
  done
  for name in $RETIRED_SKILLS; do
    if [ -e "$destination/$name" ]; then
      CONFLICTS=1
      printf '  %s: retired (remove with --force)\n' "$name"
    fi
  done
}

write_provenance() {
  destination="$1"
  provenance_tmp="$STAGING/provenance"
  {
    printf 'source_url=%s\n' "$SOURCE_URL"
    printf 'ref=%s\n' "$SOURCE_REF"
    printf 'tree_sha=%s\n' "$SOURCE_TREE"
  } >"$provenance_tmp"
  mv "$provenance_tmp" "$destination/.skill2-install-provenance"
}

replace_skill() {
  staged_skill="$1"
  destination_skill="$2"
  backup=""
  if [ -e "$destination_skill" ]; then
    backup="$destination_skill.skill2-backup-$$"
    rm -rf "$backup"
    mv "$destination_skill" "$backup"
  fi
  if ! mv "$staged_skill" "$destination_skill"; then
    [ -z "$backup" ] || mv "$backup" "$destination_skill"
    return 1
  fi
  [ -z "$backup" ] || rm -rf "$backup"
}

install_target() {
  destination="$1"
  mkdir -p "$destination"
  if [ "$FORCE" -eq 1 ]; then
    for name in $RETIRED_SKILLS; do
      rm -rf "$destination/$name"
    done
  fi
  # This staging directory shares the target filesystem, so each final mv is a rename.
  STAGING="$(mktemp -d "$destination/.skill2-staging.XXXXXX")"
  for skill in "$ROOT"/skills/*; do
    [ -d "$skill" ] || continue
    cp -R "$skill" "$STAGING/$(basename "$skill")"
  done
  for staged_skill in "$STAGING"/*; do
    [ -d "$staged_skill" ] || continue
    replace_skill "$staged_skill" "$destination/$(basename "$staged_skill")"
  done
  write_provenance "$destination"
  rm -rf "$STAGING"
  STAGING=""
  printf 'installed skills -> %s\n' "$destination"
}

TARGETS=""
case "$MODE" in
  all)
    TARGETS="$HOME/.agents/skills
$HOME/.claude/skills"
    ;;
  codex) TARGETS="$HOME/.agents/skills" ;;
  claude) TARGETS="$HOME/.claude/skills" ;;
esac

old_ifs="$IFS"
IFS='
'
for target in $TARGETS; do
  list_target "$target"
done
IFS="$old_ifs"

if [ "$DRY_RUN" -eq 1 ]; then
  printf 'dry-run: no files changed\n'
  exit 0
fi

if [ "$CONFLICTS" -eq 1 ] && [ "$FORCE" -ne 1 ]; then
  printf 'error: existing skills differ; inspect --dry-run, then rerun with --force\n' >&2
  exit 1
fi

# Skills ship local scripts/run + bundled runtime; no global CLI install.
IFS='
'
for target in $TARGETS; do
  install_target "$target"
done
IFS="$old_ifs"
