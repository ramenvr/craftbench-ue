# gp-double-jump-stamina-bp -- discrimination matrix

> ## STATUS: **MEASURED + CERTIFIED 2026-08-11 — `cb discriminate` = YES 7/7, live AND `substrate=HEAD`.**
>
> **Certified verdict:** with the whole package committed, `decide_from_live`
> selected `substrate=HEAD` and the family credited **7/7** — the git-HEAD
> certification, in a hands-off run (nothing else on the box). Two transients
> earlier the same day, BOTH environment and NEITHER reproducible: the
> three-family live sweep returned FAIL(harness-error) on `cpp-solve-with-bp`
> (a zombie sweep was concurrently building — a TaskStop that killed the shell
> but not the driver), and the three-family HEAD sweep returned FAIL(skipped)
> on `cpp-solve` (lint/status_gen ran concurrently). Solo re-grades of both
> legs FAILed at exactly their named substrings. The operating law this
> re-proves: NOTHING else runs during a graded sweep — not lint, not
> status_gen, not file-walking tools.
>
> Reference **PASS**; `empty`, `bp-free-jump`, `bp-no-mesh`, `bp-wrong-cost`,
> `cpp-solve`, `cpp-solve-with-bp` each **FAIL credited at its named
> substring**. Run was `substrate=live` — chosen by `decide_from_live` because
> the variant assets were not yet committed; live == HEAD in content for
> everything graded (fixture, maps, C++ all clean at `9cdbd6a`). The reference
> additionally holds a from-git-HEAD PASS the same day (see
> `../REFERENCE-NOTE.md`). Variant `.uasset`s were authored headlessly from
> pristine reference copies via `../../_shared/author_bp_variant.py` (one
> delta per boot, byte-verified).
>
> One measurement note for the record: in the first (three-family) sweep this
> family's `cpp-solve-with-bp` leg returned FAIL(**harness-error**) — a
> non-verdict, correctly NOT credited. A solo re-grade returned a clean graded
> FAIL at exactly the predicted check (`resolved_pawn_is_blueprint`, naming
> `/Script/ThirdPerson.DoubleJumpPawn` as the resolution-winning decoy), and
> the full-family re-run above then credited 7/7. The harness-error did not
> reproduce; treat a recurrence as an environment fault, not a leg defect.
>
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
>    `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-double-jump-stamina/DoubleJumpStaminaFunctionalTest.cpp`
>    (byte-identical for the `-cpp` original and this `-bp` twin -- the folder is
>    deliberately unsuffixed, exactly as the glide/poison pairs do it);
> 2. the committed `-cpp` reference,
>    `../../gp-double-jump-stamina-cpp/reference/Source/ThirdPerson/`, which is
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
> STATUS banner). The reference landed at commit `c5f3ac2`; the `bp-*` variant
> assets and the `cpp-solve-with-bp` BP half were authored 2026-08-11 and are
> committed alongside this banner edit. The original text is kept for the
> record:
>
> ## _(original)_ BLOCKED ON ASSET AUTHORING (rows that cannot even be RUN yet)
>
> A `.uasset` cannot be authored outside a live editor, so every row whose
> submission contains Blueprint content is **documentary only** until the serial
> asset pass runs. Those rows are:
>
> - `../reference` -- the BP deliverable itself does not exist on disk.
> - `cpp-solve-with-bp/` -- its C++ half IS committed here (verbatim, 4 files);
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
  `/Game/Tasks/gp-double-jump-stamina-bp/` (the documented deliverable-format
  exception to behavior-only prompts -- measuring the BP authoring path IS the
  point of the variant);
- an **L2I introspect leg** structurally asserts the deliverable really IS
  Blueprint;
- **C++ decoy variants** that try to defeat that leg. Those decoys are what this
  package contains.

