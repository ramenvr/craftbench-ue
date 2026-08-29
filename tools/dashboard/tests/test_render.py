"""Unit tests for tools/dashboard/render.py.

Covers report-shape normalization (verify-single + legacy batch score-report), task spec
section extraction, submission rendering, verification layer rendering, and the
live ``--preview`` bundle's "Scene stills" section.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
# tools/dashboard/tests -> repo root, so the preview tests can build REAL
# LiveBundles with the shared describer instead of stubbing its contract.
_REPO_ROOT = _PARENT.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from render import (  # noqa: E402
    _colorize_log_line,
    _fmt_seconds,
    _outcome_class,
    _read_log_excerpt,
    find_task_spec,
    humanize_evidence_line,
    normalize_report,
    parse_task_spec_excerpts,
    render_html,
)


# Real verify-single report shape, captured from a live run on 2026-05-26.
_SINGLE_REPORT = {
    "task_id": "t0-sanity-log-on-beginplay",
    "overall": "pass",
    "submission_sha": "b62b7d05b2c394e6...",
    "ue_version": "5.7.4",
    "host": {"os": "darwin", "arch": "arm64"},
    "duration_seconds": 188.78,
    "sandbox_violations": 0,
    "layers": {
        "L1": {
            "status": "pass",
            "exit_code": 0,
            "duration_seconds": 156.31,
            "log": "/tmp/cb-verifier-run/workdir/out/l1_build.log",
            "notes": [
                "target CraftBenchTemplateEditor: exit 0 in 125.4s",
                "target CraftBenchTemplate: exit 0 in 31.0s",
            ],
            "warnings_in_agent_files": 0,
        },
        "L2": {
            "status": "pass",
            "exit_code": 0,
            "duration_seconds": 22.88,
            "log": "/tmp/cb-verifier-run/workdir/out/l2_pie.log",
            "notes": [
                "scaffold L_SanityTask: skipped",
                "result_source: json",
            ],
            "tests_passed": 1,
            "tests_run": 1,
        },
    },
}

# Batch shape: same task as a verdict in a list
_BATCH_REPORT = {
    "report_schema_version": "1.0",
    "run_id": "batch-test",
    "started_at": "2026-05-26T10:00:00Z",
    "finished_at": "2026-05-26T10:05:00Z",
    "k": 1,
    "pinning": {
        "engine_version": "5.7.4",
        "harness_id": "filesystem@1.0",
        "model_id": "anthropic/claude-sonnet-4-6",
        "substrate_revision": "abc123",
        "task_set_revision": "v1.0",
        "verifier_revision": "abc123",
    },
    "host_info": {"os": "Darwin", "cpu": "arm", "python_version": "3.13.9"},
    "verdicts": [
        {
            "task_id": "task-1",
            "outcome": "PASS",
            "attempt_index": 0,
            "wall_clock_seconds": 188.0,
            "seed": "seed-1",
            "layer_results": [
                {
                    "layer": "L1",
                    "outcome": "pass",
                    "duration_seconds": 150.0,
                    "log_excerpt": "Build successful\nexit 0",
                    "attribution": "",
                },
                {
                    "layer": "L2",
                    "outcome": "pass",
                    "duration_seconds": 38.0,
                    "log_excerpt": "Test Passed: SanityFunctionalTest\n1/1 tests passed",
                    "attribution": "",
                },
            ],
            "agent_metrics": {"tokens_in": 1500, "tokens_out": 300},
        }
    ],
    "rejections": [],
    "aggregate": {"mean": 1.0, "std": 0.0, "n": 1},
    "per_bucket": {}, "per_tier": {}, "per_concept": {}, "per_category": {},
    "task_set": {"task_count": 1, "by_tier": {}, "by_bucket": {}, "by_category": {}},
    "errors": [],
}

_TASK_SPEC_MD = """# t0-sanity-log-on-beginplay

Some intro paragraph.

## Task ID and metadata

- task_id: t0-sanity-log-on-beginplay
- tier: T0

## Primary concept

- `ps-actors` — Actors

`AActor` lifecycle is the load-bearing concept.

## Prompt given to the agent

> The project contains an actor placed in the level. When gameplay begins,
> this actor must emit the exact log line `CRAFTBENCH_SANITY_OK` to the
> standard engine log.

## Verifier layers used

- L1 (build) — UBT must produce a successful build for both Editor and Game targets
- L2 (PIE) — A functional test asserts the log line appeared

## Verifier specification

