# Authoring and verification runbook

This runbook is fail-closed. Each Unreal process performs one operation, writes a fresh absolute log, and stops. Do not chain authoring, readback, admission, reference harvest, or production verification.

## Frozen paths

- Project: `UE-projects/ThirdPerson/ThirdPerson.uproject`
- Admission assets: `/Game/__CraftBenchAdmission/t3-the-guard-resumes-patrol-after-the-chase/{BB_GuardPatrolChase_Admission,BT_GuardPatrolChase_Admission}`
- Admission map: `/Game/Maps/t3-the-guard-resumes-patrol-after-the-chase/L_GuardPatrolChaseAdmission`
- Final assets: `/Game/Tasks/t3-the-guard-resumes-patrol-after-the-chase/{BB_GuardPatrolChase,BT_GuardPatrolChase}`
- Final map: `/Game/Maps/t3-the-guard-resumes-patrol-after-the-chase/L_GuardPatrolChase`
- Reference destination: `tasks/craftbench-public/t3-the-guard-resumes-patrol-after-the-chase/reference/Content/Tasks/t3-the-guard-resumes-patrol-after-the-chase/`

## Static and build boundary

1. Parse every Python script with `ast.parse` and run task-local offline tests.
2. Run tasklint. Before binary authoring, missing map/reference errors are expected; source, fixture, and fixed introspector errors are not.
3. Root has merged direct CraftBenchTests editor dependencies `AIGraph` and `BehaviorTreeEditor` in the shared Build.cs; re-check that shared diff before the build.
4. Build only `ThirdPersonEditor Win64 Development -WaitMutex -NoHotReloadFromIDE -NoUBA -MaxParallelActions=2`, then stop.
5. After Editor success, build `ThirdPerson Win64 Development` separately to prove the runtime scaffold is Game-target safe.

## Admission sequence

Use a unique fresh output directory and `-abslog=<fresh>\\author.log` for every process.

1. `author_admission_assets.py`: require both exact admission outputs absent; create the Blackboard and editable tree graph; save; emit `ADMISSION-ASSETS-SAVED`; validate the same-process structural vector.
2. `readback_admission_assets.py`: fresh process; load exactly two packages; call the native independent inspector; require `ADMISSION-ASSETS-COLD-PASS`; verify package SHA-256 before/after unchanged.
3. `author_admission_map.py`: require the exact map absent; create a readable navigable yard containing exact one guard, controller relationship, alert source, moving target, two markers, admission fixture, and navigation bounds; save and emit `ADMISSION-MAP-SAVED`.
4. `readback_admission_map.py`: fresh process; load without running behavior; call the native map-contract inspector; require `ADMISSION-MAP-COLD-PASS`; lock both assets plus the map and any OFPA side packages before/after.
5. `run_admission.py --round 1`: exact filter, exact enumeration count one, real RHI, 720-second owned-process watchdog, JSON-authoritative Success. Stop after one round regardless of outcome.

Admission is not proof of final-map or reference correctness. Repeat two further clean rounds only after root reviews round one.

## Empty workspace scaffold

After admission has established that the helper itself is viable, run these as separate fresh processes:

1. `author_baseline_assets.py`: require the final task namespace absent, create exact two editable assets with the three supplied keys and an empty tree graph, emit `GUARD-BASELINE-ASSETS-SAVED`, and preserve admission/stock hashes.
2. `readback_baseline_assets.py`: fresh-process exact-inventory and native empty-graph readback, emit `GUARD-BASELINE-ASSETS-COLD-PASS`, and preserve both baseline hashes.

The baseline author refuses existing output. It does not author the final map or reference.

## Final and reference closure

These phases are complete:

1. Author the final map once, never by copying or renaming the admission map in place.
2. Author the correct graph into a quarantinable copy of the exact final baseline assets.
3. Cold-read the exact final packages and require fixed L2I 4/4.
4. Harvest the two correct packages to `reference/Content/Tasks/...` with hashes.
5. Restore the live task namespace byte-for-byte to the empty baseline and verify its original hashes.
6. Run production reference in a fresh short work/output root; require L1, L2, and L2I PASS.
7. Run production empty independently; require L1 PASS and the exact named L2/L2I failures in `discrimination/MATRIX.md`.
8. Run official refgate only after both production rows are reviewed.

Evidence:

- final map author/readback:
  `<run-out>/author.log` and
  `<run-out>/readback.log`;
- protected reference closure:
  `<run-out>/closure.json`;
- unified reference PASS:
  `<run-out>/report.json`;
- intended empty FAIL:
  `<run-out>/report.json`.

The remaining release boundary is tasklint/refgate from the public task path
after its source, map, reference, and fixed introspector are tracked together.

## Recovery

- Never delete or overwrite an unknown package.
- If a process produces partial output, move the whole task-local namespace atomically to a unique same-volume quarantine after recording hashes and reparse-point status.
- If a hash changes during readback or behavior verification, stop and retain the full log/report; do not retry.
- A verifier-owned support failure is infrastructure. A malformed or missing submission asset is a graded failure, not a skip.
