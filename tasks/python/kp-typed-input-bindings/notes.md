# kp-typed-input-bindings — authoring notes

## 1. Provenance (the source row)

- **Source:** an earlier internal task list (not shipped) — an input row, the
  last of a group derived from observed editor-scripting-agent failures
  ("prompts name UE Python APIs verbatim; want partial-credit + efficiency
  metrics").
- **Its verification cell:** "3 typed InputActions + IMC_Eval exist; IMC
  has exactly 6 key->action mappings with correct Swizzle/Negate modifiers;
  mapping count verified."
- **Its budget cells:** "<=12 steps; <=4 min"; metrics "% of verification
  checks passed" and "# of execute_unreal_python calls + compile errors".
- **Basket:** first task of `tasks/python/`:
  outcome-graded editor-scripting work — the deliverable is the resulting
  editor state, graded by the deterministic L2I lane like `bp/`; **no gate
  asserts "python was used"**. A future v2 may re-execute submitted scripts;
  deliberately not this version. `kp-` is the python-basket family prefix
  (`tasks/README.md` basket note).

The six divergences from the source row (API-verbatim prompt rewritten
behavior-only; `/Game/EvalInput` re-pathed; the trio re-typed 2D+1D+boolean;
the transform layout re-cut to swizzle-on-two / negate-on-one; the printed
confirmation dropped; the metric cells scoped out) are recorded with
rationale in `task.md` → *Provenance and deliberate divergences*.

## 2. Design decisions

1. **Deliverable set:** `IA_Move` (Axis2D), `IA_Zoom` (Axis1D), `IA_Jump`
   (Boolean), `IMC_Bindings` with exactly six bindings:
   W→Move [swizzle YXZ]; S→Move [swizzle YXZ, negate]; A→Move [];
   D→Move []; MouseWheelAxis→Zoom []; SpaceBar→Jump [].
   This satisfies the task card's "axis swizzle on two, negate on one"
   exactly. A and D are deliberately transform-free even though a
   sane WASD setup would negate one of them — the prompt states each
   binding's chain explicitly (exactness is the basket's point), so an agent
   "fixing" the design to its prior fails honestly at a named chain gate.
2. **Grading:** 14 fixed checks, constant denominator, all structural.
   Identity by full content path (defeats the stock template's same-named
   `/Game/ThirdPerson/Input/...` assets); class asserted via tri-state
   `isinstance` (subclass-tolerant, unevaluable probe FAILS); chains
   canonicalized ordered-exact. Dead-gate audit table in `task.md` records
   the three default coincidences honestly (Jump's Boolean, the four empty
   chains, the swizzle order YXZ) with the non-default fact each is
   conjoined with.
3. **Prompt disclosure:** unlike `t1-dawn-fog-lighting-rig` (hidden bands =
   judgment row), every graded fact here is disclosed behaviorally — this
   row measures exact transcription into editor state plus knowing the
   mechanism vocabulary, which stays verifier-only.
4. **No discrimination variants** (amended checklist §7, 2026-08-11): the
   requirements table in `discrimination/MATRIX.md` found no unasserted
   requirement, so only the automatic reference-PASS / empty-FAIL legs ship.
   Four wrongness shapes were still probed offline against the real grader
   (see §4) without committing them as variants.
