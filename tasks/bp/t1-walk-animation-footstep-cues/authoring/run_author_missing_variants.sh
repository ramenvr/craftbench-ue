#!/usr/bin/env bash
# Author the 2 missing footstep-row variants, end to end. Git Bash, repo root.
# PRECONDITIONS: no editor running (the bench/eval machine is free), no
# runs/.live-run.lock. One headless editor boot, ~2-4 min.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
TASK_ID="t1-walk-animation-footstep-cues"
SUBSTRATE_CONTENT="$REPO/UE-projects/ThirdPerson/Content/Tasks/$TASK_ID"
TASK_DIR="$REPO/tasks/bp/$TASK_ID"
VAR_BOTH="$TASK_DIR/discrimination/cues-on-both-clips/Content/Tasks/$TASK_ID"
VAR_RETIME="$TASK_DIR/discrimination/clip-retimed-to-short-stub/Content/Tasks/$TASK_ID"
REFERENCE_WALK="$TASK_DIR/reference/Content/Tasks/$TASK_ID/A_WalkForward.uasset"
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
SCRIPT="$TASK_DIR/authoring/author_missing_variants.py"
BACKUP="$(mktemp -d)"
LOGDIR="$REPO/UE-projects/ThirdPerson/Saved/Logs"

echo "== 0. guards"
test ! -f "$REPO/runs/.live-run.lock" || { echo "live-run lock present - ABORT"; exit 1; }
tasklist //FI "IMAGENAME eq UnrealEditor-Cmd.exe" 2>/dev/null | grep -q UnrealEditor && { echo "editor running - ABORT"; exit 1; } || true

echo "== 1. backup committed baselines -> $BACKUP"
cp "$SUBSTRATE_CONTENT/A_WalkForward.uasset" "$SUBSTRATE_CONTENT/A_JogForward.uasset" "$BACKUP/"

echo "== 2. headless authoring pass (one boot)"
# -unattended gates Live Coding OFF (an attended editor fails every UBT build
# on this box); -ExecutePythonScript is fine for AUTHORING (only capture needs
# a ticking editor). MSYS_NO_PATHCONV protects /Game paths.
# UE args must be Windows-form paths under MSYS_NO_PATHCONV=1 (FAILURE-LOG
# 2026-07-28: a /c/Users/... arg reaches UE verbatim and the boot dies).
UPROJECT_W="$(cygpath -m "$UPROJECT")"
SCRIPT_W="$(cygpath -m "$SCRIPT")"
MSYS_NO_PATHCONV=1 "$UE_CMD" "$UPROJECT_W" \
  -ExecutePythonScript="$SCRIPT_W" -nullrhi -unattended -nosplash || true

LOG="$(ls -t "$LOGDIR"/ThirdPerson*.log | head -1)"
echo "== 3. verdict lines from $LOG"
grep -E "FOOTSTEP-CAL|VARIANT-.*-OK|FOOTSTEP-WARN|FOOTSTEP-VARIANTS" "$LOG" || true
if ! grep -q "FOOTSTEP-VARIANTS-DONE" "$LOG"; then
  echo "AUTHORING FAILED - restoring baselines, harvesting nothing"
  cp "$BACKUP/A_WalkForward.uasset" "$BACKUP/A_JogForward.uasset" "$SUBSTRATE_CONTENT/"
  exit 1
fi

echo "== 4. harvest into the variant folders"
cp "$SUBSTRATE_CONTENT/A_JogForward.uasset" "$VAR_BOTH/A_JogForward.uasset"
cp "$REFERENCE_WALK" "$VAR_BOTH/A_WalkForward.uasset"   # byte-for-byte reference
cp "$SUBSTRATE_CONTENT/A_WalkForward.uasset" "$VAR_RETIME/A_WalkForward.uasset"

echo "== 5. restore baselines + verify byte-identity against git HEAD"
cp "$BACKUP/A_WalkForward.uasset" "$BACKUP/A_JogForward.uasset" "$SUBSTRATE_CONTENT/"
for f in A_WalkForward A_JogForward; do
  git -C "$REPO" diff --quiet HEAD -- \
    "UE-projects/ThirdPerson/Content/Tasks/$TASK_ID/$f.uasset" \
    || { echo "RESTORE MISMATCH on $f - investigate before any grade"; exit 1; }
done
echo "baselines restored, byte-identical to HEAD"

echo "== 6. next steps (manual)"
echo "  - cb discriminate --task $TASK_ID   (expect: reference PASS, empty + 5 variants FAIL on their MATRIX substrings)"
echo "  - delete the two README-MISSING-ASSETS.md in the same commit that lands the assets"
echo "  - fill notes.md section 5 from the FOOTSTEP-CAL / VARIANT-*-OK lines above"
