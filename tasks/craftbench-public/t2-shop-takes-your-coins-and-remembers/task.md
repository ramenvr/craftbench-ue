---
id: t2-shop-takes-your-coins-and-remembers
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_MarketYard :: AMarketDayFunctionalTest"]
---

# t2-shop-takes-your-coins-and-remembers

Three market stalls, each with its own price, its own stock and its own capacity.
Stepping onto a stall's mat buys exactly one; a refused sale must cost nothing at
all. Part way through the day the yard is torn down and reopened with **brand new
stalls**, reset prices, a delivery each and shuffled positions — and what a stall
holds when it comes back is what it had left **plus what it was delivered, capped
at what it can hold**. The purse and the holdings come back too, and they come
back **live**: a full pack still refuses a sale you can plainly afford. The prices
do not come back.

> **Built against the 2026-08-18 difficulty bar, and against an adversarial review
> of the first design.** The first version was one transaction plus an assignment
> restore, and the review's honest estimate was 1.5–3 h — "five single-mechanism
> tasks side by side". Two things were added, both of which make a fix in one
> subsystem break the other unless the interaction is understood: the reopening is
> an **arithmetic against the fresh stall's own live numbers** rather than an
> assignment, and the carry limit makes the restored holdings **load-bearing for
> the transaction** instead of merely displayed by it. `notes.md` records every
> revision applied and the two the review demanded that were dropped rather than
> faked.

## Primary concept

- `saving-and-loading-your-game` — a record that outlives the actors that made it
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine)

The load-bearing behaviour is **deciding what belongs in the record and what does
not**, and then **reconciling it against a world that moved on while it was
away**. The grade never asks *how*: a save-game slot, a game-instance subsystem,
a world subsystem or a file all pass identically, and the fixture never looks for
one.

## Composed concepts

- `collision-overview` — a trigger volume that notices a walking character
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)
- `actor-lifecycle` — a fresh actor spawned into a world that has already begun
  play, and what its `BeginPlay` can and cannot know
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)
- `programming-subsystems` — a place to keep state that outlives the props
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine)
- `ps-strings` — the readouts a person actually reads, and what is graded
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/string-handling-in-unreal-engine)

The production pattern is the ordinary one Epic's own save-game guide describes: a
shop transaction over a player wallet and inventory, persisted across a scene
teardown. Nothing here is invented — what is measured is whether the four pieces
agree with each other.

## Prompt given to the agent

