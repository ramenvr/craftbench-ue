# Shared-helper lease authoring runbook

Status: **GENUINE THIRDPERSON REFERENCE/EMPTY CERTIFIED**. The Editor/Game
scratch builds, admission map/readback, exact-one
admission, retained final map, and final-map cold readback are green. The next
heavy boundary is the batch-wide final refgate/owner-play audit.

## Fixed paths

- Project: `UE-projects/ThirdPerson/ThirdPerson.uproject`
- Live editable source:
  `Source/ThirdPerson/Tasks/t2-shared-helper-lives-until-the-last-lease-ends/`
- Admission map:
  `/Game/__CraftBenchAdmission/t2-shared-helper-lives-until-the-last-lease-ends/L_SharedHelperLeaseAdmission`
- Final map:
  `/Game/Maps/t2-shared-helper-lives-until-the-last-lease-ends/L_SharedHelperLeases`
- Fixture class: `ASharedHelperLeaseFunctionalTest`
- Admission display label: `SharedHelperLeaseAdmissionFunctionalTest`
- Fixed introspector: `t2_shared_helper_last_lease.py` (three checks)

No shared module or project dependency is needed. Before lint/L2I, the root
owner must install the reviewed task-local introspector candidate at
`tools/verify-single/introspect/t2_shared_helper_last_lease.py`. Do not perform
that shared edit from this lane.

## 0. Static boundary

From repository root, with no UE/UBT writer:

```powershell
py -3 tasks/craftbench-public/t2-shared-helper-lives-until-the-last-lease-ends/authoring/check_static_contract.py
py -3 -m unittest tasks/craftbench-public/t2-shared-helper-lives-until-the-last-lease-ends/authoring/test_run_admission.py
py -3 -m py_compile tasks/craftbench-public/t2-shared-helper-lives-until-the-last-lease-ends/authoring/*.py
git diff --check
py -3 tools/verify-single/tasklint.py tasks/craftbench-public/t2-shared-helper-lives-until-the-last-lease-ends/task.md
```

Until the owner installs the fixed introspector and a final map is authored,
tasklint is expected to report only those explicit missing governed artifacts.
Any C++/Python syntax, missing fixture source, metadata, named-gate, or prompt
leak error is not expected and must stop the lane.

## 1. First build boundary - authorized command only

Run exactly one Editor build, then stop regardless of result:

```powershell
& '<UE-root>\Engine\Build\BatchFiles\Build.bat' `
  ThirdPersonEditor Win64 Development `
  '-Project=<repo-root>\UE-projects\ThirdPerson\ThirdPerson.uproject' `
  -WaitMutex -NoHotReloadFromIDE -NoUBA -MaxParallelActions=2
```

Expected new compiled units:

- `SharedHelperLeaseSubsystem.cpp` in `ThirdPerson`;
- `SharedHelperLeaseFunctionalTest.cpp` in `CraftBenchTests`;
- `SharedHelperLeaseAuthoringLibrary.cpp` in `CraftBenchTests`.

UHT must accept all three generated headers. Stop at the first compile/link
error; do not launch Unreal with a stale DLL. This first build has **not** been
authorized or run by the static authoring lane.

## 2. Admission map author - one fresh process

Preflight requires admission and final map files absent, an exact two-file live
inventory, an exact cpp-only reference inventory, zero link/reparse points, and
a fresh absent log path. The live scaffold header is never reference-overlaid.
Then run only:

```powershell
& '<UE-root>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
  '<repo-root>\UE-projects\ThirdPerson\ThirdPerson.uproject' `
  -run=pythonscript `
  '-script=<repo-root>\tasks\cpp\t2-shared-helper-lives-until-the-last-lease-ends\authoring\author_admission_map.py' `
  -unattended -nopause -stdout -FullStdOutLogOutput `
  '-abslog=<run-out><UTC>.log'
