#!/usr/bin/env bash
# setup.sh — thin wrapper for the CraftBench post-clone setup script.
# Locates a Python (py -3.12 -> py -3 -> python3 -> python), then runs the brain
# (tools/scripts/setup_craftbench.py) forwarding all arguments unchanged:
#   ./setup.sh [--no-tests] [--json] [--full] [--strict] [--verbose]
# Works from git-bash on Windows and from macOS/Linux shells. All logic lives
# in the brain.

here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
brain="$here/tools/scripts/setup_craftbench.py"
if [ ! -f "$brain" ]; then
    echo "FAIL  $brain not found (incomplete clone?)" >&2
    exit 1
fi

FWD=("$@")

try() { # try <exe> [pre-args...]
    local exe="$1"; shift
    command -v "$exe" >/dev/null 2>&1 || return 1
    "$exe" "$@" --version >/dev/null 2>&1 || return 1
    exec "$exe" "$@" "$brain" ${FWD[@]+"${FWD[@]}"}
}

try py -3.12
try py -3
try python3
try python

echo "FAIL  no working Python found (need 3.11+; 3.12 preferred)." >&2
exit 1
