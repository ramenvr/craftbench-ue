---
id: t2-each-catalog-reader-reports-only-its-own-records
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Content Integration
category: other
layers: [L1, L2, L2I]
fixtures: ["L_CatalogReaders :: ACatalogReadersFunctionalTest"]
introspect: [t2_catalog_reader_metadata_query.py]
deadline_s: 900
action_budget: 40
accepted_files: [Source/ThirdPerson/Tasks/t2-each-catalog-reader-reports-only-its-own-records/CatalogReaderActor.h, Source/ThirdPerson/Tasks/t2-each-catalog-reader-reports-only-its-own-records/CatalogReaderActor.cpp]
---

# t2-each-catalog-reader-reports-only-its-own-records

Two independently configured world readers must derive exact content metadata
without resolving content objects. The paired type/folder queries, protected
inside/outside decoys, actor-scoped output, and residency history make a fixed
count, a global cache, or load-and-inspect implementation observably wrong.

## Primary concept

- `ps-asset-registry` - Asset Registry
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/asset-registry-in-unreal-engine)

The load-bearing behavior is a class-and-path metadata query that returns stable
package identities while every examined package remains unloaded.

### Composed concepts

| Concept | Epic documentation | Role in the composition |
|---|---|---|
| `ps-asset-registry` | https://dev.epicgames.com/documentation/en-us/unreal-engine/asset-registry-in-unreal-engine | Supplies the on-disk metadata query and stable package identities without object resolution. |
| `ps-data-assets` | https://dev.epicgames.com/documentation/en-us/unreal-engine/data-assets-in-unreal-engine | Supplies two distinct authored record kinds plus same-type and wrong-type decoys. |
| `ps-actors` | https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine | Carries two independent world configurations and actor-scoped BeginPlay results. |

### Production-pattern justification

Epic's public Asset Registry guide documents using cached asset metadata to
search project content without loading the assets. That is the production
boundary used by content browsers, validation tools, and runtime discovery
systems: a caller filters stable metadata, then decides separately whether any
selected object should become resident. This task exercises that boundary from
two independently configured world consumers rather than rewarding one fixed
project-wide count.

### Concept-interaction notes

Each placed actor owns its current record-kind and folder facts. Those facts
must flow into a metadata query, and the resulting package identities must flow
back into that same actor's public state and protected publication. The two instances
therefore expose accidental static/global query state.

The catalog contains matching records, a wrong-kind record inside each queried
folder, and records of the requested kinds outside those folders. Exact package
identity equality makes both filter dimensions observable. A verifier-owned
load event listener plus repeated package-residency reads separately proves the
query did not resolve the objects it enumerated.

## Prompt given to the agent

> The level contains two catalog readers. Before play, the world gives each
> reader its own public identity, record kind, and content folder. When play
> begins, each reader must inspect authored content metadata for exactly its
> configured kind beneath exactly its configured folder, without opening or
> loading any matching or decoy record. It must expose the exact matching count
> and the matching package identities in ascending lexical order on that same
> reader. After setting that public result, each reader must call the supplied
> `FCatalogReaderReportBridge::Publish(this)` exactly once during the first
> frame of play. The two readers have distinct
> configurations and results; one reader must never publish or reuse the
> other's state. No additional protected publication may occur during the first
> 1.2 seconds. Work only in the supplied editable reader code. Do not edit the
> level, record types, records, build files, or tests, and do not embed any
> record package, count, reader identity, kind, or folder in code.

## Workspace state pre-task

The deliverable root is
`Source/ThirdPerson/Tasks/t2-each-catalog-reader-reports-only-its-own-records/`.

Files/assets that **exist**:

- `Source/ThirdPerson/Tasks/t2-each-catalog-reader-reports-only-its-own-records/CatalogReaderActor.h`
  and `.cpp` - the supplied editable reader. It exposes `ReaderId`,
  `ConfiguredAssetClass`, `ConfiguredPackagePath`, `ReportedCount`,
  `ReportedPackageNames`. Its constructor owns a
  transform root and the common `CatalogReader` tag. It has no BeginPlay query
  or report behavior.
- `CatalogRecordTypes.h` / `.cpp` in the same task source folder - supplied
  support declarations for two record kinds and the protected
  `FCatalogReaderReportBridge`. They are not the requested edit.
- Protected catalog packages beneath
  `Content/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/`.
  Their exact package names, classes, counts, and placement among matching and
  decoy folders are verifier facts and are not disclosed here.
- `Content/Maps/t2-each-catalog-reader-reports-only-its-own-records/L_CatalogReaders.umap`
  contains exactly two placed reader instances tagged `CatalogReader.A` and
  `CatalogReader.B`, plus the functional test. Serialized settings are decoys:
  the fixture writes two distinct live configurations after actors initialize
  and before their BeginPlay callbacks.
- The runtime and verifier modules have a direct `AssetRegistry` dependency.

