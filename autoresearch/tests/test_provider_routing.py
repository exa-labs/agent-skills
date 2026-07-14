"""Per-actor provider routing: config.actor_env resolution + run_claude env
injection. Lets cheap actors run on open-weights providers while the strategic
Outer stays on the regular Claude account."""
import json
import os
import tempfile
import unittest

from harness.claude_cli import run_claude
from harness.config import Config

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "config.json")


def _config():
    return Config.load(CONFIG_PATH)


class TestActorEnv(unittest.TestCase):
    def test_default_actor_uses_regular_account(self):
        # every actor defaults to 'anthropic' (no base_url) -> no env override,
        # so the subprocess falls through to the machine's Claude credentials.
        self.assertEqual(_config().actor_env("outer"), {})

    def test_openrouter_actor_gets_base_url_and_token(self):
        c = _config()
        c.data["actor_providers"]["inner"] = "openrouter"
        os.environ["OPENROUTER_API_KEY"] = "sk-or-xyz"
        self.addCleanup(os.environ.pop, "OPENROUTER_API_KEY", None)
        env = c.actor_env("inner")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://openrouter.ai/api")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "sk-or-xyz")
        # empty string, NOT unset: a null key makes Claude Code fall back to
        # Anthropic / a cached OAuth login and silently defeats the routing.
        self.assertEqual(env["ANTHROPIC_API_KEY"], "")

    def test_fireconnect_actor_expands_key_into_custom_header(self):
        c = _config()
        c.data["actor_providers"]["user"] = "fireconnect"
        os.environ["FIREWORKS_API_KEY"] = "fw_secret"
        self.addCleanup(os.environ.pop, "FIREWORKS_API_KEY", None)
        env = c.actor_env("user")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://router.fireworks.ai")
        self.assertEqual(env["ANTHROPIC_CUSTOM_HEADERS"],
                         "X-FireRouter-Fireworks-Key: fw_secret")

    def test_missing_credential_env_raises(self):
        c = _config()
        c.data["actor_providers"]["validator"] = "openrouter"
        os.environ.pop("OPENROUTER_API_KEY", None)
        with self.assertRaises(RuntimeError):
            c.actor_env("validator")


class TestRunClaudeEnvInjection(unittest.TestCase):
    """run_claude reflects env_extra into the subprocess: string values are set,
    a None value deletes the var (so a routed provider's token can't be
    shadowed by an inherited ANTHROPIC_API_KEY)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.stub = os.path.join(self.tmp, "echo_env.py")
        with open(self.stub, "w") as f:
            f.write(
                "#!/usr/bin/env python3\n"
                "import os, json\n"
                "print(json.dumps({\n"
                "  'result': os.environ.get('ANTHROPIC_BASE_URL', 'NONE') + '|' +\n"
                "            ('KEY' if 'ANTHROPIC_API_KEY' in os.environ else 'NOKEY'),\n"
                "  'session_id': 's', 'total_cost_usd': 0.001, 'is_error': False}))\n")
        os.chmod(self.stub, 0o755)
        self._old = os.environ.get("PIPELINE_CLAUDE_BIN")
        os.environ["PIPELINE_CLAUDE_BIN"] = self.stub
        os.environ["ANTHROPIC_API_KEY"] = "ambient-key"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if self._old is None:
            os.environ.pop("PIPELINE_CLAUDE_BIN", None)
        else:
            os.environ["PIPELINE_CLAUDE_BIN"] = self._old

    def test_none_value_unsets_var_and_string_value_sets_it(self):
        res = run_claude("hi", model="m", cwd=self.tmp, timeout_s=30,
                         env_extra={"ANTHROPIC_BASE_URL": "https://router.example",
                                    "ANTHROPIC_API_KEY": None})
        self.assertTrue(res.ok)
        self.assertEqual(res.text, "https://router.example|NOKEY")

    def test_no_env_extra_leaves_ambient_env_intact(self):
        res = run_claude("hi", model="m", cwd=self.tmp, timeout_s=30)
        self.assertTrue(res.ok)
        self.assertEqual(res.text, "NONE|KEY")


if __name__ == "__main__":
    unittest.main()