L2 fixture: ASanityFunctionalTest in Source/CraftBenchTests/.
Map: /Game/Maps/L_SanityTask
Asserts: GEngine->Log captured 'CRAFTBENCH_SANITY_OK' exactly once.

## Reference solution metadata

- author: maintainer
"""


class NormalizeReport(unittest.TestCase):
    def test_single_report_becomes_one_record(self) -> None:
        records = normalize_report(_SINGLE_REPORT)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["task_id"], "t0-sanity-log-on-beginplay")
        self.assertEqual(records[0]["outcome"], "pass")
        self.assertEqual(records[0]["ue_version"], "5.7.4")
        self.assertIn("L1", records[0]["layers"])
        self.assertIn("L2", records[0]["layers"])
        self.assertEqual(records[0]["source_shape"], "single")

    def test_batch_report_emits_one_record_per_verdict(self) -> None:
        records = normalize_report(_BATCH_REPORT)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["task_id"], "task-1")
        self.assertEqual(records[0]["source_shape"], "batch")
        self.assertEqual(records[0]["ue_version"], "5.7.4")
        # Batch shape converts layer_results list → {L1, L2} dict
        self.assertIn("L1", records[0]["layers"])
        self.assertIn("L2", records[0]["layers"])
        self.assertEqual(records[0]["layers"]["L1"]["status"], "pass")
        self.assertIn("Build successful", records[0]["layers"]["L1"]["log_excerpt"])

    def test_batch_with_no_verdicts_returns_empty(self) -> None:
        report = {"verdicts": []}
        self.assertEqual(normalize_report(report), [])


class TaskSpecParsing(unittest.TestCase):
    def test_parses_all_four_sections(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write(_TASK_SPEC_MD)
            path = Path(f.name)
        try:
            excerpts = parse_task_spec_excerpts(path)
            self.assertIn("CRAFTBENCH_SANITY_OK", excerpts["prompt"])
            self.assertIn("ps-actors", excerpts["primary_concept"])
            self.assertIn("L1 (build)", excerpts["verifier_layers"])
            self.assertIn("ASanityFunctionalTest", excerpts["verifier_spec"])
        finally:
            path.unlink()

    def test_missing_section_returns_empty_string(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write("# Just a title\n\nNo H2 sections.\n")
            path = Path(f.name)
        try:
            excerpts = parse_task_spec_excerpts(path)
            self.assertEqual(excerpts["prompt"], "")
            self.assertEqual(excerpts["primary_concept"], "")
        finally:
            path.unlink()


class FindTaskSpec(unittest.TestCase):
    def test_flat_spec_discovered_anywhere_under_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec = root / "tasks" / "concept-1" / "gp-x.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("# gp-x\n", encoding="utf-8")
            self.assertEqual(find_task_spec("gp-x", root), spec)

    def test_folder_form_spec_discovered(self) -> None:
        # Folder-per-task layout: tasks/<set>/<id>/task.md.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec = root / "tasks" / "concept-1" / "gp-x" / "task.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("# gp-x\n", encoding="utf-8")
            self.assertEqual(find_task_spec("gp-x", root), spec)

    def test_missing_spec_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tasks").mkdir()
            self.assertIsNone(find_task_spec("gp-x", root))


class LogExcerpt(unittest.TestCase):
    def test_tail_lines_returned(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".log", mode="w", delete=False) as f:
            for i in range(200):
                f.write(f"line-{i}\n")
            path = Path(f.name)
        try:
            out = _read_log_excerpt(path, layer_name="L1", tail_lines=10)
            lines = out.splitlines()
            self.assertEqual(len(lines), 10)
            self.assertEqual(lines[-1], "line-199")
        finally:
            path.unlink()

    def test_l2_keeps_test_verdict_lines_even_outside_tail(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".log", mode="w", delete=False) as f:
            f.write("Test Passed: MyEarlyTest\n")
            for i in range(100):
                f.write(f"noise-{i}\n")
            path = Path(f.name)
        try:
            out = _read_log_excerpt(path, layer_name="L2", tail_lines=10)
            self.assertIn("Test Passed: MyEarlyTest", out)
        finally:
            path.unlink()

    def test_missing_log_returns_empty(self) -> None:
        self.assertEqual(
            _read_log_excerpt(Path("/nonexistent"), layer_name="L1"), ""
        )


class Colorize(unittest.TestCase):
    def test_pass_marker_gets_pass_class(self) -> None:
        self.assertIn("pass-line", _colorize_log_line("Test Passed: foo"))

    def test_fail_marker_gets_fail_class(self) -> None:
        self.assertIn("fail-line", _colorize_log_line("Test Failed: foo"))

    def test_neutral_line_has_no_class(self) -> None:
        self.assertNotIn("pass-line", _colorize_log_line("compiling foo.cpp"))
        self.assertNotIn("fail-line", _colorize_log_line("compiling foo.cpp"))


class Helpers(unittest.TestCase):
    def test_fmt_seconds_ms(self) -> None:
        self.assertEqual(_fmt_seconds(0.123), "123 ms")

    def test_fmt_seconds_seconds(self) -> None:
        self.assertEqual(_fmt_seconds(12.7), "12.7 s")

    def test_fmt_seconds_minutes(self) -> None:
        self.assertEqual(_fmt_seconds(125.4), "2m 5s")

    def test_fmt_seconds_none(self) -> None:
        self.assertEqual(_fmt_seconds(None), "—")

    def test_outcome_class_pass(self) -> None:
        self.assertEqual(_outcome_class("pass"), "PASS")

    def test_outcome_class_unknown_becomes_error(self) -> None:
        self.assertEqual(_outcome_class("xyz"), "ERROR")


class RenderHtmlSingle(unittest.TestCase):
    def test_renders_pass_banner_with_task_id(self) -> None:
        html = render_html(report=_SINGLE_REPORT)
        self.assertIn("PASS", html)
        self.assertIn("t0-sanity-log-on-beginplay", html)
        # Green color hint somewhere in the banner area
        self.assertIn("green", html)
        # UE version is surfaced
        self.assertIn("5.7.4", html)

    def test_renders_l1_l2_layer_blocks(self) -> None:
        html = render_html(report=_SINGLE_REPORT)
        # Layer names appear
        self.assertIn(">L1<", html)
        self.assertIn(">L2<", html)
        # Per-target notes
        self.assertIn("CraftBenchTemplateEditor", html)
        # Test counts
        self.assertIn("tests 1/1 passed", html)

    def test_task_section_appears_when_spec_excerpts_provided(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write(_TASK_SPEC_MD)
            path = Path(f.name)
        try:
            excerpts = parse_task_spec_excerpts(path)
            html = render_html(report=_SINGLE_REPORT, task_spec_excerpts=excerpts)
            self.assertIn("Prompt given to the agent", html)
            self.assertIn("CRAFTBENCH_SANITY_OK", html)
            self.assertIn("Primary concept", html)
        finally:
            path.unlink()

    def test_submission_section_appears_when_dir_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "Source" / "CraftBenchTemplate"
            sub.mkdir(parents=True)
            (sub / "SanityActor.h").write_text("UCLASS()\nclass ASanityActor;", encoding="utf-8")
            (sub / "SanityActor.cpp").write_text(
                "void ASanityActor::BeginPlay() { UE_LOG(LogTemp, Log, TEXT(\"CRAFTBENCH_SANITY_OK\")); }",
                encoding="utf-8",
            )
            html = render_html(report=_SINGLE_REPORT, submission_dir=Path(tmp))
            self.assertIn("Agent submission", html)
            self.assertIn("SanityActor.h", html)
            self.assertIn("SanityActor.cpp", html)
            # File contents inlined
            self.assertIn("UCLASS", html)
            self.assertIn("CRAFTBENCH_SANITY_OK", html)


class ArtifactsSection(unittest.TestCase):
    """The Artifacts section: <img> tags when a run_id is available (the web
    report), a plain filename list without one (CLI render), nothing when the
    run has no artifacts."""

    def test_img_tags_with_run_id(self) -> None:
        html = render_html(
            report=_SINGLE_REPORT,
            artifacts=["shot-0001.png", "shot-0002.png"],
            run_id="20260603-000000-t0-claude-p-opus",
        )
        self.assertIn(">Artifacts<", html)
        self.assertIn(
            'src="/api/run/20260603-000000-t0-claude-p-opus/artifact/shot-0001.png"',
            html,
        )
        self.assertIn(
            'src="/api/run/20260603-000000-t0-claude-p-opus/artifact/shot-0002.png"',
            html,
        )
        # Filenames double as visible captions.
        self.assertIn("shot-0001.png", html)

    def test_plain_filename_list_without_run_id(self) -> None:
        html = render_html(report=_SINGLE_REPORT, artifacts=["shot-0001.png"])
        self.assertIn(">Artifacts<", html)
        self.assertIn("shot-0001.png", html)
        self.assertNotIn("<img", html)

    def test_no_section_when_no_artifacts(self) -> None:
        for artifacts in (None, []):
            html = render_html(report=_SINGLE_REPORT, artifacts=artifacts,
                               run_id="some-run")
            self.assertNotIn(">Artifacts<", html)
            self.assertNotIn("<img", html)

    def test_url_components_are_quoted(self) -> None:
        # A hostile-looking name/id must not break out of the URL or the HTML.
        html = render_html(
            report=_SINGLE_REPORT,
            artifacts=['a b"<.png'],
            run_id="run/../x",
        )
        self.assertNotIn('run/../x/artifact', html)   # separators percent-encoded
        self.assertIn("run%2F..%2Fx", html)
        self.assertNotIn('"<.png"', html)             # esc'd, not raw


class RenderHtmlBatch(unittest.TestCase):
    def test_renders_batch_verdict_as_section(self) -> None:
        html = render_html(report=_BATCH_REPORT)
        self.assertIn("task-1", html)
        self.assertIn("PASS", html)
        # Per-layer log excerpts surface in batch shape too
        self.assertIn("Build successful", html)
        self.assertIn("Test Passed: SanityFunctionalTest", html)


def _strip_generated(html_doc: str) -> str:
    """Drop the footer's wall-clock stamp so two renders are comparable."""
    return re.sub(r"Generated [^ ]+ ", "Generated <ts> ", html_doc)




