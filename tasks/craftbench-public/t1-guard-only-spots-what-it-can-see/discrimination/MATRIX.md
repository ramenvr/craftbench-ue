# Discrimination matrix — t1-guard-only-spots-what-it-can-see

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | Each guard decides for itself, every frame, from its own transform and its own two numbers: range, then the angle off the direction it faces, then a line from its supplied eye to the character's chest ignoring both endpoints. The lamp follows that answer on the frame it changes. |
| `empty` | FAIL | `LampLitWhileVisible: a guard could see the character and its lamp was dark` | The unmodified scaffold compiles, so L1 is green. `SetSpotted` exists and works; nothing calls it, so both lamps stay dark including at the very first checkpoint, where the character is 696 uu away and 15 deg off the near guard's facing with a clear line. |

## Requirements table

Every requirement the prompt states, the assertion that checks it, and the condition
under which that assertion does not run. A row with no gate is a hole; a row whose
gate can be skipped is where a submission will aim.

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| lamp red **exactly while** the guard can see the character | `LampLitWhileVisible` — every frame, against the fixture's own recomputed answer | never, once the run reaches `StartTest`; a failed L1 or an unresolvable guard ends the run before it |
| lamp **dark again as soon as** it cannot | `LampDarkWhenNotVisible` — the mirror gate, same frame, same computed answer | as above |
| no more than **1200 units** away | reference trace goes dark at 1246/1605/1275 uu (cp10–12) with range the only condition that changed | if the route never reaches the far stop — `TheRouteWasWalked` fails the run in that case |
| within **45 degrees** of the guard's facing | reference trace goes dark at 86/145/143 deg off facing (cp5–7) with the angle the only condition that changed | as above |
| **no solid object** between the two | reference trace goes dark behind the crate at cp2, `blocker=StaticMeshActor_16` | as above |
| turns red **again every time** the character becomes visible again | `SightWindows` counts the distinct visible spells; the measured reference records 4, and the sentinel gate fails a run with fewer than 2 | never |
| settles within **0.5 seconds** of any change | both lamp gates measure from `ChangedAt`, the frame the fixture's own answer flipped | never |
| the rule belongs to a guard, **not to a particular guard** | `TheWalledGuardNeverSees` + geometric assignment of the blocked guard after the jitter; the guards carry identical tags and facing, asserted at authoring time | attributed, not skipped: a guard that MOVED grades FAIL, a mis-staged yard ends `HARNESS-PRECONDITION` |
| **do not move** the guards, walls, crate or character | the same gate compares each guard against the transform `PrepareTest` left it on, to 1 cm and 0.5 deg | only for a guard the control never catches seeing — a submission that moves the CLEAR guard is not caught here, and is caught by the lamp gates instead, because moving it changes what it can see and the fixture recomputes from where it actually is |
| write the solution **in C++ under `Source/ThirdPerson/`** | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## What carries the discrimination without variants

**The fixture computes its own answer and never asks the submission for one.** Every
frame it recomputes, per guard, whether that guard should see the character — range,
cone angle, and an occlusion trace from the guard's own `Eye` component — and compares
it against what the lamp is doing. `ReadSpotted` deliberately reads the
`AlertLamp` point light's **intensity**, not the `bSpotted` flag: the level asks a
guard to light its lamp, and that is what a reviewer sees. (An earlier draft read
`bSpotted` by reflection, which would have returned `false` forever — the member is a
plain private bool with no `UPROPERTY` — and failed every correct answer.)

**Both directions are gated, and they are one verdict.** `LampLitWhileVisible` fails a
guard that can see and is dark; `LampDarkWhenNotVisible` fails a guard that is lit and
cannot see. Doing nothing fails the first; lighting both lamps unconditionally fails
the second. The corpus row this task came from scored those separately, and an empty
delivery collected 3 of its 4 checks.

**All three conditions are exercised, each on its own, and the trace names which.**
The measured reference run goes dark for a different reason each time: the crate
(cp2), walking behind the guards at 86/145/143 deg off facing (cp5–7), and walking to
1246/1605/1275 uu away (cp10–12). A submission that implements range and angle but not
occlusion passes cp5–12 and fails cp2, and the calibration line says which.

**The control is the second guard, and it is deliberately indistinguishable.** Both
guards are the same class with the same tag, the same facing and no per-instance
marker; which of them the wall blocks is decided **geometrically in `PrepareTest`,
after the jitter**, by tracing from each eye. So a submission cannot special-case by
tag, name or index. `PrepareTest` additionally jitters both guards up to 70 cm and 8
deg and nudges the crate, and the task spec withholds every coordinate — so a
submission keyed on position rather than on sight is reading a stale number.

**A control failure is attributed before it is scored.** `TheWalledGuardNeverSees`
first asks whether the guard is still on the transform `PrepareTest` gave it. If it
moved, that is the submission's doing (the brief forbids moving the guards) and grades
FAIL. If it never moved and can still see, the **yard** is mis-staged and the run ends
as `HARNESS-PRECONDITION`, never as a model failure. This is not hypothetical: on
2026-08-18 a wall that cleared the placed guards stopped clearing the jittered ones and
a correct reference solution FAILED this line.

**The route finishes, and the schedule outlives it.** `TheRouteWasWalked` fails a run
that did not reach the end of its seven waypoints, and the checkpoint schedule carries
a sentinel at t=90 s — far past the ~35 s the route takes — so the base class's
"all checkpoints sampled, therefore success" ending cannot arrive before the graded
events do.

## The staging is solved, not tuned

`authoring/author_map.py` does not carry a hand-chosen wall size. It samples the whole
route as a polyline, works out where the walled guard's sightline crosses the wall's
plane at **every corner of the jitter box**, and sizes the wall to cover all of them
with 60 cm to spare. It then refuses to save the level if the solved wall would reach
across the clear guard's view of the in-front stop, if the crate would, or if the
character's own path would walk into the wall. Three successive hand-tuned spans were
rejected by that check before one passed — twice for a margin that held at the placed
positions and not at the jittered ones.
