# tools/verify-stability — the verifier-noise (b)->0 gate

CraftBench has exactly two variance sources and they **must never be conflated**
(the eval-stability design record, §1, §2b, §3):

- **(a) AGENT stochasticity** — same prompt → different deliverable → legitimately
  different verdict. This is the **SIGNAL**; report it as a pass-RATE over N
  (handled elsewhere: `run_batch.py --repeats` + `tools/compare`).
- **(b) VERIFIER flakiness** — the **SAME FIXED deliverable** → different verdict
  across runs. This is **NOISE and must be ~0**. It is the one testable invariant,
  and this tool is the instrument that measures it.

## What it does

`stability_check.py` grades **ONE FIXED reference-solution directory N times**
(default `--n 5`) by invoking `tools/verify-single/run_task.py` as a subprocess
with a **distinct `--report-json` per run**, then asserts across the N reports:

1. all `submission_sha` are **identical** — proves the deliverable was truly fixed.
   A reference dir is a pure byte-copy (`--harness filesystem`, no model call), so a
   differing sha means the *input itself* drifted (a setup bug), not a verifier flake.
2. all `overall` are **identical**.
3. all per-layer `tests_passed` / `tests_run` are **identical** — catches a flip
   that nets out to the same `overall`.

### Acceptance

| condition | exit | meaning |
|-----------|------|---------|
| variance == 0 | `0` | STABLE — verifier-noise == 0, the gate held |
| same fixed sha but disagreeing `overall` or per-layer counts | `1` | **P0 VERIFIER BUG** — never an agent result |
| `submission_sha` not constant across runs | `2` | DELIVERABLE NOT FIXED — the experiment is invalid (a setup bug, distinct from a verifier flake; includes the F1 substrate-pin `rejected`-vs-graded env flake) |
| could not complete N runs / parse a report | `3` | USAGE |

Any disagreement on a **constant `submission_sha`** is a **P0 verifier bug, full
stop** — it is printed as such and is *never* logged as an agent failure.

### Per-layer flip-rate attribution

So the noisy layer is attributable, the report breaks the flip rate down by noise
class per layer:

- **L1 exit-code flips** — `exit_flip_rate` (UBT exit code differs run-to-run).
- **L2 band/count flips** — `count_flip_rate` (`tests_passed`/`tests_run` pair differs).
- **L2I error-vs-pass flips** — `status_flip_rate` (layer status differs, e.g. a
  cold-boot/flush `error` on one run vs `pass` on a warm run).

Each rate is the fraction of runs that disagree with the modal value (`0.0` == all
agreed; a lone outlier among N reads as `1/N`).

## Usage

```sh
python3 tools/verify-stability/stability_check.py \
    --task tasks/cpp/t0-sanity-log-on-beginplay/task.md \
    --submission tasks/cpp/t0-sanity-log-on-beginplay/reference \
    --ue-root /path/to/UE_5.8 \
    --n 5 \
    --report-dir /tmp/cb-stability-t0
```

It writes `report_<i>.json` for each run plus an aggregate `stability.json` into
`--report-dir` (a tempdir if omitted), prints a human summary, and **exits with the
acceptance code above**.

## This is a budgeted / scheduled CI job, NOT per-PR

`stability_check.py` **REQUIRES a UE 5.8 install** because it actually grades —
each of the N runs is a full `run_task.py` (L1 UBT build + L2 PIE session). That is
minutes-to-tens-of-minutes × N, far too heavy for every PR. Run it as a
**scheduled / budgeted CI job per gold reference solution on every
substrate-or-verifier change** (the inputs that can introduce verifier noise),
gated on a fresh checkout (so F1/F4 working-tree drift can't poison it). The
cheap, per-PR clean-checkout invariant (hash-pin OK + maps tracked) lives
elsewhere (TODO #5); this is the heavy, periodic measurement of TODO #4.

## Tests (offline — NO UE)

The grading invocation is factored behind an injectable `grade_once` callable, so
the acceptance logic is unit-tested with **canned report dicts, no editor, no API
key, zero cost**:

```sh
python3 -m unittest discover tools/verify-stability/tests
```

Covers: a stable scenario (N identical reports → exit 0), a flaky-`overall`
scenario (one report differs → nonzero + P0 message), a per-layer-count flip that
nets the same `overall` (must still fail), and a non-constant `submission_sha`
(must error as deliverable-not-fixed). Pure stdlib.
