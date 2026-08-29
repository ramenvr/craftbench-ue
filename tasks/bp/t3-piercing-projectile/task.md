---
id: t3-piercing-projectile
substrate: ThirdPerson
set: bp
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2I]
introspect: [t3_piercing_projectile.py]
config_allow: ["Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile :: +DefaultChannelResponses", "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile :: +Profiles"]
---

# t3-piercing-projectile

A `bp`-basket task and the **first real consumer of the semantic config
lane**: the deliverable is a project-wide collision vocabulary (one custom
object channel, three presets — written into `Config/DefaultEngine.ini`
under the two `config_allow` rules above) plus three wired-up Blueprint
actors that use it. Graded outcome-only by a deterministic verifier-owned
introspect script; any authoring route (editor UI, editor scripting, direct
ini edit + asset authoring) earns the same PASS.

### Provenance and deliberate divergences from the source row

Ported from a retired internal task list: a collision row, parked for a month
as "the one row with a missing read route" until that read was inverted: the
*definitions* half (channels + presets) is dead through reflection but readable
as config text by the verifier, and the *derived behavior* half (per-component
`BodyInstance` state) is plain `EditAnywhere` reflection.

Divergences from the source row, each deliberate:

- **Substrate: `ThirdPerson`, not the plan's G6 "CraftBenchTemplate"
  grouping.** The semantic config lane (manifest `config_writable` +
  spec `config_allow` + ini-diff validation, `tools/verify-single/
  config_lane.py`) landed on ThirdPerson 2026-07-29 and is e2e-tested
  against ThirdPerson's real `AGENT_WRITABLE.json`; the Template manifest
  still carries the blanket `Config/` deny. Porting the lane to Template is
  real manifest surgery with substrate-wide blast radius — not spent here.
  Both substrates' baseline `DefaultEngine.ini` carry **zero**
  `[/Script/Engine.CollisionProfile]` config, so the task content is
  identical.
- **The source row prompt's "trace channels" wording is dropped.** The source row's
  own verification cell demands *no new trace channels*; its prompt asking
  the agent to "setup the object types, trace channels, and collision
  presets" would bait a conforming agent into a graded FAIL. The prompt
  below asks for exactly one new **object** channel and says no other new
  channels of any kind.
- **Preset and channel names are prompt-floored.** The source row prompt names
  only the three Blueprints; its verification gates on preset names
  `Bullet`/`Piercable`/`NonPiercable` and channel name `Projectile`. A
  name the grader demands must be a name the prompt states (the glide-v2
  disclosure law), so all four names are in the prompt.
- **The "engine cube" mesh identity in the source row's checks 7-8 is relaxed** to
  "a static-mesh component": which mesh asset a wall renders is not
  load-bearing for collision semantics, and gating on one engine asset
  path would fail visually-identical conforming solves.

> **Note on the behavior-only rule (Hard Rule #2).** The prompt names the
> deliverable artifacts (three Blueprint actor names, one channel name,
> three preset names — workspace outputs, the precedented exception) and
> the graded collision vocabulary itself (object channel, preset, Block /
> Overlap / Ignore, `WorldStatic`, `Pawn`, query/physics). That vocabulary
> is the task's **subject matter** — the engine-level language any
> implementation must speak, exactly like gameplay-tag names in the gp
> tasks — not an implementation hint. What stays undisclosed: where
> channel/preset definitions live (which config file, which section, which
> keys), every authoring route, and every verifier read route.

## Primary concept

- `collision-overview` — Collision
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine)

