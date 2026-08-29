# Discrimination matrix

Status: **LIVE-SUBSTRATE REFERENCE/EMPTY DISCRIMINATION PASS - CERTIFICATION
HOLD**.

| Variant | L1 | L2 expected | Required named failure |
|---|---:|---:|---|
| Reference loader | PASS | 2/2 PASS | observed 2/2 in `district-production-reference-l2only-out-01` |
| Empty loader | PASS | 0/2 | observed both fail `ExactActorsEnterViaNamedSection` in `district-production-empty-out-01` |
| Spawn lookalikes | PASS | 0/2 | `ExactActorsEnterViaNamedSection` |
| Hide instead of unload | PASS | 0/2 | `ExactActorsLeaveAfterUnload` |
| Load every district | PASS | 0/2 | `UnrelatedSectionsUnchanged` |
| Reuse stale actors | PASS | 0/2 | `ReloadCreatesFreshSectionActors` |

## Requirements table

| Req | Prompt requirement | Asserted | Runtime pointer | Skipped when | Residual |
|---|---|---|---|---|---|
| R1 | Load the world section supplied by the request | fully | `ExactActorsEnterViaNamedSection` | never | none; package, stream, level owner, and marker are conjoined |
| R2 | Make the requested section visible | fully | `ExactActorsEnterViaNamedSection` | never | none; loaded but invisible is rejected |
| R3 | Unload that same section | fully | `ExactActorsLeaveAfterUnload` | never | none; hidden or persistent actors remain observable |
| R4 | Load it again successfully | fully | `ReloadCreatesFreshSectionActors` | never | none; old and new object identities must differ |
| R5 | Preserve the unrelated district | fully | `UnrelatedSectionsUnchanged` | never | none; stream and actor identities are pinned |
| R6 | Do not hardcode one section | fully | Alpha and Beta fixture pair | never | a conditional keyed to hidden actor identity still faces changed soft paths and IDs |
| R7 | Use real streaming rather than replacements | fully | `ExactActorsEnterViaNamedSection` | never | persistent-level or spawned lookalikes fail ownership |

The protected loader, two section maps, and admission host have independent cold
readback evidence. Three fresh native-control rounds each passed both Alpha and
Beta fixtures with 14 unique world-clock samples and unchanged input hashes.
The protected-reference closure ran, passed fixed graph L2I 5/5, harvested the
one-file reference, and restored the exact baseline bytes. The corrected final
map passed fresh cold readback. Reference L1 plus governed L2 2/2 are green;
independent empty L1 is green and L2 is the required 0/2 named failure. These
are live-substrate reports, so git-HEAD refgate and owner-play remain mandatory.
