"""ONE definition of "what counts as a submittable file", plus the collector.

WHY THIS FILE OWNS THE RULE (measured 2026-08-19). The collector used to gather a
STRICT SUBSET of what the verifier's sandbox accepts, and the gap was thrown away
before grading. Run
``runs/unreal-mcp/20260819-034252-t3-piercing-projectile-unreal-mcp-claude-sonnet-5``
graded FAIL with 8 of 9 L2I checks reporting the verifier saw NOTHING
(``PIERCE_CHANNEL_COUNT expected=1 got=0``, ``PIERCE_PRESET_MISSING name=Bullet
defined=[]``, ...). The agent had written a correct collision vocabulary to the
live project's ``Config/DefaultEngine.ini`` — a file the substrate manifest lists
in ``config_writable`` and the task's ``config_allow`` rules cover verbatim — but
``submission/`` held only the three ``.uasset`` files. The task was unwinnable as
wired, on every arm, because the rule was spelled ``manifest["writable"]`` in four
different places and ALL FOUR of them ignored ``asset_writable``,
``config_writable`` and ``deny``.

So the rule is not re-implemented here either: :class:`SubmissionRule` DELEGATES to
``tools/verify-single/sandbox.py`` — the module the verifier itself runs — so
"what the collector gathers" and "what the sandbox accepts" are the same code, not
two implementations that agree today. The one-line predicate is
``sandbox._is_writable``; it is imported by name AT IMPORT TIME on purpose, so a
rename over there fails every run-agent import loudly instead of silently drifting.
``tests/test_submission_rule.py`` pins the equivalence against sandbox's PUBLIC
``scan_submission`` over a real tree, which is the check that would catch a
semantic (rather than a naming) divergence.

Precedent for the dependency direction: ``workspace.py`` already imports
``task_layout`` out of ``verify-single/`` for exactly this reason — one source of
truth for a classification both sides must agree on.

WHAT THE RULE IS (all four manifest keys, real semantics — see the normative
``_comment`` in ``UE-projects/<substrate>/AGENT_WRITABLE.json``):
  * ``writable``        — PREFIXES; any file under one is submittable.
  * ``asset_writable``  — PREFIXES; only ``.uasset``/``.umap`` under one.
  * ``config_writable`` — EXACT FILE REL-PATHS, never prefixes. Path-accepted here,
                          then SEMANTICALLY diff-validated by the runner against the
                          task spec's ``config_allow`` (verify-single/config_lane.py).
  * ``deny``            — PREFIXES; DENY WINS over all three of the above.
Missing optional keys degrade to EMPTY (the same defaults sandbox declares), so a
substrate manifest that predates ``asset_writable``/``config_writable``/``deny``
behaves exactly as it did before this change — pinned by
``TestLegacyManifestUnchanged``, which demands byte-equality with the PRE-FIX
collector's output on the same tree.

ONE THING IS RESTATED RATHER THAN DELEGATED, and it is named here so nobody
assumes otherwise: ``from_manifest_data`` does its own field wiring, because
``sandbox.WritableManifest.load`` requires ``substrate``/``game_module`` keys that
play no part in acceptance and that the harness's own hand-built test manifests do
not carry. ``TestManifestParseMatchesTheVerifier`` runs BOTH loaders over every
committed manifest and demands an equal dataclass, so a key added to sandbox's
loader cannot be silently dropped by ours.

THE COLLECTOR. ``collect_submission`` re-walks a project dir and stages every
submittable file whose bytes differ from a BASELINE copy (or that has no baseline
counterpart, i.e. the agent created it). Two baselines, one function:
  * workspace lanes (bare / claude-p / openrouter) — baseline = the pristine
    substrate tree;
  * the live lane (aura-mcp / unreal-mcp) — baseline = ``<run>/live_backup``.
The re-walk (rather than the build-time ``workspace.writable_files`` list, frozen
before the agent ran) is what makes agent-CREATED files submittable; dropping it
silently emptied whole submissions for create-new-file tasks like gp-flight-mode.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from workspace import Workspace

# The verifier's sandbox is the AUTHORITY on submittability; see the module
# docstring. workspace.py already injects this same path for task_layout.
_VERIFY_SINGLE = str(Path(__file__).resolve().parents[1] / "verify-single")
if _VERIFY_SINGLE not in sys.path:
    sys.path.insert(0, _VERIFY_SINGLE)

from sandbox import WritableManifest as _WritableManifest  # noqa: E402
# Bound at import (not looked up per call) so a rename in sandbox.py is an
# ImportError every caller sees, never a silent behaviour change here.
from sandbox import _is_writable as _sandbox_is_writable  # noqa: E402
from sandbox import _matches_prefix as _sandbox_matches_prefix  # noqa: E402
from sandbox import _normalize_prefix as _sandbox_normalize_prefix  # noqa: E402


#: The per-substrate manifest filename, relative to a substrate/project root.
MANIFEST_NAME = "AGENT_WRITABLE.json"


@dataclass(frozen=True)
class SubmissionRule:
    """Whether a repo-relative path is a submittable file, per one substrate.

    Thin wrapper over ``sandbox.WritableManifest``: it exists so run.py and
    snapshot.py share ONE object instead of four copies of ``manifest["writable"]``,
    and so the walk helpers below have somewhere to live. It adds no acceptance
    logic of its own — ``accepts`` is a straight delegation.
    """

    manifest: _WritableManifest

    @classmethod
    def from_manifest_data(cls, data: dict) -> "SubmissionRule":
        """Build the rule from parsed AGENT_WRITABLE.json data.

        Field wiring only — every path is normalized by the VERIFIER's own
        ``_normalize_prefix`` (backslash → POSIX, leading ``./``), because a
        submission staged on Windows has to compare equal to the committed
        manifest exactly as it does inside sandbox.py. Missing optional keys read
        as EMPTY, which is what makes a substrate manifest that predates
        ``asset_writable`` / ``config_writable`` / ``deny`` behave as it always did.

        ``substrate`` / ``game_module`` default to "" rather than being required
        (``sandbox.WritableManifest.load`` requires them). They play no part in
        acceptance, and requiring them here would have turned every hand-built
        manifest in the harness's own tests into a KeyError — measured while
        wiring this in. ``tests/test_submission_rule.py`` pins this constructor
        against ``sandbox.WritableManifest.load`` on the REAL manifests, so a new
        key added over there cannot be silently dropped here.
        """
        def _paths(key: str) -> tuple:
            return tuple(_sandbox_normalize_prefix(p) for p in data.get(key, ()))

        return cls(_WritableManifest(
            substrate=str(data.get("substrate", "")),
            game_module=str(data.get("game_module", "")),
            writable=_paths("writable"),
            deny=_paths("deny"),
            asset_writable=_paths("asset_writable"),
            # Added 2026-08-24 with the first manifest to carry it. Dropping it
            # here while sandbox.py honoured it meant the harness and the
            # verifier disagreed about what the agent may write: files_under()
            # would skip a plugin asset the sandbox then ACCEPTED, so the
            # submission set and the graded set were different sets.
            plugin_asset_writable=_paths("plugin_asset_writable"),
            config_writable=_paths("config_writable"),
        ))

    @classmethod
    def load(cls, agent_writable_json: Path) -> "SubmissionRule":
        """Load the rule from a substrate's AGENT_WRITABLE.json."""
        data = json.loads(Path(agent_writable_json).read_text(encoding="utf-8"))
        return cls.from_manifest_data(data)

    @classmethod
    def for_substrate(cls, substrate_root: Path) -> "SubmissionRule":
        """Load the rule for a substrate/live-project root."""
        return cls.load(Path(substrate_root) / MANIFEST_NAME)

    def accepts(self, rel_posix: str) -> bool:
        """True iff the verifier's sandbox would ACCEPT this rel-path.

        Path acceptance only. A ``config_writable`` file still has to survive the
        runner's semantic ``config_allow`` diff gate (config_lane.py) afterwards —
        that gate is the whole reason a broad ``Config/`` prefix must never be
        added to a manifest, and it is not this function's job.
        """
        allowed, _reason = _sandbox_is_writable(rel_posix, self.manifest)
        return allowed

    def files_under(self, project_dir: Path) -> List[Path]:
        """Every existing file in ``project_dir`` the sandbox would accept.

        Sorted, so the backup / submission / restore sets are deterministic and a
        console listing is diffable between runs. Walks the whole tree exactly as
        the pre-fix ``_writable_files`` did — build output cannot match the rule,
        so pruning it would only be a speed change, and a wrong prune is how files
        get dropped in the first place.
        """
        project_dir = Path(project_dir)
        out: List[Path] = []
        for p in sorted(project_dir.rglob("*")):
            if not p.is_file():
                continue
            if self.accepts(p.relative_to(project_dir).as_posix()):
                out.append(p)
        return out

    def untracked_scan_prefixes(self) -> List[str]:
        """DIRECTORY prefixes for the live pre-drive hygiene scan.

        ``live_hygiene.quarantine_untracked_writable`` filters git's untracked
        list by PREFIX, so it cannot consume ``accepts`` directly. This returns
        the directory-shaped half of the rule (``writable`` + ``asset_writable``),
        dropping any prefix a ``deny`` prefix covers so DENY still WINS at that
        call site.

        Two deliberate approximations, stated because a reader will otherwise
        assume this equals ``accepts``:
          * No extension gate. An untracked NON-asset file under an
            ``asset_writable`` folder is quarantined even though the sandbox would
            reject it. Over-quarantine is the safe direction — quarantine MOVES
            bytes into the run dir, never deletes — and an untracked file in a
            folder only agents author into is a previous run's leftover by
            construction. Measured 2026-08-19, so the exposure is not overstated:
            in a frozen bench tree (a checkout at a pinned revision)
            none of the asset_writable folders except ``Content/Tasks/`` exist at
            all; in this tree the OFPA mirrors hold 144 files, all ``.uasset``,
            and every one of them is GITIGNORED (``.gitignore`` line 93 covers
            ``…/Tasks/_runreport/``). ``untracked_under`` runs
            ``git ls-files --others --exclude-standard``, which never lists an
            ignored file — so on both trees this widening quarantines exactly
            zero files today.
          * Whole-prefix deny coverage only. A deny prefix DEEPER than a writable
            one (``Content/Blueprints/Legacy/`` under ``Content/Blueprints/``)
            leaves the shallower prefix in the scan set. No current manifest has
            that shape.

        ``config_writable`` is EXCLUDED on purpose: those are exact paths to the
        substrate's OWN committed ini files. A config file is never an
        agent-created leftover, and quarantining one would move the project's
        engine config out of the tree.
        """
        prefixes = list(self.manifest.writable) + list(self.manifest.asset_writable)
        kept: List[str] = []
        for pre in prefixes:
            if any(_sandbox_matches_prefix(pre.rstrip("/"), deny)
                   for deny in self.manifest.deny):
                continue
            if pre not in kept:
                kept.append(pre)
        return kept


