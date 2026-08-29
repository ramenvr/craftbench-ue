"""L2-introspect — deterministic STRUCTURAL verification of a generated asset.

Runs a VERIFIER-OWNED Python introspection script headlessly via
``UnrealEditor-Cmd -ExecutePythonScript=<script>`` (the same channel as
``asset_capture.py``), and parses a JSON verdict the script
prints between ``CRAFTBENCH-INTROSPECT-JSON-START`` / ``...-END`` markers.

This is the spec's ``L2-mat`` generalized: the script loads an asset
(Material, Blueprint graph, AnimBP state machine, UMG ``WidgetTree``,
DataTable, ...) via UE's editor-Python reflection and asserts STRUCTURAL
facts about it — deterministic, no PIE, no LLM. The script is verifier-owned
(hash-pinned, deny-write to the agent), exactly like the ``AFunctionalTest``
fixtures under ``Source/CraftBenchTests/``.

Anti-circularity: introspection runs through CraftBench's OWN headless editor
+ stock UE Python (``EditorAssetLibrary`` / reflection), never through Aura's
MCP tools.

The introspect-script contract
------------------------------
A task's introspect script MUST print, on stdout, exactly one verdict block::

    CRAFTBENCH-INTROSPECT-JSON-START
    {"checks": [{"id": "<str>", "passed": <bool>, "detail": "<str>"}, ...]}
    CRAFTBENCH-INTROSPECT-JSON-END

Overall layer status is PASS iff the block parses, has >= 1 check, and every
check's ``passed`` is true. A missing/malformed block => ERROR — fail-safe:
the deterministic gate never certifies on an unconfirmed verdict. If the
script emits the block twice (re-run / double dispatch), the LAST block wins.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from layers.l2_pie import editor_binary as _default_editor_binary
from layers.l2_pie import run_editor_with_marker_kill as _default_run_editor


INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"
SUBMITTED_FILES_ENV = "CRAFTBENCH_SUBMITTED_FILES_JSON"

# Asset-integrity preamble (2026-07-29). When the runner hands the layer the
# submission's accepted asset files, the editor session FIRST validates each
# one against the asset registry — the package must contain the asset its
# file path claims, and must not be a UObjectRedirector — then chains into the
# task's introspect script. The redirector check is the real payload:
# ``load_asset`` FOLLOWS redirectors, so a submitted redirector at a legal
# path would make every grader silently grade the redirect TARGET instead of
# the submission. Identity mismatches already fail closed in practice (the
# graders' own ``*_exists`` checks miss), so that half is belt-and-braces.
INTEGRITY_JSON_START = "CRAFTBENCH-ASSET-INTEGRITY-JSON-START"
INTEGRITY_JSON_END = "CRAFTBENCH-ASSET-INTEGRITY-JSON-END"

# Violation reasons carrying these prefixes are VERIFIER-side probe failures
# (manifest unreadable, registry probe raised) and route to layer status
# "error" (→ HARNESS-ERROR), never to a graded FAIL. Everything else — a
# submitted redirector, a package that does not contain its claimed asset —
# is agent-caused and grades as a failed check. Same taxonomy rule as
# run_task.harness_error_reasons: a non-agent condition must never reach a
# graded verdict, and an agent-chosen submission property must never escape one.
_INTEGRITY_HARNESS_PREFIXES = ("INTEGRITY_",)

# BOTH MARKERS MUST END THEIR LINE. This is a grading-integrity rule, not
# formatting fussiness.
#
# The verdict block is emitted as three separate print()/unreal.log() calls, so
# each marker always terminates its line (a UE log prefix sits BEFORE the
# marker, never after), and the payload between them is a single line of
# json.dumps output. An END marker appearing anywhere else is therefore inside
# that payload -- i.e. inside a string the SUBMISSION controls, because check
# details quote asset paths and names.
#
# With the previous unanchored form the non-greedy body stopped at the FIRST
# END-shaped run of characters, so an agent that named an asset
# "CRAFTBENCH-INTROSPECT-JSON-END" truncated the block mid-JSON. The parse then
# failed, L2I reported status "error", and run_task routed that to
# HARNESS-ERROR (exit 7) -- which is NON-GRADED. A submission that could not
# solve the task would have left the pass-rate denominator entirely, by picking
# a filename. finditer + last-match does not save it: every block in the log
# carries the same poisoned payload, so every match truncates.
#
# That is the same denominator-opt-out class the build lock was deliberately
# designed to refuse (see build_lock.py: "could not take the lock -> non-graded"
# was rejected for exactly this reason). A non-agent condition must never reach
# a graded verdict -- and an agent-chosen submission property must never escape
# one. Anchoring is what keeps the second half of that rule true here.
_MARKER_EOL = r"[ \t\r]*(?:\n|$)"

_BLOCK_RE = re.compile(
    re.escape(INTROSPECT_JSON_START) + _MARKER_EOL
    + r"(?P<body>.*?)"
    + re.escape(INTROSPECT_JSON_END) + _MARKER_EOL,
    re.DOTALL,
)

_INTEGRITY_BLOCK_RE = re.compile(
    re.escape(INTEGRITY_JSON_START) + _MARKER_EOL
    + r"(?P<body>.*?)"
    + re.escape(INTEGRITY_JSON_END) + _MARKER_EOL,
    re.DOTALL,
)


def _canonical_submitted_relpaths(rel_paths: Optional[List[str]]) -> List[str]:
    """Return the complete sandbox-accepted file list in stable POSIX form.

    The caller is the runner's authoritative ``SandboxResult.accepted``
    channel.  Do not inspect the submission/workdir here: doing so could add
    scaffold, reference, foreign, or link-followed files that the sandbox did
    not accept.  The sandbox already rejects links; these checks preserve that
    trust boundary by failing closed if its internal relative-path invariant is
    ever violated before the list reaches verifier-owned editor Python.
    """
    normalized = set()
    for raw in rel_paths or []:
        if not isinstance(raw, str):
            raise ValueError("accepted submitted-file path is not a string")
        rel = raw.replace("\\", "/")
        # Preserve the existing surface-contract semantics: a harmless leading
        # ``./`` is canonicalized, so ``./Source/Answer.cpp`` remains a graded
        # source-submission violation instead of escaping to HARNESS-ERROR.
        # Strip exact prefixes rather than using lstrip("./"), which would also
        # corrupt legitimate dotted path components such as ``.staging``.
        while rel.startswith("./"):
            rel = rel[2:]
        parts = rel.split("/")
        if (
            not rel
            or rel.startswith("/")
            or re.match(r"^[A-Za-z]:", rel)
            or any(part in ("", ".", "..") for part in parts)
        ):
            raise ValueError(f"unsafe accepted submitted-file path: {raw!r}")
        normalized.add("/".join(parts))
    return sorted(normalized)


def _l2i_child_environment(submitted_files: Optional[List[str]]) -> dict:
    """Copy the caller environment and add only the accepted-file manifest."""
    child_env = os.environ.copy()
    child_env[SUBMITTED_FILES_ENV] = json.dumps(
        _canonical_submitted_relpaths(submitted_files),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return child_env


def content_package_path(rel_path: str) -> Optional[str]:
    """Map a submission asset rel-path to its UE package path, or None.

    Plain project assets map below ``/Game``; plugin assets map below their
    ``/<PluginName>`` mount. OFPA mirror packages
    (``__ExternalActors__``/``__ExternalObjects__``) are deliberately
    EXCLUDED: they are actor/instance packages that the asset registry does
    not index as assets, so a registry probe would false-positive on valid
    submissions. Source/config/descriptor files are not assets at all.
    """
    p = rel_path.replace("\\", "/")
    lower = p.lower()
    if not (lower.endswith(".uasset") or lower.endswith(".umap")):
        return None
    if p.startswith("Content/"):
        if p.startswith(("Content/__ExternalActors__/",
                         "Content/__ExternalObjects__/")):
            return None
        stem = p[len("Content/"):]
        stem = stem[: stem.rfind(".")]
        return "/Game/" + stem

    # Plugin assets mount at /<PluginName>/..., where PluginName is the
    # directory immediately containing the one Content/ segment. Reject
    # ambiguous/malformed paths rather than silently probing the wrong mount.
    if not p.startswith("Plugins/"):
        return None
    parts = p.split("/")
    content_indexes = [i for i, part in enumerate(parts) if part == "Content"]
    if len(content_indexes) != 1:
        return None
    i = content_indexes[0]
    if i < 2 or i + 1 >= len(parts):
        return None
    plugin_name = parts[i - 1]
    if re.fullmatch(r"[A-Za-z0-9_]+", plugin_name) is None:
        return None
    tail = parts[i + 1:]
    if (not tail or any(part in ("", ".", "..") for part in tail)
            or tail[0] in ("__ExternalActors__", "__ExternalObjects__")):
        return None
    tail[-1] = tail[-1][: tail[-1].rfind(".")]
    if not tail[-1]:
        return None
    return f"/{plugin_name}/" + "/".join(tail)


#: A submitted path with one of these extensions is a COMPILE INPUT. Same set as
#: ``run_task.py``'s ``--lite`` refusal, deliberately: two different answers to
#: "is this file source?" in one runner is how one of them goes quietly stale.
_SOURCE_SUFFIXES = (".cpp", ".h", ".hpp", ".cc", ".cxx", ".inl", ".cs")


def source_submission_paths(rel_paths) -> List[str]:
    """The submitted paths that make a submission a C++ answer, sorted.

    TWO rules, because each alone has a hole the other closes:

      * any COMPILE INPUT by extension, wherever it sits. A ``.cpp`` dropped
        outside ``Source/`` still gets compiled by L1 if the module globs it, so
        location alone cannot be the test.
      * anything at all under ``Source/``. A ``.Build.cs`` or a ``.uplugin``
        carries no graded logic itself but changes what L1 compiles, and a
        by-extension test alone would wave through a submission that swaps a
        module's dependencies.

    Returned rather than counted so the failing check can NAME the files: a check
    that says only "source was submitted" sends the reader back to the sandbox
    log to find out which.
    """
    out = []
    for raw in rel_paths or ():
        p = str(raw).replace("\\", "/")
        while p.startswith("./"):
            p = p[2:]
        if not p:
            continue
        if p.lower().endswith(_SOURCE_SUFFIXES) or p.startswith("Source/"):
            out.append(p)
    return sorted(set(out))


def write_integrity_bootstrap(
    *,
    out_dir: Path,
    task_script: Path,
    asset_rel_paths: List[str],
    stem: str,
    allow_redirectors: Optional[List[str]] = None,
) -> Path:
    """Write the integrity manifest + bootstrap wrapper; return the bootstrap.

    The bootstrap runs in the SAME editor session as the task script (no
    second boot): it waits for the asset-registry scan, probes every
    submitted asset, prints the integrity verdict block, then ``exec``s the
    task script with ``__name__ == "__main__"`` so its entry guard fires.

    ``allow_redirectors`` (spec-declared package paths, default-closed) marks
    those manifest entries ``redirector_ok`` — the rename-residue lane: a
    legitimate in-editor rename can leave a UObjectRedirector at the old
    path, and a task graded on the rename must not FAIL that residue. The
    key is written only when true so default manifests stay byte-identical
    to the pre-flag shape. Everything else (identity check, probe-error
    routing) is unchanged for allowed entries.
    """
    allowed = set(allow_redirectors or [])
    entries = []
    for rel in asset_rel_paths:
        pkg = content_package_path(rel)
        if pkg is not None:
            entry = {"rel": rel.replace("\\", "/"), "package": pkg}
            if pkg in allowed:
                entry["redirector_ok"] = True
            entries.append(entry)
    manifest_path = out_dir / f"asset_integrity_{stem}.json"
    manifest_path.write_text(json.dumps(entries, indent=1), encoding="utf-8")
    bootstrap_path = out_dir / f"l2i_bootstrap_{stem}.py"
    bootstrap_path.write_text(
        _BOOTSTRAP_TEMPLATE.format(
            manifest=json.dumps(str(manifest_path)),
            task_script=json.dumps(str(task_script)),
            start=INTEGRITY_JSON_START,
            end=INTEGRITY_JSON_END,
        ),
        encoding="utf-8",
    )
    return bootstrap_path


_BOOTSTRAP_TEMPLATE = '''\
"""VERIFIER-GENERATED bootstrap: asset-integrity preamble + task introspect.

