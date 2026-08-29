#!/usr/bin/env bash
# Author all t2-consistent-enum-names assets end to end.
#
# MULTI-BOOT BY NECESSITY, not by taste (2026-07-30 live findings; notes.md
# section 5). Two laws forced this shape and both are one-way:
#   1. TOMBSTONE LAW - once a package is DELETED in an editor session (which
#      is exactly what rename_asset's Lane A fixup does to the old package),
#      the registry never tells the truth about that path again in that boot:
#      get_assets_by_path DROPS it while get_asset_by_object_path keeps
#      returning STALE pre-delete AssetData (a FALSE PASS on the orphan
#      branch). Copying the file back + every rescan route tried (paths /
#      files / modified-files, forced, deny-list-ignoring) does NOT undo it.
#      So a leg's vector CANNOT be taken in the boot that authored it.
#   2. SAME-BOOT MULTI-LEG AUTHORING CORRUPTS THE BYTES - a rename leg run
#      after an earlier leg's baseline restore renames against stale loaded
#      objects and silently ships Blueprints with NO enum dependency at all.
#      So each leg is authored in its OWN fresh boot from the stash.
#
# The boot plan, therefore:
#   boot 1        RENLANE_PHASE=baseline           author + stash the baseline
#   boots 2..N    RENLANE_PHASE=author  LEG=<leg>  mutate, harvest to .staged/
#   boots N+1..   RENLANE_PHASE=verify  LEG=<leg>  grade the REAL graded lane
#                                                  (this runner materializes
#                                                  baseline+overlay on disk
#                                                  BEFORE the boot), assert the
#                                                  exact vector, then PROMOTE
#                                                  .staged/<leg> into the
#                                                  shipped tree.
# Doubtful bytes never reach reference/ or discrimination/: promotion happens
# only after a cold boot graded the leg with no rescan and no mutation.
#
# PRECONDITIONS: no editor running, no runs/.live-run.lock.
# ROUTES (live-proven 2026-07-30, notes.md section 5): the BP enum variables
# are authored from STOCK python via EdGraphPinType TEXT IMPORT (its
# properties are protected, so set_editor_property cannot build the pin), and
# every AUTHORING-phase dependency/referencer read is preceded by
# scan_paths_synchronous(force_rescan=True) because edges are scan-time. The
# VERIFY phase deliberately does not rescan - the graded lane's editor does
# not either. No MCP lane is involved.
# ESCAPE HATCHES:
#   RENLANE_ONLY=<leg>          author+verify one leg against the existing
#                               stash (the baseline boot is skipped).
#   RENLANE_REUSE_BASELINE=1    skip the baseline boot and reuse the existing
#                               stash for ALL legs. Legitimate because a leg
#                               is only ever authored FROM the stash, so
#                               re-authoring legs needs no new baseline - and
#                               reusing it is what KEEPS the enum GUIDs stable
#                               across the baseline and every leg. The runner
#                               still proves the substrate matches the stash
#                               byte-for-byte before the first author boot.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
TASK_ID="t2-consistent-enum-names"
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
SUB="$REPO/UE-projects/ThirdPerson/Content/Tasks/$TASK_ID"
STASH="$REPO/tasks/bp/$TASK_ID/authoring/.baseline-stash"
STAGE="$REPO/tasks/bp/$TASK_ID/authoring/.staged"

LEGS=("duplicate-not-rename" "one-left-behind" "reference")
if [ "${RENLANE_TRY_REDIRECTOR:-}" = "1" ]; then
  LEGS+=("redirector-wrong-target")
fi
if [ -n "${RENLANE_ONLY:-}" ]; then LEGS=("${RENLANE_ONLY}"); fi

# UE args must be Windows-form paths under MSYS_NO_PATHCONV=1 (FAILURE-LOG
# 2026-07-28: a /c/Users/... arg reaches UE verbatim and the boot dies).
UPROJECT_W="$(cygpath -m "$UPROJECT")"
SCRIPT_W="$(cygpath -m "$SCRIPT")"

boot() {  # boot <phase> [leg]
  local phase="$1" leg="${2:-}"
  echo "-- boot: phase=$phase leg=${leg:-<none>}"
  RENLANE_PHASE="$phase" RENLANE_LEG="$leg" MSYS_NO_PATHCONV=1 \
    "$UE_CMD" "$UPROJECT_W" -ExecutePythonScript="$SCRIPT_W" \
    -nullrhi -unattended -nosplash >/dev/null 2>&1 || true
  # The live log always has the fixed name; UE rotates the PREVIOUS boot's
  # into ThirdPerson-backup-*.log, so `ls -t` could tie and pick the wrong one.
  local log="$LOGDIR/ThirdPerson.log"
  grep -E "RENLANE-" "$log" | sed 's/^\[[^]]*\]\[[^]]*\]LogPython: //' || true
  grep -q "RENLANE-DONE" "$log" || {
    echo "PHASE FAILED ($phase ${leg:-}) - see the RENLANE-ERROR / "
    echo "RENLANE-*-UNAVAILABLE line above, log: $log"; exit 1; }
}

