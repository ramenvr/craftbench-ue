# kp-routine-usage-search — authoring notes

Wave-3 port of an unbuilt source row into the `tasks/python/` basket
(outcome-graded editor scripting; the deliverable is a text report graded
by the deterministic L2I lane; no gate asserts "python was used").

## 1. Provenance (source row)

- **Source**: an earlier internal task list (not shipped) — a usage-search
  row. Prompt: *"Which blueprints use
  `UMyUtilityLibrary::GetBlueprintComponent`?"*; starting assets: *"C++
  function library UMyUtilityLibrary. A blueprint that references one of
  its functions."*
- **Plan history**: the import plan filed this row and its neighbours as
  "answer-shaped, doesn't fit the overlay-and-grade verifier". That obstacle
  is now **dissolved**, not worked around: the strict-grammar report
  CROSS-CHECK pattern (`kp_blueprint_actor_audit_report.py`, refgate-proven)
  turns an answer into a graded text artifact whose every line is checked
  against verifier-owned constants. This task is the first such row to ride
  that unlock.
- **Id scheme**: `kp-` is the python-basket family prefix; the source row's
  `t11-` is a row index and is dropped. Substring audit: `kp-routine-usage-search`
  is not a substring of any other task id and contains none.

## 2. Divergences from the source row (full record)

| # | source row | this task | why |
|---|---|---|---|
| 1 | free-text answer to a question | strict-grammar report file at `Content/Tasks/<id>/reports/usage.txt` | O1: answers are not gradable; text artifacts with disclosed grammar + constant cross-check are (kp-audit precedent) |
| 2 | ONE referencing blueprint | a FOUR-entry corpus: direct caller, inheriting child, sibling-routine caller, name-only decoy | with one referencer, all-yes / name-grep / dependency-scan are indistinguishable from real search; this corpus makes each naive strategy wrong somewhere (see §3) |
| 3 | `UMyUtilityLibrary::GetBlueprintComponent` | `EvalUtilityLibrary::ComputeChecksum` (+ `FormatLabel`, `ClampScore`) | the source row symbol leaks mechanism vocabulary ("Blueprint", "Component") into an agent-visible identifier; replacements are behavior-named |
| 4 | unstated asset paths | `/Game/Tasks/<id>/corpus/` + repo-convention report path | writable-prefix law (same re-homing as every kp task) |
| 5 | implicit "don't cheat" | an explicit corpus-unmodified guard (pinned per-file sha256 + exact dir listing + registry existence) and a library-source guard | the corpus is inside the agent-writable content root, so "search the targets" is only meaningful if editing the targets is a named FAIL; disclosed verbatim in the prompt |

## 3. Design decisions + THE VERIFIER-OWNED CONSTANTS TABLE

**The central idea: truth is pinned at authoring time, never recomputed at
grade time.** The grader does zero graph reflection (no UbergraphPages, no
pin reads — both protected on 5.8); it only proves the corpus is still the
authored corpus (hashes) and that the report tells the pinned truth. That
is what makes the task gradable headless with stock python, and it is why
the corpus-unmodified guard is load-bearing rather than decorative:
**editing the targets to match the report can never move the truth.**

The authoring-time truth the introspect embeds
(`tools/verify-single/introspect/kp_routine_usage_search.py`):

