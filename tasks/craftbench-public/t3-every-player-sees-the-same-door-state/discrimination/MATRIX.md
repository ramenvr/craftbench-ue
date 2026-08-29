# Discrimination matrix

Status: **CERTIFIED REFERENCE PASS / EMPTY BEHAVIOR FAIL**.

## Requirements table

| Requirement | Protected evidence | Shortcut rejected |
|---|---|---|
| Requester waits for authority | pre-server client state/revision/transform | local-first change |
| Initial peers converge | server revision plus every peer transform | client-owned or per-peer state |
| Late join converges | new process receives existing revision without toggle | multicast-only event |
| Other requester controls same state | second owner request and next shared revision | hardcoded client/door |

Policies swap requester, transforms, order, and join timing. Every peer report is
required; a missing client cannot be averaged away. Reference and empty must use
the same dedicated network runner.

Admission rounds 04-06 each produced one authoritative aggregate PASS with all
four gates, exactly four process return codes of zero, a single shared NetGUID,
late-join revision-one convergence, and final revision-two convergence. The
reference and empty production legs remained separate from these admission
controls. The committed-head reference passed L1, all 4 L2 gates, and all 3
L2I checks. The independent submitted baseline passed L1, failed L2 as behavior
at `REVISION_ONE_TIMEOUT`, and failed the RPC and RepNotify L2I checks; the
one-file boundary check still passed.
