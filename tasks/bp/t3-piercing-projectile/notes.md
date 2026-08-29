# t3-piercing-projectile — verifier-builder notes

port of a collision row from a retired internal task list.
Companion docs: `task.md` (spec + provenance divergences),
`discrimination/MATRIX.md` (oracle + requirements table). This file pins
the reference property-by-property, the aid runbook, and the design
decisions a future editor needs before touching the grader.

## 1. Reference solution, property-by-property

### 1.1 Config half (`reference/Config/DefaultEngine.ini`)

The substrate baseline `DefaultEngine.ini` plus exactly this section (the
canonical copy lives in `aids/author_reference.py::_INI_SECTION` — edit it
THERE; this block is documentation):

```ini
[/Script/Engine.CollisionProfile]
+DefaultChannelResponses=(Channel=ECC_GameTraceChannel1,DefaultResponse=ECR_Block,bTraceType=False,bStaticObject=False,Name="Projectile")
+Profiles=(Name="Bullet",CollisionEnabled=QueryAndPhysics,bCanModify=True,ObjectTypeName="Projectile",CustomResponses=((Channel="Pawn",Response=ECR_Ignore)),HelpText="Piercing projectile body")
+Profiles=(Name="Piercable",CollisionEnabled=QueryAndPhysics,bCanModify=True,ObjectTypeName="WorldStatic",CustomResponses=((Channel="Projectile",Response=ECR_Overlap)),HelpText="Wall a projectile passes through, overlap still fires")
+Profiles=(Name="NonPiercable",CollisionEnabled=QueryAndPhysics,bCanModify=True,ObjectTypeName="WorldStatic",HelpText="Wall that stops projectiles")
```

Notes on the ini shape:

- **Slot 1 is a choice, not a demand.** `ECC_GameTraceChannel1` is the
  first free custom slot in a clean substrate; the grader parses the slot
  index from the submitted text, so ANY slot is conforming (MATRIX row 1
  residual).
- **NonPiercable carries no `CustomResponses`.** UE profile semantics
  default every response to Block; Projectile==Block is the default, and
  the grader's `_profile_response_to` implements exactly that rule — an
  explicit `(Channel="Projectile",Response=ECR_Block)` is equally
  conforming.
- **Both `config_allow` rules cover every line** (`+DefaultChannelResponses`
  and `+Profiles` in `/Script/Engine.CollisionProfile`). The reference must
  never touch another key — an out-of-allowlist line would exit 4 at the
  sandbox and mask the grade (MATRIX "How to run" note).

### 1.2 Asset half (`reference/Content/Tasks/t3-piercing-projectile/`)

| asset | parent | SCS additions | collision |
|---|---|---|---|
| `BP_Bullet` | `Actor` | `SphereComponent` "BulletCollision" | profile `Bullet`, `generate_overlap_events=True` |
| `BP_PiercableWall` | `Actor` | `StaticMeshComponent` "WallMesh", mesh `/Engine/BasicShapes/Cube` | profile `Piercable`, `generate_overlap_events=True` |
| `BP_NonPiercableWall` | `Actor` | `StaticMeshComponent` "WallMesh", mesh `/Engine/BasicShapes/Cube` | profile `NonPiercable`, overlap events off |

Component variable names and the cube mesh are AID choices, not graded
facts (MATRIX rows 5–6 residuals: any primitive class for the bullet, any
mesh for the walls).

## 2. Aid runbook (three phases — the ini MUST precede the editor)

Collision channels/presets are read from `Config/DefaultEngine.ini` at
**engine boot**. Authoring or self-grading in a session without the section
would bake unresolved profiles, so `aids/author_reference.py` fails closed
(`KPIERCE-NEEDS-INI`) unless phase A ran:

```sh
# A. stage the config half into the WORKTREE substrate (script-owned block):
py - <<'PY'
import io, re
src = io.open("tasks/bp/t3-piercing-projectile/aids/author_reference.py",
              encoding="utf-8").read()
section = re.search(r'_INI_SECTION = """\n(.*?)"""', src, re.S).group(1)
p = "UE-projects/ThirdPerson/Config/DefaultEngine.ini"
base = io.open(p, encoding="utf-8-sig").read()
assert "/Script/Engine.CollisionProfile" not in base, "already staged?"
io.open(p, "a", encoding="utf-8", newline="").write("\n" + section)
print("staged")
PY

# B. run the aid on the worktree editor (markers: KPIERCE-*):
UnrealEditor-Cmd.exe <worktree>/UE-projects/ThirdPerson/ThirdPerson.uproject \
  -ExecutePythonScript=<worktree>/tasks/bp/t3-piercing-projectile/aids/author_reference.py \
  -nullrhi -unattended -nosplash -stdout -FullStdOutLogOutput
# expect: KPIERCE-SELFGRADE 9/9 ... KPIERCE-DONE

# C. restore the substrate (the harvest kept the reference copy). This task
#    ships NO baseline asset, so the aid-authored BPs must leave the
#    substrate too (move aside, never rm - the empty leg depends on an
#    empty folder):
git checkout -- UE-projects/ThirdPerson/Config/DefaultEngine.ini
mv UE-projects/ThirdPerson/Content/Tasks/t3-piercing-projectile <scratchpad>/
git status --short UE-projects/ThirdPerson   # must be clean (scratch law)
```

