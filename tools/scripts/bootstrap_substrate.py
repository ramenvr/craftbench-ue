#!/usr/bin/env python3
"""bootstrap_substrate.py - restore Epic's UE template content into the substrate.

WHY THIS EXISTS
---------------
The two projects under ``UE-projects/`` are the benchmark substrate. Most of
what is in them is CraftBench's own work (task maps, task scaffolds, the
verifier module) and ships in this repository. But the character rig, the
animation set, the prototyping meshes, the Enhanced Input assets and the three
gameplay Variants are Epic Games' Unreal Engine *template* content: CraftBench
does not own it and therefore cannot relicense it, and the UE EULA restricts
redistribution of engine Content to Engine Licensees - which a public git
repository cannot guarantee its readers are.

So this repository does not ship that content. It ships this script, which
copies the content out of the reader's OWN UE 5.8 install. That install is
where the content already lives - the restore costs one command and no
download, and it sidesteps the licensing question completely, because nothing
Epic authored ever leaves the reader's machine.

This is a plain file copy. There is no transformation, no codegen and no
network access: every restored byte is a byte that was already on your disk,
under ``<UE root>/Templates/``. The round trip is exact, and
``--verify-manifest`` proves it against a recorded sha256 manifest.

WHAT IS AND IS NOT RESTORED
---------------------------
RESTORED (881 files, ~272 MB) - Epic-authored Content only. See MAPPING below.

NOT RESTORED, because it is CraftBench's and is committed:
    Content/Maps/**                     the task maps - the benchmark itself
    Content/Tasks/**, Content/Data/**
    Content/__ExternalActors__/Maps/**  and __ExternalObjects__/Maps/**
    Source/**                           see the note on Source below.

NOT RESTORED, deliberately, although it IS Epic-authored: the 87 files under
``UE-projects/ThirdPerson/Source/``. Those descend from the engine's
``Templates/TP_ThirdPerson/Source/``, but the project wizard renamed the module
at creation time and CraftBench then modified two of the files
(``ThirdPerson.Build.cs`` and ``ThirdPersonEditor.Target.cs``, which is what
adds the ``CraftBenchTests`` verifier module to the editor target). 85 of the 87
round-trip byte-exact from the engine after a TP_ThirdPerson -> ThirdPerson
rename; two do not, and both are load-bearing for the build. A bootstrap that
restored 85 of 87 would hand the reader a project that does not compile, so the
Source tree stays in the repository, where it is small and is a derivative work
of a freely-licensed template. Content is the 272 MB and the licensing question;
Source is neither.

USAGE
-----
    py tools/scripts/bootstrap_substrate.py                 # restore
    py tools/scripts/bootstrap_substrate.py --check         # did it work? writes nothing
    py tools/scripts/bootstrap_substrate.py --ue-root "D:/UE_5.8"
    py tools/scripts/bootstrap_substrate.py --verify-manifest tools/scripts/epic-content-manifest.json

The UE root is resolved from ``--ue-root``, then ``$CB_UE_ROOT``, then the
per-platform Epic default - the same order the rest of the harness uses.

Exit codes: 0 success / 1 substrate incomplete or a verification mismatch /
2 the environment or arguments are wrong (nothing was attempted).

Safety: stdlib-only, py 3.11+ (works on 3.10), idempotent, and it writes ONLY
the paths named by the mapping table. Re-running is a no-op. It refuses rather
than overwriting a file whose bytes differ from the engine's, so it can never
quietly clobber local work. It never writes to the engine install, which it
opens read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, NoReturn, Optional, Tuple

# --------------------------------------------------------------------------- #
# The engine version this benchmark is pinned to.
#
# The mapping below is expressed as paths RELATIVE to the UE root, so nothing
# here is hardcoded to one install location and a sibling engine version with
# the same template layout would copy without edits. That is deliberate - and
# it is also exactly why the version is checked and refused loudly. CraftBench
# is engine-version pinned: grading a submission against 5.7's template content
# does not produce a convenience, it produces a silently wrong answer, because
# the reference results were measured against 5.8's assets. Restoring from the
# wrong engine is the one failure mode of this script that would not announce
# itself, so it is the one thing that is checked twice (engine version, and the
# per-row file counts recorded below).
# --------------------------------------------------------------------------- #
PINNED_MAJOR = 5
PINNED_MINOR = 8
PINNED_LABEL = "UE 5.8"

# The marker that says "this really is a UE install with the templates in it".
ROOT_MARKER = "Templates/TP_ThirdPerson"

# Epic-default install roots, most likely first, 5.8 before any sibling.
DEFAULT_UE_ROOTS = (
    "C:/Program Files/Epic Games/UE_5.8",       # Windows (Epic launcher default)
    "/Users/Shared/Epic Games/UE_5.8",          # macOS  (Epic launcher default)
    "/Applications/Epic Games/UE_5.8",          # macOS  (alt)
    "/opt/UnrealEngine/UE_5.8",                 # Linux  (source build)
)


class Row(NamedTuple):
    """One mapping row: copy ``<ue_root>/src`` -> ``<repo>/dest``, recursively.

    ``expect`` is the file count this row restored when the mapping was
    verified against a 5.8.1 install. It is an assertion, not a display value:
    a row that produces a different count means the engine is not the pinned
    5.8, or the install is incomplete, and the restore stops.
    """
    dest: str      # repo-relative destination directory
    src: str       # UE-root-relative source directory
    expect: int    # files this row must produce


# The four Epic-authored subdirectories inside the one-file-per-actor sidecar
# trees. This split is the subtle part of the whole mapping and the reason the
# OFPA rows are per-subdirectory instead of per-tree:
#
#   Content/__ExternalActors__/   765 tracked files
#                                 = 479 under these four dirs   (EPIC, restored)
#                                 + 286 under Maps/     (CRAFTBENCH, must stay)
#   Content/__ExternalObjects__/   51 tracked files
#                                 =  42 under these four dirs   (EPIC, restored)
#                                 +   9 under Maps/     (CRAFTBENCH, must stay)
#
# Copying either tree wholesale would be harmless (the engine has no Maps/) but
# would leave the reader one careless glob away from clobbering 295 files of
# the actual benchmark. Naming the four directories explicitly means Maps/ is
# never even a candidate.
EPIC_OFPA_SUBDIRS = (
    "ThirdPerson",
    "Variant_Combat",
    "Variant_Platforming",
    "Variant_SideScrolling",
)

# Repo paths this script must never write under, at any depth. Every planned
# write is checked against this list before a single byte is copied. The
# mapping above already excludes all of them by construction; this is the
# tripwire that keeps a future edit to the table from quietly changing that.
PROTECTED_PREFIXES = (
    "UE-projects/ThirdPerson/Content/Maps/",
    "UE-projects/ThirdPerson/Content/Tasks/",
    "UE-projects/ThirdPerson/Content/__ExternalActors__/Maps/",
    "UE-projects/ThirdPerson/Content/__ExternalObjects__/Maps/",
    "UE-projects/ThirdPerson/Source/",
    "UE-projects/CraftBenchTemplate/Content/Maps/",
    "UE-projects/CraftBenchTemplate/Content/Tasks/",
    "UE-projects/CraftBenchTemplate/Content/Data/",
    "UE-projects/CraftBenchTemplate/Source/",
)


def mapping() -> List[Row]:
    """The complete Epic-content mapping: 16 rows, 881 files.

    Every row was verified file-by-file against a sha256 manifest of the
    content as it stood before removal - same paths, same bytes, zero
    mismatches. Two rows share a source: both projects carry their own copy of
    the Mannequin character set, and the engine has exactly one.
    """
    rows = [
        # ---- ThirdPerson: the graded substrate ----------------------------
        Row("UE-projects/ThirdPerson/Content/Characters",
            "Templates/TemplateResources/High/Characters/Content", 128),
        Row("UE-projects/ThirdPerson/Content/ThirdPerson",
            "Templates/TP_ThirdPerson/Content/ThirdPerson", 5),
        Row("UE-projects/ThirdPerson/Content/Variant_Combat",
            "Templates/TP_ThirdPerson/Content/Variant_Combat", 31),
        Row("UE-projects/ThirdPerson/Content/Variant_SideScrolling",
            "Templates/TP_ThirdPerson/Content/Variant_SideScrolling", 19),
        Row("UE-projects/ThirdPerson/Content/Variant_Platforming",
            "Templates/TP_ThirdPerson/Content/Variant_Platforming", 11),
        # NOTE: LevelPrototyping and Input live under a further Content/ inside
        # the engine's TemplateResources feature packs (which also carry
        # FeaturePack/ and Media/ metadata dirs that are NOT project content
        # and are correctly excluded by pointing one level deeper).
        Row("UE-projects/ThirdPerson/Content/LevelPrototyping",
            "Templates/TemplateResources/High/LevelPrototyping/Content", 29),
        Row("UE-projects/ThirdPerson/Content/Input",
            "Templates/TemplateResources/High/Input/Content", 9),
        # ---- CraftBenchTemplate: the authoring substrate -------------------
        Row("UE-projects/CraftBenchTemplate/Content/Characters",
            "Templates/TemplateResources/High/Characters/Content", 128),
    ]
    # ---- one-file-per-actor sidecars, four Epic subdirs only, never Maps/ --
    ofpa_expect = {
        ("__ExternalActors__", "ThirdPerson"): 65,
        ("__ExternalActors__", "Variant_Combat"): 141,
        ("__ExternalActors__", "Variant_Platforming"): 147,
        ("__ExternalActors__", "Variant_SideScrolling"): 126,
        ("__ExternalObjects__", "ThirdPerson"): 2,
        ("__ExternalObjects__", "Variant_Combat"): 19,
        ("__ExternalObjects__", "Variant_Platforming"): 16,
        ("__ExternalObjects__", "Variant_SideScrolling"): 5,
    }
    for tree in ("__ExternalActors__", "__ExternalObjects__"):
        for sub in EPIC_OFPA_SUBDIRS:
            rows.append(Row(
                f"UE-projects/ThirdPerson/Content/{tree}/{sub}",
                f"Templates/TP_ThirdPerson/Content/{tree}/{sub}",
                ofpa_expect[(tree, sub)],
            ))
    return rows


TOTAL_EXPECTED = 881


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def sha256_of(path: Path) -> str:
    """Streaming sha256 - some restored assets are tens of MB."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mb(n_bytes: int) -> str:
    return f"{n_bytes / 1_000_000:.1f} MB"


