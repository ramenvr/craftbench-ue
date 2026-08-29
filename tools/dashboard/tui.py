"""Terminal UI for the CraftBench dashboard — a read-only Textual app.

WHY a TUI: the maintainer batches runs from a terminal and wants to watch
"which product is strong at what" land live, without leaving the shell or
spinning up a browser. This is a *viewer*: it calls
``tools.dashboard.collect.collect(repo_root)`` on a timer and repaints. It never
launches an agent, never invokes UnrealEditor, never writes the repo — every
number it shows already exists on disk (see ``collect.py`` / the data layer).

Layout (one screen, four panels):

  * a **header** band with the headline totals (tasks / runs / products / pass /
    fail / fail-no-edits / cost) and a LIVE indicator that ticks each refresh;
  * a **run MATRIX** (``DataTable``) of task rows × product columns. Each cell is
    ``n_pass/n`` plus a pass/fail glyph; the matrix is the all-attempts view
    (matching ``compare.aggregate``'s n-counting), so a re-run shows ``n>1``.
    A row whose task sits in an UNGROUNDED capability (no task in that capability
    was run by >=2 products, per ``compare.is_grounded``) is flagged ``WARN`` so a
    viewer never reads a disjoint-task row as a real comparison (open-risk #5);
  * a **FAILURES** panel — where agents go wrong — product + task + overall +
    derived blocker, newest first (the ``blocker`` is SYNTHESIZED in the data
    layer; there is no such field in the run schema);
  * a **COVERAGE** panel — capability buckets with zero runs, plus tasks not yet
    run by >=2 products (the "what hasn't been tried" view, framed as not-yet, not
    should-have, per open-risk #5);
  * a **HEAD-TO-HEAD** panel — the only true apples-to-apples comparisons: tasks
    run by >=2 products, with each product's ``n_pass/n``.

Selecting a matrix row opens a detail screen with that (task, product) run's
summary, derived blocker, per-layer L1/L2/L2I/L3/ART/R2 results, and
cost/duration. Per-layer detail is text-parsed best-effort from
``verifier_stdout.txt`` (open-risk #1) — the coarse ``overall`` is authoritative,
and the screen says so when a run has no captured layer text. ``advisory_score``
is ``null`` in every run today (verifier is null, --r2 never ran), so the UI
NEVER implies R2 ran (open-risk #2).

Refresh: ``set_interval`` re-runs ``collect()`` every ``REFRESH_SECONDS`` and
repopulates in place — live as ``runs/`` lands. ``r`` forces a refresh, ``q``
quits. ``collect()`` is always the on-demand source of truth; the timer is a
convenience (open-risk #7).

Run it::

    python3 -m tools.dashboard.tui [--repo-root <path>]

``--repo-root`` overrides the checkout root; by default it resolves to the dir
containing ``runs/`` + ``tasks/`` two levels up from this file
(``Path(__file__).resolve().parents[2]``), matching the web UI.

This module imports ``textual`` (the one UI dep) and the pure-stdlib data layer.
The data layer stays dep-free; only this file and the web app pull a UI runtime.
"""

from __future__ import annotations

import argparse
import pathlib
from typing import Callable, Dict, List, Optional, Tuple

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Static,
)

from .collect import collect
from .live import LiveRun, active_runs, tail_events
from .model import Run, Snapshot, Task

# How often the app re-runs collect() and repaints. A convenience refresher; the
# data layer's collect() is always the on-demand source of truth (open-risk #7).
REFRESH_SECONDS: float = 2.0

# Glyphs for a cell's aggregate verdict over its (task, product) attempts.
_GLYPH_PASS = "[green]✓[/]"   # every attempt passed
_GLYPH_FAIL = "[red]✗[/]"     # >=1 attempt failed (or all)
_GLYPH_MIXED = "[yellow]◐[/]"  # some passed, some failed
_GLYPH_NONE = "[dim]·[/]"      # no run for this (task, product)
_GLYPH_VOID = "[dim]∅[/]"      # runs exist but NONE was gradable

