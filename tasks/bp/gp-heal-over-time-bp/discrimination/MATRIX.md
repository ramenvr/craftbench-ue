# gp-heal-over-time-bp -- discrimination matrix

> ## STATUS: **MEASURED + CERTIFIED 2026-08-11 — `cb discriminate` = YES 7/7, live AND `substrate=HEAD`.**
>
> **Certified verdict:** with the whole package committed, `decide_from_live`
> selected `substrate=HEAD` and the family credited **7/7** — the git-HEAD
> certification. This family credited 7/7 on every run it appeared in
> (live sweep, a concurrent-contention re-run, and the HEAD sweep).
>
> Reference **PASS**; `empty`, `bp-instant`, `bp-no-maxhealth`, `bp-no-mesh`,
> `cpp-solve`, `cpp-solve-with-bp` each **FAIL credited at its named
> substring**. Run was `substrate=live` — chosen by `decide_from_live` because
> the variant assets were not yet committed; live == HEAD in content for
> everything graded (fixture, maps, C++ all clean at `9cdbd6a`). The reference
> additionally holds a from-git-HEAD PASS the same day whose trace reproduced
> this file's predictions line for line (see `../REFERENCE-NOTE.md`). Variant
> `.uasset`s were authored headlessly from pristine reference copies via
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
>    `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/HealOverTimeFunctionalTest.cpp`
>    (byte-identical for the `-cpp` original and this `-bp` twin -- the folder is
>    deliberately unsuffixed, exactly as the glide/poison pairs do it);
> 2. the committed `-cpp` reference,
>    `../../gp-heal-over-time-cpp/reference/Source/ThirdPerson/`, which is what
>    both C++ decoys here ARE, verbatim;
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
> STATUS banner). The reference landed at commit `9cdbd6a`; the `bp-*` variant
> assets and the `cpp-solve-with-bp` BP half were authored 2026-08-11 and are
> committed alongside this banner edit. The original text is kept for the
> record:
>
> A `.uasset` cannot be authored outside a live editor, so every row whose
> submission contains Blueprint content is **documentary only** until the serial
> asset pass runs. Those rows are:
>
> - `../reference` -- the BP deliverable itself does not exist on disk.
> - `cpp-solve-with-bp/` -- its C++ half IS committed here (verbatim, 8 files);
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
  `/Game/Tasks/gp-heal-over-time-bp/` (the documented deliverable-format
  exception to behavior-only prompts -- measuring the BP authoring path IS the
  point of the variant);
- an **L2I introspect leg** structurally asserts the deliverable really IS
  Blueprint;
- **C++ decoy variants** that try to defeat that leg. Those decoys are what this
  package contains.

Both decoys are the `-cpp` reference's C++ **verbatim** -- `diff -rq` against
`../../gp-heal-over-time-cpp/reference/Source/ThirdPerson/` is empty for both,
all 8 files. That is not tidiness: a decoy that differed behaviourally would
make an L2 failure attributable to the difference rather than to the decoy, and
the whole point of `cpp-solve/` is that **L2 passes**.

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
`Ability.HealOverTime`, both a native and a Blueprint pawn can carry it, and
natives are enumerated first.

## THE L2I CHECK NAMES: ~~not yet verifiable~~ — VERIFIED 2026-08-11

`tools/verify-single/introspect/gp_heal_over_time_bp.py` ~~does not exist on
disk~~ (**it does now — committed 2026-08-10, and it graded the 2026-08-11
runs; both substrings below were confirmed verbatim in the measured legs'
verdict blocks**). Original context: verified-absent while authoring this file;
the introspect directory then held only
the glide and poison `-bp` scripts plus the six imported-set scripts. The two L2I
substrings recorded below are therefore quoted from the SHIPPED twins' scripts
-- `gp_glide_stamina_bp.py` and `gp_poison_dot_stack_bp.py`, whose check ids are
`task_folder_exists`, `bp_pawn_present`, `bp_pawn_grants_bp_ability`,
`resolved_pawn_is_blueprint`, `pawn_visibly_represented` -- on the assumption
that this twin's script reuses them.

**If the sibling script names a check anything else, the two L2I rows below
become wrong-reason FAILs, not discrimination wins.** Reconcile the two
substrings against the script the moment it lands, BEFORE running the sweep.

