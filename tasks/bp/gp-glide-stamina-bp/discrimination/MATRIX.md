# gp-glide-stamina-bp — discrimination matrix

> **✅ SUBSTRATE MIGRATION 2026-08-05 — RE-VALIDATION RESOLVED 2026-08-06 at
> `dfee504`.** The binary `.uasset`s were ported to ThirdPerson **headlessly**
> (copy + scratch-only CoreRedirects + editor-Python CDO surgery + resave — no
> live editor). The `../reference` row is **measured PASS at HEAD** on that
> commit (L2I 5/5 including `pawn_visibly_represented` via the native
> `SKM_Manny_Simple`), and 2026-08-07 a token-free `cb refgate` re-certified it
> **PASS (1/1, 154 s)** at repo `61e4c98` before the 9-rep model matrix
> (an internal eval report (not shipped) — opus-5 3/3, grok-4.5 0/2,
> deepseek-v4-pro 0/1, every failure at L1 pass / L2I pass / **L2 fail**, which
> is this matrix's axes working as designed on live agents). **`--wip` is no
> longer needed** — the assets are committed, so the ladder grades from git
> HEAD. Editor-work handoff
> an internal working note (not shipped) is spent; read it as
> history.
>
> _History:_ the `cpp-solve*/` C++ sources were re-homed to the
> `Source/ThirdPerson/` writable prefix (content unchanged — the scaffold class
> names are identical across substrates) while the binaries stayed
> CraftBenchTemplate-bound, which is what this banner used to block on. Expected
> outcomes were unchanged then and are unchanged now — every gate below was
> ported verbatim. The 2026-07-17 validation stamps below refer to the
> CraftBenchTemplate era.
>
> **One measured semantics change NOT yet reflected in the table below**
> (2026-08-06, `ca7f20c`): the shared fixture gained a checkpoint-0
> visible-character gate that fires BEFORE the last-checkpoint GAS gates. On the
> `-cpp` twin an EMPTY submission was measured failing at
> `the character is not visibly represented: ...` instead of `granted=0`. This
> matrix's empty row still records `granted=0`, and the `-cpp` MATRIX carries
> BOTH readings in two different banners — treat the empty row's exact substring
> as UNRESOLVED until someone re-runs the empty leg here (see
> `../../gp-glide-stamina-cpp/discrimination/MATRIX.md`). Either way it is a
> named, deterministic FAIL, so the row's verdict (FAIL) is not in doubt.

VALIDATED on a live runner 2026-07-17 (Windows + UE 5.8): `cb discriminate
--task gp-glide-stamina-bp` = **1/1** — `../reference` PASS, empty FAIL,
`cpp-solve/` FAIL at the named L2I `bp_pawn_present` check. Also PASS in the
`cb batch-eval --references all` gate (`runs/aura-product-eval/batch-eval-20260717-183912` — that run-dir name is `batch_eval.DEFAULT_RUN_SUBDIR`, a legacy label, not a vendor lane,
16/16 effective). The editor-authored BP reference (binary `.uasset`s under
`reference/`, see `../REFERENCE-NOTE.md`) is committed. L2 legs + gates are
identical to `gp-glide-stamina-cpp` (already validated); the new discrimination axis
here is the **L2-introspect "deliverable is Blueprint" gate**.

RE-VALIDATED on the ThirdPerson substrate 2026-08-06 at `dfee504` — but only
the `../reference` row. See the per-row "Last measured" column: three of the
four rows still carry pre-migration stamps, and one of those three
(`cpp-solve-with-bp/`) has an unported binary. Treat this matrix as **1 row
measured at HEAD, 3 rows argued from the pre-migration era.**

## Matrix

| Submission | Overall | Fails at | Expected message | Last measured |
|---|---|---|---|---|
| `../reference` | **PASS** | — | all L2 gates green + all L2I checks pass (L2I 5/5) | **2026-08-06 `dfee504`, at HEAD on ThirdPerson**; refgate PASS 1/1 again 2026-08-07 |
| empty (no overlay → base scaffold) | **FAIL** | L2 cp0, visibility gate | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | **MEASURED 2026-08-16: the banner's prediction confirmed live** — the run-2b sweep credited this leg wrong-reason against the old GAS-gate substring (its 2026-07-17 measurement predates the 2026-08-06 cp0 visibility gate); the scaffold pawn carries no assigned mesh, so the cp0 gate fires first, exactly like every sibling family's empty leg. The GAS gate is still probed by any meshed-but-abilityless submission. |
| `cpp-solve/` | **FAIL** | L2I `bp_pawn_present` | `"id": "bp_pawn_present", "passed": false` | 2026-07-17, CraftBenchTemplate era (C++ sources re-homed to `Source/ThirdPerson/`, content unchanged) |
| `cpp-solve-with-bp/` | **FAIL** | L2I `resolved_pawn_is_blueprint` | `"id": "resolved_pawn_is_blueprint", "passed": false` | 2026-08-03, **CraftBenchTemplate era — NOT re-measured after the migration; see the decoy note below** |

> **⚠ UNRESOLVED 2026-08-08 — the `cpp-solve-with-bp/` decoy was left behind by
> the port.** `dfee504` ported the **reference** binaries only (its own byte-scan
> claim is scoped to "all 8 assets" = the two references). Byte-verified on disk
> 2026-08-08: all four
> `cpp-solve-with-bp/Content/Tasks/gp-glide-stamina-bp/*.uasset` still carry
> `/Script/CraftBenchTemplate` references and **zero** `ThirdPerson` ones — i.e.
> the decoy's Blueprint half does not resolve on the current substrate.
>
> The row's **verdict** (FAIL) is not in doubt. What is in doubt is the **gate**:
> the L2I chain runs `task_folder_exists` → `bp_pawn_present` →
> `bp_pawn_grants_bp_ability` → `resolved_pawn_is_blueprint`, so an unloadable
> BP would trip `bp_pawn_present` FIRST and the variant would stop isolating the
> decoy axis it exists for — a FAIL for the wrong reason, this repo's worst
> defect class. **This has not been re-run and must not be reported as
> measured-at-HEAD.** Fix is cheap and needs no editor: re-run `dfee504`'s
> headless port recipe over the two `cpp-solve-with-bp/Content/` trees, then
> re-run the ladder.

`cpp-solve-with-bp/` is the **decoy**: `cpp-solve/`'s C++ shipped ALONGSIDE the
reference's Blueprint deliverable. Measured 2026-08-03 on UE 5.8 **and on the
CraftBenchTemplate substrate** (two days before the migration), before and
after the fix:

| verifier | L1 | L2 | L2I | overall |
|---|---|---|---|---|
| before (3 checks) | PASS | PASS 1/1 | **PASS 3/3** | **PASS** ← the false pass |
| after (4 checks) | PASS | PASS 1/1 | **FAIL 3/4** | **FAIL** |

The C++ pawn wins `ResolveAgentPawnClass` (native candidates are enumerated
before Blueprint ones), so **L2 graded the C++ solve while L2I graded the
Blueprint** — every gate green on a submission whose prompt says *"Do not add or
modify any C++ source for this task."* The reference still scores 4/4 and an
empty submission still scores 0/4, so the new check is not a dead gate. Offline
oracle: `tools/verify-single/tests/test_introspect_bp_variant_resolution.py`.

## Deterministic gates (what flips PASS/FAIL)

- **L2 (inherited unchanged from `gp-glide-stamina-cpp`)**: granted+activated,
  descent slowed vs same-run free-fall baseline, Power strictly drains to ~0,
  descent speeds back up after exhaustion.
- **L2I (new, the `-bp` axis)**: `task_folder_exists` →
  `bp_pawn_present` (a Blueprint under `/Game/Tasks/gp-glide-stamina-bp/`
  whose GeneratedClass derives from `ACraftBenchCharacter`) →
  `bp_pawn_grants_bp_ability` (its GrantedAbilities carries a
  Blueprint-generated ability class).

## Anti-gaming modes (defended by the gates)

1. Solve in C++ (the `cpp-solve/` variant — the original task's C++ reference
   verbatim: behaviorally correct, passes L2) → **L2I `bp_pawn_present`**.
2. C++ solve shipped alongside ANY conforming Blueprint (the
   `cpp-solve-with-bp/` variant) → **L2I `resolved_pawn_is_blueprint`**. This
   was the documented hole; it is closed and measured, not argued. The check
   asserts no native subclass of the provided character exists at all, which is
   strictly stronger than mirroring the fixture's tag preference — for a `-bp`
   task any C++ subclass is already the violation, and a do-nothing BP shell is
   strictly easier to satisfy than the real Blueprint used here.
3. All original gp-glide-stamina-cpp gaming modes → the inherited L2 gates.

## Bounded coverage

`cpp-solve/` is the load-bearing new variant (it is the exact failure mode this
variant task exists to catch). The inherited L2 gaming modes are argued from
the original task's validated matrix, not re-run per variant.

# bp/gp-glide-stamina-bp — Requirements table draft (checklist §7)

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked L2 span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)`
literal in `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/GlideStaminaFunctionalTest.cpp`
(the checkpoint-0 visibility literal lives in the shared base,
`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`; thresholds are pinned in
`GlideStaminaFunctionalTest.h`). Every backticked L2I span is a check-id emitted by
`tools/verify-single/introspect/gp_glide_stamina_bp.py` (mesh probe shared via `_bp_variant_lib.py`), matched as
`"id": "<check>", "passed": false` in the CRAFTBENCH-INTROSPECT-JSON block. The whole L2/L2I gate family runs only
after L1 passes (registry `requires` short-circuit) — that global skip is not repeated per row.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | an ability carrying the gameplay tag `Ability.Glide` is granted on the pawn | fully | L2 final gate (1) — `no activatable ability tagged Ability.Glide on the pawn (GAS not implemented). granted=` | an earlier checkpoint FinishTest fired first (`pawn did not spawn/resolve`, the cp0 visibility gate, the cp1 starting-Power gate) | the tag may sit anywhere in the ability's activatable-tag set; extra unrelated abilities are free |
| 2 | the game can ACTIVATE the glide by that tag | fully | L2 final gate (2) — `was granted but did NOT activate on TryActivateAbilitiesByTag` | row 1 failed first (gates fan out in order 1→2→baseline→row 4's no-descent fan→3→4→5) | activating and then doing nothing — rows 3–5 exist to catch that |
| 3 | while falling, the character descends noticeably SLOWER than an unaided fall | fully | L2 final gate (3) — `descent was not slowed by the glide: min glide |vZ|=` (bar: min glide \|vZ\| <= 0.6 × the same run's pre-trigger free-fall \|vZ\|) | rows 1–2 failed; the verifier-environment baseline sanity fired (`no free-fall baseline:`); zero descending glide samples (routes to row 4's named FAILs) | the gate reads the MINIMUM over post-trigger samples, so a single one-checkpoint dip to 0.6× passes even if the rest of the glide is fast; 0.6× itself is a generous bar (a 40% slow counts as "noticeably slower") |
| 4 | the slow is a genuine DESCENT — not a hover, a rise, or a teleport | fully | L2 — `the pawn was never DESCENDING while the ability was active` (all post-trigger Power>0 samples had vZ >= 0) / `no gliding samples captured with Power>0` (ability did nothing) | at least one post-trigger sample with Power>0 is descending (then row 3 grades that sample set) | hovering at 8 of 9 checkpoints, provided one sample descends slowly — non-descending samples are excluded, not failed, once any descent exists |
| 5 | the ability DRAINS the Power resource while gliding | fully | L2 final gate (4) — `the Power resource did not drain while gliding (the glide consumed no stamina)` | rows 1–3 failed first; the baseline sanity fired (`no free-fall baseline:`); or row 4's named FAILs fired (`the pawn was never DESCENDING while the ability was active` / `no gliding samples captured with Power>0`) — both run before gates (3) and (4) in the fixture's final-assertion order. Only the submission's own drain counts: the verifier's forced zero is excluded via `bForcedExhaust` | any strict decrease > 0.5 of the 30-point verifier preset, observed at any single checkpoint — the drain's size and rate are unconstrained (see row 6) |
| 6 | the drain is STEADY ("steadily drains the Power resource" — a continuous rate over time) | **NOT ASSERTED** | none — gate (4) is a boolean "Power decreased at least once vs the value at trigger"; no gate reads the drain's shape, monotonicity, or rate | n/a | a one-tick lump-sum deduction (e.g. −1 Power on activation, then a free glide) satisfies gate (4); it even arms the forced-exhaustion write, so gate (5) still runs against it |
| 7 | when Power reaches ZERO, the slowed descent must END | fully (since the 2026-08-09 forced exhaustion + the 2026-08-11 fast-path removal) | L2 final gate (5) — `The glide ignored stamina exhaustion.` (verifier zeroes Power itself at cp6 t=3.1 when the drain has registered but not emptied, then requires the resume) | the drain never registered (Power drop <= 0.5) by cp6 — no forced zero, gate logs `[GLIDE-ADVISORY]` and SKIPs; or the post-exhaustion window < the 0.30 s `ResumeWindowFloor` — logs `[GLIDE-RESUME-DIAG] ... SKIPPED, not failed` | a drain slower than 0.5 units by t=3.1 escapes the gate entirely (documented residual: forcing exhaustion on an undemonstrated drain would credit the verifier's own write) |
| 8 | after exhaustion the character falls at its NORMAL rate again | partially | same gate (5) — the resume bar is a RATIO: final \|vZ\| >= 1.5 × the same run's min glide speed (`ResumeFactor`), never the free-fall speed | same skips as row 7 | releasing into a SECONDARY clamp at >= 1.5× the glide speed but well below free-fall (e.g. glide 300 → "resume" 460 vs free-fall ~1200) passes — deliberate: the ratio law exists because absolutes graded the drain rate and false-failed 4 measured conforming runs |
| 9 | the slow comes from the ACTIVE ability — not a permanent fall-speed change | fully (via row 7's machinery) | L2 gate (5) — same token: a permanent low-gravity/clamped pawn stays slow after the forced zero and FAILs `The glide ignored stamina exhaustion.` | same skips as row 7 — a permanent change paired with a drain that never registers rides the row-7 skip | nothing further while the drain registers; the teleport half of this prompt bullet is row 4's business |
| 10 | the deliverable is a BLUEPRINT pawn under `Content/Tasks/gp-glide-stamina-bp/` — a BP subclass of the provided character | fully | L2I — `task_folder_exists` (folder exists, >= 1 asset) then `bp_pawn_present` (>= 1 BP asset in THAT folder whose GeneratedClass derives from `ACraftBenchCharacter`) | never silently skipped: each check is try/except-isolated; downstream checks FAIL with detail `no BP pawn resolved` rather than skip | asset NAMES are free (identity is path+derivation by design); extra junk assets in the folder are tolerated |
| 11 | the BP pawn's granted abilities carry the (Blueprint) glide ability | fully | L2I — `bp_pawn_grants_bp_ability` (>= 1 GrantedAbilities entry whose class path is under `/Game/`, AND zero `/Script/` entries — the 2026-08-10 native-ability-hole closure) | FAILs (not skips) with `no BP pawn resolved` when row 10 failed | whether that granted BP ability is the one that actually glides is L2's business (rows 1–9); if the real ability is C++ and GRANTED on the pawn, this check's OWN zero-`/Script/`-entries clause rejects it (row 12's `_native_pawn_subclasses` sweep cannot — it sweeps native PAWN subclasses only, and a native ABILITY is not a pawn, per the grader's own hole-closure comment); a decoy BP ability next to a real BP ability elsewhere stays invisible here |
| 12 | "Do not add or modify any C++ source for this task." | partially | L2I — `resolved_pawn_is_blueprint` (NO native subclass of `ACraftBenchCharacter` may exist; fail-closed when the reflection sweep cannot see the scaffold) + the zero-`/Script/`-entries clause of `bp_pawn_grants_bp_ability` | never silently skipped (fail-closed by construction); the committed abstract `CraftBenchBareCharacter` base is exempt by exact `/Script/` path | agent C++ that is neither a pawn subclass nor a granted-ability class — a BlueprintCallable function library, a custom MovementComponent, or edits to the stock ThirdPerson sources — compiles at L1, is sandbox-accepted (`Source/ThirdPerson/` is agent-writable), and is invisible to both checks; a thin BP ability calling that C++ passes every gate. **HOLE** |
| 13 | the solution is delivered ENTIRELY under `Content/Tasks/gp-glide-stamina-bp/` (all assets) | partially | L2I — `bp_pawn_present` is scoped to `/Game/Tasks/gp-glide-stamina-bp` (the PAWN's location is pinned) | see row 10 | the ability BP (and any helper assets) may live under ANY `/Game/` path the sandbox accepts — `Content/Blueprints/`, another task's folder — since `bp_pawn_grants_bp_ability` only requires the `/Game/` prefix. **HOLE** (minor: the behavioral deliverable still resolves) |
| 14 | the pawn STARTS with some Power to spend | fully | L2 checkpoint-1 gate — `the pawn does not start with any Power to spend (Power=` (read at t=1.0, before the cp2 trigger overwrites Power) | pawn unresolved, or the ASC is missing — deliberately routed to gate (1)'s named FAIL instead of a misleading Power message | any starting value > 0.5 — the verifier presets Power to 30 at the trigger, so the AMOUNT chosen never affects the drain measurement |
| 15 | the character is VISIBLY represented — a provided mannequin skeletal mesh (under `/Game/Characters/`) assigned as its mesh | fully (two layers, deliberately redundant) | L2 checkpoint-0 gate (base class) — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (sibling literals also reject hidden-in-game and ~zero-scale meshes) + L2I — `pawn_visibly_represented` (the assigned SkeletalMesh's asset path must start with `/Game/Characters/` — the pool anchor, ungameable because that content is deny-listed) | cp0 fires only if the pawn resolved (else `pawn did not spawn/resolve`); the L2I check FAILs (not skips) with `no BP pawn resolved` when row 10 failed | WHICH mannequin is free (Manny/Quinn/any pool asset); no animation is required — a T-posing statically-posed character passes both layers |

### Holes this table found (escalation list, not papered over)

- **Row 6 (NOT ASSERTED):** "steadily drains" — no gate reads the drain's shape; a single lump-sum
  deduction passes gate (4) and still arms gate (5).
- **Row 12 (partial):** the C++-source ban is only enforced for pawn subclasses and granted-ability
  classes; a C++ helper (function library / movement component / stock-source edit) called from a
  thin BP escapes both L2I checks.
- **Row 13 (partial):** only the PAWN's asset path is pinned to the task folder; the ability BP may
  be saved anywhere under `/Game/`.
- **Row 7 (documented skip residual):** a drain of <= 0.5 units by t=3.1 means stop-on-exhaustion is
  never gated that run (advisory log only).
- **Row 8 (documented residual):** "normal rate again" is graded as >= 1.5× the run's own glide
  speed, not as a return to free-fall speed — a secondary clamp above that ratio passes.
