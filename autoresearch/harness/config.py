"""Harness configuration: one JSON file, paths resolved relative to pipeline/."""
import json
import os
import re

PIPELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The skill profile: everything the harness must know about the TARGET
# skill's output contract. Keys absent from a config profile fall back to
# these values (the original exa-candidate-sourcing contract), so a config
# with no `profiles` block behaves exactly as before.
DEFAULT_PROFILE = {
    # the final deliverable the Inner agent must write into its run dir
    "output_csv": "candidates.csv",
    "viewer_html": "candidates.html",
    # columns that must exist in the output CSV (deterministic validator)
    "base_columns": ["rank", "name", "linkedinUrl", "currentTitle",
                     "currentCompany", "location", "score", "segment"],
    # column checked against expectations.exclude_employer_terms
    "org_column": "currentCompany",
    # column holding the person's current title/role (grounding claims)
    "title_column": "currentTitle",
    # key in the Exa run's structured output that carries the result list
    "structured_list_key": "candidates",
    # orchestrator session-state file (recorder's highest-fidelity source)
    "state_file": "sourcing_state.json",
    # role label for the simulated user's messages in conversation.json —
    # must match what the skill's user_llm.md prompt calls the user
    "requester_role": "recruiter",
    # skill paths (relative to the skill dir) that only execute in live runs;
    # replay-mode experiments touching them are parked as needs_live because
    # frozen fixtures cannot measure them (the orchestrator never runs in replay)
    "live_only_paths": ["orchestrator/"],
}


class Config:
    def __init__(self, data, pipeline_dir=PIPELINE_DIR):
        self.data = data
        self.pipeline_dir = pipeline_dir

    @classmethod
    def load(cls, path=None, pipeline_dir=None):
        if pipeline_dir is None:
            pipeline_dir = os.path.dirname(os.path.abspath(path)) if path else PIPELINE_DIR
        path = path or os.path.join(pipeline_dir, "config.json")
        with open(path) as f:
            return cls(json.load(f), pipeline_dir=pipeline_dir)

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def path(self, key):
        """Resolve a paths.* entry to an absolute path under pipeline/.
        '{skill}' segments resolve to skill.name, so per-skill data (suite,
        inbox, fixtures, labels, experiment log) never collides across the
        skills the pipeline targets."""
        rel = self.data["paths"][key].replace("{skill}", self.data["skill"]["name"])
        return os.path.normpath(os.path.join(self.pipeline_dir, rel))

    @property
    def profile(self):
        """The active skill's output-contract profile: DEFAULT_PROFILE keys
        overridden by config `profiles[skill.name]` (if present). This is how
        the harness supports skills whose deliverable differs from
        candidate-sourcing's candidates.csv (columns, list key, state file)
        without forking the harness."""
        overrides = self.data.get("profiles", {}).get(self.data["skill"]["name"], {})
        merged = dict(DEFAULT_PROFILE)
        merged.update(overrides)
        return merged

    def prompt_path(self, name):
        """Per-skill prompt override: prompts/<skill.name>/<name> wins over
        the shared prompts/<name>. Role prompts are prose about the domain
        (recruiter vs. generic requester), so skills override whole files
        rather than threading nouns through templates."""
        override = os.path.join(self.path("prompts"), self.data["skill"]["name"], name)
        if os.path.isfile(override):
            return override
        return os.path.join(self.path("prompts"), name)

    @property
    def skill_repo(self):
        return os.path.normpath(os.path.join(self.pipeline_dir, self.data["skill"]["repo"]))

    @property
    def skill_subpath(self):
        """Where the skill lives inside its repo. Empty when the skill IS the
        repo (standalone); "skills/<name>" when it's a subdir of a monorepo."""
        return self.data["skill"].get("path", "")

    def model(self, role):
        return self.data["models"][role]

    def actor_env(self, role):
        """Environment overrides that route this actor's `claude -p` at a
        provider other than the regular Claude account.

        Each actor (user/inner/validator/outer/importer) names a provider via
        `actor_providers`; the named preset in `providers` carries the
        base_url + credentials. The default provider is `anthropic` (no
        base_url), which returns `{}` so the actor runs on the machine's
        regular Claude account — keeping the strategic Outer on a strong
        Anthropic model while cheaper actors can route elsewhere.

        The base_url must speak the **Anthropic Messages API** (Claude Code
        only talks that protocol): the FireConnect router, an Anthropic-
        compatible proxy, etc. Secrets are read from the environment at
        runtime (never stored in config.json). A returned value of `None`
        means "delete this var from the subprocess env" (see run_claude), so
        an ambient ANTHROPIC_API_KEY can't shadow a routed provider's token.
        """
        preset_name = self.data.get("actor_providers", {}).get(role, "anthropic")
        preset = self.data.get("providers", {}).get(preset_name, {})
        base_url = preset.get("base_url")
        if not base_url:
            return {}
        # ANTHROPIC_API_KEY must be an empty string, not unset: Claude Code
        # falls back to authenticating against Anthropic (or a cached OAuth
        # login) when it is null, which would silently defeat the routing.
        env = {"ANTHROPIC_BASE_URL": _expand_env(base_url),
               "ANTHROPIC_API_KEY": ""}
        key_env = preset.get("api_key_env")
        if key_env:
            token = os.environ.get(key_env, "").strip()
            if not token:
                raise RuntimeError(
                    f"actor '{role}' routes through provider '{preset_name}', "
                    f"which needs ${key_env} — but it is unset in the environment")
            env["ANTHROPIC_AUTH_TOKEN"] = token
        headers = preset.get("custom_headers")
        if headers:
            env["ANTHROPIC_CUSTOM_HEADERS"] = _expand_env(headers)
        return env

    def limit(self, key):
        return self.data["limits"][key]


def _expand_env(s):
    """Substitute ${VAR} with os.environ[VAR] so config.json holds env-var
    references (e.g. custom_headers) instead of raw secrets."""
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), s)
