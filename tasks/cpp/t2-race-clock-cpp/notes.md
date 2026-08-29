# t2-race-clock — provenance and design decisions

## Imported from

`t2-score-attack` in an internal design note (not shipped)
(Hardening Status: **ALREADY STRONG**, 7-check rubric, `PASS = 7/7`).

Companion rows read while authoring:

- an internal design note (not shipped) → `t2-score-attack`
  (Readiness: *Draft contract*; primitives `timer-framerate-legs|pie-checkpoint-sampling`;
  layers `L1|L2`; named assertions `AssertScoreZeroAtStart | AssertNoScoreWithoutPickup |
  AssertScoreRisesOnPickup | AssertTimerExpires | AssertScoringFrozenAfterTimeout |
  TerminalStateExclusive`).
- an internal design note (not shipped) §1 row 3
  (`ADOPT+FIX · hardfail · leak`, basket `bp`, family **F-A** `L_RaceArena`).
- an internal design note (not shipped) §8 row 3
  (MED, 5 h) and §7.1.1–§7.1.4 (the four staging conventions).
- `an internal design note (not shipped):932` — "the only
  corpus row whose graded state is rendered on screen". That is why this row was
  kept at all, and it is why the readouts are **graded** here rather than
  cosmetic.

## What the owner said

an internal working note (not shipped), item `1:t2-score-attack`:

> answer: **agree**
> note: "We could deduct it to 10 seconds to be quicker. "

Applied literally: the round is **10.0 s**, not the corpus's / feedback's 60.
Note the direct conflict this creates with `startup-feedback.md` §1 row 3, which
says *"state the round length as 60 seconds in the prompt"* — the owner's later
verdict note wins, and the prompt discloses 10.0 s. Do not "fix" it back.

## What changed from the corpus row, and why

**The two owner-mandated fixes**

- **Deleted the route hard-fail.** The corpus row's *"The HUD must be authored
  without generated C++ or Slate"* + *"Scope violation forces FAIL 0/7"* zeroes a
  correct submission for picking a legal route (owner ask G / directive D5;
  §1 row 3 *Sinks it*). Only the positive requirement survives — the three named
  readouts must be live on screen and match the authoritative values. The route
  observation survives as a **non-gating advisory line** logged after the verdict
  (`[t2-race route] hud=supplied-asset|replaced|native (non-gating)`), which the
  spec states explicitly can never flip PASS/FAIL.
- **Split check 4 three ways, across two channels.** Corpus check 4
  (`HudTracksAuthoritativeScore`) folded four sample points into one point, so
  "stopped updating at timeout" and "never bound at all" were the same failure.
  The split is `4a ScoreReadoutFollowsFirstCoin` (score channel, at cp1 — the
  first moment the authoritative score differs from the supplied literal `0`),
  `4b ClockReadoutFollowsTheRunningClock` (clock channel, at cp1 — differs from
  the literal `10`), and **`4c-clock` + `4c-state`** (cp5) — two gates with two
  literals. An earlier draft AND-ed them under one message, which reproduced the
  exact fold this row exists to undo: a clock readout that binds while the state
  readout does not was indistinguishable from the reverse.
  **4c has to
  live on the clock and state channels, not the score channel**: after timeout
  the score legitimately equals its pre-timeout value, so a frozen score readout
  is indistinguishable from a correct one. A HUD that stopped updating at timeout
  shows the last pre-timeout clock (~`1`) and `InProgress`; a correct one shows
  `0` and `TimedOut`. That asymmetry is the whole reason the split works, and it
  is why the round state got an on-screen readout of its own.

**Owner's-bar changes (the batch conventions)**

- **Everything graded is on screen.** Three named readouts — `ScoreText`,
  `ClockText`, `StateText`. No graded number is log-only. Pre-state is
  photographable (score `0`, clock `10`, `InProgress`, seven coins on the floor)
  and so is the end state (score `N`, clock `0`, `TimedOut`, four coins gone,
  three still there).
- **The control is scored, and gauged at every checkpoint.** `Coin_Ctrl` at
  `(-600, +300)`, 300 cm from `Coin_B`, both in one camera frame, never contacted;
  presence + visibility + transform + `PointValue` are asserted at all eight
  checkpoints, and cp7 asserts the final total equals exactly the four collected
  coins' values, i.e. the control contributed nothing.
- **Trigger is walking into something; every trigger fires ≥ twice.** Scoring
  fires 4x (Coins A–D), the no-re-score rule fires 3x (the back-track re-crosses
  all three consumed spots), the post-timeout freeze fires 2x (Coins E and F).
  Zero key presses anywhere. The deadline itself is a one-shot by nature; its
  second independent firing is the **20 Hz `fps_legs` leg**, a second world at a
  different timestep asserting the same absolute 10.0 s.
