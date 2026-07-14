"""Git operations on the skill repository.

The harness never edits the skill in place: it clones the source repo into
pipeline/workspace/<name>/ and does all branch work there, so a crashed
experiment can never leave the user's checkout dirty. Promotion merges a
winning experiment branch into the promotion branch (never main) and pushes
both back to the source repo.

The skill may be the whole repo (standalone) or a subdirectory of a larger
repo (monorepo). `skill_subpath` names that subdir: git ops (branch, commit,
diff, promote) always run on the clone root, while `skill_dir` points the
Inner/Outer LLMs at the skill files themselves. An empty subpath means the
skill IS the repo root.
"""
import os
import subprocess


class GitError(Exception):
    pass


class PromotionConflict(GitError):
    """The winner branch doesn't merge cleanly into the promotion branch;
    needs a human merge. The clone is left clean, not mid-conflict."""


def _git(repo, *args, check=True):
    proc = subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed in {repo}:\n{proc.stderr.strip()}")
    return proc.stdout.strip()


class Workspace:
    def __init__(self, source_repo, workspace_dir, skill_subpath=""):
        self.source_repo = os.path.abspath(source_repo)
        self.clone_dir = os.path.join(os.path.abspath(workspace_dir),
                                      os.path.basename(self.source_repo))
        self.skill_subpath = skill_subpath

    @property
    def skill_dir(self):
        """Absolute path to the skill files in the clone — the clone root for a
        standalone skill, or the subdir for a monorepo skill."""
        return os.path.normpath(os.path.join(self.clone_dir, self.skill_subpath))

    def ensure_clone(self):
        """Clone the skill repo into the workspace (or fetch if already there)."""
        if os.path.isdir(os.path.join(self.clone_dir, ".git")):
            _git(self.clone_dir, "fetch", "origin", "--prune")
        else:
            os.makedirs(os.path.dirname(self.clone_dir), exist_ok=True)
            subprocess.run(["git", "clone", self.source_repo, self.clone_dir],
                           capture_output=True, text=True, check=True)
        return self.clone_dir

    def checkout(self, ref):
        """Check out a ref (branch or sha) at the SOURCE repo's current tip.

        Always recovers first: a crashed merge (e.g. a promotion conflict)
        must never wedge the clone for later runs. For branch refs, reset to
        origin/<ref> when it exists — the persistent clone's local branch goes
        stale the moment the user lands changes in the real skill repo."""
        self.ensure_clone()
        _git(self.clone_dir, "merge", "--abort", check=False)
        _git(self.clone_dir, "reset", "--hard", "--quiet")
        _git(self.clone_dir, "clean", "-fdq")
        _git(self.clone_dir, "checkout", "--quiet", ref)
        if subprocess.run(["git", "-C", self.clone_dir, "rev-parse", "--verify",
                           "--quiet", f"origin/{ref}"], capture_output=True).returncode == 0:
            _git(self.clone_dir, "reset", "--hard", "--quiet", f"origin/{ref}")
        else:
            _git(self.clone_dir, "reset", "--hard", "--quiet")
        _git(self.clone_dir, "clean", "-fdq")
        return self.clone_dir

    def create_branch(self, branch, base_ref):
        self.checkout(base_ref)
        _git(self.clone_dir, "checkout", "-B", branch, base_ref)
        return branch

    def commit_all(self, message):
        _git(self.clone_dir, "add", "-A")
        status = _git(self.clone_dir, "status", "--porcelain")
        if not status:
            return None
        _git(self.clone_dir, "commit", "-m", message)
        return self.head()

    def head(self):
        return _git(self.clone_dir, "rev-parse", "HEAD")

    def current_branch(self):
        return _git(self.clone_dir, "rev-parse", "--abbrev-ref", "HEAD")

    def diff(self, base_ref, ref=None):
        args = ["diff", f"{base_ref}...{ref or 'HEAD'}"]
        if self.skill_subpath:
            args += ["--", self.skill_subpath]
        return _git(self.clone_dir, *args)

    def branch_exists(self, branch):
        return subprocess.run(["git", "-C", self.clone_dir, "rev-parse", "--verify",
                               "--quiet", branch], capture_output=True).returncode == 0

    def promote(self, winner_branch, promotion_branch, base_ref):
        """Merge the winning experiment branch into the promotion branch and push
        both branches back to the source repo. main is never touched — the user
        reviews the promotion branch and merges it themselves."""
        if self.branch_exists(promotion_branch):
            self.checkout(promotion_branch)
        else:
            self.create_branch(promotion_branch, base_ref)
        try:
            _git(self.clone_dir, "merge", "--no-ff", "-m",
                 f"pipeline: promote {winner_branch}", winner_branch)
        except GitError as e:
            _git(self.clone_dir, "merge", "--abort", check=False)
            raise PromotionConflict(
                f"{winner_branch} does not merge cleanly into {promotion_branch}; "
                f"merge it by hand ({e})") from e
        _git(self.clone_dir, "push", "origin", promotion_branch, winner_branch)
        return self.head()

    def push_branch(self, branch):
        """Publish an experiment branch back to the source repo for inspection."""
        _git(self.clone_dir, "push", "origin", branch)
