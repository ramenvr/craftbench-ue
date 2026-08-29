"""Load the repo's ``.env`` into ``os.environ`` for the verifier's own tuning vars.

**Why this module exists.** `cb` fronts every eval-family command with
``aura_rig.stack.load_aura_env``, which exports the ``CRAFTBENCH_*`` build-tuning
values from ``craftbench/.env`` before the verifier subprocess is spawned. But
the no-cb path and README both document a deliberate **no-cb
grade path** — ``python3 tools/verify-single/run_task.py --task … --submission …
--ue-root …`` — and that path had none of the guardrails: nothing read ``.env``,
so ``CRAFTBENCH_L1_MAX_PARALLEL`` never applied and full-parallelism editor-PCH
compiles exhausted the commit charge on a 32 GB box → reproducible ``C3859`` /
exit 6, while every cb-fronted invocation of the same grade passed
(FAILURE-LOG 2026-07-10 for the C3859 class; the documented-path gap found
2026-07-25).

Per the FAILURE-LOG closure doctrine the fix is the loader, not a README
sentence telling the operator to remember an env prefix.

**Precedence.** An env var the operator set explicitly ALWAYS wins — this only
fills in what is unset or blank. That keeps ``CRAFTBENCH_L1_MAX_PARALLEL=8
python3 run_task.py …`` a working one-off override, and keeps the rig's own
pre-exported values authoritative when it shells out to us.

**Scope.** Only the ``CRAFTBENCH_`` namespace, which is the verifier's own:
``ALLOW_UBA``, ``GOVERN_RESOURCES``, ``L1_MAX_PARALLEL``, ``L1_MEM_MB``,
``L1_TIMEOUT``, ``L2_MEM_MB``, ``SANITY_OK``, ``SUBSTRATE_FROM_LIVE``,
``UE_ROOT``. The prefix is matched rather than a hand-listed set so a new
tuning var works here the day it is read — no second registry to drift. Aura
creds, Supabase keys and rig layout vars are deliberately NOT loaded: they are
the rig's business and the verifier core must stay runnable with no rig.

This module is dependency-free on purpose (``tools/verify-single`` is the lower
layer; run-agent imports it, never the reverse).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Optional

#: Only variables in this namespace are loaded (see module docstring).
ENV_PREFIX = "CRAFTBENCH_"


def dotenv_value(raw: str) -> str:
    """Dotenv semantics for the text after ``KEY=``.

    A double-quoted value ends at its closing quote (a ``#`` INSIDE the quotes
    is part of the value); an unquoted value ends at the first
    whitespace-then-``#`` (inline comment). ``CRAFTBENCH_L1_MAX_PARALLEL=2
    # tested up to 4`` must yield ``2``, not ``2 # tested up to 4`` — that exact
    line silently dropped the cap once already (FAILURE-LOG 2026-07-24), and
    ``AURA_PASSWORD="secret" # note`` cost a Supabase invalid-credentials wall
    the same day.

    Kept in lockstep with ``aura_rig.stack._dotenv_value`` (the rig-side copy
    that cannot import this tree); ``tests/test_repo_env.py`` asserts the two
    agree line-for-line on a shared table of tricky inputs.
    """
    v = raw.strip()
    if v.startswith('"'):
        end = v.find('"', 1)
        if end != -1:
            return v[1:end]
        return v.strip('"')  # unterminated quote: legacy behavior
    return re.split(r"\s#", v, maxsplit=1)[0].strip()


def parse_dotenv(text: str, prefix: str = ENV_PREFIX) -> Dict[str, str]:
    """``{KEY: value}`` for every non-empty ``prefix``-namespaced assignment.

    Commented-out lines (``#CRAFTBENCH_ALLOW_UBA=1``, the shape ``.env.example``
    ships) are skipped — a commented default must not become an active one.
    Later assignments win, matching dotenv's last-write semantics.
    """
    found: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, rest = stripped.partition("=")
        key = key.strip()
        if not key.startswith(prefix):
            continue
        value = dotenv_value(rest)
        if value:
            found[key] = value
    return found


def load_repo_env(repo_root: Path, *, env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Export ``<repo_root>/.env``'s ``CRAFTBENCH_*`` values; return what was applied.

    Best-effort and never raises: a missing or unreadable ``.env`` is a no-op
    (the verifier must grade on a box that has none). Already-set, non-blank
    variables are left alone and reported in the return value's absence.
    """
    target = os.environ if env is None else env
    dotenv = Path(repo_root) / ".env"
    try:
        text = dotenv.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    applied: Dict[str, str] = {}
    for key, value in parse_dotenv(text).items():
        if (target.get(key) or "").strip():
            continue  # explicit env wins
        target[key] = value
        applied[key] = value
    return applied