> The yard has three market stalls in a row. Each sells a different kind of goods,
> and each carries numbers of its own: what one of its goods costs in coins, how
> many it still has, and the most it can ever hold. The three stalls do not charge
> the same price and do not hold the same amount, so read those numbers off the
> stall you are actually dealing with. They are written on that stall's own sign,
> along with how many of that kind you already own. You start with a purse of
> coins, and the board by the gate says how many — and, next to it, the most of any
> one kind of goods you are able to carry.
>
> In front of each stall there is a mat. Stepping onto a stall's mat is one attempt
> to buy one of that stall's goods — exactly one. Standing on the mat does not keep
> buying; to buy another you step off and step on again.
>
> An attempt goes through only if all three of these hold: you can pay that stall's
> price, that stall has at least one left, and you are not already carrying as many
> of that kind as you can carry. Spending your last coin is a sale; going below
> nothing is not. Carrying your fill of one kind stops you taking another of *that*
> kind, and nothing else. When a sale goes through, your coins fall by exactly that
> stall's price, that stall has one fewer, and you own one more of that kind. When
> an attempt is refused — for any of those three reasons — nothing changes at all:
> not your coins, not that stall's stock, not what you own. A stall with nothing
> left sells nothing however much money you are carrying, and no stall's stock ever
> reads less than nothing.
>
> Every one of those numbers is something a person standing in the yard can see, and
> every one of them has to be true. Each stall's sign shows what that stall is
> asking, what it has left, and how many of that kind you own; the board by the gate
> shows your coins. All of it must be right within **half a second** of you stepping
> onto a mat. The two calls that write a stall's sign and write the gate board are
> supplied and working — use them, and leave the wording they print alone. Only the
> numbers you hand them are yours.
>
> Prices are the market's business and not yours. A stall asks whatever it is asking
> now — never write an older price back onto a stall or onto its sign.
>
> Part way through the day the yard closes and reopens. You wait at the gate; the
> stalls and the gate board are taken away and put back, and what comes back is
> brand new: new signs, prices the market has reset, and each stall holding whatever
> amount the market has given it. Two more numbers come back with each stall, on its
> own sign: how many of its goods were **delivered** to it while the yard was shut,
> and the most it can hold. **What a stall has when it reopens is what it had left
> when it closed, plus what it was delivered, and never more than it can hold** —
> whatever the fresh stall happens to be holding when it arrives. What comes back
> with you is what you had: the coins left in your purse and how many of each kind
> you own. Have all of it right within **half a second** of the yard reopening, on
> the signs and on the board, and have it be real rather than painted on: a stall
> that sold out but was delivered more can sell again, a stall whose delivery would
> overfill it holds only what it can hold, a nearly empty purse still cannot pay for
> much, and a kind you are already carrying your fill of still cannot be bought. So
> keep the record somewhere that outlives the stalls and the board themselves.
>
> The stalls do not come back where they were. They are shuffled along the row. A
> stall is known by what it sells, never by where it stands or by what order you
> find it in.
>
> What you own is a count on a sign, not an object lying in the yard — do not spawn
> anything. And buying never takes the character away from the player: do not stop
> them walking, do not take their controls away, and do not move, push or place
> them.
>
> The stalls, their mats and their signs, the gate board, and the two supplied calls
> that write to a sign and to the board are all supplied and working. Nothing decides
> when a sale happens, what it costs, what changes, or what should be remembered.
> Where the stalls stand, what the market charges, what it delivers and what a stall
> can hold are not yours to change; the stalls and the board are already placed in a
> level you cannot edit, so whatever you add has to land on something that is already
> running. Do not edit the level, any config file, or any test file. Write your
> solution in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed, though
  `AThirdPersonCharacter` is writable if a solution wants to live there.
- `Tasks/t2-shop-takes-your-coins-and-remembers/MarketStallActor.h` / `.cpp` —
  `class THIRDPERSON_API AMarketStallActor : public AActor`, tagged `MarketStall`.
  Supplied:
  - `Counter` — a 200 x 100 x 200 cube, **the root**, `BlockAll`, **movable**. The
    actor stands at half its own height, so the yard places it at z = 100 and it
    sits on the floor. Movable because the yard rebuilds itself mid-run and PIE
    scores moving a static actor as a failed test.
  - `Mat` — a `UBoxComponent` 240 x 240 in plan and 220 tall, sitting on the floor
    300 in front of the counter. Query-only, overlap against every channel,
    overlap events on — the substrate's established trigger recipe, the same three
    lines the shipped portal and relic scaffolds use. **Nothing is bound to it.**
  - `MatPlate` — the painted square underfoot in the mat's own footprint,
    non-colliding, so a person can see where the mat is.
  - `Sign` — a `UTextRenderComponent` above the counter, facing the customer's side.
  - `UPROPERTY(EditAnywhere)` `FName GoodsName`, `int32 PriceCoins`,
    `int32 StockCount`, `int32 StockCapacity`, `int32 DeliveredSinceClose`.
    **Read them off the stall you are dealing with; the three stalls are not set to
    the same values, and the market resets them when the yard reopens.**
  - `UFUNCTION(BlueprintCallable) void ShowSign(int32 Price, int32 Stock, int32 Owned)`
    — the supplied display. Writes the sign's `FText` in the yard's own wording,
    `"<goods>  price <P>  left <S>  yours <O>  came <D>  holds <C>"`, and in the
    same breath the three mirrors `LastShownPrice` / `LastShownStock` /
    `LastShownOwned`. `<D>` and `<C>` come straight off the stall.
  - `BeginPlay` calls `ShowSign(PriceCoins, StockCount, 0)` once so the yard opens
    honest. **No tick, no overlap handler, no purse, no notion that a sale exists.**