| constant | value | notes |
|---|---|---|
| `STATED_FUNCTION` | `ComputeChecksum` | the audited routine |
| library | `EvalUtilityLibrary` (`Source/ThirdPerson/Tasks/<id>/`) | 3 BlueprintCallable statics: `ComputeChecksum`, `FormatLabel`, `ClampScore` |
| `CORPUS_TRUTH` | `BP_North=yes` | DIRECT call wired into its begin-of-play event (MCP graph lane) |
| | `BP_East=yes` | child of `BP_North`, no logic of its own — the INDIRECT route; its own package never mentions the routine |
| | `BP_South=no` | calls sibling `FormatLabel` — same library, different routine |
| | `BP_West=no` | carries `ComputeChecksum` as an FName tag on its CDO — name present, no library tie |
| corpus package dir | `/Game/Tasks/kp-routine-usage-search/corpus` | 4 assets, exactly |
| report path | `Content/Tasks/kp-routine-usage-search/reports/usage.txt` | grammar: one `function name=` line + four `entry name=... references=yes|no` lines |
| `CORPUS_SHA256` | **SENTINEL — unpinned** | pin from the aid's `KPUSAGE-HASH` lines in the SAME commit as the binaries; fails closed (uncreditable `USAGE_CORPUS_HASH_UNPINNED`) until then |
| `LIBRARY_SHA256` `.h` | `d35e77b38540f35738fc6012999bec43438e9081cb137c8d0236ea6de187eb26` | CR-stripped sha256 (git eol-proof); pinned now, sources authored in this change-set |
| `LIBRARY_SHA256` `.cpp` | `6c5f3bf548e1640a603e4a9260049262e1e20fc386c459619c60289b5f0d5e86` | ditto |
| `EXPECTED_ENTRY_COUNT` | 4 | coverage set equality |

**Why each corpus entry exists** (the discrimination-by-construction
column — every naive strategy fails at least one row):

| strategy | North | East | South | West | verdict |
|---|---|---|---|---|---|
| truth | yes | yes | no | no | — |
| all-yes | ok | ok | WRONG | WRONG | fails |
| all-no | WRONG | WRONG | ok | ok | fails |
| per-file name grep | ok | WRONG (no name in own file) | ok | WRONG (tag hit) | fails |
| library-dependency scan | ok | ok (via parent) | WRONG (depends on the library) | ok | fails |
| honest search (name+library scan up the parent chain, or graph/reference inspection) | ok | ok | ok | ok | passes |

Other decisions:

- **No components, no member variables, no sockets anywhere in the
  corpus** — the only python-unauthorable steps are the two K2 call nodes,
  which are exactly the two-phase MCP-graph-lane handoff the aid enforces
  (`KPUSAGE-NEEDS-GRAPH-LANE`). Everything else is BlueprintFactory +
  property defaults (the West tag), all proven lanes.
- **The decoy is an FName tag, not a string variable** — tag defaults are
  plain CDO property wiring (no `add_member_variable`, which was the one
  unproven step of the kp-audit aid), and an FName lands in the package
  name table so a byte/name grep hits it just like a real call's function
  name. Structurally-minded inspection sees instantly that it is a tag.
- **Single-literal token heads** (MATRIX-oracle law): every graded
  `TOKEN key=` head lives in one contiguous source literal; the one
  repeated grammar template is a module constant (`_GRAMMAR_BAD`).
  Proven offline: all 12 graded heads grep.
- **Guard checks are four independent probes** (registry, disk listing,
  raw hashes, source hashes) so one broken API degrades to one failed
  check, and a genuine deletion is caught by two distinct graded tokens.
- **The empty leg passes the guard** (baseline intact) and fails 4/9 via
  `USAGE_REPORT_MISSING path=` fanned across the five report checks —
  the named-assertion empty-FAIL the smoke-test contract demands.
- **cameras.json not authored**: report-only deliverable, no scene, no map
  — nothing for any capture surface to film (same call as the kp-audit
  task pre-binaries; revisit only if a preview surface ever wants a shot
  of the corpus).

## 4. Calibration TODOs (authoring-lane editor session + graph-lane session)

The aid (`aids/author_reference.py`) prints `KPUSAGE-SPELLING` /
`KPUSAGE-HASH` / `KPUSAGE-VERDICT` lines to settle these; record winners
here after the runs:

- [ ] **Phase 1 run**: corpus creation via BlueprintFactory — confirm
      `parent_class` spelling on the factory, and that parenting `BP_East`
      to `BP_North`'s GENERATED class works through the factory (the one
      unproven-but-precedented step of this aid; if it refuses, the
      fallback is `BlueprintEditorLibrary.reparent_blueprint`, and failing
      that the MCP lane's create-with-parent).
