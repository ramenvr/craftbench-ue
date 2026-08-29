"""Semantic config lane -- diff-level validation of submitted Config/*.ini files.

Purpose. A blanket ``Config/`` deny blocks legitimate task classes (collision
profiles in DefaultEngine.ini, input mappings in DefaultInput.ini). The config
lane replaces the blanket deny with a TWO-stage gate:

  1. PATH acceptance -- sandbox.py accepts a submitted Config/ file only when
     its rel-path EXACTLY equals an entry in the substrate manifest's
     ``config_writable`` list (AGENT_WRITABLE.json). Files, not prefixes.
  2. SEMANTIC acceptance -- this module diffs the accepted file's UE-ini
     content against the substrate baseline and requires every change to be
     covered by the task spec's ``config_allow`` rules
     ("<Config/File.ini> :: <Section> :: <Key[*]>" entries).

Violation semantics. Violations produced here are SANDBOX-REJECT class: the
CALLER (the runner) wires them to exit 4. This module only produces
``(rel_path, reason)`` violation tuples -- it never exits, prints, or grades.

Deny-wins interaction. sandbox._is_writable short-circuits on ``deny`` BEFORE
the config_writable check, so the manifest must NOT deny a file it lists as
config_writable -- a rel-path both denied and config_writable is denied and
never reaches this lane. (That is also the safety property: everything under
Config/ that is not explicitly listed rejects by allowlist-miss.)

FOUR OUTCOMES, NAMED SEPARATELY (2026-08-19). This lane used to answer one
question -- "any violations?" -- and collapsed four different states into it.
:func:`classify_config_submission` now returns a :class:`ConfigFileOutcome`
per Config/ file with an explicit ``kind``:

  * ``OUTCOME_UNCHANGED``  -- the submitted file and the baseline are the SAME
                              config. Not a config change, so no rule is
                              needed; this is decided on BYTES first, before
                              any decode, so it holds for a file we could not
                              have parsed at all.
  * ``OUTCOME_ALLOWED``    -- the file changed and every change atom is covered
                              by a ``config_allow`` rule.
  * ``OUTCOME_DISALLOWED`` -- the file changed and at least one atom is not.
                              Violation; the runner exits 4.
  * ``OUTCOME_UNREADABLE`` -- we could not read or could not decode the file,
                              so we do not KNOW which of the three above it is.
                              Fail closed (it is still a violation, and the
                              runner still exits 4), but it is named
                              differently and its reason text says UNKNOWN --
                              never "config change not allowed", because we did
                              not observe a change. A check that cannot tell
                              "no" from "could not tell" is not a check.

``validate_config_submission`` is the back-compatible face of this: it
DELEGATES to ``classify_config_submission`` and flattens the outcomes to the
``(rel, reason)`` violation list ``run_task.main`` already consumes. One rule,
two views -- not two implementations that agree today.

Pure Python, stdlib only, no UE required.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from sandbox import _normalize_prefix

# Max characters of a value carried in ConfigChange.detail (violation texts
# stay one-line readable; UE ini values can run to kilobytes).
_DETAIL_MAX = 120


def parse_ue_ini(text: str) -> dict[str, list[tuple[str, str]]]:
    """Parse UE-dialect ini text into {section: ordered [(raw_key, value)]}.

    UE ini dialect, tolerantly:
      - ``[Section]`` headers open a section (created even if it stays empty);
      - ``Key=Value`` pairs; the array/op prefix chars ``+ - . !`` are PART of
        raw_key (``+Profiles`` and ``Profiles`` are different keys);
      - the value is everything after the FIRST ``=`` verbatim (UE values
        contain ``=`` inside parens routinely);
      - lines whose first non-blank char is ``;`` are comments; blank lines
        are skipped; CRLF and a leading UTF-8 BOM are tolerated;
      - keys appearing before any section header land under the ``""``
        (empty-string) section;
      - a non-blank line with no ``=`` is kept as (raw_key=line, value="")
        rather than silently dropped, so it still participates in diffs.

    Duplicate keys are preserved as separate entries in file order -- UE
    ``+Array`` lines depend on it.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    out: dict[str, list[tuple[str, str]]] = {}
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            out.setdefault(section, [])
            continue
        if "=" in line:
            raw_key, _, value = line.partition("=")
            raw_key = raw_key.strip()
        else:
            raw_key, value = stripped, ""
        out.setdefault(section, []).append((raw_key, value))
    return out


@dataclass(frozen=True)
class ConfigChange:
    """One diff atom: a value added to / removed from a (section, key) group."""

    section: str
    key: str
    kind: str  # "added" | "removed"
    detail: str  # the value text, truncated to _DETAIL_MAX chars