def repo_root() -> Path:
    """<repo>/tools/scripts/bootstrap_substrate.py -> <repo>."""
    return Path(__file__).resolve().parents[2]


def die(*lines: str) -> NoReturn:
    """Print a FAIL block with the fix, and exit 2 having written nothing."""
    print(f"FAIL  {lines[0]}")
    for extra in lines[1:]:
        if not extra:
            print()                       # deliberate blank separator line
            continue
        for line in extra.splitlines():
            print(f"      {line}".rstrip())
    sys.exit(2)


def engine_version(ue_root: Path) -> Tuple[Optional[Tuple[int, int]], str]:
    """(major, minor) and a human label from Engine/Build/Build.version.

    Returns (None, reason) when the file is absent or unparseable - that is a
    WARN, not a FAIL, because a source build can legitimately lack it.
    """
    vf = ue_root / "Engine" / "Build" / "Build.version"
    try:
        data = json.loads(vf.read_text(encoding="utf-8-sig"))
        major = int(data["MajorVersion"])
        minor = int(data["MinorVersion"])
    except FileNotFoundError:
        return None, "Engine/Build/Build.version not found"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, f"Engine/Build/Build.version unreadable ({exc})"
    patch = data.get("PatchVersion")
    branch = data.get("BranchName") or "?"
    label = f"{major}.{minor}" + (f".{patch}" if patch is not None else "")
    return (major, minor), f"{label} ({branch})"


