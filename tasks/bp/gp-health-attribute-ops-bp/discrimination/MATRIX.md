# gp-health-attribute-ops-bp -- discrimination matrix

> ## STATUS: **MEASURED + CERTIFIED 2026-08-11 — `cb discriminate` = YES 7/7, live AND `substrate=HEAD`.**
>
> **Certified verdict:** with the whole package committed, `decide_from_live`
> selected `substrate=HEAD` and the family credited **7/7** — the git-HEAD
> certification. This family credited 7/7 on every run it appeared in
> (live sweep, a concurrent-contention re-run, and the HEAD sweep).
>
> Reference **PASS**; `empty`, `bp-generic-pawn`, `bp-no-health-system`,
> `bp-no-mesh`, `cpp-solve`, `cpp-solve-with-bp` each **FAIL credited at its
> named substring** (the `[ok]` credit requires the row's expected message to
> appear, not just the exit code). Run was `substrate=live` — chosen by
> `decide_from_live` because the variant assets were not yet committed, and
> live == HEAD in content for everything graded (fixture, maps, C++ all clean
> at `9cdbd6a`). The reference itself additionally holds a from-git-HEAD PASS
> from the same day (see `../REFERENCE-NOTE.md`). Variant `.uasset`s were
> authored headlessly from pristine reference copies via
> `../../_shared/author_bp_variant.py` (one delta per boot, byte-verified).
> Re-run certified-from-HEAD after these dirs are committed; the historical
> prediction banner is kept below because every prediction it made was
> confirmed by the run.
>
> _Historical (pre-run) banner:_ **UNVALIDATED / NOT YET RUN.** Every row below is a PREDICTION.
>
> Nothing in this package has been compiled, launched in PIE, graded, or swept.
> No build, no UBT, no `run_task.py`, no `cb discriminate`, no editor, no test
> suite. Every "Overall" and every "Expected message" cell was derived
> STATICALLY, by reading three things on disk:
>
> 1. the SHARED L2 fixture
>    `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/HealthAttributeOpsFunctionalTest.cpp`
>    (byte-identical for the `-cpp` original and this `-bp` twin -- the folder is
>    deliberately unsuffixed, exactly as the glide/poison pairs do it);
> 2. the committed `-cpp` reference,
>    `../../gp-health-attribute-ops-cpp/reference/Source/ThirdPerson/`, which is
>    what both C++ decoys here ARE, verbatim;
> 3. the two shipped `-bp` twins -- `gp-glide-stamina-bp` and
>    `gp-poison-dot-stack-bp` -- and their introspect scripts under
>    `tools/verify-single/introspect/`.
>
> **Do not cite any row here as measured discrimination.** The commands that
> promote a row from UNVALIDATED to MEASURED are in **Re-validate**, at the
> bottom, and they are blocked -- see **Blockers**.

> ## ~~BLOCKED ON ASSET AUTHORING~~ — RESOLVED 2026-08-11
>
> Every asset named below now exists on disk and every row has RUN (see the
> STATUS banner). The reference landed at commit `e270322`; the `bp-*` variant
> assets and the `cpp-solve-with-bp` BP half were authored 2026-08-11 and are
> committed alongside this banner edit. The original text is kept for the
> record:
>
> A `.uasset` cannot be authored outside a live editor, so every row whose
> submission contains Blueprint content is **documentary only** until the serial
> asset pass runs. Those rows are:
>
> - `../reference` -- the BP deliverable itself does not exist on disk.
> - `cpp-solve-with-bp/` -- its C++ half IS committed here (verbatim, 10 files);
>   its Blueprint half is not. **In its current on-disk state this directory is
>   byte-identical to `cpp-solve/`**, so running it today would reproduce
>   `cpp-solve/`'s verdict at `bp_pawn_present` and prove nothing about the axis
>   it exists for. Do not run it before the assets land.
> - every `bp-*` row -- none of those directories exists on disk at all, so
>   `discriminate.discover_variants` emits no leg for them.
>
> Only `cpp-solve/` and the `empty` stub are complete, runnable legs today, and
> neither has been run.

