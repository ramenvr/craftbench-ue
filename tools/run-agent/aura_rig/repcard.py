"""repcard — the per-rep terminal SUMMARY CARD for `cb eval` / `cb bench`.

One aligned box-drawing card per graded run, printed by cb.py's
``_recap_run_summary`` (cmd_eval's recap) and after every bench rep, so the
operator reads verdict / cost / time / per-layer status / the per-checkpoint
story / trace + artifact locations at a glance — instead of opening
report.html for each rep.

Honesty rules (they shape the whole module):

* The per-checkpoint lines are MEASUREMENTS from the graded L2 log (the same
  ``checkpoint_states`` caption channel report.html reads). They are never
  per-checkpoint verdicts: the
  verifier does not produce those. The FAILING gate is named from the L2
  evidence lines (the ``FinishTest TestResult=Failed`` note carries the
  assertion + message); a ``✓`` appears on checkpoints only when the L2
  layer as a whole PASSed.
* Absent fields are OMITTED lines, never blanks — gen-only runs have no
  grade, old envelopes no timings, pruned workdirs no checkpoint states.
* The ``reasoning`` row is the ONE unconditional row, and only its first half
  is: what a run REQUESTED is never absent (a run knows what it sent), while
  the provider's reasoning-token count is reported by the gateway-routed lane
  alone, so the measured half follows the omission rule above. Unmeasured is
  rendered as unmeasured — never as zero, which is a measurement no unproxied
  run made.
* Color is ANSI with an honest fallback: disabled when stdout is not a TTY,
  when ``NO_COLOR`` is present (the no-color.org convention) or
  ``CB_NO_COLOR=1``, and on a Windows console that cannot be switched into
  VT mode (probed via SetConsoleMode, not assumed — Windows Terminal /
  ConEmu / ANSICON short-circuit as known-good). Rendering is PURE given
  ``color=``; only the auto-detection touches the environment.

Pure over the envelope dict + an injected states mapping, so tests render
cards from synthetic summaries with no UE and no filesystem beyond a temp
run dir.
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# ANSI + honest color detection                                                #
# --------------------------------------------------------------------------- #

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_RED = "\x1b[31m"
_GREEN = "\x1b[32m"
_YELLOW = "\x1b[33m"

# Card geometry: total inner width the flow-wrapped parts aim for. Paths and
# URLs are deliberately never wrapped (a broken path harms copy-paste).
WIDTH = 74
_LABEL_W = 11          # "agent files" — the widest left-column label


def _no_color_env(env) -> bool:
    """The two opt-outs: NO_COLOR (present and non-empty, per no-color.org)
    and the repo-local CB_NO_COLOR=1."""
    if (env.get("NO_COLOR") or "") != "":
        return True
    return str(env.get("CB_NO_COLOR", "")).strip() == "1"


def _windows_vt_capable(env) -> bool:
    """True when this Windows console speaks ANSI — known-good terminals by
    env marker, else PROBED by asking the console for VT mode (SetConsoleMode
    with ENABLE_VIRTUAL_TERMINAL_PROCESSING); an older conhost that refuses
    gets the plain fallback. Detect, never assume."""
    if env.get("WT_SESSION") or env.get("ANSICON") \
            or env.get("ConEmuANSI") == "ON" \
            or env.get("TERM_PROGRAM"):
        return True
    try:
        import ctypes
        k32 = ctypes.windll.kernel32                     # type: ignore[attr-defined]
        h = k32.GetStdHandle(-11)                        # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k32.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        if mode.value & 0x0004:                          # VT already on
            return True
        return bool(k32.SetConsoleMode(h, mode.value | 0x0004))
    except Exception:  # noqa: BLE001 — a color probe must never cost a recap
        return False


def supports_color(stream=None, env=None) -> bool:
    """Whether the card should emit ANSI color right now."""
    env = os.environ if env is None else env
    if _no_color_env(env):
        return False
    stream = sys.stdout if stream is None else stream
    try:
        if not (hasattr(stream, "isatty") and stream.isatty()):
            return False
    except Exception:  # noqa: BLE001 — a closed/odd stream means "no color"
        return False
    if os.name == "nt":
        return _windows_vt_capable(env)
    return True


def _paint(s: str, code: str, on: bool) -> str:
    return f"{code}{s}{_RESET}" if on else s


def _verdict_paint(verdict: str, on: bool) -> str:
    """green PASS / red FAIL / yellow everything non-graded."""
    if verdict == "PASS":
        return _paint(verdict, _BOLD + _GREEN, on)
    if verdict == "FAIL":
        return _paint(verdict, _BOLD + _RED, on)
    return _paint(verdict, _BOLD + _YELLOW, on)


# --------------------------------------------------------------------------- #
# Field extraction (pure over the envelope dict)                               #
# --------------------------------------------------------------------------- #

# Registry execution order first, so "the first failing layer" below means
# the same thing it does in the verifier; unknown layers append after.
_LAYER_ORDER = ("L1", "L2", "L2I", "ART", "L3", "R2")

_EVIDENCE_PREFIX = "verdict-evidence:"


def _ordered_layers(layers: dict) -> List[Tuple[str, dict]]:
    known = [(n, layers[n]) for n in _LAYER_ORDER if n in layers]
    extras = [(n, layers[n]) for n in sorted(layers) if n not in _LAYER_ORDER]
    return [(n, lr) for n, lr in known + extras if isinstance(lr, dict)]


def layer_segments(layers: dict) -> List[Tuple[str, str, str]]:
    """Per layer: (name, status_word, tail) — e.g. ("L2", "FAIL", "0/1 27s").
    status_word carries the honesty coloring hook: "pass"/"FAIL"/"ERROR"/
    "skipped" verbatim from the layer report's own status."""
    out = []
    for name, lr in _ordered_layers(layers):
        status = str(lr.get("status") or "?")
        word = {"pass": "pass", "fail": "FAIL", "error": "ERROR"}.get(status,
                                                                      status)
        bits = []
        if lr.get("tests_run") is not None:
            bits.append(f"{lr.get('tests_passed') or 0}/{lr['tests_run']}")
        dur = lr.get("duration_seconds")
        if isinstance(dur, (int, float)):
            bits.append(f"{dur:.0f}s")
        out.append((name, word, " ".join(bits)))
    return out