Generated by layers/l2_introspect.py per run; not agent-visible content.
"""
import json

import unreal

MANIFEST = {manifest}
TASK_SCRIPT = {task_script}
START = "{start}"
END = "{end}"


def _violations():
    out = []
    try:
        entries = json.load(open(MANIFEST, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        out.append({{"path": MANIFEST,
                    "reason": "INTEGRITY_MANIFEST_UNREADABLE %r" % (e,)}})
        return out
    try:
        # The registry scan is asynchronous at boot; probing before it
        # finishes would misread a valid overlaid asset as missing and
        # manufacture a false negative. Block until it settles.
        unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    except Exception as e:  # noqa: BLE001
        out.append({{"path": "<asset-registry>",
                    "reason": "INTEGRITY_REGISTRY_WAIT_ERROR %r" % (e,)}})
        return out
    for entry in entries:
        pkg = entry["package"]
        rel = entry["rel"]
        try:
            data = unreal.EditorAssetLibrary.find_asset_data(pkg)
            valid = bool(data.is_valid()) if data is not None else False
        except Exception as e:  # noqa: BLE001
            out.append({{"path": rel,
                        "reason": "INTEGRITY_PROBE_ERROR %s raised %r" % (pkg, e)}})
            continue
        if not valid:
            out.append({{"path": rel,
                        "reason": "PACKAGE_IDENTITY_MISMATCH no registered "
                                  "asset at %s (internal object name does not "
                                  "match the file path)" % pkg}})
            continue
        try:
            cls = str(data.asset_class_path.asset_name)
        except Exception as e:  # noqa: BLE001
            out.append({{"path": rel,
                        "reason": "INTEGRITY_CLASS_READ_ERROR %s raised %r" % (pkg, e)}})
            continue
        if cls == "ObjectRedirector" and not entry.get("redirector_ok"):
            out.append({{"path": rel,
                        "reason": "REDIRECTOR_SUBMITTED %s is a "
                                  "UObjectRedirector - load_asset would grade "
                                  "its TARGET, not the submission" % pkg}})
    return out


_payload = json.dumps({{"violations": _violations()}})
print(START)
print(_payload)
print(END)
try:
    unreal.log(START)
    unreal.log(_payload)
    unreal.log(END)
except Exception:  # noqa: BLE001 - stdout copy is authoritative
    pass

with open(TASK_SCRIPT, encoding="utf-8") as _f:
    _src = _f.read()
exec(compile(_src, TASK_SCRIPT, "exec"),
     {{"__name__": "__main__", "__file__": TASK_SCRIPT}})
'''


@dataclass
class IntegrityViolation:
    path: str
    reason: str

    @property
    def harness_side(self) -> bool:
        return self.reason.startswith(_INTEGRITY_HARNESS_PREFIXES)


def parse_integrity_verdict(log_text: str) -> Optional[List[IntegrityViolation]]:
    """The LAST integrity block's violations, or None if no block parsed."""
    matches = list(_INTEGRITY_BLOCK_RE.finditer(log_text))
    if not matches:
        return None
    body = matches[-1].group("body").strip()
    start_brace = body.find("{")
    end_brace = body.rfind("}")
    if start_brace != -1 and end_brace > start_brace:
        body = body[start_brace: end_brace + 1]
    try:
        obj = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    raw = obj.get("violations") if isinstance(obj, dict) else None
    if not isinstance(raw, list):
        return None
    return [
        IntegrityViolation(path=str(v.get("path", "?")), reason=str(v.get("reason", "?")))
        for v in raw if isinstance(v, dict)
    ]


