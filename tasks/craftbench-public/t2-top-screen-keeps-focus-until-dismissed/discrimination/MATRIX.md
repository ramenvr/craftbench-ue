# Discrimination matrix - t2-top-screen-keeps-focus-until-dismissed

Owner policy for new tasks is **reference + empty only**. This table records
the required discrimination contract; the execution status immediately below
records which evidence has actually been obtained.

| Submission | Overall | Expected message / substring |
|---|---|---|
| `../reference` | **PASS** | all three L2I gates and all seven L2 gates pass through the final close sentinel |
| `empty` | **FAIL** | `root_and_screens_are_activatable` |

## Observed authoring and execution status

- Reference asset authoring and independent readback are clean. The final run
  emitted zero Widget GUID ensures and restored the live baseline byte-for-byte.
- The exact admission test is green in three independent rounds: each executed
  one test, passed one, failed zero, and produced the same focus vector.
- A formal short-workdir reference run with
  `CRAFTBENCH_L1_MAX_PARALLEL=2` passed both `ThirdPersonEditor` and
  `ThirdPerson` L1 targets. A task-local recovery controller then reused those
  pinned L1 binaries: governed reference L2 passed 1/1, and the corrected UE
  5.8 introspector passed all 3/3 L2I checks.
- The same controller overlaid the untouched baseline assets for the empty
  leg. Empty L2 failed 0/1 with the exact named token above, empty L2I failed
  the missing-stack and non-focusable-button checks, and the controller restored
  all three reference assets to their original SHA-256 hashes.
- These are complete supplemental reference/empty behavior results, not yet a
  single official `cb discriminate` or `cb refgate` certificate. Promotion
  still requires the official end-to-end gate after the map is tracked.

## Requirements table

| Prompt requirement | Coverage | Enforcing gate | Gate skipped when | What a submission could get away with |
|---|---|---|---|---|
| Opening root shows only Home and focuses its primary action | fully | `real_stack_declares_home_start`, `root_activation_focuses_home` | only verifier sentinel/local-player preflight failure | no direct child or unfocused Home |
| Open-details places exact Detail alone on top | fully | `push_makes_detail_the_only_active_top` | only immutable host drive failure | no visibility-only switcher or simultaneously active Home |
| Current policy selects the detail action | fully | `declared_focus_buttons_are_focusable`, `top_detail_owns_declared_focus`, `world_policy_changes_reactivated_focus` | only immutable policy mutation failure | no literal or construction-time cached choice |
| Buried Home cannot reclaim focus | fully | `buried_screen_cannot_reclaim_focus` | only verifier-owned active-request control fails | no repeated buried focus request that steals from top Detail |
| Dismiss restores the same Home and focus | fully | `dismiss_restores_home_focus` | only immutable host drive failure | no Home recreation or focusless pop |
| Closing releases activation and all menu focus | fully | `root_deactivation_releases_focus` | unconditional after generated root was created | no hide-only close or retained focused action |
| Preserve public lifecycle controls | fully | fixture resolves and invokes exact callable functions before every lifecycle leg | unconditional after root asset loads | signatures may contain extra helpers but cannot disappear |
| Work only in editable visual assets | partially at sandbox boundary | protected map/fixture paths reject; reference is asset-only | before grading | ThirdPerson source is substrate-writable globally, so an extra native helper could exist, but it still cannot replace the required saved structure and runtime behavior |