def failing_gate(layers: dict) -> Optional[Tuple[str, Optional[str]]]:
    """(layer, message) naming the FAILING gate, or None when nothing failed.

    The message is the layer's own evidence, verbatim — never derived here:
    the ``FinishTest TestResult=Failed`` verdict-evidence note names the L2
    assertion + its message (preferred), any other verdict-evidence line is
    the fallback, and an L2I failing-check note (": FAIL") covers the
    introspect layer. First failing layer in execution order wins — it is
    the gate that decided the verdict."""
    for name, lr in _ordered_layers(layers):
        if str(lr.get("status")) not in ("fail", "error"):
            continue
        notes = [str(n).strip() for n in (lr.get("notes") or [])]
        ev = [n[len(_EVIDENCE_PREFIX):].strip() for n in notes
              if n.startswith(_EVIDENCE_PREFIX)]
        for e in ev:
            if "FinishTest" in e:
                return name, e
        if ev:
            return name, ev[0]
        checks = [n for n in notes if ": FAIL" in n]
        if checks:
            return name, checks[0]
        return name, None
    return None


def checkpoint_entries(states: Dict[int, object],
                       l2_passed: bool,
                       color: bool = False) -> List[str]:
    """One entry per checkpoint: ``cp00 t=0.5s <state…>``. The states are
    MEASUREMENTS (the graded log's caption channel); the only mark ever added
    is a green ``✓`` per checkpoint when the L2 layer as a whole PASSed —
    a per-checkpoint pass/fail the verifier did not produce is never
    invented."""
    out = []
    for idx in sorted(states):
        st = states[idx]
        entry = f"cp{getattr(st, 'idx', idx):02d}"
        t = getattr(st, "t", None)
        if t is not None:
            entry += f" t={t:g}s"
        state = getattr(st, "state", None)
        if state:
            entry += f" {state}"
        if l2_passed:
            entry = _paint("✓", _GREEN, color) + " " + entry
        out.append(entry)
    return out


