# The Harness Tour

A guided reading of the CraftBench harness, end to end. This page is the **front
door** — it frames the whole system and tells you which section file to open for
each step. The sections carry the detail; this page does not duplicate them.

> **⚠ Dated snapshot:** the tour predates three retirements — the hash manifest /
> exit-3 gate (now git-HEAD provenance + human review on commit), the map
> scaffolders (committed `.umap` binaries are the only map source), and the
> `gp-gas-launch` / `umg-image-brush-bound` tasks. Where a section contradicts
> the code, the code wins; for the current command surface read
> [`../CHEATSHEET.md`](../CHEATSHEET.md) and [`../../EVALS.md`](../../EVALS.md).

---

## What the harness is

CraftBench evaluates AI coding agents on Unreal Engine 5.8 gameplay-programming
tasks. The cleanest way to hold the whole thing in your head is a **contest**:

- **the contestant** — a coding agent is handed a *behavior-only* prompt and a
  private copy of the UE project, and edits source to produce the asked-for
  behavior. The backends: the `claude-p` Baseline (and `openrouter:` — any
  non-Anthropic model on the same generalist baseline, no Aura needed), `aura-mcp`,
  and `unreal-mcp`. A private-product browser-drive path existed internally and is NOT
  part of this public release; a legacy local-HTTP agent path is **deprecated**;
- **the arena** — that UE project, the **substrate** (`CraftBenchTemplate`): a
  base actor declares the *shape* the judge will look for but ships the behavior
  deliberately absent, so producing it is the agent's whole job;
- **the judge** — a **deterministic verifier** builds the project, drives it in a
  real PIE world, and inspects the runtime trace and the generated assets against
  the task's behavior spec. This judge, and *only* this judge, decides PASS/FAIL;
- **the scoreboard** — many `(product × task)` verdicts roll up into a per-capability
  grid and head-to-head table that answers the headline question: *which product
  is strong at what?*

The load-bearing design choice is that **the deterministic gate is the eval**
(spec FR-020d). No LLM-as-judge, no pixel comparison, nothing fuzzy ever flips a
verdict. There *are* advisory layers — an LLM rubric judge (R2) and a render-quality
track — but they are firewalled annotations that decorate a verdict; they are
structurally incapable of moving it. When you read the tour, keep that line bright:
the gate certifies, everything else annotates.

---

## End-to-end data flow

Read this as the life of one attempt, from task spec to scoreboard cell. Each step
links to the section that owns it.

```
tasks/<id>.md                                              [§01]
   │  scrub to the agent-visible prompt (answer key dropped)
   ▼
run-agent  ── builds a /tmp substrate copy, dispatches the agent,
              snapshots ONLY the changed/created writable files       [§01]
   ▼
submission/  (Source/CraftBenchTemplate/… + Content/Tasks/…)
   │
   ▼
verify-single  ── integrity-pin + sandbox pre-flight,                 [§02, §03]
                  then run the selected LAYERS in order:
                     ART → L1 (build) → L2 (PIE) → L3 → L2I → R2(advisory)
   │   exit 0 PASS · 1 FAIL · 3 substrate-reject · 4 sandbox-reject
   ▼
result.json   (overall: PASS | FAIL | FAIL_NO_EDITS; the product slug is the key) [§04]
   ▼
compare / dashboard  ── capability grid + grounded head-to-head        [§04]
```

The four hops, and where to read each:

1. **`tasks/<id>.md` → agent-visible prompt → submission.** The harness scrubs the
   spec down to the two agent-visible H2 sections (the answer-key sections —
   verifier spec, anti-gaming notes, reference solution — are dropped), copies the
   substrate into an isolated `/tmp` workspace, runs the agent, and snapshots the
   diff. → **[01-run-agent.md](01-run-agent.md)**

2. **The arena the submission is overlaid onto.** Why the substrate splits into an
   agent-writable runtime module and a verifier-only, hash-pinned test module; how
   the `AFunctionalTest` fixtures observe behavior (PIE-native time model, identity
   by tag); how a task wires its fixture + map to the verifier. →
   **[03-substrate.md](03-substrate.md)**

