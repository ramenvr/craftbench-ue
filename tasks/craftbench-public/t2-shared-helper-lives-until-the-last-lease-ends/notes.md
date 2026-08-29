# Authoring notes - t2-shared-helper-lives-until-the-last-lease-ends

## Current status

Status: **THIRDPERSON REFERENCE/EMPTY CERTIFIED / PUBLICATION READY**. The
required ThirdPerson runtime and verifier compiled in the live
project, then the cpp-only reference was overlaid only into a disposable
ThirdPerson scratch project. Both isolated Editor and Game targets passed with
NoUBA/cap2 and path-isolation checks, and the exact-one live test passed all
five GC behaviors. The live empty scaffold, canonical reference, admission
map, and retained final map remained byte-stable across governed steps.

The first test wrapper attempt reached authoritative Automation Success but
failed after the run while serializing a `WindowsPath` in the L2 dataclass. Its
five-file evidence directory was atomically preserved at
`<run-out>`. The task-local JSON
writer now serializes path-like values with `default=str`, has a regression
test, and the fresh governed retry passed. This was runner infrastructure, not
a behavior retry or threshold change.

Current ThirdPerson admission evidence root:
`<run-out>`. The exact test path is
`Project.Functional Tests.__CraftBenchAdmission.t2-shared-helper-lives-until-the-last-lease-ends.L_SharedHelperLeaseAdmission.SharedHelperLeaseAdmissionFunctionalTest`.
The report is 1/1 Success with zero warnings/errors and the log contains all
four checkpoints plus `[CB-SHARED-LEASE] PASS checkpoints=4`. Evidence hashes:
L2 log `BDD24C02FA46AE79FDC00D47ED9BEADB922283C6063436EDFBB200B3255C5F3E`,
report `93129DD9A5F7F038A8B27195A9F94927D70D882D25D5CAD04612E75C359A146A`,
L2 result `22E68CDD34BFCBDCCA11B86888AF033E836E5DFFBB44A5F162D9DFFE4C5E6CD2`,
and audit `3449AF8678A39FD591DA93209F5B8F348A002ECC0FE78FB92F9E1A3158E1BBE7`.
The admission map is 31,399 bytes, SHA-256
`11BAC6FAB7BE11115CEE6C9D416996D4E52B1EDE8B5BD5490B289C094C227330`.

The fixed introspector is installed byte-for-byte at the governed path. The
final map is authored and independently cold-read, and fresh live-substrate
reference/empty L1/L2/L2I rows discriminate exactly as designed.

Final map authoring evidence is retained at
`<run-out>/`; the exact map has SHA-256
`EA22E1F1B81B8002EE74ACF0518DA9DCBB1E70B23E049BC010A1F540AD1CF940`.
Fresh readback at
`<run-out>/` proved exact fixture
class/label/tag, zero serialized owners, the fixed runtime contract, and
unchanged admission/source hashes. Its log SHA-256 is
`8601CF13DAFBA994422F645CFC5355175E1ABB6947D8318D24AA93E5F0D8EDC8`.

Git-head production reference report
`<run-out>/report.json` is overall
PASS with warning-free Editor+Game L1, exact-one L2 PASS, and L2I 3/3;
SHA-256 `AC432E204FF5976B8BA06091E2472106509B8D2320E8A65A37ADD42838850CBB`.
Supplied-empty report
`<run-out>/report.json` is the expected
overall FAIL with warning-free L1, exact one
`SHL-0 runtime_contract_available`, no `HARNESS` marker, and L2I 3/3; SHA-256
`C71DAE9FA690C596DD2DB54D850DF5F0CD9DF68518A36D347153CB5285A5C00E`.
Both reports pin substrate revision `ad98f50c6534`.

The following reports are historical CraftBenchTemplate prototype evidence
only; they are preserved for audit but do not certify this ThirdPerson task.
The independent prototype reference root
`<run-out>/` passed L1 Editor+Game, exact-one L2
and L2I 3/3. Report SHA-256 is
`2059EAAB8C24A6C2114AFDADE0BBE2DFF31569C64C97FE8F33E905A818700D62`.
The corrected empty-behavior root
`<run-out>/` passed L1, failed exact-one L2 at
`SHL-0 runtime_contract_available` with no harness precondition, and passed
the intentional supplied-surface L2I 3/3. Report SHA-256 is
`F20FF7B242539D0789CDA7DE718AEC8DE37ADEA44AFA783652BED9A3FAB66EFA`.
The earlier `...empty-out-01` stopped at sandbox input shape before L1/UE
because the required supplied `.cpp` was absent; it is retained as
infrastructure evidence and is not a behavior row.

