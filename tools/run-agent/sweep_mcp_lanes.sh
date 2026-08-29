#!/usr/bin/env sh
# MCP-lane task-major sweep, 2026-08-20.
#
# Shape comes from the owner's 2026-08-20 decisions ("coverage-first task order
# with arms interleaved within each task"):
#   tasks  = the 6 bp tasks BOTH MCP lanes already PASSed in the go/no-gos,
#            ordered fast -> slow so a box reclaimed early still leaves
#            COMPLETE task rows rather than a ragged partial grid
#   models = the pre-registered model panel + the named reserve (5).
#            opus-5 and gpt-5.6-terra are deliberately OUT (owner, 2026-08-20).
#   arms   = B (unreal-mcp) and C (aura-mcp), interleaved within each task so a
#            partial sweep still compares tool layers on equal task footing.
#
# Deliberately a `cb eval` loop, not `cb matrix`: matrix refuses aura-*/
# unreal-mcp slugs by design (cb.py::cmd_matrix), because each MCP cell needs
# its own editor bring-up.
#
# RESUMABLE: a cell whose result.json already exists is skipped, so this can be
# re-launched after a reboot / kill / commit-exhaustion abort without re-spending.
# Cells run STRICTLY SERIALLY — concurrent UE builds contend on Build.bat's
# engine-keyed mutex and the loser returns exit 1 with no compile errors, which
# grades as an agent FAIL (build_lock.py).
set -u

CEILING="${CEILING:-3600}"          # §6b: 40-min scored budget, 60-min kill ceiling
RUNS_ROOT="${RUNS_ROOT:-C:/cb/runs}"   # the junction target — short, for MAX_PATH
LOG_DIR="${LOG_DIR:-runs/sweep-mcp-20260820}"
SUBSTRATE="${SUBSTRATE:-UE-projects/ThirdPerson}"   # every task on the slate is bp/ThirdPerson
mkdir -p "$LOG_DIR"

# ---------------------------------------------------------------------------
# THE INTERPRETER, resolved ONCE and up front. `py -3.12` DOES NOT RESOLVE on
# this box and has not since 2026-07-28: the plain-3.12 registration disappeared
# and survives only as `-V:Astral/CPython3.12.11`, so the launcher exits 103
# ("No suitable Python runtime found"). `./cb` never noticed, because it carries a
# FALLBACK CHAIN (py -3.12 -> py -3 -> python3 -> python) and lands on py -3. The
# two direct calls in this file had no chain, and each failed SILENTLY, in its own
# direction:
#
#   * cell_done's probe ran as `if py -3.12 -c ...`. 103 is falsy, so every cell
#     read as not-done and RESUME WAS DEAD — a relaunch after a reboot re-spent
#     the whole grid instead of skipping it.
#   * the leak audit ran as `py -3.12 leak_audit.py ... --void || true`. That
#     `|| true` exists to swallow the audit's own legitimate non-zero codes
#     (1 contaminated / 2 nothing to audit / 3 park exposed) and it swallowed 103
#     along with them, so THE CONTAMINATION GUARD NEVER RAN. Every cell graded
#     since it was added is unaudited — on the same box where six drives were
#     measured reading the answer key.
#
# Resolved here rather than per call site, and ABORTING rather than falling back
# to a guess, because both uses are money- or integrity-critical: a probe that
# cannot run must stop the sweep, never answer "no".
resolve_py() {
  if [ -n "${SWEEP_PY:-}" ]; then
    if $SWEEP_PY -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
         >/dev/null 2>&1; then
      printf '%s' "$SWEEP_PY"; return 0
    fi
    echo "ABORT: SWEEP_PY=\"$SWEEP_PY\" is not a working Python 3.11+." >&2
    return 1
  fi
  for _cand in "py -3.12" "py -3" "python3" "python"; do
    if $_cand -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
         >/dev/null 2>&1; then
      printf '%s' "$_cand"; return 0
    fi
  done
  echo "ABORT: no working Python 3.11+ (tried py -3.12, py -3, python3, python)." >&2
  echo "       Set SWEEP_PY to one, e.g. SWEEP_PY=\"py -3.13\"." >&2
  return 1
}
PY="$(resolve_py)" || exit 9