class PageHeading(unittest.TestCase):
    """Owner ask 2026-08-06 #1: the page heading is the TASK NAME, derived
    from data; the words "task verification" are gone from the heading area."""

    def test_heading_is_the_task_id_and_jargon_heading_is_gone(self) -> None:
        html = render_html(report=_SINGLE_REPORT)
        self.assertIn(">t0-sanity-log-on-beginplay</h1>", html)
        self.assertNotIn("task verification", html)

    def test_explicit_heading_param_wins_over_the_bare_id(self) -> None:
        # report_bridge passes the envelope's (possibly set-qualified) id.
        html = render_html(report=_SINGLE_REPORT,
                           heading="cpp/t0-sanity-log-on-beginplay")
        self.assertIn(">cpp/t0-sanity-log-on-beginplay</h1>", html)

    def test_spec_human_title_wins_when_it_differs_from_the_id(self) -> None:
        excerpts = {"title": "Sanity: log a line on BeginPlay", "prompt": "",
                    "primary_concept": "", "verifier_layers": "",
                    "verifier_spec": ""}
        html = render_html(report=_SINGLE_REPORT, task_spec_excerpts=excerpts,
                           heading="cpp/t0-sanity-log-on-beginplay")
        self.assertIn(">Sanity: log a line on BeginPlay</h1>", html)

    def test_spec_title_equal_to_the_id_defers_to_the_heading_param(self) -> None:
        excerpts = {"title": "t0-sanity-log-on-beginplay", "prompt": "",
                    "primary_concept": "", "verifier_layers": "",
                    "verifier_spec": ""}
        html = render_html(report=_SINGLE_REPORT, task_spec_excerpts=excerpts,
                           heading="cpp/t0-sanity-log-on-beginplay")
        self.assertIn(">cpp/t0-sanity-log-on-beginplay</h1>", html)

    def test_spec_excerpts_carry_the_h1_title(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False,
                                         encoding="utf-8") as f:
            f.write(_TASK_SPEC_MD)
            path = Path(f.name)
        try:
            excerpts = parse_task_spec_excerpts(path)
            self.assertEqual(excerpts["title"], "t0-sanity-log-on-beginplay")
        finally:
            path.unlink()


