#!/usr/bin/env bash
# Install the CircuitPython libraries listed in lib-requirements.txt onto
# the CIRCUITPY drive.
#
# Usage:
#   ./install-libs.sh                   # auto-detect the bundle
#   ./install-libs.sh /path/to/bundle   # use a specific bundle directory
#                                       # (the directory that contains lib/)
#
# Get the bundle from https://circuitpython.org/libraries (pick the
# "mpy" bundle matching your CircuitPython major version — 10.x for
# this project).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="$REPO_DIR/lib-requirements.txt"
MOUNT="/Volumes/CIRCUITPY"

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Missing $REQ_FILE" >&2
  exit 1
fi

if [[ ! -d "$MOUNT" ]]; then
  echo "$MOUNT not mounted. Plug in the FunHouse." >&2
  exit 1
fi

# Resolve bundle path
BUNDLE="${1:-}"
if [[ -z "$BUNDLE" ]]; then
  # Auto-detect: most recent "adafruit-circuitpython-bundle-10.x-mpy-*"
  # directory under ~/Downloads or /tmp
  for base in "$HOME/Downloads" /tmp /tmp/funhouse-update; do
    [[ -d "$base" ]] || continue
    for d in "$base"/adafruit-circuitpython-bundle-10.x-mpy-*; do
      [[ -d "$d" ]] || continue
      BUNDLE="$d"
    done
    [[ -n "$BUNDLE" ]] && break
  done
fi

if [[ -z "$BUNDLE" || ! -d "$BUNDLE" ]]; then
  echo "Could not find a CP 10.x bundle." >&2
  echo "Download it from https://circuitpython.org/libraries" >&2
  echo "Then re-run: $0 /path/to/adafruit-circuitpython-bundle-10.x-mpy-XXXXXXXX" >&2
  exit 1
fi

# Bundle may be the bundle root or already pointing at lib/
LIB_SRC="$BUNDLE/lib"
[[ -d "$LIB_SRC" ]] || LIB_SRC="$BUNDLE"
if [[ ! -d "$LIB_SRC" ]]; then
  echo "$BUNDLE doesn't contain a lib/ directory" >&2
  exit 1
fi

DEST="$MOUNT/lib"
mkdir -p "$DEST"

echo "Bundle: $LIB_SRC"
echo "Target: $DEST"
echo "---"

missing=()
copied=0
while IFS= read -r line; do
  # Strip comment / whitespace
  entry="${line%%#*}"
  entry="${entry## }"
  entry="${entry%% }"
  [[ -z "$entry" ]] && continue

  src="$LIB_SRC/$entry"
  if [[ ! -e "$src" ]]; then
    missing+=("$entry")
    echo "  ! MISSING in bundle: $entry"
    continue
  fi

  target="$DEST/$entry"

  if [[ -d "$src" ]]; then
    # Directory: mirror contents and drop stale files in target.
    # -rt = recurse + preserve mtimes. FAT silently drops perms/owner;
    # macOS rsync 2.6 doesn't have --no-* flags so we omit them.
    mkdir -p "$target"
    rsync -rt --delete "$src/" "$target/"
  else
    # Single file: same approach.
    rsync -t "$src" "$target"
  fi

  echo "  + $entry"
  copied=$((copied + 1))
done < "$REQ_FILE"

# Strip macOS resource-fork droppings the cp may have created.
find "$DEST" -name '._*' -delete 2>/dev/null || true

sync
echo "---"
echo "Installed $copied libraries."
if (( ${#missing[@]} )); then
  echo "Missing in bundle (${#missing[@]}):" >&2
  for m in "${missing[@]}"; do echo "  $m" >&2; done
  exit 2
fi