> ## MATRIX LAYOUT LAW (read before editing this file)
>
> `aura_rig.discriminate.parse_matrix` keys rows by their **FIRST CELL** and
> **LAST ROW WINS across every markdown table in the file**. A later table that
> repeats a leg name in column 1 silently re-registers that leg -- with an empty
> substring tuple if the table has no message column -- and `cb discriminate`
> then credits the leg on its exit code alone. That has happened twice in this
> repo (`t1-third-person-chase-camera`, then `gp-poison-dot-stack-bp`, repaired
> 2026-08-09).
>
> **There is exactly ONE markdown table in this file: the `## Matrix` table.**
> Everything else is a bullet list on purpose. Do not add a second table, and do
> not put a leg name or any string containing a `/` in a first column anywhere.
> This file was parsed with the real parser before it was committed -- see
> **Parser self-check**.

---

## What this package is, and what a `-bp` twin costs

This twin SHARES the `-cpp` original's L2 fixture and its committed `.umap`;
nothing new is needed on either. The deltas are exactly three:

- the prompt mandates a **Blueprint** deliverable under
  `/Game/Tasks/gp-health-attribute-ops-bp/` (the documented deliverable-format
  exception to behavior-only prompts -- measuring the BP authoring path IS the
  point of the variant);
- an **L2I introspect leg** structurally asserts the deliverable really IS
  Blueprint;
- **C++ decoy variants** that try to defeat that leg. Those decoys are what this
  package contains.

Both decoys are the `-cpp` reference's C++ **verbatim** -- `diff -rq` against
`../../gp-health-attribute-ops-cpp/reference/Source/ThirdPerson/` is empty for
both, all 10 files. That is not tidiness: a decoy that differed behaviourally
would make an L2 failure attributable to the difference rather than to the
decoy, and the whole point of `cpp-solve/` is that **L2 passes**.

## The false PASS this matrix inherits -- MEASURED on `gp-glide-stamina-bp`

`cpp-solve-with-bp/` is not a hypothetical. On `gp-glide-stamina-bp` the same
decoy -- that task's C++ reference shipped ALONGSIDE its conforming Blueprint
deliverable -- was **measured** on UE 5.8 (2026-08-03, on the CraftBenchTemplate
substrate, two days before the ThirdPerson migration), before and after the gate
that catches it existed:

- **before** (3 L2I checks): L1 PASS, L2 PASS 1/1, L2I **PASS 3/3**, overall
  **PASS**. That is the false pass, on a submission whose prompt says the
  deliverable must be a Blueprint.
- **after** (4 L2I checks): L1 PASS, L2 PASS 1/1, L2I **FAIL 3/4**, overall
  **FAIL**.

The mechanism is `ResolveAgentPawnClass` (`CraftBenchPawnFunctionalTest.cpp`,
both substrates carry the identical port): it enumerates **native** candidates
BEFORE Blueprint ones, so the C++ pawn wins resolution. **L2 grades the C++
solve while L2I grades the Blueprint** -- every gate green. The first three L2I
checks are pure EXISTENCE checks; they prove a conforming Blueprint is present,
never that it is the pawn L2 actually graded. Only `resolved_pawn_is_blueprint`
asks that question.

The same trap applies here unchanged, and for the same reason: this task's
`PreferredAbilityTag()` is `Ability.Damage`, both a native and a Blueprint pawn
can carry it, and natives are enumerated first.

## THE L2I CHECK NAMES: reconciled against `../task.md`, NOT against a script

`tools/verify-single/introspect/gp_health_attribute_ops_bp.py` ~~does not exist
on disk yet~~ (**it does now — committed 2026-08-10 and it graded the 2026-08-11
runs; the reconciliation below was performed while it was still unwritten and
its five check names all match the shipped script**). The two L2I substrings recorded below were
first quoted from the shipped `gp_glide_stamina_bp.py`, then **reconciled
against `../task.md`'s "L2-introspect" block**, which specifies five checks by
name and matches:

- `task_folder_exists`
- `bp_pawn_present` -- derivation from the TASK base `ACraftBenchBareCharacter`
  here (not the generic scaffold), so L2I and L2's HO-1 agree on what "the
  deliverable" is
- `bp_pawn_grants_bp_ability` -- `>= 2` distinct Blueprint-generated ability
  classes AND **zero** native ones
- `resolved_pawn_is_blueprint`
- `pawn_visibly_represented`

`../task.md` also states the script emits **all five checks on every leg,
reached or not**, which is exactly the property the two rows below depend on: a
substring naming a later check still matches when an earlier one also failed.

