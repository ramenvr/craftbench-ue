---
id: t1-hero-blueprint-copy-with-flashlight
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: other
layers: [L1, L2I]
introspect: [hero_blueprint_copy_with_flashlight.py]
---

# t1-hero-blueprint-copy-with-flashlight

**The first `L2I` task in the repo.** Every shipping spec before this one
declared `layers: [L1, L2]`; `L2I` has been implemented, registered and
unit-tested since 2026-06 and has never graded a real submission. This task is
the Phase-1 pilot of the set population plan (internal, not shipped) — its job is to
prove the asset-deliverable lane end to end (committed baseline `.uasset` ->
agent edits it in place -> one verifier-owned introspect script asserts named
structural checks), in the shape the retired `umg-image-brush-bound` task
established (`0486909~1`). No map, no fixture C++, no scaffold actor.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a Blueprint-editing
row that was never implemented there. Four deliberate divergences, each
recorded so the source row and the task can be reconciled:

1. **Id.** The source row's `t4-` is a row index; this repo's `t<N>-` is a tier.
   Retiering to `T1` and re-slugging to the observable outcome also keeps the
   editor operation ("reparent") out of the agent-visible content path.
   Rationale and the id-substring constraint: the set-provenance note (internal, not shipped).
2. **Content path.** The source row's `/Game/EvalTemplate/` **does not exist
   anywhere in the repo** (the only occurrence of that string is the source
   list), and a flat `/Game/EvalTemplate/` is outside every writable prefix of
   both substrates. Re-pathed to the repo convention `/Game/Tasks/<task-id>/`,
   which is agent-writable and fairness-pruned per task.
3. **Light brightness: 12000, not the source row's 5000.** `Intensity = 5000` is the
   **engine default** for every local (point/spot) light —
   `Engine/Source/Runtime/Engine/Private/Components/LocalLightComponent.cpp:13`
   in UE 5.8 sets `Intensity = 5000; IntensityUnits = Unitless`. The source row's
   check 3 (`intensity == 5000 +/- 0.5`) therefore passes for free on any
   freshly added spot light whose brightness the agent never touched: it is a
   dead gate that would inflate the per-check score with zero discriminating
   power. A non-default value makes the same assertion real without changing
   the behavior asked for. **This is the one divergence a human should
   confirm** — reverting it is a one-constant edit in the spec, the introspect
   script and `notes.md`.
