"""Harness configuration: one JSON file, paths resolved relative to pipeline/."""
import json
import os

PIPELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    def skill_repo(self):
        return os.path.normpath(os.path.join(self.pipeline_dir, self.data["skill"]["repo"]))

    def model(self, role):
        return self.data["models"][role]

    def limit(self, key):
        return self.data["limits"][key]