- [ ] **West tag on CDO**: `tags` spelling + persistence through
      compile/save/fresh-load (read-back is in the aid; confirm in a fresh
      editor).
- [ ] **Graph-lane session** (MCP, not stock python): wire
      `EvalUtilityLibrary.ComputeChecksum` into `BP_North`'s begin-of-play
      exec chain and `EvalUtilityLibrary.FormatLabel` into `BP_South`'s;
      compile + save both; confirm with `review_blueprint` that the calls
      are EXECUTED (on the exec chain), not floating — the aid's byte-scan
      proves presence, not connectivity (risk 2).
- [ ] **Phase 2 run**: byte-scan invariants all hold on the saved packages
      (in particular: `BP_East` clean of all three names, `BP_South` clean
      of `ComputeChecksum`); derived verdicts print as
      `yes/yes/no/no` with routes `direct/inherited/none/none`; self-grade
      9/9; report harvested.
- [ ] **PIN THE DIGESTS**: copy the four `KPUSAGE-HASH` lines into
      `CORPUS_SHA256` (replacing `HASH_UNPINNED`) in the SAME commit that
      adds the corpus binaries. RE-PIN LAW: any future corpus
      regeneration re-pins digests AND re-verifies `CORPUS_TRUTH` and the
      §3 strategy table in the same change — never separately.
- [ ] **Registry freshness under `-nullrhi`**: confirm
      `does_asset_exist` sees the four corpus assets in the graded
      workdir without an explicit asset-registry wait (the guard is
      three-probe so a registry lag would show as exactly one failed
      check — but it must not).
- [ ] **`cb lint --task python/kp-routine-usage-search`** — first gate
      after this change-set lands (basket tooling assumptions were flushed
      by the first python task; expect clean, verify anyway).
- [ ] **Repo-count edits** — CATALOG row + inventory count claims when
      this task lands (imported-set precedent).
- [ ] Then: `cb discriminate --wip` (reference PASS + empty FAIL) →
      commit → `cb refgate python/kp-routine-usage-search` → the close.

## 5. Reference + corpus binaries status

**EMPTY BY DESIGN in this change-set.** This track cannot run UE, so:

- `reference/` does not exist yet (not even as a directory) — it will hold
  ONLY `Content/Tasks/<id>/reports/usage.txt` after the aid harvests.
- `UE-projects/ThirdPerson/Content/Tasks/<id>/corpus/` does not exist
  yet — the four `.uasset` baselines are built by the aid (phase 1) + the
  MCP graph lane, then committed as SUBSTRATE baseline (they are inputs,
  not overlay content; the deliverable is the report only).
- No binary byte in this change-set is fabricated; the C++ library pair is
  the only committed baseline artifact, and its digests are pinned in the
  grader now.

## 6. Risks

1. **Byte-scan as the aid's ground-truth derivation is a heuristic.** It
   equates "package name table carries the function name AND the library
   class name" with "references". For THIS corpus that equivalence is
   enforced by the aid's contamination gates (South must not carry the
   function name, East must carry none of the three, West must not carry
   the library name), so a false derivation cannot slip through silently —
   but the gates themselves assume FNames serialize as plain ASCII in the
   saved package. If 5.8 packages ever hash/batch names unrecognizably,
   phase 2 dies loudly at the scan step (never a wrong harvest). Fallback:
   derive truth in the graph-lane session via MCP readback and keep the
   aid's role to grading + harvesting.
2. **Call-node presence vs. connectivity.** The scan cannot prove the
   North/South calls sit on an executed chain, only that they exist; the
   prompt's definition says "running an object ... can invoke it". The
   graph-lane session must confirm connectivity via MCP review (§4 TODO).
   The grade itself is unaffected either way (truth is pinned), but the
   prompt's definition and the corpus must actually agree — this is the
   task's honesty obligation, not a verifier gate.
