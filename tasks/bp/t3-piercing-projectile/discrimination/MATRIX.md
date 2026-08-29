# Discrimination matrix — t3-piercing-projectile

The self-validation oracle: the reference solution must PASS and the empty
leg must FAIL **at the predicted check, via the named substring**. A
wrong-reason FAIL (L1 build failure, a different check, a `0`-check/`error`
L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated —
fix it, or relabel the task for the weaker property it actually tests.

Per the amended checklist §7 (owner decision 2026-08-11) this package ships
**no hand-authored gaming variants**: the automatic reference-PASS /
empty-FAIL legs provide the non-vacuity bit, and the **requirements table**
below is the mandatory soundness artifact. Author a variant only when a
table row exposes a requirement whose defense turns out not to exist.

> **STATUS: TEXT-ONLY (authoring-lane run pending).** No binaries exist yet;
> `../aids/author_reference.py` writes the config half, authors the three
> Blueprints, and self-grades 9/9 against the real introspect before
> harvesting. The SCS-walk and compile-status routes are proven
> (kp-blueprint-actor-audit refgate 2026-08-11/12); the collision getters
> (`get_collision_profile_name` / `get_collision_object_type` /
> `get_collision_response_to_channel` on SCS templates) and the
> `ECC_GAME_TRACE_CHANNEL<N>` enum spelling are THIS task's live spike.

## Parser traps this matrix is written against (inherited from the bp L2I set)

- **ONE parseable row-table.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]`; this file has exactly one table with
  submission rows. The requirements table names none of its columns
  "substring" or "message" and its first cells are requirement prose, so
  `parse_matrix` skips it entirely.
- **Every "Expected substring" cell is a backtick-wrapped literal that
  contains a space or `=`** (`_extract_substrings` substantive-span rule).
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **Substrings are matched against the raw `detail` string inside the
  `CRAFTBENCH-INTROSPECT-JSON` block**, and every cell below is a verbatim
  contiguous span of ONE source literal in
  `tools/verify-single/introspect/t3_piercing_projectile.py` — never a span
  that crosses a printf placeholder or an adjacent-literal seam.
- **ASCII rule:** every expected substring is ASCII-only.
- **Error tokens are distinct from failure tokens.** Every exception path
  emits `PIERCE_PROBE_ERROR` / `SUBOBJECT_*` / `PIERCE_CHECK_UNREACHED` /
  `PIERCE_CHANNEL_ENUM_UNAVAILABLE`, none of which appears in any row
  below — a broken UE API name surfaces as an uncredited FAIL, never as a
  credited named failure.

## Layout (folder-local; agent-writable prefixes only)

- `../reference/Config/DefaultEngine.ini` — the substrate baseline ini
  plus the one `[/Script/Engine.CollisionProfile]` section the task asks
  for (1 channel + 3 preset lines, all inside this spec's `config_allow`).
- `../reference/Content/Tasks/t3-piercing-projectile/` — `BP_Bullet`,
  `BP_PiercableWall`, `BP_NonPiercableWall`. **EMPTY until the
  authoring-lane run**; do not fabricate binaries.
- empty leg — run IMPLICITLY by `cb discriminate` (a throwaway empty dir).
  With no submitted ini the workdir keeps the baseline
  `Config/DefaultEngine.ini`, which carries **zero** collision-profile
  config, so the empty leg is genuinely empty on both graded halves and
  scores `0/9`.

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all 9 checks green (9/9) |
| empty | FAIL | `projectile_channel_defined` | `PIERCE_CHANNEL_COUNT expected=1 got=` | baseline ini has no collision section (got=0); the three actor checks fail `PIERCE_BP_MISSING path=` and both derived checks carry their own named tokens (`0/9`) |

## Requirements table (checklist §7, the mandatory soundness artifact)

One row per requirement in the agent-visible prompt. Every backticked span
in the *verbatim token* column is a contiguous literal in
`tools/verify-single/introspect/t3_piercing_projectile.py`; the check id is
the durable join key if lines drift.

| # | Prompt requirement | Asserted | Enforcing check — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | exactly ONE new custom object channel named `Projectile`, default Block, no other new channels of any kind | fully | `projectile_channel_defined` — `PIERCE_CHANNEL_COUNT expected=1 got=` (count gate; trace channels arrive through the same ini key, so exactly-one IS the no-other-channels gate) / `PIERCE_CHANNEL_BAD ` (name / default / bTraceType / slot) | unconditional (first gate) | which `ECC_GameTraceChannel<N>` slot is used — deliberate, any slot is conforming |
| 2 | a `Bullet` preset: object type `Projectile`, query+physics, `WorldStatic` Block, `Pawn` Ignore | fully | `bullet_preset_defined` — `PIERCE_PRESET_MISSING name=` / `PIERCE_PRESET_BAD name=` (each bad field is spelled out in the same detail) | never (text half is independent of the actors) | `HelpText` / `bCanModify` and responses to channels the prompt does not name — deliberate |
| 3 | a `Piercable` preset: object type `WorldStatic`, response to `Projectile` Overlap | fully | `piercable_preset_defined` — same token family as row 2 | never | same residual as row 2 |
| 4 | a `NonPiercable` preset: object type `WorldStatic`, response to `Projectile` Block | fully | `nonpiercable_preset_defined` — same token family as row 2 (Block may be explicit or the profile default — both are the same semantic and both pass) | never | same residual as row 2 |
| 5 | `BP_Bullet` with a collision-carrying primitive component on the `Bullet` preset, overlap events enabled | fully | `bullet_actor_wired` — `PIERCE_BP_MISSING path=` / `PIERCE_NO_PRIMITIVE_COMPONENT` (backtick-span carries no space but is never a row credit — the credited spans are the other two) / `PIERCE_PROFILE_MISMATCH wanted=` / `PIERCE_OVERLAP_EVENTS_OFF ` | never | which primitive-component class (sphere/capsule/box/mesh) — deliberate, "collision-carrying primitive" is the demand; extra components unconstrained |
| 6 | `BP_PiercableWall` with a static-mesh component on `Piercable`, overlap events enabled | fully | `piercable_wall_wired` — same token family as row 5 | never | which mesh asset the wall renders — deliberate relaxation of the source row's "engine cube" (recorded in task.md provenance) |
| 7 | `BP_NonPiercableWall` with a static-mesh component on `NonPiercable` | fully | `nonpiercable_wall_wired` — same token family as row 5 | never | overlap events on the solid wall are unconstrained (nothing overlaps it by design) |
| 8 | net effect: bullet-vs-piercable = pass-through with overlap, bullet-vs-solid = blocked, pawns never interact | fully, from ENGINE-RESOLVED state | `both_sides_rule_holds` — `PIERCE_BOTH_SIDES_NO_CHANNEL ` / `PIERCE_BOTH_SIDES_COMPONENTS_MISSING ` (prerequisite fan-outs) and the resolved-state detail `pair(piercable)=` / `pair(solid)=` on a polarity miss | checks 1 and 5–7 all green are prerequisites; their rows fan out first | nothing at the response-matrix layer; NO PIE runs (accepted residual below) |
| 9 | all three Blueprints compile cleanly and are saved | fully | `all_three_compile_clean` — `PIERCE_COMPILE_MISSING_ASSETS have=` / `statuses=` on a dirty compile | asset existence (rows 5–7 fan out) | nothing; only on-disk saved assets reach the graded substrate at all |
| 10 | config discipline: nothing but the channel/preset definitions changes | fully, by the SANDBOX not the introspect | not a check id — this spec's two `config_allow` rules license ONLY `+DefaultChannelResponses` and `+Profiles` in `[/Script/Engine.CollisionProfile]`; any other section/file/key change is SANDBOX-REJECT exit 4 (`tools/verify-single/config_lane.py`, e2e-tested) | never (path+semantic gates precede grading) | additional entries under the two licensed keys — and the GRADER's exactly-one channel gate (row 1) catches the one that matters |

Every prompt requirement has an enforcing gate — nothing is unenforced
prose. Rows 5–7's component-class latitude and row 10's licensed-key
latitude are deliberate and argued below.

## Accepted residuals (documented, not defended)

- **No PIE, no simulated flight.** The pass-through/block behavior is
  graded as the engine's resolved response matrices plus the min-rule
  derivation (`both_sides_rule_holds`) — the same computation the physics
  scene consults — not as an observed projectile trajectory. A trajectory
  gate would be an L2 fixture task; this task's scope is the collision
  vocabulary. Recorded, not defended.
- **First-conforming-component semantics.** Each actor check searches the
  SCS walk for A component matching preset(+type); extra components and
  their profiles are unconstrained. Deliberate: the prompt demands the
  wired component exist, not that nothing else does.
- **Root-ness is not graded.** The prompt says the bullet's collision
  component is "the root"; the grader deliberately does not assert SCS
  root identity — root-handle semantics differ across authoring routes
  (native DefaultSceneRoot vs replaced root), and profile+overlap on a
  present primitive is the load-bearing fact. Divergence recorded here and
  in notes.md.
- **Saved-state depth.** "Saved" is enforced by the substrate model (only
  on-disk files exist to the harness); the grader does not separately
  assert package dirtiness.
- **Mechanism-agnostic by basket law**: editor UI, editor scripting,
  direct ini edit + asset authoring, and MCP-authored states are
  indistinguishable to every gate.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t3-piercing-projectile --wip
```

