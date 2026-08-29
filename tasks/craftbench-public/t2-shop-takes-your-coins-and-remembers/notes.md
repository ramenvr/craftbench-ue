# notes — t2-shop-takes-your-coins-and-remembers

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's
2026-08-18 difficulty bar. **Nothing in this repository was built or run while this
task was authored** — the orchestrator owns the build, and other agents were working
in the same tree. Every claim below that could only be established by running is
marked as unmeasured.

## Provenance

Owner seed: *"three market stalls, each with its own price and stock; stepping onto
a mat buys exactly one; a refused sale must cost nothing; and when the yard is torn
down and reopened with brand-new stalls, reset prices and shuffled positions, the
purse, the holdings and each stall's remaining stock must come back — while the
prices must not."*

The design was written, then adversarially reviewed. **The review's verdict was
`revise`**, with thirteen required revisions, six false premises and five
ungradeable gates. Everything below is what happened to each. The seed intent is
intact: the shop, the refusal, the teardown, the shuffle and the do-not-persist-the-
price rule are all still the centre of the task.

## The two things the review said were missing, and what was built instead

The review's sharpest finding was not a defect, it was a measurement: *"a frontier
model would plausibly one-shot this ... the prompt is an implementation spec in
prose ... honest hours 1.5–3 h ... this is five single-mechanism tasks side by
side."* It named the fix precisely, and both halves were built.

1. **The reopening became an arithmetic against the fresh stall's own live state.**
   Each stall now carries `StockCapacity` and `DeliveredSinceClose`, both printed on
   its own sign, both staged by the fixture. What a stall holds when it reopens is
   `Clamp(what it had left + what it was delivered, 0, what it can hold)`. That
   turns "restore" from an assignment into a three-term sum in which the naive
   overwrite, the naive keep-what-arrived, the forgot-the-remembered and the
   forgot-the-cap answers are each wrong about a *different* stall. Set 0 reopens on
   3 / 2 / 3 against remembered 0 / 1 / 2, delivered-only 3 / 1 / 2, arrived-holding
   4 / 3 / 3, uncapped 3 / 2 / 4.
2. **A carry limit made the restored holdings load-bearing for the transaction.**
   The gate board now also says the most of any one kind you can carry. Step 10 is
   refused *only* because the restored holdings are at that limit — the purse can
   pay and the stall has stock. That is what stops the record from being a thing the
   signs merely display: a submission that restores the *painted* "yours" and not
   the live count sells at step 10 and dies at `YourHandsAreOnlySoBig`.

Together these are what makes "a fix in one subsystem breaks the other" true rather
than asserted. There are now three such couplings, and the spec names all three:
saving more to fix the restore breaks the price gate; restoring the display without
the state passes the reopening sample and fails three behavioural steps after it;
and reconciling without reading the fresh stall's own capacity and delivery cannot
be right at all.

Honest revised estimate: **3–5 h**, which is mid-to-upper T2. The tier is unchanged
and the review's alternative (drop to T1) was not taken, because the added work is
genuine composition rather than more typing.

## Every required revision, and what was done