3. **submission → verifier layers → exit code → `report.json`.** The deterministic
   gate: the pluggable Layer registry, what L1 (dual-target build), L2 (PIE fixture),
   and L2I (asset introspection) each assert, the two pre-flight defenses, and the
   exit-code map (0/1 graded; 3/4 are verifier-noise rejects, never an agent FAIL). →
   **[02-verify-single.md](02-verify-single.md)**

4. **`result.json` → compare → dashboard.** How many verdicts aggregate into the
   capability × product grid, why a "leader" is only meaningful when the row is
   *grounded* (≥2 products ran the same task), the live-status disk contract, and the
   read-only dashboard. → **[04-output-side.md](04-output-side.md)**

And one step *off* the certifying path:

5. **The advisory periphery.** The firewalled R2 LLM judge (non-gating by
   construction) and the Aura autonomous-agent rig — both annotate a verdict, neither
   certifies. → **[05-advisory-periphery.md](05-advisory-periphery.md)**

---

## Recommended reading order

1. **README.md** (this page) — the frame and the data flow.
2. **[02-verify-single.md](02-verify-single.md)** — the deterministic gate. Start
   here: it *is* the eval, and the Layer model it introduces is the spine everything
   else hangs off.
3. **[03-substrate.md](03-substrate.md)** — the arena the gate runs against. Read
   right after the gate, because the fixtures and the two-module split are *why* the
   gate can be deterministic and un-gameable.
4. **[01-run-agent.md](01-run-agent.md)** — the harness that produces the submission
   the gate grades. Now that you know what a submission must satisfy, see how it's
   scrubbed, sandboxed, and snapshotted.
5. **[04-output-side.md](04-output-side.md)** — how verdicts become the scoreboard.
6. **[05-advisory-periphery.md](05-advisory-periphery.md)** — read last and read
   lightly: everything here annotates a verdict, never moves it.

> If you prefer to follow the data rather than the architecture, read in file order
> 01 → 02 → 03 → 04 → 05; the path above front-loads the deterministic gate because
> it is the concept the rest of the tour depends on.

---

## Lite glossary

Plain-English definitions of the load-bearing terms. Each is developed fully in the
linked section.

- **Substrate** — the single, engine-pinned UE 5.8 project (`CraftBenchTemplate`)
  that every task is graded against. The agent edits an isolated copy of it. See §03.
- **Fixture** — an `AFunctionalTest` C++ class in the verifier-only module that
  *observes* the agent's behavior in a live PIE world and decides PASS/FAIL for one
  task. It finds the actors it watches **by tag, never by class**, so the agent is
  free to subclass. See §03.
- **Layer / gating** — a verification method (build, PIE test, asset introspection,
  advisory judge) plugged into the verifier as a `Layer`. A *gating* layer
  contributes to the certified PASS/FAIL; a *non-gating* (advisory) layer only
  annotates and is structurally absent from the verdict computation. Adding a
  verification method = writing one Layer. See §02.
- **Sandbox** — the submission-acceptance defense: a submission file is accepted
  only if it matches the agent's `writable` allowlist and no `deny` prefix
  (`AGENT_WRITABLE.json`). A violation rejects the run (exit 4) before any build.
  See §02, §03.
- **Integrity pin** — pinned SHA-256 hashes of every file in the verifier-only test
  module (`verifier_hashes.json`). Any drift rejects the run (exit 3) before any
  build, so the agent cannot tamper with the thing measuring it. See §02, §03.
- **Discrimination check** — the calibration standard for a verifier: it must PASS
  on the reference solution **and** FAIL on an empty submission and on plausible
  gaming variants. A verifier that can't tell a real solution from a fake one isn't
  a verifier. See §03 (the fixtures' anti-gaming idioms) and §02.
- **Product** — a `<tool_layer>:<model>` slug (e.g. `claude-p:opus`,
  `aura-mcp:claude-sonnet-4-6`). The same scrubbed tasks run across products; the
  slug is the join key on the scoreboard. See §04.
- **Grounded** — a capability row on the scoreboard is *grounded* only if ≥1 of its
  tasks was run by ≥2 products (a true head-to-head). An ungrounded row aggregates
  disjoint tasks, so its "leader" is meaningless and is flagged. See §04.
