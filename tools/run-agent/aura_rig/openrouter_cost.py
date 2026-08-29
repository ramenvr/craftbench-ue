"""openrouter_cost — resolve a run's cost and model VERSION from OpenRouter's ledger.

WHY THIS EXISTS (2026-08-18). Cost for the openrouter arm used to be derived by
multiplying our token counts against a hand-maintained price table. That is an
estimate with three independent failure modes, all of which we hit:

  1. **A missing row silently costs nothing.** 17 graded runs recorded a cost of
     None while having genuinely spent — one of them 28.4M input tokens over 452
     turns. Nothing in the row said "unpriced"; it just read as free.
  2. **The table held the wrong prices.** Its rows were copied from Aura's
     ``model-pricing.ts``, i.e. what Aura bills us, not what OpenRouter charges.
     Same number, two different meanings, one column.
  3. **The pinned slug does not name the model that answered.** ``z-ai/glm-5.3``
     resolves to the dated permaslug ``z-ai/glm-5.3-20260816``; the same pin
     answered as grok-4.5 on one call and 4.6 on another. A published table that
     cites the pin is citing whatever the pin pointed at that day.

OpenRouter answers all three itself. Two sources, deliberately both used:

  * The **inline** ``usage`` block on each response (present only when the
    request sets ``usage: {"include": true}`` — see ``bare_wire``). Authoritative
    cost, no extra call, no lag. This is what lands in ``agent.cost_usd`` live.
  * ``GET /api/v1/generation?id=<generation_id>``. Same ``total_cost``, PLUS the
    dated ``model`` permaslug, ``provider_name`` and native token counts. This is
    the audit path and the only source for the run-record contract
    ``model_version`` field.

This module is the second one. It never computes a price; it reports what the
provider says it charged, or reports that it could not find out.

FOUR DELIBERATE CHOICES:

* **Never write a cost we did not receive.** A failed or pending lookup leaves
  the field absent, never 0.0. Under-reporting spend as zero is the exact bug
  this module exists to end, and re-introducing it in the fixer would be worse
  than the original.
* **Indexing lag is real and is not an error.** Measured: a generation 404s ~3s
  after the call and resolves by ~60s. A 404 is therefore reported as PENDING on
  the first passes and only becomes MISSING once the record is old enough that
  lag cannot explain it.
* **Version drift is an alarm, not a footnote.** More than one permaslug (or
  more than one provider) inside a single run means that row averages two
  systems. It is surfaced as a per-run flag, not folded into a mean.
* **Dry-run by default.** ``--apply`` is required to touch result.json, and the
  written block is additive under an ``openrouter`` key — nothing existing is
  overwritten, so a bad run of this tool cannot destroy a graded verdict.

Usage:
    python -m aura_rig.openrouter_cost                    # dry-run report, all runs
    python -m aura_rig.openrouter_cost runs/bare          # scope to a subtree
    python -m aura_rig.openrouter_cost --apply <run-dir>  # write the block
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

_API = "https://openrouter.ai/api/v1/generation"

#: A generation younger than this may legitimately not be indexed yet. Measured
#: 2026-08-18: 404 at 3s, present at ~60s. Anything younger and missing is
#: PENDING (re-runnable), anything older and missing is MISSING (a real gap).
LAG_GRACE_S = 180.0

#: Politeness between lookups. A long run can hold hundreds of generation ids and
#: there is no batch endpoint, so this is the difference between an audit and a
#: rate-limit incident.
_SLEEP_BETWEEN_S = 0.06

_TIMEOUT_S = 25.0


@dataclass
class GenerationFacts:
    """What OpenRouter says about one model call."""

    generation_id: str
    total_cost: Optional[float] = None
    model_permaslug: Optional[str] = None
    provider_name: Optional[str] = None
    native_tokens_prompt: Optional[int] = None
    native_tokens_completion: Optional[int] = None
    native_tokens_reasoning: Optional[int] = None
    #: "ok" | "pending" (lag, retry later) | "missing" | "error: ..."
    status: str = "error: not fetched"

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class RunAudit:
    """The provider-side truth for one run directory."""

    run_dir: str
    generation_ids: List[str] = field(default_factory=list)
    facts: List[GenerationFacts] = field(default_factory=list)
    recorded_cost_usd: Optional[float] = None

    @property
    def resolved(self) -> List[GenerationFacts]:
        return [f for f in self.facts if f.ok]

    @property
    def pending(self) -> int:
        return sum(1 for f in self.facts if f.status == "pending")

    @property
    def unresolved(self) -> int:
        return sum(1 for f in self.facts if not f.ok)

    @property
    def total_cost_usd(self) -> Optional[float]:
        """Provider-reported total, or None.

        None — never 0.0 — when nothing resolved, and None when the audit is
        INCOMPLETE: a partial sum silently under-reports, which is the failure
        this module exists to end. A run with no generation ids at all also
        returns None: it predates id capture and cannot be audited here.
        """
        if not self.facts or self.unresolved:
            return None
        vals = [f.total_cost for f in self.resolved if f.total_cost is not None]
        return sum(vals) if vals else None

    @property
    def model_versions(self) -> List[str]:
        return sorted({f.model_permaslug for f in self.resolved if f.model_permaslug})

    @property
    def providers(self) -> List[str]:
        return sorted({f.provider_name for f in self.resolved if f.provider_name})

    @property
    def drifted(self) -> bool:
        """True when this row averages more than one system under one label."""
        return len(self.model_versions) > 1 or len(self.providers) > 1

    def as_dict(self) -> dict:
        return {
            "source": "openrouter /api/v1/generation",
            "generations_total": len(self.generation_ids),
            "generations_resolved": len(self.resolved),
            "generations_pending": self.pending,
            "total_cost_usd": self.total_cost_usd,
            "model_versions": self.model_versions,
            "providers": self.providers,
            "version_drift": self.drifted,
            "native_tokens_prompt": _sum_or_none(self.resolved, "native_tokens_prompt"),
            "native_tokens_completion": _sum_or_none(self.resolved, "native_tokens_completion"),
            "native_tokens_reasoning": _sum_or_none(self.resolved, "native_tokens_reasoning"),
        }


def _sum_or_none(facts: Sequence[GenerationFacts], attr: str) -> Optional[int]:
    vals = [getattr(f, attr) for f in facts]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _http_get_json(url: str, api_key: str) -> tuple:
    """Returns ``(payload, http_status, error)``. Never raises on HTTP status."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status, None
    except urllib.error.HTTPError as e:
        return None, e.code, None
    except Exception as e:  # noqa: BLE001 - network shape varies; caller classifies
        return None, None, f"{type(e).__name__}: {e}"


