"""exit_status — a tiny PURE decoder that names an otherwise opaque exit code.

Why this exists: Windows hands a crashed process's **NTSTATUS straight back as its
exit code**, so an abnormal verifier/editor termination reaches the harness as a
bare integer with no explanation. A real run on 2026-07-25 recorded the verdict
string ``exit3221225794``; that is ``0xC0000142`` == ``STATUS_DLL_INIT_FAILED``,
which took a manual hex conversion and a sampler cross-check to work out. The
number was in the summary, the meaning was nowhere.

DIAGNOSTIC ONLY. Nothing here may influence a verdict — it exists so a human (or
an agent reading a log) sees *why* rather than a ten-digit integer. It is pure and
dependency-free so it can be called from any log path without import risk.
"""

from __future__ import annotations

# NTSTATUS values seen from UE / MSVC toolchain processes on Windows. Kept short
# on purpose: an unknown code still decodes to its hex form, which is the part
# that makes it searchable.
_NTSTATUS = {
    0xC0000005: "STATUS_ACCESS_VIOLATION (segfault)",
    0xC0000017: "STATUS_NO_MEMORY (heap/commit exhausted)",
    0xC000001D: "STATUS_ILLEGAL_INSTRUCTION",
    0xC0000094: "STATUS_INTEGER_DIVIDE_BY_ZERO",
    0xC00000FD: "STATUS_STACK_OVERFLOW",
    0xC0000135: "STATUS_DLL_NOT_FOUND (a required DLL is missing)",
    0xC0000142: "STATUS_DLL_INIT_FAILED (DLL init failed — often commit "
                "exhaustion or a killed session)",
    0xC000013A: "STATUS_CONTROL_C_EXIT (Ctrl-C / terminated by the operator)",
    0xC0000409: "STATUS_STACK_BUFFER_OVERRUN (/GS check, or a fail-fast assert)",
    0xC0000374: "STATUS_HEAP_CORRUPTION",
}

# POSIX shell / harness conventions. These are NOT NTSTATUS and must not be
# hex-decoded — 124/127 in particular are sentinels the L1 layer synthesizes
# itself, so mislabelling them would actively mislead.
_POSIX = {
    124: "timeout (SIGTERM by a timeout wrapper, or the L1 governed-timeout "
         "sentinel)",
    125: "the timeout wrapper itself failed",
    126: "command found but not executable",
    127: "command not found / could not be executed (the L1 'no UBT script' "
         "sentinel)",
}


def decode_exit(code: int | None) -> str | None:
    """Human-readable meaning for ``code``, or None when there is nothing to add.

    Returns None for 0 (success) and for small ordinary codes that carry no
    special meaning, so a caller can append unconditionally without producing
    noise on the happy path.
    """
    if code is None or code == 0:
        return None
    if code in _POSIX:
        return _POSIX[code]
    # Signals: a shell reports a killed child as 128+N.
    if 128 < code < 165:
        return f"killed by signal {code - 128}"
    # NTSTATUS arrives either as a raw negative int or as its unsigned 32-bit
    # form (Python's subprocess on Windows reports the unsigned value).
    unsigned = code & 0xFFFFFFFF if code < 0 else code
    if unsigned > 0xC0000000:
        named = _NTSTATUS.get(unsigned)
        hexed = f"0x{unsigned:08X}"
        return f"{hexed} {named}" if named else (
            f"{hexed} (an NTSTATUS — the process terminated abnormally; look it "
            f"up as {hexed})"
        )
    return None


def annotate_exit(code: int | None) -> str:
    """``decode_exit`` wrapped for direct string interpolation into a log line.

    Returns "" when there is nothing to say, so call sites can write
    ``f"exit={rc}{annotate_exit(rc)}"`` with no conditional.
    """
    meaning = decode_exit(code)
    return f" ({meaning})" if meaning else ""
