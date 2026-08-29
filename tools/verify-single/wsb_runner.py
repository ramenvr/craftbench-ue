"""wsb_runner — run a CraftBench grade inside a disposable Windows Sandbox.

WHY this exists (the threat model): a CraftBench grade compiles and RUNS
agent-authored C++ inside a real ``UnrealEditor-Cmd`` process on the grading
host. The agent's source is untrusted — a malicious or buggy submission can do
anything the editor process can: touch the host home dir, walk the
``Plugins/Aura`` junction into the *separate* ``aura-plugin`` repo, exfiltrate
over the network, or wedge the box. The in-process ``job_governor`` Win32
Job-Object backstop caps RAM and reaps runaway trees, but it does NOT contain
filesystem or network blast radius — it is a resource governor, not a sandbox.

``--sandbox`` adds the containment layer: it re-runs the *entire* grade inside a
**Windows Sandbox** (``.wsb``) — a throwaway, hardware-virtualized Windows VM that
is destroyed on exit. This module only **generates the ``.wsb`` config and the
in-VM launch command**; ``run_task.py`` decides whether to use it.

What the generated ``.wsb`` enforces (the containment contract):
  * **UE install mapped READ-ONLY** — the multi-GB engine is shared in, never
    copied, and the VM cannot mutate the host's engine.
  * **A COPY of the cloned workdir mapped READ-WRITE** — the grade builds + runs
    against the copy; the host's working tree is never exposed. (The caller
    copies the workdir to a staging dir first; this module never maps the
    original.)
  * **Host home dir is NEVER mapped**, and **the ``aura-plugin`` junction target
    is NEVER mapped** — that sibling repo (reachable on the host via the live
    ``Plugins/Aura`` OS junction) is precisely the blast radius we are containing.
    ``build_wsb_config`` asserts neither path appears in any ``<MappedFolder>``.
  * **``<Networking>Disable</Networking>``** — no network egress from the VM, so a
    submission cannot phone home or pull payloads mid-grade.
  * **``<LogonCommand>``** boots the grade automatically: it points the in-VM
    Python at the mapped ``run_task.py`` with the mapped workdir-copy substrate
    and the mapped (read-only) UE root.

GPU / RHI risk: Windows Sandbox exposes (at best) a paravirtualized
``WARP``/vGPU, and historically *no* hardware GPU. CraftBench L2/L2I runs already
pass ``-nullrhi`` (no swapchain, no real device), so the editor should open
headless inside the VM exactly as it does on the host. L3 (real-RHI screenshot)
is the one layer that may NOT survive the VM's software rasterizer — treat L3
inside the sandbox as UNVALIDATED. The default grade set (L1 + L2 + L2I) is
``-nullrhi`` and is the intended ``--sandbox`` workload.

STATUS — UNVALIDATED end-to-end. Windows Sandbox needs Windows **Pro / Education /
Enterprise** with the *Windows Sandbox* optional feature enabled; it does **not**
exist on Windows **Home**. This module was authored + unit-tested on a Windows 11
**Home** box, where the ``.wsb`` XML generation, path mapping, and the
not-available fallback are exercised OFFLINE, but a real sandbox could not be
launched. The XML shape follows Microsoft's documented ``.wsb`` schema; the
end-to-end build+PIE-inside-the-VM path MUST be validated on a Pro/Edu box or in
CI before relying on it for actual containment. Do not assume it works until then.

This module is **pure config generation + host capability detection** — it shells
nothing itself except the optional ``WindowsSandbox.exe`` launch in
``run_grade_in_sandbox`` (guarded by the availability check). It imports cleanly
on every platform.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence
from xml.sax.saxutils import escape as _xml_escape


IS_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------------------
# Host capability detection
# ---------------------------------------------------------------------------


def _windows_sandbox_exe() -> Optional[Path]:
    """Return the path to ``WindowsSandbox.exe`` if it exists, else None.

    The launcher binary is present in ``%SystemRoot%\\System32`` ONLY when the
    *Windows Sandbox* optional feature is installed — which requires Windows
    Pro/Education/Enterprise. On Windows Home (and every non-Windows host) it is
    absent, which is exactly the signal we use to gate ``--sandbox``.

    ``shutil.which`` is also consulted as a fallback in case the binary lives
    elsewhere on PATH, but the canonical location is the System32 check.
    """
    if not IS_WINDOWS:
        return None
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    candidate = Path(system_root) / "System32" / "WindowsSandbox.exe"
    if candidate.exists():
        return candidate
    found = shutil.which("WindowsSandbox.exe") or shutil.which("WindowsSandbox")
    return Path(found) if found else None


def windows_sandbox_available() -> bool:
    """True iff this host can launch a Windows Sandbox.

    Pure capability probe: Windows AND ``WindowsSandbox.exe`` resolvable. Never
    raises; returns False on every non-Windows host and on Windows Home (where
    the feature — and therefore the binary — does not exist).
    """
    return _windows_sandbox_exe() is not None


def unavailable_reason() -> str:
    """Human-readable explanation of why the sandbox is unavailable (for logs)."""
    if not IS_WINDOWS:
        return f"not a Windows host (os.name={os.name!r}); Windows Sandbox is Windows-only"
    return (
        "WindowsSandbox.exe not found — the Windows Sandbox optional feature is "
        "not installed. It requires Windows Pro/Education/Enterprise (it does NOT "
        "exist on Windows Home) and must be enabled via "
        "'Optional Features' / 'Enable-WindowsOptionalFeature -FeatureName "
        "Containers-DisposableClientVM'."
    )


# ---------------------------------------------------------------------------
# .wsb config generation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MappedFolder:
    """One ``<MappedFolder>`` entry in a ``.wsb`` config."""

    host_path: Path
    read_only: bool
    sandbox_path: Optional[str] = None  # in-VM mount path; default = same basename under C:\

    def in_vm_path(self) -> str:
        """The path this folder is mounted at inside the VM.

        When ``sandbox_path`` is unset, Windows Sandbox mounts a mapped folder at
        ``C:\\Users\\WDAGUtilityAccount\\Desktop\\<basename>``. We set
        ``sandbox_path`` explicitly for both maps so the LogonCommand can name a
        stable, predictable in-VM path independent of that default.
        """
        if self.sandbox_path:
            return self.sandbox_path
        # PureWindowsPath: host paths are ALWAYS Windows paths for Windows
        # Sandbox; plain Path(...).name mis-parses them on a POSIX test host
        # (backslashes aren't separators there — CI matrix failure 2026-07-11).
        from pathlib import PureWindowsPath
        return rf"C:\Users\WDAGUtilityAccount\Desktop\{PureWindowsPath(self.host_path).name}"


@dataclass(frozen=True)
class WsbSpec:
    """Everything needed to render a containment ``.wsb`` for one grade.

    Paths are HOST paths. ``ue_root_host`` is mapped read-only; ``workdir_copy_host``
    is mapped read-write. ``forbidden_paths`` are host paths that MUST NOT appear in
    any mapped folder (the home dir + the aura-plugin junction target); they are
    asserted out at render time.
    """

    ue_root_host: Path
    workdir_copy_host: Path
    # In-VM mount points (stable, explicit — see MappedFolder.in_vm_path).
    ue_root_vm: str = r"C:\ue"
    workdir_vm: str = r"C:\work"
    # The in-VM Python interpreter + the in-VM path to run_task.py (under the
    # mapped workdir copy, which carries tools/verify-single/).
    python_vm: str = "py -3.12"
    run_task_vm: str = r"C:\work\tools\verify-single\run_task.py"
    # Extra args to forward to the in-VM run_task.py (already excludes --sandbox).
    extra_run_task_args: Sequence[str] = field(default_factory=tuple)
    # Host paths that must never be mapped into the VM.
    forbidden_paths: tuple[Path, ...] = ()
    networking_disabled: bool = True
    memory_mb: Optional[int] = None  # optional <MemoryInMB> cap

    def mapped_folders(self) -> list[MappedFolder]:
        return [
            MappedFolder(self.ue_root_host, read_only=True, sandbox_path=self.ue_root_vm),
            MappedFolder(self.workdir_copy_host, read_only=False, sandbox_path=self.workdir_vm),
        ]

    def logon_command(self) -> str:
        """The single shell command the VM runs on logon to start the grade.

        It cd's nowhere special; it invokes the mapped run_task.py with the in-VM
        substrate-overlay (the workdir copy) and the in-VM read-only UE root.
        ``--substrate-overlay`` points at the mapped workdir so the in-VM grade
        does NOT try to re-clone from git (the VM has no repo / git). ``--sandbox``
        is intentionally absent (no nested sandboxing).
        """
        parts = [
            self.python_vm,
            _quote_vm(self.run_task_vm),
            "--ue-root", _quote_vm(self.ue_root_vm),
            "--substrate-overlay", _quote_vm(self.workdir_vm),
        ]
        parts.extend(self.extra_run_task_args)
        return " ".join(parts)


def _quote_vm(path: str) -> str:
    """Quote an in-VM path/arg for the cmd.exe LogonCommand if it has spaces."""
    if " " in path and not (path.startswith('"') and path.endswith('"')):
        return f'"{path}"'
    return path


def _assert_not_forbidden(folders: list[MappedFolder], forbidden: Sequence[Path]) -> None:
    """Raise ValueError if any mapped folder is at/under a forbidden host path.

    This is the load-bearing containment assertion: the home dir and the
    aura-plugin junction target must NEVER be mapped into the VM. We compare
    resolved paths and check both directions (a forbidden path equal to, an
    ancestor of, or a descendant of a mapped folder all fail closed).
    """
    norm_forbidden = []
    for fp in forbidden:
        try:
            norm_forbidden.append(Path(fp).resolve())
        except OSError:
            norm_forbidden.append(Path(fp))
    for mf in folders:
        try:
            host = mf.host_path.resolve()
        except OSError:
            host = mf.host_path
        for fp in norm_forbidden:
            if host == fp or fp in host.parents or host in fp.parents:
                raise ValueError(
                    f"refusing to map {host} — it overlaps the forbidden path {fp} "
                    f"(home dir or aura-plugin junction is the blast radius "
                    f"--sandbox exists to contain)"
                )


def build_wsb_config(spec: WsbSpec) -> str:
    """Render a ``WsbSpec`` to ``.wsb`` XML text.

    The output validates against Microsoft's documented Windows Sandbox config
    schema: ``<Configuration>`` with ``<MappedFolders>``, ``<Networking>``, and
    ``<LogonCommand>``. Raises ``ValueError`` (fail-closed) if any forbidden host
    path would be mapped.
    """
    folders = spec.mapped_folders()
    _assert_not_forbidden(folders, spec.forbidden_paths)

    folder_xml = []
    for mf in folders:
        folder_xml.append(
            "    <MappedFolder>\n"
            f"      <HostFolder>{_xml_escape(str(mf.host_path))}</HostFolder>\n"
            f"      <SandboxFolder>{_xml_escape(mf.in_vm_path())}</SandboxFolder>\n"
            f"      <ReadOnly>{'true' if mf.read_only else 'false'}</ReadOnly>\n"
            "    </MappedFolder>"
        )

    networking = "Disable" if spec.networking_disabled else "Default"
    logon = _xml_escape(spec.logon_command())

    mem_xml = ""
    if spec.memory_mb:
        mem_xml = f"  <MemoryInMB>{int(spec.memory_mb)}</MemoryInMB>\n"

    return (
        "<Configuration>\n"
        f"  <Networking>{networking}</Networking>\n"
        f"{mem_xml}"
        "  <MappedFolders>\n"
        + "\n".join(folder_xml) + "\n"
        "  </MappedFolders>\n"
        "  <LogonCommand>\n"
        f"    <Command>{logon}</Command>\n"
        "  </LogonCommand>\n"
        "</Configuration>\n"
    )


def write_wsb_config(spec: WsbSpec, dest: Path) -> Path:
    """Render ``spec`` and write it to ``dest`` (UTF-8). Returns ``dest``."""
    xml = build_wsb_config(spec)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(xml, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Default forbidden-path resolution
# ---------------------------------------------------------------------------


def default_forbidden_paths(*, repo_root: Optional[Path] = None) -> tuple[Path, ...]:
    """Best-effort set of host paths that must never be mapped into the VM.

    Always includes the user home dir. Additionally includes the resolved target
    of the ``Plugins/Aura`` junction (the aura-plugin sibling repo) when it can
    be located relative to ``repo_root`` — that junction is the specific
    data-loss blast radius ``--sandbox`` contains.
    """
    out: list[Path] = []
    home = Path(os.path.expanduser("~"))
    out.append(home)

    if repo_root is not None:
        junction = repo_root / "UE-projects" / "CraftBenchTemplate" / "Plugins" / "Aura"
        # The junction RESOLVES to the aura-plugin sibling; record the resolved
        # target so a map of that real directory is rejected too.
        try:
            if junction.exists():
                out.append(junction.resolve())
        except OSError:
            pass
        # Also forbid the conventional sibling location even if the junction is
        # absent, so the assertion is meaningful on a checkout without the link.
        out.append((repo_root.parent / "aura-plugin").resolve() if repo_root.parent else repo_root)

    # De-dupe while preserving order.
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return tuple(uniq)


# ---------------------------------------------------------------------------
# Launch (Windows + WSB-available only)
# ---------------------------------------------------------------------------


@dataclass
class SandboxLaunch:
    """Outcome of a sandbox launch attempt."""

    launched: bool
    wsb_path: Optional[Path] = None
    returncode: Optional[int] = None
    note: str = ""


def stage_workdir_copy(workdir_substrate: Path, *, dest_root: Optional[Path] = None) -> Path:
    """Copy the cloned workdir substrate to a fresh staging dir for read-write mapping.

    We never map the runner's live workdir directly — the VM gets a throwaway
    COPY so even the workdir clone on the host is untouched by the contained
    grade. Returns the staged copy's root (the dir to map read-write).

    NOTE: the staged tree must also carry ``tools/verify-single/`` so the in-VM
    LogonCommand can invoke ``run_task.py``. In the real wiring the caller stages
    a layout that includes both the substrate AND the verifier tools; this helper
    handles the substrate copy and the caller composes the rest. Kept minimal for
    the prototype.
    """
    dest_root = dest_root or Path(tempfile.mkdtemp(prefix="craftbench-wsb-stage-"))
    dest = dest_root / workdir_substrate.name
    shutil.copytree(workdir_substrate, dest)
    return dest_root


def run_grade_in_sandbox(spec: WsbSpec, *, wsb_path: Optional[Path] = None,
                         wait: bool = True) -> SandboxLaunch:
    """Generate the ``.wsb`` and launch Windows Sandbox against it.

    GUARDED: returns a non-launched ``SandboxLaunch`` (never raises, never shells)
    when the host can't run a sandbox. On a WSB-capable host, writes the ``.wsb``
    and invokes ``WindowsSandbox.exe <config>``.

    NOTE: ``WindowsSandbox.exe`` returns as soon as the VM window opens — it does
    NOT block until the in-VM LogonCommand finishes, and there is no built-in
    exit-code propagation from the contained grade back to the host. Result
    propagation (e.g. having the in-VM grade write its report.json to the
    read-write mapped folder, which the host then reads) is the caller's job and
    is OUT OF SCOPE for this prototype. ``wait`` controls only whether we wait on
    the launcher process itself.
    """
    exe = _windows_sandbox_exe()
    if exe is None:
        return SandboxLaunch(launched=False, note=unavailable_reason())

    wsb_path = wsb_path or (Path(tempfile.mkdtemp(prefix="craftbench-wsb-")) / "grade.wsb")
    try:
        write_wsb_config(spec, wsb_path)
    except ValueError as exc:
        return SandboxLaunch(launched=False, wsb_path=wsb_path,
                             note=f"refused to launch: {exc}")

    cmd = [str(exe), str(wsb_path)]
    try:
        proc = subprocess.run(cmd) if wait else subprocess.Popen(cmd)
    except (OSError, subprocess.SubprocessError) as exc:
        return SandboxLaunch(launched=False, wsb_path=wsb_path,
                             note=f"WindowsSandbox.exe launch failed: {exc}")
    rc = proc.returncode if wait else None
    return SandboxLaunch(launched=True, wsb_path=wsb_path, returncode=rc,
                         note=f"launched Windows Sandbox with {wsb_path}")
