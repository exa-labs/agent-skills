"""The curl PATH shim and sitecustomize interception, exercised as real
subprocesses — the same way an Inner session hits them. Offline: record-mode
passthrough is tested against a scripted stand-in for the real curl."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from util import PIPELINE_DIR

SHIMS = os.path.join(PIPELINE_DIR, "shims")
CURL_SHIM = os.path.join(SHIMS, "curl")


class TestCurlShim(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, "exa_http.jsonl")
        os.chmod(CURL_SHIM, 0o755)
        self.fake_real = os.path.join(self.tmp, "real-curl")
        with open(self.fake_real, "w") as f:
            f.write('#!/bin/sh\necho \'{"id":"run-1","status":"completed"}\'\n')
        os.chmod(self.fake_real, 0o755)

    def _run(self, mode, *args):
        env = dict(os.environ, EXA_HTTP_MODE=mode, EXA_HTTP_LOG=self.log,
                   REAL_CURL=self.fake_real)
        return subprocess.run([CURL_SHIM] + list(args), env=env,
                              capture_output=True, text=True)

    def _log_lines(self):
        if not os.path.isfile(self.log):
            return []
        with open(self.log) as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_replay_blocks_exa_and_logs(self):
        proc = self._run("replay", "-s", "-X", "POST", "https://api.exa.ai/agent/runs")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("LIVE_EXA_DISABLED", proc.stdout)
        lines = self._log_lines()
        self.assertEqual(lines[0]["kind"], "blocked")

    def test_record_passes_through_and_captures_body(self):
        proc = self._run("record", "-s", "https://api.exa.ai/agent/runs/run-1")
        self.assertIn('"completed"', proc.stdout)
        lines = self._log_lines()
        self.assertEqual(lines[0]["kind"], "exchange")
        self.assertIn('"run-1"', lines[0]["response_body"])
        self.assertIn("https://api.exa.ai/agent/runs/run-1", lines[0]["argv"])

    def test_replay_honors_write_out_http_code(self):
        # the skill's key check does: curl -s -o /dev/null -w "%{http_code}"
        proc = self._run("replay", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                         "-X", "POST", "https://api.exa.ai/agent/runs")
        self.assertEqual(proc.stdout.strip(), "503")

    def test_replay_writes_body_to_output_file(self):
        out = os.path.join(self.tmp, "resp.json")
        proc = self._run("replay", "-s", "-o", out, "https://api.exa.ai/agent/runs/x")
        self.assertEqual(proc.stdout, "")
        with open(out) as f:
            self.assertIn("LIVE_EXA_DISABLED", f.read())

    def test_non_exa_call_is_untouched(self):
        proc = self._run("replay", "-s", "https://example.com/page")
        self.assertIn('"completed"', proc.stdout)  # our fake real curl answered
        self.assertEqual(self._log_lines(), [])


class TestSitecustomize(unittest.TestCase):
    def test_replay_raises_catchable_httperror_on_exa_url(self):
        # HTTPError specifically: it's what the skill's orchestrator catches,
        # so a replay block degrades to a clean skipped run, not a crash
        code = ("import urllib.request, urllib.error\n"
                "try:\n"
                "    urllib.request.urlopen('https://api.exa.ai/agent/runs')\n"
                "except urllib.error.HTTPError as e:\n"
                "    print('BLOCKED:', e.code, e.reason[:17], e.read().decode())\n")
        env = dict(os.environ, PYTHONPATH=SHIMS, EXA_HTTP_MODE="replay")
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True)
        self.assertIn("BLOCKED: 503 LIVE_EXA_DISABLED", proc.stdout)
        self.assertIn('{"error":"LIVE_EXA_DISABLED"}', proc.stdout)

    def test_inactive_without_mode(self):
        code = ("import urllib.request\n"
                "print(urllib.request.urlopen.__module__)\n")
        env = dict(os.environ, PYTHONPATH=SHIMS)
        env.pop("EXA_HTTP_MODE", None)
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True)
        self.assertEqual(proc.stdout.strip(), "urllib.request")


if __name__ == "__main__":
    unittest.main()