- `Tasks/t2-shop-takes-your-coins-and-remembers/MarketLedgerActor.h` / `.cpp` —
  `class THIRDPERSON_API AMarketLedgerActor : public AActor`, tagged
  `MarketLedger`. A movable post, a `CoinsBoard` text component,
  `UPROPERTY(EditAnywhere)` `int32 StartingCoins` and `int32 CarryLimit`, and the
  supplied display `UFUNCTION(BlueprintCallable) void ShowCoins(int32 Coins)`,
  which writes `"coins <N>  carry <K>"` and the mirror `LastShownCoins`.
  `BeginPlay` calls `ShowCoins(StartingCoins)`. It holds no purse and knows nothing
  about stalls.
- `Content/Maps/t2-shop-takes-your-coins-and-remembers/L_MarketYard.umap` — the
  staged yard, committed binary. World Settings name **NO** game mode, so the level
  inherits `BP_ThirdPersonGameMode` and Enhanced Input stays alive. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 5,200 x 2,800, striped, stripes **non-colliding** | a lane stripe marks the side every mat is reached from |
  | Three `AMarketStallActor`s | in a row 900 apart, all **movable** | the fixture destroys and respawns them one place further along |
  | Three mats | 240 x 240, painted, in front of each counter | no two mats are within 250 uu of each other |
  | One `AMarketLedgerActor` | beside the row, clear of every mat and every walk | |
  | PlayerStart | at the gate end | |
  | Backdrop + landmarks | a low back wall and two differently sized posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AMarketDayFunctionalTest` | |

  **The numbers written into this level are decoys and are never the numbers a
  solution has to work from.** The fixture stages its own before anybody's
  `BeginPlay`. The authoring script refuses to save a level whose authored numbers
  have drifted into agreeing with the fixture's.

- `cameras.json` (the camera-plan lane; not part of this release) —
  the presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No purse, no holdings, no transaction, no overlap handler, no record, no restore.
  The empty submission compiles (L1 green) and FAILs L2 at the first step onto a
  mat.
- No test source in the agent's writable path. `AMarketDayFunctionalTest` lives in
  the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-shop-takes-your-coins-and-remembers/L_MarketYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive: **pie-checkpoint-sampling**
with settled off-mat samples around a fixture-driven walk, plus an every-frame
readback.

**Everything graded is read off the text a person in the yard would read.** The
fixture parses `UTextRenderComponent::Text` on each sign and on the gate board, and
requires the actors' reflected `LastShown*` mirrors to **agree with the parsed
text**. The mirrors live in a file the agent may edit, so a mirror alone is not
evidence of a sign.

**Every number a gate compares against is staged by the fixture, before any
`BeginPlay`**, through `FWorldDelegates::OnWorldInitializedActors` filtered to this
world (the shipped `ASanityFunctionalTest` pattern). Three number sets are
shipped; `-CraftBenchMarketSeed=N` selects one and the default is 0, so a
discrimination leg is byte-reproducible while no single constant is right in more
than one set. The level's own numbers agree with none of them.

**The route is computed from the stalls, not written down.** Each stall's mat
position is read off its own box component; the lane point is 700 uu further out
along the counter→mat line, which puts it 580 uu clear of the mat's near edge; the
gate is 400 uu beyond the mean lane point. So the route re-derives itself after the
stalls are shuffled. Every leg dwells: 1.2 s at the lane (then the **pre-step
sample**), 2.0 s standing **on** the mat, 1.5 s back at the lane (then the
**graded sample**). All three clear the prompt's disclosed half second several
times over, and every window was widened only in the direction that cannot fail
correct work. The dwells are sized from measured substrate movement —
`AThirdPersonCharacter` sets `MaxWalkSpeed = 500`, `BrakingDecelerationWalking =
2000` (**not** the engine defaults of 600 / 2048), so a 700 uu approach takes
~1.7 s including both ramps.

**The day.** Eight steps, then the yard closes and reopens, then four more. Each
refusal is placed where **exactly one** of the three conditions fails, and
`PrepareTest` re-simulates the staged set and refuses to run it (as an Error) if
that stops being true.

```text
staged set 0            open: coins 240, carry 3
                        stall A 30/2 (holds 4)   B 40/2 (holds 3)   C 55/4 (holds 6)
 1  A  buy      240 -> 210,  A 1 left,  1 yours
 2  A  buy      210 -> 180,  A 0 left,  2 yours     stock walks to exactly none
 3  A  REFUSED  sold out, and 180 coins could plainly pay the 30
 4  B  buy      180 -> 140                          a second stall, a second price
 5  C  buy      140 ->  85                          a third stall, a third price
 6  C  buy       85 ->  30
 7  C  REFUSED  30 coins cannot pay 55; there is stock and room
 8  A  REFUSED  sold out at EXACTLY the 30 the purse holds
    -> walk to the gate. THE YARD IS DESTROYED AND REBUILT one place along the row
       reopen: prices 10 / 20 / 70, delivered 3 / 1 / 2, holds 4 / 3 / 3,
               and each fresh stall ARRIVES holding 4 / 3 / 3
       so it must reopen reading: coins 30; A 3 left 2 yours, B 2 left 1 yours,
                                  C 3 left 2 yours; prices 10 / 20 / 70
 9  A  buy       30 ->  20,  A 2 left,  3 yours      the delivery restocked a stall
                                                    that had sold out
