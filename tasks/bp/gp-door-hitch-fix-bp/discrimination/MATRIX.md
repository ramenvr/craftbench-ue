# Discrimination matrix — gp-door-hitch-fix-bp

The self-validation oracle: the reference solution must PASS and the empty
leg must FAIL **at the predicted gate, via the named substring**. A
wrong-reason FAIL (L1 build failure, a different gate, a machine-fault
verdict) means the verifier is NOT discriminated — fix it, or relabel the
task for the weaker property it actually tests.

Per the amended checklist §7 (owner decision 2026-08-11) this package
ships **no hand-authored gaming variants**: the automatic reference-PASS /
empty-FAIL legs provide the non-vacuity bit, and the **requirements
table** below is the mandatory soundness artifact.

**This task's empty leg is special — it IS the shipped defect.** The
workdir overlay never wipes, so an empty submission runs the committed
BUGGY baseline: a door whose mid-swing re-`Interact` restarts the motion
driver from an endpoint, teleporting the mesh ~45 deg in one tick. The
empty leg therefore exercises the ENTIRE graded pipeline (map, fixture,
seam, monitor) and dies exactly at the gate the task exists to test.

## Parser traps this matrix is written against (inherited from the bp L2 set)

- **ONE parseable row-table**; the requirements table names no column
  "substring"/"message".
- **Every "Expected substring" cell is a backtick-wrapped literal with a
  space or `=`**, a verbatim contiguous span of ONE
  `FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
  `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-door-hitch-fix-bp/DoorHitchFunctionalTest.cpp`,
  never spanning a printf placeholder. ASCII-only (the cp1252 log
  read-back rule).
- **L2 substrings match the editor stdout captured in `out/l2_pie.log`**
  (the index.json verdict is authoritative for PASS/FAIL; the substring
  credits the REASON).
- **Error/machine-fault classes are never credited**: `PrepareTest: no
  UWorld`, `queued_never_started`, `rhi_unavailable`, EDITOR-GONE — no
  row below names them.

## Layout (folder-local; agent-writable prefixes only)

- Substrate baseline (committed, aid-authored via the product asset lane):
  `UE-projects/ThirdPerson/Content/Tasks/gp-door-hitch-fix-bp/BP_Door.uasset`
  — the BUGGY door (64,229 bytes; restart-from-endpoint wiring).
- Verifier map (committed, deny-listed path):
  `UE-projects/ThirdPerson/Content/Maps/gp-door-hitch-fix-bp/L_DoorHitch.umap`
  — one `BP_Door` instance tagged `HitchDoor` + the placed
  `ADoorHitchFunctionalTest`.
- `../reference/Content/Tasks/gp-door-hitch-fix-bp/BP_Door.uasset` — the
  FIXED door (65,101 bytes): the two exec routes moved from the
  restart pins to the resume pins (`notes.md` §2). Same asset path, so
  the overlay replaces the baseline.
- empty leg — run IMPLICITLY by `cb discriminate`: the untouched buggy
  baseline, as above.

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at (gate) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all seven checkpoints green; fixture finishes past cp6 |
| empty | FAIL | mid-swing continuity (cp6, monitor armed since cp0) | `mid-swing Interact teleported the door: a single-tick jump of ` | the buggy baseline PASSES the quiet/open/close-from-rest gates (its defect is mid-swing only — that is the point) and dies at THE gate with the teleport literal |

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal in
`DoorHitchFunctionalTest.cpp`; the gate name is the durable join key.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed door instance stays discoverable | fully | resolve gate — `Expected exactly one actor tagged 'HitchDoor' (the swinging door) in the running level; found ` | unconditional (first gate) | nothing; the TAG lives on the placed instance in the verifier-owned map — the agent's asset edit cannot remove it, but destroying/duplicating the actor at runtime could, and fails here |
| 2 | the door keeps a visible body | fully | surface gate — `The actor tagged 'HitchDoor' has no static-mesh part to observe - the door lost its visible body.` | door unresolvable (row 1) | mesh choice, component names, extra parts — all free (pose gates are per-part relative) |
| 3 | the `Interact` entry keeps its name and takes no parameters | fully | seam gate — `No parameterless reflected entry named 'Interact' on the door (the interaction contract is broken).` | rows 1–2 | a tolerated return value (the sprint-fixture parameter law) |
| 4 | the door stays still until `Interact` first fires | fully | quiet gate — `The door moved before any Interact fired: ` | rows 1–3 | up to 2 deg of settle jitter (disclosed tolerance) |
| 5 | opens from rest (~90 deg over ~1.5 s) | fully | opens gate — `The door did not open after Interact: displacement ` | rows 1–4 | any swing >= 45 deg by t=2.6 s — the envelope floors are deliberately generous |
| 6 | closes from rest (toggle semantics) | fully | closes gate — `The door did not return to closed after the second Interact: displacement ` | row 5 fans out | rest tolerance 10 deg |
| 7 | the reversal actually fires MID-swing (timing preserved) | fully | mid-swing gate — `The door was not visibly mid-swing when the reversal fired: displacement ` | rows 5–6 | timing latitude: anything >= 15 deg displaced at t=6.45 s |
| 8 | mid-swing `Interact` never teleports the door | fully, per-TICK | continuity gate — `mid-swing Interact teleported the door: a single-tick jump of ` (angle) / `mid-swing Interact teleported the door: a single-tick position jump of ` (translation) | rows 1–7 (prerequisites fan out first) | sub-12-deg/tick, sub-50-unit/tick motion — 4x above smooth-swing rates, 4x below the snap family |
| 9 | mid-swing `Interact` actually reverses (not suppressed/frozen) | fully | honored-reversal gate — `the mid-swing Interact was ignored: the door finished opening instead of returning - displacement ` | continuity gate fires first if both broken (owns the snap concept) | returning slower than the original swing is fine — only the final pose is gated |
| 10 | fix is IN PLACE (same asset, same folder) | fully, by the substrate model | not a gate — the map references `/Game/Tasks/gp-door-hitch-fix-bp/BP_Door`; a door authored anywhere else simply never runs | unconditional | nothing |

## Accepted residuals (documented, not defended)

- **The continuity monitor starts at the first Interact (cp0)**, so a
  cosmetic pre-quiet-window settle twitch under 2 deg is invisible.
  Deliberate: the graded concept is interaction-driven motion.
- **Reversal SPEED is unconstrained** (row 9): only continuity and the
  final pose are gated. A fix that reverses slowly but smoothly passes —
  behavior-only by design.
- **Extra runtime behavior is unconstrained**: sounds, particles, extra
  components, log lines — nothing gates them (the source row's sound clause
  was dropped by owner decision).
- **Mechanism-agnostic by basket law**: repairing the shipped machinery,
  rebuilding with interpolation, or any other route is indistinguishable
  to every gate.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/gp-door-hitch-fix-bp --wip
```