# A real failing glide run's L2 evidence notes (captured 2026-08-05, trimmed).
_GLIDE_FAIL_REPORT = {
    "task_id": "gp-glide-stamina-bp",
    "overall": "fail",
    "duration_seconds": 300.0,
    "ue_version": "5.8",
    "host": {"os": "Windows", "arch": "AMD64"},
    "layers": {
        "L1": {
            "status": "pass",
            "exit_code": 0,
            "duration_seconds": 180.2,
            "notes": ["target CraftBenchTemplateEditor: exit 0 in 110.5s"],
        },
        "L2": {
            "status": "fail",
            "exit_code": 0,
            "duration_seconds": 26.7,
            "tests_run": 1,
            "tests_passed": 0,
            "notes": [
                "map L_GlideStamina: /Game/Maps/L_GlideStamina",
                "cmd: Q:\\UE_5.8\\Engine\\Binaries\\Win64\\UnrealEditor-Cmd.exe ...",
                "verdict-evidence: FinishTest TestResult=Failed. descent was "
                "not slowed by the glide: min glide |vZ|=1326 > 0.60 * "
                "free-fall(1209) = 725 "
                "[C:\\cb\\wd\\c169ab9e13\\GlideStaminaFunctionalTest.cpp(185)]",
                "verdict-evidence: Test Completed. Result={Fail} "
                "Name={GlideStaminaFunctionalTest}",
                "verdict-evidence: [GLIDE-FINAL] granted=1 activated=1 "
                "freefall=1208.7 minglide=1326.3 minpower=-2.0 drained=1 "
                "exhausted=1 lastspeed=1679.1",
                "verdict-evidence: [GLIDE-FINAL] granted=1 activated=1 "
                "freefall=1208.7 minglide=1326.3 minpower=-2.0 drained=1 "
                "exhausted=1 lastspeed=1679.1 [log]",
                "filter: Project.Functional Tests.Maps.L_GlideStamina...",
            ],
        },
    },
}


