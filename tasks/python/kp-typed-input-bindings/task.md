---
id: kp-typed-input-bindings
substrate: ThirdPerson
set: python
tier: T1
capability_bucket: Gameplay Programming
category: input
layers: [L1, L2I]
introspect: [kp_typed_input_bindings.py]
---

# kp-typed-input-bindings

The first task of the `tasks/python/` basket (owner decision 2026-08-11):
**outcome-graded editor-scripting work**. The deliverable is the resulting
editor state — four saved assets — graded by the existing deterministic L2I
introspect lane exactly like the `bp` basket. The prompt describes an outcome
whose exactness and volume (four typed assets, six exact bindings, exact
per-binding transform chains) make editor scripting the natural way to
complete it, but **no gate asserts "python was used"** — hybrid and
task-dependent by design. A future v2 may additionally re-execute a submitted
script; that is deliberately not this version.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): an input row, one of
a group derived from observed editor-scripting-agent failures. The source row's
verification cell:
*"3 typed InputActions + IMC_Eval exist; IMC has exactly 6 key->action
mappings with correct Swizzle/Negate modifiers; mapping count verified."*

Six deliberate divergences, each recorded so the source row and the task can be
reconciled:

1. **The source row's prompt names UE Python APIs verbatim** (`UInputAction`,
   `EInputActionValueType.AXIS2_D`, `InputModifierSwizzleAxis`,
   `set_editor_property`, ...). Hard Rule #2 forbids every one of those in an
   agent-visible prompt. The prompt below is rewritten as observable
   outcomes: reading *shapes* (a pair of values / one signed value / on-off),
   key-to-action *bindings*, and value *transforms* described by what they do
   to the reading. The exact numbers (three assets, six bindings, which key,
   which transform) stay in the prompt — exactness is this basket's point.
2. **Content path.** The source row's `/Game/EvalInput` exists nowhere in either
   substrate and is outside every writable prefix. Re-pathed to the repo
   convention `/Game/Tasks/kp-typed-input-bindings/`.
3. **Action trio re-typed 2D + 1D + boolean** (task-card decision,
   2026-08-11). The source row's trio is 2D + boolean + boolean; replacing the
   redundant second boolean (`IA_Sprint`) with a one-axis action (`IA_Zoom`)
   covers all three common value types, and — because a freshly created
   action defaults to the on/off type — makes **two** of the three type gates
   default-excluding instead of one.
4. **Transform layout re-cut: swizzle on two bindings, negate on one**
   (task-card decision). The source row has swizzle on two and negate on *two*
   (S and A). Here the single negate rides the S binding (after its swizzle,
   order graded), A and D are explicitly transform-free, and the freed sixth
   binding becomes the 1D-axis binding (mouse wheel). The source row's
   `LeftShift -> IA_Sprint` row is dropped with `IA_Sprint`.
5. **"Print the asset paths and the mapping count" is dropped.** The python
   basket grades the resulting editor state, not agent prose; a printed
   confirmation is unverifiable narrative. The mapping count is graded
   structurally off the saved asset (`imc_binding_count_is_six`).
6. **The source row's metric cells are out of scope.** "% of verification checks
   passed" maps to the reported (non-gating) `tests_passed/tests_run` = x/14
   ratio the registry already records; "# of execute_unreal_python calls +
   compile errors" is a harness-level efficiency metric no current layer
   collects — recorded in `notes.md` as future work, not smuggled into the
   gate.

> **Note on the behavior-only rule (Hard Rule #2).** Like
> `t1-dawn-fog-lighting-rig` and `t1-hero-blueprint-copy-with-flashlight`,
> this task names the concrete deliverable asset paths and the four asset
> names the verifier keys on (`IA_Move`, `IA_Zoom`, `IA_Jump`,
> `IMC_Bindings`). That is the standard, precedented exception for
> asset-deliverable tasks whose whole point *is* producing specific assets —
> pre-declared identity lets the verifier load each asset directly instead of
> scanning content. Everything else stays behavior-only: **no engine class
> name, no plugin name, no scripting API name, and no editor-operation name
> appears in the prompt.** The transforms are described by their effect on
> the value ("swap the first two components", "flip the sign"), never by
> their engine names.

## Primary concept

- `enhanced-input` — Enhanced Input
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine)

The load-bearing capability is standing up the modern UE input data stack —
typed action assets and a mapping context — and dialling an exact,
non-trivial binding table into it: right value type per action, right key per
binding, right transform chain (including order) per binding. Adjacent
concepts `input-actions` and `input-modifiers` (same doc URL) are exercised
as parts of the same stack; `enhanced-input` is primary because the graded
difficulty is knowing which pieces the stack is made of and which knob on
each piece the described behavior lives on.

## Prompt given to the agent