| # | Revision | Done |
|---|---|---|
| 1 | Make `TheStallsAreTheMarketsToPrice` catch the answer it is named for | **Applied.** Both halves — the live `PriceCoins` and the shown price — are compared against the number the **fixture staged**, never against the stall's own property. The over-saved record that writes 30 into `PriceCoins` no longer satisfies "shown equals live". |
| 2 | Stop grading agent-writable mirrors as if they were the sign | **Applied.** Every sample parses `UTextRenderComponent::Text` and requires `LastShown*` to agree with the parsed number. The spec's "ShowSign is the only writer, so the mirrors are by construction what a reviewer sees" claim is **deleted** — it was false the moment the agent may edit `MarketStallActor.cpp`. |
| 3 | Make the task idempotent across runs in one workdir | **Applied, both halves.** `WipeDurableStores` empties `Saved/SaveGames` inside the world-init callback, before any `BeginPlay`; and the first settled sample checks the yard opened on the staged numbers, reporting a mismatch as an **Error** naming a leftover record as the likely cause. The reference deliberately writes a save slot, so the reference run exercises the guard. |
| 4 | Delete "write it down, do not merely hold on to it" | **Applied.** The prompt now says only "keep the record somewhere that outlives the stalls and the board themselves", which is exactly what the fixture can see. The unmeasurable half is gone, and the hole is written up in the spec's *Hidden invariants* rather than quietly left. |
| 5 | Reclassify agent-reachable preconditions as named scored FAILs | **Applied.** Missing or renamed `PriceCoins` / `StockCount` / `StockCapacity` / `DeliveredSinceClose` / `GoodsName` / `LastShown*` / `StartingCoins` / `CarryLimit` / `LastShownCoins`, a stall or board count other than 3/1, two stalls selling the same thing, a stall with no mat, and no visible player character are all `TheYardsOwnNumbersAreStillThere` or `AStallIsKnownByWhatItSells` — scored. Only the map-shaped clauses (waypoint and leg clearances) and the staged-set self-check stay Errors. |
| 6 | Movable counter root; specify the mat's Z | **Applied.** `Counter` and every child are `EComponentMobility::Movable` and the authoring script refuses to save a level where they are not. The mat is 240 x 240 x 220 sitting on the floor (world z 0..220); the walking capsule's centre is 96 above the floor, and the authoring script refuses a mat that does not span it. |
| 7 | Raise the difficulty or drop the tier | **Applied** — both of the review's suggested upgrades, above. |
| 8 | Retire the three strawman wrong answers | **Applied.** "One price for the whole yard", "no edge latch" and "only guarded on money" are gone from the spec's anti-gaming list. The review is right that the scaffold hands the agent `OnComponentBeginOverlap` on the stall's own mat, so `this` **is** the stall and the edge is free. The self-contradictory seed bug ("bails with an early return, but the deduction is below that return") is gone with them. What replaced them are seven failure modes that are all reachable from a correct-looking first pass. |
| 9 | Restate the movement premise against the substrate | **Applied.** `ThirdPersonCharacter.cpp` sets `MaxWalkSpeed = 500` **and** `BrakingDecelerationWalking = 2000` — not the engine's 600 / 2048 / `= MaxAcceleration`. The fixture's comment records the corrected numbers, and the dwells were re-derived against 2000 (they were already clear of it by more than 3x). |
| 10 | Narrow the stability literal | **Applied.** The probe now compares **only** the stall being stood on and the gate board, which is exactly what "standing on the mat does not keep buying" talks about. |
| 11 | Reword "the amount the yard was built to hold" | **Applied.** The prompt says "whatever amount the market has given it", and the correct answer never needs that number at all — it needs *left + delivered, capped*. The trap of pointing a careful agent at the level's own stock constant is gone. |
| 12 | Add per-run variation | **Applied, with a deliberate limit.** Three complete staged sets ship, selected by `-CraftBenchMarketSeed=N`, default 0. The default is fixed **on purpose** so a discrimination leg reproduces byte for byte and a false FAIL is reproducible — a wall-clock or random seed would trade a hard-coding defence for an unreproducible one, and this repo has been bitten worse by the second. What defeats hard-coding within a single run is stronger than the seed anyway: every price, stock, capacity and delivery changes at the reopening, and the level's own numbers agree with none of it. |
| 13 | Check the portfolio against `t3-checkpoint-restores-the-world` | **Checked, and the overlap is real but not fatal.** That in-flight scaffold is about *snapshot and rollback* — put the world back the way it was. This task is about *reconciliation* — the world moved on while the record was away, and the record has to be combined with what it finds rather than written over it. The review itself proposed exactly that split. **Flagged for the owner**: if t3 is later reshaped toward reconciliation, one of the two should change. |

## False premises: what was wrong and what it is now