materialize() {  # materialize <leg>: baseline + copy-only overlay, PRE-boot.
  local leg="$1"
  rm -rf "$SUB"; mkdir -p "$SUB"
  cp -r "$STASH/." "$SUB/"
  # A submission is copy-only - it can add and overwrite, never delete. This
  # is byte-for-byte what tools/verify-single does to the graded workdir.
  if [ -d "$STAGE/$leg/Content/Tasks/$TASK_ID" ]; then
    cp -r "$STAGE/$leg/Content/Tasks/$TASK_ID/." "$SUB/"
  fi
}

echo "== 0. guards"
test ! -f "$REPO/runs/.live-run.lock" || { echo "live-run lock present - ABORT"; exit 1; }
tasklist //FI "IMAGENAME eq UnrealEditor-Cmd.exe" 2>/dev/null | grep -q UnrealEditor && { echo "editor running - ABORT"; exit 1; } || true

if [ -n "${RENLANE_ONLY:-}" ] || [ "${RENLANE_REUSE_BASELINE:-}" = "1" ]; then
  echo "== 1. baseline boot SKIPPED (reusing the stash at $STASH)"
  test -d "$STASH" || { echo "no stash at $STASH - run a full pass first"; exit 1; }
  # The STASH is the source of truth (every boot is materialized from it, so
  # whatever the substrate happens to hold right now is irrelevant). Prove it
  # is a complete baseline before a single leg is authored from it.
  for f in Enums/WeaponType.uasset Enums/E_ammo_kind.uasset \
           Enums/enum_DamageType.uasset Enums/ItemRarity.uasset \
           BP_RefA.uasset BP_RefB.uasset; do
    test -f "$STASH/$f" || { echo "stash is incomplete: $f missing"; exit 1; }
  done
  COUNT=$(find "$STASH" -type f | wc -l)
  test "$COUNT" -eq 6 || { echo "stash holds $COUNT files, expected 6"; exit 1; }
  echo "stash is a complete 6-file baseline."
else
  echo "== 1. baseline boot (refuses if the substrate is not empty)"
  boot baseline
fi

echo "== 2. author each leg in its OWN fresh boot (harvest -> .staged/)"
for leg in "${LEGS[@]}"; do
  # Guarantee the ENTRY state file-level rather than inheriting the previous
  # boot's exit state: an author boot must start from the pristine baseline.
  materialize ""
  boot author "$leg"
done

echo "== 3. verify each leg COLD, in the real graded state, then promote"
if [ -z "${RENLANE_ONLY:-}" ]; then
  # The empty leg has no author phase: its graded state IS the committed
  # baseline, so verifying it certifies the baseline bytes themselves.
  materialize empty
  boot verify empty
fi
for leg in "${LEGS[@]}"; do
  materialize "$leg"
  boot verify "$leg"
done

echo "== 4. substrate must hold EXACTLY the committed baseline (6 files)"
for f in Enums/WeaponType.uasset Enums/E_ammo_kind.uasset \
         Enums/enum_DamageType.uasset Enums/ItemRarity.uasset \
         BP_RefA.uasset BP_RefB.uasset; do
  test -f "$SUB/$f" || { echo "baseline file missing: $f"; exit 1; }
done
COUNT=$(find "$SUB" -type f | wc -l)
test "$COUNT" -eq 6 || { echo "expected exactly 6 baseline files, found $COUNT"; exit 1; }
echo "baseline intact."

echo "== 5. shipped assets (reference 6 + variants 4+5 = 15 expected)"
COUNT=$(find "$REPO/tasks/bp/$TASK_ID/reference" \
             "$REPO/tasks/bp/$TASK_ID/discrimination" -name "*.uasset" | wc -l)
test "$COUNT" -eq 15 || { echo "expected 15 shipped .uassets, found $COUNT"; exit 1; }

echo "== 6. next steps (manual)"
echo "  - notes.md section 5 is already calibrated; update it only if a"
echo "    RENLANE-CAL line above disagrees with it"
echo "  - cb discriminate --task bp/$TASK_ID --wip --warm-cache   (4 legs)"
echo "  - commit the 6 baseline + 15 leg .uassets (NOT authoring/.baseline-stash"
echo "    or authoring/.staged - both gitignored), then the git-HEAD"
echo "    certification re-run (no --wip)"
