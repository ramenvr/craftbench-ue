# Discrimination matrix - t3-guard-aims-only-at-the-visible-target

Status: **5/5 ADMISSION PASS; GOVERNED REFERENCE PASS; GOVERNED EMPTY
FAILS AT THE PREDICTED L2/L2I GATES; REFGATE PENDING**.

Fresh dynamic-nav admission rounds 02-06 each executed the exact fixture and
passed all five named L2 gates with identical visible/lost/reacquired identity,
revision, aim, and locomotion telemetry. The retained two-layout map, empty
baseline, and complete reference have all passed independent cold readback.
Governed reference attempt 01 established L1 PASS and L2I 2/2 but exposed an
authored RightLow nav-bounds harness Error. The repaired map now hard-gates 8
projected endpoints and 4 complete paths; the subsequent focused reference
probe passed both layouts and all five gates. The fresh governed reference from
corrected Git HEAD then passed L1, both L2 fixtures, and L2I 2/2. The governed
locomotion-only baseline passed L1 but failed both L2 fixtures at
`PerceivedTargetDrivesAdditiveAimOverlay` with no harness precondition and
failed L2I 0/2 because the additive aim route was absent. Other shortcut rows
remain additional hardening rather than blockers for this proven reference /
empty discrimination pair.

| submission | expected verdict | expected named evidence |
|---|---|---|
| `../reference` | PASS | both layouts pass 5 L2 gates and 2/2 L2I |
| empty locomotion-only baseline | FAIL | `PerceivedTargetDrivesAdditiveAimOverlay`; L2I additive check |
| nearest/GetAllActors target | FAIL | `OnlySightPerceivedIdentityMayDriveAim` |
| cached stale target | FAIL | `OccludedTargetStopsDrivingAim` |
| rotate controller/pawn | FAIL | `PerceivedTargetDrivesAdditiveAimOverlay` or `BaseLocomotionRemainsContinuous` |
| non-additive montage/full-body pose | FAIL | `AimOffsetIsAdditiveOverLocomotion` |
| pause movement while aiming | FAIL | `BaseLocomotionRemainsContinuous` |
| hardcoded one-side values | FAIL | opposite layout directional pose gate |

## Requirements table

| Requirement | Independent evidence | Shortcut rejected |
|---|---|---|
| Exact visible identity drives aim | engine current/known sight sets plus controller target and hidden-decoy absence | nearest actor, `GetAllActors`, cached actor |
| Occlusion clears and reacquires | real perception revision, failed stimulus/forget, later same-identity reacquisition | stale target boolean or timer |
| Overlay is genuinely additive | fixed compiled AnimGraph route and evaluated main-control spine delta | montage, full-body replacement, controller rotation |
| Locomotion remains live | simultaneous control, walking mode, per-phase displacement, dense frame step and facing | pause, teleport, root rotation |
| World facts generalize | two sides/elevations and separate scenario identities | constants tuned to one layout |

## Admission requirement

Five fresh admission rounds, the focused exact-two final reference probe, and
the governed reference/empty production pair are complete and stable. The
reference passes all layers; the empty baseline fails the predicted L2 and
L2I checks without a harness failure. Nearest-target, stale-cache,
controller-rotation, and montage controls remain optional additional rows when
their isolated submissions are available. Official refgate/certification and
owner-play remain before promotion.
