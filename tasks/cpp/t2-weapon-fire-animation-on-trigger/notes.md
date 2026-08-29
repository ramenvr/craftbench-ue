# t2-weapon-fire-animation-on-trigger — build contract + verifier notes

Maintainer-only notes (never agent-visible; this folder is outside every
agent-writable prefix).

## Provenance

- Source row: an earlier internal task list, "Weapon attachment system"
  (Verification cell empty — acceptance criteria authored here, the
  footstep precedent).
- **Attach half CUT with pointer**: the weapon-in-hand deliverable already
  ships as `bp/t2-weapon-held-in-right-hand` (socket on hand_r + cube
  weapon component, 10 named L2I checks). This task grades only the net-new
  half.
- **Pose clause CUT**: "have the player's arm stretched out" has no
  deterministic observable (no pose gate exists; FR-020d).
- **Mouse-click trigger → `DoFireStart` seam**: headless PIE has no key
  events; the tp2-sprint-stamina precedent (its commit message brands the
  reflection-seam route "NEW PRECEDENT") is the sanctioned rephrase.
- Spike basis (2026-07-30, headless `-nullrhi -deterministic
  -FPS=60`): montage state fully observable — `GetCurrentActiveMontage()`
  returns the active montage, `Montage_IsPlaying` true, `Montage_GetPosition`
  advanced EXACTLY 2.000s across a 2.0s checkpoint gap; identical on default
  and forced `VisibilityBasedAnimTickOption` (default is AlwaysTickPose).
  Template assets load headless: `SKM_Manny_Simple`, `ABP_Unarmed`,
  `MM_*` clips under `Anims/Unarmed/`.

## Build contract

| piece | path | contract |
|---|---|---|
| scaffold character | `Source/ThirdPerson/Tasks/<id>/FireCharacter.{h,cpp}` | concrete `AFireCharacter : AThirdPersonCharacter`; ctor: tag `FireHero`, `FObjectFinder<USkeletalMesh>` SKM_Manny_Simple onto `GetMesh()` at rel (0,0,-90)/yaw -90, `FClassFinder<UAnimInstance>` ABP_Unarmed as anim class. NO fire logic. |
| scaffold game mode | `Source/ThirdPerson/Tasks/<id>/FireGameMode.{h,cpp}` | `DefaultPawnClass = AFireCharacter` (tp2/ladder mold) |
| fixture | `Source/CraftBenchTests/Tasks/<id>/FireAnimationFunctionalTest.{h,cpp}` | tag-resolve + reflection seam + 4 montage-state checkpoints (below) |
| map | `Content/Maps/<id>/L_FireAnimation.umap` | floor (engine cube 30x20x1 at (300,0,-48), top Z=+2), PlayerStart (0,0,120 yaw 0), fixture (0,400,120), WorldSettings GameModeOverride = AFireGameMode. NO ladder/extra actors. Recipe: `aids/author_L_FireAnimation.py`. |

## Fixture design

- Timeline `{0.5, 0.8, 1.4, 6.0}`:
  - cp0 (0.5): montage state must be EMPTY (the ABP's idle locomotion is not
    a montage — dead-gate audit below), then invoke `DoFireStart` — the
    always-playing cheat dies here, BEFORE the trigger path runs.
  - cp1 (0.8, 0.3s after the trigger): a montage must be ACTIVE. Existence
    only — `Montage_IsPlaying` is deliberately NOT required here, because a
    paused montage must survive to cp2 to die at its OWN gate (a
    `Montage_Pause` in the same frame as play sets bPlaying=false; gating
    "playing" at cp1 would kill the frozen variant at the WRONG assertion).
  - cp2 (1.4): if the SAME montage is still active, its position must have
    advanced >= 0.25 (0.6s of fixed-step play advances 0.6; frozen advances
    0.0). A clip that already ended (natural length < ~0.9s) passes — honest:
    it played through.
  - cp3 (6.0): montage state EMPTY again — loops/permanent states die here.
- Seam helper copied verbatim from the tp2/ladder fixture (tolerated return
  value; real parameters rejected; `ProcessEvent` with an initialized
  buffer).
- `ResolveAnimInstance` re-reads the anim instance per checkpoint (an agent
  may swap anim classes at runtime); its absence is a GRADED fail (the
  scaffold ships the wiring, so only an agent change removes it).
- HARNESS-PRECONDITION `FinishTest(Error, ...)`: no-UWorld only. **Honesty
  note (wave-1 convention): an automation Error result still lands as state
  "Fail" in index.json and grades as an agent FAIL today** — the prefix
  expresses the semantics for a future runner-side routing rule; it does not
  route to exit 7 yet.

## Dead-gate audit

- **cp0 empty-montage gate**: the scaffold's ABP_Unarmed drives locomotion
  through its anim graph (state machine), which is NOT a montage —
  `GetCurrentActiveMontage()` on the untouched scaffold is null, so the gate
  excludes the start state. Confirmed by the spike: probe characters wearing
  ABP_Unarmed reported `GetCurrentActiveMontage: <null>` until
  `PlaySlotAnimationAsDynamicMontage` was called. NOT a dead gate.