- **Premise 10 was verified against the wrong file.** It cited the engine defaults
  (`CharacterMovementComponent.cpp` 694 / 733 / 736) as though they governed. The
  substrate overrides braking too. Corrected in the fixture's own comment, which is
  where the next author will look.
- **"ShowSign is the ONLY writer, so the mirrors are what a reviewer sees" was
  false.** `MarketStallActor.cpp` is under the declared writable root. Deleted, and
  the grade moved to the rendered text.
- **`TheStallsAreTheMarketsToPrice` was a partially dead gate.** "Shown equals live"
  is satisfied by a submission that corrupted both. Rewritten against the staged
  number.
- **The declared hole reasoned in one direction only.** It worried that an
  in-memory record passes without being durable; the dangerous direction is the
  opposite one, where a genuinely durable record survives the PIE session and fails
  a *correct* submission on its second run. That is revision #3, and it is the
  highest-risk defect the review found.
- **A missing premise: a runtime-spawned STATIC root is a PIE failure.** The design
  specified a Static counter and then destroyed and respawned all three stalls. The
  counter is Movable now, the authoring script enforces it, and the spec says why.
- **Premise 3's citation was right** (`Runtime/Engine/Private/Character.cpp`), and
  so were premises 1, 2, 4, 5, 6, 7, 8, 9, 11 and 12. Re-verified against
  `<UE-root>/Engine/Source` while writing the fixture; nothing was taken on trust.

## Ungradeable gates: dropped, or made gradeable