@dataclass
class IntrospectCheck:
    id: str
    passed: bool
    detail: str = ""


@dataclass
class ParsedIntrospect:
    found: bool
    checks: List[IntrospectCheck] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed_count == self.total


def parse_introspect_verdict(log_text: str) -> ParsedIntrospect:
    """Extract the LAST verdict block and parse its checks.

    Fail-safe: any parse problem (no block / malformed JSON / missing
    ``checks`` list) returns ``found=False`` so the gate never treats an
    unconfirmed verdict as a pass.
    """
    matches = list(_BLOCK_RE.finditer(log_text))
    if not matches:
        return ParsedIntrospect(found=False)
    body = matches[-1].group("body").strip()
    if body.startswith("﻿"):  # UE may prepend a BOM to stdout chunks
        body = body[1:]
    # The introspect script emits the verdict via ``unreal.log``, so the line
    # carrying the JSON arrives wrapped in UE's log prefix, e.g.
    # ``[2026.06.01-10.00.58:850][  2]LogPython: {"checks": [...]}``. Strip any
    # leading/trailing log decoration by isolating the JSON object itself: the
    # payload is a single ``{...}`` object, so take the first ``{`` through the
    # matching last ``}``. Fail-safe: if there is no balanced object the
    # subsequent ``json.loads`` still fails and we return ``found=False``.
    start_brace = body.find("{")
    end_brace = body.rfind("}")
    if start_brace != -1 and end_brace > start_brace:
        body = body[start_brace : end_brace + 1]
    try:
        obj = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return ParsedIntrospect(found=False)
    raw_checks = obj.get("checks") if isinstance(obj, dict) else None
    if not isinstance(raw_checks, list):
        return ParsedIntrospect(found=False)
    checks: List[IntrospectCheck] = []
    for c in raw_checks:
        if not isinstance(c, dict):
            continue
        checks.append(IntrospectCheck(
            id=str(c.get("id", "?")),
            passed=bool(c.get("passed", False)),
            detail=str(c.get("detail", "")),
        ))
    return ParsedIntrospect(found=True, checks=checks)


