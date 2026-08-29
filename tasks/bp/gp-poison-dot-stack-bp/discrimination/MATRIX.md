# gp-poison-dot-stack-bp -- discrimination matrix

> **PARSE REPAIR 2026-08-09 (read this before editing the tables below).**
> `aura_rig.discriminate.parse_matrix` keys rows by their FIRST-COLUMN label and
> **LAST ROW WINS across every markdown table in the file**. This file used to
> carry a second table (the "Scoreboard") whose first column repeated
> `../reference`, `empty`, `bp-no-health-system/` ... -- and because that table
> has no Overall and no message column, it silently re-registered all seven rows
> with `expect_pass=False` and an EMPTY substring tuple. Measured before the
> repair: 7 rows parsed, every one with `substrings=()`, and `reference` parsed
> as `expect_pass=False`. `cb discriminate` was therefore crediting every leg on
> exit code alone. Same failure class as the documented
> `t1-third-person-chase-camera` precedent. **The scoreboard is now a bullet
> list, not a table.** There must be exactly ONE markdown table in this file: the
> `## Matrix` table. Do not add a second one.

> **REDEFINITION EPOCH 2026-08-05 (health-first two-stage restructure) --
> RE-VALIDATION RESOLVED 2026-08-06 at `dfee504`, for the reference and one
> variant.** The binary `.uasset`s were ported to ThirdPerson **headlessly** (no
> live editor was ever needed -- see `../REFERENCE-NOTE.md`), and at that commit
> `../reference` measured **overall PASS** (stage 1 + Legs A/C/D green, L2I 4/4)
> and the NEW `bp-no-health-system/` measured **FAIL at the named stage-1
> presence gate**. `--wip` is no longer needed for those two rows -- their assets
> are committed, so the ladder grades from git HEAD.
>
> **Still open:** `bp-no-refresh/` and `bp-no-cap/` do not exist on disk
> (verified 2026-08-08 -- `discrimination/` holds only `bp-no-health-system/`,
> `cpp-solve/`, `cpp-solve-with-bp/`, and this file), and
> `cpp-solve-with-bp/`'s binaries were **left behind by the port** (see its row
> note). Neither remaining item needs an editor: `dfee504`'s headless recipe is
> the lane.
>
> _History (what this banner used to block on):_ two changes shared the
> 2026-08-05 date -- (1) the ThirdPerson substrate migration; (2) the
> health-first restructure, in which stage 1 (build the health system) became
> the agent's work, the task base pawn (`ACraftBenchBareCharacter`, abstract,
> ASC-only) ships with NO attribute set, and checkpoint 0 is the stage-1 gate
> (derivation + presence + init-to-100 + a 37 != 100 write probe). The C++
> discrimination overlays (`cpp-solve*/Source/`) gained the stage-1 build so
> they still isolate the L2I axis (L2 PASS, L2I FAIL). Results before/after
> 2026-08-05 remain not comparable (same convention as glide's 2026-08-04
> redefinition); the 2026-07-17 stamps below predate both changes. **A third
> epoch stacked 2026-08-06**: the Leg C/D redefinition (refresh + cap became
> gates on a 16-checkpoint schedule -- see `../task.md`'s resolved correction
> block); the fixture pair stayed byte-identical across substrates.

VALIDATED on a live runner 2026-07-17 (Windows + UE 5.8, pre-epoch): `cb
discriminate --task gp-poison-dot-stack-bp` = **1/1** -- `../reference` PASS,
empty FAIL, `cpp-solve/` FAIL at the named L2I `bp_pawn_present` check. The
L2 legs + gates are identical to `gp-poison-dot-stack-cpp`; the discrimination
axes here are the **L2-introspect "deliverable is Blueprint" gate** and (since
2026-08-05) the shared **stage-1 gate**.

RE-VALIDATED at HEAD on ThirdPerson 2026-08-06 (`dfee504`) for **two** rows --
`../reference` PASS and `bp-no-health-system/` FAIL-by-name. The other rows
still carry pre-migration stamps or are unbuilt; the per-row Status column and
the scoreboard at the bottom of this file say which is which. Do not read the
2026-07-17 "1/1" as a current whole-matrix result.

## Matrix

