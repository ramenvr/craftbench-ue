"""L2-introspect script for the gp-dot-aoe-burn-bp task.

Structural, READ-ONLY verification that the deliverable **really is Blueprint**
(the `-bp` variant's anti-gaming gate against solving it in C++). The behavior
itself is gated by the UNCHANGED L2 fixture `AAoeBurnFunctionalTest`
(`Source/CraftBenchTests/Tasks/gp-dot-aoe-burn/`), which the `-cpp` original
and this twin share byte-identically along with the committed `L_AoeBurn.umap`.

Emits the CRAFTBENCH-INTROSPECT-JSON verdict block; every mechanism, every
fail-closed rule and the git-HEAD provenance keying of the native sweep are
documented in `_bp_variant_lib.py`. Read that module first.

The five checks, all of which must pass:

  * `task_folder_exists`        - /Game/Tasks/gp-dot-aoe-burn-bp/ exists and
                                  lists >= 1 asset
  * `bp_pawn_present`           - a Blueprint under that folder whose
                                  GeneratedClass derives from
                                  `ACraftBenchCharacter`
  * `bp_pawn_grants_bp_ability` - the burning area is Blueprint: >= 1
                                  Blueprint-generated class in the pawn's
                                  GrantedAbilities, and ZERO native ones
  * `resolved_pawn_is_blueprint`- no agent-authored C++ subclass of
                                  `ACraftBenchCharacter` exists at all
  * `pawn_visibly_represented`  - the pawn's inherited mesh component carries a
                                  SkeletalMesh from the read-only
                                  /Game/Characters/ pool

TASK-SPECIFIC NOTES

1. **The derivation base is the GENERIC `ACraftBenchCharacter`.** This family
   is not health-first: the agent's pawn needs no health system of its own,
   because the Health this task moves belongs to the FIXTURE'S OWN target
   characters. The bare lineage would be the wrong base here and the generic
   one is what the `-cpp` reference and the fixture's own targets both use.

2. **`min_bp_abilities = 1`** - the burning-area ability. The brief for this
   twin is that the ability itself be Blueprint-generated, which is precisely
   what this check asserts (plus the zero-native-entries rule that closes the
   BP-shell-plus-C++-ability shape; see `_bp_variant_lib.py`'s
   GRANTED-ABILITY NATIVE HOLE note).

3. **Nothing here asserts the radius, the rate, the duration, or - most
   importantly - the SPATIAL SELECTIVITY.** All four are behavioral and are
   gated by the shared fixture (AB-2/AB-3/AB-4/AB-5/AB-6). AB-4, the
   "affects the character inside, spares the one outside" gate, is this
   family's whole reason to exist, and it is *only* observable at runtime: no
   structural property of a Blueprint asset can prove that a distance test
   will actually be evaluated, let alone evaluated correctly. A structural
   stand-in would be a gate that looks like it covers the axis and does not -
   the worst failure mode this repo tracks. It is deliberately absent.

4. **The fixture spawns its own targets, so this script must NOT read them.**
   Those three characters are `ACraftBenchCharacter` INSTANCES created at
   runtime by the verifier; they are not assets, they never appear under
   `TASK_DIR`, and they are invisible to the asset registry this script walks.
   The native-subclass sweep in `resolved_pawn_is_blueprint` keys on committed
   git-HEAD classes, so the committed generic base the targets instantiate is
   exempt by construction - see `_bp_variant_lib.py`.

5. **Independence from the calibration.** All five checks are structural
   properties of the submitted assets, so re-pinning `StepEpsilon`,
   `StopEpsilon`, the mean-rate band or the derived total band cannot move
   this leg's verdict. That matters more here than on the sibling families:
   this family's bands were corrected TWICE on 2026-08-11 during calibration
   (per-window -> mean rate; total top 60 -> a derived 105), and this leg
   would have been unaffected by either change.

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
TASK_DIR = "/Game/Tasks/gp-dot-aoe-burn-bp"

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
