"""L2-introspect script for the gp-double-jump-stamina-bp task.

Structural, READ-ONLY verification that the deliverable **really is Blueprint**
(the `-bp` variant's anti-gaming gate against solving it in C++). The behavior
itself is gated by the UNCHANGED L2 fixture `ADoubleJumpStaminaFunctionalTest`
(`Source/CraftBenchTests/Tasks/gp-double-jump-stamina/`), which the `-cpp`
original and this twin share byte-identically along with the committed
`L_DoubleJump.umap`.

Emits the CRAFTBENCH-INTROSPECT-JSON verdict block; every mechanism, every
fail-closed rule and the git-HEAD provenance keying of the native sweep are
documented in `_bp_variant_lib.py`. Read that module first.

The five checks, all of which must pass:

  * `task_folder_exists`        - /Game/Tasks/gp-double-jump-stamina-bp/ exists
                                  and lists >= 1 asset
  * `bp_pawn_present`           - a Blueprint under that folder whose
                                  GeneratedClass derives from
                                  `ACraftBenchCharacter`
  * `bp_pawn_grants_bp_ability` - the second jump is Blueprint: >= 1
                                  Blueprint-generated class in the pawn's
                                  GrantedAbilities, and ZERO native ones
  * `resolved_pawn_is_blueprint`- no agent-authored C++ subclass of
                                  `ACraftBenchCharacter` exists at all
  * `pawn_visibly_represented`  - the pawn's inherited mesh component carries a
                                  SkeletalMesh from the read-only
                                  /Game/Characters/ pool

TASK-SPECIFIC NOTES

1. **The derivation base is the GENERIC `ACraftBenchCharacter`.** This family
   is not health-first, and the `ACraftBenchBareCharacter` lineage SUPPRESSES
   the attribute-set subobject that holds `Power` - the only attribute this
   task reads. A Blueprint parented to the bare lineage reads Power as 0.0 and
   dies at the fixture's DJ-3a by name; here it additionally fails
   `bp_pawn_present`, which is the truthful reading for a `-bp` twin.

2. **`min_bp_abilities = 1`** - the second jump. The brief for this twin is
   that the ability itself be Blueprint-generated, which is precisely what this
   check asserts (plus the zero-native-entries rule that closes the
   BP-shell-plus-C++-ability shape; see `_bp_variant_lib.py`'s
   GRANTED-ABILITY NATIVE HOLE note).

3. **Nothing here asserts the impulse, the cost, or the refusal.** All three
   are behavioral and are gated by the shared fixture (DJ-2b/2c, DJ-3a/3b/3c,
   DJ-4). In particular the refusal-below-cost leg is a SKIP-vs-FAIL gate whose
   whole point is not to report a second-jump defect under a resource-gating
   name; a structural stand-in here could only re-introduce that
   misattribution, and it would gate a magnitude the prompt fixes only for the
   cost.

4. **This family is the first consumer of the dense motion sampler (I1.4), so
   the `-cpp` original's own bars are `PROPOSED - NOT YET MEASURED`.** Nothing
   in this script depends on any of them: all five checks are structural
   properties of the submitted assets, so a re-pin of `RiseEpsilon` or
   `CostTol` cannot move this leg's verdict. That independence is deliberate -
   it keeps the "is it Blueprint" axis uncorrelated with the motion
   calibration.

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
TASK_DIR = "/Game/Tasks/gp-double-jump-stamina-bp"

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
