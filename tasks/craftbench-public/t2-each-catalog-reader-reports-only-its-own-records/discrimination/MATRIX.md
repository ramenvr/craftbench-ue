# Discrimination matrix - t2-each-catalog-reader-reports-only-its-own-records

Status: **THIRDPERSON PORT AUTHORED / GIT-HEAD MATRIX PASS**. The genuine
ThirdPerson runtime and verifier compile, fresh nine-record asset authoring and
cold readback pass, admission-map author/cold readback pass, exact-one admission
passes CR-1/CR-2/CR-3, and the final map/fresh cold readback pass. The fixed
ThirdPerson L2I is 4/4 for the reference and rejects the supplied empty scaffold
on both load-bearing behavior checks. Historical CraftBenchTemplate results are
archived and do not count. At Git-head revision `8e09b103`, the independent
reference passed L1/L2/L2I and the supplied empty scaffold kept L1 green while
failing exact CR-1 without a harness marker.

| submission | expected overall verdict | expected named evidence |
|---|---|---|
| `../reference` | **PASS (executed, Git-head)** | L1 both targets with zero warnings, L2 1/1, L2I 4/4; all three named gates green through checkpoint 2 |
| supplied empty scaffold | **FAIL (executed, Git-head)** | L1 PASS with zero warnings; L2 exact `CR-1 exact_actor_scoped_metadata_reports`; no harness failure; behavior-bearing L2I checks fail |

## Requirements table

| Agent-visible requirement | Coverage | Assertion pointer | Skip condition | What a submission could otherwise get away with |
|---|---|---|---|---|
| Use each reader's live kind and folder | fully asserted | `CatalogReadersFunctionalTest.cpp:CheckExactReaderState` (`CR-1`) | unconditional | Reuse map defaults, actor names, one folder, or one global query. |
| Publish exact count and ascending package identities per reader | fully asserted | `CatalogReadersFunctionalTest.cpp:CheckExactReaderState` (`CR-1`) | unconditional | Emit a count only, an unsorted list, or the other reader's list. |
| Keep matching and decoy packages unloaded | fully asserted | `CatalogReadersFunctionalTest.cpp:OnProtectedAssetLoaded` + `CheckCatalogStayedUnloaded` (`CR-2`) | unconditional | Load objects, read fields, then unload/GC before the final sample. |
| Publish once per instance through the protected bridge | fully asserted | `CatalogReadersFunctionalTest.cpp:CheckOneBeginPlayReportPerReader` (`CR-3`) | unconditional | Populate public fields without publishing, publish another actor, or spam. |
| Publish during the first frame and no later duplicate through 1.2 s | fully asserted | protected bridge frame + checkpoint-2 cardinality (`CR-3`) | unconditional | Delay publication to a timer/Tick or emit again after initial success. |
| Do not hardcode catalog/world facts | behavior + fixed source gate | hidden pre-BeginPlay configs, CR-1 oracle, and `t2_catalog_reader_metadata_query.py` | unconditional | Embed protected names, enumerate files, load assets, or retain literal lookup tables. |

## Bounded-coverage note

The current owner rule requires reference plus empty only for new tasks. Both
canonical Git-head production legs are executed from separate fresh workdirs
through the standard runner. No hand-authored gaming variant is claimed.
