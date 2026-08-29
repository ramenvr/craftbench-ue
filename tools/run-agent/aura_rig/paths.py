"""paths — THE single resolver for CraftBench's machine-local directory roots.

Phase A (final structure): every out-of-repo directory the rig creates hangs
off ONE machine root, ``CB_ROOT`` (default ``C:\\cb`` on Windows, ``~/cb``
elsewhere)::

    <CB_ROOT>/wd                         verifier workdirs (SHORT: MAX_PATH dodge)
    <CB_ROOT>/scratch/CraftBenchGraded   graded-drive scratch project
    <CB_ROOT>/scratch/CraftBenchScratch  headless-drive playground

Back-compat contract: the OLD env overrides keep working —
``CRAFTBENCH_WD_ROOT`` (workdirs), ``CB_GRADED_PROJECT`` (graded scratch),
``CB_DRIVE_PROJECT`` (playground; resolved in :mod:`aura_rig.stack`) — only
the DEFAULTS changed. The old defaults are RETIRED: ``C:\\cbwd`` and the
LOCALAPPDATA / XDG-cache ``CraftBench/scratch`` tree are no longer produced;
a machine that relied on them either sets the env override or migrates its
dirs under ``CB_ROOT``.

``cb where`` prints every resolved dir (read-only); ``cb where --link`` drops
gitignored ``<repo>/.cb/{wd,scratch}`` links at the repo root so the machine
dirs are one click away from the checkout.

This module is deliberately tiny and stdlib-only — everyone (stack, driver,
batch_eval, graded_scratch, cb) imports FROM here; nobody re-derives a root.
"""
from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

__all__ = ["cb_root", "wd_root", "scratch_root", "graded_project_dir",
           "tmp_scratch_roots"]


def _is_windows_family() -> bool:
    """Windows-family host detection, mirroring l2_pie._editor_binary: a
    Git-Bash / Cygwin / MSYS / MinGW python reports os.name == "posix" but
    platform.system() like "MSYS_NT-10.0" — still a Win64 host where the
    SHORT ``C:\\cb`` default (MAX_PATH dodge) is the right choice; an MSYS
    home path like C:\\msys64\\home\\<user>\\cb would defeat it."""
    return (
        platform.system().lower().startswith(("win", "cygwin", "msys", "mingw"))
        or os.name == "nt"
    )


def cb_root() -> Path:
    """The ONE machine-local root every rig dir hangs off.

    Precedence: env ``CB_ROOT`` → ``C:\\cb`` (Windows-family host) / ``~/cb``
    (POSIX). Deliberately SHORT on Windows (UE build paths under it must stay
    inside the 260-char MAX_PATH limit) and outside any synced/OneDrive tree."""
    env = os.environ.get("CB_ROOT")
    if env:
        return Path(env)
    if _is_windows_family():
        return Path(r"C:\cb")
    return Path.home() / "cb"


def wd_root() -> Path:
    """Root for the SHORT per-run verifier workdirs.

    Precedence: env ``CRAFTBENCH_WD_ROOT`` (back-compat override) →
    ``cb_root()/wd``. (Old default ``C:\\cbwd`` is retired.)"""
    env = os.environ.get("CRAFTBENCH_WD_ROOT")
    if env:
        return Path(env)
    return cb_root() / "wd"


def tmp_scratch_roots() -> "list[Path]":
    r"""DEDICATED temp scratch roots that hold harness workdirs, for cleanup.

    Why this exists: on a Windows host whose profile carries an 8.3 short name
    (``C:\Users\SHORT~1\...``) the L2 leg cannot retrieve its automation result
    under a short ``-ReportExportPath``, so every task scored FAIL -- the 0/15
    batch of 2026-07-25. ``envgate``'s documented remediation is to point
    TEMP+TMP at a short, tilde-free root (``set TEMP=C:\cbtmp``). Once an
    operator does that, every ``tempfile.mkdtemp()`` in the rig lands under
    ``C:\cbtmp`` instead of :func:`wd_root` -- and ``cb clean --workdirs``,
    which only ever walked :func:`wd_root`, could not see a byte of it. On
    2026-08-20 that blind spot had grown to ~95 GB: one 2.4 GB ``SharedPCH`` per
    staged workdir, 44 copies of the same file.

    DELIBERATELY NOT the bare :func:`tempfile.gettempdir`. The sweep deletes
    whole child directories, and the system temp is shared with pip, the OS and
    every other tool on the box -- enumerating it as a workdir root would put
    unrelated data one age-check away from deletion. Only roots that exist to
    hold rig scratch are returned:

    * ``CB_TMP`` when EXPLICITLY set (an operator naming a scratch dir),
    * ``C:\cbtmp`` -- the root ``envgate`` tells operators to use -- if present,
    * a live ``TEMP``/``TMP`` whose leaf name is itself ``cbtmp``.

    Callers must still pass ``require_project_shape=True`` for these roots: a
    hand-set ``CB_TMP`` may point somewhere shared, and shape ("does this child
    contain a ``.uproject``?") is the only check that survives that mistake.
    """
    roots = []  # type: list[Path]
    try:
        sys_tmp = Path(tempfile.gettempdir()).resolve()
    except OSError:
        sys_tmp = None

    def _add(cand):
        try:
            rp = Path(cand).resolve()
        except OSError:
            return
        # never the bare system temp -- see the docstring
        if sys_tmp is not None and rp == sys_tmp:
            return
        if rp not in roots:
            roots.append(rp)

    env = os.environ.get("CB_TMP")
    if env:
        _add(env)
    if _is_windows_family():
        cbtmp = Path(r"C:\cbtmp")
        if cbtmp.is_dir():
            _add(cbtmp)
    # A TEMP override only counts when it is plainly a dedicated rig root.
    for var in ("TEMP", "TMP"):
        val = os.environ.get(var)
        if not val:
            continue
        try:
            cand = Path(val).resolve()
        except OSError:
            continue
        if cand.name.lower() in ("cbtmp", "cb-tmp"):
            _add(cand)
    return roots


def scratch_root() -> Path:
    """Parent of the out-of-repo scratch PROJECTS (graded + playground):
    ``cb_root()/scratch``. (Old LOCALAPPDATA / XDG-cache default retired.)"""
    return cb_root() / "scratch"


def graded_project_dir(explicit: str = "") -> Path:
    """The graded-drive scratch project dir.

    Precedence: ``explicit`` arg → env ``CB_GRADED_PROJECT`` (back-compat
    override) → ``scratch_root()/CraftBenchGraded``."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("CB_GRADED_PROJECT")
    if env:
        return Path(env)
    return scratch_root() / "CraftBenchGraded"
