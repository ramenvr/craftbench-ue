"""Shared machinery for authoring discrimination variants inside a UE editor.

VERIFIER-SIDE tooling. Never shipped to agents, never graded. Imported by the
per-task ``aids/author_variants.py`` scripts, which run headless via
``UnrealEditor-Cmd -ExecutePythonScript=<script> -nullrhi -unattended -nosplash``.

Three things are identical for every variant and each is easy to get subtly wrong
per task: reusing a task's own ``author_reference.py`` without executing its
``main()``, deciding whether a graded leg may be harvested, and copying the saved
assets out. They live here once, tested.

Nothing here imports ``unreal`` — the caller is already inside the editor and passes
in what it needs. That is what makes this file unit-testable off-box.
"""
from __future__ import annotations

import os
import shutil


class AuthoringError(RuntimeError):
    """A refusal. Callers print it and abort the leg rather than harvest."""


# --------------------------------------------------------------------------- #
# 1. Load a task's reference author WITHOUT running it
# --------------------------------------------------------------------------- #

def load_reference_helpers(path, required_names=(), namespace_name="__cb_author_helpers__"):
    """Exec ``author_reference.py`` for its helpers only; never run its ``main()``.

    Returns the resulting namespace dict.

    Two tail shapes exist in the corpus and both are handled: a bare trailing
    ``main()`` call (stripped) and an ``if __name__ == "__main__":`` guard (inert,
    because the exec namespace is deliberately not named ``__main__``). An
    unrecognised tail RAISES rather than being exec'd blind — authoring a reference
    over a variant needs a git checkout to undo.

    Raises ``AuthoringError`` on a missing file, an unrecognised tail, or any name in
    ``required_names`` being absent afterwards.
    """
    if not os.path.isfile(path):
        raise AuthoringError("reference author not found at %s" % path)
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise AuthoringError("reference author %s is empty" % path)

    # ORDER MATTERS, and getting it wrong is not a subtle failure. A guarded file
    # ends with an INDENTED `main()` inside the guard body, so a check on
    # `lines[-1].strip()` matches it too — popping that line leaves a dangling
    # `if __name__ == "__main__":` and the exec dies with IndentationError.
    # (Caught by tests/test_cb_variant_lib.py the first time this ran.) So:
    # recognise the guard FIRST, and only ever strip a call at column zero.
    if _has_main_guard(lines):
        # Shape B: nothing to strip. The guard is inert because the exec
        # namespace below is deliberately not named __main__.
        pass
    elif lines[-1].rstrip() == "main()":
        # Shape A: an unindented module-level call. Strip exactly that line.
        lines.pop()
    else:
        # Neither shape. Refuse rather than exec something whose side effects
        # are unknown — authoring a reference over a variant is unrecoverable
        # without a git checkout.
        raise AuthoringError(
            "reference author %s ends in neither a bare main() call nor an "
            "`if __name__ == \"__main__\":` guard (last line %r) — refusing to "
            "exec it blind" % (path, lines[-1].strip()))

    ns = {"__name__": namespace_name, "__file__": path}
    exec(compile("\n".join(lines) + "\n", path, "exec"), ns)  # noqa: S102
    missing = [n for n in required_names if n not in ns]
    if missing:
        raise AuthoringError(
            "%s no longer defines %s" % (path, ", ".join(repr(m) for m in missing)))
    return ns


def _has_main_guard(lines):
    for line in lines:
        s = line.strip().replace("'", '"')
        if s.startswith("if __name__ ==") and '"__main__"' in s:
            return True
    return False


# --------------------------------------------------------------------------- #
# 2. Decide whether a graded leg may be harvested
# --------------------------------------------------------------------------- #

def acceptance(vector, target, substring, cascades=()):
    """Return ``(ok, reason)`` for one graded variant.

    ``vector`` maps check-id -> ``(passed, detail)``, the shape every
    ``grade_in_process()`` in this repo returns.

    The criterion is EQUALITY between the observed failure set and the set the leg's
    design predicts (``{target} | cascades``), not membership: a leg that also fails
    something unforeseen is credited at the MATRIX's substring while actually dying
    elsewhere, which reads identically to a clean isolation.

    ``cascades`` exists because some graders fan out by design — ``kp_anim_track_bake``
    check 5 reports "(check 4 failed)" whenever check 4 fails, so no leg can isolate
    check 4 alone and refusing those would mean never probing them. Declaring a
    cascade keeps the check exact; an UNDECLARED extra failure is still a refusal.
    """
    if target not in vector:
        return False, ("target check %r is not in the grader's vector (have: %s)"
                       % (target, ", ".join(sorted(vector))))
    unknown = [c for c in cascades if c not in vector]
    if unknown:
        return False, ("declared cascade(s) %s are not in the grader's vector — a "
                       "renamed check would otherwise silently widen what this leg "
                       "is allowed to fail" % sorted(unknown))
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    expected = sorted({target} | set(cascades))
    if fails != expected:
        return False, ("wanted exactly %s, got %s" % (expected, fails))
    detail = vector[target][1]
    if substring not in detail:
        return False, ("isolates %s, but its detail %r does not contain the "
                       "substring the MATRIX will credit (%r) — harvesting this "
                       "would create a wrong-reason credit"
                       % (target, detail, substring))
    return True, "isolates %s and credits %r" % (target, substring)


