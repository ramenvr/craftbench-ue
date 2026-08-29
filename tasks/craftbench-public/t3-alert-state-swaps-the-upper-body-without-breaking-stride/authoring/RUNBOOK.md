# Alert Stride authoring runbook

All commands run from the repository root. Never combine phases. Every author
output package and every log/output path must be absent before launch.

1. Build `ThirdPersonEditor Win64 Development` with `-WaitMutex
   -NoHotReloadFromIDE -NoUBA -MaxParallelActions=2`; stop on any error. Then
   build `ThirdPerson Win64 Development` with the same limits.
2. Run `author_admission_assets.py` once in a fresh real-RHI
   `UnrealEditor-Cmd` process. Require `ALERT-STRIDE-ASSETS-SAVED mode=admission
   packages=5 editable=4 complete=1`, then stop.
3. In a second fresh process run `readback_assets.py --mode admission` and
   require `ALERT-STRIDE-ASSET-READBACK-PASS mode=admission inventory=5
   editable=4`.
4. Run `author_admission_map.py` once with real RHI. Require
   `ALERT-STRIDE-MAP-SAVED mode=admission`, one group/subject/signal/fixture,
   exact protected hashes, then stop.
5. Independently load exact map package
   `/Game/__CraftBenchAdmission/t3-alert-state-swaps-the-upper-body-without-breaking-stride/L_AlertStrideAdmission`
   and execute `readback_map.py --mode admission`. Require the cold readback
   marker and exact cardinality.
6. Run `run_admission.py --output <fresh-short-output> --ue-root <UE-root>`
   once. It uses the exact full test path, `-nullrhi`, expected count one,
   a 720-second owned-child-tree watchdog, and asset/map/reference byte locks.
   Any failure or timeout stops work. Repeat only with explicit authorization.
7. After stable admission and threshold review, run
   `author_final_assets.py`; it creates one read-only interface contract under
   the map namespace plus four incomplete editable baseline assets. Require the
   marker, then cold
   read it with `readback_assets.py --mode final`.
8. Run `author_final_map.py`; require two distinct fact vectors and cold-read
   the exact retained map with `readback_map.py --mode final`.
9. Follow `REFERENCE_RECIPE.md` in a disposable substrate, harvest exactly four
   editable reference `.uasset` files, and prove the live baseline/interface
   stayed byte-identical.
10. Ask the shared-file owner to install the fixed introspector. Run governed
    reference and empty production legs (L1/L2/L2I), update MATRIX with actual
    paths/evidence, then owner-play and refgate.

## Current executed boundary

- Admission rounds 03-07: exact-one PASS five times with unchanged metrics.
- Final baseline/interface authoring and cold readback: PASS.
- Corrected retained final map author/cold readback: PASS, SHA-256
  `9EC800C1595BC4F843D31EFB26C02A4FE0A66F72DE8080A1B8DFCCE5CFF8EA2A`.
- Protected reference closure: PASS; exactly four editable assets harvested and
  the live baseline/interface restored byte-identically.
- First governed WIP production run: L1 PASS and L2I 4/4, but its old map labels
  yielded zero L2 tests. Preserve it as infrastructure evidence only.
- Corrected-map direct reference L2: authoritative 2/2 PASS.
- Corrected-map direct empty L2: authoritative 2/2 FAIL at the named linked-
  layer gate, with no harness precondition. Empty L2I is an overall FAIL at
  1/4, because montage-route avoidance is intentionally true in the baseline.
- Fresh governed live-substrate reference: L1 PASS, L2 2/2 PASS, L2I 4/4
  under `<run-out>`.
- Fresh governed supplied-empty: L1 PASS, L2 both fixtures failed the named
  linked-layer gate with no harness precondition, L2I 1/4 under
  `<run-out>`.

Do not publish from this boundary. After the batch commit tracks the corrected
map and reference, perform owner-play, tasklint/refgate on git HEAD, and the
final leak/cheat audit.

Exact author commands use the pinned project and fresh absolute logs, for
example:

```text
<UE-root>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe <ThirdPerson.uproject> -unattended -nopause -nosplash -stdout -FullStdOutLogOutput -run=pythonscript -script=<absolute-author-script> -abslog=<fresh-absolute-log>
```

Map authoring is real-RHI. Functional admission is `-nullrhi`. No author step
may overwrite an existing package.
