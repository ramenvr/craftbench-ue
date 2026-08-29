"""cb bench interactive wizard — tasks -> models -> params -> confirm.

Bare ``cb bench`` in a terminal opens this flow instead of silently launching
the flag defaults (a token spend). The wizard's job is to make the three
model-selection dimensions VISIBLE — backend, model, and each backend's naming
vocabulary — and to end by printing the exact equivalent flag command, so every
wizard run teaches the non-interactive form.

taskpicker.py's portable console idiom throughout: plain print + input() (both
injected), numbered menus, no curses/ANSI — works in Windows PowerShell and is
fully unit-testable with a scripted answer list (tests/test_benchwizard.py).
Model catalogs derive LIVE from model_keys.KEY_TO_WIRE, so a `cb sync-aura`
constants resync updates the wizard for free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from aura_rig import model_keys
from aura_rig import tasks as taskreg
from aura_rig.bench import parse_task_spec
from aura_rig.matrix import parse_models
from aura_rig.taskpicker import _read

_COST_ANCHOR = ("cost anchor: aura-product t0 ~$0.03-0.14/rep; wave1 tasks "
                "~$0.007-0.68/rep (same-task variance up to 6x)")

_TOGGLE_HINT = '  ? numbers toggle ("1 3", "2-4"), a=all, Enter=done, q=quit'


@dataclass(frozen=True)
class WizardResult:
    model: str      # exactly what --model would carry, e.g. "opus-4.8,claude-p:opus"
    task: str       # exactly what --task would carry
    repeat: int
    ceiling: int


# --------------------------------------------------------------------------- #
# Reusable console pieces                                                      #
# --------------------------------------------------------------------------- #

def _multi_select(input_fn, out, title: str, rows: List[str], *,
                  headers: Optional[Dict[int, str]] = None,
                  min_one: bool = True) -> Optional[List[int]]:
    """A [ ]/[x] checkbox list over preformatted ``rows``. One input line may
    carry many tokens split on comma/whitespace: digits toggle, 'N-M' toggles a
    range, 'a' selects all, Enter/'d' finishes, 'q' quits (returns None).
    ``headers`` maps a row index to an unnumbered group-header line printed
    above it. Returns the selected indices in row order."""
    headers = headers or {}
    picked = [False] * len(rows)
    while True:
        out("")
        out(title)
        for i, label in enumerate(rows):
            if i in headers:
                out(f" {headers[i]}")
            out(f"  {i + 1:>2}) [{'x' if picked[i] else ' '}] {label}")
        line = _read(input_fn, "Toggle/Enter: ")
        if line in ("q", "quit"):
            return None
        if line in ("", "d", "done"):
            if any(picked) or not min_one:
                return [i for i, p in enumerate(picked) if p]
            out("  ? select at least one (numbers toggle), or q=quit")
            continue
        ok = True
        for tok in re.split(r"[,\s]+", line):
            if not tok:
                continue
            m = re.fullmatch(r"(\d+)-(\d+)", tok)
            if tok == "a":
                picked = [True] * len(rows)
            elif tok.isdigit() and 1 <= int(tok) <= len(rows):
                picked[int(tok) - 1] = not picked[int(tok) - 1]
            elif m and 1 <= int(m.group(1)) <= int(m.group(2)) <= len(rows):
                for j in range(int(m.group(1)) - 1, int(m.group(2))):
                    picked[j] = not picked[j]
            else:
                ok = False
        if not ok:
            out(_TOGGLE_HINT)


def _ask_int(input_fn, out, prompt: str, default: int) -> Optional[int]:
    """Enter = default; positive int accepted; q = quit (None)."""
    while True:
        s = _read(input_fn, f"{prompt} [{default}]: ")
        if s in ("q", "quit"):
            return None
        if s == "":
            return default
        if s.isdigit() and int(s) > 0:
            return int(s)
        out("  ? a positive integer (Enter = default, q = quit)")


def _ask_yes(input_fn, out, prompt: str) -> bool:
    return _read(input_fn, prompt) in ("y", "yes")


# --------------------------------------------------------------------------- #
# Stage 1 — tasks                                                              #
# --------------------------------------------------------------------------- #

def _stage_tasks(repo: Path, input_fn, out) -> Optional[List[str]]:
    """Flat continuously-numbered checkbox list of every registered task,
    grouped by set headers. Returns the selected ids (order of the tree)."""
    sets = taskreg.discover(repo)
    if not sets:
        out("no tasks found under tasks/ (add a <id>.md to a set dir).")
        return None
    rows: List[str] = []
    headers: Dict[int, str] = {}
    ids: List[str] = []
    for set_name, items in sets.items():
        headers[len(rows)] = f"{set_name}:"
        for t in items:
            rows.append(f"{t.id:<36} {t.concept[:44]}")
            ids.append(t.id)
    sel = _multi_select(
        input_fn, out,
        'Select task(s) — numbers toggle ("1 3", "2-4"), a=all, Enter=done, q=quit',
        rows, headers=headers)
    if sel is None:
        return None
    return [ids[i] for i in sel]


# --------------------------------------------------------------------------- #
# Stage 2 — models (backend-first, loop to mix backends)                       #
# --------------------------------------------------------------------------- #

_BACKENDS: Tuple[Tuple[str, str], ...] = (
    ("aura-product", "Aura's product agent (the authentic path) — slug = bare Aura key"),
    ("claude-p", "Claude Code baseline (`claude -p`, no editor) — slug = claude-p:<model>"),
    ("openrouter", "any OpenRouter model, same baseline harness — slug = openrouter:<provider/model>"),
    ("bare", "any model, MINIMAL scaffold (our 5-tool loop, no Claude Code) — slug = bare:<provider/model>"),
)

_CLAUDE_P_ALIASES: Tuple[Tuple[str, str], ...] = (
    ("opus", "latest-opus CLI alias"),
    ("sonnet", "latest-sonnet CLI alias"),
    ("haiku", "latest-haiku CLI alias"),
)


def _claude_p_choices() -> List[str]:
    """CLI aliases + every anthropic wire id the rig knows, derived live from
    KEY_TO_WIRE (adapters/claude_p.py passes the post-colon string verbatim to
    `claude --model`, which accepts both aliases and full ids)."""
    wires = [w for w in model_keys.KEY_TO_WIRE.values() if w.startswith("claude-")]
    return [a for a, _ in _CLAUDE_P_ALIASES] + wires


def _pick_backend(input_fn, out) -> Optional[str]:
    out("")
    out("Pick a backend (you can add models from more than one):")
    for i, (name, desc) in enumerate(_BACKENDS, 1):
        out(f"  {i}) {name:<13} {desc}")
    out("     (aura-mcp / unreal-mcp: per-run via `cb eval`, not benchable)")
    while True:
        sel = _read(input_fn, "Backend [number, q=quit]: ")
        if sel in ("q", "quit"):
            return None
        if sel.isdigit() and 1 <= int(sel) <= len(_BACKENDS):
            return _BACKENDS[int(sel) - 1][0]
        out("  ? enter a number from the list (or q=quit)")


def _models_for_aura(input_fn, out) -> Optional[List[str]]:
    keys = sorted(model_keys.KEY_TO_WIRE)
    rows = [f"{k:<24} -> {model_keys.KEY_TO_WIRE[k]:<30} (slug: {k})" for k in keys]
    out("")
    out("(picks limited to known keys: an unknown bare Aura key silently falls "
        f"back to {model_keys.FALLBACK_WIRE} — served AND billed as such)")
    sel = _multi_select(input_fn, out,
                        "aura-product models — the slug is the bare Aura KEY:",
                        rows, min_one=False)
    if sel is None:
        return None
    return [keys[i] for i in sel]


def _models_for_claude_p(input_fn, out) -> Optional[List[str]]:
    choices = _claude_p_choices()
    n_alias = len(_CLAUDE_P_ALIASES)
    rows = [f"{a:<28} {d:<22} (slug: claude-p:{a})" for a, d in _CLAUDE_P_ALIASES]
    rows += [f"{w:<28} {'':<22} (slug: claude-p:{w})" for w in choices[n_alias:]]
    sel = _multi_select(input_fn, out,
                        "claude-p models — the slug is claude-p:<model> "
                        "(passed verbatim to `claude --model`):",
                        rows, min_one=False)
    if sel is None:
        return None
    picked = [choices[i] for i in sel]
    extra = _read(input_fn, "other claude model id (Enter to skip): ")
    if extra in ("q", "quit"):
        return None
    if extra:
        picked.append(extra)
    # never a bare `claude-p` — an unpinned slug runs the session default model
    return [f"claude-p:{m}" for m in picked]


def _models_for_openrouter(input_fn, out) -> Optional[List[str]]:
    sugg = [w for w in model_keys.KEY_TO_WIRE.values() if "/" in w]
    rows = [f"{w:<32} (slug: openrouter:{w})" for w in sugg]
    sel = _multi_select(input_fn, out,
                        "openrouter models — the slug is openrouter:<provider/model> "
                        "(needs OPENROUTER_API_KEY):",
                        rows, min_one=False)
    if sel is None:
        return None
    picked = [sugg[i] for i in sel]
    while True:
        extra = _read(input_fn, "other <provider/model> id (Enter to skip): ")
        if extra in ("q", "quit"):
            return None
        if extra == "":
            break
        if "/" in extra:
            picked.append(extra)
            break
        out("  ? OpenRouter ids are <provider>/<model> (e.g. openai/gpt-5)")
    return [f"openrouter:{m}" for m in picked]


def _models_for_bare(input_fn, out) -> Optional[List[str]]:
    """Same id space as openrouter — the difference is the SCAFFOLD, not the model.

    ``bare:`` runs our own minimal 5-tool loop; ``openrouter:`` runs the Claude
    Code CLI pointed at the same endpoint. Picking the same model under both is
    the intended way to measure what the agent harness itself is worth.
    """
    sugg = [w for w in model_keys.KEY_TO_WIRE.values() if "/" in w]
    rows = [f"{w:<32} (slug: bare:{w})" for w in sugg]
    sel = _multi_select(input_fn, out,
                        "bare models — minimal scaffold, slug is "
                        "bare:<provider/model> (needs OPENROUTER_API_KEY):",
                        rows, min_one=False)
    if sel is None:
        return None
    picked = [sugg[i] for i in sel]
    while True:
        extra = _read(input_fn, "other <provider/model> id (Enter to skip): ")
        if extra in ("q", "quit"):
            return None
        if extra == "":
            break
        if "/" in extra:
            picked.append(extra)
            break
        out("  ? ids are <provider>/<model> (e.g. openai/gpt-5)")
    return [f"bare:{m}" for m in picked]


_BACKEND_PICKERS = {
    "aura-product": _models_for_aura,
    "claude-p": _models_for_claude_p,
    "openrouter": _models_for_openrouter,
    "bare": _models_for_bare,
}


def _stage_models(input_fn, out) -> Optional[List[str]]:
    """Backend menu -> per-backend checkbox list, looping so a mixed-backend
    comparison composes in one pass. Returns ordered, deduped slugs."""
    picked: List[str] = []
    while True:
        backend = _pick_backend(input_fn, out)
        if backend is None:
            return None
        got = _BACKEND_PICKERS[backend](input_fn, out)
        if got is None:
            return None
        for slug in got:
            if slug not in picked:
                picked.append(slug)
        out("")
        out("models so far: " + (", ".join(picked) or "(none)"))
        if not picked:
            out("  ? pick at least one model (or q at the backend menu to quit)")
            continue
        if not _ask_yes(input_fn, out, "Add models from another backend? [y/N]: "):
            return picked


# --------------------------------------------------------------------------- #
# Stage 3 — params, Stage 4 — confirm, and the wizard itself                   #
# --------------------------------------------------------------------------- #

def _stage_params(n_models: int, default_ceiling: int,
                  input_fn, out) -> Optional[Tuple[int, int]]:
    out("")
    why = (">1 model -> head-to-head comparison" if n_models > 1
           else "single model -> cost/variance spread")
    repeat = _ask_int(input_fn, out,
                      f"--repeat  reps per (model, task) pair ({why})",
                      1 if n_models > 1 else 3)
    if repeat is None:
        return None
    ceiling = _ask_int(input_fn, out,
                       "--ceiling agent wall-clock ceiling, seconds", default_ceiling)
    if ceiling is None:
        return None
    return repeat, ceiling


def run_wizard(repo: Path,
               input_fn: Callable[[str], str] = input,
               out: Callable[[str], None] = print,
               *,
               preset_model: Optional[str] = None,
               preset_task: Optional[str] = None,
               default_ceiling: int = 900) -> Optional[WizardResult]:
    """The whole flow. ``preset_model``/``preset_task`` non-None skip that stage
    (the flag was given explicitly — `--wizard` with partial flags). Returns
    None on quit at any stage or a declined confirm."""
    out("")
    out("=== cb bench wizard ===  (q quits at any prompt; explicit --model/--task skip stages)")
    if preset_task:
        out(f"using --task {preset_task} (given)")
        task_str = preset_task
    else:
        task_ids = _stage_tasks(repo, input_fn, out)
        if task_ids is None:
            return None
        task_str = ",".join(task_ids)
    if preset_model:
        out(f"using --model {preset_model} (given)")
        model_str = preset_model
    else:
        models = _stage_models(input_fn, out)
        if models is None:
            return None
        model_str = ",".join(models)
    # Round-trip through THE parsers (matrix.parse_models / bench.parse_task_spec)
    # so the wizard can never emit something the downstream flow reads differently.
    n_models = len(parse_models(model_str))
    params = _stage_params(n_models, default_ceiling, input_fn, out)
    if params is None:
        return None
    repeat, ceiling = params
    task_specs = parse_task_spec(task_str, repeat)
    cells = n_models * sum(n for _, n in task_specs)
    out("")
    out("-" * 60)
    out("equivalent command:")
    out(f"  cb bench --model {model_str} --task {task_str} "
        f"--repeat {repeat} --ceiling {ceiling}")
    out(f"grid: {n_models} model(s) x {len(task_specs)} task(s) x {repeat} rep(s) "
        f"= {cells} cell(s)")
    out(_COST_ANCHOR)
    out("-" * 60)
    if not _ask_yes(input_fn, out, "Run it? SPENDS tokens [y/N]: "):
        out("declined — copy the command above to run it later.")
        return None
    return WizardResult(model=model_str, task=task_str, repeat=repeat, ceiling=ceiling)
