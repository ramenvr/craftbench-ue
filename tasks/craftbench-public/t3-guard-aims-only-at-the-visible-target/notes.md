# Author notes - t3-guard-aims-only-at-the-visible-target

Status: **AUTHORED / 5 OF 5 ADMISSION PASS / GOVERNED REFERENCE PASS /
GOVERNED EMPTY FAILS AS PREDICTED / REFGATE PENDING**.

The first exact-one NullRHI attempt at
`<run-out>` was a genuine harness failure: PIE's
default Recast had zero active tiles before any graded gate. The task-local
author and fixture now serialize `RuntimeGeneration=Dynamic`, verify the
runtime capability, and call the public synchronous navigation build only when
PIE starts with zero tiles. The replacement admission map passed independent
cold readback with one scenario/fixture, two guards/targets/occluders/goals,
and exact dynamic Recast support (`145CB02F7E6AEA51218E60504268DE4799682965B466EBEBD83F400940891E4D`).

Fresh rounds 02 through 06 under
`<run-out>*` are 5/5 exact-one
Automation Success results with zero audit problems. Every round reported 60
runtime nav tiles and the same fail-closed sequence: visible target at cp0
(`alpha=1`, yaw `-33.85`, pitch `7.07`, revision 2), no target at cp1
(`alpha=0`, neutral aim, revision 4), and the same target reacquired at cp2
(`alpha=1`, yaw `-60.64`, pitch `10.97`, revision 5). Main and control guards
advanced identically to X `295.98`, `595.23`, and `908.73`; all five named
gates and the terminal marker passed. Package locks were unchanged in every
round.

The retained locomotion-only AnimBlueprint passed author and cold readback
(`C47B666A1B97E37875D01D09491971694008EB0FCB95E1CC653E5F595BA43F1C`).
The first governed reference leg at
`<run-out>` built both targets
successfully and passed L2I 2/2. `LeftHigh` passed L2, while `RightLow` ended
as a harness Error before grading because both path requests returned Failed.
The new cold route diagnostic proved the authored boundary exactly: the old
map had 60 active nav tiles but only 6/8 projected endpoints and 2/4 complete
paths because its floor/nav bounds ended at X=4750 while both RightLow goals
were at X=5900. The production report SHA-256 is
`2E5F922777DC6BF88171F48FF618E760D6589BDEC71ABCBB4F4F6D956C3168AA`;
the diagnostic log SHA-256 is
`34EA4A10820AEE76465A14E6D8FB0980249C41EE5EB8F1135E66A02131897594`.

The repaired retained map expands the physical floor and nav bounds and now
requires all endpoints to project plus complete synchronous paths during both
author and cold readback. A first focused probe then exposed a second honest
world-fact defect: the RightLow sight target origin was exactly on the floor,
so engine sight traced to an occluded endpoint. The target was moved to a low
above-floor position that still yields positive yaw and more than four degrees
of downward aim; no behavior threshold was changed. The final map now has 84
active tiles, 8/8 endpoints, and 4/4 paths and passed independent cold readback
(`BFE1A4EE65A0637DDBDA91CFAB4D4A24CE1DAA9938807466D70111B1D8CA924B`).
The focused reference probe at
`<run-out>` passed both exact final
fixtures, both 2400 cm route pairs, and all five named gates, then restored the
empty baseline and protected inputs byte-for-byte. Its probe manifest SHA-256
is `5C89D4ACA85A8335F4009A8597D626F1A6A6DAAFEDE4226434192C5C69137977`.

The atomic reference closure at
`<run-out>` authored and cold-read the
complete graph, restored and cold-read the baseline byte-for-byte, and
installed the single reference asset
(`0F01F7B2ED6AD46121CB86C00732025D8F5A069B0EFC2562D7AEDDFF2E3E7A15`).

The corrected governed reference run at
`<run-out>` used Git substrate
`b8010b798ad8aa0f836c5808567e1bbcb5913984` and passed all layers: L1 built
Editor and Game with NoUBA/cap 2, L2 passed both final fixtures, and L2I passed
2/2. Its report SHA-256 is
`0BD6C8D08A5BB42B9576926F1271C354EBB5C667A51233D9C7BFE2523DE4B23B`;
the L2 and L2I log SHA-256 values are
`2D12967D4620B0950EE84635A2A5A12998633756B401D40ADDFBB30DCD681533`
and `1F1609A35087D232A13540B86D6261A79A6A160F9DFC7375C49D64BA2589F2F5`.

The governed negative run at
`<run-out>` submitted the exact
retained locomotion-only baseline. L1 passed both targets, while L2 failed
both layouts at the intended
`GATE[PerceivedTargetDrivesAdditiveAimOverlay]` with
`harness_precondition=false`; L2I independently failed 0/2 because the graph
had no aim node or additive final route. Its report, L2, and L2I SHA-256 values
are respectively
`E9B41601C361F5C06C49275EAD644C71712F677E45D93F4C279776A2A45F764C`,
`666419B760D1389F6D3BD583DEE3F7618BE61A677BE287BC1E880A5F78F733A6`,
and `44E353D850B040538C0DF2AA923EDB4415AA82028D614262E8A285BC9680E65B`.
A literal zero-file submission was rejected earlier by the sandbox contract,
so it was not misreported as a behavior leg.

The package supplies a true sight listener, sight stimulus sources,
engine forgetting, controller path following, a native animation-state bridge,
one locomotion-only baseline graph, a complete isolated admission graph, two
world-varying final fixtures, an independent control twin, live bone telemetry,
and fixed two-check graph introspection. The reference and retained baseline
are authored, and the corrected retained map now has governed positive and
negative production evidence. Official refgate/certification and owner-play
remain.

The stock read-only assets are:

- `/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run`
- `/Game/Characters/Mannequins/Anims/Rifle/AIM/AO_Rifle`
- `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`

The latter Aim Offset already owns genuine additive Rifle pose samples, so the
task does not fabricate animation telemetry. Admission telemetry is stable
across five engine runs, and the governed positive/negative pair proves the
retained two-layout grader distinguishes the complete graph from its exact
locomotion-only baseline. Official refgate and owner-play remain before final
promotion.

The task-local and installed fixed introspectors are byte-identical (SHA-256
`D9C6B16EF652D62E91DF00244C52CBC81B28435F17FDE8F244036EF0C461030C`).
