---
id: kp-config-source-audit
substrate: ThirdPerson
set: python
tier: T2
capability_bucket: Content Integration
category: other
layers: [L1, L2I]
introspect: [kp_config_source_audit.py]
---

# kp-config-source-audit

A `tasks/python/` basket task (outcome-graded editor-scripting work): a
**diagnosis** task. The workspace ships a committed corpus of four
near-identical configuration assets plus one committed wiring artifact that
makes exactly one of them the live source of a stated gameplay value. The
deliverable is ONE plain-text report naming the live asset and its value —
found by **tracing the committed wiring, not by guessing from names** (the
names are deliberately deceptive and anti-correlated with liveness). The
exactness of the demanded answer (an exact project path and an exact stored
number the prompt never states) makes editor scripting the natural route,
but per the basket law **no gate asserts "python was used"** — any route
that produces a truthful report passes identically.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a data-asset config
row. Its cells: capability *"Whether it can find the right data asset
for GAS config in a Lyra project"*; expected outcome *"discovers or infers
AbilitySet_ShooterHero and lists its abilities"*; prompt *"what are the
current default player abilities?"*; substrate *"Lyra Project"*. Full
divergence record: `notes.md` §2. Headlines:

1. **ADAPTED AWAY FROM LYRA.** There is no Lyra substrate and never was
   one on disk (Hard Rule 5; `docs/AUTHORING_TEMPLATE.md` substrate note)
   — `AbilitySet_ShooterHero` does not exist anywhere this harness can
   grade. The row's real capability — *find which committed config asset
   actually drives a gameplay value, against plausible impostors* — is
   preserved by a **verifier-authored corpus + wiring** on `ThirdPerson`:
   four look-alike candidates, one wiring artifact making exactly one of
   them live, decoys referenced by nothing.