# Per-phase glyphs for the LIVE "Active runs" panel (spec §5.1 phase enum). Mirrors
# the in-Aura benchmark's TEST_STATUS_EMOJI so the live view reads familiarly.
_PHASE_GLYPH = {
    "queued": "[dim]⏳[/]",
    "launching": "[cyan]🚀[/]",
    "running": "[cyan]▶[/]",
    "grading": "[yellow]⚖[/]",
    "done": "[green]✓[/]",
    "error": "[red]✗[/]",
    "timeout": "[red]⏱[/]",
    "cancelled": "[dim]🚫[/]",
}


def _active_glyph(phase: str, stale: bool = False) -> str:
    """Glyph for a live phase; a stale running/launching row is flagged red."""
    if stale:
        return "[red]⚠[/]"
    return _PHASE_GLYPH.get(phase, f"[dim]{phase}[/]")


def _active_row_cells(r: LiveRun) -> List[str]:
    """The Active-runs DataTable cells for one live run (spec §8).

    Coarse-mode rows (step/current_tool/tool_count null) degrade to phase
    only; adapters that emit those fields show the live detail.
    """
    phase_cell = f"{_active_glyph(r.phase, r.stale)} {r.phase}"
    if r.stale:
        phase_cell += " [red](stale)[/]"
    step_cell = (
        f"{r.step}/{r.max_steps}" if r.step is not None and r.max_steps is not None
        else (str(r.step) if r.step is not None else "[dim]—[/]")
    )
    tool_cell = r.current_tool or "[dim]—[/]"
    tools_cell = str(r.tool_count) if r.tool_count is not None else "[dim]—[/]"
    if r.tokens_in is not None or r.tokens_out is not None:
        tok_cell = f"{r.tokens_in or 0}/{r.tokens_out or 0}"
    else:
        tok_cell = "[dim]—[/]"
    return [f"[b]{r.task_id}[/b]", phase_cell, tool_cell, step_cell, tools_cell, tok_cell]


def _tape_line(evt: Dict[str, object]) -> Optional[str]:
    """Render one events.jsonl event (spec §5.2) as a tool-tape line, or None to skip."""
    t = evt.get("type")
    if t == "tool_call":
        name = evt.get("tool") or "?"
        prev = evt.get("input_preview")
        tail = f" [dim]{prev}[/]" if prev else ""
        return f"  [cyan]▶[/] {name}{tail}"
    if t == "tool_result":
        ok = evt.get("ok")
        glyph = "[green]✓[/]" if ok else "[red]✗[/]"
        ms = evt.get("ms")
        prev = evt.get("output_preview")
        bits = []
        if ms is not None:
            bits.append(f"{ms}ms")
        if prev:
            bits.append(str(prev))
        tail = f" [dim]({', '.join(bits)})[/]" if bits else ""
        return f"    {glyph}{tail}"
    if t == "finish":
        fr = evt.get("finish_reason") or "?"
        return f"  [b]■ finish[/] [dim]({fr})[/]"
    if t == "phase":
        return f"  [dim]· phase → {evt.get('phase')}[/]"
    return None


# ---------------------------------------------------------------------------
# Pure helpers over a Snapshot — no Textual, easy to unit-test.
# ---------------------------------------------------------------------------


def _runs_by_task_product(snap: Snapshot) -> Dict[Tuple[str, str], List[Run]]:
    """Group all attempts by ``(task_id, product)`` for the matrix cells.

    All-attempts (no dedupe) so n matches ``compare.aggregate``'s counting; the
    cell glyph collapses the attempts into one verdict and shows ``n_pass/n``.
    """
    grouped: Dict[Tuple[str, str], List[Run]] = {}
    for r in snap.runs:
        grouped.setdefault((r.task_id, r.product), []).append(r)
    return grouped