- **Durability** — the demand was **removed from the prompt** rather than left
  unmeasured (revision #4).
- **The price gate** — made gradeable (revision #1).
- **The mirrors** — made evidence-backed (revision #2).
- **"Do not stop them walking"** — the review said `AActor::DisableInput` was
  invisible to a fixture that drives with `AddMovementInput`, and recommended either
  driving the whole human lane or asserting explicitly. **Asserting explicitly turned
  out to be enough, and better.** `APawn` *overrides* `DisableInput` to clear
  `bInputEnabled` (`Pawn.cpp:1177-1186`), `APlayerController::BuildInputStack` reads
  it (`PlayerController.cpp:2668-2680`), and `APawn::InputEnabled()` is public
  (`Pawn.h:367`). So `TheBuyerKeepsWalking` reads the pawn's own flag, plus
  `IsMoveInputIgnored()`, the movement mode, the top speed and a per-frame
  displacement bound. All four freeze shapes and the shove are caught, and all of it
  is disclosed by "do not stop them walking, do not take their controls away, and do
  not move, push or place them."
  (`APlayerController::IsInputComponentInStack` was considered and rejected: a
  possessed pawn's input component is never in `CurrentInputStack` — the controller
  pushes it directly in `BuildInputStack` — so that check would have been silently
  vacuous. This is exactly the trap the review was pointing at, one layer deeper.)
- **The harness-precondition list** — split (revision #5).

## Engine facts checked while writing, with where

Everything the fixture and the scaffolds rest on was read out of
`<UE-root>/Engine/Source` rather than remembered:

- `APawn::AddMovementInput` — `GameFramework/Pawn.h:499`, `ENGINE_API virtual`,
  default args as used.
- `APawn::InputEnabled()` — `Pawn.h:367`; set by `APawn::EnableInput` /
  `DisableInput` at `Private/Pawn.cpp:1165-1186`; read by
  `APlayerController::BuildInputStack`, `Private/PlayerController.cpp:2668-2680`.
- `AController::SetIgnoreMoveInput` / `IsMoveInputIgnored` —
  `GameFramework/Controller.h:360, 368`; `APawn::IsMoveInputIgnored` — `Pawn.h:561`.
- `UTextRenderComponent::Text` is `UPROPERTY(EditAnywhere, BlueprintReadOnly) FText`
  and `SetText` is `ENGINE_API` — `Components/TextRenderComponent.h:48-50, 104`.
  `SetHorizontalAlignment` / `SetVerticalAlignment` / `SetTextRenderColor` /
  `SetWorldSize` at `:120, 124, 128, 148`; `EHTA_Center` at `:22`,
  `EVRTA_TextBottom` at `:35`.
- `UShapeComponent::SetLineThickness` — `Components/ShapeComponent.h:97`;
  `UBoxComponent::SetBoxExtent` — `Components/BoxComponent.h:39`.
- `UWorld::SpawnActorDeferred` — `Engine/World.h:3851` (it sets
  `bDeferConstruction`); `AActor::FinishSpawning` — `GameFramework/Actor.h:3117`.
- `UGameplayStatics` save API — `Kismet/GameplayStatics.h:1124` (CreateSaveGameObject),
  `1167` (SaveGameToSlot), `1175` (DoesSaveGameExist), `1211` (LoadGameFromSlot),
  `1231` (DeleteGameInSlot); `USaveGame` — `GameFramework/SaveGame.h:22-23`.
- `IFileManager::DeleteDirectory(Path, RequireExists, Tree)` —
  `HAL/FileManager.h:125`.
- `UCharacterMovementComponent::MovementMode` —
  `GameFramework/CharacterMovementComponent.h:230`; `GetMaxSpeed` —
  `GameFramework/MovementComponent.h:225`.
- `UGameInstance::GetSubsystem<T>()` — `Engine/GameInstance.h:440`;
  `AActor::GetGameInstance()` — `GameFramework/Actor.h:3772`;
  `UGameInstanceSubsystem` — `Runtime/Engine/Public/Subsystems/GameInstanceSubsystem.h`
  (note: **Public/**, not Classes/ — the include is
  `"Subsystems/GameInstanceSubsystem.h"` either way).
- `AActor::InputComponent` is public — `GameFramework/Actor.h:891`;
  `AActor::DisableInput` only pops from the controller stack —
  `Private/Actor.cpp:4930-4949`. Both read, both rejected as detectors; see above.

## Design decisions and why

- **The mat is a `UBoxComponent` on the stall with nothing bound to it.** The
  substrate's trigger recipe verbatim (`TeleportPortalActor.cpp:19-21`,
  `RelicPickup.cpp:17-19`). The design deliberately does **not** treat the edge latch
  as a difficulty axis, because the review is right that `OnComponentBeginOverlap`
  hands it to you. The latch is still in the reference, and the stability probe still
  runs, because a distance-poll implementation is a legitimate choice and must still
  behave.
- **Twelve steps, not eight.** Eight before the reopening and four after it. The
  four after are what make the record load-bearing: one that proves the delivery
  restocked a dead stall, one refused only by the carry limit, one that spends the
  restored purse to exactly zero, and one that proves that deduction happened.
- **The `>=` boundary is a SALE, and it is after the reopening.** Step 11 pays
  exactly. It could not be put in round 1 without colliding with step 8, which needs
  "affordable but sold out" — spending to zero and then having coins left for a
  sold-out stall are mutually exclusive without a second income.
- **Every refusal has exactly one reason, and `PrepareTest` proves it.** Otherwise
  "sold out" and "cannot pay" become gradeable by the same accident and two gates
  collapse into one.
- **The route is derived from the stalls' own box components.** Not from written-down
  coordinates, so it re-derives itself after the shuffle and the level can be
  re-authored without touching the fixture.
- **The gate for a refusal is named after the reason the day placed it there.** The
  *check* is identical in all three cases (nothing moved); only the name and the
  message differ. That is deliberate and it is written down in `MATRIX.md`, because
  a reader could otherwise think three gates were doing three different things.
- **The stalls rotate one place, not swap.** A swap of three leaves one where it was.

## Hazards hit while authoring, and what they cost

1. **The counter is the root, so it cannot be offset from the actor.** The first
   draft put a `kCounterOffset` of +100 Z on the root component, which does nothing
   — setting a root's relative location sets the *actor's* location. Every offset is
   now measured from the counter's centre and the yard places each stall at z = 100.
   The `MatPlate` offset was wrong in the same way (+4 instead of −96) and was
   caught by re-deriving all four offsets from one origin rather than by reading the
   code again.
2. **A child component's box extent is scaled by its world scale.** The mat hangs
   off a counter scaled (2, 1, 2), so its relative scale has to be the reciprocal or
   a `SetBoxExtent(120,120,110)` silently becomes a 60 x 120 x 55 trigger. The
   authoring script now reads `get_scaled_box_extent()` back and refuses to save a
   mat that does not measure 240 square.
3. **A mat that does not reach the capsule's centre would make the task
   unwinnable while looking perfect in the editor.** The capsule's centre sits 96
   above the floor. The authoring script refuses a mat that does not span it.
4. **A dead member is a review finding, not a tidiness one.** The first scaffold
   draft stored a `MatLook` material and never used it. It became a visible
   `MatPlate` instead, which the task needed anyway.
5. **`GradeReopening`'s message tried to recover the closing stock by subtraction**
   (`ReopenStock - min(Delivered, ReopenStock)`), which is wrong whenever the sum
   was capped — i.e. exactly in the case the message exists to explain. The closing
   stock is now carried in `ClosingStock[3]` and the message spells the sum out.
6. **THE NEAR-MISS THAT WOULD HAVE FAILED EVERY SUBMISSION.** The first cut resolved
   the player character inside `ResolveYard`, which runs during
   `OnWorldInitializedActors` -- i.e. during staging. The stalls are placed actors and
   exist by then; **the pawn does not.** It is spawned by the game mode inside
   `UWorld::BeginPlay`, which is after that delegate has fired. So
   `GetPlayerCharacter` would have returned null on a perfectly healthy yard and every
   run -- the reference included -- would have ended `TheYardsOwnNumbersAreStillThere:
   there is no visibly represented player character`. Hero resolution now lives in a
   separate `ResolveHero()` called from `PrepareTest`, which is where the shipped t1
   fixture does it and which runs after BeginPlay. The general shape of the mistake is
   the repo's probe-premise law: a negative result is only as good as the state the
   probe built, and "no character" was a statement about the CLOCK, not about the yard.
7. **`SpawnActorDeferred` defaults to `MultiplyWithRoot`, `FinishSpawning` to
   `OverrideRootScale`.** The transform captured off a destroyed stall already carries
   the counter's (2, 1, 2) root scale, so the default would have spawned the fresh
   stall at (4, 1, 4) for the length of the deferred window -- with the mat's box
   extent scaled with it. `FinishSpawning` would have corrected it before BeginPlay, so
   nothing would have been visibly wrong; both ends now pass `OverrideRootScale`
   explicitly rather than relying on that.
8. **A heredoc is not a way to write UE C++.** Two of these files were half-written
   through a shell heredoc before an unbalanced quote inside a `TEXT()` literal
   truncated one at line 125. Everything from that point was written with the file
   tools.

## What has NOT been done, and must be

- **Nothing has been built or run.** No `cb`, no UBT, no editor — other agents were
  working in the same tree. So:
  - `Content/Maps/t2-shop-takes-your-coins-and-remembers/L_MarketYard.umap`
    **does not exist yet**; `authoring/author_map.py` is the thing that makes it and
    it has never been executed.
  - `MATRIX.md`'s two cells are **predictions derived from the sources**, not
    measurements. The empty leg's substring is quoted from the fixture's literal.
  - The fixture and the reference have never been compiled. The C++ was written
    against the engine source with every signature checked, but "checked" is not
    "compiled".
- **The empirical half of the difficulty bar is untouched.** The honest 3–5 h is a
  senior-dev estimate, not a measurement. One `cb eval --model claude-p:<cheap
  model>` run is what would settle it: passing first try with zero iteration means
  another axis is needed, and the natural next one is a second kind of goods per
  stall.
- **The portfolio question in revision #13 is for the owner**, not for me.
