# Authoring notes — t1-blueprint-graph-on-beginplay

## Provenance

- Source idea: **the internal design corpus R142** (simple-slate wave, 2026-08-11).
- Slate intent: SIMPLE SLATE — a task a WEAK model should pass, so the
  model-comparison leaderboard gains resolution at the bottom end. Simplicity
  is a requirement of the prompt design (one graph, two variable reads, one
  add, one string build, one print); the verifier still has teeth (empty
  submission FAILs at a named assertion; every anti-gaming note names a real
  defense).

## Design decisions

1. **t0-sanity-bp idiom, plus one twist.** The fixture loads the deliverable
   by its required path and spawns it (no asset scan, no tags) exactly like
   `t0-sanity-bp-log-on-beginplay`. The twist that makes it T1: in
   `FWorldDelegates::OnWorldInitializedActors` (the repo's documented
   pre-BeginPlay hook) the fixture spawns the instance into the
   not-yet-begun world and OVERRIDES both editable values (137/42) before
   BeginPlay dispatches — so a hardcoded print of the default-derived sum
   (7+5=12) fails, and only real variable reads produce the expected
   `CRAFTBENCH_GRAPH_TOTAL=179`.
2. **"Placed in the task map" is realized as verifier-owned runtime placement,
   not a map edit.** The task card's outcome phrasing suggests a placed
   instance, but `AGENT_WRITABLE.json` denies `Content/Maps/` (defense in
   depth), and the graded map cannot contain an instance of an asset the agent
   has not authored yet (a pre-placed reference-classed instance would be gold
   in the map). The fixture's world-init spawn gives the same lifecycle as a
   level-placed actor (BeginPlay dispatched with the rest of the world, after
   the override) while keeping the committed map fixture-only. Consequently
   the map contains ONLY the fixture actor — the "scaffold-derived placed
   actor" from the task card is the runtime-spawned subject, not a map export.
3. **Integer variables, not floats.** Blueprint int-to-string conversion is
   clean ("179"), float conversion is not ("179.0"); an exact-line assertion
   must not depend on float formatting.
4. **Two counters in one GLog device** (marker-prefix count + exact-line
   count) so the checkpoint distinguishes silent / wrong-value / multi-print
   with three distinct named assertions — each a grep target in
   `discrimination/MATRIX.md`, each verified to sit inside ONE quoted string
   segment (the multi-line `TEXT("..." "...")` seams were checked).
5. **`BlueprintReadOnly` on both scaffold properties.** The agent's graph gets
   getter nodes but no setters — closing the "plant your own values then
   print them" line (anti-gaming note 5) at the reflection level rather than
   by assertion.
6. **Construction-script residual from t0 is CLOSED here for free**: the
   override lands after construction, before BeginPlay, so a construction-time
   print can only see the defaults and fails the exact-line gate.

## Weak-model difficulty rationale (tier T1)

The reference is ~5 nodes and one asset: create Blueprint at a named path with
a named parent, wire BeginPlay -> two getter nodes -> integer Add -> append to
a literal prefix -> Print String. No timing, no physics, no components, no
input, one checkpoint, one mechanism. Everything the fixture asserts is
disclosed in the prompt (exact format, exactly-once, current-values-not-
defaults, required path, required parent). A weak model that can author any
Blueprint graph at all should pass; models that hardcode, print on Tick, or
skip the asset entirely are separated into three different named failures —
which is the leaderboard resolution this slate exists for. Senior-dev time
under 15 minutes (T1 floor; T0 is reserved for the two sanity smokes).

## Pending binaries — DO NOT fabricate

- `UE-projects/CraftBenchTemplate/Content/Maps/t1-blueprint-graph-on-beginplay/L_GraphMath.umap`
  does NOT exist yet. `aids/author_reference.py` creates it in the
  authoring-lane run (real editor, `-RenderOffScreen`). **`cb lint` will flag
  the missing map until then — expected.**
- `reference/` is **EMPTY** pending the same run: the reference Blueprint's
  event graph must be wired via the MCP bp lane (vanilla UE 5.8 editor Python
  cannot create/wire K2 nodes — precedent and recipe in
  `tasks/bp/t0-sanity-bp-log-on-beginplay/REFERENCE-NOTE.md`, including the
  AuraSandbox promotion step), after which `aids/author_reference.py`
  verifies, compiles, harvests to `reference/Content/Tasks/<id>/`, and
  deletes the substrate copy (no gold in the graded tree). The aid is
  fail-closed: `GRAPHMATH-DONE` (log line + `aids/author_reference.DONE`)
  appears only on full success.
- `docs/MAPS.md` inventory row and `cameras.json` (the camera-plan lane; not part of this release) (checklist step 5,
  a camera plan) are owed WITH the map commit — both need
  the scene to exist first.

## Calibration TODOs (resolve in the authoring-lane run, before trusting MATRIX.md)