def resolve_ue_root(cli_value: Optional[str], allow_version_mismatch: bool) -> Path:
    """--ue-root, then $CB_UE_ROOT, then the platform default. Validated."""
    candidates: List[Tuple[str, str]] = []
    if cli_value:
        candidates.append((cli_value, "--ue-root"))
    elif os.environ.get("CB_UE_ROOT"):
        candidates.append((os.environ["CB_UE_ROOT"], "$CB_UE_ROOT"))
    else:
        candidates.extend((p, "platform default") for p in DEFAULT_UE_ROOTS)

    how_to_fix = (
        "Point this script at your UE 5.8 install, one of:\n"
        "    py tools/scripts/bootstrap_substrate.py --ue-root \"<path to UE_5.8>\"\n"
        "    set CB_UE_ROOT=<path to UE_5.8>          (Windows)\n"
        "    export CB_UE_ROOT=<path to UE_5.8>       (macOS / Linux)\n"
        "\n"
        f"The root is the directory that CONTAINS Engine/ and Templates/, e.g.\n"
        f"    {DEFAULT_UE_ROOTS[0]}\n"
        "\n"
        f"If you have no UE install: this benchmark is pinned to {PINNED_LABEL}. "
        "Install it\nfrom the Epic Games Launcher (~100 GB, allow hours) - "
        "the template content this\nscript restores ships inside it."
    )

    found: Optional[Path] = None
    tried: List[str] = []
    for raw, src in candidates:
        path = Path(raw).expanduser()
        # Report whether the path exists at all: "wrong path" and "exists but is
        # not an engine install" have different fixes, and the reader is about
        # to point this script at 100 GB of someone else's software.
        note = "" if path.is_dir() else "  (no such directory)"
        tried.append(f"{raw}    [{src}]{note}")
        if (path / ROOT_MARKER).is_dir():
            found = path
            break

    if found is None:
        die(
            "no Unreal Engine install found.",
            "Looked for a directory containing " + ROOT_MARKER + " at:",
            "\n".join("  " + t for t in tried),
            "",
            how_to_fix,
        )

    ue_root = found.resolve()
    version, label = engine_version(ue_root)
    if version is None:
        print(f"WARN  engine version could not be read ({label}).")
        print(f"      This benchmark is pinned to {PINNED_LABEL}; restoring from any other")
        print("      version produces a substrate that grades wrong without saying so.")
    elif version != (PINNED_MAJOR, PINNED_MINOR):
        if not allow_version_mismatch:
            die(
                f"engine at {ue_root} is UE {label}, but this benchmark is pinned "
                f"to {PINNED_LABEL}.",
                "",
                "This is refused, not warned about. The reference results, the",
                "verifier expectations and the committed task maps were all measured",
                f"against {PINNED_LABEL}'s template content. Restoring a sibling version's",
                "assets yields a substrate that still builds and still runs - and grades",
                "the wrong answer, silently.",
                "",
                f"Install {PINNED_LABEL} and pass --ue-root, or, if you have accepted the",
                "consequence and are deliberately experimenting off-pin, re-run with",
                "    --allow-version-mismatch",
            )
        print(f"WARN  engine is UE {label}, not the pinned {PINNED_LABEL} "
              f"(--allow-version-mismatch given).")
        print("      Grades produced on this substrate are NOT comparable to published results.")
    return ue_root