10  A  REFUSED  can pay 10, it has 2 left, and 3 of A is all you can carry
11  B  buy       20 ->   0                          the last coin buys: >= is a sale
12  C  REFUSED  nothing left to pay with, so step 11's deduction really happened
```

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
assert: EachStallChargesItsOwnCurrentPrice -- at the settled sample after every
        step the ledger says must succeed, the gate board's shown coins fell by
        exactly that stall's STAGED current price. Fails naming the stall, the
        expected total, the found total, the price and the reading before the step

assert: OneStepOntoTheMatBuysExactlyOne -- (a) at that same sample, that stall's
        shown stock moved by exactly -1 and its shown "yours" by exactly +1;
        (b) no OTHER stall's shown numbers moved at all; (c) from 0.8 s after the
        character settles on a mat until it leaves, THAT stall's three shown
        numbers and the gate board's coins do not change

assert: ARefusedSaleCostsNothing -- at the settled sample after a step refused for
        want of money, the shown coins, that stall's shown stock and its shown
        "yours" are identical to the pre-step sample

assert: SoldOutStaysSoldOut -- the same identity after a step onto a stall whose
        shown stock is 0 (steps 3 and 8; at step 8 the purse holds EXACTLY the
        price, so money cannot be the reason), and, every frame, no stall's shown
        stock is negative

assert: YourHandsAreOnlySoBig -- the same identity at step 10, where the purse can
        pay, the stall has stock, and the only thing standing in the way is that
        the restored holdings are already at the carry limit

assert: TheYardRemembersWhatYouSpent -- at one settled sample 4.0 s after the yard
        reopens, the board reads the balance the day closed on, and each fresh
        stall shows "what it had left + what it was delivered, capped at what it
        can hold" and the count owned -- matched to the stall BY WHAT IT SELLS.
        Fails spelling the sum out: closed with N, delivered D, holds C, so it
        should reopen with X; its sign says Y

assert: TheStallsAreTheMarketsToPrice -- every frame, each stall's LIVE PriceCoins
        equals the price the FIXTURE staged for that goods, AND its shown price
        equals that same staged number. Both halves compare against the fixture's
        number, never against the stall's own live property

assert: TheSignsSayWhatTheYardShows -- at every sample, each sign states a price,
        a count left, a count owned, a delivery and a capacity in the yard's own
        wording; the delivery and capacity are the market's staged numbers; the
        board states coins and the carry limit; and every mirror agrees with the
        parsed text

assert: AStallIsKnownByWhatItSells -- every frame, no stall's GoodsName changed,
        no two stalls sell the same kind, and every stall found after the
        reopening sells one of the three kinds the yard closed with

assert: TheBuyerKeepsWalking -- every frame: the character's input is enabled, its
        move input is not being ignored, its movement mode is not None, its top
        speed is above zero, and it moved no further in one frame than six times
        what walking could carry it

assert: TheYardsOwnNumbersAreStillThere -- exactly three stalls and one board, each
        exposing every property the yard's own displays are written from, and a
        visibly represented player character

assert: TheMarketDayFinished -- at the SENTINEL checkpoint (t = 480 s, far past a
        walk that measures ~130 s) all twelve steps and the reopening must have
        happened; the failure names the step reached and the waypoint it stuck on
```