One family-specific note for whoever writes that script: this task's reference
pawn derives from the **generic** `ACraftBenchCharacter`, not from the
health-first `ACraftBenchBareCharacter` (PIN.md D2 routes it that way on purpose
so its stage-1 population does not correlate with the health-ops and poison
families). So `bp_pawn_present` must test derivation from the generic scaffold
class, and `resolved_pawn_is_blueprint`'s native sweep must still exempt the
committed ABSTRACT `CraftBenchBareCharacter` by exact `/Script/` path, exactly
as the glide script does.

---

## Matrix

Each "Expected message" cell carries **exactly one** backticked literal, because
`_extract_substrings` returns every substantive backticked span and `grade_leg`
requires **ALL** of them to appear in the concatenated L2 + L2I log. Each
literal is either

- a verbatim **literal run** of a real `FinishTest(EFunctionalTestResult::Failed,
  ...)` message in the shared fixture -- never a run that spans a `%.1f` / `%.2f`
  / `%d` placeholder, which can never match at runtime (`granted=` is matchable;
  `granted=0` is not); or
- a verbatim run of the L2I verdict JSON line (`json.dumps` with default
  separators, so `"id": "x", "passed": false` is a literal run of it).

Predicted numbers are deliberately kept OUTSIDE backticks and live in the last
column: a human-readable summary inside a substring cell can never match and
would read as a wrong-reason FAIL. Note that two of the literals below END IN A
SPACE, which is load-bearing -- the character after it is a `%` placeholder.

| Submission | Overall | Fails at | Expected message | Status |
|---|---|---|---|---|
| `../reference` | **PASS** | -- | all nine L2 gates green plus every L2I check passing | **MEASURED 2026-08-11: ran, PASS** (from-git-HEAD PASS same day, see `../REFERENCE-NOTE.md`; was: blocked on asset authoring) |
| empty (no overlay -> generic scaffold pawn) | **FAIL** | L2 cp0, HOT-0 | `MaxHealth was not initialized: read ` | **MEASURED 2026-08-11: ran, credited at its named substring.** Runnable today. The generic scaffold pawn pre-builds the contract attribute set but nothing initializes MaxHealth, so it reads 0.0 and the very first gate fires, before the visible-character gate. Shares this substring with `bp-no-maxhealth/` -- see ISOLATION CAVEAT |
| `cpp-solve/` | **FAIL** | L2I `bp_pawn_present` | `"id": "bp_pawn_present", "passed": false` | **MEASURED 2026-08-11: ran, credited at its named substring.** Runnable today (C++ only, 8 files, verbatim). L2 is expected to PASS -- that is the point -- which is what isolates the deliverable-format axis. `task_folder_exists` also reports false on the same run; both appear in the verdict block |
| `cpp-solve-with-bp/` | **FAIL** | L2I `resolved_pawn_is_blueprint` | `"id": "resolved_pawn_is_blueprint", "passed": false` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- the C++ half is committed, the Blueprint half is not, so today this directory equals `cpp-solve/` and would die at the wrong gate. Anti-gaming mode 2; the measured PASS-then-FAIL record is the glide section above |
| `bp-no-maxhealth/` | **FAIL** | L2 cp0, HOT-0 | `MaxHealth was not initialized: read ` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP pawn with the MaxHealth initialization removed and Health left initialized, one value |
| `bp-no-mesh/` | **FAIL** | L2 cp0, HOT-7 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP pawn with the Mesh component's skeletal mesh cleared, one property. HOT-0 passes first, so this leg isolates the visibility axis alone |
| `bp-instant/` | **FAIL** | L2 last cp, HOT-2 | `the restore was not periodic: Health did not keep rising in steps (A1=` | **MEASURED 2026-08-11: ran, credited at its named substring.** (was: blocked on asset authoring) -- planned as the reference BP effect with its duration policy switched to Instant and its whole amount applied once, so both rise steps read zero while the total stays inside the disclosed band and HOT-4 cannot take the credit |

---

## ISOLATION CAVEAT -- `empty` and `bp-no-maxhealth/` share one named FAIL