def fetch_generation(
    generation_id: str,
    api_key: str,
    *,
    age_s: Optional[float] = None,
    http_get: Optional[Callable] = None,
) -> GenerationFacts:
    """One ledger lookup. ``age_s`` decides whether a 404 is lag or a real gap."""
    out = GenerationFacts(generation_id=generation_id)
    get = http_get or _http_get_json
    payload, status, err = get(f"{_API}?id={generation_id}", api_key)
    if err is not None:
        out.status = f"error: {err}"
        return out
    if status == 404:
        # A 404 is ambiguous by design: young => not indexed yet, old => gone.
        # Calling both "missing" would either hide a gap or invent one.
        out.status = "pending" if (age_s is None or age_s < LAG_GRACE_S) else "missing"
        return out
    if status != 200 or not isinstance(payload, dict):
        out.status = f"error: http {status}"
        return out
    d = payload.get("data") or {}
    out.total_cost = d.get("total_cost")
    out.model_permaslug = d.get("model")
    out.provider_name = d.get("provider_name")
    out.native_tokens_prompt = d.get("native_tokens_prompt")
    out.native_tokens_completion = d.get("native_tokens_completion")
    out.native_tokens_reasoning = d.get("native_tokens_reasoning")
    out.status = "ok"
    return out


def read_run(result_json: Path) -> Optional[RunAudit]:
    """Pull the audit inputs out of a result.json. None when it is not readable."""
    try:
        d = json.loads(Path(result_json).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    agent = d.get("agent") or {}
    ids = agent.get("generation_ids") or []
    return RunAudit(
        run_dir=str(Path(result_json).parent),
        generation_ids=[str(i) for i in ids],
        recorded_cost_usd=agent.get("cost_usd"),
    )


def audit_run(
    audit: RunAudit,
    api_key: str,
    *,
    age_s: Optional[float] = None,
    http_get: Optional[Callable] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> RunAudit:
    for i, gid in enumerate(audit.generation_ids):
        if i:
            sleep(_SLEEP_BETWEEN_S)
        audit.facts.append(
            fetch_generation(gid, api_key, age_s=age_s, http_get=http_get))
    return audit


def apply_to_result_json(result_json: Path, audit: RunAudit) -> bool:
    """Write the ``openrouter`` block. Additive; returns True when it wrote."""
    p = Path(result_json)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    d.setdefault("agent", {})["openrouter"] = audit.as_dict()
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")
    return True


def _run_age_s(result_json: Path) -> Optional[float]:
    try:
        return max(0.0, time.time() - Path(result_json).stat().st_mtime)
    except OSError:
        return None


def main(argv: List[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    apply = "--apply" in argv
    root = Path(args[0]) if args else Path("runs")

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY is not set — the ledger cannot be read, "
              "and this tool will not fall back to computing a price.",
              file=sys.stderr)
        return 2

    results = sorted(root.rglob("result.json")) if root.is_dir() else [root]
    if not results:
        print(f"no result.json under {root}")
        return 0

    auditable, skipped = [], 0
    for rj in results:
        a = read_run(rj)
        if a is None:
            continue
        if not a.generation_ids:
            skipped += 1
            continue
        auditable.append((rj, a))

    print(f"{len(results)} run(s) scanned | {len(auditable)} auditable | "
          f"{skipped} without generation ids")
    if skipped:
        print("  NOTE: runs without ids predate id capture (2026-08-18). Their cost "
              "cannot be recovered here — /api/v1/activity would be the only route "
              "and it requires a MANAGEMENT key, which the run key is not.")
    if not auditable:
        return 0

    drift, gaps, total = [], [], 0.0
    print(f"\n{'run':<58}{'gens':>5}{'provider $':>12}  model version(s)")
    for rj, a in auditable:
        audit_run(a, api_key, age_s=_run_age_s(rj))
        cost = a.total_cost_usd
        total += cost or 0.0
        shown = f"{cost:.6f}" if cost is not None else ("PENDING" if a.pending else "—")
        vers = ",".join(a.model_versions) or "?"
        print(f"{Path(a.run_dir).name[:56]:<58}{len(a.generation_ids):>5}{shown:>12}  {vers}")
        if a.drifted:
            drift.append(a)
        if cost is None:
            gaps.append(a)
        if apply and apply_to_result_json(rj, a):
            pass

    print(f"\nprovider-reported total over fully-resolved runs: ${total:.4f}")
    if drift:
        print(f"\nVERSION DRIFT — {len(drift)} run(s) were served by more than one "
              f"model version or provider. Each such row averages two systems under "
              f"one label and should not be reported as a single cell:")
        for a in drift:
            print(f"  {Path(a.run_dir).name}: models={a.model_versions} "
                  f"providers={a.providers}")
    if gaps:
        print(f"\n{len(gaps)} run(s) did not fully resolve (pending lag or missing "
              f"records); their cost is left ABSENT rather than partially summed.")
    if not apply:
        print("\n(dry run — pass --apply to write agent.openrouter into result.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
