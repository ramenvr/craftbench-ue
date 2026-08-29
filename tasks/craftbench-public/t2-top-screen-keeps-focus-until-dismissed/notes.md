# Authoring notes

Public placement: `tasks/craftbench-public/t2-top-screen-keeps-focus-until-dismissed/`.
The owner moved this asset-deliverable task out of the `bp` basket into the
open disclosure set on 2026-08-20; its UE task-id paths are unchanged.

## Shared substrate integration

The root integrator merged the shared Common UI substrate atoms once while
preserving the co-resident Epoch 2 work:

- `UE-projects/ThirdPerson/ThirdPerson.uproject` enables `CommonUI`.
  `CommonInput` is a runtime module inside that plugin, not a separate plugin.
- `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchTests.Build.cs`
  carries the verifier-only Common UI, Common Input, and Blueprint authoring
  dependencies.

`AMenuFocusPolicy` does not require a Common UI dependency in
`ThirdPerson.Build.cs`. The saved Widget Blueprints depend on the enabled
plugin through their generated classes. Unified incremental
`ThirdPersonEditor` builds, including `FocusStackAssetAuthoring.cpp`, have
compiled and linked successfully.

## Authored artifacts

The deterministic authoring helper and thin Python driver have now executed:

- The three baseline Widget Blueprints were created and independently read
  back. The reference authoring stage compiled and validated all three assets,
  harvested a candidate, atomically replaced the declared reference trio, and
  restored all live baseline files byte-for-byte.
- The clean reference run emitted zero Widget GUID ensures, zero Blueprint/K2
  errors or warnings, three harvest markers, six independent asset-readback
  markers, `FOCUS-AUTHOR-BASELINE-RESTORED`, and
  `FOCUS-AUTHOR-REFERENCE-DONE`.
- `L_FocusStack.umap` was authored at its declared package path with the
  policy, lifecycle host, final fixture, and admission fixture anchors. The
  authoring readback found all four exact placements and their constructor
  tags where applicable.

The live project intentionally retains the baseline-behavior assets. The
edited solution assets exist only under the task-local `reference/` overlay.

Current on-disk SHA-256 evidence is:

| Asset | Live baseline | Task-local reference |
|---|---|---|
| `WBP_DetailScreen` | `936801F0362797E3CC23E22FF58C29DA24CB3D16FFA1F519908C0EB18574E812` | `A83A445B9C088A637FD065D58820D3500B77922CBBB8DFF3BC8BA0D41310BD92` |
| `WBP_HomeScreen` | `D8A55C5FFE5F821466861126BAEC4D52FA82EF600E9D9305D32C862DCE715DD2` | `55ADA61246A8BD879E43DB429A12BC1E332D62E84BFEDC11BB1C9BFE8954632B` |
| `WBP_MenuRoot` | `7D670DCF05CFE716298C5AC2BD3062E7388830BFBE362F7E341B7155DCB94344` | `21AC55E5B2717B6D364AD08428EC735AC7119E3591E2C4F89AF73A1D0320D761` |

The map is 12,985 bytes with SHA-256
`4D3A46F9E11ABE6B6A0F0D039B769C4005798224AAA7A5F3757CD73535F308BC`.
Its side mirrors contain 69 external-actor packages and 2 external-object
packages. The map and all 71 side packages are currently untracked promotion
artifacts; tasklint correctly rejects that state until they are added by the
integrator.

`authoring/_baseline_backup/` is retained as historical authoring evidence and
is intentionally ignored task-locally. Its three bytesets are the empty
overlay used by the supplemental empty run; they are not asserted to equal the
later editor-resaved live baseline hashes above. No cleanup step should delete
or silently refresh that evidence.

## Admission evidence

The exact admission automation test ran three times through the real L2
runner. All three rounds reported exactly one executed test, one success, zero
failures, and the same eight-stage focus vector:

```text
sentinel
home-active
detail-primary
visible-direct-focus
active-refresh-focus
buried-request-rejected
home-restored
detail-alternate
```

At every stage the expected target owned focus and the unexpected target did
not. Evidence is retained under
`runs/authoring/t2-top-screen-keeps-focus-until-dismissed/admission/round-{1,2,3}/`.

Runtime visibility is graded through the real stack's exact active-widget
pointer, the top screen's live Slate visibility, and the buried screen's
inactive state. The verifier intentionally does not use
`BuriedWidget->IsVisible()` as a negative oracle: a switcher can stop arranging
a child while that child's own cached visibility remains Visible.

## Formal verification status

Formal short-workdir grading with
`CRAFTBENCH_L1_MAX_PARALLEL=2` reached authoritative L1 success for both
`ThirdPersonEditor` and `ThirdPerson`. The retained cfr3 L1 log contains
`Result: Succeeded` for both targets and both UBT commands contain
`-MaxParallelActions=2`.

The original formal reference leg froze during early PreRHI/NullRHI startup
while unrelated UE/UBT work was active. A task-local recovery controller then
reused the pinned green L1 binaries without weakening the ordinary 8 GB L2
resource governor. Reference L2 passed its exact test 1/1. After replacing an
unavailable UE 5.8 Python enumeration call with exact WidgetTree-name
resolution, reference L2I passed all 3/3 fixed checks.

The recovery controller also ran the real empty overlay. Empty L2 executed one
test and failed it at
`GATE[root_and_screens_are_activatable]: `; empty L2I failed the missing-stack
and non-focusable-button checks. Its `finally` path restored the three staged
reference assets byte-for-byte, with all final SHA-256 values matching the
pre-run reference values. Evidence is retained at
`<run-out>`,
`<run-out>`, and
`<run-out>`.

This is complete supplemental L2/L2I discrimination evidence. It is not a
replacement for the official single-run `cb discriminate`/`cb refgate`
certificate required before promotion, because L1 was reused rather than rerun
inside the recovery controller.

Official `cb discriminate` and `cb refgate` remain pending. No promotion claim
should describe the task as certified until the Git-tracked map/mirrors are
present in the clean checkout and the official reference/empty gate completes.

## Exact recovery plan

Wait until unrelated Unreal Editor and UnrealBuildTool processes have exited.
Use fresh, short paths that do not already exist, then run the official
reference leg with the low-parallelism cap:

```powershell
$env:CRAFTBENCH_L1_MAX_PARALLEL = '2'
py -3 tools\verify-single\run_task.py `
  --task tasks\craftbench-public\t2-top-screen-keeps-focus-until-dismissed\task.md `
  --submission tasks\craftbench-public\t2-top-screen-keeps-focus-until-dismissed\reference `
  --ue-root <UE-root> `
  --report-json <run-out><stamp>\report.json `
  --workdir <run-out><stamp> `
  --out-dir <run-out><stamp> `
  --substrate-from-live
Remove-Item Env:CRAFTBENCH_L1_MAX_PARALLEL
```

Only after that report is a full L1/L2/L2I PASS, create a new empty submission
directory and run the same official command with fresh `focus_empty_<stamp>`
work/out paths. The supplemental run has already observed the required empty
failure token `GATE[root_and_screens_are_activatable]`; the official leg must
reproduce it.

If a clean-host reference run freezes at the same PreRHI boundary, repeat once
with fresh paths and `--no-govern-resources` solely as an infrastructure
diagnostic. Do not record that diagnostic as the final discrimination matrix;
the final evidence should come from the ordinary governed command above.
