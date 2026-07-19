import os
import tempfile
import unittest

from util import GIT_ENV, PIPELINE_DIR, make_skill_repo  # noqa: F401  (sys.path setup)

from harness.config import Config
from harness.optimizer import _live_only_changes, _slug
from harness.workspace import Workspace


class TestSlugSanitization(unittest.TestCase):
    def test_llm_slugs_become_valid_branch_names(self):
        cases = {
            "tighten-ranking": "tighten-ranking",
            "tighten ranking": "tighten-ranking",
            "fix: dupes!": "fix-dupes",
            "a/b nested": "a-b-nested",
            "Weird~^:?*Chars": "weird-chars",
            "": "edit",
            None: "edit",
            "x" * 100: "x" * 30,
        }
        for raw, expected in cases.items():
            self.assertEqual(_slug({"slug": raw}), expected, raw)

    def test_missing_slug_key(self):
        self.assertEqual(_slug({}), "edit")


class TestLiveOnlyChanges(unittest.TestCase):
    """Diff-based needs_live parking: the orchestrator never executes in
    replay, so a replay evaluation of an orchestrator edit would dishonestly
    measure it as 'no change' — regardless of what stages the proposal
    self-reported."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ.update(GIT_ENV)
        self.subpath = "skills/test-skill"
        source = make_skill_repo(os.path.join(self.tmp, "skill-repo"), self.subpath)
        self.ws = Workspace(source, os.path.join(self.tmp, "workspace"), self.subpath)
        self.config = Config({"skill": {"name": "test-skill", "repo": "..",
                                        "path": self.subpath, "base_ref": "main"},
                              "paths": {"prompts": "prompts"}})

    def _commit(self, relpath, content):
        clone = self.ws.clone_dir
        path = os.path.join(clone, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        self.ws.commit_all(f"edit {relpath}")

    def test_orchestrator_edit_is_flagged(self):
        self.ws.checkout("main")
        self.ws.create_branch("exp/001-x", "main")
        self._commit(f"{self.subpath}/orchestrator/search_people.py", "# tweak\n")
        hits = _live_only_changes(self.config, self.ws, "main")
        self.assertEqual(hits, [f"{self.subpath}/orchestrator/search_people.py"])

    def test_skill_md_edit_is_not_flagged(self):
        self.ws.checkout("main")
        self.ws.create_branch("exp/002-y", "main")
        self._commit(f"{self.subpath}/SKILL.md", "# revised skill\n")
        self.assertEqual(_live_only_changes(self.config, self.ws, "main"), [])

    def test_mixed_edit_reports_only_live_only_paths(self):
        self.ws.checkout("main")
        self.ws.create_branch("exp/003-z", "main")
        self._commit(f"{self.subpath}/SKILL.md", "# revised\n")
        self._commit(f"{self.subpath}/orchestrator/render.py", "# viewer\n")
        hits = _live_only_changes(self.config, self.ws, "main")
        self.assertEqual(hits, [f"{self.subpath}/orchestrator/render.py"])


if __name__ == "__main__":
    unittest.main()