The load-bearing capability is **project collision-vocabulary design**:
defining a custom object channel and presets so that pairwise interaction
(the engine's both-sides rule — the weaker of the two responses wins) yields
pass-through-with-overlap against one wall class and hard blocking against
the other. Adjacent (not primary): `collision-response-reference` —
Collision Response Reference
(https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-response-reference-in-unreal-engine),
the response-matrix semantics the derived checks exercise.

## Prompt given to the agent

> Your project needs the collision setup for a piercing projectile: bullets
> that pass through some walls (but still register the hit) and are stopped
> by others.
>
> - Define **exactly one** new custom **object** channel named
>   `Projectile`, whose default interaction with everything is Block. Do
>   not define any other new channel of any kind.
> - Define three new collision presets:
>   - `Bullet` — for the projectile itself. Its object type is
>     `Projectile`; it collides for both queries and physics; it is
>     stopped by static world geometry (`WorldStatic` = Block) and ignores
>     pawns entirely (`Pawn` = Ignore).
>   - `Piercable` — for pass-through walls. Object type `WorldStatic`;
>     its response to `Projectile` is Overlap, so a bullet passes through
>     while the touch still registers.
>   - `NonPiercable` — for solid walls. Object type `WorldStatic`; its
>     response to `Projectile` is Block.
> - Create three Blueprint actors in
>   `Content/Tasks/t3-piercing-projectile/`, using those presets:
>   - `BP_Bullet` — an actor whose root is a collision-carrying primitive
>     component set to the `Bullet` preset, with overlap events enabled.
>   - `BP_PiercableWall` — an actor with a static-mesh wall component set
>     to the `Piercable` preset, with overlap events enabled (the
>     pass-through must be observable).
>   - `BP_NonPiercableWall` — an actor with a static-mesh wall component
>     set to the `NonPiercable` preset.
>
> All three Blueprints must compile cleanly and be saved. Assume both wall
> types are `WorldStatic` objects. Net effect: a `Bullet` meeting a
> `Piercable` wall overlaps (passes through, both sides notified); the same
> bullet meeting a `NonPiercable` wall is blocked; pawns and bullets never
> interact.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t3-piercing-projectile/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate.

Config state the agent starts from:

- `Config/DefaultEngine.ini` exists and contains **no**
  `[/Script/Engine.CollisionProfile]` section — no custom channels, no
  custom presets. The file is `config_writable` in the substrate manifest,
  and this spec's `config_allow` rules license exactly two kinds of
  change: new channel definitions and new preset definitions in that
  section. **Any other config change — another section, another file, a
  removal — is sandbox-rejected (exit 4)**, the config lane's fail-closed
  default.

Files that **do not exist** (the agent must create):

- The three Blueprint actors under `Content/Tasks/t3-piercing-projectile/`
  named in the prompt (names are graded — they are the deliverable
  contract).

Out of scope / not needed:

- No C++ is required or expected. No level, no placement, no PIE: the
  graded surface is the config text plus the three saved assets'
  engine-resolved collision state.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded fact is either static config text
(the definitions half — dead through reflection, population plan §12.2) or
a static engine-resolved property of the three saved assets (the behavior
half — resolved by the editor **from the submitted config** at grade-time
boot). Nothing is observed over time, so L2 is not declared; no rendering
assertion, so L3 is not declared.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content+config-only, so L1 is a precondition (the project
must load with the submitted ini), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/t3_piercing_projectile.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block with **exactly 9 named
checks on every leg** (constant denominator). PASS requires all 9:

```text
projectile_channel_defined     Config/DefaultEngine.ini has EXACTLY ONE
                               +DefaultChannelResponses entry; it is an
                               object channel (bTraceType absent-or-False),
                               Name="Projectile", DefaultResponse=ECR_Block
bullet_preset_defined          a +Profiles entry Name="Bullet":
                               ObjectTypeName="Projectile",
                               CollisionEnabled=QueryAndPhysics,
                               resolved WorldStatic response Block,
                               resolved Pawn response Ignore
piercable_preset_defined       a +Profiles entry Name="Piercable":
                               ObjectTypeName="WorldStatic", resolved
                               response to the Projectile channel Overlap
nonpiercable_preset_defined    a +Profiles entry Name="NonPiercable":
                               ObjectTypeName="WorldStatic", resolved
                               response to the Projectile channel Block
both_sides_rule_holds          from ENGINE-RESOLVED component state (not
                               re-parsed text): min-rule(bullet vs
                               piercable wall) == Overlap AND min-rule(
                               bullet vs non-piercable wall) == Block
bullet_actor_wired             BP_Bullet resolves; its SCS carries a
                               primitive component whose
                               collision_profile_name == "Bullet" and
                               generate_overlap_events == True
piercable_wall_wired           BP_PiercableWall resolves; a static-mesh
                               component with collision_profile_name ==
                               "Piercable" and generate_overlap_events
                               == True
nonpiercable_wall_wired        BP_NonPiercableWall resolves; a static-mesh
                               component with collision_profile_name ==
                               "NonPiercable"
all_three_compile_clean        each Blueprint's compile status reads
                               up-to-date after a verifier-triggered
                               compile; all three saved
```

**The definitions/behavior cross-check (the anti-gaming spine).** Checks
1–4 parse the submitted ini text with UE-ini semantics (profile responses
default to Block; `CustomResponses` lists deviations). Checks 5–8 read the
engine's **resolved** state at grade time: the grader boots with the
submitted ini, parses the channel's `ECC_GameTraceChannel<N>` index from
the text, then reads each component template's
`get_collision_response_to_channel`, `get_collision_object_type`,
`collision_profile_name` and `generate_overlap_events`. A text-only
submission (ini right, Blueprints on default profiles) dies at 6–8; a
reflection-only submission (components hand-set, presets never defined)
dies at 2–4 **and** at 5 — an unresolvable profile leaves the component's
response container at defaults, so the min-rule computes Block/Block.

**Read routes** (each wrapped, multi-spelling, fail-closed):

- *ini text* — plain file read of the workdir `Config/DefaultEngine.ini`;
  section/entry parsing mirrors `config_lane.parse_ue_ini` semantics
  (array `+` prefixes part of the key, duplicate keys preserved).
- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist` on the
  three pre-declared content paths; never asset-name scanning.
- *SCS walk* — the proven `SubobjectDataSubsystem` route
  (`kp_blueprint_actor_audit_report` precedent); component identity by
  `isinstance` (`PrimitiveComponent` / `StaticMeshComponent`),
  subclass-tolerant, tri-state.
- *resolved collision state* — `get_collision_object_type` /
  `get_collision_response_to_channel` (BlueprintCallable, live on
  template objects) against `unreal.CollisionChannel.ECC_GAME_TRACE_CHANNEL<N>`
  with `<N>` taken from the submitted ini, plus `ECC_WORLD_STATIC` /
  `ECC_PAWN` for the bullet's fixed rows.
- *compile status* — `unreal.BlueprintEditorLibrary.compile_blueprint`
  then the blueprint's reflected status property, up-to-date-or-fail.

**Every graded fact excludes the value an untouched or lazy delivery gets
for free** (the dead-gate audit):

| gate | free/untouched value | graded demand | free value inside the gate? |
|---|---|---|---|
| channel definition | zero `+DefaultChannelResponses` entries in baseline | exactly one, named, object-type, Block-default | **no** |
| preset definitions | zero `+Profiles` entries in baseline | three, each with named object type + responses | **no** |
| both-sides rule | default components: Block/Block both pairs | Overlap for the piercable pair AND Block for the other | **no** (all-Block fails the Overlap half) |
| component profiles | `BlockAll`-family defaults on fresh components | the three named custom presets | **no** |
| overlap events | `generate_overlap_events` False on fresh static-mesh components | True on bullet + piercable wall | **no** |
| compile status | vacuously true only if assets exist | assets must exist first (existence gates 6–8) | **no** |

**Score granularity.** `report.json` carries `x/9`; `overall` stays
`all(status == "pass")`.

## Reference solution metadata

- LOC range: **0** shipped lines of code; the config half is ~6 ini lines.
  The natural route is the editor's collision settings surface (or a
  direct ini edit) plus three short Blueprint-authoring steps.
- Files touched: `Config/DefaultEngine.ini` (one new section, ~6 lines) +
  3 created `.uasset`.
- Senior-dev hours: 0.5–1.0. The T3 content is the *vocabulary design* —
  knowing definitions and per-component wiring are two halves and that the
  both-sides rule derives the observable behavior — not volume.

## Anti-gaming notes

Per the amended checklist §7 (2026-08-11) the discrimination package ships
no hand-authored gaming variants; the requirements table in
`discrimination/MATRIX.md` is the soundness artifact. The failure modes it
is written against:

1. **Empty or partial delivery.** A missing ini section fails 1–4; missing
   Blueprints fail 6–8 by existence; the constant 9-check denominator
   scores unreachable checks as failures.
2. **Text-only config, default components.** Presets defined, Blueprints
   never wired: dies at `bullet_actor_wired` / `piercable_wall_wired` /
   `nonpiercable_wall_wired` (profile-name mismatch).
3. **Hand-set responses without presets.** Components set to a custom
   profile with matching responses but no ini definitions: dies at 2–4
   (text) and at 6–8 (profile-name mismatch), and an unresolvable profile
   leaves default response containers, so `both_sides_rule_holds` computes
   Block/Block.
4. **Config smuggling, both flavors.** *Inside the allowlist*: extra
   `+DefaultChannelResponses` entries (e.g. a trace channel "to be safe")
   are admitted by the lane but fail `projectile_channel_defined`'s
   exactly-one gate — the GRADER holds that line. *Outside it*: any change
   beyond the two allowed keys (another section, another file, `-Profiles`
   removals, `+EditProfiles` engine-preset edits) is **sandbox-rejected
   exit 4** before grading — the config lane's fail-closed contract,
   e2e-tested in `test_config_lane.py`.
5. **Wrong response polarity.** Piercable set to Block (or NonPiercable to
   Overlap) passes definitions-presence but fails its named preset check
   and `both_sides_rule_holds`.

## Discrimination

`discrimination/MATRIX.md` — reference-PASS / empty-FAIL legs plus the
mandatory requirements table, each requirement joined to its named check
and verbatim failure token.