class EvidenceMapping(unittest.TestCase):
    """The evidence-line -> plain-language mapping table (owner ask #4)."""

    def test_finishtest_failed_keeps_the_message_drops_the_source_loc(self) -> None:
        items = humanize_evidence_line(
            "FinishTest TestResult=Failed. descent was not slowed by the "
            "glide: min glide |vZ|=1326 > 0.60 * free-fall(1209) = 725 "
            "[C:\\cb\\wd\\x\\GlideStaminaFunctionalTest.cpp(185)]")
        self.assertEqual(len(items), 1)
        mark, text = items[0]
        self.assertEqual(mark, "bad")
        self.assertIn("descent was not slowed by the glide", text)
        # inline parens survive; only the trailing [file(line)] is dropped.
        self.assertIn("free-fall(1209)", text)
        self.assertNotIn(".cpp(185)", text)

    def test_test_completed_success_maps_to_a_plain_sentence(self) -> None:
        items = humanize_evidence_line(
            "Test Completed. Result={Success} Name={PoisonStackFunctionalTest} "
            "Path={Project.Functional Tests...}")
        self.assertEqual(items, [
            ("ok", "the behavior test passed in the running game")])

    def test_glide_final_flags_and_measurements(self) -> None:
        items = humanize_evidence_line(
            "[GLIDE-FINAL] granted=1 activated=1 freefall=1208.7 "
            "minglide=1326.3 minpower=-2.0 drained=1 exhausted=1 "
            "lastspeed=1679.1")
        texts = {t for _m, t in items}
        marks = {t: m for m, t in items}
        self.assertEqual(
            marks["the ability is granted to the character"], "ok")
        self.assertEqual(
            marks["the ability activated when triggered"], "ok")
        self.assertEqual(
            marks["energy drained while the ability was active"], "ok")
        self.assertIn(
            "free-fall descent speed before the ability: 1208.7 cm/s", texts)
        self.assertIn("slowest descent while gliding: 1326.3 cm/s", texts)
        self.assertIn("the energy reserve ran out during the test", texts)

    def test_final_zero_flags_map_to_failures(self) -> None:
        items = humanize_evidence_line(
            "[GLIDE-FINAL] granted=0 activated=0 drained=0")
        marks = {t: m for m, t in items}
        self.assertEqual(
            marks["the ability was never granted to the character"], "bad")
        self.assertEqual(
            marks["the ability did not activate when triggered"], "bad")
        self.assertEqual(
            marks["energy did not drain while the ability was active"], "bad")

    def test_poison_final_ratio_and_leftover_values(self) -> None:
        items = humanize_evidence_line(
            "[POISON-FINAL] granted=1 activated=1 A1=95.0 AStop=75.0 "
            "ratio=3.00")
        texts = [t for _m, t in items]
        self.assertIn("the stacked effect drained 3x faster than a single "
                      "application", texts)
        # Unmapped fields survive as raw measured values, never dropped.
        leftover = [t for t in texts if t.startswith("other measured values")]
        self.assertEqual(len(leftover), 1)
        self.assertIn("A1=95.0", leftover[0])
        self.assertIn("AStop=75.0", leftover[0])

    def test_advisory_line_is_kept_as_plain_note(self) -> None:
        items = humanize_evidence_line(
            "[POISON-ADVISORY] 4-application / single-stack drain-rate ratio "
            "= 3.00x (gated to [2.0, 3.5])")
        self.assertEqual(items[0][0], "info")
        self.assertIn("drain-rate ratio", items[0][1])
        self.assertNotIn("[POISON-ADVISORY]", items[0][1])

    def test_unknown_evidence_falls_back_to_raw_text(self) -> None:
        raw = "SOMETHING nobody has ever mapped idx or otherwise"
        self.assertEqual(humanize_evidence_line(raw), [("info", raw)])