3. **Hash-guard brittleness is a feature with a cost**: ANY corpus
   resave/regeneration (engine bump, redirector fixup sweep, a well-
   meaning "resave all" pass) breaks the pins and every leg fails with
   `USAGE_CORPUS_MODIFIED file=` until re-pinned. That is fail-closed in
   the right direction, and the refgate certificate keying on the
   substrate git tree means drift is caught at authoring/refgate time, not
   mid-bench. The RE-PIN LAW (§4) keeps truth and digests moving together.
4. **`BP_East` via factory-parenting to a BP generated class is
   unproven** from stock python on 5.8 (named fallbacks in §4). If every
   route fails, the corpus design does not change — East just becomes a
   graph-lane-created asset like the two call nodes.
5. **Line-ending normalization on the library sources**: guarded by
   CR-stripped hashing, so autocrlf checkouts agree; an exotic filter that
   rewrites more than line endings would still flip the pin (accepted —
   that IS drift).
6. **The corpus lives inside the agent-writable prefix by necessity**
   (`Content/Tasks/` is the only asset-writable task root), so nothing
   sandbox-rejects a corpus edit — the guard is the sole defense, which is
   why it is three independent probes plus pinned truth rather than a
   single hash check.

## 7. Checklist state (docs/TASK-AUTHOR-GUIDE.md)

- [x] 1. Spec — `task.md` (v2 front matter, round-tripped through the real
      `spec.py` 2026-08-11: `set_name=python`,
      `introspect_scripts=('kp_routine_usage_search.py',)`; behavior-only
      prompt; 5 anti-gaming notes with resolvable defense pointers)
- [x] 2. Scaffold — the C++ library baseline
      `Source/ThirdPerson/Tasks/<id>/EvalUtilityLibrary.{h,cpp}` (marker
      comment `for task kp-routine-usage-search`; comments behavior-only;
      no Build.cs edit needed — `PrivateIncludePaths` already resolves
      `Tasks/<id>/`). NB: this is baseline INPUT, not an agent scaffold to
      fill — the guard pins its bytes.
- [ ] 3. Fixture pair — N/A (no L2; L2I only)
- [ ] 4. Map — N/A (no map anywhere in this task)
- [ ] 5. Camera plan — N/A by design (§3; report-only deliverable)
- [ ] 6. Reference — PENDING the two-phase authoring-lane + graph-lane
      runs (§4, §5)
- [x] 7. Discrimination — `discrimination/MATRIX.md`: automatic
      reference-PASS / empty-FAIL rows + the §7a requirements table
      (7 rows, every prompt requirement mapped to a live assertion; no
      variant owed)
- [ ] 8. Gates — lint can run now; discriminate/refgate blocked on the
      binaries + digest pinning
- [ ] 9. Commit + PR + refgate close — future work

## Accepted residuals (moved from task.md 2026-08-16; lint spec-h2-allowlist)

- **Truth is pinned, not recomputed at grade time.** A defect in the
  authoring-time derivation would grade a wrong answer as right; mitigated
  by the aid deriving every verdict twice (byte-scan + parent-chain walk),
  asserting the derivation equals the pinned constants, and self-grading
  9/9 before harvest (`aids/author_reference.py`). Recorded, with the
  re-pin protocol, in `notes.md` §4.
- **The hash guard is strict by design**: an agent that resaves a corpus
  asset byte-identically passes (nothing changed), but an editor resave
  that alters bytes without altering meaning FAILs. That is intended — the
  prompt says do not modify — but it makes accidental corpus touches
  fatal; disclosed verbatim in the prompt.
- **The guard cannot distinguish "agent modified the corpus" from "a
  substrate drift changed it"** — either way the run fails closed and the
  digests name the file; a substrate-side drift is caught at the refgate
  before any agent sees it.
- **No gate asserts the mechanism** (basket law): reading the four assets
  by eye in an editor session and typing six truthful lines passes. That
  is the basket's design, not a leak.
