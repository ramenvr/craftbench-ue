# L2-introspect — verification layer contract

**Status:** layer + verdict parser shipped and unit-tested
(`layers/l2_introspect.py`, `tests/test_l2_introspect.py`, 10 tests).
Runner wiring into `run_task.py` + the first real task are the **next** step
(see *Wiring-time decisions* below).

## What it is

A **deterministic, structural** verification layer for *generated assets* —
the spec's `L2-mat` generalized to Material / Blueprint-graph / AnimBP-state-
machine / UMG-`WidgetTree` / DataTable / behavior-tree structure. It runs a
**verifier-owned** Python introspection script headlessly via
`UnrealEditor-Cmd -ExecutePythonScript=<script>` (the `scaffold_map.py`
channel), and reads a JSON verdict the script prints. No PIE, no LLM —
this is an R0/R1 (deterministic) layer and is eligible for the certification
gate (FR-020d-compliant).

Runtime behavior (e.g. "is the AnimInstance actually in `Walk` at t=0.5s")
is **not** this layer — that needs the PIE runner (`l2_pie.py`).

## The verdict contract

The introspect script MUST print exactly one block on stdout (and ideally
mirror it to the UE log):

```
CRAFTBENCH-INTROSPECT-JSON-START
{"checks": [{"id": "<str>", "passed": <bool>, "detail": "<str>"}, ...]}
CRAFTBENCH-INTROSPECT-JSON-END
```

Status semantics (`run_l2_introspect` → `L2IntrospectResult.status`):

| Condition | status |
|---|---|
| block parses, ≥1 check, **every** check `passed` true | `pass` |
| block parses, ≥1 check, any check false **or** zero checks | `fail` |
| no block / malformed JSON / missing `checks` list | `error` (fail-safe — never certifies on an unconfirmed verdict) |

If the block appears twice (re-run / double dispatch), the **last** one wins.

### `error` is NON-GRADED — it does not reach the agent's verdict

`error` says the **verdict channel** produced nothing to read, so the thing that
went wrong is verifier-owned (a missing script, a typo in a grader, a malformed
block) — never submission content. `L2IntrospectLayer` therefore propagates it
verbatim onto the `LayerReport` (it does **not** collapse to `fail`; that bug
was fixed 2026-07-27) and `run_task.harness_error_reasons` predicate (5) turns
it into **exit 7 / `overall: "harness-error"`**, which
`adapters.base.GRADED_VERDICTS` excludes from every pass-rate denominator.

Two consequences worth knowing when authoring:

- **`error` dominates `fail`** across a multi-script L2I layer: if any script's
  channel died the gate is incomplete and must not certify.
- **One carve-out.** The governed timeout (`exit_code` 124) stays a **graded
  FAIL**, because agent C++ is linked into the editor this layer launches and a
  pathological submission can hang it — the same asymmetry that keeps L1's 124
  graded. See `run_task.LAYER_ERROR_GRADED_EXITS`.

A script that runs correctly and finds the asset wrong must report
`{"passed": false}` checks (→ `fail`, graded). Never signal an agent failure by
suppressing the verdict block.

Copy `introspect_template.py` and adapt its two EDIT blocks.

## Hard rules for introspect scripts

- **READ-ONLY** — never mutate the asset, level, or project.
- **Identity by pre-declared content path / tag, never by class** (agents may
  subclass).
- **Anti-circularity** — stock UE Python only (`EditorAssetLibrary`,
  `MaterialEditingLibrary`, reflection); **never** call Aura's MCP tools to
  grade Aura.
- **Never echo submission-derived text into a detail string raw.** Asset
  paths, class names, registry tag text and "unexpected file" names are all
  chosen by the AGENT. Cap the length and neutralize the marker family
  (`CRAFTBENCH-INTROSPECT-JSON-START` / `-END`) before it reaches a check
  detail — `_defang` in `kp_derived_class_search.py` is the reference
  implementation; some graders instead map whitespace and `=` to `~`, which
  also works. Echo the agent's own text at all only when it is what makes a
  FAIL diagnosable.

  **Status of this rule, stated precisely because it changed (2026-08-12).**
  It was previously enforced by convention and copy-paste alone: 25 of the
  26 verdict-emitting graders implement some form of it, no two identically,
  and this contract did not mention it — so the one that forgot would have
  been exposed with nothing to catch it. What it was defending was real: an
  embedded END marker TRUNCATED the JSON body, the parse failed, L2I
  reported `error`, and `run_task` routed that to HARNESS-ERROR — a
  NON-GRADED verdict, i.e. a submission deleting itself from the pass-rate
  denominator by choosing a filename. **That hole is now closed at the
  layer**: both marker regexes are end-of-line anchored, so a marker inside
  a payload cannot terminate the block
  (`tests/test_introspect_marker_anchoring.py`). Per-grader defanging is
  therefore defense-in-depth rather than the only thing standing between an
  adversarial name and the denominator — keep writing it (a capped, quiet
  detail is better than a 50 KB one regardless), but a new grader that
  forgets it is no longer a grading-integrity hole.