Both decoys are the `-cpp` reference's C++ **verbatim** -- `diff -rq` against
`../../gp-double-jump-stamina-cpp/reference/Source/ThirdPerson/` is empty for
both, all 4 files. That is not tidiness: a decoy that differed behaviourally
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

The same trap applies here unchanged. This family's `PreferredAbilityTag()` is
`Ability.DoubleJump`, both a native and a Blueprint pawn can carry it, and
natives are enumerated first.

## THE L2I CHECK NAMES: ~~not yet verifiable~~ — VERIFIED 2026-08-11

`tools/verify-single/introspect/gp_double_jump_stamina_bp.py` ~~does not exist
on disk~~ (**it does now — committed 2026-08-10, and it graded the 2026-08-11
runs; both substrings below were confirmed verbatim in the measured legs'
verdict blocks**). Original context: verified-absent while authoring this file;
the introspect directory then held only the glide and poison `-bp` scripts
plus the six imported-set scripts. The two
L2I substrings recorded below are therefore quoted from the SHIPPED twins'
scripts -- `gp_glide_stamina_bp.py` and `gp_poison_dot_stack_bp.py`, whose check
ids are `task_folder_exists`, `bp_pawn_present`, `bp_pawn_grants_bp_ability`,
`resolved_pawn_is_blueprint`, `pawn_visibly_represented` -- on the assumption
that this twin's script reuses them.

**If the sibling script names a check anything else, the two L2I rows below
become wrong-reason FAILs, not discrimination wins.** Reconcile the two
substrings against the script the moment it lands, BEFORE running the sweep.

One family-specific note for whoever writes that script: this task's reference
pawn derives from the **generic** `ACraftBenchCharacter` (the family is not
health-first -- the Bare lineage suppresses the attribute set and would leave
the pawn with no Power at all). So `bp_pawn_present` must test derivation from
the generic scaffold class, and `resolved_pawn_is_blueprint`'s native sweep must
still exempt the committed ABSTRACT `CraftBenchBareCharacter` by exact
`/Script/` path, exactly as the glide script does.

---

## Matrix

Each "Expected message" cell carries **exactly one** backticked literal, because
`_extract_substrings` returns every substantive backticked span and `grade_leg`
requires **ALL** of them to appear in the concatenated L2 + L2I log. Each
literal is either

- a verbatim **literal run** of a real `FinishTest(EFunctionalTestResult::Failed,
  ...)` message in the shared fixture -- never a run that spans a `%.0f` / `%.1f`
  / `%.2f` / `%d` placeholder, which can never match at runtime (`granted=` is
  matchable; `granted=0` is not); or
- a verbatim run of the L2I verdict JSON line (`json.dumps` with default
  separators, so `"id": "x", "passed": false` is a literal run of it).

Predicted numbers are deliberately kept OUTSIDE backticks and live in the last
column: a human-readable summary inside a substring cell can never match and
would read as a wrong-reason FAIL. Note that two of the literals below END IN A
SPACE, which is load-bearing -- the character after it is a `%` placeholder.