# Build.bat, for the missing-binary self-heal below. Resolved from the same UE
# root every other path uses; absent is not fatal here because the heal is the
# only consumer and it checks before shelling.
UE_ROOT_BAT="${UE_ROOT_BAT:-${CB_UE_ROOT:-C:/Program Files/Epic Games/UE_5.8}/Engine/Build/BatchFiles/Build.bat}"
echo "interpreter: $PY ($($PY -c 'import sys; print(sys.version.split()[0])' 2>/dev/null))"

# PRECONDITION: stop OneDrive — step 3 of the brief's hygiene playbook
# ("OneDrive: paused, or the repo path excluded from sync"). It is one of the
# three holders the playbook names for the fairness-hide lock, and this box's
# measured precedent (the 2026-08-11 editor balloon WAS OneDrive); it also syncs
# this repo path, so it holds .uasset handles, and it is the ~28-30 GB commit leak
# the owner disabled that day — which a reboot undoes.
# Calibrated claim, since I got this wrong in both directions on 2026-08-20: it is
# a LIKELY holder, not THE holder. A lock recurred with OneDrive verifiably
# stopped, so stopping it is necessary-not-sufficient. No envgate probe covers it,
# so the sweep enforces it itself.
if tasklist 2>/dev/null | grep -qi "OneDrive"; then
  echo "PRECONDITION: stopping OneDrive (holds .uasset handles; beats the fairness hide)"
  powershell -NoProfile -Command "Get-Process -Name 'OneDrive*' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
fi