# --------------------------------------------------------------------------- #
# planning
# --------------------------------------------------------------------------- #

class Item(NamedTuple):
    rel: str        # repo-relative destination path
    src: Path       # absolute source path in the engine install
    row: int        # index into the mapping table


def build_plan(ue_root: Path, rows: List[Row]) -> Tuple[List[Item], List[str]]:
    """Walk every source row and produce the full list of intended writes.

    Returns (items, problems). ``problems`` is non-empty when a source row is
    missing or produced an unexpected file count - either means this engine
    install cannot serve the restore, and nothing should be written.
    """
    items: List[Item] = []
    problems: List[str] = []
    for idx, row in enumerate(rows):
        src_root = ue_root / row.src
        if not src_root.is_dir():
            problems.append(f"source directory missing: {row.src}")
            continue
        found = sorted(p for p in src_root.rglob("*") if p.is_file())
        for path in found:
            rel_in_row = path.relative_to(src_root).as_posix()
            items.append(Item(f"{row.dest}/{rel_in_row}", path, idx))
        if len(found) != row.expect:
            problems.append(
                f"{row.src}: found {len(found)} files, expected {row.expect} "
                f"(row -> {row.dest})"
            )
    return items, problems


def guard_plan(items: List[Item], repo: Path) -> None:
    """Refuse the whole run if any planned write is somewhere it must not be.

    Two independent checks, both cheap and both fatal:
      1. no planned path may fall under a PROTECTED_PREFIXES directory;
      2. every planned path must resolve inside <repo>/UE-projects/ (a symlink
         or a '..' component in the engine tree cannot escape the substrate).
    """
    substrate = (repo / "UE-projects").resolve()
    violations: List[str] = []
    for item in items:
        for prefix in PROTECTED_PREFIXES:
            if item.rel.startswith(prefix):
                violations.append(f"{item.rel}  (protected: {prefix})")
        resolved = (repo / item.rel).resolve()
        try:
            resolved.relative_to(substrate)
        except ValueError:
            violations.append(f"{item.rel}  (escapes UE-projects/ -> {resolved})")
    if violations:
        die(
            f"the mapping table would write {len(violations)} path(s) outside the "
            "Epic content set.",
            "This is a bug in this script's mapping table, not a problem with your",
            "install. Nothing was written. Offending paths:",
            "\n".join("  " + v for v in violations[:20]),
            ("  ... and %d more" % (len(violations) - 20)) if len(violations) > 20 else "",
        )


