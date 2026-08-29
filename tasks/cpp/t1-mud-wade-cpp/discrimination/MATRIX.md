# Discrimination matrix — t1-mud-wade

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `the figure waded the patch at a measured 30-50 percent` | The figure notices the tagged patch every frame, drops `MaxWalkSpeed` to 40% of its own normal top speed, and plays the SUPPLIED clip on the mesh so the wade genuinely drives the pose; leaving puts back both the speed and the animation blueprint it recorded at BeginPlay rather than a guessed one. |
| `empty` | FAIL | `WadesSlowlyThroughTheMud: on the patch the figure measured` + `and the level asks for 30-50` | The unmodified scaffold compiles, so L1 is green. Nothing notices the patch, so the figure walks it at full speed with the ordinary walk still driving the pose. |

## What carries the discrimination without variants

**Speed is judged from MEASURED ground speed** -- distance actually covered per frame,
smoothed so one hitching frame cannot decide a verdict -- never from `MaxWalkSpeed`. A
submission that sets the number without the figure slowing down does not pass, and one
that slows the figure by any legitimate means passes regardless of how.

**The reference speed is measured on THIS run, not assumed.** The fixture averages the
graded figure's clean-ground speed before it first touches the patch, and every band
below is a fraction of that. So "40% of normal" cannot be satisfied by quietly
changing what normal is -- and the clean-ground speed is separately checked against the
400-600 band the prompt discloses, which is what catches a submission that slows the
ordinary walk instead of adding a wade.

**The pose question is answered by asking the MESH.** `WadeDrivesPose` reads the
single-node player's current asset and the active montage, and accepts either route --
so a submission is free to drive the clip however it likes, and cannot answer by
setting a flag. Two named gates hang off it: the wade must drive the pose while the
figure is slowed, and the ordinary walk must be back after it leaves.

**Both directions carry the half-second the prompt states**, and both are checked
continuously rather than at a sample: entering, the figure has 0.5 s to be inside the
30-50% band with the wade driving; leaving, 0.5 s to be back inside 85-115% with the
wade gone.

**The control is a second, identical figure patrolling a parallel lane** 600 cm clear
of the mud, driven by the fixture so its speed is a real measurement rather than a
still reading. It may never drop below 70% of the graded figure's clean-ground speed,
and the wade may never drive its pose -- which is what stops a submission slowing
everything, or swapping the animation globally, and calling it a wade.

**Two crossings, and the second must behave like the first.** The route walks past the
patch, back, and past again; the sentinel gate fails if fewer than two crossings
happened or if the wade drove the pose on fewer than two of them, each with its own
message, so a one-shot implementation is diagnosable rather than merely absent.

## The supplied clip

`Content/Tasks/t1-mud-wade/A_MudWade` is SUPPLIED content, not
the agent's work: the authoring script duplicates a visibly different mannequin gait
into place before the level is built, and the authoring script REFUSES to save a level
whose pawn cannot resolve it. What the agent has to build is deciding WHEN it drives
the pose.
