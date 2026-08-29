# notes — t1-gameplay-tag-gate

## Provenance

- **Coverage gap: `gameplay-tags` (uncovered concept).** Authored 2026-08-11
  for the SIMPLE SLATE (weak-model floor: tasks a weak model should pass, so
  the model-comparison leaderboard gains resolution at the bottom end).
  `gameplay-tags` (concepts.csv row: Gameplay Tags, weight `high`, bucket
  Content Integration) had no task exercising it as a primary concept.
- Tier T1, substrate CraftBenchTemplate, basket cpp, layers [L1, L2] (no L2I).

## Design decisions

1. **The seam is reflection, not a type.** The fixture drives the marker
   remove/re-add via `FindFunction`/`ProcessEvent` on accessor names the
   SCAFFOLD declares (`AddGateTag`/`RemoveGateTag`, one `FGameplayTag` param
   each). It never includes the agent module's header and never names the
   agent's class — host resolution is by the `TagGateRoot` tag, per repo law.
   An agent may subclass or even fully replace the scaffold class; only the
   tag, the accessor names/signatures, and the behavior are load-bearing (all
   three are disclosed). A `ParmsSize`/`NumParms` guard makes a reshaped
   accessor a named prepare-time FAIL instead of a ProcessEvent memory hazard.
2. **Tag registration is native, in the scaffold module.**
   `UE_DEFINE_GAMEPLAY_TAG_COMMENT` in `TagGateActor.cpp` registers
   `CraftBench.TagGate.Active` at module load — no `Config/` edit, no
   `ue-config/` overlay, nothing for the agent to set up. Both substrate
   Build.cs files already depend on `GameplayTags` (restored GAS deps), so
   **no Build.cs edit was needed anywhere**. The fixture requests the tag
   non-fatally and FAILs by name if a submission deleted the definition.
3. **Steering to gameplay tags without breaking Hard Rule #2.** The prompt is
   behavior-only ("hierarchical state markers"); the steer to the tag system
   comes from the workspace state: the accessor signatures take `FGameplayTag`
   and the native tag symbol sits in the scaffold header. Those are inputs,
   not instructions. Residual (stated in task.md): storage in a
   `TSet<FGameplayTag>` instead of an `FGameplayTagContainer` passes — L2
   cannot see container types and no L5 exists. The concept the verifier
   genuinely discriminates is *holding/querying/reacting to a gameplay-tag
   value*, which the seam forces.
4. **Checkpoint arithmetic.** Period 0.5 s; checkpoints {1.8, 3.6, 5.4} are
   deliberately mid-interval (and exact frame multiples at the deterministic
   60 FPS: frames 108/216/324), so no legal implementation races a checkpoint
   against a scheduled emission. Bands: cp0 [3,4] (first line at 0.5 s gives
   3; a legal immediate first line gives 4), cp1 exactly 0 new, cp2 [2,4] new
   (computed legit range 3-4 for timer-restart, gated-callback, and
   immediate-resume shapes; floor 2 is one below as margin). All bands are
   two-sided so spam fails high and silence fails low.
5. **Single fixture, no `fps_legs`.** Simplicity is a requirement of this
   slate: one map, one fixture, one editor leg. The cost is that a
   frame-counter implementation (30 frames/emission) passes at the always-60
   verifier rate — recorded as an accepted residual in task.md. Hardening
   option if this task ever graduates from the simple slate: add
   `fps_legs: [60, 20]` (the fixture asserts world-time counts and works
   unchanged at any rate) and disclose framerate-independence in the prompt.
6. **Empty-FAIL path verified by construction.** The scaffold's accessor
   stubs are empty and there is no timer, so an empty submission compiles
   (L1 PASS), sails through every prepare-time gate (actor placed, tag
   natively registered, accessors present), and dies at cp0's named assertion
   with count 0 — a graded FAIL at `expected 3-4 CRAFTBENCH_TAG_GATE_TICK
   emissions while the marker is present`, not a wrong-reason FAIL.
7. **Discrimination package per the 2026-08-11 §7 amendment**: requirements
   table + automatic reference-PASS/empty-FAIL rows; no hand-authored
   variants, because the table found no unasserted prompt requirement (the
   known residuals are accepted-and-stated, not holes).

## Weak-model difficulty rationale

The whole solution is: one container member, seed one tag in `BeginPlay`,
start one looping 0.5 s timer, one `HasTag` check in the callback, two
one-line accessor bodies (~25 LOC in the reference, 2 files, zero new files,
zero Build.cs edits). No GAS, no input, no movement, no assets, no math. The
only conceptual step above t0 is *conditionality*: the log must be gated by
runtime-mutable state. Every number the fixture gates on is disclosed in the
prompt (period, 0.6 s windows, exact token/category/verbosity, stop/resume
semantics), so there is nothing to reverse-engineer — a weak model fails this
only by failing the concept.

## Pending binaries + calibration TODOs (in order)

The map is a committed BINARY this authoring pass cannot create (no UE run in
this lane). Until it lands, `cb lint` will flag the missing
`Content/Maps/t1-gameplay-tag-gate/L_TagGate.umap` — **expected**.

- [ ] Build `CraftBenchTemplateEditor` (first compile of scaffold + fixture;
      also compile-validates the reference overlay separately). Watch for two
      reference-specific risks: `FNativeGameplayTag -> FGameplayTag` implicit
      conversion at the `AddTag(TAG_CraftBench_TagGate_Active)` call sites
      (swap to `.GetTag()` if 5.8 lacks the operator), and the
      `Fn->ParmsSize == sizeof(FGameplayTag)` guard in the fixture (an
      editor-build FName layout surprise would show up here as a false
      `unexpected parameter layout` FAIL against the reference).
- [ ] Authoring-lane run of `aids/author_reference.py` (real RHI, not
      -nullrhi) to create + save the map; grep the editor log for
      `TAGGATE-DONE`.
- [ ] Add the `docs/MAPS.md` inventory row (placed actors, automation name
      `Project.Functional Tests.Maps.t1-gameplay-tag-gate.L_TagGate.TagGateFunctionalTest`,
      authoring provenance = the aid script). `cb lint` cross-checks the map
      count against `git ls-files`.
- [ ] `cb lint --task cpp/t1-gameplay-tag-gate` — zero ERRORs.
- [ ] `cb discriminate --task cpp/t1-gameplay-tag-gate --wip` — reference
      PASS, empty FAIL via the named cp0 substring; update MATRIX.md's Status
      section with the executed result.
- [ ] Calibrate: read the fixture's observed counts from the reference run
      log (expect 3 / 0 / 3 at cp0/cp1/cp2) and record them here BEFORE
      finalizing; widen nothing without a measured reason.
- [ ] `cameras.json` (the camera-plan lane; not part of this release) (SHOULD, presentation-only): propose AFTER the
      scaffold/map commit; subject is a bare-`AActor` scaffold
      (meshless — frames correctly but renders nothing; a `pose` wide shot of
      the fixture area is the honest choice, or skip).
- [ ] `tasks/CATALOG.md` row.
- [ ] Post-commit: `./cb refgate cpp/t1-gameplay-tag-gate` green against the
      landed commit (the close), then `cb batch-eval --references all` stays
      N/N.

> **RECONCILIATION 2026-08-11/12 (authoring-lane + graph-lane runs DONE).**
> Statements above about pending binaries / empty reference/ describe the
> authoring-time state and are now historical: binaries are committed
> (39433c2, 09781a8) and `cb refgate` graded this task's reference PASS
> from git HEAD. Remaining: the empty-FAIL discriminate leg.
