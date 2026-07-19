import os
import subprocess
import tempfile
import unittest

from util import GIT_ENV, make_skill_repo

from harness.workspace import PromotionConflict, Workspace, skill_size


def commit_in(repo, filename, content, message):
    with open(os.path.join(repo, filename), "w") as f:
        f.write(content)
    env = dict(os.environ, **GIT_ENV)
    subprocess.run(["git", "-C", repo, "add", "-A"], env=env, check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", message], env=env,
                   check=True, capture_output=True)


def branches(repo):
    out = subprocess.run(["git", "-C", repo, "branch", "--format=%(refname:short)"],
                         capture_output=True, text=True, check=True).stdout
    return set(out.split())


class TestWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ.update(GIT_ENV)
        self.source = make_skill_repo(os.path.join(self.tmp, "skill-repo"))
        self.ws = Workspace(self.source, os.path.join(self.tmp, "workspace"))

    def test_clone_checkout_branch_commit_push(self):
        clone = self.ws.checkout("main")
        self.assertTrue(os.path.isfile(os.path.join(clone, "SKILL.md")))

        self.ws.create_branch("exp/001-test", "main")
        with open(os.path.join(clone, "SKILL.md"), "a") as f:
            f.write("\nedited\n")
        sha = self.ws.commit_all("exp: test edit")
        self.assertIsNotNone(sha)
        self.assertIn("edited", self.ws.diff("main"))

        self.ws.push_branch("exp/001-test")
        self.assertIn("exp/001-test", branches(self.source))

    def test_commit_all_with_no_changes_returns_none(self):
        self.ws.checkout("main")
        self.assertIsNone(self.ws.commit_all("noop"))

    def test_changed_files_lists_experiment_paths(self):
        clone = self.ws.checkout("main")
        self.ws.create_branch("exp/002-files", "main")
        os.makedirs(os.path.join(clone, "orchestrator"), exist_ok=True)
        with open(os.path.join(clone, "orchestrator", "search.py"), "w") as f:
            f.write("# new\n")
        with open(os.path.join(clone, "SKILL.md"), "a") as f:
            f.write("\nedited\n")
        self.ws.commit_all("exp: two files")
        self.assertEqual(sorted(self.ws.changed_files("main")),
                         ["SKILL.md", "orchestrator/search.py"])

    def test_skill_size_counts_md_text_only(self):
        clone = self.ws.checkout("main")
        with open(os.path.join(clone, "big_module.py"), "w") as f:
            f.write("x = 1\n" * 500)  # code must not count
        base = skill_size(clone)
        self.assertGreater(base["chars"], 0)
        self.assertEqual(base["md_files"], 1)  # only SKILL.md
        with open(os.path.join(clone, "extra.md"), "w") as f:
            f.write("ten more words " * 10)
        grown = skill_size(clone)
        self.assertEqual(grown["md_files"], 2)
        self.assertGreater(grown["chars"], base["chars"])

    def test_checkout_discards_dirt(self):
        clone = self.ws.checkout("main")
        with open(os.path.join(clone, "junk.txt"), "w") as f:
            f.write("junk")
        self.ws.checkout("main")
        self.assertFalse(os.path.exists(os.path.join(clone, "junk.txt")))

    def test_checkout_tracks_source_repo_tip(self):
        clone = self.ws.checkout("main")
        commit_in(self.source, "SKILL.md", "# v2 of the skill\n", "user lands v2")
        self.ws.checkout("main")
        with open(os.path.join(clone, "SKILL.md")) as f:
            self.assertIn("v2", f.read())

    def test_promotion_conflict_reported_and_clone_recovers(self):
        clone = self.ws.checkout("main")
        # round 1: winner A edits SKILL.md, promoted cleanly
        self.ws.create_branch("exp/001-a", "main")
        with open(os.path.join(clone, "SKILL.md"), "a") as f:
            f.write("edit A\n")
        self.ws.commit_all("exp A")
        self.ws.promote("exp/001-a", "pipeline/candidate", "main")
        # round 2: winner B branches from main and edits the same line
        self.ws.create_branch("exp/002-b", "main")
        with open(os.path.join(clone, "SKILL.md"), "a") as f:
            f.write("edit B\n")
        self.ws.commit_all("exp B")
        with self.assertRaises(PromotionConflict):
            self.ws.promote("exp/002-b", "pipeline/candidate", "main")
        # the clone is not wedged mid-merge: later checkouts still work
        self.ws.checkout("main")
        self.assertEqual(self.ws.current_branch(), "main")

    def test_monorepo_subpath_skill_dir_and_scoped_diff(self):
        # skill lives at skills/mine/ inside a larger repo; the harness clones
        # the whole repo but must point the LLMs at the subdir and scope diffs
        # to it so unrelated repo files never look like the skill changed.
        skill_rel = "skills/mine"
        os.makedirs(os.path.join(self.source, skill_rel))
        commit_in(self.source, os.path.join(skill_rel, "SKILL.md"),
                  "# mono skill\n", "add skill subdir")
        commit_in(self.source, "unrelated.txt", "harness file\n", "add sibling")

        ws = Workspace(self.source, os.path.join(self.tmp, "ws-mono"), skill_rel)
        clone = ws.checkout("main")
        self.assertEqual(ws.skill_dir, os.path.join(clone, skill_rel))
        self.assertTrue(os.path.isfile(os.path.join(ws.skill_dir, "SKILL.md")))

        ws.create_branch("exp/001-mono", "main")
        with open(os.path.join(ws.skill_dir, "SKILL.md"), "a") as f:
            f.write("edited skill\n")
        with open(os.path.join(clone, "unrelated.txt"), "a") as f:
            f.write("edited sibling\n")
        ws.commit_all("exp: touch both")
        diff = ws.diff("main")
        self.assertIn("edited skill", diff)
        self.assertNotIn("edited sibling", diff)

    def test_promote_merges_and_pushes_without_touching_main(self):
        clone = self.ws.checkout("main")
        main_head = self.ws.head()
        self.ws.create_branch("exp/002-win", "main")
        with open(os.path.join(clone, "SKILL.md"), "a") as f:
            f.write("\nwinning edit\n")
        self.ws.commit_all("exp: winning edit")

        self.ws.promote("exp/002-win", "pipeline/candidate", "main")
        self.assertIn("pipeline/candidate", branches(self.source))
        self.assertIn("exp/002-win", branches(self.source))

        src_main = subprocess.run(["git", "-C", self.source, "rev-parse", "main"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(src_main, main_head)


if __name__ == "__main__":
    unittest.main()
