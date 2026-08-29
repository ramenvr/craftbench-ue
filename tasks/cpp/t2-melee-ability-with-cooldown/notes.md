# t2-melee-ability-with-cooldown — build contract + design notes

Task-implementor working notes (not agent-visible; agent surfaces are composed
from the substrate trees only). Provenance: a source row "Melee attack (GAS)"
out of an earlier internal task list (Verification cell EMPTY — the
acceptance criteria are authored here, footstep precedent). Cuts: the
animation-montage clause (no anim baseline on CraftBenchTemplate; the source row's
"reuse the jump animation" is ThirdPerson-specific; montages are unobservable
headless) and the J-key binding (headless PIE has no key events; the ability
TAG is the input seam — gp-poison precedent). The debug-print clause is kept
advisory, never gated.

## Build contract

| artifact | contract |
|---|---|
| Shared tag registry | `CraftBenchGameplayTags.{h,cpp}` gain `AbilityMelee()` / `UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Melee, "Ability.Melee")` — the established pattern (Launch/Fly/Glide/Poison precede it). The fixture references the tag through the registry header (a `Tasks/` subfolder header is NOT includable cross-module; the registry root header is — poison fixture precedent). |
| Scaffold | `Tasks/<id>/MeleeDummyActor.{h,cpp}`: tag `MeleeDummy`, `float Health = 100` (EditAnywhere), StaticMesh root (engine cylinder), **Mobility=Movable** (the fixture repositions placed instances — a Static root refuses SetActorLocation; an earlier review lesson), collision OFF (a passive target must not block or bump the pawn). No behavior. |
| Fixture | `AMeleeCooldownFunctionalTest : ACraftBenchPawnFunctionalTest` — resolve-by-tag + spawn/possess is base-owned; `PreferredAbilityTag() = Ability.Melee` so the resolver never picks another task's pawn. Schedule {0.6, 1.2, 1.8, 3.4, 4.0}. |
| Map | `Content/Maps/<id>/L_MeleeCooldown.umap`: floor (engine cube, scale 30x30x1, top at Z=+2) + TWO placed `AMeleeDummyActor`s (authored spots are cosmetic — the fixture repositions both) + the fixture actor. No PlayerStart/GameMode: the base spawns + possesses the pawn. Recipe: `aids/author_L_MeleeCooldown.py`. |
| Reference | 4 files under `reference/Source/CraftBenchTemplate/Tasks/<id>/`: `MeleeAbility` (tag + CommitAbility + a **hand-rolled 2.0s cooldown gate** — `LastStrikeTime` + world game-time; refused triggers never re-arm — + reach 250 / facing cos 0.5 sweep + reflection Health write of 25), `MeleePawn` (grants). **The GAS-idiomatic cooldown-GE route is REJECTED**: granting tags on a GE needs `UTargetTagsGameplayEffectComponent`, and `FindOrAddComponent` in a GE constructor is a guaranteed engine Fatal on UE 5.8 (`AddComponent` → `NewObject(this)` → `FObjectInitializer::AssertIfInConstructor`, tripped at CDO registration on module load — adversarial review, 2026-07-30). The hand-rolled gate is behaviorally identical and timing-deterministic. |

## Fixture design

- **Fixture-owned geometry.** At cp0 the two pinned targets are placed
  relative to the SETTLED pawn: near = pawn + forward*150 (inside the
  disclosed ~250 reach), far = pawn + forward*900. Map placement and floor
  height never need re-calibration; both targets sit along the facing so the
  far gate discriminates on reach, not on facing alone (a facing-only filter
  still damages the far target and fails).
- **Trap inside the cheat window (tp2 lesson).** Cooldown runs 0.6→2.6. The
  re-trigger lands at 1.2 and the hold-check at 1.8 — both INSIDE. A
  no-cooldown solution's second strike lands ~1.2 and is caught at 1.8,
  before a "short cooldown" could expire. The recovery trigger at 3.4 has
  0.8s margin past expiry.
- **Delta gates only.** The agent owns the scaffold source, so Health=100 is
  not trustworthy as an absolute; every gate is a delta from a
  fixture-captured baseline, plus the equal-baseline symmetry check at cp0
  (catches asymmetric pre-damage without trusting any absolute).
- **Pinned pointers, name-sorted, BEFORE the pawn exists.** The two targets
  are resolved and pinned at the TOP of PrepareTest, before
  `Super::PrepareTest()` spawns the agent pawn — so nothing the pawn's
  BeginPlay spawns can ever be a pin candidate. Residual (documented in
  MATRIX.md's coverage note): the agent owns the scaffold source, so
  scaffold-BeginPlay decoys and self-scripted Health remain possible; the
  delta/symmetry/far-flat gates plus the GAS gates carry that case — total
  scripted-trace immunity is NOT claimed.
- **Empty-leg channel**: cp0's `granted >= 1` / activation checks (poison
  wording mold). A granted-but-inert ability gets the distinct
  "did NOT activate" message.
- **Blocked triggers must not re-arm.** The GAS commit path naturally
  satisfies this (a refused CanActivate never applies the cooldown GE); a
  hand-rolled timer that restarts on refused triggers pushes expiry past 3.4
  and dies at cp4. Covered by the hidden invariant, no dedicated variant.

## Dead-gate audit

- **Cooldown 2.0s vs engine default**: there is no default cooldown — an
  ability with no cooldown GE activates every trigger, which FAILS cp2. The
  gate excludes the default. ALIVE.
- **Reach/facing vs the sloppy default**: the natural sloppy implementation
  (damage every `GetAllActorsWithTag` hit) FAILS the far gate. ALIVE.
