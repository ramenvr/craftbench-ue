# Guard Visible Aim authoring runbook

All commands run from the repository root. Never combine phases. Every output
package must be absent before its author command.

1. Build `ThirdPersonEditor Win64 Development` with `-WaitMutex
   -NoHotReloadFromIDE -NoUBA -MaxParallelActions=2`; stop on any error.
2. Run `author_admission_assets.py` in one fresh real-RHI
   `UnrealEditor-Cmd` process; stop and independently run
   `readback_assets.py --mode admission` in a second process.
3. Run `author_admission_map.py` in a third fresh real-RHI process; stop and
   independently load that exact map with the script argument embedded in the
   Python commandlet value using forward slashes:
   `-script=C:/.../readback_map.py --mode admission`. Do not append the mode
   after a standalone `--`; Unreal does not forward that shape to Python.
4. Run `run_admission.py --output <fresh-out> --ue-root <UE-root>` once. It
   uses `-nullrhi`, expected count one, the exact admission full test path, a
   720-second outer watchdog, and task-byte locks. Any FAIL/timeout stops work.
5. Repeat admission/reference and negative controls as required by MATRIX.
   Threshold changes require recorded evidence, never a guessed relaxation.
6. Only after admission authorization, run `author_final_assets.py`, then its
   independent final readback. It creates the retained locomotion-only empty
   baseline.
7. Run `author_final_map.py`, then its independent final-map readback. The map
   must contain two fixture/scenario groups and retain final asset bytes.
8. Run `close_reference.py --preflight-only --output <fresh-out>`, then its
   non-preflight form. It atomically parks the live one-file baseline, authors
   and cold-reads the complete graph, restores and cold-reads the original
   baseline byte-for-byte, and installs only `ABP_GuardVisibleAim.uasset` under
   `reference/Content/Tasks/...`.
9. Copy the fixed introspector through the shared owner seam, then run governed
   reference and empty production legs (L1/L2/L2I), owner-play, and the `cb discriminate` close.

After any retained-map harness repair, run the non-grading focused reference
probe before repeating an expensive governed production leg:
`py -3 -B authoring/run_final_reference_probe.py --output <fresh-out>
--ue-root <UE-root>`. It must report exact two Success results, two route
vectors (`projected=4 paths=2`), and restore the one-file live empty baseline
byte-for-byte even when the probe fails.

Author markers: `GUARD-AIM-ASSETS-SAVED`, `GUARD-AIM-MAP-SAVED`.
Cold markers: `GUARD-AIM-ASSET-READBACK-PASS`,
`GUARD-AIM-MAP-READBACK-PASS`. Runtime terminal marker:
`GUARD-VISIBLE-AIM-PASS`.
