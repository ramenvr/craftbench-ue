# notes — t1-touched-crate-lights-up

Authored 2026-08-18 on the ThirdPerson substrate, UE 5.8. Built against the
owner's 2026-08-18 difficulty bar. **Last task of batch 1.**

## Provenance

Startup Eval corpus row `t1-custom-depth-stencil-outline`, adopted per
an internal design note (not shipped) row 12
(`ADOPT+FIX · log-only · leak · id-leak`, MED/7h).

| The review said | What was built | Why |
|---|---|---|
| matched non-target crate 2 m away, never highlighted, never carrying the group value | built, and made LOAD-BEARING: the second crate is not a passive control, it has a **different reach**, so one hard-coded number is wrong about one of them | a control that is only ever "the other one" is passed by any answer that happens to key on the right crate. A control with its own number has to be read. |
| plain → highlighted → plain again | built, and **twice per crate**, with a spell counter that requires at least two separate lightings | "and again" is a different claim from "and back", and an overlap-begin handler with no end passes the first while failing the second. |
| rename because `bt`/`custom-depth-stencil` puts the mechanism in the agent-visible path | renamed | an overlap volume, a distance check in Tick and a timer poll all pass identically. |
| it renders nothing unless the fixture ships the outline post-process material AND `r.CustomDepth=3` via the per-task `ue-config` append lane; without that it is STRUCTURAL_ONLY forever | **not used.** The highlight is a point light plus a material swap on the crate's own body | the review is right that a stencil outline needs both, and the `ue-config` lane really does exist and really does avoid invalidating refgate. But the review's own principle settles it: the prompt is behaviour-only and the mechanism is the agent's choice, so what the task must grade is *the crate visibly lights up*, not *the crate uses the custom depth pass*. A lamp is readable headless, visible when played, and cannot be "set" without effect. STRUCTURAL_ONLY was never a risk here because nothing structural is inspected. |

## The three difficulty axes, and how each is enforced

1. **Two reaches, 260 uu and 520 uu.** The fixture refuses to start if they are
   within 100 uu of each other, and the authoring script refuses to save such a
   level. So the axis cannot be silently lost by a later edit.
2. **The crates swap places between the legs.** The route is recomputed from
   their live positions, so the same schedule lights a different crate the second
   time round.
3. **The highlight has to re-arm.** At least two distinct spells per crate; the
   measured reference records four.

## Two staging faults that failed a correct implementation first

Written up in `discrimination/MATRIX.md`. In short: the route walked through the
crates (solid boxes) and jammed the character at stop 3 of 7 while its highlight
logic was working perfectly, and the authoring script used
`static_mesh_component` on an actor that is not a `StaticMeshActor` — which
raised *after* `new_level()` had already saved an empty package, leaving a
plausible-looking 6 KB map on disk that the automation run reported as "No
automation tests".

The second is worth keeping as a rule: **`new_level()` saves immediately, so a
map file existing is not evidence that the authoring script finished.** Check the
log for the SAVED line, not the filesystem for the file.

## Still to do

The empirical half of the difficulty bar. **No task in this set has been run
against a model.** `cb eval --model claude-p:<cheap model>` on this task, once:
passing first try with zero iteration means it needs another axis.
