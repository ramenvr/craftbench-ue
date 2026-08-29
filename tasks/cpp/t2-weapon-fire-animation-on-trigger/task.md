---
id: t2-weapon-fire-animation-on-trigger
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_FireAnimation :: AFireAnimationFunctionalTest"]
---

# t2-weapon-fire-animation-on-trigger

A fire action that plays a one-shot body animation on the **ThirdPerson
substrate**: on request, the possessed playable character's body plays a
firing animation exactly once — starting promptly, running its natural
length, ending on its own — and plays nothing before any request. Sourced
from an earlier internal task list (not shipped) ("Weapon attachment system" —
the hardest kind of row of its block). The source row's ATTACH half (weapon in the character's
hand) already ships as `bp/t2-weapon-held-in-right-hand` and is cut here
with that pointer; its "arm stretched out" pose is cut for having no
deterministic observable; the mouse-click trigger is rephrased to the
substrate's programmatic `Do*` seam convention because headless PIE has no
key events (the tp2-sprint-stamina precedent). What remains — the net-new
half no shipping task grades — is trigger-driven one-shot animation playback,
judged from the anim instance's montage state over time.

## Primary concept

- `anim-montage` — Animation montage playback
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-montage-in-unreal-engine)

The load-bearing behavior is trigger-driven one-shot animation playback on a
possessed character — starting, advancing, and ending a montage on the body's
anim instance in response to a gameplay request, without disturbing the
underlying locomotion.

## Prompt given to the agent

> Give the character the player controls a fire action:
>
> - Expose a function on the character named exactly `DoFireStart`. It takes
>   no parameters and must be declared so the engine's reflection system can
>   find and call it (the character's existing jump functions follow the same
>   convention). Each call requests one firing action.
> - When a fire is requested, the character's body must visibly play a firing
>   animation: it starts promptly (within a fraction of a second), plays
>   forward at normal speed for its natural length — about a second or two,
>   like a real weapon-firing motion — and then ends on its own. It must not
>   loop or keep playing indefinitely.
> - The firing animation must play as an OVERLAY on top of the character's
>   existing animation setup, which must stay in place throughout: the body's
>   normal idle/locomotion animation resumes seamlessly when the firing
>   motion ends. Do not swap out or replace the character's animation setup
>   to play the clip.
> - Before any fire has been requested, the body must not be playing any such
>   animation — the character just stands under its normal idle locomotion.
> - A fire requested while the firing animation is still playing may be
>   ignored; what matters is that one request produces one animation, not a
>   permanent state.
>
> The project's animation content (the mannequin's clips under the Characters
> folder) is available to use; any clip that reads as a firing/attack motion
> is acceptable. Correctness is judged by the character's animation state
> over time: silent before the request, a forward-playing animation after it,
> and a return to silence once it has run its natural length. Implement in
> C++ in the existing gameplay module — do not edit the level, any config
> file, or any test file.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`
  with its `DoMove`/`DoJumpStart`/`DoJumpEnd` input seams, game mode, the
  Variant_* trees). No edit needed, though the character sources show the
  house convention the new function must follow.
- `Tasks/t2-weapon-fire-animation-on-trigger/FireCharacter.h` / `.cpp` —
  declares and defines `class THIRDPERSON_API AFireCharacter : public
  AThirdPersonCharacter` (concrete — the stock template character is abstract
  and unspawnable). Its constructor adds `Tags.Add(FName("FireHero"))` and
  wires the project's standard animated body: the mannequin skeletal mesh
  (`SKM_Manny_Simple`) and its animation blueprint (`ABP_Unarmed`), so every
  instance starts with a body that can play animations. **No fire function
  and no animation-playing logic ship** — the behavior is entirely the
  agent's to implement (on this class or on the writable stock parent; both
  grade identically).
- `Tasks/t2-weapon-fire-animation-on-trigger/FireGameMode.h` / `.cpp` — a
  game mode whose constructor sets `DefaultPawnClass =
  AFireCharacter::StaticClass()`. The task map's world settings select it, so
  PIE spawns and possesses the tagged character at the PlayerStart.
- `Content/Maps/t2-weapon-fire-animation-on-trigger/L_FireAnimation.umap` —
  a flat floor, a PlayerStart, and one placed `AFireAnimationFunctionalTest`.
- `Content/Characters/Mannequins/...` — the stock mannequin meshes, animation
  blueprints, and clips (idle/jog/attack/death families), readable as anim
  content for the firing motion.

Files that **do not exist**:

- No `DoFireStart` anywhere, no montage/animation-playing code. The empty
  submission compiles (L1 green) and fails L2 at the named seam gate.
- No test source in the agent's writable path. `AFireAnimationFunctionalTest`
  lives in a separate `CraftBenchTests` module the agent cannot read or
  modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-weapon-fire-animation-on-trigger/L_FireAnimation.umap` on the
