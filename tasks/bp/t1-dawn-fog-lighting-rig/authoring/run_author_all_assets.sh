#!/usr/bin/env bash
# Author all 6 dawn-fog assets end to end. Git Bash, repo root. One headless
# editor boot; each asset is graded IN-PROCESS by the real verifier before it
# is harvested. PRECONDITIONS: no editor running, no runs/.live-run.lock.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
TASK_ID="t1-dawn-fog-lighting-rig"
UPROJECT="$REPO/UE-projects/ThirdPerson/ThirdPerson.uproject"
# UE_CMD resolution (fixed 2026-08-16 — was hardcoded to one machine's engine
# path, so this script could only ever run on that box). Precedence mirrors the
# rig's own rule (stack.py:264-275): an exported
# CB_UE_ROOT wins, then the gitignored .env fills it, then a short search. Never
# hardcode an engine path — the fallback list is the Epic default plus one
# common alternate install root.
_ue_root="${CB_UE_ROOT:-}"
if [ -z "$_ue_root" ] && [ -f "$REPO/.env" ]; then
  _ue_root="$(sed -n 's/^[[:space:]]*CB_UE_ROOT[[:space:]]*=[[:space:]]*//p' "$REPO/.env" | tail -1 | tr -d '"'"'"'
')"
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
# UE args must be Windows-form paths under MSYS_NO_PATHCONV=1 (FAILURE-LOG
# 2026-07-28: a /c/Users/... arg reaches UE verbatim and the boot dies).
UPROJECT_W="$(cygpath -m "$UPROJECT")"
SCRIPT_W="$(cygpath -m "$SCRIPT")"
MSYS_NO_PATHCONV=1 "$UE_CMD" "$UPROJECT_W" \
  -ExecutePythonScript="$SCRIPT_W" -nullrhi -unattended -nosplash || true

LOG="$(ls -t "$LOGDIR"/ThirdPerson*.log | head -1)"
echo "== 2. verdict lines from $LOG"
grep -E "DAWNFOG-" "$LOG" || true
grep -q "DAWNFOG-DONE" "$LOG" || { echo "AUTHORING FAILED - nothing may be trusted; check DAWNFOG-ERROR above"; exit 1; }

echo "== 3. substrate must end clean (this task ships NO baseline)"
if [ -e "$STRAY" ] && [ -n "$(ls -A "$STRAY" 2>/dev/null)" ]; then
  echo "WARNING: leftover files under $STRAY - delete before any grade"
  ls -la "$STRAY"; exit 1
fi
rmdir "$STRAY" 2>/dev/null || true
git -C "$REPO" status --short -- "UE-projects/ThirdPerson/Content/Tasks/" | grep -v "_runreport" || echo "substrate content clean"

echo "== 4. harvested assets"
find "$REPO/tasks/bp/$TASK_ID" -name "*.uasset" -newer "$SCRIPT" -print

echo "== 5. next steps (manual)"
echo "  - cb discriminate --task $TASK_ID   (expect: reference PASS, empty + 5 variants FAIL per MATRIX.md)"
echo "  - delete the five README-MISSING-ASSETS.md in the same commit that lands the assets"
echo "  - fill notes.md section 5 from the DAWNFOG-SPELLING / DAWNFOG-VECTOR lines above"
echo "  - look-inspection once the rig exists (human eyes only, never gates)"
