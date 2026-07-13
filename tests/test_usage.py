from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from skill2.usage import parse_claude_usage, parse_codex_usage, parse_usage

FIXTURES = Path(__file__).parent / "fixtures" / "usage"


class UsageTest(unittest.TestCase):
    def test_parses_real_codex_shapes_without_transcript_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = _make_skills(root / "skills")
            codex = root / "codex"
            _copy_fixture(
                "desktop-session.jsonl",
                codex / "sessions" / "2026" / "07" / "01",
                skills,
            )
            _copy_fixture("archived-worker.jsonl", codex / "archived_sessions", skills)

            result = parse_codex_usage(codex, skills)
            events = [event.to_dict() for event in result.events]

            self.assertEqual(
                events,
                [
                    _event(
                        "2026-07-01T00:00:01Z",
                        "desktop-1",
                        "alpha",
                        "activation",
                        "medium",
                        "function_call",
                    ),
                    _event(
                        "2026-07-01T00:00:03Z",
                        "desktop-1",
                        "beta",
                        "maintenance",
                        "medium",
                        "function_call",
                    ),
                    _event(
                        "2026-07-01T00:00:04Z",
                        "desktop-1",
                        "gamma",
                        "unknown",
                        "low",
                        "function_call",
                    ),
                    _event(
                        "2026-07-02T00:00:01Z",
                        "worker-1",
                        "delta",
                        "worker_read",
                        "low",
                        "command_execution",
                    ),
                ],
            )
            payload = result.to_dict()
            self.assertEqual(payload["schema_version"], "1")
            self.assertEqual(
                payload["summary"]["by_category"],
                {"activation": 1, "maintenance": 1, "unknown": 1, "worker_read": 1},
            )
            self.assertNotIn("confidential prompt", json.dumps(payload))
            self.assertEqual(
                set(events[0]),
                {"timestamp", "harness", "session", "skill", "source", "confidence", "category"},
            )

    def test_marks_four_distinct_skills_as_broad_scan_and_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = _make_skills(root / "skills")
            codex = root / "codex"
            _copy_fixture("broad-session.jsonl", codex / "sessions" / "2026" / "07" / "03", skills)

            first = parse_codex_usage(codex, skills).to_dict()
            second = parse_codex_usage(codex, skills).to_dict()

            self.assertEqual(first, second)
            self.assertEqual(first["summary"]["total_events"], 4)
            self.assertEqual({event["category"] for event in first["events"]}, {"broad_scan"})
            self.assertEqual({event["confidence"] for event in first["events"]}, {"low"})

    def test_excludes_cached_vendor_and_historical_skill_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = _make_skills(root / "skills")
            codex = root / "codex"
            _copy_fixture("ignored-paths.jsonl", codex / "sessions" / "2026" / "07" / "04", skills)

            result = parse_codex_usage(codex, skills)

            self.assertEqual(result.events, ())
            self.assertEqual(
                result.summary,
                {"total_events": 0, "by_category": {}, "by_skill": {}, "by_harness": {}},
            )

    def test_matches_installed_skill_alias_without_leaking_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = _make_skills(root / "skills")
            session = root / "codex" / "sessions" / "alias.jsonl"
            session.parent.mkdir(parents=True)
            alias = Path.home() / ".agents" / "skills" / "alpha" / "SKILL.md"
            records = [
                {
                    "timestamp": "2026-07-05T00:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "alias-session"},
                },
                {
                    "timestamp": "2026-07-05T00:00:01Z",
                    "item": {"type": "command_execution", "command": f"sed -n 1,80p {alias}"},
                },
            ]
            session.write_text(
                "\n".join(json.dumps(record) for record in records), encoding="utf-8"
            )

            payload = parse_codex_usage(root / "codex", skills).to_dict()

            self.assertEqual(payload["events"][0]["skill"], "alpha")
            self.assertNotIn(str(Path.home()), json.dumps(payload))

    def test_parses_portable_relative_skill_md_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = _make_skills(root / "skills")
            session = root / "codex" / "sessions" / "relative.jsonl"
            session.parent.mkdir(parents=True)
            records = [
                {
                    "timestamp": "2026-07-06T00:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "relative-1", "thread_source": "user"},
                },
                {
                    "timestamp": "2026-07-06T00:00:01Z",
                    "item": {
                        "type": "command_execution",
                        "command": "cat skills/alpha/SKILL.md",
                    },
                },
                {
                    "timestamp": "2026-07-06T00:00:02Z",
                    "item": {
                        "type": "command_execution",
                        "command": "sed -n '1,40p' skills/beta/SKILL.md",
                    },
                },
            ]
            session.write_text(
                "\n".join(json.dumps(record) for record in records), encoding="utf-8"
            )

            payload = parse_codex_usage(root / "codex", skills).to_dict()
            events = payload["events"]

            self.assertEqual(
                [(event["skill"], event["category"]) for event in events],
                [("alpha", "activation"), ("beta", "activation")],
            )
            dumped = json.dumps(payload)
            self.assertNotIn(str(skills.resolve()), dumped)
            self.assertNotIn(str(Path.home()), dumped)
            self.assertNotIn("confidential", dumped)

    def test_parses_claude_read_and_sidechain_as_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = _make_skills(root / "skills")
            session = (
                root
                / "claude"
                / "projects"
                / "-Users-demo"
                / "claude-session.jsonl"
            )
            session.parent.mkdir(parents=True)
            alpha = skills.resolve() / "alpha" / "SKILL.md"
            beta = skills.resolve() / "beta" / "SKILL.md"
            records = [
                {
                    "type": "assistant",
                    "timestamp": "2026-07-10T00:00:01Z",
                    "sessionId": "claude-1",
                    "isSidechain": False,
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": str(alpha)},
                            }
                        ]
                    },
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-07-10T00:00:02Z",
                    "sessionId": "claude-1",
                    "isSidechain": True,
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "input": {"command": f"cat {beta}"},
                            }
                        ]
                    },
                },
            ]
            session.write_text(
                "\n".join(json.dumps(record) for record in records), encoding="utf-8"
            )

            payload = parse_claude_usage(root / "claude", skills).to_dict()
            events = payload["events"]

            self.assertEqual(
                [(event["skill"], event["category"], event["harness"]) for event in events],
                [
                    ("alpha", "activation", "claude"),
                    ("beta", "worker_read", "claude"),
                ],
            )
            self.assertEqual(payload["summary"]["by_harness"], {"claude": 2})
            self.assertNotIn(str(Path.home()), json.dumps(payload))

    def test_merge_codex_and_claude_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = _make_skills(root / "skills")
            codex_session = root / "codex" / "sessions" / "c.jsonl"
            claude_session = (
                root / "claude" / "projects" / "p" / "c.jsonl"
            )
            codex_session.parent.mkdir(parents=True)
            claude_session.parent.mkdir(parents=True)
            alpha = skills.resolve() / "alpha" / "SKILL.md"
            codex_session.write_text(
                "\n".join(
                    json.dumps(record)
                    for record in (
                        {
                            "timestamp": "2026-07-11T00:00:00Z",
                            "type": "session_meta",
                            "payload": {"id": "codex-1"},
                        },
                        {
                            "timestamp": "2026-07-11T00:00:01Z",
                            "item": {
                                "type": "command_execution",
                                "command": f"cat {alpha}",
                            },
                        },
                    )
                ),
                encoding="utf-8",
            )
            claude_session.write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": "2026-07-11T00:00:02Z",
                        "sessionId": "claude-2",
                        "isSidechain": False,
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"file_path": str(alpha)},
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            payload = parse_usage(
                skills,
                codex_root=root / "codex",
                claude_root=root / "claude",
            ).to_dict()

            self.assertEqual(payload["summary"]["total_events"], 2)
            self.assertEqual(payload["summary"]["by_harness"], {"claude": 1, "codex": 1})
            self.assertEqual({event["skill"] for event in payload["events"]}, {"alpha"})


def _make_skills(root: Path) -> Path:
    names = (
        "alpha",
        "beta",
        "gamma",
        "delta",
        "plugins/cache/cached",
        "vendor_imports/vendor",
        "history/old",
    )
    for name in names:
        skill = root / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"---\nname: {name.split('/')[-1]}\n---\n", encoding="utf-8")
    return root


def _copy_fixture(name: str, directory: Path, skills: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    content = (FIXTURES / name).read_text(encoding="utf-8")
    resolved = content.replace("__SKILL_ROOT__", str(skills.resolve()))
    (directory / name).write_text(resolved, encoding="utf-8")


def _event(
    timestamp: str,
    session: str,
    skill: str,
    category: str,
    confidence: str,
    source: str,
) -> dict[str, str]:
    return {
        "timestamp": timestamp,
        "harness": "codex",
        "session": session,
        "skill": skill,
        "source": source,
        "confidence": confidence,
        "category": category,
    }


if __name__ == "__main__":
    unittest.main()