```

Require one terminal marker:

```text
SHARED-HELPER-MAP-AUTHOR SAVED ... fixtures=1 tag=1 serialized_owners=0 runtime_contract=PASS
```

The script refuses overwrite and protects live source, reference source, and
final-map absence. If a partial `.umap` appears without the terminal marker,
stop; after writer count zero and exact hash/no-reparse checks, move only the
task's exact admission-map directory atomically to a new same-volume quarantine.

## 3. Fresh cold map readback

Use a new process and a new absent log path:

```powershell
& '<UE-root>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
  '<repo-root>\UE-projects\ThirdPerson\ThirdPerson.uproject' `
  -run=pythonscript `
  '-script=<repo-root>\tasks\cpp\t2-shared-helper-lives-until-the-last-lease-ends\authoring\admission_readback.py' `
  -unattended -nopause -stdout -FullStdOutLogOutput `
  '-abslog=<run-out><UTC>.log'
```

Require exact one package in the admission namespace, unchanged map/source
hashes, final map absent, and one
`SHARED-HELPER-MAP-READBACK PASS ... fixtures=1 tag=1 serialized_owners=0`.

## 4. Scratch reference admission - one phase at a time

Choose a short absent root. The live runtime remains empty and byte-locked.

```powershell
$shlRun = '<run-out><UTC>'
py -3 tasks/craftbench-public/t2-shared-helper-lives-until-the-last-lease-ends/authoring/run_admission.py `
  --phase prepare --output-root $shlRun

py -3 tasks/craftbench-public/t2-shared-helper-lives-until-the-last-lease-ends/authoring/run_admission.py `
  --phase build --output-root $shlRun --ue-root <UE-root>

py -3 tasks/craftbench-public/t2-shared-helper-lives-until-the-last-lease-ends/authoring/run_admission.py `
  --phase test --output-root $shlRun --ue-root <UE-root>
```

Stop after every command. `prepare` requires four locks (live source 2,
reference source 1, admission map 1), keeps the final map absent, copies through
the shared no-link substrate copier, and overlays exactly the reference cpp
inside scratch while retaining the copied live header. `build` uses Editor then
Game with `-WaitMutex`,
`-NoHotReloadFromIDE`, `-NoUBA`, and `-MaxParallelActions=2`. `test` uses shared
`run_l2`, NullRHI, 60 Hz, expected count one, 710-second inner timeout and
720-second owned-tree watchdog.

Require the authoritative exact full path:

```text
Project.Functional Tests.__CraftBenchAdmission.t2-shared-helper-lives-until-the-last-lease-ends.L_SharedHelperLeaseAdmission.SharedHelperLeaseAdmissionFunctionalTest
```

Require one Success, four `[CB-CP]` markers, terminal
`[CB-SHARED-LEASE] PASS checkpoints=4`, no SHL failure/HARNESS line, and all
four locks unchanged. A failed GC witness is an admission HOLD, not permission
to remove weak-invalidation gates.

## 5. Final map and production gates

Run `author_final_map.py` once with a fresh real/offscreen editor process, then
run `final_map_readback.py` in a second fresh NullRHI process. The author
refuses any existing final namespace and locks the admission map plus live and
reference source bytes. The readback requires exact one final map, exact one
fixture with display label `SharedHelperLeaseFunctionalTest`, the fixture tag,
zero serialized owner actors, the runtime contract, and byte-identical inputs.

Observed result: PASS. Final map SHA-256 is
`EA22E1F1B81B8002EE74ACF0518DA9DCBB1E70B23E049BC010A1F540AD1CF940`;
the fresh-readback log SHA-256 is
`8601CF13DAFBA994422F645CFC5355175E1ABB6947D8318D24AA93E5F0D8EDC8`.

Then run governed production legs independently:

1. reference: L1 both targets, exact L2 fixture, fixed L2I 3/3;
2. empty: L1 passes, L2 fails exact `SHL-0 runtime_contract_available`;
3. refgate and owner-play only after both matrix rows have authoritative
   reports.

The former CraftBenchTemplate production reports are archived prototype
evidence only and cannot certify this port. Run new git-head ThirdPerson
reference and supplied-empty rows after the substrate commit. The supplied
empty submission must contain the exact live empty `.cpp` because the sandbox
requires the accepted file to exist; a literally empty directory is an input
shape failure, not the intended behavioral negative.

Do not mark promotion-ready from admission. Update `notes.md` and `MATRIX.md`
only with observed evidence and immutable report/log hashes.