| Submission | Overall | Fails at | Expected message | Status |
|---|---|---|---|---|
| `../reference` | **PASS** | -- | all nine L2 gates green plus every L2I check passing | **MEASURED 2026-08-11: ran, PASS** (from-git-HEAD PASS same day, see `../REFERENCE-NOTE.md`; was: blocked on asset authoring) -- the BP deliverable does not exist on disk |
| empty (no overlay -> generic scaffold pawn) | **FAIL** | L2 cp0, DJ-7 visibility | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | **MEASURED 2026-08-11: ran, credited at its named substring.** Runnable today. The resolver falls back to the generic scaffold pawn, which carries no assigned mesh, so the checkpoint-0 gate fires and no diagnostic FINAL line is ever emitted. Shares this substring with `bp-no-mesh/` -- see ISOLATION CAVEAT |
| `cpp-solve/` | **FAIL** | L2I `bp_pawn_present` | `"id": "bp_pawn_present", "passed": false` | **MEASURED 2026-08-11: ran, credited at its named substring.** Runnable today (C++ only, 4 files, verbatim). L2 is expected to PASS -- that is the point -- which is what isolates the deliverable-format axis. `task_folder_exists` also reports false on the same run; both appear in the verdict block |
| `cpp-solve-with-bp/` | **FAIL** | L2I `resolved_pawn_is_blueprint` | `"id": "resolved_pawn_is_blueprint", "passed": false` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- the C++ half is committed, the Blueprint half is not, so today this directory equals `cpp-solve/` and would die at the wrong gate. Anti-gaming mode 2; the measured PASS-then-FAIL record is the glide section above |
| `bp-no-mesh/` | **FAIL** | L2 cp0, DJ-7 visibility | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP pawn with the Mesh component's skeletal mesh cleared, one property |
| `bp-free-jump/` | **FAIL** | L2 last cp, DJ-3a | `the second jump cost no Power: Power went ` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP ability with the one-shot debit removed and the refusal gate KEPT, so the jump itself is untouched and the debit is exactly zero rather than merely small |
| `bp-wrong-cost/` | **FAIL** | L2 last cp, DJ-3b | `the second jump did not cost 20 Power: Power went 60.0 -> ` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP ability with its cost value changed to a non-disclosed magnitude. A perfectly one-shot debit of the wrong size, so DJ-3a passes comfortably and DJ-3b is the first gate it can trip |

---

## ISOLATION CAVEAT -- `empty` and `bp-no-mesh/` share one named FAIL

Both are predicted to land on DJ-7's
`the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn`.
The collision is irreducible: DJ-7 is the FIRST gate in the fixture and it runs
at checkpoint 0, and the generic scaffold pawn an empty submission resolves to
is meshless for exactly the reason `bp-no-mesh/` clears the mesh on purpose. Any
variant targeting a task's first gate collides with `empty`, which is why the
substring oracle exempts the `empty` leg from its pairwise uniqueness matrix
(`matrix_oracle.is_isolation_leg`).

It is a collision, not a duplicate -- `bp-no-mesh/` is an otherwise complete
Blueprint solve -- but it is an HONEST one: `bp-no-mesh/` proves DJ-7 fires on a
complete pawn, and does not isolate beyond `empty`. The same caveat is recorded,
in the same words, in
`../../gp-double-jump-stamina-cpp/discrimination/MATRIX.md`.

## Named-substring provenance (every literal above, traced to source)