Phase-B fallback: if `add_new_subobject` cannot produce templates
(`KPIERCE-SPELLING … NEEDS-GRAPH-LANE`), author the components through the
MCP editor lane (graph-lane runbook, wave-3 notes) and re-run the aid — it
reuses existing assets (`bp-exists` vector) and still self-grades +
harvests.

## 3. Grader design decisions (`t3_piercing_projectile.py`)

- **Two halves cross-check** (population plan §12.2): definitions from ini
  TEXT (reflection-dead: `UCollisionProfile` is bare `globalconfig`, zero
  UFUNCTIONs), behavior from ENGINE-RESOLVED template state (plain
  `EditAnywhere` + BlueprintCallable getters) at grade-time boot — the
  submitted ini is live in the grading session, so an undefined preset
  cannot resolve.
- **Exactly-one channel gate is the no-other-channels gate**: trace AND
  object channels both arrive as `+DefaultChannelResponses` entries
  (`bTraceType` flag), so `len(entries) == 1` covers the source row's "no new
  trace channels" clause. The source row PROMPT's own "setup the … trace
  channels" bait is dropped from our prompt (task.md provenance).
- **UE struct-literal parsing is first-occurrence-wins** (`_struct_fields`):
  outer fields precede anything nested in `CustomResponses`, and the outer
  fields of interest never appear inside a response tuple.
  `_RE_CUSTOM_RESPONSE` is whitespace-tolerant for hand-edited inis.
- **Profile response resolution** (`_profile_response_to`): default
  `ECR_Block`, `CustomResponses` lists deviations — mirrors
  `FCollisionResponseTemplate` semantics.
- **The min-rule** (`_min_rule`, Ignore < Overlap < Block, weaker wins) is
  the engine's pairwise interaction rule; `both_sides_rule_holds` computes
  it from the located components' resolved responses, never from re-parsed
  text.
- **Root-ness is not graded** (MATRIX residual): root-handle semantics
  differ across authoring routes; profile+overlap on a present primitive is
  the load-bearing fact.
- **Fail-closed token discipline**: `PIERCE_*` failure tokens are matrix
  currency; `PIERCE_PROBE_ERROR` / `SUBOBJECT_*` / `PIERCE_CHECK_UNREACHED`
  are the uncredited error class.

## 4. Live spikes owed to the authoring-lane run

Proven lanes reused as-is: SCS walk + compile-status read
(kp-blueprint-actor-audit refgate 2026-08-11/12), BlueprintFactory +
`AddNewSubobjectParams` (KPBOOT aid), verdict plumbing + `_defang`
(wave-3 family). Owed to THIS task's first live run:

1. `get_collision_profile_name` / `get_collision_object_type` /
   `get_collision_response_to_channel` on **SCS template objects** (the
   BlueprintCallable-on-template pattern worked for socket reads on R6;
   collision getters are untried).
2. The `unreal.CollisionChannel.ECC_GAME_TRACE_CHANNEL<N>` enum spelling —
   the grader probes three spellings and raises its named token if none
   resolves.
3. Profile resolution from a submitted ini at grade-time boot (the
   PostLoad/FixupData re-apply assumption — if a saved component does NOT
   re-resolve its profile on load, `both_sides_rule_holds` will read stale
   authored-state responses; the aid's self-grade inside the ini-staged
   session cannot distinguish this, but the REFGATE run can: it boots a
   fresh workdir from git HEAD, so a resolution failure there fails 5–8
   loudly).
4. `set_collision_profile_name` ON the template during authoring (aid
   fallback: `body_instance` struct-copy write; last resort: MCP lane).

## 5. Provenance extras

- row R8 = source row `t7-piercing-projectile`; the month-long block and
  its inversion are population plan §10.4 → §12.2. The config lane (D4
  write half) landed 2026-07-29: manifest `config_writable` + spec
  `config_allow` + `config_lane.py` ini-diff validation (exit 4),
  e2e-tested in `test_config_lane.py` — whose own test literal IS the
  collision rule this spec declares.
- Substrate divergence (ThirdPerson, not the plan's G6 Template grouping)
  and the two prompt repairs (trace-channel bait dropped; preset/channel
  names floored) are recorded in task.md's provenance section.
- No camera plan (`cameras.json` (the camera-plan lane; not part of this release)): this task authors no level and no
  visual scene — nothing for a review capture to frame. Checklist step 5 is
  N/A by shape, recorded here so its absence is never read as an omission.

## 6. Status

Text-only track, authored 2026-08-12 (spec + grader + MATRIX + aid).
Binaries, refgate certificate, and the discriminate legs pend the
authoring-lane run (runbook §2).