# --------------------------------------------------------------------------- #
# modes
# --------------------------------------------------------------------------- #

def print_header(repo: Path, ue_root: Path, mode: str) -> None:
    version, label = engine_version(ue_root)
    print(f"CraftBench substrate bootstrap - {mode}")
    print(f"  repo    {repo}")
    print(f"  engine  {ue_root}   [UE {label}]" if version
          else f"  engine  {ue_root}")
    print()


def mode_check(repo: Path, items: List[Item], rows: List[Row]) -> int:
    """Report presence/absence per row. Writes nothing. Non-zero if incomplete."""
    per_row_present = [0] * len(rows)
    per_row_missing = [0] * len(rows)
    per_row_differs = [0] * len(rows)
    missing_examples: List[str] = []
    differs_examples: List[str] = []

    for item in items:
        dest = repo / item.rel
        if not dest.is_file():
            per_row_missing[item.row] += 1
            if len(missing_examples) < 5:
                missing_examples.append(item.rel)
        elif dest.stat().st_size != item.src.stat().st_size or \
                sha256_of(dest) != sha256_of(item.src):
            per_row_differs[item.row] += 1
            if len(differs_examples) < 5:
                differs_examples.append(item.rel)
        else:
            per_row_present[item.row] += 1

    print("  present  differ  missing   row")
    for idx, row in enumerate(rows):
        status = "ok " if per_row_missing[idx] == 0 and per_row_differs[idx] == 0 else "-- "
        print(f"{status}{per_row_present[idx]:8d}{per_row_differs[idx]:8d}"
              f"{per_row_missing[idx]:9d}   {row.dest}")

    total_present = sum(per_row_present)
    total_missing = sum(per_row_missing)
    total_differs = sum(per_row_differs)
    print()
    print(f"  {total_present} present / {total_differs} differing / "
          f"{total_missing} missing   (expected {TOTAL_EXPECTED})")

    if total_missing == 0 and total_differs == 0:
        print()
        print(f"PASS  substrate is complete: all {total_present} Epic content files are "
              "present and match the engine.")
        return 0

    print()
    if total_missing:
        print(f"FAIL  {total_missing} Epic content file(s) are missing from the substrate.")
        for ex in missing_examples:
            print(f"        {ex}")
        if total_missing > len(missing_examples):
            print(f"        ... and {total_missing - len(missing_examples)} more")
    if total_differs:
        print(f"FAIL  {total_differs} file(s) differ from the engine's copy.")
        for ex in differs_examples:
            print(f"        {ex}")
        if total_differs > len(differs_examples):
            print(f"        ... and {total_differs - len(differs_examples)} more")
        print("      A differing file is either local work or a restore from a different")
        print("      engine version. This script will not overwrite it - inspect it, then")
        print("      delete it and re-run to take the engine's copy.")
    print()
    print("  Fix:  py tools/scripts/bootstrap_substrate.py")
    return 1