# Between cells, AFTER the editor is dead: the fairness restore runs while the
# lane's editor is still up, so it can log `NOT RESTORED / WinError 32` on locked
# assets and still report PASS. That was benign on 2026-08-20 only because the
# locked bytes happened to be identical — a drive that MODIFIED those assets
# would leave the modified bytes live and hand them to the next cell. Grading
# materializes the substrate from git HEAD and each cell's deliverable is already
# captured under its own run dir, so resetting the live tree here loses nothing.
# Scoped to the substrate's Content/ + Source/ ONLY: never a repo-wide checkout,
# because that could traverse a locally-supplied Plugins/ tree and a checkout
# through a symlink there deletes files outside this repository.
reset_substrate() {
  # Config/ and the .uproject are the two paths NO restore owns: Config/ sits
  # outside the writable backup tree (only the config-overlay revert touches it,
  # and only what it applied) and the .uproject is staged per drive. Either
  # left dirty ABORTS the next cell exit 4 pre-spend — measured 2026-08-22, an
  # agent's DefaultGameplayTags.ini edit survived and would have burned all 15
  # remaining cells at ~4.5 min of bring-up each.
  # FILE/dir-scoped deliberately: a locally-supplied Plugins/ tree may be symlinks
  # to a checkout elsewhere, and a checkout through them deletes files there.
  _paths="$SUBSTRATE/Content $SUBSTRATE/Source $SUBSTRATE/Config"
  for _up in "$SUBSTRATE"/*.uproject; do
    [ -f "$_up" ] && _paths="$_paths $_up"
  done
  dirty="$(git status --short -- $_paths 2>/dev/null)"
  if [ -n "$dirty" ]; then
    echo "  post-cell: substrate dirty after restore — resetting from git HEAD:"
    printf '%s\n' "$dirty" | head -10
    git checkout -- $_paths 2>&1 | head -3
  fi
}

# Overridable so a new block reuses this loop instead of forking it. Edit ONLY
# while the script is not running: sh reads a script incrementally.
TASKS="${TASKS:-bp/t1-third-person-chase-camera
bp/t1-dawn-fog-lighting-rig
bp/gp-poison-dot-stack-bp
bp/t3-piercing-projectile
bp/gp-dot-aoe-burn-bp
bp/gp-glide-stamina-bp}"

# The run plan pins these four. qwen/qwen3.8-max is the NAMED RESERVE,
# promoted only by a logged swap when a pinned family is unservable — it is
# not a fifth arm, and the 2026-08-22 sweep ran it as one.
MODELS="${MODELS:-claude-sonnet-5
deepseek/deepseek-v4-pro-0813
x-ai/grok-4.6
google/gemini-3.7-flash}"

LANES="${LANES:-unreal-mcp aura-mcp}"

# A clean pause. `touch` this and the loop stops at the next CELL BOUNDARY --
# after the in-flight cell has been graded AND audited, never mid-drive.
#
# Why a flag and not a signal: killing the loop from outside cannot be done
# safely. Measured 2026-08-23 -- a waiter polling every 45s for `cb eval` to
# clear never caught the gap, because the loop starts the next cell within
# seconds. Tightening the poll only narrows the race; it does not remove it. And
# killing mid-cell skips that cell's post-cell leak audit (issue 13), which is
# how a contaminated PASS got banked on 2026-08-23.
#
# The flag is CONSUMED (deleted) when it fires, so a forgotten one can never
# silently refuse to start a later sweep -- the same footgun class as an unset
# CRAFTBENCH_L1_MAX_PARALLEL, where the dangerous value is the one nobody sees.
STOP_FLAG="${STOP_FLAG:-runs/.sweep-stop}"

stop_requested() {
  [ -e "$STOP_FLAG" ] || return 1
  rm -f "$STOP_FLAG"
  echo
  echo "=== STOP REQUESTED ($STOP_FLAG) — pausing at the cell boundary ==="
  echo "    The in-flight cell finished and was audited; nothing is mid-drive."
  echo "    Flag consumed, so the next launch is not blocked. Relaunch to resume:"
  echo "    graded cells are skipped, so nothing is re-spent."
  return 0
}

# The fairness-hide file-lock abort. Per the owner's playbook in
# the 2026-08-20 overnight-matrix brief this is the anti-cheat failing
# CLOSED, pre-spend: $0, no graded verdict, and the hide self-heals on the next
# run. It means a STALE PROCESS holds the tree (UE only locks packages it has
# LOADED, and a fresh editor sits on the default level), so the remedy is box
# hygiene — `./cb down`, an empty editor tasklist, OneDrive paused, no concurrent
# refgate/test suites — and explicitly NEVER a code change or
# CB_ALLOW_FOREIGN_EDITOR=1. Retrying after that hygiene is therefore the
# prescribed action, not a re-roll: the cell produced no verdict to re-roll.
is_harness_lock_abort() {
  grep -q "fairness move still locked after" "$1" 2>/dev/null
}

editors_up() { tasklist 2>/dev/null | grep -icE 'UnrealEditor' || true; }

# The three SERVER ports the vendor stack used to bind (hosting, client,
# dev-browser). Only the aura-mcp lane ever raised them, and that lane is not
# runnable from this repository; the gate below is kept because it also catches
# a stray editor left behind by any arm.
#
# The trailing-space match is not cosmetic: netstat prints `127.0.0.1:3000` with
# the address column space-padded, and a bare `:3000` substring-matches `:30010`,
# the editor's own Remote Control port. That would make the gate read a live
# editor as a live stack and vice versa.
#
# :41299 (the logging proxy) is deliberately NOT here. It is the operator's, it
# holds no editor, and `cb down` does not own it.
stack_ports_up() {
  netstat -ano 2>/dev/null | grep -E 'LISTENING' \
    | grep -cE ':(3000|3002|9222)[[:space:]]' || true
}

# `cb down` RETURNS BEFORE THE EDITOR EXITS — measured 2026-08-20: returned at
# t+3s, process gone at t+7s. Checking immediately after it returns catches the
# editor mid-exit, and starting the next cell there hands the fairness hide a
# live holder (WinError 5). So wait for the process to actually go.
#
# WAITING ON THE EDITOR ALONE IS NOT ENOUGH — measured 2026-08-25, and it cost
# three consecutive cells. The chain:
#
#   1. an aura-mcp cell ends leaving an ORPHANED STACK MANIFEST. Its own log says
#      so: "stack left UP but no live session anchor resolved - the janitor will
#      tear it down within ~1 poll";
#   2. this gate saw `editors_up == 0`, called the box clean, and released the
#      next cell;
#   3. the JANITOR then reaped that orphan with a full `stack.stop_stack`, which
#      contains a BLANKET `kill_by_image("UnrealEditor")` (janitor.py:190);
#   4. so it killed the NEXT cell's editor.
#
# runs/.kill-audit.log has it exactly: `02:15:05 pid=39140 image=UnrealEditor
# reason=kill_by_image` — three seconds after that cell started. The cell before
# it died the same way, 0.96 s after its editor bound :30010, and the harness
# reported "EXITED before binding ... missing/out-of-date plugin binary" for what
# was actually a clean external shutdown of a correctly-loaded editor.
#
# So the gate now also waits for the SERVER ports. That is the observable proof
# that `stop_stack` ran to completion and consumed the manifest, which is what
# makes a pending janitor reap impossible rather than merely unlikely.
hygiene_gate() {
  _tag="${1:-cell}"
  for attempt in 1 2; do
    ./cb down > "$LOG_DIR/down-$_tag-$attempt.log" 2>&1 || true
    waited=0
    while { [ "$(editors_up)" -gt 0 ] || [ "$(stack_ports_up)" -gt 0 ]; } \
          && [ "$waited" -lt 90 ]; do
      sleep 3; waited=$((waited + 3))
    done
    if [ "$(editors_up)" -eq 0 ] && [ "$(stack_ports_up)" -eq 0 ]; then
      [ "$waited" -gt 6 ] && echo "  teardown complete after ${waited}s"
      return 0
    fi
    echo "  WARN teardown attempt $attempt: editors=$(editors_up) \
stack-ports=$(stack_ports_up) after ${waited}s"
  done
  echo "  ABORT: an editor or a stack server survived two full teardowns."
  echo "         An editor locks the next cell's hide (WinError 5); a surviving"
  echo "         stack means a janitor reap is still pending, and that reap"
  echo "         blanket-kills the next cell's editor (see the note above)."
  echo "         Clear it by hand (cb down; check tasklist + netstat) and resume."
  return 1
}

# Has (backend, task, model) already produced a GRADED verdict? Model slugs
# contain '/', which run.py flattens to '_' in the run id.
#
# "result.json exists" is NOT the test, and that distinction is load-bearing: a
# non-graded verdict (AGENT-CONFIG-ERROR, HARNESS-ERROR, ERROR, TIMEOUT,
# UNGRADED, COMMIT-EXHAUSTED) means the cell was never measured, so skipping on
# one would let a harness fault permanently occupy a cell and silently shrink the
# grid. Measured 2026-08-20: a `model_not_found` run wrote a result.json, and the
# first cut of this function would have skipped that cell forever on the strength
# of it. Graded set mirrors adapters/base.GRADED_VERDICTS (PASS/FAIL plus the
# three MODEL_OUTCOME_VERDICTS) — asked of the harness rather than hardcoded, so
# the two cannot drift.
cell_done() {
  _lane="$1"; _task="$2"; _model="$3"
  _bare="$(basename "$_task")"
  _slug="$(printf '%s' "$_model" | tr '/' '_')"
  for d in "$RUNS_ROOT/$_lane"/*"-$_bare-$_lane-$_slug"; do
    [ -f "$d/result.json" ] || continue
    # Exit 0 graded, 1 not graded, 9 COULD NOT DECIDE. The third code is the
    # point: "could not read it" and "it is not graded" both used to collapse
    # into falsy, and a falsy answer re-spends a cell that was already paid for.
    $PY -c "
import json, sys
sys.path.insert(0, r'tools/run-agent')
try:
    from adapters.base import is_graded_verdict
    v = json.load(open(sys.argv[1], encoding='utf-8')).get('overall')
except Exception as exc:
    print('cell_done: could not decide: %s' % exc, file=sys.stderr)
    sys.exit(9)
sys.exit(0 if is_graded_verdict(v) else 1)
" "$d/result.json"
    _crc=$?              # captured before `case`, same reason as leak_audit below
    case "$_crc" in
      0) return 0 ;;
      1) ;;                 # a real, readable, non-graded verdict — cell is open
      *) echo "ABORT: cell_done could not read $d/result.json (exit $_crc)." >&2
         echo "       Resuming blind re-spends cells already paid for, so this" >&2
         echo "       stops instead of guessing." >&2
         exit 8 ;;
    esac
  done
  return 1
}

# An abandoned repo-level hide is SELF-DEADLOCKING, not self-healing: it renames
# tools/verify-single aside, and aura_rig/tasks.py imports spec from there, so cb
# cannot start and therefore cannot reach its own heal path. Measured 2026-08-20:
# 43 cells failed in ~5s each on `No module named 'spec'` and the loop raced the
# whole grid. Refuse instead of racing.
assert_tree_intact() {
  for req in tools/verify-single tasks .git; do
    if [ ! -e "$req" ]; then
      echo "ABORT: $req is missing — a previous run's answer-key hide was abandoned."
      echo "       Restore it (fairness.stage_fairness_restore from the newest"
      echo "       runs/*/*/fairness_backup) before sweeping; cb cannot self-heal this."
      return 1
    fi
  done
  return 0
}

