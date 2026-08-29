#!/usr/bin/env bash
# Author all 6 cutscene-row assets end to end (one boot; each state graded
# in-process by the real verifier before harvest). Substrate ships NO baseline
# and must end without the task folder.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
TASK_ID="t2-cutscene-camera-push-and-hero-rise"
UPROJECT="$REPO/UE-projects/ThirdPerson/ThirdPerson.uproject"
# UE_CMD resolution (fixed 2026-08-16 — was hardcoded to one machine's engine
# path, so this script could only ever run on that box). Precedence mirrors the
# rig's own rule (stack.py:264-275): an exported
# CB_UE_ROOT wins, then the gitignored .env fills it, then a short search. Never
# hardcode an engine path — the fallback list is the Epic default plus one
# common alternate install root.
_ue_root="${CB_UE_ROOT:-}"
if [ -z "$_ue_root" ] && [ -f "$REPO/.env" ]; then
  _ue_root="$(sed -n 's/^[[:space:]]*CB_UE_ROOT[[:space:]]*=[[:space:]]*//p' "$REPO/.env" | tail -1 | tr -d '"'"'"'')"
fi
if [ -z "$_ue_root" ]; then
  for _c in "C:/Program Files/Epic Games/UE_5.8" "F:/Games/UE_5.8"; do
    [ -x "$_c/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" ] && { _ue_root="$_c"; break; }
  done
fi
UE_CMD="$_ue_root/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
test -x "$UE_CMD" || { echo "UnrealEditor-Cmd not found. Set CB_UE_ROOT (env or $REPO/.env) to your UE 5.8 root; tried: '$_ue_root'" >&2; exit 1; }
SCRIPT="$REPO/tasks/bp/$TASK_ID/authoring/author_all_assets.py"
LOGDIR="$REPO/UE-projects/ThirdPerson/Saved/Logs"
STRAY="$REPO/UE-projects/ThirdPerson/Content/Tasks/$TASK_ID"

echo "== 0. guards"
test ! -f "$REPO/runs/.live-run.lock" || { echo "live-run lock present - ABORT"; exit 1; }
tasklist //FI "IMAGENAME eq UnrealEditor-Cmd.exe" 2>/dev/null | grep -q UnrealEditor && { echo "editor running - ABORT"; exit 1; } || true
test ! -e "$STRAY" || { echo "substrate already has $STRAY - resolve first"; exit 1; }

echo "== 1. headless authoring + in-process grading (one boot)"
UPROJECT_W="$(cygpath -m "$UPROJECT")"
SCRIPT_W="$(cygpath -m "$SCRIPT")"
MSYS_NO_PATHCONV=1 "$UE_CMD" "$UPROJECT_W" \
  -ExecutePythonScript="$SCRIPT_W" -nullrhi -unattended -nosplash || true

LOG="$(ls -t "$LOGDIR"/ThirdPerson*.log | head -1)"
echo "== 2. verdict lines from $LOG"
grep -E "CUTSCENE-" "$LOG" || true
grep -q "CUTSCENE-DONE" "$LOG" || { echo "AUTHORING FAILED - check CUTSCENE-ERROR above"; exit 1; }

echo "== 3. substrate must end clean"
if [ -e "$STRAY" ] && [ -n "$(ls -A "$STRAY" 2>/dev/null)" ]; then
  echo "WARNING: leftover files under $STRAY"; ls -la "$STRAY"; exit 1
fi
rmdir "$STRAY" 2>/dev/null || true

echo "== 4. harvested assets"
find "$REPO/tasks/bp/$TASK_ID" -name "*.uasset" -newer "$SCRIPT" -print

echo "== 5. next steps (manual)"
echo "  - cb discriminate --task $TASK_ID   (expect reference PASS, empty + 5 variants FAIL per MATRIX.md)"
echo "  - delete the six README-MISSING-ASSETS.md in the landing commit"
echo "  - fill notes.md section 6 from the CUTSCENE-VECTOR lines above"