@dataclass
class L2IntrospectResult:
    status: str  # "pass" | "fail" | "error"
    log_path: Path
    duration_seconds: float
    checks: List[IntrospectCheck]
    total: int
    passed_count: int
    notes: List[str]
    exit_code: int
    result_source: str  # "json" | "none"


def run_l2_introspect(
    *,
    ue_root: Path,
    project_path: Path,
    introspect_script: Path,
    log_path: Path,
    timeout_seconds: float = 300.0,
    use_nullrhi: bool = True,
    submitted_assets: Optional[List[str]] = None,
    forbid_source_submissions: bool = False,
    allow_redirectors: Optional[List[str]] = None,
    _editor_binary: Optional[Callable[[Path], Path]] = None,
    _run_editor: Optional[Callable] = None,
) -> L2IntrospectResult:
    """Run a verifier-owned introspection script headlessly + parse its verdict.

    ``submitted_assets`` is the complete submitted-file rel-path list accepted
    by the sandbox (the parameter name predates non-asset consumers).  Every
    L2I editor receives that exact list through
    ``CRAFTBENCH_SUBMITTED_FILES_JSON``; assets additionally opt in to the
    asset-integrity preamble, where the same editor session validates registry
    identity + no-redirector before the task script runs. Agent-caused
    violations grade as failed checks; verifier-side probe failures route to
    status "error".

    ``allow_redirectors`` (spec-declared package paths, default-closed)
    exempts exactly those packages from the preamble's redirector rejection —
    the rename-residue lane. See write_integrity_bootstrap.

    ``_editor_binary`` and ``_run_editor`` are injectable seams so the layer
    is unit-testable with no UE install.
    """
    notes: List[str] = []
    resolve_editor = _editor_binary or _default_editor_binary
    run_editor = _run_editor or _default_run_editor

    # Own the output directory HERE rather than relying on the caller to have made
    # it. The asset-integrity bootstrap below writes its manifest into this
    # directory, and it used to do so before anything created it -- an undeclared
    # precondition that held only because registry.py happens to mkdir out_dir
    # first. mkdir is idempotent, so this costs nothing and removes the ordering
    # dependency; the later mkdir before the editor run is left in place because
    # the error returns above it exit early.
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        child_env = _l2i_child_environment(submitted_assets)
    except ValueError as e:
        log_path.write_text(
            f"L2-introspect ABORTED: invalid accepted-file manifest: {e}\n",
            encoding="utf-8",
        )
        return L2IntrospectResult(
            status="error", log_path=log_path, duration_seconds=0.0,
            checks=[], total=0, passed_count=0,
            notes=[f"invalid accepted-file manifest: {e}"], exit_code=127,
            result_source="none",
        )

    script_to_launch = introspect_script
    integrity_expected = False
    if submitted_assets:
        eligible = [r for r in submitted_assets if content_package_path(r)]
        if eligible:
            script_to_launch = write_integrity_bootstrap(
                out_dir=log_path.parent,
                task_script=introspect_script,
                asset_rel_paths=eligible,
                stem=introspect_script.stem,
                allow_redirectors=allow_redirectors,
            )
            integrity_expected = True
            notes.append(
                f"asset-integrity preamble: {len(eligible)} submitted asset(s)"
            )

    editor = resolve_editor(ue_root)
    if not editor.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"L2-introspect ABORTED: editor not found at {editor}\n", encoding="utf-8"
        )
        return L2IntrospectResult(
            status="error", log_path=log_path, duration_seconds=0.0,
            checks=[], total=0, passed_count=0,
            notes=[f"editor binary missing at {editor}"], exit_code=127,
            result_source="none",
        )

    cmd: List[str] = [
        str(editor),
        str(project_path),
        f"-ExecutePythonScript={script_to_launch}",
        "-unattended", "-nopause", "-nosplash", "-nosound",
        "-log", "-stdout", "-fullstdoutlogoutput",
    ]
    if use_nullrhi:
        cmd.insert(2, "-nullrhi")

    notes.append("cmd: " + " ".join(cmd))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        exit_code, _killed = run_editor(
            cmd=cmd, env=child_env, log_path=log_path,
            timeout_seconds=timeout_seconds,
            extra_markers=(INTROSPECT_JSON_END,),
        )
    except Exception as e:  # noqa: BLE001  — timeout / exec error, fail-safe to error
        return L2IntrospectResult(
            status="error", log_path=log_path,
            duration_seconds=time.monotonic() - start,
            checks=[], total=0, passed_count=0,
            notes=notes + [f"editor run failed: {e}"], exit_code=124,
            result_source="none",
        )

    duration = time.monotonic() - start
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_introspect_verdict(log_text)

    integrity_checks: List[IntrospectCheck] = []
    if integrity_expected:
        violations = parse_integrity_verdict(log_text)
        if violations is None:
            # The preamble is VERIFIER-generated; its block going missing is
            # our artifact, never the submission's — route to harness-error
            # exactly like a dead task-script verdict channel.
            return L2IntrospectResult(
                status="error", log_path=log_path, duration_seconds=duration,
                checks=[], total=0, passed_count=0,
                notes=notes + ["no parseable asset-integrity block emitted by bootstrap"],
                exit_code=exit_code, result_source="none",
            )
        harness_side = [v for v in violations if v.harness_side]
        if harness_side:
            return L2IntrospectResult(
                status="error", log_path=log_path, duration_seconds=duration,
                checks=[], total=0, passed_count=0,
                notes=notes + [
                    f"asset-integrity probe failure (verifier-side): {v.path}: {v.reason}"
                    for v in harness_side
                ],
                exit_code=exit_code, result_source="none",
            )
        integrity_checks = [
            IntrospectCheck(
                id="asset_integrity", passed=False,
                detail=f"{v.reason} path={v.path}",
            )
            for v in violations
        ]

    if not parsed.found:
        return L2IntrospectResult(
            status="error", log_path=log_path, duration_seconds=duration,
            checks=[], total=0, passed_count=0,
            notes=notes + ["no parseable verdict block emitted by introspect script"],
            exit_code=exit_code, result_source="none",
        )
    # THE SURFACE CONTRACT, for a task whose answer must be a Blueprint.
    #
    # Every other L2I check on a -bp task looks for a NEW NATIVE CLASS, so the
    # shape of submission that defeats them all is an IN-PLACE EDIT of a shipped
    # scaffold .cpp -- which is exactly the shape of the committed -cpp reference.
    # With an empty Blueprint beside it, such a submission passed every
    # structural check while L1 compiled the C++ and L2 graded it, and the run
    # reported the Blueprint surface. Nothing in the runner noticed.
    #
    # Graded, NOT a refusal. The task asks for a Blueprint; answering in C++ is
    # the model failing the task, not the harness failing to run. A refusal would
    # void the run and cost the model nothing, which would bias the benchmark
    # toward whichever models ignore the constraint.
    #
    # Emitted even when it PASSES, unlike the asset-integrity checks above which
    # appear only on violation. A gate that leaves no trace when it holds cannot
    # be told apart from a gate that never ran -- this repo has already shipped
    # one unfailable dead gate (--strict-warnings) and did not notice for weeks.
    surface_checks: List[IntrospectCheck] = []
    if forbid_source_submissions:
        offenders = source_submission_paths(submitted_assets)
        surface_checks.append(IntrospectCheck(
            id="no_source_submitted",
            passed=not offenders,
            detail=(
                "the answer must be a Blueprint, but the submission carries "
                "%d source/compile input(s), which L1 compiled and L2 graded: %s"
                % (len(offenders), ", ".join(offenders[:6])
                   + ("..." if len(offenders) > 6 else ""))
                if offenders else
                "no source or compile input among the %d accepted path(s)"
                % len(list(submitted_assets or ()))
            ),
        ))

    checks = integrity_checks + surface_checks + parsed.checks
    total = len(checks)
    passed_count = sum(1 for c in checks if c.passed)
    status = "pass" if (total > 0 and passed_count == total) else "fail"
    return L2IntrospectResult(
        status=status, log_path=log_path, duration_seconds=duration,
        checks=checks, total=total, passed_count=passed_count,
        notes=notes, exit_code=exit_code, result_source="json",
    )