**This is a spec-to-spec reconciliation, not a verification.** If the script as
written names a check anything else, the two L2I rows below become wrong-reason
FAILs, not discrimination wins. Re-check both substrings against the script
itself the moment it lands, BEFORE running the sweep.

One consequence worth stating for `cpp-solve-with-bp/`: `bp_pawn_grants_bp_ability`
reads the **Blueprint pawn's** granted-abilities array, not the C++ pawn's, so a
Blueprint half copied verbatim from the reference (2 BP abilities, 0 native
entries) satisfies it and the leg still lands on `resolved_pawn_is_blueprint`,
which is the axis it exists for.

---

## Matrix

Each "Expected message" cell carries **exactly one** backticked literal, because
`_extract_substrings` returns every substantive backticked span and `grade_leg`
requires **ALL** of them to appear in the concatenated L2 + L2I log. Each
literal is either

- a verbatim **literal run** of a real `FinishTest(EFunctionalTestResult::Failed,
  ...)` message in the shared fixture -- never a run that spans a `%.1f` / `%.2f`
  / `%d` / `%s` placeholder, which can never match at runtime (`granted=` is
  matchable; `granted=0` is not); or
- a verbatim run of the L2I verdict JSON line (`json.dumps` with default
  separators, so `"id": "x", "passed": false` is a literal run of it).

Predicted numbers are deliberately kept OUTSIDE backticks and live in the last
column: a human-readable summary inside a substring cell can never match and
would read as a wrong-reason FAIL.

| Submission | Overall | Fails at | Expected message | Status |
|---|---|---|---|---|
| `../reference` | **PASS** | -- | all eleven L2 gates green plus every L2I check passing | **MEASURED 2026-08-11: ran, PASS** (from-git-HEAD PASS same day, see `../REFERENCE-NOTE.md`; was: blocked on asset authoring) |
| empty (no overlay -> generic scaffold pawn) | **FAIL** | L2 cp0, HO-1 derivation | `does not derive from the provided task base pawn (CraftBenchBareCharacter).` | **MEASURED 2026-08-11: ran, credited at its named substring.** Runnable today. The resolver falls back to the concrete generic scaffold pawn, which is not on the task-base lineage, so the first rung of the stage-1 ladder fires. Shares this substring with `bp-generic-pawn/` -- see ISOLATION CAVEAT |
| `cpp-solve/` | **FAIL** | L2I `bp_pawn_present` | `"id": "bp_pawn_present", "passed": false` | **MEASURED 2026-08-11: ran, credited at its named substring.** Runnable today (C++ only, 10 files, verbatim). L2 is expected to PASS -- that is the point -- which is what isolates the deliverable-format axis. `task_folder_exists` also reports false on the same run; both appear in the verdict block |
| `cpp-solve-with-bp/` | **FAIL** | L2I `resolved_pawn_is_blueprint` | `"id": "resolved_pawn_is_blueprint", "passed": false` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- the C++ half is committed, the Blueprint half is not, so today this directory equals `cpp-solve/` and would die at the wrong gate. Anti-gaming mode 2; the measured PASS-then-FAIL record is the glide section above |
| `bp-generic-pawn/` | **FAIL** | L2 cp0, HO-1 derivation | `does not derive from the provided task base pawn (CraftBenchBareCharacter).` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP pawn REPARENTED to the generic scaffold character, one property, everything else carried along |
| `bp-no-health-system/` | **FAIL** | L2 cp0, HO-2 presence | `stage 1 not built: the pawn's health attribute system is absent` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP pawn with its attribute-set wiring removed. The BP twin of the poison family's `bp-no-health-system/`, which IS proven at HEAD on the byte-identical stage-1 ladder |
| `bp-no-mesh/` | **FAIL** | L2 cp0, HO-5 visibility | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP pawn with the Mesh component's skeletal mesh cleared, one property |

---

## ISOLATION CAVEAT -- `empty` and `bp-generic-pawn/` share one named FAIL

Both are predicted to land on HO-1's
`does not derive from the provided task base pawn (CraftBenchBareCharacter).`
The collision is irreducible: HO-1 is the FIRST rung of the stage-1 ladder, and
an empty submission resolves to exactly the class `bp-generic-pawn/` reparents
to on purpose. Any variant targeting a task's first gate collides with `empty`,
which is why the substring oracle exempts the `empty` leg from its pairwise
uniqueness matrix (`matrix_oracle.is_isolation_leg`).

