"""L2-introspect script for the gp-health-attribute-ops-bp task.

Structural, READ-ONLY verification that the deliverable **really is Blueprint**
(the `-bp` variant's anti-gaming gate against solving it in C++). The behavior
itself is gated by the UNCHANGED L2 fixture `AHealthAttributeOpsFunctionalTest`
(`Source/CraftBenchTests/Tasks/gp-health-attribute-ops/`), which the `-cpp`
original and this twin share byte-identically along with the committed
`L_HealthOps.umap`.

Emits the CRAFTBENCH-INTROSPECT-JSON verdict block; every mechanism, every
fail-closed rule and the git-HEAD provenance keying of the native sweep are
documented in `_bp_variant_lib.py`. Read that module first.

The five checks, all of which must pass:

  * `task_folder_exists`        - /Game/Tasks/gp-health-attribute-ops-bp/
                                  exists and lists >= 1 asset
  * `bp_pawn_present`           - a Blueprint under that folder whose
                                  GeneratedClass derives from
                                  `ACraftBenchBareCharacter`
  * `bp_pawn_grants_bp_ability` - **both** operations are Blueprint: >= 2
                                  distinct Blueprint-generated classes in the
                                  pawn's GrantedAbilities, and ZERO native ones
  * `resolved_pawn_is_blueprint`- no agent-authored C++ subclass of
                                  `ACraftBenchCharacter` exists at all
  * `pawn_visibly_represented`  - the pawn's inherited mesh component carries a
                                  SkeletalMesh from the read-only
                                  /Game/Characters/ pool

TASK-SPECIFIC NOTES

1. **The derivation base is the TASK base, not the generic scaffold.** The
   `-cpp` original's gate HO-1 fails a pawn that is not on the
   `ACraftBenchBareCharacter` lineage, because the generic
   `ACraftBenchCharacter` ships a pre-built attribute set and subclassing it
   would skip the task's whole stage 1. This script therefore requires the
   Blueprint pawn to reparent to the same task base, so L2I and L2 agree on
   what "the deliverable" is. `ACraftBenchBareCharacter` is `UCLASS(Abstract)`,
   which does not prevent a Blueprint from parenting to it.

2. **`min_bp_abilities = 2`** - this family is the only tier-1 one with two
   operations (damage + heal), and the brief for this twin is that BOTH be
   Blueprint-generated. Deliberately a COUNT of DISTINCT Blueprint ability
   classes (one class granted twice counts once - the 2026-08-16 Q7 dedup;
   `[GA_Damage, GA_Damage]` no longer satisfies 2), not a per-tag lookup: the L2
   fixture's HO-6 already gates, per tag, that an ability carrying that tag is
   granted AND activates, so re-deriving tag ownership here would double-book
   one axis on an ability-tag reflection API this repo has never live-validated
   - and get it wrong in the false-FAIL direction if UE 5.8's
   `AbilityTags` -> `AssetTags` rename behaves differently than expected.
   Combined with the fixture, the pair is airtight: L2 proves the two tags
   exist and move Health in opposite directions, L2I proves the classes
   carrying them are Blueprints and that no C++ ability is granted.

3. **The sweep base stays `ACraftBenchCharacter` (the root), not the task
   base.** A C++ decoy for this task must derive from `ACraftBenchBareCharacter`
   to satisfy HO-1, and every such class is also an `ACraftBenchCharacter`
   subclass - so the root sweep catches it, plus every C++ pawn on the wrong
   lineage. For a `-bp` task ANY C++ subclass of the provided character is
   already the violation.

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
TASK_DIR = "/Game/Tasks/gp-health-attribute-ops-bp"

# The task base pawn the Blueprint must reparent to - the same lineage the L2
# fixture's HO-1 gate requires (note 1 above).
PAWN_BASE_CLASS = "CraftBenchBareCharacter"

# Damage + heal (note 2 above).
MIN_BP_ABILITIES = 2

SPEC = bpl.BpVariantSpec(
    task_dir=TASK_DIR,
    pawn_base_class=PAWN_BASE_CLASS,
    min_bp_abilities=MIN_BP_ABILITIES,
)


def main():
    bpl.main(SPEC)


if __name__ == "__main__":
    main()