| Submission | Overall | Fails at | Expected message | Status (evidence) |
|---|---|---|---|---|
| `../reference` | **PASS** | -- | all L2 gates green (incl. the stage-1 gate) plus all L2I checks pass, L2I 4/4 | **MEASURED at HEAD 2026-08-06 (`dfee504`)** -- stage 1 rides DefaultStartingData into DT_HealthInit |
| empty (no overlay -> base scaffold) | **FAIL** | L2 cp0 gate (a), derivation | `does not derive from the provided task base pawn (CraftBenchBareCharacter)` | **NOT re-run since the 2026-08-05 epoch.** The substring is read off the fixture source (PoisonStackFunctionalTest.cpp lines 82-87), not off a recorded log; the pre-epoch run recorded the retired granted=0 message instead |
| `bp-no-health-system/` | **FAIL** | L2 cp0 gate (b), presence | `stage 1 not built: the pawn's health attribute system is absent - the ASC has no attribute set exposing Health` | **MEASURED at HEAD 2026-08-06 (`dfee504`).** One-delta confirmed by byte scan 2026-08-08: its BP pawn carries CraftBenchBareCharacter and SKM_Manny_Simple, so gates (a) and (e) pass, and carries no DefaultStartingData, DT_HealthInit or CraftBenchAttributeSet, so gate (b) is the first and only gate it can trip |
| `bp-no-refresh/` | **FAIL** | L2 Leg C refresh gate (new 2026-08-06) | `re-application did not refresh the duration: after a mid-window re-apply (trigger+3.6) the drain was already over before the refreshed expiry` | **UNAUTHORED -- absent from disk (verified 2026-08-08), never run on this task.** Planned as the reference BP GE with Duration Refresh Policy set to Never Refresh; the BP twin of the C++ original's `no-refresh/`, which IS proven on the byte-identical fixture logic. No editor session is required -- `dfee504` proved the headless authoring lane |
| `bp-no-cap/` | **FAIL** | L2 Leg D cap gate (new 2026-08-06) | `stack cap violated (or scaling is not ~proportional): 4 applications drained` | **UNAUTHORED -- absent from disk (verified 2026-08-08), never run on this task.** Planned as the reference BP GE with Stack Limit Count set to 0; the BP twin of the C++ original's `no-cap/`, whose measured 4.00x pinned the 3.5x bar. Same headless lane as above |
| `cpp-solve/` | **FAIL** | L2I `bp_pawn_present` | `"id": "bp_pawn_present", "passed": false` | **MEASURED 2026-07-17, pre-migration; NOT re-run at HEAD.** L2 PASSes (the C++ pawn builds stage 1 correctly), isolating the deliverable-format axis |
| `cpp-solve-with-bp/` | **FAIL** | L2I `resolved_pawn_is_blueprint` | `"id": "resolved_pawn_is_blueprint", "passed": false` | **NEVER measured on this task**, and its binaries were left unported by `dfee504` -- see the note below. The AGENT-authored native pawn is what must be detected; the committed abstract task base is exempted by exact /Script/ path and must NOT trip this check |

> **`cpp-solve-with-bp/` is NOT YET MEASURED on this task, and its binaries
> were left behind by the 2026-08-06 port.** The variant and the
> `resolved_pawn_is_blueprint` check are ported from `gp-glide-stamina-bp`,
> where the same decoy was measured PASS->FAIL on UE 5.8 (2026-08-03) -- but on
> the **CraftBenchTemplate** substrate, before the migration. `dfee504` ported
> the reference binaries only; byte-verified on disk 2026-08-08, all three
> `cpp-solve-with-bp/Content/Tasks/gp-poison-dot-stack-bp/*.uasset` still carry
> `/Script/CraftBenchTemplate` references and zero `ThirdPerson` ones, and none
> derives from `CraftBenchBareCharacter` (so the decoy also predates the
> health-first restructure). The row's **verdict** (FAIL) is safe; the **gate**
> is not -- the L2I chain runs `bp_pawn_present` before
> `resolved_pawn_is_blueprint`, so an unloadable BP would fail at the wrong,
> non-isolating gate. Sequence to close it: re-run the offline oracle
> (`tools/verify-single/tests/test_introspect_bp_variant_resolution.py`) after
> the 2026-08-05 staged script change (the abstract-base exemption), re-port
> these three binaries with `dfee504`'s headless recipe, THEN run
> `cb discriminate --task gp-poison-dot-stack-bp` to promote the row to
> measured.

## Named-substring provenance (every cell above, traced to source)

