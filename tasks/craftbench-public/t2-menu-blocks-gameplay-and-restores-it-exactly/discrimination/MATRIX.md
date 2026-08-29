# Discrimination matrix - t2-menu-blocks-gameplay-and-restores-it-exactly

Owner policy for new tasks is reference plus empty only. Both production
discrimination legs have now run independently. Baseline/support assets and
the protected map have been authored and cold-read successfully.
Admission is GO after rounds 03, 04, and 05 each returned independent exact-one
`Success`. Reference closure 02 authored one reference package and independently
cold-read all four L2I gates, but this is not a production runtime verdict.

| Submission | Expected overall | Expected message / substring | Status |
|---|---|---|---|
| `../reference` | **PASS** | all four named runtime gates and all four L2I checks pass through the final sentinel | observed under governed D3D11 production run: L1 PASS, exact-one L2 PASS, L2I 4/4 |
| `empty` | **FAIL** | TopMenuConsumesItsOwnAction | observed independently: L1 PASS, exact-one named L2 FAIL, L2I 1/4, no harness failure |

## Requirements table

| Prompt requirement | Coverage | Enforcing gate | What an incorrect submission cannot get away with |
|---|---|---|---|
| Active top menu blocks the shared gameplay action | full; round 03 observed | `GameplayActionBlockedWhileMenuActive` | gameplay callback firing behind the menu |
| Top menu consumes its own real routed action | full; round 03 observed | `TopMenuConsumesItsOwnAction` | UIOnly mode, direct callback, or visual-only overlay |
| Current world assignment and priority are used | full; round 03 observed | L2I `activation_adds_only_current_world_context` plus both live legs | one hardcoded context or construction-time cached priority |
| Pop restores exact prior state | full; round 03 observed | `PopRestoresExactPriorContexts` | clearing everything, guessed defaults, or removing current policy instead of captured identity |
| Unrelated bindings remain untouched | full; round 03 observed | `UnrelatedContextRemainsUntouched` | losing hidden or stock contexts or changing priorities |
| Only editable menu asset changes | partial at sandbox boundary | protected map/support/config/fixture plus mandatory asset structure | extra writable native code cannot substitute for the exact saved screen and runtime action route |

## Evidence status

- Editor+Game baseline build, exact ten assets, map+71 OFPA side packages, and
  both fresh cold readbacks are observed green.
- Admission round 01 (`<run-out>`) enumerated the
  exact one test but ended in a startup-config `HARNESS-PRECONDITION`; it is not
  behavioral evidence. The standalone runner overlay omission is fixed.
- Admission round 02 (`<run-out>`) enumerated the
  exact one test and reached behavior, then failed
  `GATE[PopRestoresExactPriorContexts]` at the pre-menu gameplay probe with
  checkpoint vector `gameplay=0 unrelated=0`. The empty stack root had selected
  CommonUI's default `Menu` mode before any menu was pushed. No threshold or
  named gate changed in the task-local stack-root correction.
- Admission round 03 (`<run-out>`) rebuilt that
  correction, executed the exact one test, returned runner exit 0, and reported
  JSON state `Success` through the final sentinel with all four named gates.
  It was behavior green 1/3.
- Admission rounds 04 and 05 independently repeated exact-one `Success`, runner
  exit 0, the same terminal named-gate vector, byte-identical config restore,
  and unchanged map72/assets10/stock4 hashes. Admission is 3/3 green.
- Reference closure 01 stopped before save at an over-strict baseline guard:
  the frozen factory WBP contains disabled, unlinked `PreConstruct`,
  `Construct`, and `Tick` placeholders. Live baseline SHA remained `1c61d351...`
  and reference remained absent. No reference or empty verdict was produced.
- After the corrected guard rebuilt green, closure 02 at
  `<run-out>` completed author and fresh cold
  readback. L2I was 4/4; the one-file reference SHA-256 is
  `a85f80464522dba76e86828c61ef61042a398677318890710a0c8d3b21b06fc7`;
  live baseline was restored exactly to
  `1c61d351779608bb69df3880ac00371dfcb1b68c1c3745a3d852e04b57ee3fd0`;
  and map72/support9/stock4 manifests were unchanged.
- Production reference attempt 01 at
  `<run-out>` passed L1 and L2I 4/4,
  but real-RHI L2 hit D3D12 `CreateHeap` `E_OUTOFMEMORY` while opening the
  test world. It produced `tests=0/0` and authoritative `HARNESS-ERROR`, so it
  is not reference behavior evidence and does not open the empty leg.
- Governed D3D11 production reference at
  `X:\cb\authoring\menu-input-production-reference-out-03` passed L1,
  exact-one L2, and L2I 4/4. Report SHA-256:
  `D49415F7BBCF30D5F5BB61352E83B7E3F3A1F98B923407C2F43B2F5AFCDCECD1`.
- Independent empty baseline at
  `X:\cb\authoring\menu-input-production-empty-out-01` passed L1 and failed
  the exact-one L2 at `GATE[TopMenuConsumesItsOwnAction]:`; L2I was 1/4 and
  there was no harness failure. Report SHA-256:
  `91870118BF2F62104F1B7B2D31ED8E42F0B4B1B6186F100C774A4EEEDF2F04F3`.
- Official committed-state `cb refgate` is pending.