def _group_values(
    parsed: dict[str, list[tuple[str, str]]],
) -> tuple[dict[tuple[str, str], Counter], list[tuple[str, str]]]:
    """Group parsed entries by (section, raw_key) -> value multiset, keeping
    first-appearance order of the groups."""
    groups: dict[tuple[str, str], Counter] = {}
    order: list[tuple[str, str]] = []
    for section, pairs in parsed.items():
        for key, value in pairs:
            gk = (section, key)
            if gk not in groups:
                groups[gk] = Counter()
                order.append(gk)
            groups[gk][value] += 1
    return groups, order


def diff_ue_ini(base_text: Optional[str], new_text: str) -> list[ConfigChange]:
    """Diff two UE ini texts into a list of ConfigChange atoms.

    Model: entries are grouped by (section, raw_key) and each group's VALUES
    are compared as MULTISETS -- order-insensitive within a key group, because
    UE array entries reorder legally. A value present in new but not base is
    "added"; present in base but not new is "removed". A MODIFICATION is
    therefore represented as one "removed" + one "added" pair -- the simplest
    correct multiset model (there is no reliable way to say WHICH occurrence
    of a repeated key was edited, so we do not pretend to know). When
    ``base_text`` is None (no baseline file) every entry in new is "added".

    Output order: groups in new-file appearance order, then base-only groups
    in base order; within a group, removed values before added values.
    """
    base_parsed = parse_ue_ini(base_text) if base_text is not None else {}
    base_groups, base_order = _group_values(base_parsed)
    new_groups, new_order = _group_values(parse_ue_ini(new_text))

    order = list(new_order)
    order.extend(gk for gk in base_order if gk not in new_groups)

    changes: list[ConfigChange] = []
    for section, key in order:
        base_c = base_groups.get((section, key), Counter())
        new_c = new_groups.get((section, key), Counter())
        if base_c == new_c:
            continue
        for value, count in (base_c - new_c).items():
            for _ in range(count):
                changes.append(
                    ConfigChange(section, key, "removed", value[:_DETAIL_MAX])
                )
        for value, count in (new_c - base_c).items():
            for _ in range(count):
                changes.append(
                    ConfigChange(section, key, "added", value[:_DETAIL_MAX])
                )
    return changes


@dataclass(frozen=True)
class ConfigAllowRule:
    """One parsed ``config_allow`` entry: FILE :: SECTION :: KEY.

    ``file`` is a POSIX-normalized rel path (exact match); ``section`` is
    exact; ``key`` is the raw key including any ``+ - . !`` prefix, with an
    optional trailing ``*`` meaning prefix-match.
    """

    file: str
    section: str
    key: str

    def matches(self, rel_path: str, section: str, key: str) -> bool:
        if rel_path != self.file or section != self.section:
            return False
        if self.key.endswith("*"):
            return key.startswith(self.key[:-1])
        return key == self.key


def parse_config_allow(entries: Sequence[str]) -> tuple[ConfigAllowRule, ...]:
    """Parse spec ``config_allow`` entries into ConfigAllowRule tuples.

    Each entry is three ``::``-separated fields (same separator style as the
    spec's fixtures list), whitespace-stripped:

        Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile :: +Profiles

    The file field is POSIX-normalized like sandbox._normalize_prefix; the
    key field supports one optional trailing ``*`` wildcard (prefix match).
    A malformed entry (not exactly three fields, or any empty field) raises
    ValueError naming the offending entry -- fail closed at spec-parse time.
    Note this means pre-section keys (empty-string section) cannot be
    allowlisted; UE config files do not use them.
    """
    rules: list[ConfigAllowRule] = []
    for entry in entries:
        parts = [p.strip() for p in entry.split("::")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                f"malformed config_allow entry {entry!r} -- expected "
                f"'<Config/File.ini> :: <Section> :: <Key[*]>'"
            )
        file_field, section, key = parts
        rules.append(
            ConfigAllowRule(
                file=_normalize_prefix(file_field), section=section, key=key
            )
        )
    return tuple(rules)


# ---------------------------------------------------------------------------
# Reading a submitted ini: decode, and know when you could not
# ---------------------------------------------------------------------------

# Byte-order marks we can act on, LONGEST FIRST -- the UTF-32LE mark
# (ff fe 00 00) begins with the UTF-16LE mark (ff fe), so testing utf-16 first
# would decode a UTF-32LE file as UTF-16 and produce plausible-looking garbage.
_BOM_CODECS = (
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xfe\xff", "utf-16"),
    (b"\xff\xfe", "utf-16"),
)