def _cell_text(runs: List[Run]) -> str:
    """A matrix cell: ``glyph n_pass/n`` (+ ``!k`` voided), or a dim dot.

    Graded runs only in the denominator — a harness fault never reached a
    gradable state, so counting it rendered infrastructure failures as agent
    failures. But the exclusion must stay VISIBLE, or filtering just converts a
    wrong number into an invisible one:

      * no runs at all              -> ``·`` (nothing was attempted)
      * runs, but none gradable     -> ``∅ 0 !k`` (attempted, all voided)
      * both                        -> ``✓ 2/2 !1``

    The all-voided case must NOT collapse to ``·``: "every attempt here died on
    the harness" and "nobody ran this" are opposite facts.
    """
    if not runs:
        return _GLYPH_NONE
    graded = [r for r in runs if r.graded]
    n_void = len(runs) - len(graded)
    void_suffix = f" [dim]!{n_void}[/]" if n_void else ""
    if not graded:
        return f"{_GLYPH_VOID} 0{void_suffix}"
    n = len(graded)
    n_pass = sum(1 for r in graded if r.passed)
    if n_pass == n:
        glyph = _GLYPH_PASS
    elif n_pass == 0:
        glyph = _GLYPH_FAIL
    else:
        glyph = _GLYPH_MIXED
    return f"{glyph} {n_pass}/{n}{void_suffix}"


def _ungrounded_caps(snap: Snapshot) -> set:
    """Capabilities whose row aggregates disjoint tasks (compare's grounding).

    Delegated to compare via the data layer — the dashboard does no grounding
    math of its own. Falls back to an empty set if compare is unreachable so the
    TUI degrades to "nothing flagged" rather than crashing.
    """
    try:
        return set(snap.to_dict()["ungrounded_capabilities"])
    except Exception:  # pragma: no cover - compare import is the only failure mode
        return set()


def _newest_failures(snap: Snapshot) -> List[Run]:
    """Non-passing runs, newest first — the 'where agents go wrong' feed.

    Sorted by ``started_at`` descending (None sorts last). Includes both FAIL and
    FAIL_NO_EDITS; each carries a derived ``blocker`` string from the data layer.
    Non-graded runs (HARNESS-ERROR, TIMEOUT, ...) are NOT listed: this feed is
    "where agents go wrong", and a harness fault is not the agent going wrong.
    """
    import datetime as _dt

    epoch = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
    fails = [r for r in snap.runs if r.graded and not r.passed]
    return sorted(fails, key=lambda r: (r.started_at or epoch, r.run_id), reverse=True)


def _empty_capabilities(snap: Snapshot) -> List[str]:
    """Capability buckets declared by tasks but with ZERO runs."""
    run_caps = {_cap_for_task_id(snap, r.task_id) for r in snap.runs}
    return [c for c in snap.capabilities if c not in run_caps]


def _cap_for_task_id(snap: Snapshot, task_id: str) -> str:
    """Capability bucket for a task_id (via the parsed Task), else 'uncategorized'."""
    for t in snap.tasks:
        if t.task_id == task_id:
            return t.capability_bucket
    return "uncategorized"


def _tasks_undercovered(snap: Snapshot) -> List[Tuple[str, int]]:
    """Tasks run by fewer than 2 products — not yet a true head-to-head.

    Returns ``(task_id, n_products)`` for every declared task whose distinct
    product count is < 2 (0 = never run, 1 = single product). Framed as
    "not yet attempted broadly", not "should have run" (open-risk #5).
    """
    by_task: Dict[str, set] = {}
    for r in snap.runs:
        by_task.setdefault(r.task_id, set()).add(r.product)
    out: List[Tuple[str, int]] = []
    for t in snap.tasks:
        n = len(by_task.get(t.task_id, set()))
        if n < 2:
            out.append((t.task_id, n))
    return out


def _format_totals(snap: Snapshot, tick: int) -> str:
    """The header line: headline counters + a spinning LIVE indicator."""
    t = snap.totals()
    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[tick % 10]
    cost = t["total_cost_usd"]
    cost_str = f"${cost:.2f}" if cost else "n/a"
    return (
        f"[b]CraftBench[/b]  "
        f"tasks [b]{t['n_tasks']}[/b]  "
        f"runs [b]{t['n_runs']}[/b]  "
        f"products [b]{t['n_products']}[/b]  "
        f"[green]pass {t['n_pass']}[/]  "
        f"[red]fail {t['n_fail']}[/]  "
        f"[yellow]no-edits {t['n_fail_no_edits']}[/]  "
        f"cost {cost_str}  "
        f"[dim]gen {snap.generated_at}[/]  "
        f"[cyan]{spinner} LIVE[/]"
    )