class PlainVerificationSection(unittest.TestCase):
    """The default Verification view is a plain checklist; the jargon moved
    into the collapsed "Verifier internals" fold (owner asks #4/#5)."""

    def test_pass_run_reads_as_a_checklist(self) -> None:
        html = render_html(report=_SINGLE_REPORT)
        self.assertIn(">Verification</h2>", html)
        self.assertIn("the code compiles", html)
        self.assertIn("the behavior test passed in the running game", html)

    def test_failing_gate_names_why_the_run_failed(self) -> None:
        html = render_html(report=_GLIDE_FAIL_REPORT)
        self.assertIn("the code compiles", html)
        self.assertIn("the ability is granted to the character", html)
        self.assertIn("the ability activated when triggered", html)
        self.assertIn("descent was not slowed by the glide", html)
        self.assertIn("this is why the run failed", html)
        # The annotation rides the failing evidence item, not a pass item.
        why = html.index("this is why the run failed")
        self.assertLess(html.index("descent was not slowed"), why)

    def test_duplicate_log_suffixed_evidence_renders_once(self) -> None:
        html = render_html(report=_GLIDE_FAIL_REPORT)
        self.assertEqual(
            html.count("the ability is granted to the character"), 1)

    def test_jargon_is_folded_into_verifier_internals(self) -> None:
        html = render_html(report=_GLIDE_FAIL_REPORT)
        self.assertIn("Verifier internals", html)
        internals_at = html.index("Verifier internals")
        # cmd lines / layer ids appear only inside the fold, after everything.
        self.assertGreater(html.index("UnrealEditor-Cmd.exe"), internals_at)
        self.assertGreater(html.index(">L1<"), internals_at)
        self.assertGreater(html.index(">L2<"), internals_at)
        # The fold is collapsed by default (no `open` attribute on it).
        fold = html[internals_at - 200:internals_at]
        self.assertNotIn("<details open", fold)

    def test_section_order_task_verification_then_rest(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False,
                                         encoding="utf-8") as f:
            f.write(_TASK_SPEC_MD)
            path = Path(f.name)
        try:
            excerpts = parse_task_spec_excerpts(path)
        finally:
            path.unlink()
        html = render_html(
            report=_SINGLE_REPORT,
            task_spec_excerpts=excerpts,
            run_id="run-1",
            run_summary={"verdict": "pass"},
        )
        i_task = html.index(">Task</h2>")
        i_verif = html.index(">Verification</h2>")
        i_summary = html.index(">Run summary</h2>")
        i_internals = html.index("Verifier internals")
        self.assertLess(i_task, i_verif)
        self.assertLess(i_verif, i_summary)
        self.assertLess(i_summary, i_internals)

    def test_old_reports_without_evidence_degrade_to_status_sentences(self) -> None:
        report = {
            "task_id": "old-task",
            "overall": "fail",
            "layers": {
                "L1": {"status": "fail", "exit_code": 1,
                       "notes": ["compilation error in SanityActor.cpp"]},
                "L2": {"status": "skipped",
                       "notes": ["short-circuited: L1 did not pass"]},
            },
        }
        html = render_html(report=report)
        self.assertIn("the code does not compile", html)
        self.assertIn("this is why the run failed", html)
        self.assertIn("the in-game behavior test was not run", html)



class FailingReport(unittest.TestCase):
    def test_l1_fail_renders_fail_styling(self) -> None:
        report = dict(_SINGLE_REPORT)
        report["overall"] = "fail"
        report["layers"] = {
            "L1": {
                "status": "fail",
                "exit_code": 1,
                "duration_seconds": 5.0,
                "log": "/nonexistent.log",
                "notes": ["compilation error in SanityActor.cpp"],
            },
            "L2": {
                "status": "skipped",
                "duration_seconds": 0.0,
                "notes": ["short-circuited: L1 did not pass"],
            },
        }
        html = render_html(report=report)
        self.assertIn("FAIL", html)
        # Red color tint somewhere (Tailwind)
        self.assertIn("red", html)
        self.assertIn("compilation error", html)
        self.assertIn("short-circuited", html)




if __name__ == "__main__":
    unittest.main()