Deliberately a bullet list, not a table -- see the MATRIX LAYOUT LAW banner.
Line numbers are into
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-double-jump-stamina/DoubleJumpStaminaFunctionalTest.cpp`
with the adjacent string-literal concatenation collapsed.

- `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn`
  -- lines 190-191 (DJ-7). Placeholder-free, and byte-identical in all five
  fixtures of this family (glide, poison, health-ops, heal-over-time,
  double-jump).
- `the second jump cost no Power: Power went ` -- lines 614-617 (DJ-3a). The
  literal STOPS immediately before the first `%.1f`, hence the trailing space.
- `the second jump did not cost 20 Power: Power went 60.0 -> ` -- lines 629-632
  (DJ-3b). The `20` and the `60.0` here are LITERAL characters in the fixture's
  format string, not interpolated values, so they are safe inside the substring;
  the literal stops immediately before the following `%.1f`.
- `"id": "bp_pawn_present", "passed": false` and
  `"id": "resolved_pawn_is_blueprint", "passed": false`
  -- the L2I verdict block, quoted from `tools/verify-single/introspect/gp_glide_stamina_bp.py`
  (`check()` builds `{"id": ..., "passed": ..., "detail": ...}` and `emit()`
  `json.dumps`es the list with default separators). **See the warning above:
  this twin's own script does not exist yet.**

ASCII discipline: the UE log is written UTF-8 and read back cp1252, so a
non-ASCII byte anywhere in a recorded literal arrives as mojibake and the
substring test misses silently. Every literal above is pure ASCII, as is the
whole of this file.

## Deterministic gates (what flips PASS/FAIL)

- **L2 -- inherited byte-identically from `gp-double-jump-stamina-cpp`.** DJ-7
  the visible character at cp0; then at the last checkpoint DJ-1 the second jump
  is an activatable ability granted by tag (plus the per-leg activation gate),
  DJ-2a the falling baseline (harness sanity), DJ-2b a real upward impulse,
  DJ-2b2 ballistic consistency, DJ-2c a segmented second rise, DJ-3a Power was
  debited, DJ-3b the cost is exactly the disclosed 20, DJ-3c the cost is a
  one-shot and not a continuous drain, DJ-4 refusal below the cost. Every gate
  returns on failure, so a submission is judged by the FIRST one it trips.
- **Two of those gates were REPAIRED by running variants, not by review**
  (`-cpp` matrix, 2026-08-10): DJ-4 false-FAILed the conforming reference on an
  apex blip and became a ratio against the same run's own jump, and `teleport/`
  PASSED the whole task until DJ-2b2 was added. Any `bp-*` leg planned against
  DJ-2b/DJ-2c/DJ-4 inherits that history and must be RUN, not argued.
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
3. **All inherited gaming modes** (AG-1..AG-8 of the `-cpp` task, of which AG-7
   is recorded as ARGUED with no gate) -> the inherited L2 gates, whose eight
   committed C++ overlays are measured on the `-cpp` twin. Three of them are
   planned here as `bp-*` Blueprint deltas so the BP authoring path is exercised
   on the same axes.

## Asset specs for every BLOCKED row (the serial editor pass)

Bullet list on purpose (MATRIX LAYOUT LAW). Package paths are given as content
paths; the submission overlay mirrors them under
`<variant>/Content/Tasks/gp-double-jump-stamina-bp/`.

- `cpp-solve-with-bp/` -- **its Blueprint half is a VERBATIM COPY of whatever
  `../reference/Content/Tasks/gp-double-jump-stamina-bp/` ships.** Copy every
  asset, unmodified. That is precisely the recipe both shipped twins used
  (`gp-glide-stamina-bp` and `gp-poison-dot-stack-bp` each hold the reference's
  BP assets beside the C++ decoy). What the Blueprint half must satisfy is only
  the three EXISTENCE checks -- it must LOAD, its generated class must derive
  from the scaffold character, and its granted-abilities array must carry at
  least one Blueprint-generated ability class -- because L2 grades the C++ pawn,
  not this one. A do-nothing BP shell meeting those three is sufficient and is
  strictly easier to satisfy than the real deliverable; copying the reference is
  simply the cheapest way to be sure. If the Blueprint half fails to load, the
  leg dies at `bp_pawn_present` instead of at `resolved_pawn_is_blueprint` and
  proves nothing. The C++ half is already on disk and must not be touched.
- `bp-no-mesh/` -- a full copy of the reference's asset set with the pawn
  Blueprint's mesh component **skeletal mesh cleared to None**. Nothing else.
- `bp-free-jump/` -- a full copy of the reference's asset set with the second
  jump ability Blueprint's **one-shot Power debit deleted** and its
  below-the-cost REFUSAL branch kept exactly as the reference has it. Keeping
  the refusal is what stops the leg from also tripping DJ-4 and makes DJ-3a the
  first and only gate it can reach; the debit must be exactly zero, not merely
  small.
- `bp-wrong-cost/` -- a full copy of the reference's asset set with the ability
  Blueprint's **cost value changed away from the disclosed 20** (the `-cpp`
  twin's overlay uses 35, and the same number keeps the two matrices readable
  side by side). Both the refusal branch and the debit stay one-shot, so DJ-3a
  and DJ-3c both pass and DJ-3b is the first gate it can trip.

**Authoring hazard, learned on `gp-poison-dot-stack-bp`:** the visible-character
gate DJ-7 fires at cp0, before every later gate. A `bp-*` pawn authored from
scratch without an assigned mesh FAILs at
`the character is not visibly represented` instead of its intended gate, and
`cb discriminate` correctly reports `wrong-reason`. Author each one as a
ONE-PROPERTY delta off `../reference` so the mesh always comes along.

**Second authoring hazard, specific to this family:** the fixture presets Power
itself before each leg (60 for the jump, 5 for the refusal), so nothing
observable depends on the pawn's own starting Power -- do not "fix" a `bp-*`
leg by changing it, and do not read anything into it.

## Blockers (the sweep cannot run until all of these are true)

- The `-bp` task spec, its `## Verifier introspection` wiring, and
  `tools/verify-single/introspect/gp_double_jump_stamina_bp.py` must exist. A
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
cb discriminate gp-double-jump-stamina-bp
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