Both are predicted to land on HOT-0's `MaxHealth was not initialized: read `.
The collision is irreducible: HOT-0 is the FIRST gate in the fixture, and the
generic scaffold pawn an empty submission resolves to has an uninitialized
MaxHealth for exactly the reason `bp-no-maxhealth/` removes the initializer on
purpose. Any variant targeting a task's first gate collides with `empty`, which
is why the substring oracle exempts the `empty` leg from its pairwise uniqueness
matrix (`matrix_oracle.is_isolation_leg`).

It is a collision, not a duplicate: `empty` reaches HOT-0 incidentally, while
`bp-no-maxhealth/` is a behaviourally COMPLETE Blueprint solve -- periodic
restore, correct duration, correct total, clamp, mesh -- whose single defect is
one missing initializer. The same caveat is recorded, for the same reason, in
`../../gp-heal-over-time-cpp/discrimination/MATRIX.md`.

## Named-substring provenance (every literal above, traced to source)

Deliberately a bullet list, not a table -- see the MATRIX LAYOUT LAW banner.
Line numbers are into
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/HealOverTimeFunctionalTest.cpp`
with the adjacent string-literal concatenation collapsed.

- `MaxHealth was not initialized: read ` -- lines 157-161 (HOT-0). The literal
  STOPS immediately before `%.1f`, hence the trailing space. Do not extend it to
  `read 0.0`: a value is not a literal and would be unmatchable.
- `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn`
  -- lines 197-198 (HOT-7). Placeholder-free, and byte-identical in all five
  fixtures of this family (glide, poison, health-ops, heal-over-time,
  double-jump).
- `the restore was not periodic: Health did not keep rising in steps (A1=`
  -- lines 358-362 (HOT-2). The literal stops immediately before the first
  `%.1f`, hence the trailing `A1=`.
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

- **L2 -- inherited byte-identically from `gp-heal-over-time-cpp`.** At cp0,
  HOT-0 MaxHealth initialized to 100 read before any trigger and before any
  fixture write, then HOT-7 the visible character. Then, across three legs and
  ten checkpoints: HOT-1 the restore is an activatable ability granted by tag
  (and HOT-1c that every one of the three activations landed), HOT-2 the restore
  is periodic across two congruent 1.5 s rise windows, HOT-3 it STOPS inside the
  post-band stop window, HOT-4 the total restored sits inside the disclosed
  10-40 band, HOT-5 the clamp gate read on BOTH the current and the base value,
  HOT-6 the at-max no-op. Every gate returns on failure, so a submission is
  judged by the FIRST one it trips.
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
3. **All inherited gaming modes** (AG-1..AG-7 of the `-cpp` task) -> the
   inherited L2 gates, whose nine committed C++ overlays are measured on the
   `-cpp` twin. Three of them are planned here as `bp-*` Blueprint deltas so the
   BP authoring path is exercised on the same axes.

## Asset specs for every BLOCKED row (the serial editor pass)

Bullet list on purpose (MATRIX LAYOUT LAW). Package paths are given as content
paths; the submission overlay mirrors them under
`<variant>/Content/Tasks/gp-heal-over-time-bp/`.

- `cpp-solve-with-bp/` -- **its Blueprint half is a VERBATIM COPY of whatever
  `../reference/Content/Tasks/gp-heal-over-time-bp/` ships.** Copy every asset,
  unmodified. That is precisely the recipe both shipped twins used
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
- `bp-no-maxhealth/` -- a full copy of the reference's asset set with the pawn
  Blueprint's **MaxHealth initialization removed** and its Health initialization
  left exactly as the reference has it. Every other asset copied byte-for-byte
  so the periodic effect, the clamp and the mesh come along and the leg's only
  defect is the missing cap.
- `bp-no-mesh/` -- a full copy of the reference's asset set with the pawn
  Blueprint's mesh component **skeletal mesh cleared to None**. Nothing else.
- `bp-instant/` -- a full copy of the reference's asset set with the restore
  effect's **duration policy switched from a periodic, duration-limited shape to
  Instant**, and its whole amount applied in that single application. The total
  must stay inside the disclosed 10-40 band, or the leg dies at HOT-4 instead of
  HOT-2 and stops isolating the periodicity axis -- the `-cpp` twin's `instant/`
  overlay uses a single application of 25 and is the shape to mirror.

**Authoring hazard, learned on `gp-poison-dot-stack-bp`:** the visible-character
gate HOT-7 fires at cp0, before every later gate. A `bp-*` pawn authored from
scratch without an assigned mesh FAILs at
`the character is not visibly represented` instead of its intended gate, and
`cb discriminate` correctly reports `wrong-reason`. Author each one as a
ONE-PROPERTY delta off `../reference` so the mesh always comes along.

## Blockers (the sweep cannot run until all of these are true)

- The `-bp` task spec, its `## Verifier introspection` wiring, and
  `tools/verify-single/introspect/gp_heal_over_time_bp.py` must exist. A spec
  that declares an L2I leg whose script is missing produces a layer
  `status: "error"`, which routes to HARNESS-ERROR (exit 7) -- a non-graded
  verdict, not a discrimination result.
- Every Blueprint asset named above must be authored and committed.
- **The reference's own feasibility is an open question on this family, and it
  is worth settling before the decoys are authored.** HOT-5 requires the restore
  to be clamped in the BASE value as well as the current one, and the `-cpp`
  reference gets that from `PreAttributeChange` + `PostGameplayEffectExecute` --
  plain `UAttributeSet` virtuals, not `BlueprintNativeEvent`s, so a Blueprint
  attribute set cannot override them. If a pure-Blueprint deliverable cannot
  clamp the base value, the twin is not winnable as prompted and no decoy here
  can rescue it. This does NOT block `cpp-solve-with-bp/`, whose Blueprint half
  need only satisfy the three existence checks, but it does block
  `../reference`.
- The runner grades from **git HEAD**. Anything uncommitted needs
  `--substrate-from-live`, and nothing may be committed while a sweep runs.
- The engine must be free: UBT's mutex is keyed on the ENGINE INSTALL, so a
  contended build returns exit 1 with no compile errors, which reads exactly
  like a variant failing L1.

## Re-validate -- what promotes a row from UNVALIDATED to MEASURED

Once the blockers clear, the single command is

```sh
cb discriminate gp-heal-over-time-bp
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
leg's `[HEALOVERTIME-FINAL]` line beside it.

## Parser self-check

This file was parsed with the repo's own parser
(`aura_rig.discriminate.parse_matrix`) before it was finished, and the result is
recorded here so a future editor can tell instantly whether an edit broke it:
**7 rows** -- `reference`, `empty`, `cpp-solve`, `cpp-solve-with-bp`,
`bp-no-maxhealth`, `bp-no-mesh`, `bp-instant` -- with `reference` carrying
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
re-run per variant here. Three of them are planned as `bp-*` rows above; HOT-1,
HOT-3, HOT-4, HOT-5 and HOT-6 have no `bp-*` leg planned -- and HOT-5 is the
gate this family exists for, so if the clamp question in **Blockers** resolves
in favour of a Blueprint route, a `bp-current-only-clamp/` leg mirroring the
`-cpp` twin's is the first one to add.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every L2 token is a verbatim contiguous span (adjacent string-literal concatenation collapsed, never
crossing a printf placeholder — seven tokens end in a load-bearing trailing space (four) or `=` (three) for that reason) of a
`FinishTest(EFunctionalTestResult::Failed, ...)` literal in the shared fixture
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/HealOverTimeFunctionalTest.cpp`
(HOT-7's literal lives in the hoisted base,
`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`). Every L2I token is a
literal run of the CRAFTBENCH-INTROSPECT-JSON verdict line emitted by
`tools/verify-single/introspect/gp_heal_over_time_bp.py` via `_bp_variant_lib.py` (`json.dumps`, default
separators). The gate name (HOT-n / check id) is the durable join key.

Skip-range convention: every "HOT-0..HOT-n fire first" skip range below implicitly also includes the
OTHER cp0 gate HOT-7 (HealOverTimeFunctionalTest.cpp:184-186, which FinishTests before any final
assert) and the per-checkpoint pawn-resolve / null-ASC preamble routes (:91/:97) — the final asserts
HOT-1..HOT-6 run only if the run reaches cp9; the authoritative gate order is the source.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the restore is an **activatable ability** the game can start (not a Tick/BeginPlay fake, not an on-spawn effect) | fully | HOT-1 activation — `an ability tagged Ability.HealOverTime was granted but did NOT activate on TryActivateAbilitiesByTag`; and HOT-1c, every one of the three per-leg activations must land — `an ability tagged Ability.HealOverTime refused a later activation: ` (trailing space; next char is `%d`) | pawn/ASC never resolves (`pawn did not spawn/resolve`), or a cp0 gate (rows 8, 14) FinishTests first — the final asserts HOT-1..HOT-6 run only if the run reaches cp9 (t=23.2 s) | mechanism entirely free: duration GameplayEffect, ability timer loop, anything `TryActivateAbilitiesByTag` reaches; the ability may end immediately as long as its effect keeps running |
| 2 | tagged `Ability.HealOverTime` and added to the pawn's granted abilities | fully | HOT-1 grant count — `no activatable ability tagged Ability.HealOverTime on the pawn`; plus L2I — `"id": "bp_pawn_grants_bp_ability", "passed": false` (>= 1 Blueprint-generated class in GrantedAbilities AND zero native ones) | L2 half: as row 1; L2I half: never skipped — all five checks emit on every run (constant denominator; a missing BP pawn degrades this check to a `no BP pawn resolved` FAIL, not a skip) | extra tags on the ability and extra BLUEPRINT abilities in the array are free; a native ability granted alongside fails the zero-native half |
| 3 | raises Health **repeatedly — about once per second** | partially | HOT-2 — `the restore was not periodic: Health did not keep rising in steps (A1=` (two congruent 1.5 s rise windows, (trigger+1.1, +2.6] and (+2.6, +4.1], must each rise by more than RiseEpsilon) | rows 8, 14, 1 fire first (gates return on first failure in order HOT-1 -> 1c -> 2 -> 3 -> 4 -> 5 -> 6) | the ~1 s cadence is NOT pinned: any period that lands >= 1 tick in each 1.5 s window (roughly <= 1.5–2 s) passes; irregular step sizes pass — pure direction predicate with a noise floor, no rate bar |
| 4 | it must not be a single instant restore | fully | HOT-2 — same token as row 3: an instant restore rises once then reads flat, so its second step is 0 | as row 3 | two ticks inside ~3 s already clear both windows |
| 5 | runs "roughly five seconds"; any duration in the disclosed 4–7 s band accepted | partially | HOT-3 gates the UPPER edge only — the stop window opens at trigger+7.1, past the band top (token in row 6) | as row 3, plus HOT-2 fires first | the band FLOOR is unenforced: a ~3 s duration still ticks in both rise windows, stays in the 10–40 band, and is silent before +7.1 — it passes despite sitting under the stated 4 s minimum (shortest passing duration is ~2.7 s, whatever last tick clears the second rise window) |
| 6 | then **stops** — must not keep restoring forever | fully | HOT-3 — `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` | HOT-0/HOT-7/HOT-1/HOT-1c/HOT-2 fire first | a residual rise <= StopEpsilon (0.25) across the 2.1 s stop window is absorbed as jitter |
| 7 | each application restores a total of **10–40** Health | fully (application 1 only) | HOT-4 — `the total restored is outside the stated 10-40 band: Health went 40.0 -> ` (trailing space; next char is `%`) — Leg 1 preset 40 vs ATail | HOT-0..HOT-3 fire first | only the FIRST application is totalled; Legs 2–3 deliberately run into the cap, so a magnitude that varies per application is measured once |
| 8 | MaxHealth is **100** and the pawn must initialize it to 100 | fully | HOT-0 — `MaxHealth was not initialized: read ` (trailing space; next char is `%`) — read at cp0 (t=0.5 s), BEFORE any trigger and any fixture write, against 100 +/- MaxHealthEpsilon | only a pawn/ASC resolution failure precedes it — effectively unconditional, the fixture's first gate | the init route is free: `InitStats` on BeginPlay, an AttributeMetaData DataTable, or an instant init GameplayEffect all conform |
| 9 | Health never exceeds MaxHealth — neither the value read back nor the underlying stored value | fully | HOT-5, the dual read — `the restore pushed Health past its cap: current=` — cp7 (leg-2 trigger+5.1) reads CURRENT and BASE at one instant, both against the cp0-pinned cap + ClampEpsilon | HOT-0..HOT-4 fire first; a refused leg-2 activation cannot void it silently — HOT-1c fails by name instead | a TRANSIENT over-cap between checkpoints is invisible (one sampling instant); overshoot <= ClampEpsilon; raising MaxHealth at runtime does not help — the gate compares against the cp0 read and only LOGS the live value (L2maxLive) |
| 10 | activating at full health leaves Health at 100 — must not push past it, must not lower it | fully | HOT-6 — `activating the restore at full health changed Health: 100.0 -> ` (trailing space; next char is `%`) — gated in BOTH directions on the CURRENT value at leg-3 trigger+5.1 | HOT-0..HOT-5 fire first; a refused leg-3 activation is named by HOT-1c | the leg-3 BASE value is reported but not gated — deliberate, so base overshoot fails at HOT-5 alone and one defect gets one named gate |
| 11 | deliver **entirely as Blueprint assets**; do not add or modify any C++ source | partially | L2I — `"id": "resolved_pawn_is_blueprint", "passed": false` (no agent-authored native subclass of ACraftBenchCharacter may exist; exemption by exact /Script/ path of the committed abstract scaffold only) plus the zero-native half of `bp_pawn_grants_bp_ability` (row 2) | never skipped — all five L2I checks emit on every run; an empty submission scores 0/5 | **the family's sharpest gap:** a native `UGameplayModMagnitudeCalculation`, `UAttributeSet` or `UGameplayEffect` subclass referenced FROM Blueprint assets is not swept — a C++ clamp behind a genuine BP pawn+ability passes all five checks (the V2.1 native-decoy sweep is NOT BUILT; task.md anti-gaming note 3 records this as ARGUED, NOT DEFENDED) |
| 12 | saved under `Content/Tasks/gp-heal-over-time-bp/` — "the only path the verifier looks in" | partially | L2I — `"id": "task_folder_exists", "passed": false` (/Game/Tasks/gp-heal-over-time-bp/ exists, >= 1 asset) and `"id": "bp_pawn_present", "passed": false` (the qualifying pawn must live IN that folder); the L2 fixture's Asset-Registry resolution only scans /Game/Tasks | never skipped (constant denominator) | only the PAWN's location is gated: the ability, effect, magnitude calc or init DataTable saved under any other asset-writable prefix (`Content/Blueprints/`, `Content/Abilities/`, ...) passes every check while violating the prompt's folder clause |
| 13 | a Blueprint subclass of the provided character | fully | L2I — `"id": "bp_pawn_present", "passed": false` (a Blueprint whose GeneratedClass derives from ACraftBenchCharacter); the L2 fixture independently resolves by that same derivation plus the preferred tag `Ability.HealOverTime` | never skipped (constant denominator); the L2 resolution failure surfaces as `pawn did not spawn/resolve` | asset naming is entirely free (identity is pre-declared path + derivation, never name); parenting the OTHER scaffold (`CraftBenchBareCharacter`) fails here and again at HOT-0 with no Health to read |
| 14 | visibly represented: one of the provided mannequin skeletal meshes (under `/Game/Characters/`) assigned as the mesh | fully | L2 HOT-7 — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (base-class check; hidden-in-game and zero-scaled meshes get sibling literals in the same family) plus L2I — `"id": "pawn_visibly_represented", "passed": false` (the assigned SkeletalMesh's asset path must live under the read-only /Game/Characters/ pool) | HOT-7 is skipped when any of the three cp0 gates ahead of it FinishTests first: the per-checkpoint preamble's pawn-resolve (`pawn did not spawn/resolve`) or null-ASC (`pawn has no AbilitySystemComponent`) checks, which run before the cp0 switch, or HOT-0 at the same checkpoint; the L2I half is never skipped | which mannequin, scale, pose, animation — all free; the L2 half alone accepts ANY assigned mesh (an empty placeholder under the writable path) — the pool anchoring that closes that is L2I-only |
| 15 | Blueprint assets "created in the editor" | **NOT ASSERTED** | no gate reads asset provenance — both layers verify structure (derivation, grant array, mesh path), never how the `.uasset` bytes were produced | — | a `.uasset` authored headlessly/programmatically or copied from another project passes both layers unexamined; near-immaterial (the structural checks capture the clause's intent), but the prompt states it and nothing asserts it |

Layout-law compliance (see the MATRIX LAYOUT LAW banner above): every first cell in this table is a
bare integer — no leg name, no `/` — and no column is named "substring" or "message", so
`aura_rig.discriminate.parse_matrix` registers no leg from it; re-run the parser self-check after any
edit regardless.
