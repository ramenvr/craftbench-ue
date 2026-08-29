"""Interactive task picker for ``cb tasks`` — browse sets -> tasks -> detail -> run.

A portable numbered-menu loop: works in any terminal including Windows PowerShell
(where ``curses`` isn't bundled) and is pipe-safe. Data comes from :mod:`aura_rig.tasks`;
this module is just the console flow. ``input_fn``/``out`` are injected so the whole
flow is unit-testable with a scripted input sequence.

:func:`pick` returns the chosen task id (to hand to ``cb eval --task <id>``), or
``None`` if the user quit without choosing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from aura_rig import tasks as taskreg

# _pick_task sentinels: None = quit the picker, "" = back to the set list.
_BACK = ""


def _menu(out: Callable[[str], None], title: str, rows: List[str]) -> None:
    out("")
    out(title)
    for i, label in enumerate(rows, 1):
        out(f"  {i:>2}) {label}")


def _read(input_fn, prompt: str) -> str:
    """Read one answer, normalized. Treats EOF / Ctrl-C as 'q' (quit cleanly instead
    of a traceback), and tolerates piped stdin that arrives NUL/BOM-decorated so
    non-tty input still works. PowerShell prepends a UTF-8 BOM (EF BB BF) to piped
    stdin; Python sees it as ``\\ufeff`` (utf-8 stdin) or the mojibake ``ï»¿`` (cp1252
    stdin) — strip either, plus any UTF-16 BOM / interleaved NULs, before parsing.

    NB: benchwizard.py imports this — the Windows input normalization has ONE
    home. Keep it importable if you rename/refactor."""
    try:
        s = input_fn(prompt)
    except (EOFError, KeyboardInterrupt):
        return "q"
    s = s.replace("\x00", "")
    for bom in ("﻿", "ï»¿", "\xff\xfe", "\xfe\xff"):
        while s.startswith(bom):
            s = s[len(bom):]
    return s.strip().lower()


def _ask_index(input_fn, out, prompt, n, *, allow_back):
    """Return a 1..n int, or 'q'/'b' (b only when allow_back), reprompting on junk."""
    while True:
        sel = _read(input_fn, prompt)
        if sel in ("q", "quit"):
            return "q"
        if allow_back and sel in ("b", "back", ""):
            return "b"
        if not allow_back and sel == "":
            return "q"
        if sel.isdigit() and 1 <= int(sel) <= n:
            return int(sel)
        out("  ? enter a number from the list" + (" (or b=back, q=quit)" if allow_back
                                                  else " (or q=quit)"))


def _confirm_run(t: taskreg.TaskInfo, input_fn, out) -> bool:
    """Show the task detail and ask to run it. True = run, False = back to the list."""
    out("")
    out(f"  {t.id}   [{t.set_name}]")
    if t.title and t.title != t.id:
        out(f"    title   : {t.title}")
    if t.concept:
        out(f"    concept : {t.concept}")
    if t.layers:
        out(f"    layers  : {t.layers}")
    if t.prompt_preview:
        out(f"    prompt  : {t.prompt_preview}")
    out(f"    run     : cb eval --task {t.id}")
    ans = _read(input_fn, "Run this? brings up the stack + spends tokens [y/N]: ")
    return ans in ("y", "yes")


def _pick_task(items: List[taskreg.TaskInfo], input_fn, out) -> Optional[str]:
    """Within one set: list tasks, show detail, confirm. Returns an id (run), ``_BACK``
    (back to sets), or ``None`` (quit)."""
    while True:
        _menu(out, f"{items[0].set_name} ({len(items)} tasks):",
              [f"{t.id:<36} {t.concept[:44]}" for t in items])
        choice = _ask_index(input_fn, out, "Select a task [number, b=back, q=quit]: ",
                            len(items), allow_back=True)
        if choice == "q":
            return None
        if choice == "b":
            return _BACK
        t = items[choice - 1]
        if _confirm_run(t, input_fn, out):
            return t.id
        # not confirmed -> re-list the tasks in this set


def pick(repo: Path, input_fn: Callable[[str], str] = input,
         out: Callable[[str], None] = print) -> Optional[str]:
    """Browse sets -> tasks -> detail and return the chosen task id, or None if quit."""
    sets = taskreg.discover(repo)
    if not sets:
        out("no tasks found under tasks/ (add a <id>.md to a set dir).")
        return None
    names = list(sets.keys())
    while True:
        _menu(out, "CraftBench task sets:",
              [f"{n:<14} ({len(sets[n])} tasks)" for n in names])
        choice = _ask_index(input_fn, out, "Select a set [number, q=quit]: ",
                            len(names), allow_back=False)
        if choice == "q":
            return None
        chosen = _pick_task(sets[names[choice - 1]], input_fn, out)
        if chosen is None:        # quit
            return None
        if chosen == _BACK:       # back to the set list
            continue
        return chosen             # an id to run
