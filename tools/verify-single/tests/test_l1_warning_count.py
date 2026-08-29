"""Unit tests for L1's compiler-warning counter.

WHY THIS FILE EXISTS. There were NO tests for warning counting, and that is
exactly how it stayed a DEAD GATE: UE 5.8's MSVC emits `file(line,col):` and
_WARNING_RE only accepted `file(line):`, so every MSVC warning went uncounted and
`--strict-warnings` could not fire. Found 2026-08-15 from evidence, not by
reading: all 63 reports of that day's reference sweep carry
`warnings_in_agent_files: 0`, while a retained build log of one of them holds a
`warning C4996` in an agent-writable file.

The MSVC-with-column line below is COPIED FROM A REAL LOG rather than
constructed, because the constructed one (no column) is precisely what passed
while the real one failed.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from layers.l1_build import _WARNING_RE, _count_warnings  # noqa: E402

# Verbatim from C:/cb/wd/poison2/out/l1_build.log, gp-poison-dot-stack-cpp.
_REAL_MSVC = (r"C:\cb\wd\poison2\ThirdPerson\Source\ThirdPerson\PoisonEffect"
              r".cpp(34,2): warning C4996: 'UGameplayEffect::StackingType': "
              r"Stacking Type is deprecated")
_MSVC_NO_COL = (r"C:\p\ThirdPerson\Source\ThirdPerson\Foo.cpp(12): "
                r"warning C4244: conversion")
_CLANG = "/p/ThirdPerson/Source/ThirdPerson/Foo.cpp:12:3: warning: unused"


class WarningRegexTest(unittest.TestCase):
    def test_msvc_with_column_matches(self):
        """The form UE 5.8 actually emits. This is the regression."""
        m = _WARNING_RE.search(_REAL_MSVC)
        self.assertIsNotNone(m)
        self.assertEqual("34", m.group("msvc_line"))
        self.assertTrue(m.group("path").endswith("PoisonEffect.cpp"))

    def test_msvc_without_column_still_matches(self):
        m = _WARNING_RE.search(_MSVC_NO_COL)
        self.assertIsNotNone(m)
        self.assertEqual("12", m.group("msvc_line"))

    def test_clang_still_matches(self):
        m = _WARNING_RE.search(_CLANG)
        self.assertIsNotNone(m)
        self.assertEqual("12", m.group("clang_line"))

    def test_an_error_line_is_not_counted_as_a_warning(self):
        self.assertIsNone(_WARNING_RE.search(
            r"C:\p\Foo.cpp(19,1): error C2059: syntax error"))


class CountWarningsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log = Path(self._tmp.name) / "l1_build.log"

    def tearDown(self):
        self._tmp.cleanup()

    def _count(self, lines, prefixes=("Source/ThirdPerson/",)):
        self.log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return _count_warnings(self.log, prefixes)

    def test_agent_file_warning_is_attributed(self):
        total, agent = self._count([_REAL_MSVC])
        self.assertEqual((1, 1), (total, agent))

    def test_non_agent_file_warning_counts_to_total_only(self):
        engine = (r"Q:\UE_5.8\Engine\Source\Runtime\Core\Public\Foo.h(9,4): "
                  r"warning C4996: engine-side")
        total, agent = self._count([engine])
        self.assertEqual((1, 0), (total, agent))

    def test_mixed_log_splits_correctly(self):
        engine = r"Q:\UE_5.8\Engine\Source\Runtime\Foo.h(9,4): warning C4996: e"
        total, agent = self._count(
            [_REAL_MSVC, engine, _MSVC_NO_COL, _CLANG,
             "Building ThirdPerson...", r"C:\p\Foo.cpp(1,1): error C2059: x"])
        self.assertEqual(4, total)
        self.assertEqual(3, agent)   # the three under Source/ThirdPerson/

    def test_no_prefixes_means_no_agent_attribution(self):
        total, agent = self._count([_REAL_MSVC], prefixes=())
        self.assertEqual((1, 0), (total, agent))

    def test_unreadable_log_is_zero_not_an_exception(self):
        self.assertEqual((0, 0), _count_warnings(
            self.log.parent / "absent.log", ("Source/ThirdPerson/",)))


if __name__ == "__main__":
    unittest.main()
