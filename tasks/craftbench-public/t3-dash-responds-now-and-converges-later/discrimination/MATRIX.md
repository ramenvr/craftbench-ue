# Discrimination matrix

Status: **NETWORK ADMISSION PASS 3/3 / PRODUCTION REFERENCE-EMPTY DISCRIMINATION PASS**.

## Requirements table

| Requirement | Role-qualified evidence | Shortcut rejected |
|---|---|---|
| Immediate owner response | autonomous movement before server ack | server-only movement |
| Owner/server converge | correction and retained error window | client-only movement |
| Simulated proxy sees one dash | remote sequence/displacement count | owner cosmetic only or multicast duplicates |
| Accepted cost once | one server accounting revision/delta | client+server double spend |
| Rejected rollback/no cost | correction to server state and zero revisions | always accept or spend-before-validation |

Both fixture policies include accepted and rejected attempts. Packet conditions,
direction, and energy vary. Missing peer/correction/telemetry is a harness error,
never a denominator reduction.

## Retained admission evidence

| Round | Policies | Processes | Result |
|---|---:|---:|---|
| `dash-admission-06` | A + B | 6 | 5/5 PASS, inputs unchanged |
| `dash-admission-07` | A + B | 6 | 5/5 PASS, inputs unchanged |
| `dash-admission-08` | A + B | 6 | 5/5 PASS, inputs unchanged |

Policy A uses accept-first, energy 137, cost 31, cooldown 7, lag 115 ms,
loss 1%. Policy B reverses request order and uses energy 181, cost 43,
cooldown 11, lag 165 ms, loss 2%. Both require one immediate owner prediction,
one accepted authority resolution, one simulated observation, exact convergence,
and a rejected rollback with the order-appropriate unchanged accounting state.

## Committed-head production discrimination

| Submission | L1 | L2 | L2I | Classification |
|---|---:|---:|---:|---|
| Reference, commit `fe1fce76` | PASS | 2/2 scenarios, 5/5 gates PASS | 4/4 PASS | accepted |
| Byte-identical live baseline | PASS | 0/2, protected behavior FAIL in A and B | 1/4 PASS | rejected |

Reference evidence is retained at `<run-out>`; report SHA-256
is `0A201665E3F5EA9AE7135F19E0A69CC293CE822F655A352A76AAD680D26F4926`.
Baseline evidence is retained at `<run-out>`; report SHA-256
is `8525F8BEEDB93218F13EF3D34A165150C7E859F56D014686437ED9F13B17C8F4`.
The baseline scenarios both ended with `FIRST_REQUEST_TIMEOUT`, `timed_out=false`,
no harness marker, and unchanged inputs. This is the intended behavioral
discrimination, not an infrastructure failure. Committed-head refgate remains
the next publication gate.