It is a collision, not a duplicate: `empty` reaches HO-1 incidentally (it builds
nothing, so the rung it trips first is an accident of ladder order), while
`bp-generic-pawn/` is a behaviourally COMPLETE Blueprint solve whose single
defect is the parent class. The same caveat is recorded, for the same reason, in
`../../gp-health-attribute-ops-cpp/discrimination/MATRIX.md`.

## Named-substring provenance (every literal above, traced to source)

Deliberately a bullet list, not a table -- see the MATRIX LAYOUT LAW banner.
Line numbers are into
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/HealthAttributeOpsFunctionalTest.cpp`
with the adjacent string-literal concatenation collapsed.

- `does not derive from the provided task base pawn (CraftBenchBareCharacter).`
  -- lines 118-123 (HO-1). The message OPENS
  `stage 1 not built: the graded pawn (%s) `, so the head of that sentence is
  NOT usable; this literal starts immediately after the `%s`.
- `stage 1 not built: the pawn's health attribute system is absent`
  -- lines 133-136 (HO-2). Placeholder-free message; this literal is its head.
  Note the ASCII apostrophe and, further along the same message, the ASCII
  hyphen-minus rather than an en dash: the UE log is written UTF-8 and read back
  cp1252, so a non-ASCII byte arrives as mojibake and the substring test misses
  silently.
- `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn`
  -- line 201-202 (HO-5). Placeholder-free, and byte-identical in all five
  fixtures of this family (glide, poison, health-ops, heal-over-time,
  double-jump).
- `"id": "bp_pawn_present", "passed": false` and
  `"id": "resolved_pawn_is_blueprint", "passed": false`
  -- the L2I verdict block, quoted from `tools/verify-single/introspect/gp_glide_stamina_bp.py`
  (`check()` builds `{"id": ..., "passed": ..., "detail": ...}` and `emit()`
  `json.dumps`es the list with default separators). **See the warning above:
  this twin's own script does not exist yet.**

## Deterministic gates (what flips PASS/FAIL)

- **L2 -- inherited byte-identically from `gp-health-attribute-ops-cpp`.** The
  cp0 stage-1 ladder HO-1 derivation, HO-2 Health present, HO-3 init to 100 read
  before any fixture write, HO-4 write-then-read at 37, HO-5 visible character;
  then at cp4 HO-6 both abilities granted and activating per tag, HO-7 direction,
  HO-8 the disclosed 5-25 band, HO-9 repeatability `drop2/drop1`, HO-10 symmetry
  `healDelta/drop1`, HO-11 the idle window. Every gate returns on failure, so a
  submission is judged by the FIRST one it trips.
- **L2I -- the `-bp` axis, and the only thing this package adds.** The chain
  runs `task_folder_exists` -> `bp_pawn_present` -> `bp_pawn_grants_bp_ability`
  -> `resolved_pawn_is_blueprint` (-> `pawn_visibly_represented` on the glide
  script). ALL checks are emitted in one verdict block whatever the outcome, so
  a substring naming a later check still matches when an earlier one also
  failed -- which is why `cpp-solve/`'s row names `bp_pawn_present` even though
  `task_folder_exists` fails on the same run.

## Anti-gaming modes (defended by the gates)

1. **Solve it in C++** -- `cpp-solve/`, the `-cpp` reference verbatim:
   behaviourally correct, L2 PASSES, and the only thing wrong with it is the
   deliverable format. Caught by L2I `bp_pawn_present`.
2. **C++ solve shipped alongside a conforming Blueprint** -- `cpp-solve-with-bp/`.
   Both layers go green on a 3-check verifier; only
   `resolved_pawn_is_blueprint` catches it. **Documented as a MEASURED false
   PASS on `gp-glide-stamina-bp` before that check existed** (see above), not
   argued.
3. **All eleven inherited gaming modes** (AG-1..AG-6 of the `-cpp` task) -> the
   inherited L2 gates, whose seven committed C++ overlays are measured on the
   `-cpp` twin. Three of them are planned here as `bp-*` Blueprint one-property
   deltas so the BP authoring path is exercised on the same axes.

## Asset specs for every BLOCKED row (the serial editor pass)

Bullet list on purpose (MATRIX LAYOUT LAW). Package paths are given as content
paths; the submission overlay mirrors them under
`<variant>/Content/Tasks/gp-health-attribute-ops-bp/`.