**ThirdPerson** substrate. The engine ticks the world at a fixed deterministic
step (`-deterministic -FPS=60`). The map's world settings select
`AFireGameMode`, which spawns and possesses the `FireHero`-tagged character at
the PlayerStart. Montage state is read from the body's anim instance —
spike-proven observable headless (position advances exactly with the fixed
dt).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
AFireAnimationFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        resolve hero via GetAllActorsWithTag("FireHero"); assert exactly one
        assert it is a character-type pawn with a body mesh
        resolve DoFireStart by reflection; assert it exists with no real
        input parameters
        (named failure: "... 'DoFireStart' ... (fire seam missing).")
        SetCheckpointSchedule({0.5, 0.8, 1.4, 6.0})
    OnCheckpoint(i):  // Active = the anim instance's current active montage
        cp0 t=0.5: assert Active == null  ("already playing before any fire
                   request"); invoke DoFireStart
        cp1 t=0.8: assert Active != null  ("no firing animation started");
                   record the montage + its playback position
        cp2 t=1.4: if the SAME montage is still active, assert its position
                   advanced >= 0.25s  ("frozen, not playing"); a short clip
                   that already ran its natural length and ended passes
        cp3 t=6.0: assert Active == null  ("it never ended") -> Succeeded
    every checkpoint logs "[t2-fireanim calib] cp<i> t=<t> active=<m> pos=<p>"
    (LogTemp/Display) for calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: hero
resolved by tag, never by class; the fire seam by reflection, so the agent may
implement on the scaffold subclass or the stock parent; the animation is
judged by montage STATE (any clip/slot the agent picks), never by asset name.

## Reference solution metadata

- LOC range: 25-40 added (header: one UFUNCTION + one clip UPROPERTY; cpp:
  ctor clip wiring + a guarded PlaySlotAnimationAsDynamicMontage call)
- Files touched: 2 (both pre-existing scaffold files:
  `FireCharacter.{h,cpp}`)
- Senior-dev hours: 0.25-0.5

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffold compiles with no
   fire function at all; L1 passes. *Defense*: `PrepareTest` resolves the seam
   by reflection (`FindFunction("DoFireStart")`, no real input parameters
   allowed) and FAILs via the named message `fire seam missing` —
   FAIL-on-empty, not differs-from-reference.
2. **Always-playing.** *Failure mode*: a firing-looking animation loops from
   BeginPlay, so "an animation is playing" is trivially true whenever the
   verifier looks. *Defense*: the first checkpoint runs BEFORE any fire
   request and requires the montage state to be empty; anything already
   playing FAILs via `already playing before any fire request`. (The idle
   locomotion driven by the animation blueprint is not a montage and does not
   trip this gate.)
3. **Fake "playing" state.** *Failure mode*: the fire request starts an
   animation and immediately pauses it — an active-but-frozen montage
   satisfies any "is something playing?" existence check. *Defense*: two
   samples 0.6s apart must show the animation's playback position moving
   forward; a frozen position FAILs via `frozen, not playing`.
4. **Permanent fire state.** *Failure mode*: the request starts a looping or
   never-ending animation — right start, no ending, and "one request, one
   animation" is lost. *Defense*: the final checkpoint sits well past any
   natural one-shot clip length (t=6.0s) and requires the montage state to be
   empty again; anything still playing FAILs via `it never ended`.
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD (an on-disk edit never reaches the grade; committed changes are
   review-gated on commit), and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The checkpoint instants (0.5/0.8/1.4/6.0) are not disclosed in the prompt;
  only "promptly", "natural length, about a second or two", and "ends on its
  own" are. A point-fit solution keyed to guessed sample times has four
  independent chances to miss.
- The silence check runs FIRST, before the fixture ever requests a fire —
  an always-playing fake is caught before the trigger path is even exercised.
- The frozen gate compares two positions across 0.6s of fixed-step time — an
  existence-only fake (montage started then paused) cannot satisfy it.
- The end gate at 6.0s leaves generous room for any natural one-shot clip
  (the template's attack clips run ~1-2s) while still catching loops and
  permanent states.
