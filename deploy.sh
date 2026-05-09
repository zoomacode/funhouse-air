#!/usr/bin/env bash
# Deploy code.py and components/ to the FunHouse's CIRCUITPY drive.
#
# Usage:
#   ./deploy.sh                # just copy
#   ./deploy.sh --reload       # also send Ctrl-D over serial to trigger reload
#   ./deploy.sh --tail         # also tail serial for 10s after deploy
#   ./deploy.sh --reload --tail
#   ./deploy.sh --tail --tail-secs 30
#
# Notes:
#   - settings.toml (with WiFi/MQTT creds) is intentionally NOT touched.
#   - Library files in lib/ are not deployed; they're a one-time setup.

set -euo pipefail

RELOAD=false
TAIL=false
TAIL_SECONDS=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reload|-r) RELOAD=true; shift ;;
    --tail|-t) TAIL=true; shift ;;
    --tail-secs) TAIL_SECONDS=$2; shift 2 ;;
    -h|--help)
      awk '
        NR==1 && /^#!/ { next }
        /^#/ { sub(/^# ?/, ""); print; next }
        /^[^#]/ { exit }
      ' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Run with --help for usage." >&2
      exit 1
      ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOUNT="/Volumes/CIRCUITPY"

if [[ ! -d "$MOUNT" ]]; then
  echo "Error: $MOUNT not mounted. Plug in the FunHouse." >&2
  exit 1
fi

echo "Deploying $REPO_DIR -> $MOUNT"

# code.py
if [[ -f "$REPO_DIR/code.py" ]]; then
  cp "$REPO_DIR/code.py" "$MOUNT/code.py"
  echo "  + code.py"
else
  echo "  ! code.py not found in repo" >&2
fi

# components/*.py
if [[ -d "$REPO_DIR/components" ]]; then
  mkdir -p "$MOUNT/components"
  for f in "$REPO_DIR/components"/*.py; do
    [[ -f "$f" ]] || continue
    bn=$(basename "$f")
    cp "$f" "$MOUNT/components/$bn"
    echo "  + components/$bn"
  done
fi

# Flush macOS write cache so the device sees the new files.
sync

# Pick the first usbmodem port (FunHouse exposes exactly one).
SERIAL=""
for s in /dev/cu.usbmodem*; do
  [[ -e "$s" ]] || continue
  SERIAL="$s"
  break
done

configure_port() {
  if [[ -n "$SERIAL" ]]; then
    stty -f "$SERIAL" 115200 cs8 -cstopb -parenb raw -echo 2>/dev/null || true
  fi
}

if $RELOAD; then
  if [[ -z "$SERIAL" ]]; then
    echo "  ! no /dev/cu.usbmodem* found, skipping reload" >&2
  else
    configure_port
    # Ctrl-D in the REPL triggers a reload of code.py.
    printf '\x04' > "$SERIAL"
    echo "  ↻ sent Ctrl-D to $SERIAL"
  fi
fi

if $TAIL; then
  if [[ -z "$SERIAL" ]]; then
    echo "  ! no /dev/cu.usbmodem* found, skipping tail" >&2
  else
    configure_port
    echo "  … tailing $SERIAL for ${TAIL_SECONDS}s (Ctrl-C to stop early)"
    cat "$SERIAL" &
    CAT_PID=$!
    # macOS doesn't have `timeout`, so DIY.
    sleep "$TAIL_SECONDS"
    kill "$CAT_PID" 2>/dev/null || true
    wait "$CAT_PID" 2>/dev/null || true
    echo
  fi
fi

echo "Done."