The checkpoint schedule is 60 logging checkpoints at 6 s intervals plus a
**sentinel at t = 480 s**, because `ACraftBenchFunctionalTest::Tick` ends the test
the moment the last scheduled checkpoint is sampled. A run that completes finishes
`Succeeded` explicitly at the final gate waypoint, long before the sentinel.

**Two things are attributed, not scored** (`HARNESS-PRECONDITION`, an Error):

1. **A staged set that stopped measuring what it claims.** `PrepareTest`
   re-simulates the selected set: every refusal must have exactly one reason, every
   price must move at the reopening, no two prices may be within 8 coins, and the
   reopening must be wrong for all four naive restores (remembered-only,
   delivered-only, kept-what-arrived, added-without-a-cap).
2. **A yard the walk could not be run in** — a waypoint within 150 uu of a counter
   or 250 uu of a mat it is not about, or a leg of the walk that passes that close
   to a counter.

Everything else that could stop the grade — a missing property, a renamed one, the
wrong number of stalls, two stalls selling the same thing — is reachable from
`Source/ThirdPerson/` and is therefore a **named, scored FAIL**, not an
unattributed Error. A submission must not be able to escape grading by deleting a
property.

**One further Error, deliberately:** before anything begins play the fixture empties
the project's save-slot directory, and then checks at the first settled sample that
the yard opened on the staged numbers. If it did not, the run ends as an Error
naming the likely cause — a record written down by an earlier run **in the same
workdir** that the wipe could not reach. A correct submission that obeys the
prompt's "keep the record somewhere that outlives the stalls" is exactly the one
that would otherwise be failed on its second run, and that failure would read as a
model error.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| coins fall by **exactly that stall's** price | `EachStallChargesItsOwnCurrentPrice`, at every settled sample after a successful step | on refused steps (the identity gates cover those) |
| the three stalls charge differently | not a gate but a **precondition**: the set is rejected if two prices are within 8 coins | never |
| **exactly one** per step-on | `OneStepOntoTheMatBuysExactlyOne` (a) | on refused steps |
| standing on the mat does not keep buying | `OneStepOntoTheMatBuysExactlyOne` (c), from 0.8 s after settling until the character leaves | for the first 0.8 s on the mat — three times the disclosed half second |
| a sale touches only that stall | `OneStepOntoTheMatBuysExactlyOne` (b) | never |
| spending your last coin **is** a sale | step 11 is exactly affordable; a `>` instead of `>=` fails `EachStallChargesItsOwnCurrentPrice` | never |
| a refusal for want of money changes nothing | `ARefusedSaleCostsNothing` (steps 7 and 12) | never |
| a sold-out stall sells nothing however much you carry | `SoldOutStaysSoldOut` (steps 3 and 8) | never |
| stock never reads less than nothing | `SoldOutStaysSoldOut`, every frame | never |
| a full pack refuses a sale you can afford | `YourHandsAreOnlySoBig` (step 10) | never |
| within **half a second** of stepping on | every graded sample is taken at least 1.5 s after the character leaves the mat, and the stability probe arms at 0.8 s | never |
| the purse comes back | `TheYardRemembersWhatYouSpent` | never |
| the holdings come back, and come back **live** | `TheYardRemembersWhatYouSpent` for what is shown; `YourHandsAreOnlySoBig` for whether it is real | never |
| stock = left + delivered, capped at capacity | `TheYardRemembersWhatYouSpent`, and step 9 proves it is live stock and not paint | never |
| a stall is known by what it sells | the reopening sample is matched by goods, and the stalls come back rotated one place | never |
| prices do **not** come back | `TheStallsAreTheMarketsToPrice`, both on the sign and on the stall | never |
| the market's delivery and capacity are not yours | `TheSignsSayWhatTheYardShows` compares both against the staged numbers | never |
| the displays are the yard's wording | `TheSignsSayWhatTheYardShows` | never |
| do not stop them walking / take their controls / move them | `TheBuyerKeepsWalking`, every frame | never |
| do not spawn anything | not gated directly; a spawned pickup changes no shown number, so it can only lose. **Declared, not claimed** — see Hidden invariants | always |
| the day gets walked at all | `TheMarketDayFinished` at the sentinel | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched: 6.** Two edits to the supplied scaffolds
  (`MarketStallActor.{h,cpp}` — bind the mat's begin/end overlap, latch, register
  with the keeper; `MarketLedgerActor.{h,cpp}` — register with the keeper), plus
  two new pairs: `MarketDayRecord.h` (a `USaveGame` holding coins, a
  `TMap<FName,int32>` of holdings and a `TMap<FName,int32>` of per-stall stock) and
  `MarketKeeperSubsystem.{h,cpp}` (a `UGameInstanceSubsystem` holding the purse,
  the holdings and the reconciliation).