Files/assets that **do not exist**: any reader query, result sorting, result
publication, or BeginPlay report implementation. The protected catalog, map,
support record declarations, build files, and verifier source are not part of
the submission.

The load-bearing world facts are the live `ReaderId`, `ConfiguredAssetClass`,
and `ConfiguredPackagePath` values on each placed reader. Reading constructor
defaults, serialized map decoys, actor names, or one global query cannot satisfy
both readers.

## Verifier specification

Layer choice is **L1 + L2 + L2I**. L1 builds both targets. L2 uses a protected
publication callback and PIE state probes with a verifier-owned Asset Registry
oracle. Candidate-authored log text is never captured or parsed. The fixture
never resolves a protected record object and never ticks the world manually.

### L1 - build

```text
assert: UnrealBuildTool exits 0 for ThirdPersonEditor Win64 Development
assert: UnrealBuildTool exits 0 for ThirdPerson Win64 Development
```

### L2 - two actor-scoped metadata queries

Before placed actors receive BeginPlay, the fixture:

1. resolves exactly one actor for each specific reader tag;
2. scans only protected catalog metadata, then proves the exact nine protected
   packages, expected classes, wrong-type-inside decoys, same-type-outside
   decoys, and zero initial package residency;
3. overwrites both serialized decoys with distinct live reader identities,
   classes, and folders;
4. installs the protected publication listener and an asset-load event listener.

At world-time checkpoints `0.20`, `0.80`, and `1.20` seconds:

```text
for each reader:
    require ReportedCount == independently enumerated matching count
    require ReportedPackageNames == exact ascending matching package names
named failure: CR-1 exact_actor_scoped_metadata_reports

for every matching and decoy package:
    require no asset-load event was observed
    require FindPackage(package) remains null at every checkpoint
named failure: CR-2 all_examined_packages_remain_unloaded

at the final checkpoint:
    require exactly two protected publications total
    require each publication source is the expected placed reader
    require the bridge-time snapshot equals the independent oracle
    require each publication arrived within frame delta 0..1 from world actor init
named failure: CR-3 one_beginplay_report_per_instance
```

### L2I - fixed four-check source contract

The verifier-owned read-only script always emits exactly four checks:

1. the staged submission surface is exactly the supplied header/source pair;
2. an `FARFilter` consumes both live actor configuration dimensions and is
   passed to `IAssetRegistry::GetAssets`;
3. object loads, filesystem enumeration, protected package literals, and
   fixture-owned identities are absent; and
4. package identities are sorted into public state before the protected bridge
   publication.

These source gates do not trust candidate log strings and cannot shrink their
denominator when a file is missing or malformed.

Protected catalog corruption or a missing pre-BeginPlay listener is a named
verifier `Error`. Submission-reachable reader/tag/state failures are graded
`Failed`, never converted into a skip or no-verdict escape.

## Reference solution metadata

- LOC range: 55-95 C++ LOC across the supplied header/source pair.
- Files touched: 2; no map, asset, record-type, build, config, or verifier edits.
- Senior-dev hours: 2-4 hours including exact filtering, stable sorting,
  actor-scoped reporting, and residency-safe validation.

## Anti-gaming notes

1. **Hardcoded package list or count.** The fixture replaces map decoys with two
   distinct hidden class/folder configurations and compares exact independently
   enumerated package identities; `CR-1` rejects literals and partial filters.
2. **Global/shared result.** Both placed actors report in the same BeginPlay
   frame with different results; actor-local arrays plus exact per-reader protected publications
   make a static cache or last-writer-wins state fail `CR-1`/`CR-3`.
3. **Loading records to inspect them.** A pre-BeginPlay asset-load delegate
   records any protected object resolution even if later garbage collection
   removes the package, while repeated `FindPackage` reads catch surviving
   residency; either route fails `CR-2`.
4. **Folder-only or type-only query.** Wrong-type assets inside both folders and
   same-type assets outside both folders are part of the protected exact oracle;
   either incomplete filter changes the package set and fails `CR-1`.
5. **Repeated or delayed reporting.** The protected bridge counts exact source
   actors, snapshots public results independently, requires one per reader and
   two total, and pins the first-frame delta. Log spam cannot affect this gate;
   Tick publication or a deferred publication fails `CR-3`.

## Hidden invariants

- Identity is resolved by specific actor tag and cardinality before casting to
  the supplied public contract; subclasses remain valid.
- The map stores decoy values. The live configurations are fixture-owned world
  state written before BeginPlay, so constructor/map caching cannot pass.
- The fixture scans metadata only and pins all nine protected package/class
  facts. It never calls `FAssetData::GetAsset`, `LoadObject`, or `LoadPackage`.
- Residency is historical as well as sampled: `OnAssetLoaded` catches a
  load-then-GC shortcut, while `FindPackage` catches retained packages.
- The exact public arrays are checked at every checkpoint, and the publication
  snapshots are compared with verifier-owned facts. Candidate log text is ignored.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