def mode_restore(repo: Path, items: List[Item], rows: List[Row], dry_run: bool) -> int:
    """Copy every planned file that is absent. Refuse on any byte conflict.

    Two passes, and the split matters: the entire plan is checked for conflicts
    BEFORE anything is written, so a collision two thirds of the way through
    cannot leave the substrate half-restored.
    """
    to_copy: List[Item] = []
    conflicts: List[str] = []
    already = 0

    for item in items:
        dest = repo / item.rel
        if not dest.is_file():
            to_copy.append(item)
            continue
        if dest.stat().st_size == item.src.stat().st_size and \
                sha256_of(dest) == sha256_of(item.src):
            already += 1          # idempotent: identical bytes, nothing to do
        else:
            conflicts.append(item.rel)

    if conflicts:
        die(
            f"{len(conflicts)} destination file(s) already exist with different bytes.",
            "Nothing was written. This script will not overwrite a file it did not",
            "put there - a differing file is local work, a partial restore from",
            "another engine version, or a genuine CraftBench asset that collided",
            "with the Epic mapping.",
            "",
            "\n".join("  " + c for c in conflicts[:20]),
            ("  ... and %d more" % (len(conflicts) - 20)) if len(conflicts) > 20 else "",
            "",
            "Inspect them. If they are stale, delete them and re-run.",
        )

    total_bytes = sum(i.src.stat().st_size for i in to_copy)

    if dry_run:
        print(f"  --dry-run: would copy {len(to_copy)} file(s), {mb(total_bytes)}; "
              f"{already} already present.")
        return 0

    per_row = [0] * len(rows)
    for item in to_copy:
        dest = repo / item.rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item.src, dest)
        per_row[item.row] += 1

    print("   copied  present   row")
    for idx, row in enumerate(rows):
        row_total = sum(1 for i in items if i.row == idx)
        print(f"{per_row[idx]:9d}{row_total:9d}   {row.dest}")
    print()
    print(f"PASS  restored {len(to_copy)} file(s), {mb(total_bytes)}"
          + (f"; {already} already present (no-op)." if already else "."))
    print()
    print("  Next:")
    print("    py tools/scripts/bootstrap_substrate.py --check    # confirm completeness")
    print("    cb doctor                                          # confirm the harness is ready")
    return 0