- **LOC: ~330** across those files, of which ~150 is the keeper.
- **Honest senior-dev hours: 3–5.** Where they go: ~30 min on the transaction
  order (three tests, then five changes, with every refusal path leaving all five
  untouched); ~30 min on the mat listener and its latch; ~90 min on the record —
  deciding what is in it (coins, per-goods holdings, per-goods stock) and what is
  emphatically not (the price), keying it by goods rather than by index, writing it
  after every change rather than once, and reconciling on a fresh actor so it
  overrides what the stall arrived with instead of being overwritten by it; ~30 min
  keeping two displays truthful on every path including the refusals; ~60–90 min in
  the PIE loop, because four of the failure modes only appear after the reopening.
- The reference deliberately does **both**: it keeps the live state on a game
  instance subsystem (which is what makes it survive the actors) *and* writes it to
  a save slot after every change (which is what makes it survive the process). The
  grade requires neither route.

## Anti-gaming notes

1. **Serialising the stall.** *Failure mode*: the record keeps `{goods, price,
   stock}` together, because those three things are what a stall *is*, and writes
   all three back on restore. *Defense*: `TheStallsAreTheMarketsToPrice` compares
   both the live `PriceCoins` and the shown price against **the price the fixture
   staged**, never against the stall's own property — so writing the stale price
   onto the stall does not make "shown equals live" a defence. Every goods' price
   changes at the reopening and the fixture refuses a set where it does not. This
   is the one gate where the natural fix for the restore ("save more") breaks
   something else.
2. **Restoring by assignment.** *Failure mode*: `Stock = Remembered` — the shape
   that is right until the market starts delivering. *Defense*: set 0 reopens on
   3 / 2 / 3 where the remembered values were 0 / 1 / 2, the delivered-only values
   would be 3 / 1 / 2, the values the fresh stalls arrive holding are 4 / 3 / 3, and
   the uncapped sum would be 3 / 2 / 4. `PrepareTest` refuses to run a set unless
   all four of those are wrong about at least one stall, so the gate can never be
   vacuous.
