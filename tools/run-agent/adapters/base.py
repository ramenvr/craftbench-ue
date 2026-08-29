"""Adapter interface — the only model-specific seam in the harness.

Any backend (claude -p, OpenRouter, local LLM, ...) that satisfies the
AgentAdapter Protocol can be dropped into adapters/registry.py without
touching the rest of the harness.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Verifier verdict vocabulary (shared single source of truth)
#
# The verifier (tools/verify-single/run_task.py) communicates its outcome via
# the process exit code AND a report.json. The harness paths (run.py,
# run_batch.py) must map that outcome to a verdict string CONSISTENTLY — and
# CRUCIALLY must NOT fold pure verifier-noise (a verifier-hash-manifest reject, a
# sandbox reject) into the agent's PASS/FAIL score. This mirrors
# aura_rig/driver.py's VERDICT map so all three harness paths agree on the
# same exit code. (F2/F5 rationale; background: the Aura agent notes.)
#
# verify-single exit codes (run_task.py):
#   0 -> overall PASS         (graded: counts toward pass-rate)
#   1 -> overall FAIL         (graded: counts toward pass-rate)
#   2 -> usage / spec error   (NOT graded: the grade never started)
#   3 -> RETIRED-AND-RESERVED (the removed verifier-hash-manifest reject).
#        Never re-used; kept mapped so an old artifact still reads correctly.
#   4 -> sandbox reject       (NOT graded: submission rejected, excluded)
#   5 -> no .uproject in the materialized substrate (NOT graded: harness error)
#   6 -> FORBIDDEN, never emitted here. 6 is UBT's OWN build-failure code and
#        docs/harness-tour/02-verify-single.md documents "Exit 6 does not exist
#        here" — do not add a mapping for it.
#   7 -> harness could not answer (NOT graded: no verdict was produced at all)
# ---------------------------------------------------------------------------

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_SUBSTRATE_REJECT = "SUBSTRATE-REJECT"
VERDICT_SANDBOX_REJECT = "SANDBOX-REJECT"
# The agent produced no edits at all (``run.py``), or produced nothing the rig
# could submit (``run_graded.py``). Both describe what the MODEL did, so both
# are graded model outcomes — see MODEL_OUTCOME_VERDICTS below. Named here
# because until 2026-08-17 they were bare string literals in five files and the
# taxonomy's own constants module did not name two of its own verdicts.
VERDICT_FAIL_NO_EDITS = "FAIL_NO_EDITS"
VERDICT_NO_DELIVERABLE = "NO_DELIVERABLE"
# The verifier itself could not produce a verdict: the gating layer set came
# back empty/incomplete, the build tool could not be executed at all (L1 exit
# 127), a gating layer RAN and counted nothing while every dependency it
# declares PASSED, the graded substrate had no .uproject, or main() died on an
# uncaught exception. This is NOT "the agent failed" — there is no measurement,
# so it is kept out of GRADED_VERDICTS and out of every pass-rate denominator.
# It is deliberately NOT the string "ERROR": that label is already taken by
# verify-single exit 2 (usage/spec error) in aura_rig/driver.py's VERDICT map
# and renaming it would churn historical summary.json for zero gain.
VERDICT_HARNESS_ERROR = "HARNESS-ERROR"
# verify-single exit 2 — a usage/spec error, i.e. the grade never started. Same
# spelling driver.VERDICT has always used for key 2 (do not rename: historical
# summary.json carries it).
VERDICT_ERROR = "ERROR"
# The agent's Aura MCP tools all returned a subscription-validation 401, so it
# could not actuate at all. An infra/auth failure, NOT a model outcome — kept
# out of GRADED_VERDICTS so it never counts as a FAIL in a pass-rate.
VERDICT_TOOL_AUTH_BLOCKED = "TOOL-AUTH-BLOCKED"
# The :41200 editor was open on a DIFFERENT Unreal project than the craftbench
# substrate, so the agent's edits would land off-target. A setup/infra failure
# caught BEFORE driving (no tokens spent) — also kept out of GRADED_VERDICTS.
VERDICT_EDITOR_WRONG_PROJECT = "EDITOR-WRONG-PROJECT"
# The drive editor never came up, on the lane that starts it AFTER the fairness
# hide (aura-mcp, run.py --defer-editor). No tokens were spent and no submission
# exists, so this is a harness state, not a model outcome — non-graded, which is
# what keeps the grid cell OPEN for a re-run (sweep_mcp_lanes.sh::cell_done keys
# on is_graded_verdict). Distinct from HARNESS-ERROR because the verifier never
# ran at all, and from TOOL-AUTH-BLOCKED because the tool path was never reached.
VERDICT_EDITOR_NOT_READY = "EDITOR-NOT-READY"
# The agent process started but NEVER REACHED THE PROVIDER — its own config was
# rejected before any API call (a model name the CLI refuses, a missing key). Was a
# bare string literal in run.py until 2026-08-17; named here so the one place that
# writes it and the tests that assert it non-graded share a definition.
VERDICT_AGENT_CONFIG_ERROR = "AGENT-CONFIG-ERROR"
# The agent reached the provider but the CALL failed on transport — a read timeout,
# a 5xx, a rate limit, a gated model's 403. Kept DISTINCT from
# AGENT-CONFIG-ERROR because the two demand opposite responses: a config error is
# ours and must be fixed before re-running, a transport error is the provider's and
# the rep should simply be re-run. Collapsing them would hide which of those a
# sweep's losses were.
#
# Why this exists at all (measured 2026-08-17, bare:deepseek/deepseek-v4-flash on
# gp-dot-aoe-burn-cpp): the LLM call hit a 60s per-read timeout, the adapter
# returned exit 1 with 0 turns / 0 tokens / 0 tools, the submission snapshot still
# found the untouched scaffold — so it was NOT empty, the empty-submission guard
# never ran, the verifier graded the unmodified scaffold, and the run recorded a
# model **FAIL**. The bias is directional and invisible: slow and cheap models time
# out more often, so this manufactured fake FAILs for exactly the low-price end of
# the slate, i.e. against the price-vs-capability claim the sweep exists to test.
VERDICT_AGENT_TRANSPORT_ERROR = "AGENT-TRANSPORT-ERROR"
# The repo-level answer-key hide was DEFEATED mid-drive: a tree
# stage_repo_answer_hide parked (tasks/, tools/verify-single/, .git) was back on
# disk when the agent finished, so the drive may have read the reference
# solution. Non-graded in BOTH directions on purpose — a PASS may be copied and
# a FAIL is unmeasured — and distinct from HARNESS-ERROR because the verifier
# worked fine; the fairness precondition did not.
VERDICT_FAIRNESS_BREACH = "FAIRNESS-BREACH"
# verify-single exit 8 — the run deliberately did not certify (--lite skipped the
# L1 build, so the layers ran against binaries the run did not produce). A CHOICE,
# not a fault, which is why it is not folded into HARNESS-ERROR: a dashboard must
# be able to tell a cheap iteration run from a broken one. Non-graded by omission
# from GRADED_VERDICTS, like every other non-PASS/FAIL verdict.
VERDICT_UNGRADED = "UNGRADED"

# Exit-code -> verdict for the non-graded (noise / rejection / harness-error)
# codes ONLY. Exit 0/1 are deliberately absent here because the PASS/FAIL
# distinction is read authoritatively from report.json's ``overall`` field (a
# stdout regex is only a fallback), not inferred from the exit code.
#
# This map MUST agree with aura_rig/driver.py's VERDICT on every shared key —
# the two are the verifier-facing halves of the SAME taxonomy on two different
# harness paths (run.py/run_batch.py vs the cb rig), and a disagreement means
# the same run reads as two different outcomes depending on who graded it.
# tests/test_verdict_mapping.py::TestExitTaxonomyAgreement pins that.
VERIFIER_EXIT_VERDICT = {
    2: VERDICT_ERROR,
    3: VERDICT_SUBSTRATE_REJECT,
    4: VERDICT_SANDBOX_REJECT,
    5: VERDICT_HARNESS_ERROR,
    7: VERDICT_HARNESS_ERROR,
    8: VERDICT_UNGRADED,
}

# The verdicts that describe what the MODEL did rather than what the HARNESS
# did. They belong IN the pass-rate denominator: excluding them biases scores
# UPWARD, which is the exact mirror of charging a harness fault to the model and
# equally wrong. Owner decision 2026-08-14; the denominator rule is the
# authoritative statement.
MODEL_OUTCOME_VERDICTS = frozenset({
    VERDICT_FAIL_NO_EDITS, VERDICT_SANDBOX_REJECT, VERDICT_NO_DELIVERABLE,
})

# Verdicts that represent an actual graded agent outcome and therefore belong
# in a pass-rate / PASS-FAIL denominator. Everything else (substrate reject,
# harness timeout/error, HARNESS-ERROR, ERROR, TIMEOUT, UNGRADED, and every
# rig-only infra verdict) is verifier-noise or a harness condition and MUST be
# excluded from the denominator so it can never be silently relabelled an agent
# FAIL.
#
# This is an ALLOWLIST on purpose: every verdict added to the taxonomy is
# non-graded by default, so a new harness state can never leak into a
# pass-rate by omission. Do not turn it into a denylist.
#
# WIDENED 2026-08-17 from ``{PASS, FAIL}``, closing the divergence
# the denominator rule recorded as "known, tracked separately":
# ``tools/compare/compare_products.py`` and ``tools/dashboard/collect.py``
# already counted the three MODEL_OUTCOME_VERDICTS, so ONE run set produced TWO
# different pass rates depending on which aggregator you asked — which would
# have put two contradicting tables in a published comparison. Three consequences, each
# deliberate, each pinned by a test:
#   1. ``cb bench`` resume stops re-rolling a SANDBOX-REJECT rep (cb.py's
#      ``kept`` count). That is the retry-until-graded bias the
#      void-and-retry rule names as a bias to close, not a regression.
#   2. Exit codes are UNCHANGED — SANDBOX-REJECT still exits 4. The published
#      VERIFIER_EXIT_VERDICT table now wins over this set inside
#      ``run_graded.exit_code_for_summary``; it used to be the other way round,
#      which was invisible only because the two sets happened to coincide.
GRADED_VERDICTS = frozenset({VERDICT_PASS, VERDICT_FAIL}) | MODEL_OUTCOME_VERDICTS


def is_graded_verdict(verdict: Optional[str]) -> bool:
    """True iff ``verdict`` is a real graded agent outcome.

    That is PASS, FAIL, or one of the three MODEL_OUTCOME_VERDICTS
    (FAIL_NO_EDITS / SANDBOX-REJECT / NO_DELIVERABLE) — all five describe
    something the model did.

    Non-graded verdicts (SUBSTRATE-REJECT, HARNESS-ERROR, ERROR, TIMEOUT,
    UNGRADED, TOOL-AUTH-BLOCKED, and the rig's other infra verdicts) return
    False and must be excluded from any pass-rate denominator the harness
    computes. This predicate answers *denominator membership only* — it is not a
    proxy for "exit 0/1" (see run_graded.exit_code_for_summary).
    """
    return verdict in GRADED_VERDICTS


def pass_rate(verdicts: Iterable[Optional[str]]) -> Optional[float]:
    """Pass-rate over an iterable of verdicts, EXCLUDING non-graded outcomes.

    The denominator is the count of graded verdicts only (``GRADED_VERDICTS``);
    a SUBSTRATE-REJECT / HARNESS-ERROR / TIMEOUT never inflates or deflates the
    rate. A SANDBOX-REJECT / NO_DELIVERABLE / FAIL_NO_EDITS DOES count, as a
    non-pass — it is a model outcome (the denominator rule). Returns None when
    there is no graded sample (denominator == 0) so a caller can distinguish
    "0% pass" from "nothing graded".
    """
    graded = [v for v in verdicts if is_graded_verdict(v)]
    if not graded:
        return None
    return sum(1 for v in graded if v == VERDICT_PASS) / len(graded)


def _overall_from_report_json(stdout: str) -> Optional[str]:
    """Read the authoritative ``overall`` from report.json if the runner printed
    its path (``json report: <path>``) and the file is still on disk.

    Returns the UPPERCASED verdict (report.json stores lowercase ``pass``/
    ``fail``; the rendered stdout line uppercases it), or None if there is no
    marker / the file is gone / it is unparseable — in which case the caller
    falls back to the stdout regex.
    """
    marker = "json report:"
    for line in stdout.splitlines():
        if marker in line:
            json_path = line.split(marker, 1)[1].strip()
            try:
                data = json.loads(Path(json_path).read_text(encoding="utf-8"))
            except Exception:
                return None
            overall = data.get("overall")
            if isinstance(overall, str) and overall:
                return overall.upper()
            return None
    return None


def _overall_from_stdout_regex(stdout: str) -> str:
    """Fallback parse of the human-rendered ``overall : <VALUE>`` stdout line.

    Used ONLY when no report.json is available.

    Defaults to HARNESS-ERROR — NOT FAIL — when the line is absent. The legacy
    default-to-FAIL was a silent mislabel: no report.json AND no rendered
    ``overall`` line means the verifier never reached the point where it states
    a verdict (it died early, was killed, or wrote its report somewhere this
    process cannot see). Calling that "the agent failed" invents a measurement
    that was never taken and puts it in the pass-rate denominator; HARNESS-ERROR
    is non-graded, so the run is excluded and visibly flagged instead.
    """
    for line in stdout.splitlines():
        m = re.match(r"\s*overall\s*:\s*(\S+)\s*$", line)
        if m:
            return m.group(1)
    return VERDICT_HARNESS_ERROR


def verdict_from_verifier(returncode: Optional[int], stdout: str) -> str:
    """Map a verify-single run to a harness verdict.

    1. A non-graded exit code (VERIFIER_EXIT_VERDICT: 2 -> ERROR,
       3 -> SUBSTRATE-REJECT, 4 -> SANDBOX-REJECT, 5/7 -> HARNESS-ERROR) wins
       outright — these are verifier-noise / rejection / harness error, never an
       agent FAIL, and on these codes the verifier may write no usable PASS/FAIL
       anyway (exit 7 from an uncaught exception writes no report.json at all,
       which is precisely why the exit code is consulted FIRST).
    2. Otherwise prefer the authoritative ``overall`` from report.json.
    3. Fall back to the stdout regex only when no report.json is available
       (HARNESS-ERROR when even the regex finds nothing — see
       _overall_from_stdout_regex).
    """
    if returncode in VERIFIER_EXIT_VERDICT:
        return VERIFIER_EXIT_VERDICT[returncode]
    from_report = _overall_from_report_json(stdout)
    if from_report is not None:
        return from_report
    return _overall_from_stdout_regex(stdout)


# ---------------------------------------------------------------------------
# Reasoning policy — ONE declaration, read by every adapter and by the result
# writer (run.py's _write_result). Restating it per adapter is how the record and
# the wire drift apart.
#
# It records THE REQUEST, not a guess at the outcome. There is deliberately no
# "effort level" field: on the wire the panel runs on, an effort request is
# accepted with HTTP 200 and has no measured effect, no provider reports a level
# back, and two panel models refuse to disable reasoning at all
# (the 2026-08-24 reasoning-level probe). A level we picked and the
# provider ignored would be a label no measurement supports — the same defect as
# the hand-maintained price table this repo has already been wrong with twice.
# ---------------------------------------------------------------------------

#: Request-side parameter names that raise, lower, or reveal a provider's
#: reasoning effort, across every shape this harness can speak: the
#: OpenAI-compatible scalar, OpenRouter's unified block, Anthropic's native block
#: and its budget, and the Claude Code CLI's env lever — the claude-p lanes send a
#: PROCESS rather than a body, so a flag or an env var is as much an emission as a
#: JSON key. The guard normalizes case, dashes and a leading ``--`` before
#: matching, so one entry covers ``"reasoning_effort"``, ``--reasoning-effort``
#: and ``REASONING_EFFORT``.
#:
#: tests/test_reasoning_policy.py scans the request builders for these, so a new
#: wire shape has to be named HERE to be guarded.
REASONING_REQUEST_PARAMS = (
    "reasoning",
    "reasoning_effort",
    "include_reasoning",
    "thinking",
    "budget_tokens",
    "max_thinking_tokens",
)

#: The reasoning parameter this harness puts on the wire: none, on every request
#: path. Recorded verbatim (JSON null) rather than as a word, because "we sent
#: nothing" is a fact about our own request layer — the only reasoning fact a run
#: witnesses for certain.
REASONING_PARAM_SENT = None

#: The label for the REQUEST above, never for the effort it produced. Anything
#: that starts sending a parameter changes this in the same edit; the guard fails
#: when the two disagree.
REASONING_POLICY = "provider-default"


def reasoning_policy_fields(reasoning_tokens: Optional[int]) -> dict:
    """The reasoning block for one run's record: what was REQUESTED, then what was
    MEASURED.

    ``reasoning_tokens`` is the provider's own count (AgentResult's field, filled
    only where the wire reports it — in practice the gateway-routed lane). It is
    passed in rather than read off an AgentResult because the two halves have
    different certainty: the requested half is knowable on every path, the
    measured half almost never.

    ``reasoning_measurement`` carries the state an integer cannot. "the provider
    reported 0" and "nothing reported anything" must not read alike — a consumer
    writing ``n or 0`` collapses them — and neither may read like a record written
    before this block existed, where the key is absent entirely. So the
    discriminator is always present, and no consumer has to infer it from the
    count.
    """
    return {
        "reasoning_policy": REASONING_POLICY,
        "reasoning_requested": REASONING_PARAM_SENT,
        "reasoning_tokens": reasoning_tokens,
        "reasoning_measurement": ("reported" if reasoning_tokens is not None
                                  else "unmeasured"),
    }


@dataclass
class AgentResult:
    exit_code: int                              # 0 = adapter ran cleanly; non-zero = adapter/process error
    transcript: str                             # raw stdout from the model process (stream-json for claude-p)
    summary: Optional[str]                      # final assistant message text, if recoverable
    tool_use_count: Optional[int]               # total tool calls; None for adapters that can't count
    duration_s: float
    mcp_tool_use_count: Optional[int] = None    # subset of tool_use_count starting with "mcp__"
    tool_names: Optional[List[str]] = None      # ordered list of tool names invoked (verbatim)
    cost_usd: Optional[float] = None            # adapter-reported $ cost, if surfaced
    num_turns: Optional[int] = None             # number of model turns in the loop
    tokens_in: Optional[int] = None             # TOTAL billable input tokens (uncached + cache creation +
                                                # cache read), if surfaced; None when unknown. Under prompt
                                                # caching the uncached remainder alone is a rounding error —
                                                # see the claude_p adapter's usage-parsing note.
    tokens_out: Optional[int] = None            # completion/output tokens, if surfaced; None when unknown
    cache_creation_tokens: Optional[int] = None  # input tokens WRITTEN to the prompt cache (billed 1.25x)
    cache_read_tokens: Optional[int] = None      # input tokens SERVED from the prompt cache (billed 0.1x)
    # OUTPUT tokens the provider says were spent THINKING — a subset of
    # tokens_out, not an addition to it. On the wire it is
    # completion_tokens_details.reasoning_tokens (OpenAI shape, bare_wire) and
    # usage.output_tokens_details.thinking_tokens (Anthropic shape, aura_rig.proxy).
    # Under REASONING_POLICY above (nothing requested), this is the only per-run
    # record of what a provider's DEFAULT effort produced. None means nothing
    # reported it, never that the model did not think — reasoning_policy_fields()
    # is what puts that distinction on the record.
    reasoning_tokens: Optional[int] = None
    models_used: Optional[List[str]] = None     # model ids that ACTUALLY answered (attribution — a bare
                                                # backend slug runs on the CLI's session default)

    # PROVIDER-SIDE ACCOUNTING (2026-08-18). The loop already collected both of
    # these and this mapping DROPPED them, so the join key to OpenRouter's own
    # ledger never reached result.json and no published cost could be audited
    # against anything but our own arithmetic. Same failure as the tokens_in/out
    # drop fixed on 2026-08-17 — collected, then lost one layer from the disk.
    generation_ids: Optional[List[str]] = None   # OpenRouter ids, one per model call.
                                                 # The join key for /api/v1/generation,
                                                 # which returns total_cost AND the DATED
                                                 # model permaslug (e.g.
                                                 # z-ai/glm-5.3-20260816) that the pinned
                                                 # slug alone does not identify.
    providers_served: Optional[List[str]] = None  # distinct backends that answered. MORE
                                                  # THAN ONE means this row averages two
                                                  # systems (hosts differ in quantization
                                                  # and version cadence), not one.

    # SCAFFOLD IDENTITY (2026-08-17). Without these, "bare scored 0 and the product
    # scored 60" reads as a statement about the MODEL when it is a statement about
    # the scaffold. `tool_names` records what FIRED; these record what the arm could
    # ever have done, so a reader can tell the two comparisons apart.
    tools_offered: Optional[List[str]] = None    # every tool the arm exposed this run
    system_prompt_sha: Optional[str] = None      # the prompt is a silent fairness lever
    truncated_turns: Optional[int] = None        # turns cut off at the output limit
    max_consecutive_repeats: Optional[int] = None  # longest identical-call run (see
    #                                                aura_mcp.max_consecutive_repeats)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


@runtime_checkable
class AgentAdapter(Protocol):
    name: str

    def run(
        self,
        prompt_path: Path,
        workspace_dir: Path,
        max_turns: int,
        timeout_s: int,
    ) -> AgentResult:
        ...