- `cpp-solve-with-bp/` -- **its Blueprint half is a VERBATIM COPY of whatever
  `../reference/Content/Tasks/gp-health-attribute-ops-bp/` ships.** Copy every
  asset, unmodified. That is precisely the recipe both shipped twins used
  (`gp-glide-stamina-bp` and `gp-poison-dot-stack-bp` each hold the reference's
  BP assets beside the C++ decoy), and it is what makes the row isolate the
  resolution axis: the Blueprint half must be a fully CONFORMING deliverable, or
  the leg dies at `bp_pawn_present` / `bp_pawn_grants_bp_ability` instead of at
  `resolved_pawn_is_blueprint` and proves nothing. The C++ half is already on
  disk and must not be touched.
- `bp-generic-pawn/` -- a full copy of the reference's asset set with the pawn
  Blueprint's **parent class** changed from the task base character to the
  generic scaffold character. Exactly one property; every other asset copied
  byte-for-byte so the abilities, effects and mesh come along and the leg's only
  defect is derivation.
- `bp-no-health-system/` -- a full copy of the reference's asset set with the
  pawn Blueprint's health-system wiring removed (on the poison twin's proven
  shape this is the ability-system component's `DefaultStartingData` entry and
  the init DataTable it points at). The pawn must still grant both abilities and
  still carry its mesh, so gates HO-1 and HO-5 pass and HO-2 is the first and
  only gate it can trip.
- `bp-no-mesh/` -- a full copy of the reference's asset set with the pawn
  Blueprint's mesh component **skeletal mesh cleared to None**. Nothing else.

**Authoring hazard, learned on `gp-poison-dot-stack-bp`:** the visible-character
gate HO-5 fires at cp0, BEFORE every stage-2 gate. A `bp-*` pawn authored from
scratch without an assigned mesh FAILs at
`the character is not visibly represented` instead of its intended gate, and
`cb discriminate` correctly reports `wrong-reason`. Author each one as a
ONE-PROPERTY delta off `../reference` so the mesh always comes along.

## Blockers (the sweep cannot run until all of these are true)

- The `-bp` task spec, its `## Verifier introspection` wiring, and
  `tools/verify-single/introspect/gp_health_attribute_ops_bp.py` must exist. A
  spec that declares an L2I leg whose script is missing produces a layer
  `status: "error"`, which routes to HARNESS-ERROR (exit 7) -- a non-graded
  verdict, not a discrimination result.
- Every Blueprint asset named above must be authored and committed.
- The runner grades from **git HEAD**. Anything uncommitted needs
  `--substrate-from-live`, and nothing may be committed while a sweep runs.
- The engine must be free: UBT's mutex is keyed on the ENGINE INSTALL, so a
  contended build returns exit 1 with no compile errors, which reads exactly
  like a variant failing L1.

## Re-validate -- what promotes a row from UNVALIDATED to MEASURED

Once the blockers clear, the single command is

```sh
cb discriminate gp-health-attribute-ops-bp
```

Read the results this way. If `../reference` FAILs, STOP -- every other verdict
is uninterpretable until the control is green. If `cpp-solve/` FAILs at L1, or
at any L2 gate, the decoy is wrong: it is the `-cpp` reference verbatim and L2
is supposed to PASS. If `cpp-solve-with-bp/` FAILs at `bp_pawn_present` rather
than at `resolved_pawn_is_blueprint`, its Blueprint half did not load or does
not conform -- that is a FAIL for the wrong reason, this repo's worst defect
class, and it is exactly the state `gp-glide-stamina-bp`'s and
`gp-poison-dot-stack-bp`'s copies of this decoy are stuck in today (their
binaries were left behind by the 2026-08-06 substrate port).

Replace each row's UNVALIDATED stamp with the measured verdict and paste the
leg's `[HEALTHOPS-FINAL]` line beside it.

## Parser self-check

This file was parsed with the repo's own parser
(`aura_rig.discriminate.parse_matrix`) before it was finished, and the result is
recorded here so a future editor can tell instantly whether an edit broke it:
**7 rows** -- `reference`, `empty`, `cpp-solve`, `cpp-solve-with-bp`,
`bp-generic-pawn`, `bp-no-health-system`, `bp-no-mesh` -- with `reference`
carrying `expect_pass=True` and an empty substring tuple, and each of the other
six carrying `expect_pass=False` and **exactly one** substring. No row is blank
and no row is shadowed. Re-run that check after any edit.