3. **Restoring the display, not the state.** *Failure mode*: repaint the signs and
   the board from the record and leave the fresh stalls' live stock and the live
   holdings alone. *Defense*: three post-reopening steps are behavioural, not
   visual — step 9 buys from a stall that had sold out (so the delivery must be
   live), step 10 is refused only because the **restored holdings** are at the carry
   limit (so the holdings must be live), and step 11 spends the purse to exactly
   zero (so the purse must be live).
4. **Keying the record by index or by where a stall stands.** *Failure mode*:
   `Stock[0]`, or a lookup by transform. *Defense*: the three stalls come back
   rotated **one place** along the row — a shift, not a swap, so every stall moves —
   and the reopening sample is matched to a stall by what it sells. Every leftover
   lands on the wrong stall and all three numbers are right about the wrong thing.
5. **Writing the record once.** *Failure mode*: create it when it is first needed
   and never rewrite it. *Defense*: the reopening expects the state after step 8,
   not after step 1; the gate names both the number it wanted and the number it got.
6. **Reading the level instead of the world.** *Failure mode*: hard-code the
   prices, stocks, capacities and purse found in the committed `.umap`. *Defense*:
   the fixture stages entirely different numbers before any `BeginPlay`, three sets
   of them, and the authoring script refuses to save a level whose numbers have
   drifted into agreeing with the fixture's.
7. **Freezing or shoving the buyer.** *Failure mode*: disable input on step-on and
   re-enable it only on the success path, or push the character off the mat when
   they cannot pay. *Defense*: `TheBuyerKeepsWalking` reads the pawn's own
   input-enabled flag, whether its move input is being ignored, its movement mode
   and its top speed every frame, and bounds how far it may travel in one frame;
   `TheMarketDayFinished` catches anything that stalls the walk without tripping
   those.

## Hidden invariants

- **The staged numbers are re-derived, not asserted.** Every expectation the gates
  hold is computed by simulating the selected set against the twelve steps, so a
  change to the table moves the expectations with it and cannot leave a stale
  constant behind. The table is data; the shape is checked.
- **Both halves of the price gate compare against the fixture, not the world.** A
  gate of the form "what is shown equals what the stall says" is satisfied by a
  submission that corrupted both. This one is not.
- **The mirrors are never trusted alone.** `LastShownPrice` / `LastShownStock` /
  `LastShownOwned` / `LastShownCoins` are written by supplied code that the agent
  may nonetheless edit, so every sample parses the rendered `FText` and requires
  the mirror to match it.
- **Declared hole — "do not spawn anything" is not gated.** No assertion counts
  actors. The requirement is in the prompt because a solution that drops physical
  goods on the floor is not what is being asked for, but the fixture measures
  shown numbers and behaviour, and a spawned object changes neither. It is recorded
  here as unenforced rather than claimed as defended.
- **Declared hole — durability is not distinguishable from persistence in memory.**
  The reopening destroys the *actors*, not the process, so a record on a game
  instance subsystem restores correctly without ever reaching disk. The prompt
  therefore asks only that the record outlive the stalls and the board, which is
  exactly what the fixture can see. The earlier draft of this task asked the agent
  to "write it down" and had no gate for it; worse, obeying that sentence was the
  only way to trip the stale-slot hazard the save-directory wipe now guards. The
  demand was removed rather than left unmeasured. The clean upgrade — a second
  fixture on a second map, since each PIE session gets a fresh `UGameInstance` — is
  a follow-up, not a promise this task keeps.
- **`DisableInput` on a possessed pawn is measurable here, and was checked.**
  `APawn::DisableInput` sets `bInputEnabled`, which `APlayerController::BuildInputStack`
  reads and `APawn::InputEnabled()` exposes — so the "lock the player at the till"
  answer is caught even though the fixture drives through `AddMovementInput` rather
  than through the input stack.