## Source provenance

- Dossier: an internal design note (not shipped).
- Capability bucket: Architecture & Systems; set `craftbench-public`; tier T2.
- Coupled concepts: `programming-subsystems`, `ps-garbage-collection`, and
  `ps-uproperties` from `tools/coverage/concepts.csv`.
- Retained hardening: multi-owner same-version sharing, an independent key,
  overlapping retired/current versions, exact payloads, and real weak
  invalidation after fixture-only forced GC.

## UE5.8 API audit

| API / type | Local source | Contract used |
|---|---|---|
| `UGameInstanceSubsystem` | `Engine/Source/Runtime/Engine/Public/Subsystems/GameInstanceSubsystem.h` | automatically instantiated subsystem scoped to one game instance |
| `UGameInstance::GetSubsystem<T>()` | `Engine/Source/Runtime/Engine/Classes/Engine/GameInstance.h:440` | obtains the submitted live subsystem in PIE |
| `UEngine::ForceGarbageCollection(bool)` | `Engine/Source/Runtime/Engine/Classes/Engine/Engine.h:2828` | public request for collection at the next engine opportunity; `true` requests full purge |
| `FGuid::NewGuid()` | `Engine/Source/Runtime/Core/Public/Misc/Guid.h:366` | fresh per-world keys, versions, and payloads |
| `FObjectPropertyBase`, `FWeakObjectProperty`, `FArrayProperty`, `FStructProperty` | `CoreUObject/Public/UObject/UnrealType.h` | verifier-only readback of exact reflected ownership topology |
| `TWeakObjectPtr::IsValid()` | `CoreUObject/Public/UObject/WeakObjectPtrTemplates.h` | independent live/invalid identity observation without retaining the helper |

No plugin or new module is required. `Core`, `CoreUObject`, `Engine`, and
`FunctionalTesting` are already direct dependencies of the applicable modules.

## Load-bearing decisions

1. The helper is an ordinary transient UObject. The reference uses
   `GetTransientPackage()` as Outer so its lifetime is explained only by
   reflected cache/lease edges, never by a task-owned outer graph.
2. The fixture never owns a helper strongly. It owns only lease tokens and
   stores all helper identities in `TWeakObjectPtr`.
3. GC is fixture-only and scheduled, never an agent API requirement. The
   fixture requests `ForceGarbageCollection(true)` and waits across normal PIE
   frames before sampling.
4. Every forced collection has a verifier-only unrooted witness. If the witness
   survives, lifetime assertions do not run and the fixture reports `HARNESS`.
5. Old and new versions overlap. A replacement that rewrites one singleton or
   clears all entries on any release is observable without inspecting a
   submitted counter.
6. Admission uses the exact reference source only as a scratch overlay. The
   verifier fixture is identical to production; it never contains a fallback
   cache or alternate implementation.

## First-wave artifact checklist

- [x] Canonical v2 task specification.
- [x] Empty supplied subsystem/cache/lease scaffold.
- [x] Minimal reference source overlay.
- [x] World-clock fixture with real GC and weak invalidation.
- [x] Fixed reflected runtime/world readback helper.
- [x] Reference/empty discrimination matrix and requirements table.
- [x] Admission map author/readback scripts and fail-closed runner.
- [x] Task-local fixed-introspector candidate and shared patch request.
- [x] Root-owned introspector installation under `tools/verify-single/introspect/`.
- [x] Genuine ThirdPerson live Editor build.
- [x] Admission map author and fresh cold readback.
- [x] Scratch reference two-target build and exact-one admission.
- [x] Final map author/readback.
- [x] Git-head ThirdPerson reference/empty L1+L2+L2I discrimination.
- [x] Tracking/commit and public placement.
- [ ] Batch-wide final refgate/owner-play audit.

## Calibration boundary

No numerical promotion threshold is inferred from a single admission run. The only schedule is
four checkpoints at `epoch + 0.15/0.45/0.75/1.05` world seconds, leaving at
least 0.30 world seconds between a GC request and its observation. Admission
proved sufficient for UE5.8 to collect the independent witness on the governed
60 Hz NullRHI path. The five named behavior gates were not weakened.

## First build boundary

The build, admission, final-map cold readback, and git-head reference/empty
matrix are complete. The remaining boundary is the batch-wide final refgate
and owner-play audit. See `authoring/AUTHORING_RUNBOOK.md` for retained evidence.