- **cp1 montage-active gate**: null on the untouched scaffold and the
  no-animation variant (nothing ever plays) — excludes both. NOT dead.
- **cp2 advance gate**: 0.6s of play advances the position ~0.6 (spike:
  position tracks fixed dt exactly); a paused montage advances 0.0. The 0.25
  threshold sits 2.4x below the expected advance and infinitely above the
  frozen case. NOT dead.
- **cp3 empty gate**: MM_Attack_01 (reference clip) is a template one-shot
  (~1-2s class); with blend-out it is long gone by 6.0. A 100-loop or
  permanently re-triggered montage is still active. NOT dead.

## Calibration checklist (fill from the first `cb discriminate --wip` run)

1. **MM_Attack_01 exact length** vs the cp2/cp3 instants — the reference must
   still be PLAYING at cp2 (needs natural length + blend >= ~1.0s from the
   0.5s trigger, i.e. clip >= ~0.9s) OR already ended (also passes cp2), and
   must be ENDED by cp3 (clip <= ~5.3s). Template attack clips sit ~1-2s, so
   both hold with wide margin — confirm from the calib lines (`pos=` at cp1/
   cp2, `active=` at cp3).
2. **`PlaySlotAnimationAsDynamicMontage` on ABP_Unarmed's `DefaultSlot`** —
   the spike proved the montage ACTIVATES and its position ADVANCES with a
   bare template ABP; whether ABP_Unarmed's graph contains a DefaultSlot node
   only affects the VISUAL blend, never the graded montage state. Recorded,
   not gating.
3. **Ctor `FObjectFinder` for `/Game/...` content in the scaffold** — the
   CBT default-cube task ships the same idiom for `/Engine/` content;
   `/Game/` content finders are equally standard but this is the first
   scaffold here to use one. The L1+map-load leg of the first discriminate
   run proves it (a failed finder logs and leaves the mesh empty — the
   graded empty leg would then die at the anim-instance gate instead of the
   seam gate; watch the empty leg's message).
4. **cp1 at 0.3s after trigger**: montage activation is synchronous with the
   `Montage_Play` call inside the seam invocation (cp0), so cp1 sees it
   active even for very short clips — confirm the frozen variant also still
   holds its paused montage at cp1 (Montage_Pause keeps it in the active
   list; spike did not test pause — the ONE unproven engine behavior in this
   fixture; if pause DROPS the montage from the active list, the frozen
   variant dies at cp1's message instead → wrong-reason, re-time or re-shape
   the variant).
5. **PlayerStart settle by cp0=0.5** — proven by the ladder task (identical
   spawn geometry, cp0=0.6); 0.5 has the same margin over the ~2-frame
   settle. Confirm no idle-locomotion montage appears on possession.

## Landing gate

Do NOT land in CATALOG/registry before: the `.umap` is authored + committed,
the fixture/scaffolds are committed, and one full `cb discriminate --wip` run
has confirmed reference PASS + all four negative legs at their named
assertions (the frozen variant's gate being the one to watch, per calibration
item 4).

## Residual bounds (acknowledged, not gates)

- A solution that plays the montage a SECOND time (internal re-trigger)
  ending before 6.0s passes — "one request, one animation" is graded as
  bounded by the cp3 window, not as an exact play-count. Recorded in the
  MATRIX coverage note.
- The fixture cannot verify the clip LOOKS like firing (no pixel gate,
  FR-020d) — any montage the agent plays counts. The prompt's "reads as a
  firing/attack motion" is advisory.
- **Observable-channel disclosure (adversarial-review fix)**: the fixture
  grades exclusively through the anim instance's MONTAGE channel
  (`GetCurrentActiveMontage`). A behavior-correct single-node implementation
  (`GetMesh()->PlayAnimation(clip)` + a restore-the-ABP timer) would LOOK
  right on screen but never touch that channel — so the prompt now DISCLOSES
  the overlay contract ("plays as an overlay on top of the character's
  existing animation setup, which must stay in place throughout"), which
  excludes the animation-setup swap and makes the montage/slot route the
  disclosed contract (the same sanction class as the Do* seam names). The
  single-node route is prompt-excluded, not silently failed.

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date (Win11, UE 5.8, substrate=live via
`--wip`): **`cb discriminate` = discriminated: YES** — reference PASS; empty +
EVERY variant FAIL via its named MATRIX substring (`[ok ]` on all legs).
Editor-target builds of the scaffold/fixture C++ were clean; per-leg run dirs
not retained (no `--keep`) — the verdicts answer the checklist's yes/no items.

Wave-3 specifics: montage observability (spike-proven) held in the graded leg;
checklist unknown #4 resolved by the verdict — the frozen variant died at cp2's
named assert, so `Montage_Pause` keeps the montage readable in the active list
on this build.