(`--wip` until the reference binaries and this task's first commit land.)
Per-leg fallback while iterating:

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t3-piercing-projectile/task.md \
    --submission tasks/bp/t3-piercing-projectile/reference \
    --ue-root "$UE" --workdir C:\cb\wd\pierce        # expect exit 0
```

The submission carries a `Config/DefaultEngine.ini`, so this task also
exercises the sandbox's config lane on the way in: an out-of-allowlist
change in the reference would exit 4 BEFORE grading — that exit code is a
reference bug, not a grade.

## Status

- Authored 2026-08-12, text-only track. **Never executed against a real
  editor.** Proven lanes reused: SCS walk + compile status
  (kp-blueprint-actor-audit refgate), constant-denominator verdict
  plumbing + `_defang` (wave-3 family). Live spikes owed to the
  authoring-lane run: the three collision getters on SCS templates, the
  `ECC_GAME_TRACE_CHANNEL<N>` enum spelling (multi-spelling probe in the
  grader), and profile resolution from a submitted ini at grade-time boot.
- **Still missing, in order:** (1) the reference ini + binaries
  (`../aids/author_reference.py`); (2) the refgate certificate; (3) the
  empty-FAIL discriminate leg on the next sweep.

> **UPDATE 2026-08-13 (authoring-lane run DONE):** every pending-binary
> statement above is now historical - the reference binaries are committed
> (eb36cfb, pins in the same commit) and `cb refgate` refgated PASS from git HEAD (228 s, 2026-08-12/13). All four live spikes held: the collision getters on SCS templates, the hidden-enum fix (integer cast, EngineTypes.h:1520), profile resolution from the submitted ini at grade-time boot, and the config lane admitting the reference ini on the way in. Self-grade 9/9 (KPIERCE-DONE); both-sides resolved pair(piercable)=ECR_Overlap pair(solid)=ECR_Block. The
> empty-FAIL leg rides the next `cb discriminate` sweep.
