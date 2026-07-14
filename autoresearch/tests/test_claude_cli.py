import json
import os
import tempfile
import unittest

from util import FAKE_CLAUDE

from harness.claude_cli import ClaudeError, ClaudeResult, run_claude


class TestClaudeCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old = os.environ.get("PIPELINE_CLAUDE_BIN")
        os.environ["PIPELINE_CLAUDE_BIN"] = FAKE_CLAUDE

    def tearDown(self):
        if self._old is None:
            os.environ.pop("PIPELINE_CLAUDE_BIN", None)
        else:
            os.environ["PIPELINE_CLAUDE_BIN"] = self._old

    def test_json_mode(self):
        res = run_claude("You are playing a RECRUITER...\nsurvey_only: yes",
                         model="m", cwd=self.tmp, timeout_s=30)
        self.assertTrue(res.ok)
        self.assertTrue(res.session_id)
        self.assertGreater(res.cost_usd, 0)
        payload = res.json_payload()
        self.assertEqual(payload["action"], "accept")
        self.assertIn("ux", payload)

    def test_stream_mode_writes_transcript_and_parses_result(self):
        transcript = os.path.join(self.tmp, "t.jsonl")
        res = run_claude("Skill directory: /tmp/skill",
                         model="m", cwd=self.tmp, timeout_s=30,
                         transcript_path=transcript)
        self.assertTrue(res.ok)
        self.assertIn("search plan", res.text)
        with open(transcript) as f:
            events = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(events[-1]["type"], "result")

    def test_resume_flag_reaches_binary(self):
        os.environ["FAKE_INNER_NO_CSV"] = "1"
        self.addCleanup(os.environ.pop, "FAKE_INNER_NO_CSV", None)
        res = run_claude("anything", model="m", cwd=self.tmp, timeout_s=30,
                         resume="session-123")
        self.assertTrue(res.ok)
        self.assertEqual(res.session_id, "session-123")

    def test_json_payload_extraction(self):
        fenced = ClaudeResult('here:\n```json\n{"a": 1}\n```\ndone', None, 0, [], True)
        self.assertEqual(fenced.json_payload(), {"a": 1})
        bare = ClaudeResult('noise {"b": {"c": 2}} trailing', None, 0, [], True)
        self.assertEqual(bare.json_payload(), {"b": {"c": 2}})
        with self.assertRaises(ClaudeError):
            ClaudeResult("no json here", None, 0, [], True).json_payload()

    def test_is_error_result_is_not_ok(self):
        os.environ["FAKE_CLAUDE_ERROR"] = "credit balance too low"
        self.addCleanup(os.environ.pop, "FAKE_CLAUDE_ERROR", None)
        res = run_claude("anything", model="m", cwd=self.tmp, timeout_s=30)
        self.assertFalse(res.ok)
        self.assertIn("credit balance", res.error)

    def test_missing_binary_returns_error_result(self):
        os.environ["PIPELINE_CLAUDE_BIN"] = "/nonexistent/claude"
        res = run_claude("hi", model="m", cwd=self.tmp, timeout_s=5)
        self.assertFalse(res.ok)
        self.assertIn("failed to exec", res.error)

    def test_timeout_returns_error_result(self):
        slow = os.path.join(self.tmp, "slow.sh")
        with open(slow, "w") as f:
            f.write("#!/bin/sh\nsleep 5\n")
        os.chmod(slow, 0o755)
        os.environ["PIPELINE_CLAUDE_BIN"] = slow
        res = run_claude("hi", model="m", cwd=self.tmp, timeout_s=1)
        self.assertFalse(res.ok)
        self.assertIn("timed out", res.error)


if __name__ == "__main__":
    unittest.main()