def score(vector):
    """``(passed, total)`` for logging."""
    total = len(vector)
    return total - sum(1 for _, (ok, _) in vector.items() if not ok), total


# --------------------------------------------------------------------------- #
# 3. Harvest saved assets into a variant overlay
# --------------------------------------------------------------------------- #

def grade_vector(grader_path, marker="CRAFTBENCH-INTROSPECT-JSON"):
    """Run a verifier introspect grader IN-PROCESS; return ``{cid: (passed, detail)}``.

    For tasks whose ``author_reference.py`` cannot supply this — most expose
    ``grade_in_process()`` returning exactly this vector, but ``kp-anim-track-bake``'s
    ``self_grade()`` returns a bool and dies unless the score is perfect, which a
    variant can never be.

    Two details are load-bearing: ``__name__`` must NOT be ``"__main__"`` or the
    grader's entry guard fires and its verdict block goes to the real stdout instead
    of the captured buffer; and the return shape is the vector dict, not the raw
    ``checks`` list.

    Never raises on grader trouble — returns ``(None, reason)`` so a caller refuses
    one leg instead of aborting the boot.
    """
    import contextlib
    import io
    import json
    import re

    if not os.path.isfile(grader_path):
        return None, "grader not found at %s" % grader_path
    try:
        src = io.open(grader_path, encoding="utf-8").read()
    except OSError as e:
        return None, "grader unreadable: %r" % (e,)
    buf = io.StringIO()
    ns = {"__name__": "__cb_selfgrade__", "__file__": grader_path}
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(src, grader_path, "exec"), ns)  # noqa: S102 verifier-owned
            if "main" not in ns:
                return None, "grader defines no main()"
            ns["main"]()
    except Exception as e:  # noqa: BLE001
        return None, "grader raised %r" % (e,)
    m = re.search(re.escape(marker) + r"-START\s*\n(.*?)\n\s*"
                  + re.escape(marker) + r"-END", buf.getvalue(), re.S)
    if m is None:
        return None, "grader produced no %s block" % marker
    try:
        checks = json.loads(m.group(1))["checks"]
        return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}, None
    except Exception as e:  # noqa: BLE001
        return None, "unparseable verdict block %r" % (e,)


def call_with_rebound_globals(ns, fn_name, **rebinds):
    """Call ``ns[fn_name]()`` with some of its module globals temporarily changed.

    Several reference authors own a proven ``harvest()`` that walks the substrate into
    a module-level destination constant; a variant needs that same walk with a
    different destination. For a LEVEL task the walk must also cover the
    One-File-Per-Actor prefixes (``__ExternalActors__``, ``__ExternalObjects__``), and
    a reimplementation that misses one yields a level whose ACTORS are silently
    absent — which grades as a different failure than intended.

    Functions resolve globals through ``__globals__`` at call time and the exec'd
    namespace IS that dict, so rebinding here is visible to the callee. Restored even
    on exception. Rebinding a name that does not exist RAISES, so a renamed constant
    cannot be silently ignored.
    """
    if fn_name not in ns:
        raise AuthoringError("namespace does not define %r" % fn_name)
    missing = [k for k in rebinds if k not in ns]
    if missing:
        raise AuthoringError(
            "cannot rebind %s — not defined in the namespace (a renamed constant "
            "would otherwise be silently ignored and the harvest would write to "
            "the reference directory)" % ", ".join(repr(m) for m in sorted(missing)))
    saved = {k: ns[k] for k in rebinds}
    ns.update(rebinds)
    try:
        return ns[fn_name]()
    finally:
        ns.update(saved)


def harvest(task_dir, variant, task_id, asset_names, substrate_task_dir,
            content_subpath=("Content", "Tasks")):
    """Copy each saved ``.uasset`` into ``discrimination/<variant>/…``; return the dest.

    Raises ``AuthoringError`` if any expected file is missing — a silent partial
    harvest commits a leg without one of its assets, which grades as a different
    failure than the one intended.
    """
    dst = os.path.join(task_dir, "discrimination", variant,
                       *content_subpath, task_id)
    os.makedirs(dst, exist_ok=True)
    written = []
    for name in asset_names:
        src = os.path.join(substrate_task_dir, name + ".uasset")
        if not os.path.isfile(src):
            raise AuthoringError("saved asset not on disk at %s" % src)
        out = os.path.join(dst, name + ".uasset")
        shutil.copy2(src, out)
        written.append(out)
    if len(written) != len(asset_names):
        raise AuthoringError("harvested %d of %d assets for %s"
                             % (len(written), len(asset_names), variant))
    return dst