def _pack(entries: List[str], width: int) -> List[str]:
    """Greedy-flow entries into ``" · "``-joined lines of at most ``width``
    visible chars; an oversize entry stands alone rather than being cut."""
    lines: List[str] = []
    cur = ""
    for e in entries:
        cand = e if not cur else f"{cur} · {e}"
        if cur and len(cand) > width:
            lines.append(cur)
            cur = e
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------- #
# The card                                                                     #
# --------------------------------------------------------------------------- #

def _fmt_tokens(n) -> str:
    return f"{int(n):,}" if isinstance(n, (int, float)) else str(n)


def _fmt_s(v) -> str:
    """Seconds without a trailing .0 (1111.0 -> '1111', 285.6 -> '285.6')."""
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


#: Where a run records the reasoning parameter it SENT: our own name for the
#: record, plus the wire parameter's name for a recorder that mirrors the
#: request shape. Searched in the agent block first (it belongs to the layer
#: that owns the request), then top-level for envelopes whose agent block is
#: written elsewhere (the aura lanes write their own shape).
_REASONING_REQUEST_KEYS = ("reasoning_requested", "reasoning_effort")
#: Presence of any of these is what makes the envelope a WITNESS to the request.
#: adapters.base.reasoning_policy_fields stamps them together, so one is enough.
_REASONING_RECORD_KEYS = _REASONING_REQUEST_KEYS + ("reasoning_policy",
                                                    "reasoning_measurement")


def _requested_reasoning(s: dict, agent: dict):
    for where in (agent, s):
        for key in _REASONING_REQUEST_KEYS:
            if where.get(key) is not None:
                return where[key]
    return None


def _records_reasoning(s: dict, agent: dict) -> bool:
    """Whether this envelope says anything about the reasoning request at all."""
    return any(k in where for where in (agent, s)
               for k in _REASONING_RECORD_KEYS)


def reasoning_row(s: dict) -> str:
    """The reasoning row: what was REQUESTED, then what was MEASURED.

    The requested half is read OFF THE ENVELOPE, never assumed: a recorded
    parameter is named verbatim, and only its absence means none went on the
    wire. A renderer that hard-coded the default would keep saying "default"
    on the first run that sets effort.

    "no parameter sent" is a claim about our own request layer, which is the
    only thing the envelope witnesses — a lane where a product front-end makes
    the call could set one without it reaching this record. An envelope
    carrying no reasoning block at all witnesses nothing, and says so.
    """
    agent = s.get("agent") or {}
    req = _requested_reasoning(s, agent)
    if req is None and not _records_reasoning(s, agent):
        # No reasoning block at all: a record written before the field existed,
        # or a lane whose writer does not stamp it. Saying "no parameter sent"
        # here would assert a fact about a request this envelope never saw --
        # and it is the affirmative form that would get quoted.
        txt = "requested: not recorded"
    elif req is None:
        txt = "requested: provider default (no reasoning parameter sent)"
    elif isinstance(req, dict):
        txt = "requested: " + " ".join(f"{k}={req[k]}" for k in sorted(req))
    else:
        txt = f"requested: {req}"
    rt = agent.get("reasoning_tokens")
    if isinstance(rt, (int, float)):
        # Share against the SAME record's output count only. The cost
        # snapshot's output figure is thread-billed (tool/sub-agent turns
        # included), so dividing by it would ratio two different accountings.
        out = agent.get("tokens_out")
        share = (f" ({rt / out:.1%} of output)"
                 if isinstance(out, (int, float)) and out > 0 else "")
        return txt + f"  ·  measured: {_fmt_tokens(rt)} reasoning tok{share}"
    return txt + "  ·  measured: not reported (unmeasured, not zero)"