- **Coin count grew from "declared coins" to seven with explicit roles**
  (A–D pre-deadline, E–F post-deadline, Ctrl untouched). `Coin_D` is the one that
  is not in the corpus row at all: it is collected **late** (~7.6 s) purely so
  that a submission which freezes scoring early — which satisfies every
  post-timeout check for free — is caught. Without a late pre-deadline coin,
  "froze at 5 s" is unobservable.
- **The character is visibly represented.** `ARaceCollector`'s constructor
  assigns `SKM_Manny_Simple` + `ABP_Unarmed` from the read-only
  `/Game/Characters/` pool. This is a deliberate departure from the shipped
  `ASprintCharacter` (`Source/ThirdPerson/Tasks/tp2-sprint-stamina/SprintCharacter.cpp`),
  whose constructor stamps a tag and nothing else — so tp2's pawn is invisible,
  which is the exact defect `PawnVisiblyRepresented()` was added for. Do not copy
  that scaffold verbatim.
- **The collector is staged by the map's game mode, not by the fixture.** So a
  human pressing Play drives the *same* class from the *same* PlayerStart with
  WASD that the fixture drives with the per-frame movement timeline — "same
  observable, two drivers" is literal here, not approximate.

**Hardening beyond the corpus row**

- **Both sides of the HUD check are no longer submission-owned.** The corpus
  row's weakness (called out for the sibling row §1 #2: *"Both sides of
  `HudMatchesState` are submission-owned … a shadow counter passes it"*) is
  closed here without needing that row's out-of-band-write leg, because the
  fixture has an **independent** expected value on every channel: the score from
  the coins' own reflected `PointValue`, the clock from
  `GetWorld()->GetTimeSeconds()`, the deadline from its own 10.0 s constant. Each
  readout is gated against the independent expectation **and** against the round
  marker's authoritative property, with distinct named failures — the divergence
  law from §8 row 4 ("5 reads the state, 6 reads the transform").
- **Per-coin values are the hidden-value pattern.** Mechanism, count and range
  (5–100) are disclosed; the numbers are not. A hardcoded per-coin amount cannot
  satisfy both the three-coin sum at cp1 and the four-coin sum at cp3. Declared
  in `## Hidden invariants` per the batch rule.
- **Four continuous every-tick guards (G1–G4)** rather than point samples only:
  pre-contact score, no-early-`TimedOut`, no-late-`InProgress`, and no negative
  clock frame. A point sample cannot see any of these between checkpoints.
- **Grafted `t1-countdown-ends-match`'s one surviving check.**
  `startup-feedback.md` §4a: *"Carry one check it does not have: the countdown
  never displays a number below zero."* That is guard G4 plus the exact-`0` reads
  at cp5 and cp7. Credit recorded here so the graft is not re-filed later.
- **Demoted the free-for-empty checks to preconditions.** cp0 (score `0`, state
  `InProgress`, seven coins present, HUD on screen) is unscored: the supplied
  baseline already satisfies all of it, so scoring it would hand an empty
  submission points. Same move as §8 row 1's "demote checks 1–2".
- **Declared a tolerance for the deadline, in the prompt.** ±0.5 s around 10.0 s.
  Undisclosed thresholds are how §8 rows 5/6/8 were flagged; this one is stated.
- **Deliberately NOT graded:** whether a *post*-deadline coin disappears when
  contacted. Both answers are legal for "adds nothing", so gating it would
  false-FAIL a correct submission. Stated in the spec so nobody adds it.

**Format / plumbing decisions**

- **`deliverable_root:` is NOT in the front matter.** `tools/verify-single/spec.py`
  `_KNOWN_KEYS` rejects unknown keys with a hard `ValueError` → exit 2 "spec
  malformed", never a graded FAIL. Verified by feeding the parser a copy of this
  spec with the key added: *"unknown front matter key(s) … deliverable_root"*.
  So `tasks/README.md`'s mandatory mitigation is satisfied the
  other way the batch conventions allow: the deliverable root is the **first line
  of `## Workspace state pre-task`** and is repeated in the prompt body. Both are
  agent-visible — `tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS` is
  exactly `('Prompt given to the agent', 'Workspace state pre-task')`, and the
  extraction was run against this file to confirm both statements reach the
  agent. The README should be amended to say "front matter *or* the prose of an
  agent-visible section" — that is a README fix, not a spec fix.
- **Heading name.** The batch brief says `## Workspace pre-state`; the normative
  heading in `docs/AUTHORING_TEMPLATE.md` — and the FROZEN one in
  `prompt_extract.py` — is `## Workspace state pre-task`. Used the frozen one; a
  rename would silently make the section invisible to the agent.