def decode_ini_bytes(raw: bytes) -> str:
    """Decode UE ini bytes to text, or raise -- never guess, never mangle.

    If the file opens with a byte-order mark, decode with the codec that mark
    names; otherwise decode STRICT utf-8. Every decode is strict, so a file we
    cannot honestly read raises UnicodeDecodeError instead of returning text
    that merely looks like the file.

    NO ``errors="replace"``, NO latin-1 FALLBACK, deliberately. Both always
    succeed, which would erase the difference between "read it fine" and "could
    not read it" -- and the failure mode is not merely a missing answer, it is a
    WRONG one: mojibake diffed against the baseline reports a large, entirely
    fictional set of config changes. Strict decoding is what keeps
    ``OUTCOME_UNREADABLE`` a real, separate answer.

    WHY BOM-DRIVEN DECODING AT ALL, measured 2026-08-19. The previous code did
    ``read_text(encoding="utf-8")``. Re-encoding the REAL
    ``UE-projects/ThirdPerson/Config/DefaultEngine.ini`` to UTF-16 without
    altering one character -- same config, different bytes -- flipped this
    lane's answer from "no violations" to ``config file unreadable: 'utf-8'
    codec can't decode byte 0xff in position 0``, i.e. exit 4 on a submission
    that changed nothing. NOT OBSERVED IN A REAL RUN: all 13 committed
    ``UE-projects/*/Config/*.ini`` and all 6 config files captured by the
    2026-08-19 bench runs under ``C:/cb/bench-tree/runs/`` decode as valid utf-8
    today. It became REACHABLE when the collector started capturing config
    files on every live-project run, and the file is agent-writable, so its
    encoding is not ours to assume. Note the one grader that reads this file,
    ``introspect/t3_piercing_projectile.py``, already decodes ``utf-8-sig``
    with ``errors="replace"`` -- the gate was the stricter of the two, which is
    the wrong way round for the half that can reject the whole run.
    """
    for bom, codec in _BOM_CODECS:
        if raw.startswith(bom):
            return raw.decode(codec)
    return raw.decode("utf-8")


# ---------------------------------------------------------------------------
# The gate: four named outcomes
# ---------------------------------------------------------------------------

# The four answers this lane can give about ONE Config/ file. Module constants
# so callers and tests branch on an identifier rather than on a substring of an
# English reason line.
OUTCOME_UNCHANGED = "unchanged"
OUTCOME_ALLOWED = "allowed"
OUTCOME_DISALLOWED = "disallowed"
OUTCOME_UNREADABLE = "unreadable"

# Prefix carried by every OUTCOME_UNREADABLE reason, and by nothing else.
# Distinct from the "config change not allowed" prefix ON PURPOSE: an operator
# reading a rejected run must be able to tell "the agent edited something it may
# not" from "we could not look".
UNREADABLE_REASON_PREFIX = "config UNKNOWN"

# The reason prefix for an observed, uncovered change. Named so tests and
# callers stop hard-coding the sentence.
DISALLOWED_REASON_PREFIX = "config change not allowed"


@dataclass(frozen=True)
class ConfigFileOutcome:
    """What this lane concluded about ONE submitted Config/ file.

    ``kind`` is one of the four ``OUTCOME_*`` constants. ``changes`` is the full
    diff (empty for UNCHANGED, and for UNREADABLE, where no diff exists).
    ``violations`` is the ``(rel, reason)`` subset the runner must reject --
    empty for UNCHANGED and ALLOWED, non-empty for DISALLOWED and UNREADABLE.
    """

    rel: str
    kind: str
    changes: tuple = ()
    violations: tuple = ()

    @property
    def ok(self) -> bool:
        """True only when the file is affirmatively fine.

        UNREADABLE is deliberately NOT ok: we did not observe a permitted
        state, we failed to observe anything.
        """
        return not self.violations


def _unreadable(rel: str, detail: str) -> "ConfigFileOutcome":
    """Build the fail-closed outcome for a file we could not inspect.

    The reason leads with :data:`UNREADABLE_REASON_PREFIX` and states the
    verdict is UNDETERMINED, so it can never be misread as an observed policy
    violation -- we did not see a change, we failed to look. It is still a
    violation (the runner still exits 4): fail closed, and say so.
    """
    return ConfigFileOutcome(
        rel=rel,
        kind=OUTCOME_UNREADABLE,
        violations=(
            (
                rel,
                f"{UNREADABLE_REASON_PREFIX}: {detail} -- cannot compute the "
                "ini diff, so allowed-vs-disallowed is UNDETERMINED; "
                "failing closed",
            ),
        ),
    )