# ---------------------------------------------------------------------------
# Run detail modal — opened when a matrix row is selected.
# ---------------------------------------------------------------------------


class RunDetailScreen(ModalScreen):
    """A read-only drill-down for one (task, product) cell's attempts.

    Shows every attempt's overall + derived blocker + summary + cost/duration and
    its per-layer results. Per-layer detail is best-effort text from
    ``verifier_stdout.txt`` (open-risk #1) — the screen says so when a run carries
    no captured layer text. R2/advisory is NEVER implied to have run (open-risk #2).
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    RunDetailScreen {
        align: center middle;
    }
    RunDetailScreen > VerticalScroll {
        width: 90%;
        max-width: 120;
        height: 80%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, task_id: str, product: str, runs: List[Run]) -> None:
        super().__init__()
        self._task_id = task_id
        self._product = product
        self._runs = runs

    def compose(self) -> ComposeResult:
        body = VerticalScroll()
        yield body

    def on_mount(self) -> None:
        body = self.query_one(VerticalScroll)
        body.mount(Label(f"[b]{self._task_id}[/b]  on  [b]{self._product}[/b]"))
        if not self._runs:
            body.mount(Static("[dim]No run for this task/product pair.[/]"))
            return
        for run in self._runs:
            body.mount(Static(self._render_run(run)))

    def _render_run(self, run: Run) -> str:
        verdict = (
            "[green]PASS[/]"
            if run.passed
            else f"[red]{run.overall}[/]"
        )
        when = run.started_at.strftime("%Y-%m-%d %H:%M:%SZ") if run.started_at else "?"
        dur = f"{run.duration_s:.0f}s" if run.duration_s is not None else "n/a"
        cost = f"${run.cost_usd:.4f}" if run.cost_usd is not None else "n/a"
        lines: List[str] = [
            "",
            f"[b]• {verdict}[/]  [dim]{run.run_id}[/]",
            f"  when {when}   duration {dur}   cost {cost}",
        ]
        if run.summary:
            lines.append(f"  [i]summary[/i] {run.summary}")
        if run.blocker:
            lines.append(f"  [red]blocker[/] {run.blocker}")
        if run.layer_results:
            lines.append("  [u]layers[/u]")
            for lr in run.layer_results:
                colour = {
                    "pass": "green",
                    "fail": "red",
                    "skip": "yellow",
                    "error": "red",
                    "n/a": "dim",
                }.get(lr.status, "white")
                head = f"    [{colour}]{lr.key:<4}{lr.status.upper()}[/]"
                lines.append(head)
                if lr.detail:
                    for dline in lr.detail.splitlines():
                        lines.append(f"        [dim]{dline}[/]")
        else:
            lines.append(
                "  [dim]no per-layer text captured "
                "(verifier_stdout.txt absent — overall is authoritative)[/]"
            )
        return "\n".join(lines)

    def action_dismiss(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Live tool-tape — opened when an ACTIVE run row is selected (spec §8).
# ---------------------------------------------------------------------------


class LiveTapeScreen(ModalScreen):
    """A live, incrementally-tailing tool tape for one in-flight run (spec §8).

    Reads ``runs/<id>/events.jsonl`` via ``live.tail_events`` on a timer, appending
    only events with ``seq`` greater than the last seen (the incremental tail). The
    tail source is injectable so tests drive it without disk. Read-only: it never
    writes the run dir (one-writer invariant, spec §4).
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    LiveTapeScreen {
        align: center middle;
    }
    LiveTapeScreen > VerticalScroll {
        width: 90%;
        max-width: 120;
        height: 80%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(
        self,
        run_id: str,
        run_dir: pathlib.Path,
        *,
        tail_provider: Optional[Callable[[int], List[Dict[str, object]]]] = None,
        refresh_seconds: float = 1.0,
    ) -> None:
        super().__init__()
        self._run_id = run_id
        self._run_dir = pathlib.Path(run_dir)
        # Default: tail the real events.jsonl by seq. Tests inject a fake.
        self._tail = tail_provider or (lambda after: tail_events(self._run_dir, after))
        self._refresh_seconds = refresh_seconds
        self._after_seq = 0
        # In-memory render buffer (we own it rather than reading the Static back).
        self._lines: List[str] = []

    def compose(self) -> ComposeResult:
        body = VerticalScroll()
        yield body

    def on_mount(self) -> None:
        body = self.query_one(VerticalScroll)
        body.mount(Label(f"[b]live tape[/b]  {self._run_id}"))
        body.mount(Static("", id="tape"))
        self._poll_tape()
        if self._refresh_seconds > 0:
            self.set_interval(self._refresh_seconds, self._poll_tape)

    def _poll_tape(self) -> None:
        """Append any events with seq > last-seen; advance the cursor. Read-only."""
        try:
            new_events = self._tail(self._after_seq)
        except Exception:  # pragma: no cover - keep the modal alive on a transient read error
            return
        if not new_events:
            return
        changed = False
        for evt in new_events:
            seq = evt.get("seq")
            if isinstance(seq, int) and seq > self._after_seq:
                self._after_seq = seq
            line = _tape_line(evt)
            if line is not None:
                self._lines.append(line)
                changed = True
        if changed:
            self.query_one("#tape", Static).update("\n".join(self._lines))

    def action_dismiss(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# The app.
# ---------------------------------------------------------------------------


class DashboardApp(App):
    """Live read-only CraftBench dashboard.

    Holds the current ``Snapshot`` and rebuilds the four panels from it. A
    ``set_interval`` timer re-runs ``collect(repo_root)`` and repopulates in
    place. The app NEVER writes to disk and NEVER launches a run; ``repo_root`` is
    only ever read.
    """

    TITLE = "CraftBench dashboard"
    SUB_TITLE = "read-only · live"

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    CSS = """
    #totals {
        height: 1;
        padding: 0 1;
        background: $panel;
    }
    #panels {
        height: 1fr;
    }
    #matrix-pane {
        width: 3fr;
        border: round $primary;
    }
    #side {
        width: 2fr;
    }
    .pane-title {
        text-style: bold;
        background: $boost;
        padding: 0 1;
    }
    #failures, #coverage, #headtohead {
        border: round $secondary;
        height: 1fr;
    }
    DataTable {
        height: 1fr;
    }
    #active-pane {
        height: auto;
        max-height: 11;
        border: round $accent;
    }
    #active {
        height: auto;
        max-height: 9;
    }
    """

    def __init__(
        self,
        repo_root: pathlib.Path,
        *,
        refresh_seconds: float = REFRESH_SECONDS,
        snapshot: Optional[Snapshot] = None,
        live_provider: Optional[Callable[[], List[LiveRun]]] = None,
    ) -> None:
        """``snapshot`` lets tests inject a fixed Snapshot (no disk read);
        ``live_provider`` injects the Active-runs source (default: read the live
        ``runs/*/status.json`` contract via ``live.active_runs``)."""
        super().__init__()
        self._repo_root = pathlib.Path(repo_root)
        self._refresh_seconds = refresh_seconds
        # Allow a pre-built snapshot (tests); else collect() lazily on mount.
        self._snapshot: Optional[Snapshot] = snapshot
        self._live_provider: Callable[[], List[LiveRun]] = (
            live_provider or (lambda: active_runs(self._repo_root))
        )
        self._live_runs: List[LiveRun] = []
        self._tick = 0
        # Maps a matrix DataTable row key -> (task_id, capability) so a row
        # selection can open the detail modal for the right task.
        self._row_tasks: Dict[str, Tuple[str, str]] = {}
        self._products: List[str] = []

    # -- layout -----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="totals")
        with VerticalScroll(id="active-pane"):
            yield Label("Active runs  (live)", classes="pane-title")
            yield DataTable(id="active", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="panels"):
            with VerticalScroll(id="matrix-pane"):
                yield Label("Run matrix  (task × product)", classes="pane-title")
                yield DataTable(id="matrix", cursor_type="row", zebra_stripes=True)
            with VerticalScroll(id="side"):
                yield Label("Failures  (newest first)", classes="pane-title")
                yield Static("", id="failures")
                yield Label("Coverage gaps", classes="pane-title")
                yield Static("", id="coverage")
                yield Label("Head-to-head  (shared tasks)", classes="pane-title")
                yield Static("", id="headtohead")
        yield Footer()

    def on_mount(self) -> None:
        if self._snapshot is None:
            self._snapshot = collect(self._repo_root)
        self._refresh_live()
        self._rebuild()
        if self._refresh_seconds > 0:
            self.set_interval(self._refresh_seconds, self._poll)

    # -- refresh ----------------------------------------------------------------

    def _poll(self) -> None:
        """Timer callback: re-collect + re-read live state, then repaint (read-only)."""
        try:
            self._snapshot = collect(self._repo_root)
        except Exception:  # pragma: no cover - keep the UI alive on a transient I/O error
            return
        self._refresh_live()
        self._rebuild()

    def action_refresh(self) -> None:
        """'r' — force an immediate re-collect + repaint."""
        self._poll()

    def _rebuild(self) -> None:
        """Repopulate every panel from the current Snapshot."""
        self._tick += 1
        snap = self._snapshot
        assert snap is not None
        self.query_one("#totals", Static).update(_format_totals(snap, self._tick))
        self._build_active()
        self._build_matrix(snap)
        self._build_failures(snap)
        self._build_coverage(snap)
        self._build_headtohead(snap)

    # -- active runs (live, spec §8) --------------------------------------------

    def _refresh_live(self) -> None:
        """Refresh the live Active-runs list (best-effort; never raises)."""
        try:
            self._live_runs = list(self._live_provider())
        except Exception:  # pragma: no cover - keep the UI alive on a transient read error
            self._live_runs = []

    def _build_active(self) -> None:
        """Populate the Active-runs DataTable from the current live runs."""
        table = self.query_one("#active", DataTable)
        table.clear(columns=True)
        for col in ("task", "phase", "tool", "step", "tools", "tok in/out"):
            table.add_column(col)
        for r in self._live_runs:
            table.add_row(*_active_row_cells(r), key=r.run_id)

    @on(DataTable.RowSelected, "#active")
    def _on_active_selected(self, event: DataTable.RowSelected) -> None:
        """Open the live tool-tape for the selected active run (spec §8)."""
        run_id = event.row_key.value
        if not run_id:
            return
        # Use the discovered run dir (runs may nest under a per-backend
        # folder); fall back to the flat runs/<run_id> for rows without one.
        row = next((r for r in self._live_runs if r.run_id == run_id), None)
        run_dir = (row.path if row is not None and row.path is not None
                   else self._repo_root / "runs" / run_id)
        self.push_screen(LiveTapeScreen(run_id, run_dir))

    # -- matrix -----------------------------------------------------------------

    def _build_matrix(self, snap: Snapshot) -> None:
        table = self.query_one("#matrix", DataTable)
        table.clear(columns=True)
        self._row_tasks.clear()

        products = snap.products
        self._products = products
        table.add_column("task", key="task")
        table.add_column("capability", key="cap")
        for p in products:
            # Short column label: the model suffix when present, else the slug.
            label = p.split(":", 1)[1] if ":" in p else p
            table.add_column(label, key=p)

        grouped = _runs_by_task_product(snap)
        ungrounded = _ungrounded_caps(snap)

        for t in snap.tasks:
            cap = t.capability_bucket
            cap_cell = (
                f"[yellow]{cap} WARN[/]" if cap in ungrounded else f"[dim]{cap}[/]"
            )
            row = [f"[b]{t.task_id}[/b]", cap_cell]
            for p in products:
                row.append(_cell_text(grouped.get((t.task_id, p), [])))
            row_key = t.task_id
            table.add_row(*row, key=row_key)
            self._row_tasks[row_key] = (t.task_id, cap)

    @on(DataTable.RowSelected, "#matrix")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the run-detail modal for the selected task row."""
        row_key = event.row_key.value
        if row_key is None or self._snapshot is None:
            return
        task_id, _cap = self._row_tasks.get(row_key, (row_key, ""))
        # Let the user pick which product? v1 shows ALL attempts for the task
        # across ALL products in one detail screen, grouped per run.
        runs = [r for r in self._snapshot.runs if r.task_id == task_id]
        runs.sort(key=lambda r: (r.product, r.run_id))
        product_label = ", ".join(sorted({r.product for r in runs})) or "(no runs)"
        self.push_screen(RunDetailScreen(task_id, product_label, runs))

    # -- failures ---------------------------------------------------------------

    def _build_failures(self, snap: Snapshot) -> None:
        fails = _newest_failures(snap)
        if not fails:
            self.query_one("#failures", Static).update("[green]No failing runs.[/]")
            return
        lines: List[str] = []
        for r in fails:
            when = r.started_at.strftime("%m-%d %H:%M") if r.started_at else "  ?  "
            tag = (
                "[yellow]NO-EDITS[/]"
                if r.overall.upper() == "FAIL_NO_EDITS"
                else "[red]FAIL[/]"
            )
            lines.append(
                f"[dim]{when}[/] {tag} [b]{r.task_id}[/b] [dim]on[/] {r.product}"
            )
            if r.blocker:
                blocker = r.blocker.splitlines()[0]
                if len(blocker) > 88:
                    blocker = blocker[:88] + "…"
                lines.append(f"        [dim]{blocker}[/]")
        self.query_one("#failures", Static).update("\n".join(lines))

    # -- coverage ---------------------------------------------------------------

    def _build_coverage(self, snap: Snapshot) -> None:
        lines: List[str] = []
        empty_caps = _empty_capabilities(snap)
        lines.append("[u]capabilities with 0 runs[/u]")
        if empty_caps:
            for c in empty_caps:
                lines.append(f"  [red]{c}[/]")
        else:
            lines.append("  [green]none — every capability has >=1 run[/]")

        lines.append("")
        lines.append("[u]tasks not yet run by >=2 products[/u]")
        under = _tasks_undercovered(snap)
        if under:
            for task_id, n in under:
                label = "never run" if n == 0 else f"{n} product"
                colour = "red" if n == 0 else "yellow"
                lines.append(f"  [{colour}]{task_id}[/] [dim]({label})[/]")
        else:
            lines.append("  [green]all tasks run by >=2 products[/]")
        self.query_one("#coverage", Static).update("\n".join(lines))

    # -- head-to-head -----------------------------------------------------------

    def _build_headtohead(self, snap: Snapshot) -> None:
        try:
            hh = snap.head_to_head()
        except Exception:  # pragma: no cover - compare import failure
            hh = []
        if not hh:
            self.query_one("#headtohead", Static).update(
                "[dim]No task run by >=2 products yet — no true head-to-head.[/]"
            )
            return
        lines: List[str] = []
        for row in hh:
            lines.append(f"[b]{row['task_id']}[/b] [dim]{row['capability']}[/]")
            for product, stats in sorted(row["products"].items()):
                n, n_pass = stats["n"], stats["n_pass"]
                rate = stats["pass_rate"]
                colour = "green" if n_pass == n else ("red" if n_pass == 0 else "yellow")
                lines.append(
                    f"    [{colour}]{n_pass}/{n}[/] [dim]({rate:.0%})[/] {product}"
                )
        self.query_one("#headtohead", Static).update("\n".join(lines))


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


def _default_repo_root() -> pathlib.Path:
    """The checkout root: the dir containing runs/ + tasks/ (parents[2])."""
    return pathlib.Path(__file__).resolve().parents[2]


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.dashboard.tui",
        description="Read-only live terminal dashboard over CraftBench runs/ + tasks/.",
    )
    ap.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=None,
        help="checkout root (dir containing runs/ + tasks/); defaults to parents[2].",
    )
    ap.add_argument(
        "--refresh-seconds",
        type=float,
        default=REFRESH_SECONDS,
        help=f"auto-refresh interval (default {REFRESH_SECONDS}; <=0 disables).",
    )
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root or _default_repo_root()
    app = DashboardApp(repo_root, refresh_seconds=args.refresh_seconds)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