def render_card(s: dict, run_dir: Path,
                states: Optional[Dict[int, object]] = None,
                color: bool = False,
                report_name: str = "summary.json") -> List[str]:
    """Render the summary card for one run envelope. Pure: the envelope dict,
    the injected checkpoint states, and the color switch fully determine the
    output. Absent fields yield absent lines — except the reasoning row, which
    always renders: on a record that stamps the block it names the request, and
    on one that does not it says the request was not recorded."""
    run_dir = Path(run_dir)
    agent = s.get("agent") or {}
    t = s.get("timings") or {}
    verifier = s.get("verifier") or {}
    layers = verifier.get("layers") or {}
    states = states or {}

    def lab(name: str) -> str:
        return _paint(f"{name:<{_LABEL_W}}", _DIM, color)

    body: List[str] = []

    def row(label: str, text: str) -> None:
        body.append(f"{lab(label)} {text}")

    def wrapped_row(label: str, text: str) -> None:
        first, cont = f"{lab(label)} ", " " * (_LABEL_W + 1)
        for i, ln in enumerate(textwrap.wrap(text, WIDTH - _LABEL_W - 1,
                                             break_long_words=False,
                                             break_on_hyphens=False)
                               or [text]):
            body.append((first if i == 0 else cont) + ln)

    # --- verdict / model / cost / time / tools -----------------------------
    verdict = s.get("verdict") or s.get("overall")
    if verdict:
        row("verdict", _verdict_paint(str(verdict), color))
    # Attribution first (what actually answered), label as fallback.
    models_used = agent.get("models_used")
    model = ",".join(models_used) if models_used else s.get("model")
    if model:
        pinned = s.get("model_pinned")
        row("model", str(model) + (f"  (pinned: {pinned})" if pinned else ""))
    # A property of the CONFIGURATION, so it sits with attribution and above
    # spend. Renders always — see the module docstring on why this row alone
    # does not follow the omit-when-absent rule.
    wrapped_row("reasoning", reasoning_row(s))
    cost = s.get("est_cost_usd")
    if cost is None:
        cost = agent.get("cost_usd")
    if isinstance(cost, (int, float)):
        txt = f"${cost:.4f}"
        cs = s.get("cost_thread") or s.get("cost_snapshot") or {}
        if cs.get("input_tokens") is not None:
            txt += (f"  ({_fmt_tokens(cs['input_tokens'])} in / "
                    f"{_fmt_tokens(cs.get('output_tokens'))} out tok)")
        # Same label/explanation as report.html (owner ask 2026-08-06 #6):
        # thread-billed includes tool/sub-agent turns, so PostHog's main
        # trace shows a smaller number by design.
        txt += "  ·  thread-billed; PostHog's main trace shows less"
        wrapped_row("model spend", txt)
    elif s.get("cost_capture_failed"):
        row("model spend", "UNCAPTURED")
    time_bits = []
    if t.get("aura_execution_time") is not None:
        agent_txt = f"agent {_fmt_s(t['aura_execution_time'])}s"
        if t.get("drive_s") is not None:
            agent_txt += f" (wall {_fmt_s(t['drive_s'])}s)"
        time_bits.append(agent_txt)
    elif t.get("agent_s") is not None:
        time_bits.append(f"agent {_fmt_s(t['agent_s'])}s")
    elif t.get("drive_s") is not None:
        time_bits.append(f"drive {_fmt_s(t['drive_s'])}s")
    verify = t.get("grade_s", t.get("verify_s"))
    if verify is None:
        verify = verifier.get("duration_seconds")
    if verify is not None:
        time_bits.append(f"verify {verify:.0f}s"
                         if isinstance(verify, (int, float))
                         else f"verify {verify}s")
    if time_bits:
        # Same explanation as report.html's "agent time" (owner ask
        # 2026-08-06 #6): wall clock incl. editor/tool work — PostHog shows
        # LLM generation time only.
        has_agent = any(b.startswith(("agent ", "drive ")) for b in time_bits)
        note = ("  ·  wall clock incl. editor/tool work; PostHog shows LLM "
                "generation time only") if has_agent else ""
        wrapped_row("time", "  ·  ".join(time_bits) + note)
    ntools = agent.get("tool_calls", agent.get("tool_use_count"))
    if ntools is not None:
        by = agent.get("by_tool") or {}
        if by:
            top = sorted(by.items(), key=lambda kv: -kv[1])[:3]
            more = ", ..." if len(by) > 3 else ""
            row("tools", f"{ntools} ("
                + ", ".join(f"{k} x{v}" for k, v in top) + more + ")")
        else:
            row("tools", str(ntools))

    # --- per-layer status + the failing gate -------------------------------
    segs = layer_segments(layers)
    if segs:
        parts = []
        for name, word, tail in segs:
            code = {"pass": _GREEN, "FAIL": _RED,
                    "ERROR": _YELLOW}.get(word, _DIM)
            parts.append(f"{name} {_paint(word, code, color)}"
                         + (f" {tail}" if tail else ""))
        row("layers", "  ·  ".join(parts))
    gate = failing_gate(layers)
    if gate is not None:
        gname, message = gate
        wrapped_row(f"{gname} gate",
                    message if message
                    else "(layer failed; no evidence line recorded — "
                         "read the layer log)")

    # --- the per-checkpoint story ------------------------------------------
    if states:
        l2_passed = str((layers.get("L2") or {}).get("status")) == "pass"
        note = ("all green — L2 passed" if l2_passed
                else "measured states, not verdicts — the gate above decided")
        body.append(lab("checkpoints") + " " + _paint(f"({note})", _DIM, color))
        for ln in _pack(checkpoint_entries(states, l2_passed, color=color),
                        WIDTH - 2):
            body.append("  " + ln)

    # --- where things are (paths never wrapped) ----------------------------
    row("report", str(run_dir / report_name)
        + ("  (embeds the verifier report)" if verifier else ""))
    if s.get("posthog_url"):
        row("posthog", str(s["posthog_url"]))
    deliverable = None
    for sub in ("deliverable", "submission"):
        if (run_dir / sub).is_dir():
            deliverable = run_dir / sub
            break
    if deliverable is not None:
        row("agent files", str(deliverable))
    gw = s.get("graded_workdir")
    if gw:
        row("graded wd", f"{gw}  (l1_build.log / l2_pie.log under out{os.sep})")
    proj = s.get("project")
    if proj:
        row("project", f"{proj}  (left DIRTY — `cb view --graded`; close "
                       "that editor before the next eval)")
    if deliverable is not None and deliverable.name == "deliverable":
        row("re-inspect", f"cb review {run_dir}")

    # --- the box -----------------------------------------------------------
    task = s.get("task_id") or s.get("task") or verifier.get("task_id")
    title = " run summary " + (f"· {task} " if task else "")
    top = "┌─" + _paint(title, _BOLD, color) + "─" * max(0, WIDTH - 2
                                                         - len(title))
    return [top] + ["│ " + ln for ln in body] + ["└" + "─" * (WIDTH - 1)]


def card_for_run(run_dir, repo_root=None, color: Optional[bool] = None
                 ) -> List[str]:
    """The card for a run dir on disk: load the envelope (summary.json — the
    graded harness envelope — wins over result.json, same precedence as the
    report bridge), resolve checkpoint states through the guarded
    `checkpoint_states` reader, auto-detect color. [] when no envelope is readable — the
    caller prints nothing, exactly like the old recap."""
    import json
    run_dir = Path(run_dir)
    s = report_name = None
    for name in ("summary.json", "result.json"):
        try:
            s = json.loads((run_dir / name).read_text(encoding="utf-8"))
            report_name = name
            break
        except (OSError, ValueError):
            continue
    if not isinstance(s, dict):
        return []
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    states: Dict[int, object] = {}
    try:
        from aura_rig import checkpoint_states as _cs
        states = _cs.checkpoint_states(run_dir) or {}
    except Exception:  # noqa: BLE001 - a caption source must never cost a recap
        states = {}
    return render_card(s, run_dir, states=states,
                       color=supports_color() if color is None else color,
                       report_name=report_name or "summary.json")
