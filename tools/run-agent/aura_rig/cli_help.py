"""cli_help — the curated help + shell-completion surface behind ``cb``.

One registry (:data:`COMMANDS`) is the single source of truth for three
user-facing features:

  * the grouped command overview printed by bare ``cb`` / ``cb help`` /
    ``cb --help`` (:func:`render_overview`, wired as the parser epilog);
  * scoped per-command help — ``cb help <command>`` and ``cb <command>
    --help`` (:func:`render_command`; cb.main pre-scans argv because the
    flat parser would otherwise dump every command's flags);
  * tab completion — ``cb __complete <mode> [arg]`` emits candidates
    (:func:`complete`) and ``cb completions powershell|bash`` prints the
    shell registration snippet (:data:`POWERSHELL_COMPLETER` /
    :data:`BASH_COMPLETER`).

Drift is guarded by tests/test_cli_help.py: every dispatch command must have
a registry entry, and every flag named here must exist on the real parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# The registry.                                                                #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Cmd:
    name: str
    group: str
    synopsis: str                                  # one line for the overview
    flags: Tuple[Tuple[str, str], ...] = ()        # (flag, one-liner) — KEY flags only
    example: Optional[str] = None
    notes: Tuple[str, ...] = ()                    # extra lines for `cb help <cmd>`
    # Trailing positionals this command CONSUMES, in order (metavars). The
    # parser is flat — it offers two shared optional positionals to every
    # command — so this is the ONLY statement of which commands actually read
    # them, and cb.main hard-fails a stray word on the rest (a bare task id
    # after `cb eval` used to parse into `outputs` and grade --task's DEFAULT).
    positional: Tuple[str, ...] = ()


GROUPS = (
    "RUN AN EVAL (spends tokens)",
    "VERIFY (token-free, deterministic)",
    "STACK & INSPECT",
    "SETUP & MAINTENANCE",
)

_RUN, _VERIFY, _STACK, _SETUP = GROUPS

COMMANDS: Dict[str, Cmd] = {c.name: c for c in (
    # ------------------------------- RUN -------------------------------- #
    Cmd("smoke", _RUN,
        "prove the golden path: preflight -> verifier unit tests -> a real t0 reference grade (exit 0 = this machine benches)",
        flags=(("--agent", "append ONE live graded eval (bare = claude-p; any model slug; SPENDS tokens)"),
               ("--no-preflight", "skip the ~2s environment gate")),
        example="cb smoke",
        notes=("Run it after clone (setup suggests it) and after harness changes.",)),
    Cmd("eval", _RUN,
        "graded eval of ONE task: agent drive -> L1 build -> L2 PIE -> VERDICT (backend chosen by the --model slug)",
        flags=(("--task", "task id (bare or <set>/<id>; default t0-sanity-log-on-beginplay)"),
               ("--model", "claude-p[:<m>] / openrouter:<p/m> / bare:<p/m> = baseline; unreal-mcp[:<m>]; aura-mcp[:<m>] (see the aura-mcp note below)"),
               ("--ceiling", "agent time ceiling in seconds (default 1200)"),
               ("--visible", "windowed live editor + real-RHI verifier legs"),
               ("--capture", "assert-free per-checkpoint screenshots into the run dir"),
               ("--keep", "persist a lean project snapshot with the run"),
               ("--keep-workdir", "keep the FULL built verifier workdir (~5.9 GB) instead of the slim default (CB_WORKDIR_RETENTION=full); NOT --keep, whose lean copy cannot be rebuilt"),
               ("--reuse-editor", "skip the per-drive fresh-editor restart (faster repeat/debug)"),
               ("--no-preflight", "skip the ~2s environment gate")),
        example="cb eval --task t1-movement-component-drives-actor --model claude-p:sonnet",
        notes=("On the unreal-mcp lane the editor stack auto-brings-up and stays warm "
               "between runs; only `cb down` stops it. The baseline lanes (claude-p / "
               "openrouter / bare) get file tools and a workspace copy of the substrate, "
               "and never start an editor at all.",
               "aura-mcp is DISCLOSED BUT NOT REPRODUCIBLE from this repository. The arm "
               "is dispatchable and its config + verifier are published so its results can "
               "be read and audited, but running it needs a private UE plugin, two private "
               "local servers and an entitled account, and the login machinery was removed "
               "before release. `cb eval --model aura-mcp[:<m>]` therefore fails fast with "
               "that message instead of half-starting a stack it cannot log into.")),
    Cmd("matrix", _RUN,
        "{model} x {task} cross product (baseline backends only) -> runs/matrix-<ts>/leaderboard.{html,md,json}",
        flags=(("--model", "comma list, e.g. claude-p:sonnet,openrouter:openai/gpt-5"),
               ("--task", "task id, set, or <set>/<id>")),
        example="cb matrix --model claude-p:sonnet,openrouter:openai/gpt-5 --task cpp"),
    Cmd("bench", _RUN,
        "N SEQUENTIAL repetitions per {model} x {task} -> cost/time SPREAD + model-comparison leaderboard in runs/bench-<ts>/bench.{json,md} + leaderboard.html",
        flags=(("--task", "COMMA LIST of task ids = a multi-task matrix (set-qualified preferred; per-task ':N' repeat override)"),
               ("--repeat", "repetitions per pair (default 3; --repeat 1 = pure model comparison; per-task override --task <id>:N)"),
               ("--refgates", "OPT IN to the per-task reference gates: token-free reference grade of every distinct task BEFORE any spend (FAIL aborts with exit 9; certified tasks self-skip). Default OFF since 2026-08-06 — gate at authoring time with `cb refgate`"),
               ("--run-mismatched-cells", "run baseline-x-asset-task cells the parse-time check refuses (guaranteed harness-reason FAILs)"),
               ("--prune-workdirs", "delete each rep's workdir right after its grade — only the ~42 MB slim remnant unless the rep also used --keep-workdir"),
               ("--resume", "rejoin an interrupted bench (bare = newest runs/bench-* DIR with a readable bench.json)"),
               ("--no-teardown", "leave the editor stack up afterwards; default STOPS it, since a stale stack costs the next run ~5x verify"),
               ("--wizard", "force the interactive wizard (bare `cb bench` in a terminal opens it automatically)"),
               ("--no-preflight", "skip the ~2s environment gate")),
        # Every slug here must be a ROUTABLE arm: the old example listed bare
        # Aura account keys (opus-4.8, grok-4, ...), which the colon-free
        # namespace no longer accepts — `cb bench` refuses them at minute 0.
        example="cb bench --model claude-p:sonnet,claude-p:opus,openrouter:openai/gpt-5,bare:openai/gpt-5-mini --task bp/gp-glide-stamina-bp,cpp/gp-glide-stamina-cpp,bp/gp-poison-dot-stack-bp,cpp/gp-poison-dot-stack-cpp --repeat 2 --ceiling 1200 --keep",
        notes=("THE multi-model comparison surface: every BASELINE arm (claude-p / "
               "openrouter / bare) in ONE invocation; leaderboard cells link each rep to its "
               "run's report.html and flag models_used mismatches (trust the envelope "
               "attribution, never the slug). unreal-mcp brings its own editor up per run "
               "and is reported unsupported here — drive it one run at a time with "
               "`cb eval`; aura-mcp is refused before the first rep.",
               "MULTI-TASK certified matrix (the release check): every task id resolves and every "
               "(model, task) cell is sanity-checked at parse time; a cost preview (cells x anchors "
               "+ ceiling) prints before launch. Reference gates NO LONGER run by default "
               "(2026-08-06): certify tasks at authoring time with `cb refgate <task>` (or "
               "`cb refgate --all` on a fresh machine), or pass --refgates to gate inline — a "
               "gate FAIL prints the task + verdict-evidence and aborts with exit 9, before any "
               "spend (--skip-refgates is a deprecated no-op). Execution order: baselines first "
               "(they need no editor stack), then per-task blocks with models within (a task "
               "switch invalidates the composed scratch's incremental build).",
               "Bare `cb bench` in an interactive terminal opens the wizard (tasks -> models -> "
               "reps -> confirm) instead of silently running the default model x t0 x 3 reps; "
               "non-TTY / explicit --model/--task keep the classic behavior.")),

    # ------------------------------ VERIFY ------------------------------ #
    Cmd("lint", _VERIFY,
        "static spec lint (front matter, fixtures, map binaries, prompt hygiene) - instant, no UE",
        flags=(("--task", "narrow to one id/set (default: all specs)"),),
        example="cb lint"),
    Cmd("discriminate", _VERIFY,
        "FR-017 matrix per task: reference -> PASS, empty + each discrimination/ variant -> FAIL via its named substring",
        flags=(("--task", "task id, set, or <set>/<id>"),
               ("--warm-cache", "build matrix legs from the warm pool (~6x L1)"),
               ("--wip", "force --substrate-from-live (maintainer mid-edit)"),
               ("--keep", "keep the per-leg run dirs")),
        example="cb discriminate --task cpp/t2-homing-projectile"),
    Cmd("wip", _VERIFY,
        "alias of discriminate (pair with --wip to grade the live working tree)",
        flags=(("--task", "task id, set, or <set>/<id>"),
               ("--wip", "force --substrate-from-live (maintainer mid-edit)")),
        example="cb wip --task <id> --wip"),
    Cmd("batch-eval", _VERIFY,
        "PARALLEL deterministic grade of a folder of submission dirs; --references sweeps every committed reference solution",
        flags=(("--references", "[all|<set>] grade the tasks' OWN references (the all-references regression gate)"),
               ("--verify-concurrency", "parallel width (default 1; raise only on >32 GB)"),
               ("--warm-cache", "use the warm L1 pool"),
               ("--wip", "force from-live for every task"),
               # Exit codes (2026-07-25): 0 = every graded submission PASSed,
               # 1 = a graded FAIL or NOTHING graded, 2 = usage/envgate.
               ("--no-gate", "exit 0 despite graded FAILs (measurement, not a gate)"),
               ("--no-preflight", "skip the ~2s environment gate")),
        example="cb batch-eval --references all",
        positional=("[submissions-dir]",)),
    Cmd("refgate", _VERIFY,
        "certify tasks' committed references token-free (THE authoring-time gate; exit 9 on a FAIL; PASSes cache a per-machine cert so repeats self-skip)",
        flags=(("--all", "sweep EVERY task with a committed reference (fresh-machine / post-pull certification; certified tasks self-skip)"),
               ("--force", "regrade even where a valid gate certificate would self-skip"),
               ("--no-preflight", "skip the ~2s environment gate")),
        example="cb refgate cpp/t2-homing-projectile",
        notes=("Run it whenever you author or change a task, its fixture, or the substrate — "
               "and `cb refgate --all` on a fresh machine or after a pull. A PASS writes a "
               "gate certificate (gitignored runs/.refgate-certs.json, keyed on the task + "
               "substrate git trees, UE root and hostname), so an unchanged task skips in "
               "seconds; a dirty working tree still grades but is never certified.",
               "`cb bench` no longer runs these gates automatically (2026-08-06); "
               "`cb bench --refgates` opts back in and honors the same certificates.",),
        positional=("<task>[,<task>...]",)),
    Cmd("warm-prime", _VERIFY,
        "build the L1 warm-cache pool so verifies build incrementally (~6x faster L1)",
        flags=(("--warm-slots", "pool slots (default 2; match --verify-concurrency)"),
               ("--force", "rebuild slots even if current")),
        example="cb warm-prime --warm-slots 2"),

    # ------------------------------ STACK ------------------------------- #
    Cmd("up", _STACK,
        "bring up the headless editor + Epic MCP server and gate on a real initialize, no run (`cb eval --model unreal-mcp` does this for itself)"),
    Cmd("status", _STACK,
        "one-shot READ-ONLY overview: editor-stack readiness (a real MCP initialize, never a port probe), stack owner, LiveCoding count, scratch, last run + verdict",
        example="cb status",
        notes=("Starts nothing and stops nothing; exit 0 whatever it finds — DOWN is an "
               "answer, not an error. `cb doctor` is the other read-only command: it asks "
               "whether this machine COULD run, this one asks what it is doing now.",
               "It reports the ONE component this release brings up (the headless editor "
               "+ Epic's in-engine MCP server). The multi-component frame it used to print "
               "— a vercel dev server, a CDP dev browser, the private client — went with "
               "the aura-product lane; there is nothing left here to be down.")),
    Cmd("where", _STACK,
        "print every resolved machine dir (repo, substrate, CB_ROOT, wd root, scratches, runs/) + existence",
        flags=(("--link", "drop gitignored <repo>/.cb/{wd,scratch} links to the real dirs"),)),
    Cmd("tasks", _STACK, "interactive browser: sets -> tasks -> detail; confirming runs `cb eval --task <id>`"),
    Cmd("view", _STACK,
        "open a WINDOWED editor to see/PIE a change (default: the playground scratch, else the graded scratch)",
        flags=(("--graded", "open the graded-eval scratch AT THE COMPOSED TASK'S MAP (the project `cb eval` leaves dirty)"),
               ("--map", "open a specific map (bare L_* name or full /Game/... path; bare names resolve through per-task folders)"),
               ("--run", "overlay a graded run's deliverable onto the template"),
               ("--project", "target your own project dir")),
        example="cb view --graded"),
    Cmd("review", _STACK,
        "overlay a run dir's deliverable/ onto the SCRATCH, list artifacts, open a windowed editor",
        example="cb review runs/claude-p/<run-dir>",
        positional=("<run-dir>",)),
    Cmd("reliability", _VERIFY,
        "adjudicate a repeated bench: is the set POOLABLE, harness-clean and unanimous? "
        "(a pass rate alone cannot say)",
        example="cb reliability runs/bench-20260809-014634",
        positional=("<bench-dir>",)),
    Cmd("down", _STACK, "stop the whole stack (supervisor + editor + LiveCodingConsole) and free the engine build lock"),

    # ------------------------------ SETUP ------------------------------- #
    Cmd("doctor", _SETUP,
        "READ-ONLY per-tier readiness diagnostic (grade-only / baseline) + a fix hint per blocker"),
    Cmd("clean", _SETUP,
        "reset the playground scratch to pristine; flags prune workdirs / runs / crash-debris presnaps instead",
        flags=(("--workdirs", "prune verifier workdirs unreferenced by any runs/**/summary.json"),
               ("--slim", "slim EVERY workdir in place (~5.5 GB each) — keeps the dir, its out/ reports and its launchable Binaries; implies --workdirs"),
               ("--runs", "prune run dirs (ledger-first; --keep-last K)"),
               ("--presnaps", "sweep orphaned crash-debris pre-run snapshots"),
               ("--older-than", "only prune items older than N days"),
               ("--check", "dry-run")),
        example="cb clean --workdirs --runs --check"),
    Cmd("completions", _SETUP,
        "print the tab-completion registration for your shell (commands, flags, task ids, model slugs)",
        example="cb completions powershell   # then: add the printed line to $PROFILE",
        notes=("PowerShell: cb completions powershell | Out-String | Invoke-Expression   (session)",
               "bash:       eval \"$(cb completions bash)\"                              (session)",
               "Persist by adding that same line to $PROFILE / ~/.bashrc."),
        positional=("<powershell|bash>",)),
)}


# --------------------------------------------------------------------------- #
# Rendering.                                                                   #
# --------------------------------------------------------------------------- #

def render_overview() -> str:
    """The grouped command overview (parser epilog / bare ``cb``)."""
    lines: List[str] = []
    for group in GROUPS:
        lines.append(group + ":")
        for c in COMMANDS.values():
            if c.group == group:
                lines.append(f"  {c.name:<12} {c.synopsis}")
        lines.append("")
    lines += [
        "cb help <command>          scoped help: the flags that matter + an example",
        "cb <command> --help        same thing",
        "cb completions powershell|bash   enable tab-completion",
    ]
    return "\n".join(lines)


def render_command(name: str) -> str:
    """Scoped help for one command (``cb help <name>`` / ``cb <name> --help``)."""
    if name in ("help",):
        return ("cb help [<command>]\n\n  Bare: the grouped overview. With a "
                "command: that command's flags + example.")
    c = COMMANDS.get(name)
    if c is None:
        known = ", ".join(sorted(COMMANDS))
        return f"cb: no help for {name!r}. Commands: {known}"
    lines = [f"cb {c.name} — {c.synopsis}", ""]
    if c.flags:
        lines.append("key flags:")
        width = max(len(f) for f, _ in c.flags)
        for f, desc in c.flags:
            lines.append(f"  {f:<{width}}  {desc}")
        lines.append("")
    if c.example:
        lines += ["example:", f"  {c.example}", ""]
    for n in c.notes:
        lines.append(f"note: {n}")
    lines.append("")
    lines.append("full flag reference: docs/CHEATSHEET.md; run-book: EVALS.md")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Completion candidates (`cb __complete <mode> [arg]`).                        #
# --------------------------------------------------------------------------- #

def _task_id_candidates(repo: Path) -> List[str]:
    """Bare + set-qualified ids from the folder-per-task layout (no parsing —
    completion must stay fast and never fail)."""
    out = set()
    try:
        for spec in (repo / "tasks").glob("*/*/task.md"):
            out.add(spec.parent.name)
            out.add(f"{spec.parent.parent.name}/{spec.parent.name}")
    except OSError:
        pass
    return sorted(out)


def _model_candidates() -> List[str]:
    """The published arms, as <backend>[:<model>] slugs.

    There is no bare-key namespace any more: the colon-free slugs used to be
    Aura account keys that routed to the product backend, which this release
    does not ship. Offering them back would only complete a slug the dispatch
    now refuses, so the list is the backends themselves — a completer that
    suggests something unrunnable is worse than a short list."""
    return ["claude-p", "claude-p:", "openrouter:", "bare:",
            "unreal-mcp", "unreal-mcp:", "aura-mcp", "aura-mcp:"]


def complete(mode: str, arg: str, repo: Path) -> List[str]:
    """Candidates for the shell completers. Unknown mode -> [] (never error:
    a completer that throws breaks the user's TAB key)."""
    if mode == "commands":
        return sorted(COMMANDS) + ["help"]
    if mode == "flags":
        c = COMMANDS.get(arg or "")
        flags = [f for f, _ in c.flags] if c else []
        return sorted(set(flags) | {"--help"})
    if mode == "task-ids":
        return _task_id_candidates(repo)
    if mode == "models":
        return _model_candidates()
    if mode == "shells":
        return ["powershell", "bash"]
    return []


# --------------------------------------------------------------------------- #
# Shell registration snippets (`cb completions <shell>`).                      #
# --------------------------------------------------------------------------- #

POWERSHELL_COMPLETER = r"""
# cb tab-completion (PowerShell 5.1+). Session:  cb completions powershell | Out-String | Invoke-Expression
# Persist: add that same line to your $PROFILE.
Register-ArgumentCompleter -Native -CommandName cb -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $tokens = @($commandAst.CommandElements | ForEach-Object { $_.ToString() })
    $prev = ''
    if ($wordToComplete -and $tokens.Count -ge 3) { $prev = $tokens[$tokens.Count - 2] }
    elseif (-not $wordToComplete -and $tokens.Count -ge 2) { $prev = $tokens[$tokens.Count - 1] }
    $cmd = ''
    foreach ($t in ($tokens | Select-Object -Skip 1)) { if ($t -notmatch '^-') { $cmd = $t; break } }
    if ($prev -eq '--task') { $cands = cb __complete task-ids }
    elseif ($prev -in @('--model', '--agent')) { $cands = cb __complete models }
    elseif ($prev -eq 'completions' -or $cmd -eq 'completions') { $cands = cb __complete shells }
    elseif ($wordToComplete -like '-*') { $cands = cb __complete flags $cmd }
    elseif ($cmd -eq '' -or $cmd -eq $wordToComplete) { $cands = cb __complete commands }
    else { $cands = @() }
    $cands | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}
""".strip()

BASH_COMPLETER = r"""
# cb tab-completion (bash / git-bash). Session:  eval "$(cb completions bash)"
# Persist: add that same line to ~/.bashrc.
_cb_complete() {
    local cur prev cmd mode
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    cmd=""
    for w in "${COMP_WORDS[@]:1}"; do case "$w" in -*) ;; *) cmd="$w"; break;; esac; done
    if [ "$prev" = "--task" ]; then mode="task-ids"
    elif [ "$prev" = "--model" ] || [ "$prev" = "--agent" ]; then mode="models"
    elif [ "$cmd" = "completions" ]; then mode="shells"
    elif [[ "$cur" == -* ]]; then mode="flags $cmd"
    elif [ -z "$cmd" ] || [ "$cmd" = "$cur" ]; then mode="commands"
    else COMPREPLY=(); return; fi
    COMPREPLY=($(compgen -W "$(cb __complete $mode 2>/dev/null)" -- "$cur"))
}
complete -F _cb_complete cb ./cb cb.cmd
""".strip()