5. **Asset names** `IA_*` / `IMC_*` are naming conventions, not class names;
   pre-declared deliverable names are the precedented Hard-Rule-#2 exception
   (`t1-dawn-fog-lighting-rig`'s note). The id `kp-typed-input-bindings`
   names the capability area, matches the card, and is no substring of any
   other id. NB: the id is agent-visible via the content path; "mappings" is
   outcome vocabulary ("key-to-intent bindings"), not an editor-operation
   leak.
6. **Introspect script name** `kp_typed_input_bindings.py` = the task id
   with underscores, which is exactly what
   `tools/coverage/status_gen.py::classify_tasks` probes for — this task
   dodges the classifier quirk recorded in
   the set-provenance note (internal, not shipped) (scripts named without the tier
   prefix stay invisible to it).

## 3. Reference: PENDING THE AUTHORING-LANE RUN

**The `reference/` dir is EMPTY on purpose.** `.uasset` binaries cannot be
authored from a text-only track and none is fabricated.
`aids/author_reference.py` is the headless authoring lane
(`UnrealEditor-Cmd <ThirdPerson.uproject> -ExecutePythonScript=... -nullrhi
-unattended -nosplash`): it builds the four assets at the real content path,
saves, **grades in-process with the real verifier** (harvest only on 14/14),
copies the `.uasset` files into `reference/Content/Tasks/<id>/`, deletes the
staged assets, and prints `KPEIM-DONE` only on full success. It derives every
path from its own location (no hardcoded basket) and refuses a substrate that
already carries the folder.

## 4. Offline validation already done (2026-08-11, no editor)

Run with a simulated `unreal` module through the REAL grader + parsers:

- empty leg → 0/14, `ia_move_asset_exists` detail is verbatim
  `IA_MOVE_MISSING /Game/Tasks/kp-typed-input-bindings/IA_Move`.
- reference-shaped state → **14/14**.
- wrongness probes, each dying at its predicted one-piece token:
  S-chain reordered → `MAP_S_MODIFIER_CHAIN_WRONG chain=`; W bound to the
  stock same-named action → `MAP_W_WRONG_ACTION action=`; W duplicated
  (7 mappings) → `IMC_BINDING_COUNT_WRONG count=7 expected=6` AND
  `MAP_W_KEY_NOT_BOUND_ONCE count=2`; everything Boolean-typed →
  `IA_MOVE_VALUE_TYPE_WRONG value_type=BOOLEAN expected=AXIS2D`.
- no-`unreal` import → all 14 fail as `*_PROBE_ERROR` (uncreditable tokens,
  no MATRIX row claims them).
- `MATRIX.md` → real `aura_rig.discriminate.parse_matrix` registers exactly
  `{reference, empty}` (the requirements table registers nothing — its first
  column is slash-free by construction against `_VARIANT_DIR_RE.search`).
- every MATRIX-named span verified to live inside ONE source literal of the
  grader (AST constant walk) — the static oracle can grep them.
- front matter → real `spec.py::parse_task_file`: id/set/substrate/layers/
  `introspect_scripts=('kp_typed_input_bindings.py',)` all round-trip.

## 5. Calibration TODOs (need a live editor, in order)

- [ ] Run `aids/author_reference.py` headless; require `KPEIM-DONE`. Record
      the `KPEIM-SPELLING` lines here (settles: `value_type` vs
      `action_value_type`; `mappings`; `key_name`; `order`; the
      `EnhancedActionKeyMapping` member spellings; whether `unreal.Key`
      accepts constructor kwargs; whether `DataAssetFactory` needs its class
      pinned).
- [ ] `cb discriminate --task python/kp-typed-input-bindings --wip` —
      reference PASS + empty FAIL at `IA_MOVE_MISSING /Game/Tasks/`.
- [ ] `cb lint --task python/kp-typed-input-bindings` — zero ERRORs
      (watch: first task ever with `set: python`; and the inventory/CATALOG
      count claims — plan §9.2 says one new task costs a CATALOG row plus
      count edits across the repo conventions / skills).
- [ ] Commit binaries, then `./cb refgate python/kp-typed-input-bindings`
      (git-HEAD certified close) + `cb batch-eval --references all` stays
      N/N.
- [ ] Cameras: this task has no placeable visual (data assets only) —
      confirm whether `cameras.json` (the camera-plan lane; not part of this release) is waivable for asset-only tasks the
      way the checklist's "meshless subjects render NOTHING" note implies,
      or ship a minimal plan. Not authored yet on purpose.

## 6. Risks

1. **UE property-spelling risk (main).** The grader and the aid both probe
   several spellings and fail closed, but only an editor settles them. If
   `Mappings` or `Modifiers` is not reflection-readable on 5.8 (both are
   EditAnywhere in engine headers, so they should be), the grader fails with
   uncreditable `*_READ_ERROR` tokens — visible, never a silent pass.
2. **Instanced-modifier serialization.** The aid creates modifier objects
   with the IMC as outer; if `new_object`+array-set does not serialize
   instanced entries correctly, the in-process 14/14 gate catches it before
   harvest. Fallback lane if it fails: author the IMC in the editor UI once
   and harvest by hand (record it here if taken); the aura-mcp
   `add_input_action_to_mapping_context` lane exists but MCP writes need the
   AuraSandbox promotion step and grade Aura with Aura — avoid for the
   reference.
3. **`set: python` is new to the toolchain.** `spec.py` parses it (free
   scalar, verified), but `tasklint` / `inventory.py` / CATALOG tooling may
   carry `bp|cpp` assumptions — surface at the first `cb lint --all`.
4. **Enum spelling drift** (`AXIS2_D` vs `Axis2D`): both sides canonicalize
   through upper-alnum, so a false FAIL requires a genuinely different enum
   name, not a spelling.
5. **Map-loading pattern: NOT needed.** No level is loaded or graded; the
   L2I lane runs with no map argument. Flag recorded per the task card.
6. **Boolean default coincidence** (IA_Jump): a submission that creates the
   three actions and types none of them still fails 2 of 3 type gates;
   recorded in the dead-gate table rather than "fixed" by inventing an
   undisclosed non-default requirement for Jump.

## 7. Checklist state (§1-§9 of these notes)

- [x] §1 Spec — folder + v2 front matter + behavior-only prompt +
      anti-gaming notes with resolvable pointers (task.md)
- [x] §7 Discrimination — MATRIX.md with automatic legs + requirements
      table; no variants (amendment applied); offline logic oracle green
- [ ] §2-§4 scaffold/fixture/map — N/A by design (no C++, no L2, no map)
- [ ] §5 cameras.json — open question (see §5 TODO above)
- [ ] §6 reference/ — PENDING the authoring-lane run (aids/author_reference.py)
- [ ] §8 gates — need live editor + lint run
- [ ] §9 commit/PR/refgate close — after binaries exist

> **RECONCILIATION 2026-08-11/12 (authoring-lane + graph-lane runs DONE).**
> Statements above about pending binaries / empty reference/ describe the
> authoring-time state and are now historical: binaries are committed
> (39433c2, 09781a8) and `cb refgate` graded this task's reference PASS
> from git HEAD. Remaining: the empty-FAIL discriminate leg.
