<!--
CraftBench benchmark preamble — the ONE editable source of the prompt contract
every backend prepends to every task prompt. Edit THIS file to tune the wording;
no code change is needed (tools/run-agent/preamble.py renders it verbatim).

Placeholders (replaced literally by preamble.py — do not use other {tokens}):
  {task_id}                   the active task id
  {scaffold_files}            comma-separated repo-relative scaffold paths for THIS task
  {writable_roots}            comma-separated writable path prefixes (AGENT_WRITABLE.json "writable")
  {asset_roots}               comma-separated asset-writable prefixes (AGENT_WRITABLE.json "asset_writable")
  {lane_rules}                lane-scoped operational rules from tasks/PREAMBLE.<lane>.md
                              (empty for lanes without a file).
                              A lane file exists ONLY for a rule that lane's harness cannot
                              ENFORCE — enforceable policy goes in adapters/registry.py::
                              _DENIED_ORCHESTRATION. Each lane file ships verbatim in that
                              arm's Harness Card.
  {scaffold_excerpt_section}  the "Current scaffold contents" appendix (aura paths only;
                              rendered fresh from disk at drive time; empty on backends
                              whose tools already show workspace files)

Fairness rules for editing this file (Authoring Hard Rule #2 still applies):
  - Naming scaffold FILE PATHS is allowed — they are discoverable by listing the
    workspace; this is workspace STATE, not solution guidance.
  - NEVER name verifier tags, assertions, fixture classes, tolerances, or the
    design pattern the solution should use.

KEEP THIS FILE LEAN, AND KEEP IT UNIFORM.
Two rules that pull in the same direction:

  1. ONE preamble CONTRACT for every backend. Everything below except
     {lane_rules} is byte-identical across arms — making the CONTRACT
     backend-conditional would quietly break run-to-run comparability, the
     thing it exists to protect. Lane-scoped OPERATIONAL rules (rules about a
     lane's own tool lifecycle, which are scaffold, not task content) live in
     tasks/PREAMBLE.<lane>.md and render only for that lane (this supersedes
     an earlier fully-uniform rule, which paid every lane tokens for prose
     about tools it could not even call).
  2. The agent gets the RULE; the rationale stays up here, where it is
     stripped before the agent ever sees it (preamble.py::_strip_template_comment).
     Every character below is prepended to EVERY task prompt on EVERY run, so
     an explanation written for a maintainer is paid for by every eval.

  Corollary: prefer HARNESS ENFORCEMENT over prose. A tool that must not be
  called belongs in adapters/registry.py::_DENIED_ORCHESTRATION, where the
  MCP lanes cannot call it at all. A lane file earns its existence only for a
  rule that lane cannot enforce; no lane in this release needs one, so no
  tasks/PREAMBLE.<lane>.md file ships and {lane_rules} renders empty for
  every arm. The mechanism stays because it is arm-generic.
-->

# Benchmark session rules

- Unattended benchmark run: finish in this one session. Never ask questions,
  offer options, or wait for confirmation — no operator will answer. If a tool
  call fails, retry it or work around it, then continue.
- You are graded on the files on disk when the session ends. Finish with the
  deliverable written to disk, and compiled if it is code.
{lane_rules}

# Task workspace ({task_id})

- The pre-existing scaffold for THIS task is exactly: {scaffold_files}.
  Implement the requested behavior by extending these files (or subclassing the
  types they declare) — not in any other pre-existing actor or class, and never
  in another task's files.
- Create new files only under: {writable_roots}. New assets (Blueprints,
  materials, etc.) belong under: {asset_roots}. Everything else in the project
  is read-only or absent by design — do not write there.
- Trust the filesystem over any remembered or preloaded project context. If
  a file you expect is not on disk, it is not part of this task — do not
  recreate it.
- Grading internals (the verifier's test sources and its file manifest) are
  hidden or stubbed during your session by design. Do not spend time looking
  for them or trying to reconstruct them — including through version-control
  history. Build to the behavior specified in the task, which is the only
  contract you are graded against.
- You may verify your work by playing it in-editor (e.g. one PIE session) AT
  MOST ONCE, at the end, before finishing. Do not iterate through repeated
  play-test cycles — this is a delegated task, not a debugging session; budget
  your remaining time for completing the deliverable instead.
{scaffold_excerpt_section}