2. **"Lists its abilities" becomes "states its value."** The Lyra ability
   list is unreproducible off Lyra; the discriminating act (read the RIGHT
   asset's contents, not a plausible one) is kept as an exact stored
   number the report must echo.
3. **Chat answer becomes a FILE.** The source row grades a conversational
   answer against Aura's own output; this harness grades a plain-text
   artifact at a pre-declared path with a strict disclosed grammar,
   cross-checked against introspected truth (the
   `kp-blueprint-actor-audit-report` idiom).
4. **A corpus-unmodified guard is added.** The corpus and wiring live
   under the agent-writable `Content/Tasks/` prefix (the sandbox cannot
   protect them), and a diagnosis task is trivially gamed by editing the
   evidence — so every committed fact is re-asserted at grade time
   against verifier-owned constants.

> **Note on the behavior-only rule (Hard Rule #2).** Like the other
> asset-deliverable tasks in this basket, the prompt names the concrete
> starting-state paths, asset names, part/slot names and the report
> grammar the verifier keys on — starting-state inputs and the outcome
> contract, per the basket's standing exception. **No engine class name,
> no API name, no editor-operation name appears in the prompt**, and —
> unlike the sibling authoring tasks — the ANSWER (which candidate is
> live, and every stored value) appears in no agent-visible surface at
> all.

## Primary concept

- `ps-data-assets` — Data Assets
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/data-assets-in-unreal-engine)

The load-bearing capability is the source row's: **config-in-assets
literacy** — knowing that a gameplay value lives in a committed
designer-tunable asset, that several plausible carriers can coexist, and
that only a reference trace (what does the live object actually point
at?) identifies the real one. Adjacent concept: `ps-asset-registry` —
Asset Registry
(https://dev.epicgames.com/documentation/en-us/unreal-engine/asset-registry-in-unreal-engine)
— enumeration and reference inspection are the natural tools for the
trace. (The corpus carriers are Blueprint assets rather than literal
`UDataAsset` instances — an authoring-lane constraint recorded in
`notes.md` §3; the graded capability is unchanged.)

## Prompt given to the agent

> The committed folder `Content/Tasks/kp-config-source-audit/` contains two
> things, prepared ahead of time and off-limits to changes:
>
> - `corpus/` — four candidate configuration assets: `Flash_Primary`,
>   `Flash_Current`, `Flash_Archive_2024`, `Flash_Test_DoNotUse`. Each
>   carries exactly one brightness number, stored on its single
>   light-emitting part (named `Glow`). The four look alike on purpose,
>   and their names are deliberately misleading — no name hints at which
>   one is really used.
> - `wiring/` — one rig asset named `BP_DashRig`: the committed object
>   that decides where the dash-flash brightness really comes from. The
>   rig carries a slot named `FlashSlot` that produces exactly ONE of the
>   four candidates when the flash fires; the candidate held in that slot
>   is the live source. The other three are referenced by nothing.
>
> Work out — by tracing the committed wiring, not by guessing from names
> — which candidate is live and what brightness number it stores, then
> write a plain-text report at
> `Content/Tasks/kp-config-source-audit/reports/config.txt`. The report
> consists of exactly these two lines (blank lines are ignored; the two
> lines may appear in either order; values contain no spaces):
>
> ```text
> source asset=/Game/Tasks/kp-config-source-audit/corpus/<candidate-name>
> value brightness=<number>
> ```
>
> `<candidate-name>` is the name of the live candidate and `<number>` is
> the brightness stored in that candidate, written as a plain number.
> Both lines are checked against the project's real state, not against
> this brief.
>
> Do not modify, move, rename, replace, or delete the candidates or the
> rig in any way, and do not add anything to the `corpus/` folder. The
> verifier re-reads every committed value and the rig's slot against its
> own records; any difference fails the task regardless of what the
> report says.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-config-source-audit/` (verifier-authored, committed as
substrate baseline; built by the authoring-lane aid — see `notes.md` §5):

- `corpus/Flash_Primary.uasset`, `corpus/Flash_Current.uasset`,
  `corpus/Flash_Archive_2024.uasset`, `corpus/Flash_Test_DoNotUse.uasset`
  — four look-alike config carriers, each a placeable-object class whose
  single light part `Glow` stores one brightness value. Exactly one is
  live; three are decoys referenced by nothing. Which is which — and
  every stored value — is verifier-owned and appears in no agent-visible
  file.
- `wiring/BP_DashRig.uasset` — the one wiring artifact: its `FlashSlot`
  holds exactly one corpus candidate's class, making that candidate the
  live source.

These files sit inside the agent-writable Content carve-out of the
`ThirdPerson` substrate (`UE-projects/ThirdPerson/AGENT_WRITABLE.json`
lists `Content/Tasks/` under `writable` and `asset_writable`), so the
sandbox cannot reject an edit to them — the L2I corpus-unmodified guard
is what enforces the prompt's do-not-touch pledge.

Files that **do not exist** (the agent must create exactly one):

- `Content/Tasks/kp-config-source-audit/reports/config.txt`

Out of scope / not needed:

- No C++ is required or expected; no level or map is involved.
  `Content/Maps/` and the stock content folders are deny-listed.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is a static property of
saved editor state (asset structure, one text file) read by
verifier-owned editor-Python reflection. L2 is deliberately not declared:
nothing evolves over time and no PIE world is needed. Nothing asserts
*how* the report was produced (basket law: outcome-graded, no "python was
used" gate).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is a single text file, so L1 is a precondition (the
project must load cleanly), never a correctness signal.

### L2I — Corpus-unmodified guard + report cross-check

The verifier-owned script
`tools/verify-single/introspect/kp_config_source_audit.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block with **exactly 12
named checks on every leg** (constant denominator). PASS requires all 12.

Group 1a — the corpus guard (5 checks; asset-fact assertions on every
corpus file, each pinned to verifier-owned constants):

```text
corpus_set_exact          the corpus folder enumerates EXACTLY the four
                          pre-declared assets (additions and removals both
                          fail: CORPUS_SET_CHANGED found=)
corpus_primary_intact     Flash_Primary exists, its part Glow is a
corpus_current_intact     point-source light part (subclass-tolerant,
corpus_archive_intact     tri-state probe), and its stored brightness
corpus_testflash_intact   equals the pinned constant within 1e-3
                          (CORPUS_ASSET_MISSING path= /
                           CORPUS_MODIFIED_PARTS asset= /
                           CORPUS_MODIFIED_PART_TYPE asset= /
                           CORPUS_MODIFIED_VALUE asset=)
```

Group 1b — the wiring guard (2 checks):

```text
wiring_rig_present        wiring/BP_DashRig resolves
                          (WIRING_RIG_MISSING path=)
wiring_slot_intact        the slot FlashSlot exists on the rig and its
                          held class is exactly the pinned live corpus
                          class (CORPUS_MODIFIED_WIRING names= /
                          CORPUS_MODIFIED_WIRING_CLASS slot_class=)
```

Group 2 — the report (5 checks):

```text
report_file_present         Content/Tasks/<id>/reports/config.txt exists
                            (CONFIG_REPORT_MISSING path=)
report_grammar_parses       exactly one source line + one value line in
                            the two disclosed shapes, nothing else
                            (CONFIG_GRAMMAR_BAD line=)
report_source_is_live_asset the reported path equals the pinned live
                            asset path (after the one disclosed
                            normalization: /pkg/Name.Name -> /pkg/Name)
                            (CONFIG_SOURCE_WRONG reported=)
report_value_is_live_value  |reported - pinned live value| <= 1e-3
                            (CONFIG_VALUE_WRONG reported=)
report_agrees_with_wiring   a FRESH live trace (slot class -> corpus
                            asset -> stored brightness) must match the
                            report on both fields
                            (CONFIG_WIRING_DISAGREES reported_asset=)
```

**The gold-leak defense.** Every expected value (four names, four
brightness values, the live asset path, the live generated-class path,
the part and slot names) is **pinned in the verifier script's
constants**. Nothing expected is read from anything the agent can write;
the live-wiring cross-check only ever adds "the report must tell the
truth about what is actually wired".

**Fail-closed properties** (set convention):

- A missing/empty submission fails all 5 report checks with the named
  `CONFIG_REPORT_MISSING path=` root cause fanned out. The 7 guard checks
  PASS on the empty leg by design (the baseline is intact), so the empty
  submission scores 7/12 and FAILs overall — never a vacuous pass, never
  a shrunken denominator.
- Every exactness assertion is conjoined with the positive read that
  produced it; a failed prerequisite fans its own token into dependents.
- Error tokens (`*_PROBE_ERROR`, `*_READ_ERROR`, `*_WALK_ERROR`,
  `*_ABORTED`, `CHECK_NOT_EVALUATED`) are disjoint from graded failure
  tokens and appear in no MATRIX row, so a broken UE API can never be
  credited as a named failure.
- All details are ASCII-only (the cp1252 log read-back trap).

**Known-risk reads, all fail-closed** (full list + calibration plan in
`notes.md` §4): the SCS walk and template property reads are proven by
this basket's sibling tasks; the `child_actor_class` template read and
`list_assets` enumeration shape are precedented-but-unproven for this
exact combination. None can produce a false PASS — only an uncreditable
FAIL the reference gate surfaces before any agent sees the task.

**Score granularity.** `registry.py` reports `tests_passed/tests_run`,
so `report.json` carries `x/12`, while `overall` stays `all(pass)`.

## Reference solution metadata

- LOC range: **0** lines of module code. The deliverable is one 2-line
  text file; the natural route is a throwaway editor-python script of
  roughly 20-60 lines (enumerate the corpus, open the rig, read the slot,
  read the winner's value, write the file) that is not itself graded or
  submitted.
- Files touched: 1 created (`reports/config.txt`), 0 modified.
- Senior-dev hours: 1.0-2.5 — trivial once the trace idea is seen, but
  finding where a class-holding slot's reference lives (headless, no
  visual graph), resisting the name bait, and matching the exact report
  grammar is genuine T2 "one non-obvious decision" work: the non-obvious
  decision is *trust the wiring, not the names*.

## Anti-gaming notes

1. **Guess by name / plausibility.** *Failure mode*: the agent picks
   `Flash_Current` or `Flash_Primary` because the name sounds live —
   exactly what the source row's "infers AbilitySet_ShooterHero" grading
   would have rewarded. *Defense*: the live pick is name-anti-correlated
   (the "archive" is live) and `report_source_is_live_asset` pins the
   exact path (`CONFIG_SOURCE_WRONG reported=`); the decoys' values are
   all distinct, so the paired value line fails too
   (`CONFIG_VALUE_WRONG reported=`). Pointer:
   `kp_config_source_audit.py::_report_checks`. Residual: a 1-in-4 blind
   guess (see Accepted residuals).
2. **Edit the evidence to match the report.** *Failure mode*: the agent
   rewires `FlashSlot` to their guessed candidate, or edits a decoy's
   stored value, making a wrong report "true". *Defense*: the corpus
   guard re-asserts every committed fact against verifier-owned pins —
   `wiring_slot_intact` fails a rewire (`CORPUS_MODIFIED_WIRING_CLASS
   slot_class=`), the per-asset gates fail a value edit
   (`CORPUS_MODIFIED_VALUE asset=`), and `corpus_set_exact` fails a
   planted or removed candidate (`CORPUS_SET_CHANGED found=`). Pointer:
   `kp_config_source_audit.py::_corpus_checks` / `::_wiring_checks`.
3. **Transcribe the answer from the brief.** *Failure mode*: report
   written from prompt text without opening the editor. *Defense*:
   impossible by construction — neither the live candidate nor any
   brightness value appears in the prompt, the workspace docs, or any
   agent-visible file; the only place the answer exists is inside the
   committed binaries. The grammar's single-source rule blocks
   "enumerate all four paths" hedging (`CONFIG_GRAMMAR_BAD line=`).
   Pointer: `kp_config_source_audit.py::_parse_report` plus the pinned
   constants block.
4. **Right path, made-up number (or vice versa).** *Failure mode*: the
   agent traces the wiring correctly but rounds, invents, or copies a
   decoy's value — a report that is half true. *Defense*: both fields
   gate independently against the pins AND jointly against the fresh
   live trace: `report_value_is_live_value` (`CONFIG_VALUE_WRONG
   reported=`) and `report_agrees_with_wiring`
   (`CONFIG_WIRING_DISAGREES reported_asset=`) both fail. Pointer:
   `kp_config_source_audit.py::_report_checks` (live-wiring cross-check).
5. **Denominator gaming.** *Failure mode*: a submission that makes
   checks unreachable (corrupt report encoding, deleted corpus) to
   improve its reported ratio. *Defense*: the check list has a constant
   length of 12 on every leg; unreadable inputs fail their checks with
   error or root-cause tokens fanned into dependents, never a skip.
   Pointer: `kp_config_source_audit.py::main` (`CHECK_IDS` assembly +
   fanout idiom).

## Hidden invariants

- **The check denominator is fixed at 12 on every leg** (empty
  submission: 7/12, overall FAIL via `report_file_present`).
- **Every pinned corpus value excludes the untouched default**: a fresh
  point-source light part stores 5000.0; the four pinned values are
  1450 / 950 / 725 / 1200, so a freshly authored impostor asset can
  never satisfy a value gate by accident, and a decoy value can never
  equal the live value (all four are distinct).
- **The wiring guard and the wiring cross-check are separate checks on
  purpose**: a rewired slot fails `wiring_slot_intact` against the pin
  even when the report honestly describes the rewired state (and the
  pinned source/value checks fail such a report too).