## Bounded coverage (honest note)

Nothing has been run. `TASK-AUTHOR-GUIDE.md` section B's acceptance gate --
reference PASS, `empty` FAIL, one attributable named FAIL per anti-gaming
note -- is **not met**, and not because a variant is missing: no leg has been
graded. Two of the seven rows are complete on disk; five wait on the editor.

The inherited L2 gaming modes are argued from the `-cpp` twin's matrix, not
re-run per variant here. Three of them are planned as `bp-*` rows above; HO-3,
HO-4, HO-6..HO-11 have no `bp-*` leg planned at all, and HO-11 has no leg
anywhere in the family -- the `-cpp` matrix shows the arithmetic for why no
constant-rate passive drift can reach it under the current bars.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every L2 backticked span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)`
source literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/HealthAttributeOpsFunctionalTest.cpp`
(never spanning a printf placeholder; ASCII-only per the cp1252 read-back rule) —
except row 6's L2 literal, which lives in the hoisted base helper
`ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented`
(`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`) and is
FinishTest-ed verbatim by this fixture. Every L2I backticked span is a verbatim run of the
CRAFTBENCH-INTROSPECT-JSON verdict line emitted by
`tools/verify-single/introspect/gp_health_attribute_ops_bp.py` through the shared
`tools/verify-single/introspect/_bp_variant_lib.py::run_checks` (all five checks are
emitted on every leg, so no L2I row can be skipped by an earlier failure). The gate name
(HO-n / check id) is the durable join key; the literal is the credit token.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | a gradeable pawn exists: resolvable by derivation, spawnable, possessable, owning the inherited ability system | fully | pre-gates — `pawn did not spawn/resolve` / `pawn has no AbilitySystemComponent` | only when L1 FAILs (the registry skips dependent layers); otherwise run at EVERY checkpoint before any HO gate | nothing; the fixture resolves by derivation + the preferred tag `Ability.Damage` and spawns/possesses the pawn itself (the map places no pawn), so an unresolvable deliverable dies here, not at a behavioral gate |
| 2 | the pawn is a subclass of the provided TASK character, not the generic one | fully, by TWO independent gates | L2 HO-1 — `pawn (CraftBenchBareCharacter). An empty submission` ; L2I — `"id": "bp_pawn_present", "passed": false` (same base, `CraftBenchBareCharacter`, so L2 and L2I agree on what "the deliverable" is) | HO-1: row 1 fires first. L2I: never (all five checks emitted on every leg) | subclass depth and intermediate Blueprint parents are free; the abstract base itself can never win resolution |
| 3 | a Health attribute exposed through the pawn's ability system, using the attribute set type the project provides | fully | L2 HO-2 — `stage 1 not built: the pawn's health attribute system is absent` (the probe reads the CONTRACT attribute, `UCraftBenchAttributeSet::GetHealthAttribute()`, so a home-grown "Health" on a different set fails here) | rows 1–2 | the wiring route (DefaultStartingData DataTable, an init GameplayEffect, anything editor-visible); `MaxHealth`/`Power` may be left uninitialized — no gate reads them |
| 4 | Health initialized to 100 | fully | L2 HO-3 — `stage 1 incomplete: Health must initialize to 100 but read ` (read BEFORE any fixture write, so the fixture's own preset can never mask it) | rows 1–3 | ±0.5 (BaselineEpsilon); the init route is free |
| 5 | Health readable AND writable through the standard attribute APIs (the verifier both reads and writes it) | fully | L2 HO-4 — `stage 1 incomplete: health attribute is inert, write-then-read failed (wrote ` (write-then-read at 37, a value != 100 on purpose, so an inert set initialized at 100 cannot pass vacuously) | rows 1–4 | only one base-value write is probed, once; the read side is exercised at every checkpoint anyway |
| 6 | the character is visibly represented: one of the provided mannequin skeletal meshes (under `/Game/Characters/`) assigned as its mesh | fully, by TWO independent gates | L2 HO-5 — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (one of four base-helper literals; the helper also rejects hidden-in-game and ~zero-scale meshes) ; L2I — `"id": "pawn_visibly_represented", "passed": false` (the assigned SkeletalMesh's asset path must start with `/Game/Characters/` — the read-only pool the agent cannot author into) | HO-5: rows 1–5. L2I: never | which mannequin, capsule alignment, transform, animation — all free. L2 alone would accept ANY mesh (even a static mesh or an agent-authored placeholder); the pool pin is L2I's half, so only the pair makes "a provided mannequin" binding |
| 7 | a damage ability tagged `Ability.Damage`, granted on the pawn (in its granted abilities) | fully | L2 HO-6 — `no activatable ability tagged Ability.Damage on the pawn` | cp0 ladder (rows 1–6) FinishTest-ed the leg first; otherwise first of the final-assert gates at cp4 | more than one ability may carry the tag (the gate is `>= 1`); extra unrelated granted abilities are free |
| 8 | a heal ability tagged `Ability.Heal`, granted on the pawn | fully | L2 HO-6 — `no activatable ability tagged Ability.Heal on the pawn` | rows 7, 9 (its damage half), 10 (damage grant, damage activation and HO-6c run first in the final-assert order) | same latitudes as row 7 |
| 9 | each tag is stamped on the ability ITSELF, in its own tag list, so the ability activates BY that tag (the verifier activates by tag directly, never via gameplay events) | fully, behaviorally | L2 HO-6 — `was granted but did NOT activate on TryActivateAbilitiesByTag` (fired per tag: the literal is preceded by `an ability tagged Ability.Damage ` / `an ability tagged Ability.Heal ` in the two source messages) | after the corresponding grant gate (rows 7–8) | additional tags in the ability's tag list, and any extra trigger-event wiring, are free — only activation-by-tag is gated |
| 10 | activations ~0.7 s apart must EACH land their full effect (an ability still running, or on cooldown, when the next activation arrives is not counted) | fully | L2 HO-6c — `an ability tagged Ability.Damage refused a later activation: ` | after row 7's grant + first-activation gates | a cooldown or active phase strictly shorter than 0.7 s; the cadence is only probed on the damage tag (heal is activated once) |
| 11 | the damage ability lowers Health | fully | L2 HO-7 — `the damage operation did not lower Health: Health went ` | rows 7–10 (final-assert order) | nothing beyond the noise floor: a drop > 0.5 clears HO-7, but HO-8 then floors it at 5 |
| 12 | each application changes Health by a FIXED amount between 5 and 25, the same amount every time | fully | L2 HO-8 — `the per-application Health change is outside the stated ` (the disclosed 5–25 band, on Drop1) ; L2 HO-9 — `the damage operation is not a fixed amount: the first application removed ` (Drop2/Drop1 in [0.90, 1.10] over congruent 0.7 s windows) | HO-8 after HO-7; HO-9 after HO-8 and the named denominator guard | the band is checked on the FIRST application only; the second is constrained only through the ±10% ratio, so a ±10% jitter reads as "fixed"; the heal magnitude is never band-checked directly (it is bounded via row 13's ratio) |
| 13 | one heal restores exactly as much Health as one damage removes (and therefore raises Health) | fully | L2 HO-10 — `heal does not restore what damage removes: one damage removed ` (HealDelta/Drop1 in [0.90, 1.10] over congruent 0.7 s windows; a positive ratio against a positive Drop1 is what asserts "raises") | rows 11–12 (HO-7..HO-9 fan out first) | "exactly" is graded as a 0.90–1.10 ratio over one sample per side; restore-to-full dies here by design (ratio ~6 from the preset of 60) |
| 14 | neither ability changes Health except when it is activated | fully | L2 HO-11 — `Health kept moving with no operation active: ` (the idle window (cp3, cp4], nothing triggered) | rows 7–13 (last gate in the leg) | one single 0.7 s idle window ending at t=3.3 s is observed: a drift <= 0.5 HP per window (~0.7 HP/s) is invisible, and anything deferred past cp4 (a delayed effect, a slow timer) is never sampled |
| 15 | the solution is saved under `Content/Tasks/gp-health-attribute-ops-bp/` ("that content folder is the only path the verifier looks in") | **partially** | L2I — `"id": "task_folder_exists", "passed": false` (folder exists and lists >= 1 asset) ; L2I — `"id": "bp_pawn_present", "passed": false` (the pawn Blueprint is discovered ONLY from that folder's asset list) | never (all five checks emitted on every leg; the layer runs only after L1) | **HOLE** — only the PAWN's location is pinned. The ability, effect and DataTable assets are read off the pawn's class defaults, not off the folder, so supporting assets saved to any other asset-writable prefix (`Content/Blueprints/`, `Content/Abilities/`, ...) pass every gate despite the prompt's "saved under" covering the whole solution. (The pawn itself saved elsewhere fails L2 resolution too — the fixture only scans `/Game/Tasks` — so the pawn half is airtight.) |
| 16 | the deliverable is ENTIRELY Blueprint: a Blueprint pawn with BOTH abilities authored in Blueprint and granted on it | fully (for the pawn and everything in its granted-abilities array) | L2I — `"id": "bp_pawn_grants_bp_ability", "passed": false` (>= 2 Blueprint-generated entries in `GrantedAbilities` AND zero native `/Script/` entries — the zero-native half closes the BP-shell-next-to-C++-ability hole) ; L2I — `"id": "resolved_pawn_is_blueprint", "passed": false` | never | class/asset NAMES are free (identity is path + derivation, never name); ability count above 2 is free; the >= 2 counts DISTINCT class paths (`distinct_class_count`, deduped 2026-08-16 per decision Q7 — one BP ability class granted twice no longer satisfies it. **CORRECTED 2026-08-16 after an adversarial review:** an earlier version of this cell claimed "no false PASS was reachable" because HO-6 and rows 7–8 would catch such a pawn. That was FALSE and it understated the fix. `NumGrantedAbilitiesWithTag` (`CraftBenchPawnFunctionalTest.cpp:389-403`) counts per TAG and is class-agnostic — it matches any spec whose ability carries the tag — so **one** ability class carrying BOTH `Ability.Damage` and `Ability.Heal` in its asset tags satisfies rows 7 AND 8. Granted twice, it also satisfied the old raw `len() >= 2`. So a single dual-tagged Blueprint ability WAS a reachable false-PASS route through this gate, and the dedup is load-bearing anti-gaming rather than cosmetic. **Regression it introduces, stated as decision Q7 requires:** a pawn whose class defaults hold the same ability twice while the second distinct ability is granted at RUNTIME now FAILs this check — runtime grants are invisible to the class-defaults probe by construction (`_bp_variant_lib.py:357-375` reads only `cdo.get_editor_property("granted_abilities")`). That false-FAIL family already existed for fully-runtime-granting submissions (count 0); the dedup narrows it rather than opening it); the residual is row 17's |
| 17 | "Do not add or modify any C++ source for this task" | **partially** | L2I — `"id": "resolved_pawn_is_blueprint", "passed": false` (NO agent-authored native subclass of the scaffold root `ACraftBenchCharacter` may exist; exemption by exact git-HEAD `/Script/` path; fails CLOSED if the sweep stops seeing the scaffold) plus the zero-native half of `bp_pawn_grants_bp_ability` (row 16) | never | **HOLE (documented residual, task.md anti-gaming note 3 / `_bp_variant_lib.py` "WHAT THIS MODULE DOES NOT COVER")** — the native sweep is scaffold-PAWN-shaped and the granted-abilities check is ability-CLASS-shaped, so agent C++ that is neither passes all five checks: a native `UGameplayEffect`, `UAttributeSet`, `UGameplayModMagnitudeCalculation` or Blueprint function library referenced FROM the Blueprint assets does the real work while every gate stays green. Closing it is the internal design note (not shipped) V2.1's native-decoy sweep, which is not built. |

Reading notes, so the table stays self-contained:

- **L2 gate order is load-bearing for the "skipped when" column.** The cp0 stage-1
  ladder (rows 1–6) runs top-to-bottom and each rung `FinishTest`s the whole leg,
  so a submission is judged by the FIRST gate it trips; the final asserts at cp4
  run in the order: damage grant, damage activation, HO-6c, heal grant, heal
  activation, HO-7, HO-8, the named denominator guard, HO-9, HO-10, HO-11.
- **The two "partially" rows are the holes**, and both are the residuals the task
  spec itself records rather than papers over: row 15's supporting-asset location
  and row 17's non-pawn, non-granted-ability native C++. Neither has an enforcing
  gate today; do not cite either requirement as defended.
- **Tolerances in force** (all `PROPOSED - NOT YET MEASURED` per the fixture
  header): BaselineEpsilon 0.5 (rows 4–5), DirectionEpsilon 0.5 (row 11),
  MagnitudeMin/Max 5/25 (row 12), RepeatTol/SymTol 0.10 (rows 12–13),
  IdleEpsilon 0.5 (row 14); the cp0 preset is 60, the write probe 37.
