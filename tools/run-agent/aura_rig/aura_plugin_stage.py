"""Temporarily enable the Aura plugin in a substrate ``.uproject``.

WHY THIS EXISTS. ``aura-mcp`` had never produced a single graded run — 0 on disk,
and its bring-up always died on ``:30010 did not come back within 480s``. Measured
2026-08-18: the editor's own log from a failed attempt mentions ``Aura`` and
``RemoteControl`` **zero** times, so it never loaded them. ``:30010`` is served by
the stock RemoteControl plugin, which reaches the project only as an Aura
*dependency* — so with Aura absent from the ``.uproject`` the port can never bind
and the lane is structurally dead. Enabling Aura binds it in **~5s** (39 log
mentions), so this was one missing line of config, not a slow cold start.

WHY IT IS STAGED RATHER THAN COMMITTED. The ``.uproject`` is part of the GRADED
SUBSTRATE. Committing an Aura entry would change the substrate every other lane is
measured against — `bare`, `claude-p`, `openrouter` and `unreal-mcp` all grade a
tree materialized from git HEAD — and would put every previously recorded run in a
different substrate generation than every future one. Staging it for the duration of
the drive and restoring afterwards keeps the committed substrate byte-identical, so
aura-mcp results stay comparable with runs recorded before this existed.

This mirrors the fairness staging in ``run.py`` (hide the answer key, restore it
after), including its failure posture: restoration happens in a ``finally``, and a
crashed drive leaves the substrate dirty exactly the way a crashed fairness stage
does — which the batch runner's ``heal_substrate`` already repairs.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Optional

#: The plugin to stage, and the one it transitively provides. RemoteControl is NOT
#: added directly: it arrives through Aura's dependency list, and adding it
#: separately would mask the real requirement if Aura's dependencies ever change.
AURA_PLUGIN = "Aura"


@contextmanager
def aura_enabled(uproject: Path, log: Optional[Callable[[str], None]] = None):
    """Ensure ``Aura`` is enabled in ``uproject`` for the duration of the block.

    A no-op when it is already present, so this is safe to wrap around a project
    that lists Aura for its own reasons — and in that case nothing is restored,
    because nothing was changed.
    """
    say = log or (lambda _m: None)
    uproject = Path(uproject)
    try:
        original = uproject.read_text(encoding="utf-8")
        spec = json.loads(original)
    except Exception as exc:  # noqa: BLE001
        # Fail OPEN: a project we cannot parse is not one to rewrite. The drive then
        # fails at the readiness gate with its own clear message rather than here
        # with a confusing one.
        say(f"  WARN  could not read {uproject.name} to stage Aura ({exc}); "
            f"continuing unstaged")
        yield False
        return

    plugins = spec.get("Plugins") or []
    if any((p or {}).get("Name") == AURA_PLUGIN for p in plugins):
        yield False
        return

    spec["Plugins"] = list(plugins) + [{"Name": AURA_PLUGIN, "Enabled": True}]
    uproject.write_text(json.dumps(spec, indent=4) + "\n", encoding="utf-8")
    say(f"  ..    staged {AURA_PLUGIN} into {uproject.name} "
        f"(brings RemoteControl -> :30010; restored after the drive)")
    try:
        yield True
    finally:
        # Restore the EXACT original bytes, not a re-serialisation: re-dumping JSON
        # would silently reformat a committed file and show up as a dirty substrate
        # on every run.
        try:
            uproject.write_text(original, encoding="utf-8")
            say(f"  ..    restored {uproject.name}")
        except Exception as exc:  # noqa: BLE001
            say(f"  WARN  FAILED to restore {uproject}: {exc} — "
                f"run `git checkout -- {uproject}` before the next graded run")