def mode_verify_manifest(repo: Path, items: List[Item], manifest_path: Path) -> int:
    """Compare the substrate against a {repo_relative_path: sha256} JSON.

    Entries the mapping table restores are the round-trip proof. Entries the
    manifest carries but this script does not manage (the Source/ tree, which
    ships in git) are checked too but reported under their own heading, so a
    reader cannot mistake "not restored by design" for "restore failed".
    """
    try:
        manifest: Dict[str, str] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"manifest not found: {manifest_path}")
    except (OSError, ValueError) as exc:
        die(f"manifest unreadable: {manifest_path}", str(exc))
    if not isinstance(manifest, dict):
        die(f"manifest is not a JSON object of {{path: sha256}}: {manifest_path}")

    managed = {item.rel for item in items}
    buckets = {
        "restored by this script": sorted(k for k in manifest if k in managed),
        "in the manifest, not restored by this script (tracked in git)":
            sorted(k for k in manifest if k not in managed),
    }

    print(f"  manifest  {manifest_path}   ({len(manifest)} entries)")
    print()
    failures = 0
    for heading, keys in buckets.items():
        if not keys:
            continue
        ok = 0
        missing: List[str] = []
        mismatch: List[str] = []
        for key in keys:
            path = repo / key
            if not path.is_file():
                missing.append(key)
            elif sha256_of(path) != manifest[key]:
                mismatch.append(key)
            else:
                ok += 1
        print(f"  {heading}:")
        print(f"    {ok} match / {len(mismatch)} mismatch / {len(missing)} missing "
              f"  (of {len(keys)})")
        for label, group in (("MISMATCH", mismatch), ("MISSING", missing)):
            for key in group[:10]:
                print(f"      {label}  {key}")
            if len(group) > 10:
                print(f"      ... and {len(group) - 10} more {label}")
        failures += len(missing) + len(mismatch)
        print()

    # A managed file that the manifest does not mention is also a finding: the
    # restore produced something the oracle never recorded.
    unrecorded = sorted(managed - set(manifest))
    if unrecorded:
        print(f"  restored but ABSENT from the manifest: {len(unrecorded)}")
        for key in unrecorded[:10]:
            print(f"      EXTRA  {key}")
        if len(unrecorded) > 10:
            print(f"      ... and {len(unrecorded) - 10} more")
        failures += len(unrecorded)
        print()

    if failures == 0:
        print(f"PASS  every one of the {len(manifest)} manifest entries is present "
              "with matching bytes.")
        return 0
    print(f"FAIL  {failures} manifest discrepancy/discrepancies.")
    return 1


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bootstrap_substrate.py",
        description=(
            "Restore Epic's UE template content into the CraftBench substrate by "
            "copying it out of your own UE 5.8 install. This repository does not "
            "redistribute Epic-owned engine content; your install already has it."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Resolution order for the engine: --ue-root, then $CB_UE_ROOT, then the\n"
            "platform default. Run with --check after restoring to confirm it worked."
        ),
    )
    parser.add_argument("--ue-root", metavar="DIR",
                        help="UE install root (the directory containing Engine/ and "
                             "Templates/). Overrides $CB_UE_ROOT.")
    parser.add_argument("--check", action="store_true",
                        help="report what is present/missing and exit non-zero if the "
                             "substrate is incomplete. Writes nothing.")
    parser.add_argument("--verify-manifest", metavar="JSON", type=Path,
                        help="compare the substrate against a {path: sha256} JSON "
                             "manifest and report every mismatch. Writes nothing.")
    parser.add_argument("--dry-run", action="store_true",
                        help="restore mode: say what would be copied, copy nothing.")
    parser.add_argument("--allow-version-mismatch", action="store_true",
                        help=f"proceed even if the engine is not the pinned "
                             f"{PINNED_LABEL}. Results become non-comparable; see --help.")
    parser.add_argument("--repo-root", metavar="DIR", type=Path,
                        help="repository root (default: inferred from this script's "
                             "own location).")
    args = parser.parse_args(argv)

    if args.check and args.verify_manifest:
        die("--check and --verify-manifest are separate modes; run them one at a time.")

    repo = (args.repo_root.expanduser().resolve() if args.repo_root else repo_root())
    if not (repo / "UE-projects").is_dir():
        die(
            f"no UE-projects/ directory under {repo}.",
            "This script must run from inside a CraftBench checkout. Either run it",
            "from the repository (py tools/scripts/bootstrap_substrate.py) or pass",
            "    --repo-root <path to the checkout>",
        )

    ue_root = resolve_ue_root(args.ue_root, args.allow_version_mismatch)
    rows = mapping()

    mode = ("check" if args.check else
            "verify-manifest" if args.verify_manifest else
            "restore (dry run)" if args.dry_run else "restore")
    print_header(repo, ue_root, mode)

    items, problems = build_plan(ue_root, rows)
    if problems:
        die(
            f"this engine install cannot serve the restore ({len(problems)} problem(s)).",
            "\n".join("  " + p for p in problems),
            "",
            f"Expected {TOTAL_EXPECTED} files across {len(rows)} directories, from a stock",
            f"{PINNED_LABEL} install. A missing directory or an unexpected file count means",
            "the engine is a different version, or its template feature packs were not",
            "installed. Verify the engine version, or reinstall the templates via the",
            "Epic Games Launcher.",
        )
    guard_plan(items, repo)

    if args.check:
        return mode_check(repo, items, rows)
    if args.verify_manifest:
        return mode_verify_manifest(
            repo, items, args.verify_manifest.expanduser().resolve())
    return mode_restore(repo, items, rows, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
