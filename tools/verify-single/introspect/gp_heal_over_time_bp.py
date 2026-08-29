"""L2-introspect script for the gp-heal-over-time-bp task.

Structural, READ-ONLY verification that the deliverable **really is Blueprint**
(the `-bp` variant's anti-gaming gate against solving it in C++). The behavior
itself is gated by the UNCHANGED L2 fixture `AHealOverTimeFunctionalTest`
(`Source/CraftBenchTests/Tasks/gp-heal-over-time/`), which the `-cpp` original
and this twin share byte-identically along with the committed
`L_HealOverTime.umap`.

Emits the CRAFTBENCH-INTROSPECT-JSON verdict block; every mechanism, every
fail-closed rule and the git-HEAD provenance keying of the native sweep are
documented in `_bp_variant_lib.py`. Read that module first.

The five checks, all of which must pass:

  * `task_folder_exists`        - /Game/Tasks/gp-heal-over-time-bp/ exists and
                                  lists >= 1 asset
  * `bp_pawn_present`           - a Blueprint under that folder whose
                                  GeneratedClass derives from
                                  `ACraftBenchCharacter`
  * `bp_pawn_grants_bp_ability` - >= 1 Blueprint-generated class in the pawn's
                                  GrantedAbilities, and ZERO native ones
  * `resolved_pawn_is_blueprint`- no agent-authored C++ subclass of
                                  `ACraftBenchCharacter` exists at all
  * `pawn_visibly_represented`  - the pawn's inherited mesh component carries a
                                  SkeletalMesh from the read-only
                                  /Game/Characters/ pool

TASK-SPECIFIC NOTES

1. **The derivation base is the GENERIC `ACraftBenchCharacter`** (PIN.md D2 for
   the `-cpp` original): this family is deliberately NOT health-first, so the
   pre-built attribute set is a given and there is no stage-1 ladder and no
   fixture derivation gate. A submission on the `ACraftBenchBareCharacter`
   lineage has no Health at all and dies at the fixture's HOT-0 by name; here
   it would additionally fail `bp_pawn_present`, which is the truthful reading
   for a `-bp` twin - such a Blueprint is not a subclass of "the provided
   character" the prompt names.

2. **`min_bp_abilities = 1`.** One restorative ability. The clamp - this
   family's headline discriminator (HOT-5's dual current/base read) - is
   deliberately NOT asserted structurally here: the lawful Blueprint clamp
   routes are plural (a BP `UAttributeSet` subclass, a BP
   `UGameplayModMagnitudeCalculation`, a BP ability loop), PIN.md section 6
   requires `ClampEpsilon` to be calibrated against three different solves for
   exactly that reason, and a structural gate that recognized only one of them
   would false-FAIL the other two while adding nothing L2 does not already
   measure behaviorally.

3. **KNOWN GAP, recorded rather than assumed covered.** The native sweep is
   scaffold-PAWN shaped. A native `UAttributeSet` or
   `UGameplayModMagnitudeCalculation` subclass referenced from an otherwise
   conforming Blueprint pawn is NOT swept, so the clamp itself could be written
   in C++ behind a Blueprint deliverable and this script would not name it.
   This is `bp-g2-verifier-extensions.md` V2.1's own observation about the two
   shipped `-bp` scripts, and it applies here with more force because the clamp
   is where the work is. What DOES cover part of it: `bp_pawn_grants_bp_ability`
   refuses any native ability class in `GrantedAbilities`, so the ability lane
   is closed; and a native attribute set still cannot reach the pawn without a
   C++ pawn subclass to construct it UNLESS the agent overrides the inherited
   subobject class from Blueprint, which UE does not expose. Closing the
   remainder needs the non-pawn native sweep V2.1 budgets (~150 LOC); it is not
   built, and this note exists so the gap is explicit.

Anti-circularity: stock UE Python only; never Aura's MCP tools.
Identity is by **pre-declared content path + derivation**, never by asset or
class NAME - the agent may name its Blueprints anything.
Run headless by the runner via `UnrealEditor-Cmd -ExecutePythonScript=`.
"""
import os
import sys

# `_bp_variant_lib` is a sibling of this file. The runner may launch this
# script directly, or `exec` it from a VERIFIER-GENERATED asset-integrity
# bootstrap living in the run's log dir (`layers/l2_introspect.py`); that
# bootstrap sets `__file__` to THIS path, so anchoring on `__file__` works on
# both paths while a bare `import` would only work on one.
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # no __file__ - cannot locate the lib; see below
    _HERE = None
if _HERE and _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# A failure HERE is deliberately NOT caught. A missing or broken verifier-owned
# library is a verifier defect: it must kill the verdict channel so the layer
# reports `error` -> HARNESS-ERROR (exit 7, NON-GRADED), never be converted
# into a failed check that would score OUR bug against the model.
# See layers/INTROSPECT_CONTRACT.md.
import _bp_variant_lib as bpl  # noqa: E402

# Pre-declared content folder of the task's deliverable (NEVER name-based).
TASK_DIR = "/Game/Tasks/gp-heal-over-time-bp"

# The generic scaffold pawn - this family's base (note 1 above).
PAWN_BASE_CLASS = "CraftBenchCharacter"

MIN_BP_ABILITIES = 1

SPEC = bpl.BpVariantSpec(
    task_dir=TASK_DIR,
    pawn_base_class=PAWN_BASE_CLASS,
    min_bp_abilities=MIN_BP_ABILITIES,
)


def main():
    bpl.main(SPEC)


if __name__ == "__main__":
    main()