> This project's own input content is off-limits and irrelevant to this
> task. The folder `Content/Tasks/kp-typed-input-bindings/` is empty, and
> everything below must be created in it and saved there.
>
> Produce **three input-definition assets**, each describing one player
> intent and the shape of the value that intent carries:
>
> - `IA_Move` — carries a **two-axis reading**: a pair of numbers, one per
>   movement axis.
> - `IA_Zoom` — carries a **one-axis reading**: a single signed number.
> - `IA_Jump` — carries a plain **on/off reading**.
>
> Then produce **one input-configuration asset**, named `IMC_Bindings`, that
> binds physical inputs to those three intents. It must hold **exactly six**
> key-to-intent bindings — these six and no others, one binding per line
> below, each with exactly the value transforms listed for it:
>
> 1. The **W** key drives `IA_Move`. Its raw press arrives on the first
>    component of the pair, so this binding carries one transform: **swap
>    the first two components of the value** (the third, unused component
>    stays put), so the press lands on the second component.
> 2. The **S** key drives `IA_Move`, with **two** transforms applied in this
>    order: first the same **first-two-component swap** as W, then a **sign
>    flip** of the value.
> 3. The **A** key drives `IA_Move`, with **no transforms**.
> 4. The **D** key drives `IA_Move`, with **no transforms**.
> 5. The **mouse wheel axis** drives `IA_Zoom`, with **no transforms**.
> 6. The **space bar** drives `IA_Jump`, with **no transforms**.
>
> Each key above must appear in exactly one binding. All four assets must be
> saved in the named folder under exactly the names given.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-typed-input-bindings/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json` lists `Content/Tasks/`
  under both `writable` and `asset_writable`); fairness isolation keeps this
  task's folder while hiding every other task's.

Files that **do not exist** (the agent must create all four):

- `Content/Tasks/kp-typed-input-bindings/IA_Move.uasset`
- `Content/Tasks/kp-typed-input-bindings/IA_Zoom.uasset`
- `Content/Tasks/kp-typed-input-bindings/IA_Jump.uasset`
- `Content/Tasks/kp-typed-input-bindings/IMC_Bindings.uasset`

Out of scope / not needed:

- No C++ is required or expected. No level needs to be created, opened or
  saved, and no map is loaded by the grader (this task does **not** need the
  map-loading pattern). No character or config wiring is graded: the
  deliverable is the four assets, nothing consumes them at runtime.
- The stock template's own input content (which includes same-named action
  assets) lives under `Content/ThirdPerson/` and `Content/Input/` — both
  deny-listed. `Content/Maps/`, `Content/__ExternalActors__/` (outside
  `Tasks/`), `Config/` (beyond the two `config_writable` files, none needed
  here) and the other stock content dirs are likewise off-limits; the agent
  neither can nor needs to touch them.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of a saved asset (which assets exist, what kind each is, one
enum on each action, and the exact binding table on the configuration
asset), so it is read by verifier-owned editor-Python reflection over the
submitted assets — not by rendering, ticking, or a PIE world. L2 is
deliberately **not** declared: there is nothing to observe over time, and a
fixture would need a map and a pawn this task has no use for.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/kp_typed_input_bindings.py` runs headless
via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 14
named checks on every leg** (constant denominator, so the reported
`tests_passed/tests_run` ratio is comparable across submissions). PASS
requires all 14:

```text
ia_move_asset_exists          /Game/Tasks/<id>/IA_Move resolves, loads, AND
                              is an input-action asset (isinstance,
                              subclass-tolerant)
ia_move_reads_axis2d          its value type is the two-axis type
ia_zoom_asset_exists          IA_Zoom resolves / loads / right asset kind
ia_zoom_reads_axis1d          its value type is the one-axis type
ia_jump_asset_exists          IA_Jump resolves / loads / right asset kind
ia_jump_reads_boolean         its value type is the on/off type
imc_asset_exists              IMC_Bindings resolves, loads, AND is an
                              input-configuration asset
imc_binding_count_is_six      the mapping array holds EXACTLY 6 entries
map_w_move_swizzled           key W bound exactly once; target == IA_Move
                              (by full content path); modifier chain ==
                              [axis-swap YXZ] exactly
map_s_move_swizzled_negated   key S bound exactly once; target == IA_Move;
                              chain == [axis-swap YXZ, negate] in that order
map_a_move_plain              key A bound exactly once; target == IA_Move;
                              chain empty
map_d_move_plain              key D bound exactly once; target == IA_Move;
                              chain empty
map_wheel_zoom_plain          key MouseWheelAxis bound exactly once; target
                              == IA_Zoom; chain empty
map_space_jump_plain          key SpaceBar bound exactly once; target ==
                              IA_Jump; chain empty
```

