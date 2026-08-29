# Alert Stride authoring notes

Status: **AUTHORED / LIVE-SUBSTRATE REFERENCE-EMPTY MATRIX PASS / REFGATE READY**.

The exact production slice is ready for public placement and fresh
committed-substrate refgate certification.

The task-local runtime/verifier, Editor target, and Game target build green.
Five isolated admission assets and the admission map passed independent fresh-
process asset/map readback with byte-stable inputs. Round 01 exposed a real
behavior defect: the original `spine_03` bone-space roll changed the engine
state and linked instance but moved the live hand only 0.038 cm. Round 02 then
exposed an authoring defect: the exposed ModifyBone `Translation` pin default
overwrote the direct struct assignment. The author now writes that exact pin.

Rounds 03 through 07 are five independent exact-one NullRHI/FPS60 admission
passes. Each observed the real `Root,Calm -> Root,Alert -> Root,Calm` sequence,
the exact calm/alert linked instances, ordinary 285 cm/s movement, and stable
live metrics: pose delta 17.999 cm, restoration delta 0.064 cm, and lower-body
maxima 0.008/0.007/0.008 cm. No threshold was relaxed.

The retained incomplete four-asset baseline, read-only layer interface, and
two-fixture final map now pass fresh cold readback. The corrected final map is
59,951 bytes with SHA-256
`9EC800C1595BC4F843D31EFB26C02A4FE0A66F72DE8080A1B8DFCCE5CFF8EA2A`.
The prior map is recoverably quarantined because its actor labels did not match
the Functional Test class names used by automation discovery.

A disposable protected reference closure authored, cold-read, L2I-checked,
harvested, and byte-restored exactly four editable reference assets. The first
governed WIP production run proved L1 Editor+Game PASS and L2I 4/4, but its L2
enumerated zero tests because of the old actor-label map. After installing the
corrected map into the already-built scratch, the reference L2 ran the exact two
fixtures and passed 2/2 from authoritative JSON. The retained empty baseline
then failed both fixtures at the named
`BehaviorStateLinksAndDrivesDeclaredLayer` gate with
`harness_precondition=false`; its fixed L2I failed overall at 1/4 (the montage-
avoidance check correctly remains true). Fresh governed live-substrate
production legs now confirm the same result end to end: reference L1 PASS,
L2 exact 2/2 PASS, L2I 4/4 PASS; supplied empty L1 PASS, L2 exact 0/2 with both
fixtures failing `BehaviorStateLinksAndDrivesDeclaredLayer`, and L2I 1/4.
Neither leg reported a harness precondition.

Reference evidence is under
`<run-out>`; report, L1 log, and L2
log SHA-256 values are
`F438F0CA37410E6C753DE52872DC11160BB7E146AF0712E7EED3F173D99D904B`,
`D056ED04902311643F99E73EE1D5DA6F0479391D7D04F25213F21C4C78BE2C4F`,
and `0409173C33041F1167976470BAE813E498AA4C03A17231752B17191A3A3131BD`.
Empty evidence is under `<run-out>`;
corresponding hashes are
`2C95B87F09F2F9DCCDC45BDFBD45A9C0F7A490BC491AE4E08723D42071BBB31A`,
`DFB6826AED612F67467597931A914C1D22207D5E0DBA857D244F85AF6FBCA54B`,
and `17A23A0801A09E54CC154339724CD55B58711841C48B1CFA99B8C67FE0146491`.

The evidence design intentionally couples four independent engine surfaces:

- `UStateTreeComponent` supplies active Calm/Alert names.
- `USkeletalMeshComponent` supplies exact live linked-layer instances.
- evaluated Manny bones supply upper- and lower-body pose evidence.
- `UCharacterMovementComponent` supplies velocity, grounded mode, and ordinary
  movement while the fixture samples dense frame steps.

The admission fixture uses one third fact vector. The retained map uses
`SlowEarly` and `FastLate`, whose world-authored speeds, directions, and signal
times differ. All checkpoint deadlines are derived from each fixture's own
world-time Prepare epoch.

Static numeric margins are admissions, not certified values. Do not relax pose,
stride, speed, restoration, or timing gates without named telemetry from
repeated admission/reference/control runs.

Remaining certification work is deliberately narrow: run the newly committed
public slice through Git-HEAD refgate and retain its authoritative report.