4. **Parent-class acceptance.** The source row says "parent class is `Character`".
   This task accepts `Character` *or any subclass of it*, because the graded
   property is behavioral ("it is a walking, possessable figure with the
   inherited animated body part"), and a strict class-equality gate would
   penalize an agent that legitimately derived from the substrate's own
   character type. Rationale in **Verifier specification**.

> **Note on the behavior-only rule (Hard Rule #2).** Like
> `t0-sanity-bp-log-on-beginplay`, this task names the concrete deliverable
> asset paths and the two subobject names the verifier keys on. That is the
> standard, precedented exception for asset-deliverable tasks whose whole point
> *is* producing a specific asset — naming the path lets the verifier load one
> asset directly instead of scanning content. Everything else in the prompt
> stays behavior-only: no class name, no component type name, and no editor
> operation name ("duplicate as an asset copy" is the observable; "reparent"
> and "spot light component" are not said).

## Primary concept

- `ps-bp-class` — Blueprint Class
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-class-assets-in-unreal-engine)

The load-bearing capability is authoring a Blueprint *class asset*: deriving a
new one from an existing one, changing what it is built on so it inherits a
whole behavior stack it did not have, and composing a new subobject into the
inherited hierarchy at the right attachment point. `ps-components` (Components,
https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine)
is the adjacent concept the attachment check exercises; it is not the primary
one, because the graded difficulty is the class-hierarchy edit, not the
existence of a component.

## Prompt given to the agent

> This project ships one game-object asset at
> `Content/Tasks/t1-hero-blueprint-copy-with-flashlight/BP_Source`: an inert
> thing with a cube body part named `Body` and a numeric value named `Health`
> set to 100. We want a playable hero built from it, leaving the
> original untouched.
>
> In that same folder, produce a second asset named `BP_Hero` that begins as an
> exact copy of `BP_Source` — it must still carry a part named `Body` and still
> report `Health` as 100 — and then make `BP_Hero` a fully walking,
> player-controllable figure: placed in a level and possessed it walks, jumps
> and collides using the engine's standard humanoid locomotion, and it gains the
> animated humanoid body part such a figure comes with. Give
> `BP_Hero` a cone-shaped light named `Flashlight`, mounted directly beneath
> that inherited animated body part — not beneath the root and not beneath the
> cube `Body` — so the beam follows the body as it animates, and set its
> brightness to 12000. `BP_Source` must be unchanged when you are done: still
> inert, still carrying no light. `BP_Hero` must compile cleanly, and both
> assets must be saved.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t1-hero-blueprint-copy-with-flashlight/`:

- `BP_Source.uasset` — a Blueprint class asset built on the plain
  non-moving object type, containing:
  - a cube-shaped static body part named `Body`, parented under the asset's
    default root, using an engine primitive mesh;
  - a numeric variable named `Health`, type float, default value `100`,
    readable through the engine's reflection surface;
  - it is compiled and saved, and it carries no light of any kind.

  This asset ships with the project as committed, saved content.
  `Content/Tasks/<task-id>/` is the agent-writable Content carve-out of the
  `ThirdPerson` substrate (`UE-projects/ThirdPerson/AGENT_WRITABLE.json`) and is
  where this task's content belongs; fairness isolation keeps this task's folder
  while hiding every other task's.

Files that **do not exist** (the agent must create):

- `Content/Tasks/t1-hero-blueprint-copy-with-flashlight/BP_Hero.uasset`.

Out of scope / not needed:

- No C++ is required or expected. No level, no placed actor, no functional
  test: the whole deliverable is Blueprint asset content. `Content/Maps/`,
  `Config/`, `Content/Characters/`, `Content/ThirdPerson/` and
  `Content/Input/` are deny-listed — the agent neither can nor needs to touch
  them.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of a saved `.uasset` (what the class is built on, which
subobjects exist, where one of them attaches, one numeric default), so it is
read by verifier-owned editor-Python reflection over the submitted assets — not
by rendering, ticking, or a PIE world. L2 is deliberately **not** declared:
there is nothing to observe over time, and a fixture would need a map and a
placed actor this task has no use for.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/hero_blueprint_copy_with_flashlight.py` runs
headless via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`,
read-only, and prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits
**exactly 13 named checks on every leg** (a constant denominator, so the
per-check `tests_passed/tests_run` the registry already records is comparable
across submissions). PASS requires all 13:

```text
hero_asset_exists                          /Game/Tasks/<id>/BP_Hero resolves
hero_parent_is_character                   its generated class is a walking-character
                                           class (Character or a subclass)
hero_retains_body_component                a subobject named "Body" survives on BP_Hero
hero_retains_health_100                    BP_Hero's default Health == 100 (+/-0.01)
hero_has_flashlight_component              a subobject named "Flashlight" exists
hero_flashlight_is_cone_light              that subobject is a cone-beam light
hero_flashlight_attach_parent_is_mesh      its attach parent is the INHERITED animated
                                           body part: named "Mesh"/"CharacterMesh0" AND
                                           a skeletal mesh component AND inherited/native
                                           rather than authored by the submission
hero_flashlight_intensity_12000            its brightness == 12000 (+/-0.5)
hero_compiles_up_to_date                   BP_Hero loads with an up-to-date compile
                                           status (BS_UpToDate / ...WithWarnings)
source_unchanged_not_character             BP_Source's class is NOT a walking-character
                                           class (it was not reparented in place)
source_has_no_flashlight                   BP_Source carries no "Flashlight" subobject
```

**Read routes** (all confirmed live on UE 5.8.0-55116800, 2026-07-27, plan §10;
none is guessed):

- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist`.
- *class identity* — `EditorAssetLibrary.load_blueprint_class(path)` +
  `unreal.get_default_object`, cross-recorded against the asset-registry tags
  `ParentClass` / `NativeParentClass` (read via `EditorAssetLibrary
  .find_asset_data(...).get_tag_value(...)`, which is cheaper than loading and
  is the route the plan proved).
- *component walk* — `unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)`.
  It is an **engine** subsystem: `get_editor_subsystem` raises
  `TypeError: Cannot nativize`. Then
  `SubobjectDataBlueprintFunctionLibrary.get_data / get_variable_name /
  get_parent_handle / get_object`.
- *attach parent* — `get_parent_handle` on the `Flashlight` subobject's data.
  `FSubobjectData::GetVariableName` returns the SCS node's variable name for
  authored components and the anchoring property name for native inherited
  ones, which is why the inherited mesh is accepted under **either** its
  property name `Mesh` or its native object name `CharacterMesh0` — the same
  pair the source row names. **The name is necessary, never sufficient**: the
  check additionally requires the parent's component template to be a
  `SkeletalMeshComponent` and to report
  `IsInheritedComponent`/`IsNativeComponent`
  (`SubobjectDataBlueprintFunctionLibrary.h:113-117`), which is what stops a
  submission-authored component *named* `CharacterMesh0` from satisfying
  anti-gaming note #2. Two corroborating reads are recorded in the detail and
  can only add a failure: the `GetAttachParent()` UFUNCTION
  (`SceneComponent.h:700-702` — the `AttachParent`/`AttachSocketName`
  UPROPERTIES are reflection-denied, plan §12.1; `GetAttachSocketName` is the
  wrong accessor because the graded property is the parent component, not a
  socket), and path-name identity against `ACharacter::Mesh` on the hero CDO
  (`Character.h:351`), which is the same UObject the subobject walk sees
  because `K2_GatherSubobjectDataForBlueprint` walks
  `GeneratedClass->GetDefaultObject()` (`SubobjectDataSubsystem.cpp:147-154`).

**Identity is by pre-declared content path and pre-declared subobject name,
never by class.** The two asset paths and the three names (`Body`, `Health`,
`Flashlight`) are fixed by the spec and stated in the prompt; the agent may
subclass, rename the generated class, or reach the outcome by building
`BP_Hero` from scratch rather than by copying, and none of that is penalized.

**Why the parent check accepts subclasses.** The behavior being graded is "it
is a walking, possessable figure that owns an inherited animated body part".
`isinstance(cdo, unreal.Character)` is true for `Character` and for anything
derived from it, which is exactly the set of solutions that deliver the
behavior; class *equality* would fail an agent that derived from the
substrate's own character type while satisfying every observable. The
complementary `source_unchanged_not_character` check uses the same predicate
negated, so "the agent reparented the source instead of the copy" is still
caught.

**Why `saved` is not a separate check.** The source row's check 5 asks for
"compiled clean **and** saved (not dirty)". Dirtiness is not observable to this
layer and does not need to be: the runner grades a file overlay materialized
onto a clean substrate, so unsaved editor state never reaches the grader at
all — an unsaved edit presents as the *baseline* bytes and fails the content
checks. The compile half is asserted directly off the freshly loaded asset.

**Score granularity.** `registry.py:340-346` sets `tests_run`/`tests_passed`
from the per-check counts, so `report.json` already carries `x/13` for this
task. That number is **reported, not gating** — `overall` stays
`all(status == "pass")` (plan §3.2).

## Reference solution metadata

- LOC range: **0** lines of code. The deliverable is one new `.uasset` plus an
  untouched baseline `.uasset`.
- Files touched: 1 created
  (`Content/Tasks/t1-hero-blueprint-copy-with-flashlight/BP_Hero.uasset`), 0
  modified.
- Senior-dev hours: 0.2-0.5 (asset copy, one class-hierarchy change, one
  component added at a specific attach point, one numeric default, compile and
  save — plus verifying the original really is untouched).

## Anti-gaming notes

1. **Copy made, never made walkable.** *Failure mode*: the agent duplicates
   `BP_Source`, hangs the light on it and stops — the copy is still an inert
   object, so nothing "walks". *Defense*: `hero_parent_is_character` fails
   (`HERO_PARENT_NOT_CHARACTER`), and because an inert object owns no inherited
   animated body part, `hero_flashlight_attach_parent_is_mesh` fails too — two
   independent named checks, so a partial fix cannot silently pass.
2. **Light hung anywhere convenient.** *Failure mode*: the agent adds a
   correctly named, correctly configured light but attaches it to the root or
   to the cube `Body`, which is the path of least resistance in every editor
   flow (a newly added component parents to whatever is selected). *Defense*:
   `hero_flashlight_attach_parent_is_mesh` resolves the subobject's *parent
   handle* and requires the inherited mesh
   (`HERO_FLASHLIGHT_ATTACH_PARENT_WRONG`), so "present and correct-looking" is
   not the same as "mounted where asked". The name match alone would be gamed
   by any component the agent simply *called* `CharacterMesh0`, so the check
   also requires that parent to be a skeletal mesh component **and** to be
   inherited/native rather than authored by the submission — a component added
   to `BP_Hero`'s own construction script is neither, whatever it is named.
3. **Original mutated instead of copied.** *Failure mode*: the agent edits
   `BP_Source` in place and renames it, or reparents and lights the source and
   then makes `BP_Hero` a thin copy of the *result*, destroying the template.
   *Defense*: two checks read `BP_Source` independently of `BP_Hero` —
   `source_unchanged_not_character` (`SOURCE_PARENT_CHANGED`) and
   `source_has_no_flashlight` (`SOURCE_HAS_FLASHLIGHT`) — and they run even
   when `BP_Hero` is missing entirely.
4. **Copy gutted / rebuilt from a blank.** *Failure mode*: the agent authors a
   fresh walking-figure asset named `BP_Hero` and never carries the source's
   content across, so the "starts as an exact copy" half is silently dropped.
   *Defense*: `hero_retains_body_component` (`HERO_BODY_COMPONENT_MISSING`) and
   `hero_retains_health_100` (`HERO_HEALTH_NOT_100`). Note that building from
   scratch and *then* reproducing `Body` and `Health = 100` is an accepted
   solution — it satisfies every observable and costs strictly more work; per
   the behavior-only law, wrong-path success is not a defect here.
5. **Default-shaped light.** *Failure mode*: the agent adds an omni light
   rather than a beam, or adds the beam and leaves its brightness at whatever
   the engine gave it. *Defense*: `hero_flashlight_is_cone_light`
   (`HERO_FLASHLIGHT_NOT_CONE`) rejects a non-beam light, and
   `hero_flashlight_intensity_12000` (`HERO_FLASHLIGHT_INTENSITY_WRONG`) is
   pinned to a **non-default** value on purpose: the engine's own default is
   `5000` (`LocalLightComponent.cpp:13`), so the source row's literal `5000`
   would have made this check unfailable. Prose claiming success cannot satisfy
   either check — the verdict is read only from the submitted bytes.

## Hidden invariants

- The two `source_*` checks are not implied by anything in the prompt beyond
  "leave the original alone", and they are evaluated **independently of whether
  `BP_Hero` exists**. An agent that gets the hero perfect by cannibalizing the
  source still fails, and it fails through a differently named assertion than
  any hero-side mistake, so the discrimination matrix can tell the two apart.
- The check denominator is fixed at 13 on every leg, including the empty
  submission. A submission cannot improve its reported `tests_passed/tests_run`
  by making checks unreachable — the crash-shaped "fewer checks ran, so the
  ratio looks better" path is closed by construction.