**Read routes** (each declaration's Python readability follows from
`CPF_Edit | CPF_BlueprintVisible`; every read tries the pythonized and the
raw spelling and fails closed when none reads):

- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist` +
  `load_asset`, then `isinstance` against `unreal.InputAction` /
  `unreal.InputMappingContext` as a tri-state probe (an unevaluable probe
  FAILS the check — it never passes on the absence of an exception).
- *value type* — the action's `ValueType` enum (`EditAnywhere,
  BlueprintReadOnly` in `InputAction.h`), compared through a canonical
  upper-alnum form so `AXIS2_D` / `Axis2D` spellings cannot cause a false
  FAIL; the source row's `action_value_type` spelling is tried as a fallback.
- *binding table* — the context's `Mappings` array (`EditAnywhere,
  BlueprintReadOnly` in `InputMappingContext.h`); per element the `Key`
  (FKey; its `KeyName` FName compared case-insensitively, matching FName
  semantics), the `Action` object (identity by **full content path**, so the
  stock template's same-named `/Game/ThirdPerson/Input/Actions/IA_Move` can
  never satisfy a gate), and the `Modifiers` instanced array, canonicalized
  in order: a swizzle-type modifier contributes `swizzle_<order>` (order read
  off its `Order` enum), a negate-type modifier contributes `negate`, any
  other class contributes `other_<class>`. Chain equality is **ordered and
  exact** — extra, missing, reordered, or foreign modifiers all fail.

**Identity is by pre-declared content path and pre-declared asset name,
never by class and never by scanning.** Class is consulted only as the
assertion ("is the thing at IA_Move really an input-action asset"), written
as `isinstance`, so a legitimate subclass is not penalized.

**Every gate excludes the untouched default, or its coincidence is recorded.**
A freshly created action asset defaults to the **on/off** value type; a
freshly created configuration asset has an **empty** mapping array; a
mapping added without transforms has an **empty** modifier chain; the
axis-swap modifier's order property defaults to **YXZ**. Audited:

| graded fact | untouched default | gate | default inside gate? |
|---|---|---|---|
| IA_Move value type | on/off (Boolean) | two-axis | **no** |
| IA_Zoom value type | on/off (Boolean) | one-axis | **no** |
| IA_Jump value type | on/off (Boolean) | on/off | **yes — recorded**: exactness confirmation only; the non-default fact is the asset existing at all, and the check still discriminates a wrongly-typed submission |
| binding count | 0 | == 6 | **no** |
| W / S chains | empty | non-empty exact chains | **no** |
| A / D / wheel / space chains | empty | empty | **yes — recorded**: conjoined with the non-default facts that the binding exists, exactly once, on the right action |
| swizzle order | YXZ | YXZ | **yes — recorded**: the non-default fact is a swizzle modifier existing on the mapping at all; the order read confirms exactness and would catch an explicit wrong order |

**These structural facts are disclosed in the prompt on purpose.** Unlike
`t1-dawn-fog-lighting-rig` (whose numeric bands are hidden because the row
measures *judgment*), this row measures **exact transcription of a precise
outcome into editor state** — the python basket's declared point. Everything
gated is stated in the prompt in behavioral terms; nothing is a hidden taste
boundary. What stays verifier-only is the *mechanism* vocabulary (class
names, enum spellings, API routes), which is exactly the knowledge the row
exists to measure.

**Failure attribution.** An unresolvable asset fans its resolution token out
to the checks that depend on it (one cause, one token — never three invented
downstream failures); every exception path emits a `*_READ_ERROR` /
`*_PROBE_ERROR` / `*_ABORTED` token that appears in **no** MATRIX row, so a
broken UE API name can never be credited as a named failure.

**Score granularity.** `registry.py` sets `tests_run`/`tests_passed` from
the per-check counts, so `report.json` carries `x/14`. That number is
**reported, not gating** — `overall` stays `all(status == "pass")`.

### Accepted residuals

- **Extra assets in the task folder are not failed.** A submission may leave
  scratch assets beside the four graded ones; only the four pre-declared
  paths are read. Accepted because the sandbox already bounds where those
  extras can live, and a `no_extra_assets` gate would fail agents for
  harmless intermediate artifacts. (The binding table itself has no such
  residual: count == 6 is exact and each key is exactly-once.)
- **Trigger configuration is ungraded.** The prompt never mentions
  press/hold behavior, so a submission adding triggers to a binding is not
  failed for it — the chain gate reads modifiers only. Recorded so a future
  edit does not silently start grading an undisclosed axis.
- **Negate axis flags are ungraded.** The sign-flip transform is graded by
  type presence and position; its per-axis enable flags (default: all axes)
  are not read. "Flip the sign of the value" is satisfied by the default
  flags, and grading them would gate an axis the prompt does not disclose.
- **How the assets were made is ungraded** — editor UI, scripting, or MCP
  tooling all pass identically. This is the python basket's outcome-graded
  law, not an oversight.

## Reference solution metadata

- LOC range: **0** lines of shipped code. The deliverable is four new
  `.uasset` files (an authoring script an agent may write to produce them is
  not part of the deliverable).
- Files touched: 4 created, 0 modified.
- Senior-dev hours: 0.3-0.75 (four assets, one enum each on three of them,
  a six-row binding table with three modifier instances — trivial in the
  editor UI, moderately fiddly via scripting, which is the intended
  difficulty).

## Anti-gaming notes

Per the amended checklist §7 (2026-08-11), each note names its defense with
a resolvable pointer; no per-note variant is authored — the automatic
reference-PASS / empty-FAIL legs plus the requirements table in
`discrimination/MATRIX.md` carry the non-vacuity and soundness burden.

1. **Right names, wrong kinds.** *Failure mode*: four assets with the four
   required names, but generic data assets (or renamed copies of something
   else) that no input system could consume. *Defense*: every `*_asset_exists`
   check requires name AND `isinstance` against the required asset class,
   tri-state (an unevaluable probe fails); an impostor dies at
   `IA_MOVE_WRONG_CLASS class=` / `IMC_WRONG_CLASS class=` with the found
   class named. Pointer: `_resolve_asset` in
   `tools/verify-single/introspect/kp_typed_input_bindings.py`; rows 1/3/5/7
   of the requirements table.
2. **Everything left on/off-typed.** *Failure mode*: three actions created
   and never typed — the freshly-created default satisfies the Jump gate and
   the agent hopes the others slide. *Defense*: the Move and Zoom type gates
   exclude the creation default by construction (dead-gate table above);
   they die at `IA_MOVE_VALUE_TYPE_WRONG value_type=` /
   `IA_ZOOM_VALUE_TYPE_WRONG value_type=`. Pointer: requirements rows 2/4.
3. **Padded or collapsed binding table.** *Failure mode*: six bindings
   reached by duplicating an easy one and dropping a transform-bearing one,
   or seven bindings hoping only presence is counted. *Defense*: the count
   gate is exact (`IMC_BINDING_COUNT_WRONG count=`) AND each of the six keys
   is independently gated to appear **exactly once**
   (`MAP_W_KEY_NOT_BOUND_ONCE count=`, etc.) — padding always breaks at
   least one of the seven gates. Pointer: `_binding_check`; requirements
   rows 8-14.
4. **Transforms on the wrong binding, or in the wrong order.** *Failure
   mode*: the swizzle lands on A instead of W, or S's chain is
   [negate, swap] — same modifier multiset, wrong table. *Defense*: chain
   equality is per-binding, ordered, and exact against the canonical chain
   (`MAP_S_MODIFIER_CHAIN_WRONG chain=`, `MAP_A_MODIFIER_CHAIN_WRONG
   chain=`); an extra modifier on a plain binding fails that binding's gate.
   Pointer: `_canon_chain` + `_binding_check`; requirements rows 9-14.
5. **Binding to look-alike actions.** *Failure mode*: the context binds the
   substrate's own stock action assets (same leaf names, different folder) —
   or the agent's own extra copies — instead of the three graded ones.
   *Defense*: action identity is the **full content path** under
   `/Game/Tasks/kp-typed-input-bindings/`, compared exactly
   (`MAP_W_WRONG_ACTION action=` prints both paths). The stock content is
   also deny-listed, so the graded assets cannot be replaced in place.
   Pointer: `_object_content_path`; requirements rows 9-14; sandbox law in
   `UE-projects/ThirdPerson/AGENT_WRITABLE.json`.

## Hidden invariants

- **The check denominator is fixed at 14 on every leg**, including the empty
  submission (which scores 0/14 — this task ships no baseline for any check
  to pass against). A submission cannot improve its reported ratio by making
  checks unreachable.
- **Error tokens are disjoint from failure tokens.** Every exception path
  emits `*_READ_ERROR` / `*_PROBE_ERROR` / `*_ABORTED`, none of which
  appears in any MATRIX row — a broken UE API name surfaces as an
  uncredited FAIL, never as a variant's named failure.
- **Every MATRIX-keyed token is a single source literal** (missing-asset
  tokens embed the full pre-declared path in one piece), so the static
  MATRIX oracle can verify every expected substring by grepping the script —
  no span crosses a placeholder or a concatenation.
- **The default-coincident gates are recorded, not hidden.** The dead-gate
  table above names the three coincidences (Jump's type, the four empty
  chains, the swizzle order) and the non-default fact each is conjoined
  with; any future re-cut of the binding table must re-run that column.