def classify_config_submission(
    submitted: Sequence[tuple[Path, str]],
    substrate_root: Path,
    rules: Sequence[ConfigAllowRule],
) -> list[ConfigFileOutcome]:
    """Classify every submitted Config/ file into one of the four outcomes.

    ``submitted`` is (abs_file, rel_path) pairs -- the shape of
    ``SandboxResult.accepted``. Non-Config rels are skipped entirely (not this
    lane's business; path policy already ran in sandbox.py) and produce no
    outcome. Output order follows ``submitted``.

    Per file, in this order:

      1. Read the submitted file's BYTES; an OSError is UNREADABLE.
      2. Read the baseline's bytes from ``substrate_root/rel`` when that file
         exists; an OSError there is UNREADABLE too. We cannot diff against a
         baseline we cannot load, and treating it as absent would silently
         reclassify every line of the submission as "added".
      3. BYTES EQUAL -> UNCHANGED, stop. Decided before any decode on purpose:
         identical bytes are the same config whatever the encoding is, so the
         overwhelmingly common case -- the collector captured a config file the
         agent never touched -- cannot be failed by a decode problem. This is
         not a new allowance: identical bytes always diffed to zero changes, so
         no DECODABLE submission changes answer here.
      4. Decode both with :func:`decode_ini_bytes`; a UnicodeDecodeError is
         UNREADABLE.
      5. Diff, and test each atom against the rules whose ``file`` is this rel.
         A file no rule names has no rules, so ANY change is uncovered -- that
         is the intended "no config_allow means no config edits" law, which
         several task specs' anti-gaming entries lean on by name.

    A MISSING baseline file (step 2 finds nothing) is not an error: the
    baseline is None and every entry diffs as "added", which is how a brand-new
    config file gets rule coverage demanded of it.

    Never exits, prints or grades -- the caller decides consequences.
    """
    outcomes: list[ConfigFileOutcome] = []
    substrate_root = Path(substrate_root)
    for abs_file, rel in submitted:
        if not rel.startswith("Config/"):
            continue

        try:
            new_bytes = Path(abs_file).read_bytes()
        except OSError as e:
            outcomes.append(_unreadable(rel, f"config file unreadable: {e}"))
            continue

        base_path = substrate_root / rel
        base_bytes = None
        if base_path.exists():
            try:
                base_bytes = base_path.read_bytes()
            except OSError as e:
                outcomes.append(
                    _unreadable(rel, f"config baseline unreadable: {e}")
                )
                continue

        # (3) Same bytes, same config. No decode attempted, none needed.
        if base_bytes is not None and base_bytes == new_bytes:
            outcomes.append(ConfigFileOutcome(rel=rel, kind=OUTCOME_UNCHANGED))
            continue

        try:
            new_text = decode_ini_bytes(new_bytes)
        except UnicodeDecodeError as e:
            outcomes.append(
                _unreadable(
                    rel,
                    "submitted config file could not be decoded as text "
                    f"(no usable BOM and not valid utf-8): {e}",
                )
            )
            continue

        base_text: Optional[str] = None
        if base_bytes is not None:
            try:
                base_text = decode_ini_bytes(base_bytes)
            except UnicodeDecodeError as e:
                outcomes.append(
                    _unreadable(
                        rel,
                        "config baseline could not be decoded as text "
                        f"(no usable BOM and not valid utf-8): {e}",
                    )
                )
                continue

        file_rules = [r for r in rules if r.file == rel]
        changes = diff_ue_ini(base_text, new_text)
        violations = tuple(
            (
                rel,
                f"{DISALLOWED_REASON_PREFIX}: [{change.section}] "
                f"{change.key} ({change.kind})",
            )
            for change in changes
            if not any(
                r.matches(rel, change.section, change.key) for r in file_rules
            )
        )
        if not changes:
            # Different bytes, identical config -- a line-ending or encoding
            # rewrite by the editor, say. Same answer as byte-identity, and the
            # answer the old code already gave.
            kind = OUTCOME_UNCHANGED
        elif violations:
            kind = OUTCOME_DISALLOWED
        else:
            kind = OUTCOME_ALLOWED
        outcomes.append(
            ConfigFileOutcome(
                rel=rel,
                kind=kind,
                changes=tuple(changes),
                violations=violations,
            )
        )
    return outcomes


def validate_config_submission(
    submitted: Sequence[tuple[Path, str]],
    substrate_root: Path,
    rules: Sequence[ConfigAllowRule],
) -> list[tuple[str, str]]:
    """The violation-list view of :func:`classify_config_submission`.

    DELEGATES -- it holds no rule of its own, it flattens each outcome's own
    ``violations``. This is the shape ``run_task.main`` consumes (it appends
    every ``(rel, reason)`` to ``sandbox_result.violations``, i.e. exit 4), and
    it is kept exactly so the runner needs no change. Call
    ``classify_config_submission`` directly when you need to tell UNCHANGED
    from ALLOWED, or DISALLOWED from UNREADABLE -- the distinction this
    flattening throws away.

    Returns the violation list; the caller decides the consequences (the runner
    treats any violation as SANDBOX-REJECT, exit 4).
    """
    return [
        v
        for outcome in classify_config_submission(
            submitted, substrate_root, rules
        )
        for v in outcome.violations
    ]