- **Section order** follows `AUTHORING_TEMPLATE.md`'s normative atomic order
  (Primary concept → Prompt → Workspace state pre-task → Verifier specification →
  Reference solution metadata → Anti-gaming notes → Hidden invariants), **not**
  the order shipped in `tasks/cpp/tp2-sprint-stamina/task.md`, which re-orders
  them. The template is the format law.
- **Authored ATOMIC, not compositional**, despite being a T2 "Game Composition"
  corpus row. Compositional requires a public production-pattern citation (Hard
  Rules #1/#4) and no verifiable public artifact for "timed score-attack round"
  was found; fabricating one is worse than filing it atomic. Every shipped T2 in
  the tree (`t2-hud-layout-and-countdown`, `tp2-sprint-stamina`) is atomic too.
- **`concept_id: game-mode-and-game-state`** (Gameplay Programming, `high`,
  `in_scope: yes`). Deliberately not a UI concept: the graded core is the
  authoritative round state, and the owner explicitly de-weighted the HUD route.
  **Note for anyone copying `t2-hud-layout-and-countdown`: its cited
  `umg-widget-basics` does not exist in `tools/coverage/concepts.csv`.** Do not
  reuse that id.
- **`set: craftbench-public`** parses — `set` is an unvalidated free scalar in
  `spec.py` (line 301), so the new set name needs no parser change.
- **The prompt is ~270 words, over `AUTHORING_TEMPLATE.md`'s 50–200 guidance.**
  Knowing deviation, not an oversight: the batch's disclose-every-graded-number
  rule and the seven-clause behavioural contract cannot both fit under 200 words
  without dropping a disclosed number, and an undisclosed threshold is a false
  FAIL on correct-but-conservative work — the harder rule wins. Shipped
  `tasks/cpp/tp2-sprint-stamina/task.md` is ~250 words for the same reason. Every
  sentence in the prompt either states a disclosed number, a graded observable, or
  the deliverable root; there is no prose left to cut.
- Verified with the real tooling, not by eye: `spec.py::parse_task_file` parses
  the front matter (`fps_legs=(60, 20)`, one fixture), the same parser **rejects**
  a `deliverable_root:` variant, `prompt_extract` returns both agent-visible
  sections with the deliverable root appearing 3x, exactly one H1, all seven H2s
  canonical, and `cb lint` reports this spec with only the two
  build-verifier-owned errors (missing fixture source, missing `.umap`) plus the
  standard no-reference-yet warning — no `spec-h2-allowlist`, no `prompt-jargon`,
  no `anti-gaming-count` warning.

## What still needs building

Nothing under `reference/` or `discrimination/` was created here — that is the
build-verifier skill's job. `cb lint` currently reports this spec with exactly
the same two errors as its four sibling batch tasks (missing fixture source,
missing committed `.umap`) plus the standard missing-reference warning.

**1. The map — `Content/Maps/L_RaceArena.umap`**
(committed binary; the only map source). Family **F-A**, from the §7.1.1 showroom
script: 4000x4000 floor, 200 cm stripe decals, PlayerStart at `(-1400, 0)` on the
floor facing `+X`, two *visibly different* landmark pillars at `X = ±1600`, world
settings selecting `ARaceGameMode`. Placed: one `BP_RaceRound`, one
`ARaceTheClockFunctionalTest`, and the **seven** `BP_RaceCoin` instances at the
exact coordinates in the spec's table, each with its own per-instance
`PointValue` override in 5–100 (make all seven distinct, and make no two subsets
sum equal — otherwise a lucky wrong grouping passes cp1 or cp3).
**The basename `L_RaceArena` is unique repo-wide, and the earlier claim here was
wrong.** This spec originally declared `L_CollectArena`, which
`tasks/craftbench-public/t2-collect-then-exit/` also declares — and the note that
"F-A is a shared staging shape, not a shared file, so per-task foldering makes it
safe" was **false against the runner**. `map_locator._map_candidates` globs
`Content/Maps/<map>.umap` **and** `Content/Maps/*/<map>.umap`, and `locate_map`
raises `DuplicateMapBasenameError` on two or more candidates → **exit 7
HARNESS-ERROR for every submission of BOTH tasks**, with `cb lint` staying green
because `tasklint._check_map` is satisfied by any one tracked copy. Renamed to
`L_RaceArena` 2026-08-17; `t2-collect-then-exit` keeps `L_CollectArena`. F-A
remains a shared staging *shape*: the two maps are independently authored to the
same §7.1.1 showroom recipe, and neither file is shared.

**2. `cameras.json` (the camera-plan lane; not part of this release)** beside the map (authoring-time, per the camera-plan
standard): a shot framing `Coin_B` + `Coin_Ctrl` + the round marker + ≥ 4 floor
stripes, and a shot that keeps the HUD legible at the deadline. Presentation-only,
non-gating.

**3. The baseline assets under `Content/Tasks/t2-race-clock-cpp/`** —
`BP_RaceCoin` (visible coin mesh, ~60 cm contact region already detecting the
character, tag `RaceCoin`, editable `PointValue`, **no scoring**), `BP_RaceRound`
(visible short post, tag `RaceRound`, the three exposed properties at their
defaults, and *only* the "put `WBP_RaceHud` on screen when play begins" logic),
and `WBP_RaceHud` (three text readouts named `ScoreText` / `ClockText` /
`StateText` holding the hardcoded literals `0` / `10` / `InProgress`, bound to
nothing, with labels in separate readouts). The frozen HUD is deliberate: it
makes the empty submission a *legible* FAIL a reviewer can photograph.

**4. The C++ scaffold under `Source/ThirdPerson/Tasks/t2-race-clock-cpp/`**
— `RaceCoinBase`, `RaceRoundBase`, `RaceCollector` (assign
`/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple` and
`/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed`; the stock
`AThirdPersonCharacter` is `UCLASS(abstract)` so the subclass must be concrete),
`RaceGameMode`.

**5. The fixture — `Source/CraftBenchTests/Tasks/t2-race-clock-cpp/RaceTheClockFunctionalTest.{h,cpp}`**,
deriving `ACraftBenchFunctionalTest`. Two duplications are deliberate and
owner-approved; **do not edit either base class** (they belong to the other
machine): (a) the visible-mesh predicate, because
`ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented()` is bound to that base's
own `Pawn` member and is unreachable from here; (b) the waypoint drive loop, per
the shipping pattern at `TeleportPortalFunctionalTest.cpp:194`,
`LadderClimbFunctionalTest.cpp:246`, `NpcFollowFunctionalTest.cpp:144`. Note that
this task needs **no** second-pawn spawner at all — its control subject is a
map-placed coin, so the base class's one-pawn limit never binds.

**6. Calibration duty, and the two real risks.**

- **`fps_legs: [60, 20]` has never run from front matter.** The
  `timer-framerate-legs` primitive itself is PROVEN
  (`docs/pie-verification-playbook.md:25`, on the since-retired
  `gp-timer-delayed-destroy`), but it ran through the hardcoded
  `run_task._DT_LEGS_BY_TASK` dict, which is **empty today** (`run_task.py:193`).
  The front-matter route is implemented and wired
  (`layers/registry.py:196-215`, all legs must pass, fail-fast) and no shipping
  task declares it — `grep fps_legs tasks/` returns only a prose mention in
  `tasks/cpp/t1-gameplay-tag-gate/task.md`. So this spec is the **first
  consumer**. Verify the reference passes *both* legs before shipping. Fallback
  if the 20 Hz leg proves flaky for reasons unrelated to the submission: drop to
  `fps_legs: [60]` and add a note — do **not** loosen the deadline tolerance to
  make a rate pass, because the tolerance is disclosed in the prompt and
  widening it silently changes the graded contract.
- **All eight checkpoints must land on a frame boundary at BOTH rates.**
  `{0.6, 3.6, 6.0, 8.8, 9.4, 10.9, 12.4, 13.6}` are all exact multiples of 1/60
  and of 0.05, which was chosen deliberately. Any re-timing must preserve that.
  The slack between the modelled waypoint arrival and its checkpoint is ≥ 0.9 s
  on a ~2.7 s traversal (≥ 30%), assuming the stock 500 uu/s max walk speed —
  re-measure the actual arrival times at both rates and log the
  `[t2-race calib]` line before trusting any of them. A behind-schedule drive
  must report through the `HARNESS-PRECONDITION:` message prefix
  (`TeleportPortalFunctionalTest.cpp:128`) so triage can tell a staging problem
  from a model failure.
- `TimeLimit` lands at 15.6 s per leg (last checkpoint + the base's 2.0 s
  margin), so the two legs cost roughly 2 x 16 s of PIE plus map load.

**7. Discrimination variants.** The automatic `reference PASS` / `empty FAIL`
legs plus the requirement-to-gate table in the spec are the mandatory artifacts
(owner decision 2026-08-11). If a hand-authored variant is wanted, the corpus row
already names the three worth writing — constant score, per-tick score, and
no-freeze — and the spec's anti-gaming entry 3 (freeze-everything-early) names a
fourth the corpus did not have. Each must FAIL on its **named** assertion, not
merely differ from the reference.