def collect_submission(
    project_dir: Path,
    baseline_dir: Path,
    submission_dir: Path,
    rule: SubmissionRule,
) -> List[Path]:
    """Stage every submittable file that differs from its baseline counterpart.

    ``baseline_dir`` is the pristine substrate (workspace lanes) or the live
    backup (live lane) — the ONE difference between the two flows, which is why
    they share this function rather than each carrying a copy of the loop.

    A file with no baseline counterpart is treated as agent-CREATED and staged.
    Returns the staged destination paths (under ``submission_dir``);
    ``submission_dir`` is created lazily, so "no edits" leaves no directory.
    """
    project_dir = Path(project_dir)
    baseline_dir = Path(baseline_dir)
    staged: List[Path] = []
    for src in rule.files_under(project_dir):
        rel = src.relative_to(project_dir)
        baseline = baseline_dir / rel
        if baseline.exists() and src.read_bytes() == baseline.read_bytes():
            continue
        dst = submission_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        staged.append(dst)
    return staged


def snapshot_submission(
    workspace: Workspace,
    submission_dir: Path,
    substrate_root: Path,
    rule: Optional[SubmissionRule] = None,
) -> List[Path]:
    """Copy modified/created submittable files from a workspace into submission_dir.

    The rule is loaded from the SUBSTRATE's manifest, not from
    ``workspace.writable_prefixes``: that field carries only the ``writable`` key
    (build_workspace uses it to classify which files the PROMPT lists as writable
    source), and reading the collector's rule out of it is precisely the defect
    this module now closes. Callers that already hold a rule pass it in; tests
    inject one built from a temp manifest.
    """
    if rule is None:
        rule = SubmissionRule.for_substrate(substrate_root)
    return collect_submission(
        workspace.project_dir, substrate_root, submission_dir, rule)