# One sweep per box: two loops interleaving cells means each one's `cb down` kills
# the other's editor mid-drive, which is how the hide above got abandoned.
LOCK="$LOG_DIR/.sweep.lock"
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "ABORT: sweep already running (pid $(cat "$LOCK")). Stop it first."
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

assert_tree_intact || exit 1

# A live --live-project run holds runs/.live-run.lock for its whole
# hide->drive->restore->grade span, and run.py refuses (exit 4) rather than let
# two of them share one tree. A refused cell looks like a finished cell to this
# loop, so a single survivor silently ate 25 cells on 2026-08-21 (two whole task
# rows). Refuse to START while one is in flight.
#
# ASK THE LOCK, DO NOT COUNT PROCESSES. sweep_probes.py was written for exactly
# this and then never called: the loop kept the process count it was meant to
# replace. That count is not merely noisy, it is unreliable in the direction that
# COSTS a sweep — it read "6 live runs" and "loop=4" on 2026-08-21 when the truth
# was 1 and 0, and a false positive here refuses to start at all. runs/.live-run.lock
# is an OS fd lock, so is_live_run_active cannot be wrong about itself.
# Exit 0 = idle, 1 = busy, 2 = could not measure; 2 aborts, because "I could not
# tell" must not be read as "clear" when being wrong costs the whole grid.
$PY tools/run-agent/sweep_probes.py live-run
_prc=$?
case "$_prc" in
  0) ;;
  1) echo "ABORT: a live-project run is in flight (runs/.live-run.lock is held)."
     echo "       Every cell here would refuse (exit 4) at \$0 and look finished to"
     echo "       the resume check. Wait for it or kill it, then resume."
     exit 1 ;;
  *) echo "ABORT: could not measure the live-run lock (sweep_probes exit $_prc)." >&2
     echo "       Not treated as idle: being wrong here silently eats cells." >&2
     exit 2 ;;
