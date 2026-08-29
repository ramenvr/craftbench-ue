# Shared-owner handoff

This task does not require a shared Build.cs or `.uproject` change in the
current epoch2 substrate. Existing direct dependencies already cover the task:

- `ThirdPerson`: `Engine`, `StateTreeModule`, `GameplayStateTreeModule`.
- `CraftBenchTests`: the runtime modules above plus `StateTreeDeveloper`,
  `StateTreeEditorModule`, `AnimGraph`, `AnimGraphRuntime`, `BlueprintGraph`,
  `KismetCompiler`, and `UnrealEd`.

Before promotion, the shared-file owner must copy byte-for-byte:

`tasks/craftbench-public/t3-alert-state-swaps-the-upper-body-without-breaking-stride/authoring/t3_alert_stride_linked_layer.py`

to:

`tools/verify-single/introspect/t3_alert_stride_linked_layer.py`

and run the shared introspector wiring tests. The task author must not perform
that shared edit.