Each Expected-message cell holds **exactly one** backticked literal, and that
literal is a verbatim run of characters -- never a run that spans a `%s` /
`%.1f` / `%.2f` placeholder, which cannot match at runtime. Verified 2026-08-09
by reading the sources below with the string-literal concatenation collapsed:

- `does not derive from the provided task base pawn (CraftBenchBareCharacter)`
  -- `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/PoisonStackFunctionalTest.cpp`
  lines 82-87. The full message opens `stage 1 not built: the graded pawn (%s)`,
  so the head of that sentence is NOT usable; the literal starts after the `%s`.
- `stage 1 not built: the pawn's health attribute system is absent - the ASC has no attribute set exposing Health`
  -- same file, lines 99-102. Placeholder-free message; the literal is its head.
  Note the ASCII hyphen-minus, not an en dash -- the UE log is written UTF-8 and
  read back cp1252, so a non-ASCII character would arrive as mojibake and the
  substring test would silently miss.
- `re-application did not refresh the duration: after a mid-window re-apply (trigger+3.6) the drain was already over before the refreshed expiry`
  -- same file, lines 289-293. The literal stops immediately before `(CPost1=%.1f`.
- `stack cap violated (or scaling is not ~proportional): 4 applications drained`
  -- same file, lines 323-327. The literal stops immediately before `%.2fx`.
  The recorded value `4.00x` from the C++ twin is a VALUE, not a literal, and is
  deliberately not part of the substring.
- `"id": "bp_pawn_present", "passed": false` and
  `"id": "resolved_pawn_is_blueprint", "passed": false`
  -- `tools/verify-single/introspect/gp_poison_dot_stack_bp.py`, `check()` +
  `emit()`. The verdict block is `json.dumps` with default separators, so these
  are literal runs of the emitted JSON line that lands in the L2I log.

**Substrings are unique per leg, and no two legs die at the same gate.** `empty`
and `bp-no-health-system/` both die inside checkpoint 0, but at different
sub-gates -- (a) derivation vs (b) presence -- with different messages, so the
two are still distinguishable by name. Every other leg dies at a different gate
entirely.

**Authoring hazard for the two unauthored variants:** stage-1 gate (e) (the
visible-character gate) fires at checkpoint 0, BEFORE any Leg C/D gate. A
`bp-no-refresh/` or `bp-no-cap/` pawn authored without an assigned mesh would
FAIL at `the character is not visibly represented` instead of its intended gate,
and `cb discriminate` would correctly report `wrong-reason`. Author them as
one-flag deltas off `../reference` so the mesh comes along.

## Deterministic gates (what flips PASS/FAIL)

- **L2 stage-1 gate (checkpoint 0, NEW as a task gate 2026-08-05, all named
  FAILs)**: (a) pawn derives from the task base; (b) ASC carries Health; (c)
  Health reads 100 BEFORE any fixture write; (d) write-then-read at 37 (!= 100
  so an inert-write set that inits at 100 cannot pass vacuously); (e) the pawn
  is visibly represented by a mesh component with a mesh assigned (added
  2026-08-06, owner decision, shared across the glide/poison family).
- **L2 stage-2 (inherited; extended at the 2026-08-06 Leg C/D epoch)**:
  granted+activated, periodic steps, band-calibrated stop check, **Leg C
  refresh gate** (both directions named), stacking-scales-rate, **Leg D cap
  gate** (RateB/Rate1 <= 3.5; uncapped measures 4.00x).

  > **Correction (2026-08-03) -- RESOLVED 2026-08-06:** duration refresh and
  > the stack cap are now real gates (Legs C/D, 16-checkpoint schedule). See
  > `../task.md` section "Verifier specification" for the resolved block and the
  > C++ original's cap note for the congruent-window measurement argument.
- **L2I (the `-bp` axis)**: `task_folder_exists` -> `bp_pawn_present` ->
  `bp_pawn_grants_bp_ability` -> `resolved_pawn_is_blueprint` (no AGENT-authored
  native subclass; the committed abstract stage-1 base is exempted by exact
  path -- staged script change 2026-08-05).

## Anti-gaming modes (defended by the gates)

1. Skip stage 1 / dodge via generic-parent BP / inert init-write fakes -> the
   L2 stage-1 gate (a)-(d).
2. Solve in C++ (the `cpp-solve/` variant) -> **L2I `bp_pawn_present`**.
3. BP shell + real C++ solve (`cpp-solve-with-bp/`) -> **L2I
   `resolved_pawn_is_blueprint`**.