## Wiring-time decisions (next step, partly the maintainer's call)

1. **Where introspect scripts live + integrity.** Like `AFunctionalTest`
   fixtures, they're verifier-owned and must be **deny-write** so an agent
   can't supply its own grader. They live under `tools/verify-single/introspect/`
   (outside the submission overlay entirely) and are integrity-anchored by
   git-HEAD provenance (the hash manifest + `--regen-verifier-hashes` retired
   2026-07-16; the tests module additionally carries a human review gate on
   commit).
2. **The `Content/` write boundary** (dev-plan "OPEN DECISION 1"). Generated
   `.uasset` deliverables land under `Content/`, which `AGENT_WRITABLE.json`
   currently **denies** — so an agent can't even submit a material/widget/BP
   today. To run asset-deliverable tasks: carve out a writable `Content/`
   subtree (e.g. `Content/Materials/`, `Content/UI/`) while keeping
   `Content/Maps/` + verifier assets denied. The verifier then loads the
   overlaid `.uasset` via this layer and asserts structure.
3. **`run_task.py` wiring.** A task spec declares it uses the introspect
   layer + names its script + target asset path; `run_task` runs
   `run_l2_introspect` and folds the verdict into the report. (Deferred to
   avoid colliding with the in-flight PIE-runner work on `run_task.py`.)

## Asset-integrity preamble (2026-07-29)

When the runner passes the sandbox-accepted submission rel-paths into the
layer (`LayerContext.submitted_files` -> `run_l2_introspect(submitted_assets=...)`),
the grading editor session runs a VERIFIER-GENERATED bootstrap that validates
every plain `Content/` asset (`.uasset`/`.umap`; OFPA mirror packages are
excluded - the registry does not index them as assets) BEFORE chaining into
the task's introspect script in the same session:

  * the package must contain the asset its file path claims
    (`PACKAGE_IDENTITY_MISMATCH` otherwise), and
  * it must not be a `UObjectRedirector` (`REDIRECTOR_SUBMITTED`) - the whole
    point: `load_asset` FOLLOWS redirectors, so a submitted redirector at a
    legal path would make a grader silently grade the redirect TARGET.

The bootstrap prints its own block (`CRAFTBENCH-ASSET-INTEGRITY-JSON-START` /
`...-END`) ahead of the task verdict block. Taxonomy routing, mirrored from
`run_task.harness_error_reasons`: agent-caused violations are PREPENDED as
failed `asset_integrity` checks (graded FAIL; note this adds to the check
denominator only on violating submissions), while verifier-side probe
failures (reason prefix `INTEGRITY_`) and a missing integrity block route the
layer to status `error` (-> HARNESS-ERROR exit 7). The bootstrap waits for
the asset-registry scan (`wait_for_completion`) before probing so a slow
startup scan can never misread a valid asset as missing. Tests:
`tests/test_asset_integrity.py`.

### The `allow_redirectors` exception (2026-07-30, rename-residue lane)

A rename task's legitimate submission can contain a `UObjectRedirector` at
the OLD path (UE's rename manager leaves one whenever a referencer cannot be
fixed up in place). The spec front-matter key `allow_redirectors:` names the
exact `/Game/...` packages whose submitted redirector the preamble tolerates.
Properties, all fail-closed:

  * **Default-closed**: absent key = pre-flag behavior, byte-identical
    manifests. The exemption narrows ONLY the redirector rejection; the
    identity check and probe-error routing still run on allowed entries, and
    a redirector at any NON-listed path still grades `REDIRECTOR_SUBMITTED`.
  * **Task-scoped**: `spec.py` rejects (ValueError -> exit 2, spec error)
    any entry outside the task's own `/Game/Tasks/<id>/` namespace, and the
    key at all when `L2I` is not in `layers`.
  * **Grader rule (load-bearing, NOT mechanically enforced)**: a grader for
    a task that declares this key may read allowed old paths ONLY through
    registry `AssetData` (`asset_class_path`, `get_tag_value("DestinationObject")`,
    `get_referencers`) - NEVER `load_asset`/`load_object` through them
    (that silently grades the redirect TARGET, the exact hole the preamble
    exists to close). New-path packages may be `load_asset`-ed only after a
    registry class check proves them non-redirector. Reviewers must check
    this by hand on every grader whose spec declares the key.

Threading: `spec.py` (`TaskSpec.allow_redirectors`) -> `registry.py`
L2I call site -> `run_l2_introspect(allow_redirectors=...)` ->
`write_integrity_bootstrap` marks matching manifest entries
`"redirector_ok": true` (key written only when true) -> the bootstrap's
redirector branch consults it. Tests: `tests/test_asset_integrity.py`
(`TestAllowRedirectorsFlag`, `TestSpecAllowRedirectors`).