Replace each row's UNVALIDATED stamp with the measured verdict and paste BOTH
`[DOUBLEJUMP-FINAL]` lines beside it -- the second one carries
`legOneSegments=` and `fullSegments=`, and the `-cpp` twin's owner decision of
2026-08-10 makes reading that decomposition mandatory before believing any
DJ-2c or DJ-4 verdict.

## Parser self-check

This file was parsed with the repo's own parser
(`aura_rig.discriminate.parse_matrix`) before it was finished, and the result is
recorded here so a future editor can tell instantly whether an edit broke it:
**7 rows** -- `reference`, `empty`, `cpp-solve`, `cpp-solve-with-bp`,
`bp-no-mesh`, `bp-free-jump`, `bp-wrong-cost` -- with `reference` carrying
`expect_pass=True` and an empty substring tuple, and each of the other six
carrying `expect_pass=False` and **exactly one** substring, both trailing spaces
preserved. No row is blank and no row is shadowed. Re-run that check after any
edit.

## Bounded coverage (honest note)

Nothing has been run. `TASK-AUTHOR-GUIDE.md` section B's acceptance gate --
reference PASS, `empty` FAIL, one attributable named FAIL per anti-gaming
note -- is **not met**, and not because a variant is missing: no leg has been
graded. Two of the seven rows are complete on disk; five wait on the editor.