4. All original stage-2 gaming modes -> the inherited L2 gates, now including
   **no-refresh -> Leg C** and **no-cap -> Leg D** (2026-08-06).

## Bounded coverage

`cpp-solve/` and `cpp-solve-with-bp/` are the load-bearing format variants;
`bp-no-health-system/`, `bp-no-refresh/`, and `bp-no-cap/` are the behavioral
discriminators (each C++ twin is proven on the byte-identical fixture logic --
`no-health-system/` probe-proven 2026-08-05, `no-refresh/` + `no-cap/` graded
2026-08-06). The remaining inherited stage-2 gaming modes are argued from the
original task's validated matrix, not re-run per variant.

## Scoreboard as of 2026-08-09 (2 of 7 rows measured at HEAD)

Deliberately a BULLET LIST, not a table -- a second markdown table whose first
column repeats these labels silently overwrites the `## Matrix` rows above (see
the PARSE REPAIR banner at the top of this file).

- reference (`../reference`) -- on disk: yes, 4 assets. Measured at HEAD: **yes,
  `dfee504`**. Missing: nothing.
- empty stub -- on disk: n/a, the runner creates a throwaway dir. Measured at
  HEAD: no; the 2026-08-05 epoch changed its message and it has not been re-run.
  Missing: a run.
- no-health-system variant (`bp-no-health-system/`) -- on disk: yes, 3 assets.
  Measured at HEAD: **yes, `dfee504`**. Missing: nothing.
- no-refresh variant (`bp-no-refresh/`) -- on disk: **no**. Measured at HEAD:
  no. Missing: headless authoring, one GE flag off the reference, then a run.
- no-cap variant (`bp-no-cap/`) -- on disk: **no**. Measured at HEAD: no.
  Missing: headless authoring, one GE flag off the reference, then a run.
- cpp-solve variant (`cpp-solve/`) -- on disk: yes, C++ only. Measured at HEAD:
  no; the 2026-07-17 stamp is pre-migration. Missing: a run.
- cpp-solve-with-bp variant (`cpp-solve-with-bp/`) -- on disk: yes, but the
  **binaries are unported**. Measured at HEAD: no, never measured on this task
  at all. Missing: a re-port plus a run.

Because `bp-no-refresh/` and `bp-no-cap/` are absent from disk,
`discriminate.discover_variants` emits no leg for them: their rows above are
documentary until the folders exist. The other five rows are live legs.