Per-leg fallback while iterating:

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/gp-door-hitch-fix-bp/task.md \
    --submission tasks/bp/gp-door-hitch-fix-bp/reference \
    --ue-root "$UE" --workdir C:\cb\wd\doorhitch-ref    # expect exit 0
```

## Status

- Authored 2026-08-12. Fixture C++ committed-track (built clean, 91 s
  UBT); baseline + reference + map authored via the MCP editor lane the
  same day (the repo's FIRST live `AuraTimelineStatics` end-to-end
  timeline authoring — pin-name catch: the resume-from-end pin is
  `ReverseFromEnd`, not the doc's "ReverseFromStart"), sandbox-promoted,
  graph read-back verified.
- **Validation legs run 2026-08-12 (`--substrate-from-live`, first live
  runs of the fixture): the oracle held exactly.**
  - reference: **PASS** (L1 208.3 s; L2 39.7 s, tests=1/1, "All
    checkpoints sampled").
  - empty (= the buggy baseline): **FAIL** at the continuity gate with
    the credited literal — measured `a single-tick jump of 46.5 deg
    (limit 12.0) at t=6.45s` (the calibration table predicted ~45 deg at
    the reversal instant); L1 PASS and every rest-behavior gate green
    first, exactly the targeted-debug shape.
- **Refgate (certified, from git HEAD): PASS, 191 s** (2026-08-12,
  commit cbd9572 — fixture + baseline + map + reference all survive
  the checkout seam). The empty-FAIL leg rides the next
  `cb discriminate` sweep; the camera plan rides with it.