- **Damage >= 1.0 (MinDamage)**: a zero-damage "strike" fails cp1. The
  reference's 25 has 24 points of margin. ALIVE.
- **Equal-baseline epsilon 0.1**: both placed instances share the class
  default whatever its value — the check gates asymmetry, not the absolute,
  so an agent-edited default cannot dead-gate it. ALIVE (bounded: symmetric
  pre-damage passes cp0, but symmetric pre-damage doesn't help any gaming
  shape — every later gate is a delta).

## Calibration checklist (fill from the first live legs)

0. **Verdict-taxonomy honesty (wave-1 convention):** the fixture's three
   `HARNESS-PRECONDITION`-prefixed `FinishTest(Error)` paths GRADE AS AGENT
   FAIL today (automation Error lands as state Fail in index.json and
   l2_pie.py counts it; no runner rule reads fixture messages). The prefix
   expresses the semantics and marks the log for the future runner-side
   exit-7 routing rule; it does not route today.
1. **RESOLVED (review, 2026-07-30): cooldown mechanism.** The GE-component
   route was rejected pre-build as a guaranteed 5.8 module-load Fatal (see
   Build contract). The shipped hand-rolled gate is plain world game-time
   arithmetic — `GetWorld()->GetTimeSeconds()` under `-deterministic -FPS=60`
   advances in fixed steps, so there is NO GAS timing dependency left; the
   2.6 expiry lands between cp4 (2.5) and cp5 (3.4) by construction. Confirm
   on the reference leg via the [MELEE] calib lines.
2. (folded into 1 — no separate GE timing question remains)
3. Pawn settle: spawn (0,0,120) over floor-top Z=+2 → capsule rest ~Z=90 well
   before cp0=0.6 (30uu fall). Confirm no residual bounce at cp0 (geometry is
   fixture-relative, so only a pawn still FALLING at 0.6 matters — it would
   place targets at falling height; check the calib line's near/far reads).
4. Reflection Health read/write on the scaffold instance (fixture read at
   cp0-cp4; reference write in ActivateAbility) — both use
   `FindFProperty<FFloatProperty>`; confirm on the reference leg.
5. `TriggerAbilityByTag` return + `bAbilityActivated` latch semantics for a
   commit-refused activation (the 1.2 re-trigger): the latch was set at cp0,
   so cp1's re-trigger needs no assertion — only the health trace gates.
   Confirm no spurious activation notification fires on the refused commit.
6. Variant `no-cooldown` second strike lands by cp2 (activation at 1.2 damages
   instantly in this reference shape — confirm on the variant leg).
7. The 2.2s re-trigger (cp3) is refused with the shipped gate (window ends
   2.6) and its hold-check at 2.5 stays flat — 0.1s margin to expiry is 6
   fixed frames at 60fps; confirm no off-by-one-frame flakiness on the
   reference leg before trusting the band claim in Hidden invariants.

## Landing gate

Do NOT land this task in CATALOG/registry before (1) the `.umap` + sources
are committed and (2) one full `cb discriminate` run has filled the
calibration record above and the MATRIX Status section.

## Discrimination record

Not yet run — see `discrimination/MATRIX.md` §Status. To be filled from the
first `cb discriminate --wip` after the map lands: per-leg verdicts, the
calib line values at each checkpoint, and any re-timed checkpoints.

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date on this box (Win11, UE 5.8 at
`C:\Program Files\Epic Games\UE_5.8`, substrate=live via `--wip`):

- **Build**: editor target compiled the task's scaffold + fixture C++ clean on
  the FIRST attempt (post-adversarial-review sources).
- **Map**: authored headless by the `aids/` script (`-ExecutePythonScript`,
  `-RenderOffScreen`); single monolithic `.umap`; placement log line confirmed.
- **Matrix**: `cb discriminate --wip` = **discriminated: YES on the first
  attempt** — reference PASS; empty + EVERY variant FAIL, each credited via
  its named MATRIX substring (`[ok ]` on all legs).
- **Not retained**: per-leg run dirs (no `--keep`) — numeric calib lines
  unharvested; the checklist's yes/no assumptions are answered by the
  verdicts. Re-run with `--keep` only if a checkpoint ever needs re-timing.

Checklist items resolved by the 2026-07-30 matrix (verdict-level evidence):
1. **The hand-rolled cooldown gate under fixed-dt: CONFIRMED** — cp2/cp4
   holds and cp5/cp6 recovery all discriminated at the shipped times
   (2.6s expiry landed between cp4=2.5 and cp5=3.4 as designed).
2. The GAS lane end-to-end (Ability.Melee tag registration, pawn resolver,
   TriggerAbilityByTag, reflection Health read/write) worked on the first
   attempt; the deleted GE-component route was never needed.
3. Dummy pin-before-Super + fixture-owned geometry: the reference's near/far
   placement discriminated `hits-everything` at cp1 as designed.

## Provenance (moved from task.md 2026-08-16; lint spec-h2-allowlist)

Source row "Melee attack (GAS)", out of an earlier internal task list (its
Verification cell is EMPTY — the acceptance criteria above were authored here,
footstep precedent). Cut from the source row, with reasons:

- **The animation-montage clause** ("plays an attack montage... reuse the
  existing jump animation") — the CraftBenchTemplate substrate ships no
  animation baseline to reuse (the jump-anim suggestion is ThirdPerson
  Blueprint-project specific), and montage playback is not observable under
  the headless verifier. The damage/cooldown mechanics carry the gates.
- **The J-key binding** — headless PIE has no key events; the ability TAG is
  the input seam (gp-poison precedent).
- **The debug-print clause** is kept as an ADVISORY suggestion in the prompt,
  never gated (FR-020d: log-content gates only on disclosed exact markers,
  which this row does not need).