The word "PENDING" no longer appears in this file for anything an editor
session gates: `dfee504` proved every remaining item is reachable headlessly.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every L2 token is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` literal in `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/PoisonStackFunctionalTest.cpp`, except the row-16 visibility literal, which lives in the shared base `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp` (`PawnVisiblyRepresented`, hoisted 2026-08-11); every L2I token is a verbatim run of the `json.dumps` verdict line emitted by `tools/verify-single/introspect/gp_poison_dot_stack_bp.py`. No token spans a printf placeholder; all are ASCII (the cp1252 log read-back rule). First-column labels are bare numerals and no column is named "substring"/"message" — the parse-safe shape the door-hitch exemplar established (this file's PARSE REPAIR "exactly ONE table" sentence must be amended to "one SUBMISSION-ROW table" when this section lands). Global skip: an L1 build FAIL short-circuits both the L2 and L2I legs; inside L2, any `FinishTest` ends the test, so every later gate in the chain below is skipped by any earlier one firing.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the pawn is a subclass of the provided TASK character, not the generic one | fully | L2 cp0 gate (a), derivation — `does not derive from the provided task base` (the full emitted message continues "pawn (CraftBenchBareCharacter)…" from the next concatenated C++ string segment; the quoted span stays inside one segment) | the pawn never resolves/spawns (per-checkpoint guards `pawn did not spawn/resolve` / `pawn has no AbilitySystemComponent` fire first) | nothing on lineage; the class NAME is free (identity is by derivation, never by name) — an empty submission resolves to the generic scaffold pawn and dies here |
| 2 | the pawn is authored as a BLUEPRINT and IS the pawn L2 grades (no native decoy) | fully | L2I — `"id": "bp_pawn_present", "passed": false` + `"id": "resolved_pawn_is_blueprint", "passed": false` | never within L2I (both sweeps fail CLOSED on API breakage; dependent checks auto-FAIL, they do not skip); the whole L2I leg runs only after L1 | nothing structural: the committed ABSTRACT task base is exempt by exact /Script/ThirdPerson.CraftBenchBareCharacter path (composed, not a verdict-line literal: `"/Script/%s.CraftBenchBareCharacter" % SCAFFOLD_MODULE` with `SCAFFOLD_MODULE = "ThirdPerson"`, gp_poison_dot_stack_bp.py:79/:68) and the L2 resolver skips CLASS_Abstract, so it can never be the decoy |
| 3 | stage 1: a Health attribute exposed through the pawn's ability system, via the attribute set type the project provides | fully | L2 cp0 gate (b), presence — `the pawn's health attribute system is absent` (`HasAttributeSetForAttribute` on the CONTRACT set's Health FProperty) | row 1's gate (a) fires first | a Blueprint or C++ SUBCLASS of the contract attribute set still exposes the contract Health FProperty and passes — the type family, not the exact class, is what is pinned |
| 4 | Health initialized to 100 | fully | L2 cp0 gate (c), init read BEFORE any fixture write — `stage 1 incomplete: Health must initialize to ` | gates (a)-(b) fire first | +/-0.5 tolerance (`BaselineEpsilon`); an init route of any kind (data table, init GE, class defaults) — the route is unobserved, only the read |
| 5 | Health readable AND writable through the standard attribute APIs | fully | L2 cp0 gate (d), write-then-read at 37 (!= 100 on purpose) — `health attribute is inert, write-then-read failed` | gates (a)-(c) fire first | nothing: an inert-write set that inits at 100 cannot pass vacuously (the probe value differs from the init value); +/-0.5 read-back tolerance |
| 6 | stage 1 wired and initialized IN THE EDITOR, not in C++ | partially | no direct gate — enforced only via the native-class sweeps of rows 2/19/20 | n/a | building stage 1 by EDITING committed C++ (e.g. registering the attribute set inside `CraftBenchBareCharacter.cpp` — a modified base keeps its exempted `/Script/` path) evades every sweep; there is no diff-vs-HEAD check (documented proportionate-on-purpose, owner steer 2026-08-11) |
| 7 | an ability tagged `Ability.Poison` is in the pawn's granted abilities (poison applyable by that tag) | fully | L2 final assert — `no activatable ability tagged Ability.Poison on the pawn` (gates on `Granted < 1`, cpp:234, where `Granted` comes from `NumGrantedAbilitiesWithTag(PoisonTag)`, cpp:212) | any checkpoint gate FinishTest'd earlier (final asserts run only after checkpoint 15 of 16) | extra unrelated abilities — `>= 1` is the bar; how the ability is authored beyond the tag is free |
| 8 | the tagged ability actually activates when applied by tag | fully | L2 final assert — `an ability tagged Ability.Poison was granted but did NOT activate on TryActivateAbilitiesByTag` | row 7's gate fires first | nothing — activation is observed on the fixture's own `TriggerAbilityByTag` calls |
| 9 | Health drops repeatedly — about once per second — not a single hit | fully (banded) | L2 Leg A periodic gate — `poison was not periodic: Health did not keep dropping in steps` (samples at trigger+1.1/+2.6/+4.1; each ~1.5 s window needs a drop >= `PeriodicMinStep`) | rows 7-8 fire first | any period fast enough to land >= 1 tick in each 1.5 s sample window — 0.4 s and 1.4 s periods both read as "about once per second" |
| 10 | the drain stops after roughly five seconds (not a drain that never ends) | fully (banded) | L2 Leg A stop gate — `poison did not STOP after its duration` (stable in (trigger+7.1, trigger+9.2], PAST the band top) | rows 7-9 fire first | any duration inside the deliberate ~4-7 s acceptance band; jitter under `StopEpsilon` in the stop window |
| 11 | each new application refreshes the duration (~5 s from the MOST RECENT application) | fully | L2 Leg C refresh gate, direction 1 — `re-application did not refresh the duration` (drain must continue in (CStart+7.2, CStart+8.7], past the UN-refreshed band top) | rows 7-10 fire first | refresh is probed at exactly ONE re-apply instant (trigger+3.6); refresh semantics at other phases are argued, not sampled |
| 12 | the refreshed poison still expires | fully | L2 Leg C refresh gate, direction 2 — `refreshed poison never expired` (stable in (re-apply+7.1, re-apply+9.2]) | rows 7-11 fire first | nothing beyond `StopEpsilon` jitter — a "refresh" that never ends fails here by name |
| 13 | more active stacks drain proportionally faster (three stacks ~= three times one stack's per-second loss) | fully (banded) | L2 Leg B ratio lower bound — `stacking did not scale the drain rate` (RateB/Rate1 >= 2.0 over CONGRUENT 4.1 s windows) | rows 7-12 fire first | sub-proportional scaling down to 2.0x; the exact 3x value is logged ADVISORY, only the [2.0, 3.5] band is gated |
| 14 | a fourth application must NOT exceed three stacks (cap of 3) | fully (banded, via the same ratio) | L2 Leg D ratio upper bound — `stack cap violated (or scaling is not ~proportional): 4 applications drained ` (RateB/Rate1 <= 3.5; honest uncapped measures ~4.00x) | rows 7-13 fire first | the stack COUNT is never read directly — any config whose 4-app/1-app rate ratio lands <= 3.5 passes, including a cap implemented as a rate clamp rather than a stack limit |
| 15 | each application adds ONE stack (2- and 3-stack intermediate behavior) | **NOT ASSERTED** | none — the fixture samples only the 1-application rate (Leg A) and the 4-application rate (Leg B/D); no 2- or 3-application leg exists | n/a | a GE that jumps straight to 3 stacks on the second application (or any other intermediate-count behavior) passes Legs B/D unchanged |
| 16 | the character is visibly represented (a reviewer watching the run can see it) | fully | L2 cp0 gate (e) — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (base-class `PawnVisiblyRepresented`; sibling literals also reject hidden-in-game and ~zero-scale meshes) | gates (a)-(d) fire first | mesh type, asset path and size are deliberately NOT asserted — only "a mesh, assigned, rendering, at a real size" |
| 17 | the mesh is one of the provided mannequin skeletal meshes under `/Game/Characters/` | **NOT ASSERTED** | none — row 16's gate deliberately asserts no asset path or mesh type (stated in the base-class comment) | n/a | a visible static CUBE (or any non-mannequin mesh) satisfies row 16 and nothing checks the `/Game/Characters/` provenance the prompt names |
| 18 | the solution is delivered entirely as assets saved under `Content/Tasks/gp-poison-dot-stack-bp/` | partially | L2I — `"id": "task_folder_exists", "passed": false` (folder exists, >= 1 asset) + `bp_pawn_present` scans ONLY that folder for the pawn | L2I runs only after L1; within L2I the checks always emit | only the PAWN is pinned to the folder: the granted ability's class path needs only a `/Game/` prefix (any sandbox-accepted asset folder works, e.g. `Content/Blueprints/`) and the GameplayEffect's location is never checked at all |
| 19 | the granted ability is Blueprint-authored (no C++ ability) | fully (for class-defaults grants) | L2I — `"id": "bp_pawn_grants_bp_ability", "passed": false` (>= 1 `/Game/` entry AND zero `/Script/` entries in the CDO's GrantedAbilities) | auto-FAILs (never skips) when no BP pawn resolved | the check reads the CLASS-DEFAULTS array only — a native ability granted at RUNTIME from the BP graph (`GiveAbility` in BeginPlay) is invisible to it, and a native `UGameplayAbility` subclass is outside every sweep (see row 21) |
| 20 | the GameplayEffect is Blueprint-authored (the graded behavior — period, duration, modifier, stacking, cap, refresh — is not C++) | fully (for GE subclasses) | L2I — `"id": "effect_is_blueprint", "passed": false` (native `UGameplayEffect` sweep, fail-closed, conjoined with BP-pawn presence so an empty submission cannot score it vacuously) | never skips; L2I after L1 | nothing via a `UGameplayEffect` subclass — but behavior moved into a native ability/task body (row 19/21) is not a GE subclass and evades this sweep |
| 21 | "Do not add or modify any C++ source for this task" | partially | the three L2I native sweeps only: native pawn subclasses (row 2), native GrantedAbilities CDO entries (row 19), native GE subclasses (row 20) | n/a | native classes OUTSIDE the swept families (a runtime-granted native `UGameplayAbility`, a native `UAttributeSet` subclass, helper actors/components) and EDITS to committed sources all compile in L1 and pass every sweep — there is deliberately no submission-wide diff-vs-HEAD (owner steer 2026-08-11: "one more reflection sweep, not heavy machinery") |