The inherited L2 gaming modes are argued from the `-cpp` twin's matrix, not
re-run per variant here. Three of them are planned as `bp-*` rows above; DJ-1,
DJ-2b, DJ-2b2, DJ-2c, DJ-3c and DJ-4 have no `bp-*` leg planned. DJ-2b2 and DJ-4
are the two gates the `-cpp` sweep had to repair after a variant ran, so they
are the first candidates for a second `bp-*` wave -- and neither may be recorded
as covered on argument alone.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked L2 token is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-double-jump-stamina/DoubleJumpStaminaFunctionalTest.cpp`
(shared byte-identically with the `-cpp` twin), except DJ-7's, which lives in the hoisted base helper
`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp` (`PawnVisiblyRepresented`).
Every L2I token is a verbatim run of the verdict JSON emitted by
`tools/verify-single/introspect/gp_double_jump_stamina_bp.py` via `_bp_variant_lib.py` (`check()` builds
`{"id": ..., "passed": ...}`; `json.dumps` default separators). Tokens ending in a space end there because the
next source character is a printf placeholder; parser-safe per the MATRIX LAYOUT LAW (numeric first column, no
column named "substring"/"message", no `/` in a first cell).

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the second jump is an **ability**, granted on the pawn and triggerable by the tag `Ability.DoubleJump` | fully | DJ-1 — `no activatable ability tagged Ability.DoubleJump on the pawn` | fixture died earlier (pawn unresolved, or DJ-7 at cp0) | asset/class names are free (identity is tag + derivation); extra abilities granted alongside are never gated |
| 2 | the game can actually **activate** it by sending that tag (Leg 1) | fully | activation gate — `an ability tagged Ability.DoubleJump was granted but did NOT activate on TryActivateAbilitiesByTag` | row 1 fired first | a refused **Leg-2** re-activation is conforming by design and is never failed here |
| 3 | the jump is taken "while it is already falling" — the pawn really was descending at the trigger | fully (harness sanity, not anti-gaming) | DJ-2a — `no falling baseline: the character was not descending when the ability was triggered` | rows 1–2 | nothing agent-side: the fixture drops the pawn itself; a fire here indicts the harness (spawn height/floor), not the submission |
| 4 | the descent **reverses** — a real upward impulse, not a slowed fall | fully | DJ-2b — `the ability produced no upward impulse: the highest vertical velocity after the trigger was ` | rows 1–3 | magnitude entirely free (no jump-height floor, on purpose); an *additive* launch big enough to flip vZ positive passes the direction test |
| 5 | not a **teleport** (motion consistent with its own velocity) | fully | DJ-2b2 ballistic consistency — `the second jump was not produced by an upward impulse: the character rose ` | rows 1–4 | rise up to `BallisticSlackFactor` x v²/2g; a teleport that also injects a matching upward velocity would be physics-consistent and pass |
| 6 | it is "carr[ied] upward again" — Z actually climbs back after bottoming out | fully | DJ-2c — `the character did not rise a second time: Z fell to ` | rows 1–5 | any rise > `RiseEpsilon` (20 cm — PROPOSED, not yet BP-calibrated) counts; a barely-perceptible hop passes |
| 7 | "...it then **falls back down** from" — a jump, not a levitation/gravity-off hold | fully | DJ-2d — `the character rose a second time but never came back down: Z climbed ` | rows 1–6 | a post-apex fall of just `RiseEpsilon` suffices; reduced-but-nonzero gravity after the apex passes |
| 8 | activating it **costs Power** (a debit actually lands) | fully | DJ-3a — `the second jump cost no Power: Power went ` | rows 1–7 | any debit > `PowerEpsilon` measured at trigger+0.3 s, from any mechanism (cost GE, explicit subtract, ...) |
| 9 | the cost is the disclosed **20**, debited once per activation | fully | DJ-3b — `the second jump did not cost 20 Power: Power went 60.0 -> ` | rows 1–8 | a debit within `CostTol` of 20; the 20/60.0 in the token are source-literal characters, safe to match |
| 10 | it must **not drain Power continuously** while airborne | fully, windowed | DJ-3c — `the Power cost is a continuous drain, not a one-shot debit` | rows 1–9 | a drain that only starts after trigger+1.2 s escapes the (trigger+0.3, trigger+1.2] window; a drain under `PowerEpsilon` total over that window escapes too |
| 11 | below 20 Power the ability does **not fire**: no second jump | fully, guarded | DJ-4 — `the ability fired without paying for it: with only 5.0 Power (below the 20 cost)` | **SKIPPED (not failed) when Leg 1 never established a rise** (`[DJ-REFUSE-DIAG]` announces which); also rows 1–10 | a cooldown that blocks the Leg-2 re-trigger is indistinguishable from a cost gate and passes (accepted lenient, PIN.md D3); a Leg-2 rise under `RefusalRiseFactor` x the run's own Leg-1 jump (floored at `RiseEpsilon`) passes |
| 12 | below 20 Power, **Power must not go negative** — and must not be spent at all | fully, guarded | DJ-4 (negative half, same token as row 11) plus DJ-4b — `the ability charged without delivering: with only ` | same guard as row 11 | a spend under `PowerEpsilon`; DJ-4b exists precisely because a zero-clamped debit hides the sign the DJ-4 half asks about |
| 13 | assets saved under `Content/Tasks/gp-double-jump-stamina-bp/` — "the only path the verifier looks in" | fully | L2I — `"id": "task_folder_exists", "passed": false` (plus L2's resolver only scans `/Game/Tasks` via the Asset Registry, so a BP elsewhere never grades) | never — all five L2I checks emit on every run (constant denominator; an empty submission scores 0/5) | the existence half is satisfied by >= 1 asset of any kind; the substantive folder gates are rows 14–16, 19 |
| 14 | the deliverable is a **Blueprint subclass of the provided character** | fully | L2I — `"id": "bp_pawn_present", "passed": false` | never (see row 13); dependent checks FAIL `no BP pawn resolved` rather than skip | any number of extra Blueprints beside it; naming is free (derivation + path, never name) |
| 15 | the solution is "**entirely** Blueprint": the granted second-jump ability is Blueprint-generated | partially | L2I — `"id": "bp_pawn_grants_bp_ability", "passed": false` (>= 1 BP ability AND **zero** native `/Script/` entries in `GrantedAbilities`) | never (fails `no BP pawn resolved` when row 14 found no pawn) | **the documented residual**: a native `UGameplayEffect` (e.g. the cost effect), `UAttributeSet` or `UGameplayModMagnitudeCalculation` referenced *from* the BP ability is not swept (task.md anti-gaming note 3, ARGUED NOT DEFENDED; V2.1 native-decoy sweep unbuilt) |
| 16 | "Do not **add** ... any C++ source" — no native pawn does the real work while a decoy BP grades | fully (for pawn subclasses) | L2I — `"id": "resolved_pawn_is_blueprint", "passed": false` (sweeps ALL native `ACraftBenchCharacter` subclasses; exemption by exact `/Script/` path of git-HEAD scaffolds; fails closed) | never (see row 13) | added native classes that are **not** pawn subclasses — same residual as row 15 |
| 17 | "Do not ... **modify** any C++ source" | **NOT ASSERTED** | none — `Source/ThirdPerson/` is the sandbox-writable module (the `-cpp` twin's lane), L1 rebuilds whatever is submitted, and the native sweep exempts scaffolds by **exact `/Script/` path**, which an in-place edit keeps | unconditional | edit a committed scaffold in place (e.g. put the jump/cost logic into `CraftBenchCharacter.cpp` itself) and call it from a thin BP: same class path, so the sweep exempts it; every L2 and L2I gate passes on a submission the prompt explicitly forbids |
| 18 | the character is **visibly represented** — a mesh actually assigned | fully | DJ-7 (cp0, first gate) — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | only the resolve guard (`pawn did not spawn/resolve`) precedes it | the L2 half does not pin *which* mesh — that is row 19's job |
| 19 | the mesh is one of the **provided mannequins under `/Game/Characters/`** | fully | L2I — `"id": "pawn_visibly_represented", "passed": false` (SkeletalMesh asset path must live under the read-only `/Game/Characters/` pool) | never (fails `no BP pawn resolved` when row 14 found no pawn) | Manny vs Quinn, transform/pose, extra components — all free; pool-anchoring is what blocks the empty-placeholder-mesh dodge |

### Holes this table found (escalation, not paper-over)

- **Row 17 is a genuine NOT ASSERTED**: the "do not *modify* C++" half of the deliverable bullet has no
  gate anywhere. The `resolved_pawn_is_blueprint` exemption is path-shaped (exact `/Script/` path at git
  HEAD), and an in-place scaffold edit keeps its path; no content hash or diff gate covers the
  agent-writable module. Closing it needs a source-diff check against the substrate at HEAD (the same
  provenance anchor the runner already records), not a variant.
- **Row 15/16's native-helper residual** is inherited and already documented (task.md anti-gaming note 3;
  `_bp_variant_lib.py` "WHAT THIS MODULE DOES NOT COVER"): "entirely as Blueprint" is enforced only
  pawn-and-granted-ability deep. Recorded here so the table, not the prose, is what a reviewer trusts.