esac


# COVERAGE-STAMP. The cost ledger is only as good as the window the proxy was
# up for, and block 1 proved that is not something to assume: the usage log
# began at 18:10Z while the first OpenRouter cell ran at 06:24Z, so several
# cells' spend was simply absent. Worse, the absence was UNEVEN across models
# (34-107% when checked against the gateway dashboard), which distorts
# model-to-model comparison far more than a uniform undercount would.
#
# `proxy_base_url_for` already refuses to start when no proxy answers, so this
# does not gate; it RECORDS, so any later analysis can prove coverage instead of
# assuming it. Written once, before the first cell.
if [ -n "${LOG_DIR:-}" ]; then
  mkdir -p "$LOG_DIR" 2>/dev/null || true
  {
    echo "sweep_start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "proxy_healthz=$(curl -s -m 5 http://127.0.0.1:41299/healthz 2>/dev/null || echo UNREACHABLE)"
    _ulog="${CB_TMP:-${TEMP:-/tmp}}/cb-anthropic-usage.jsonl"
    echo "usage_log=$_ulog"
    echo "usage_log_lines_at_start=$(wc -l < "$_ulog" 2>/dev/null || echo 0)"
    echo "# A later cost analysis must confirm the log's FIRST row is at or"
    echo "# before the first OpenRouter cell. If it is not, the ledger is"
    echo "# incomplete and its per-model totals are not comparable."
    echo ""
    # RESOURCE HEADROOM AT START. Both per-cell gates are exhaustible and neither
    # is checked before a block commits to 20+ hours:
    #   * disk   -- envgate WD_FREE_FAIL_GB=15. Workdirs accumulate; 178 orphans
    #               held 67 GB and took C: to 11.3 GB mid-block.
    #   * commit -- floor 10 GB. Spent by whatever else runs on the box (Unity,
    #               Chrome, the GPU overlay), nothing to do with CraftBench.
    # Measured 2026-08-28: both crossed mid-block, 189 cells refused at exit=2
    # over ~1 hour. Every refusal was pre-spend, so the cost was wall-clock only
    # -- but a block that STARTS near a floor is one that will stop at it, and
    # nothing recorded the starting margin. This does not gate; it records, so
    # "did we start with room" is answerable afterwards.
    echo "disk_c_free_gb=$(powershell -NoProfile -Command "'{0:N1}' -f ((Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\").FreeSpace/1GB)" 2>/dev/null || echo unknown)"
    echo "commit_free_gb=$(powershell -NoProfile -Command "'{0:N1}' -f ((Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory/1MB)" 2>/dev/null || echo unknown)"
    echo "# Gates: disk needs 15 GB (envgate WD_FREE_FAIL_GB), commit needs 10 GB."
    echo "# Starting within a few GB of either means the block will stall part-way."
  } > "$LOG_DIR/COVERAGE-STAMP.txt"
  echo "  ..    cost-ledger coverage stamped -> $LOG_DIR/COVERAGE-STAMP.txt"
fi

total=0; ran=0; skipped=0
for task in $TASKS; do
  for model in $MODELS; do
    for lane in $LANES; do
      total=$((total + 1))
      # Checked BEFORE cell_done so a pause costs nothing: the previous cell is
      # graded and audited, and this one has not spent a token.
      if stop_requested; then
        echo "=== sweep PAUSED: $total cells seen, $ran run, $skipped skipped ==="
        exit 0
      fi
      if cell_done "$lane" "$task" "$model"; then
        echo "[skip] $lane :: $task :: $model (result.json present)"
        skipped=$((skipped + 1))
        continue
      fi
      assert_tree_intact || exit 1
      # ISSUE 11: refuse to drive a project whose verifier module's build
      # products are poisoned. An agent recompile while fixtures were stubbed
      # bakes the stubs into UnrealEditor-CraftBenchTests.dll; the engine then
      # cannot initialise the module and NO editor starts, on either substrate,
      # for any lane. Nine consecutive cells died that way at ~2 min each while
      # the stack log blamed "crash on startup", and the 21-check preflight
      # passed every one of them. The restore now invalidates the products when
      # it detects the rewrite; this covers the case it CANNOT — a run killed
      # before its restore ran, which leaves the marker as the only trace.
      _poison="$($PY -c "
import sys
sys.path.insert(0, r'tools/run-agent')
from fairness import verifier_build_suspect
why = verifier_build_suspect(sys.argv[1])
print(why or '')
" "$SUBSTRATE" 2>/dev/null)"
      # SELF-HEAL THE MISSING-BINARY CASE, because it recurs after almost every
      # cell. The restore INVALIDATES (deletes) the verifier build products
      # whenever an agent recompiles them while the fixtures are stubbed --
      # correct, since a recompile bakes the stubs in -- and its log says "the
      # next build regenerates them". That next build is L1, which builds a
      # WORKDIR COPY; the LIVE project is never rebuilt. So on 2026-08-25 cell 1
      # passed and every later cell died, on BOTH lanes, until the editor target
      # was rebuilt by hand.
      #
      # Aborting here would be correct but useless: the sweep would stop after
      # essentially every cell that edits C++. Rebuilding is the action the
      # message asks for, it is deterministic (~4 min CraftBenchTemplate, ~13 min
      # ThirdPerson from cold; far less incrementally), and it changes NOTHING the
      # grade reads -- the graded substrate is materialised from git HEAD, and
      # `Binaries/` is gitignored.
      #
      # Scoped to MISSING only. A POISONED marker still aborts: that one means
      # the products could not be cleaned automatically, and rebuilding on top of
      # a poisoned tree would bake the stubs in deeper.
      if [ -n "$_poison" ] && [ "${_poison#*is MISSING}" != "$_poison" ]; then
        echo "  HEAL  $SUBSTRATE declares a module with no binary — rebuilding the"
        echo "        editor target (the live project is never rebuilt by L1)."
        _tgt="$(basename "$SUBSTRATE")Editor"
        _proj="$(ls "$SUBSTRATE"/*.uproject 2>/dev/null | head -1)"
        if [ -z "$_proj" ]; then
          echo "ABORT: no .uproject under $SUBSTRATE — cannot heal."
          exit 6
        fi
        # UBT resolves -Project= ITSELF and REJECTS a path relative to the
        # shell's cwd -- "Unable to find project file based on argument
        # UE-projects/ThirdPerson/ThirdPerson.uproject", which is exactly how
        # the first real heal failed on 2026-08-25. $SUBSTRATE is relative by
        # design (the launcher sets UE-projects/ThirdPerson so one value serves
        # both the fitness probe and the python calls), so the project path has
        # to be absolutised HERE, in the drive-letter form UBT parses.
        #
        # Verifying the rebuild by hand is what HID this: the hand-run command
        # used an absolute path, so it proved the build works and proved nothing
        # about the argument the script actually assembles. `cygpath -m` alone
        # is not enough either -- on a relative input it returns it unchanged;
        # -a is the part that absolutises.
        if command -v cygpath >/dev/null 2>&1; then
          _proj="$(cygpath -m -a "$_proj")"
        else
          _proj="$(cd "$(dirname "$_proj")" && pwd)/$(basename "$_proj")"
        fi
        # Per-SUBSTRATE, appended, timestamped. NOT "$safe" -- that is
        # assigned BELOW this block, so here it is empty on the first cell
        # and holds the PREVIOUS cell's name on every later one. The heal is
        # a property of the substrate anyway, and appending keeps every heal
        # for a project in one file instead of overwriting the last one.
        _hlog="$LOG_DIR/heal-$(basename "$SUBSTRATE").log"
        echo "=== heal $(date -u +%Y%m%dT%H%M%SZ) | $lane:$model | $task ===" >> "$_hlog"
        "$UE_ROOT_BAT" "$_tgt" Win64 Development -Project="$_proj" -WaitMutex \
            >> "$_hlog" 2>&1
        _hrc=$?
        _poison="$($PY -c "
import sys
sys.path.insert(0, r'tools/run-agent')
from fairness import verifier_build_suspect
print(verifier_build_suspect(sys.argv[1]) or '')
" "$SUBSTRATE" 2>/dev/null)"
        if [ -n "$_poison" ]; then
          echo "ABORT: rebuild exited $_hrc and $SUBSTRATE is still not fit."
          echo "       $_poison"
          echo "       build log: $_hlog"
          exit 6
        fi
        echo "  OK    rebuilt; $SUBSTRATE is fit to drive again"
      fi
      if [ -n "$_poison" ]; then
        echo "ABORT: $SUBSTRATE is not fit to drive."
        echo "       $_poison"
        exit 6
      fi
      if tasklist 2>/dev/null | grep -qi "Aura.exe"; then
        echo "  CLOSING Aura desktop (envgate blocks arm-C while it runs; it will"
        echo "          not close it itself). Operator-sanctioned for this sweep."
        powershell -NoProfile -Command "Get-Process -Name 'Aura' -ErrorAction SilentlyContinue | Stop-Process -Force" >/dev/null 2>&1 || true
        sleep 3
      fi
      stamp="$(date -u +%Y%m%dT%H%M%SZ)"
      safe="$(printf '%s' "$lane-$(basename "$task")-$model" | tr '/:' '__')"
      log="$LOG_DIR/$safe-$stamp.log"
      echo "=== [$stamp] $lane :: $task :: $model  -> $log"
      {
        echo "=== cell start $stamp | $lane:$model | $task | ceiling=$CEILING ==="
        ./cb eval --model "$lane:$model" --task "$task" --ceiling "$CEILING"
        echo "exit=$? | cell end $(date -u +%Y%m%dT%H%M%SZ)"
      } > "$log" 2>&1
      ran=$((ran + 1))
      if is_harness_lock_abort "$log"; then
        echo "  RETRY: fairness-hide lock — a stale holder, per the brief's playbook."
        echo "         Failing CLOSED pre-spend (\$0, no verdict); re-running after hygiene."
        hygiene_gate "$safe-pre-retry" || exit 1
        reset_substrate
        rlog="$LOG_DIR/$safe-$stamp-retry.log"
        {
          echo "=== RETRY $(date -u +%Y%m%dT%H%M%SZ) | $lane:$model | $task ==="
          ./cb eval --model "$lane:$model" --task "$task" --ceiling "$CEILING"
          echo "exit=$? | retry end $(date -u +%Y%m%dT%H%M%SZ)"
        } > "$rlog" 2>&1
        cat "$rlog" >> "$log"
        if is_harness_lock_abort "$rlog"; then
          echo "  STILL LOCKED after retry — recorded as a harness abort, NOT a model verdict"
        fi
      fi
      # A contaminated cell must not bank. run.py's breach gate covers a hide
      # that fell; this covers what the transcript actually READ, which is the
      # only evidence for an index that served pre-hide bytes.
      _rd="$(ls -dt "$RUNS_ROOT/$lane"/*"-$(basename "$task")-$lane-$(printf '%s' "$model" | tr '/' '_')" 2>/dev/null | head -1)"
      if [ -n "$_rd" ]; then
        # Exit codes are the audit's own contract (leak_audit.py docstring):
        # 0 clean / 1 contaminated / 2 nothing to audit / 3 park exposed only.
        # Handled EXPLICITLY rather than with `|| true`, because that swallowed
        # the launcher's 103 along with them and turned the guard into a no-op
        # nobody could see. Anything outside the contract stops the sweep: an
        # anti-cheat detector that cannot run must not be mistaken for one that
        # ran and found nothing.
        $PY tools/run-agent/leak_audit.py "$_rd" --void
        _lrc=$?          # captured BEFORE anything else: inside `case` branches
                         # `$?` is the case statement's own status, not this one's.
        case "$_lrc" in
          0) ;;
          1) echo "  CONTAMINATED — cell VOIDED by leak_audit (answer-key material in tool results)" ;;
          2) echo "  leak_audit: no transcript to audit" ;;
          3) echo "  WARN leak_audit: park EXPOSED but not consumed — a defect, not a void" ;;
          *) echo "  ABORT: leak_audit could not RUN (exit $_lrc). Every later cell would" >&2
             echo "         bank unaudited, which is how six drives read the answer key" >&2
             echo "         without a single incident being filed." >&2
             exit 7 ;;
        esac
      fi

      # Between cells: the brief's mandatory `./cb down` (a previous lane's
      # editor holding a loaded map is the measured way into the hide lock), which
      # also hands the engine back so the next bring-up is not starved by a stale
      # stack (measured 5x verify slowdown — the machine-characterisation notes §3).
      hygiene_gate "$safe" || exit 1
      reset_substrate          # only valid once cb down has killed the editor
    done
  done
  echo "=== task complete: $task ==="
done
echo "=== sweep done: $total cells, $ran run, $skipped skipped ==="
