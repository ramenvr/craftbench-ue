"""R2 evaluator config defaults (advisory-only, anti-circular).

Design intent: judge.py's module docstring (the canonical statement).
"""
from __future__ import annotations

R2_CONTRACT_VERSION = "1.0"

# The R2 dimensions — the residue the deterministic gate cannot express.
DIMENSIONS = ("visual_fidelity", "design_quality", "advice_quality")

# The closed evidence-source vocabulary (anti-circularity boundary). The judge
# may cite ONLY these; all are produced by stock-UE primitives CraftBench
# controls (never Aura's MCP tools, never the agent-under-test).
#
# FIREWALL: there is deliberately NO "gate_result" source. The judge must form
# its advisory verdict WITHOUT ever seeing the deterministic gate's PASS/FAIL —
# anchoring on the gate would couple the two signals and destroy the advisory
# layer's independence. The gate verdict is computed separately and withheld
# from the judge's context and tools (enforced by assert_firewalled in judge.py).
EVIDENCE_SOURCES = (
    "pie_state_probe",      # P1 RemoteControl :30010 PIE state probe
    "editor_introspect",    # P2 headless editor-Python reflection
    "workspace_file",       # raw read of the applied project tree (CraftBench's own fs)
    "disk_log_read",        # P3 the judge's OWN re-run logs (NEVER the gate's report/logs)
    "profiler_csv",         # P4 CSV profiler
    "viewport_screenshot",  # P5 HighResShot (fuzzy)
    "submission_artifact",  # the agent's prose/diff — judged, never world-truth
    "task_groundtruth",     # author-pinned reference facts (rubric-scoped, not the gate verdict)
)
# Sources that count as world-truth "referees" (vs the claimant submission).
REFEREE_SOURCES = (
    "pie_state_probe", "editor_introspect", "workspace_file", "disk_log_read",
    "profiler_csv", "task_groundtruth",
)
FUZZY_SOURCES = ("viewport_screenshot",)

# --- Judge firewall vocabulary (anti-anchoring boundary) --------------------
# The judge sees ONLY the same scrubbed surface the agent-under-test saw, plus
# its rubric. These are the ONLY task H2 sections allowed into the judge's
# context (mirrors run-agent/prompt_extract.ALLOWED_SECTIONS — the agent scrub).
JUDGE_VISIBLE_TASK_SECTIONS = (
    "Prompt given to the agent",
    "Workspace state pre-task",
)
# Task H2 sections that are the deterministic "answer key" — NEVER shown to the
# judge (they would reveal what the gate checks / the intended solution shape).
FIREWALLED_TASK_SECTIONS = (
    "Verifier specification",
    "Verifier introspection",
    "Verifier fixtures",
    "Anti-gaming notes",
    "Reference solution",
    "Reference solution notes",
)
# On-disk artifacts of the deterministic gate / answer key that must NOT be
# reachable inside the judge's investigation workspace (basename match).
FIREWALLED_ARTIFACT_NAMES = (
    "report.json",          # the verifier's score report (carries outcome)
    "verdict.json",
    "score-report.json",
)
# Path segments whose presence in a reachable file path trips the firewall:
# the gate's log dir and the author's reference solution / discrimination
# variants — both the legacy tests/ homes and the folder-per-task layout
# (tasks/<set>/<id>/reference|discrimination). Matched case-insensitively as
# whole path segments, anywhere in the path (see assert_firewalled in judge.py).
FIREWALLED_PATH_SEGMENTS = (
    "reference-solutions",  # the answer key (legacy tests/reference-solutions/)
    "gate-logs",            # the deterministic gate's captured logs
    "reference",            # folder-local answer key (tasks/<set>/<id>/reference/)
    "discrimination",       # gamed variants (folder-local + legacy tests/discrimination/)
)

DEFAULT_ENSEMBLE_N = 5
# MUST differ from the agent-under-test's model (anti-self-grading; enforced in judge.py).
DEFAULT_EVALUATOR_MODEL = "anthropic/claude-opus-4-x@pinned"

# Reliability thresholds (non-gating signals).
AGREEMENT_LOW = 0.66     # per-criterion agreement below this → low_agreement flag
RUN_ALPHA_LOW = 0.67     # run-level Krippendorff alpha below this → low reliability
CI_FLOOR_DEFAULT = 0.35  # gamed exemplar must score below this in CI
CI_CEILING_DEFAULT = 0.80  # good exemplar must score above this in CI