1. **Spawn-during-OnWorldInitializedActors legality.** The fixture spawns the
   subject inside the world-init delegate (world initialized, not begun play)
   and relies on BeginPlay being deferred to world start. This is believed
   safe (InitializeActorsForPlay has completed component registration) but is
   the one lifecycle claim this task adds beyond the proven t0 recipe —
   confirm on the first reference leg; the `PrepareTest` deferred-spawn
   fallback is the designed retreat if it misbehaves (it preserves
   override-before-BeginPlay via `SpawnActorDeferred`).
2. **Print String int formatting.** Confirm the reference's int append yields
   `CRAFTBENCH_GRAPH_TOTAL=179` with no grouping/locale artifacts in the
   `LogBlueprintUserMessages` line (t0 confirmed the channel/verbosity
   routing headless on Windows; the int rendering is the remaining check).
3. **Checkpoint margin.** cp0 at 0.3 s world time (t0 used 0.2 s and passed);
   confirm the BeginPlay emission always lands before it under
   `-deterministic -FPS=60`.
4. **Fallback-path double-spawn guard.** Verify the delegate fires exactly
   once per PIE world under the automation runner so the `bWorldInitHandled`
   guard + `NotAttempted` fallback never both spawn (would show as prefix
   count 2 on a correct reference — a wrong-reason FAIL the first run would
   expose immediately).
5. **Hardening option, only if the readable-fixture residual bites:**
   per-run randomization of the override pair (fixture picks values, computes
   the expected line at runtime). Deliberately NOT done now — it would break
   the "every expected substring is a verbatim source literal" MATRIX oracle
   and is out of proportion for the simple slate.

## Checklist state (docs/TASK-AUTHOR-GUIDE.md)

- [x] 1. Spec `task.md` (v2 front matter, behavior-only prompt, 5 anti-gaming
      notes with named defenses)
- [x] 2. Scaffold pair (`GraphMathActor.{h,cpp}` — tag + two editable ints,
      no behavior, `for task t1-blueprint-graph-on-beginplay` marker,
      behavior-only comments)
- [x] 3. Fixture pair (`GraphMathFunctionalTest.{h,cpp}` — base-class derive,
      no manual ticking, ASCII-only single-segment named assertions,
      pre-BeginPlay override)
- [ ] 4. Map binary + `docs/MAPS.md` row (authoring-lane run)
- [ ] 5. `cameras.json` (after the map exists)
- [ ] 6. Reference solution (MCP graph lane + `aids/author_reference.py`)
- [x] 7. Discrimination package (`MATRIX.md` with the §7 requirements table;
      no variants owed)
- [ ] 8. Gates: `cb lint`, `cb discriminate --wip`, `cb refgate`,
      `cb batch-eval --references all`
- [ ] 9. Commit + PR (`Source/CraftBenchTests/**` is review-gated on commit) +
      post-merge refgate close

> **RECONCILIATION 2026-08-11/12 (authoring-lane + graph-lane runs DONE).**
> Statements above about pending binaries / empty reference/ describe the
> authoring-time state and are now historical: binaries are committed
> (39433c2, 09781a8) and `cb refgate` graded this task's reference PASS
> from git HEAD. Remaining: the empty-FAIL discriminate leg.

- 2026-08-16 Q9 (DECISION-DIALOGUE-2026-08-16 Q9, D6): audited the prompt for the `BeginPlay` API-name leak the answer orders reworded - the prompt ALREADY reads "When gameplay begins for an instance of your Blueprint" / "at the moment gameplay begins" (behavior wording; verified at HEAD and back through git history - no committed version ever carried the token). Zero prompt characters changed, so no D6 replacement occurred and prior numbers remain VALID, not historical.

## Queued: ID RENAME (decision Q15) — the reason `prompt-jargon` was retired, not satisfied

**2026-08-17.** The `BeginPlay` reword of 2026-08-16 (decision Q9, a D6 contract
replacement) removed every prose instance from `## Prompt given to the agent`. The lint kept
firing, and the reason was NOT prose: the only surviving instance is this task's own **id**,
which the prompt necessarily shows as the required `Content/Tasks/<id>/` asset path.

That is exactly the leak decision Q15 approved renames for: *"the id becomes the agent-visible
`Content/Tasks/<id>/` path, so a mechanism-named id leaks the mechanism into the workspace the
agent is looking at."*

The `prompt-jargon` rule was retired on 2026-08-17 because it was unclearable by construction
(it asked a human to confirm a word) and parked this task in an OWNER-EYES verdict no task work
could clear. **Retiring the warning did not fix the leak — this note is where the obligation
lives now.** Requirements when it is done, in ONE batched commit:

- a new id naming the OUTCOME, not the mechanism, and neither equal to nor contained in any
  other id (decision Q15 rule 2; re-run the containment check over all 62 ids first);
- the task folder, its per-task UE folders (`Source/…/Tasks/<id>/`, `Content/Tasks/<id>/`,
  `Content/Maps/<id>/`), the fixture/grader names and every `<id>` string inside them;
- `tasks/CATALOG.md`, `docs/MAPS.md` rows, and anything else `cb lint`'s inventory checks;
- prior measurements become historical (D6: the task is replaced, not versioned);
- every certificate re-keys, so batch it with other grader/substrate work and re-gate once.
