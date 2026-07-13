from __future__ import annotations

import unittest

from skill2.models import ScanResult, SkillRecord, SkillSource
from skill2.report import build_report, render_terminal
from skill2.usage import UsageEvent, UsageResult


class ReportTest(unittest.TestCase):
    def test_builds_terminal_report_with_usage_and_tests(self) -> None:
        scan = _scan("demo")
        usage = UsageResult(
            events=(
                UsageEvent(
                    timestamp="2026-07-01T00:00:00Z",
                    harness="codex",
                    session="session-1",
                    skill="demo",
                    source="command_execution",
                    confidence="medium",
                    category="activation",
                ),
                UsageEvent(
                    timestamp="2026-07-01T00:00:01Z",
                    harness="claude",
                    session="session-2",
                    skill="demo",
                    source="tool_use",
                    confidence="low",
                    category="broad_scan",
                ),
                UsageEvent(
                    timestamp="2026-07-01T00:00:02Z",
                    harness="claude",
                    session="session-3",
                    skill="demo",
                    source="tool_use",
                    confidence="low",
                    category="worker_read",
                ),
            ),
            summary={"by_harness": {"codex": 1, "claude": 2}},
        )
        report = build_report(
            scan,
            usage,
            ({"skill": "demo", "trials": [{"status": "pass"}]},),
        )
        text = render_terminal(report)

        self.assertEqual(report["summary"]["direct_calls"], 1)
        self.assertEqual(report["summary"]["indirect_calls"], 2)
        self.assertEqual(report["skills"][0]["tests"], {"total": 1, "passed": 1})
        self.assertIn("Skill Library", text)
        self.assertIn("demo", text)
        self.assertIn("Legend", text)
        self.assertIn("█", text)
        self.assertIn("░", text)
        self.assertIn("direct", text)
        self.assertIn("indirect", text)

        text_with_suggestions = render_terminal(
            report,
            (
                {
                    "action": "delete_candidate",
                    "target": "gone",
                    "reason": "No usage signal, test evidence, or ownership evidence was found.",
                },
                {
                    "action": "downgrade",
                    "target": "demo",
                    "reason": "Observed use is low-confidence broad or worker reading.",
                },
            ),
        )
        self.assertIn("Delete candidates", text_with_suggestions)
        self.assertIn("Downgrade candidates", text_with_suggestions)
        self.assertIn("gone", text_with_suggestions)
        self.assertNotIn("lifecycle", text_with_suggestions.lower())

    def test_renders_empty_inputs(self) -> None:
        report = build_report(
            ScanResult(root="/empty", skills=()),
            UsageResult(events=(), summary={}),
            (),
        )
        text = render_terminal(report)

        self.assertIn("No scanned skills.", text)
        self.assertIn("Limits", text)


def _scan(name: str) -> ScanResult:
    source = SkillSource(text="", body="", frontmatter={}, frontmatter_error=None)
    return ScanResult(
        root="/library",
        skills=(
            SkillRecord(
                name=name,
                path="/library/skill/SKILL.md",
                description="Test report",
                body_tokens=42,
                references=(),
                scripts=(),
                assets=(),
                scope="global",
                hash="a" * 64,
                _source=source,
            ),
        ),
    )
