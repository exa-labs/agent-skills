import json
import os
import tempfile
import unittest

from util import POOL, VERIFY_VERDICTS

from harness.recorder import latest_bundle, load_bundle, prepare_replay, record_bundle

COMPLETED_DISCOVERY = {
    "id": "run-abc", "status": "completed",
    "output": {
        "structured": {"candidates": [
            {"name": "Dana Field", "linkedinUrl": "https://linkedin.com/in/dana-field",
             "currentCompany": "Northgate"},
            {"name": "Eli Stone", "linkedinUrl": None, "currentCompany": "Southline"}]},
        "grounding": [
            {"field": "structured.candidates[0]",
             "citations": [{"url": "https://example.com/dana", "title": "Dana"}]},
            {"field": "structured.candidates[0].currentCompany",
             "citations": [{"url": "https://example.com/dana2"}]},
            {"field": "structured", "citations": [{"url": "https://example.com/trail"}]}],
    },
}

COMPLETED_VERIFY = {
    "id": "run-def", "status": "completed",
    "output": {"structured": {"verdicts": [
        {"id": "li:dana-field", "name": "Dana Field", "exists": "confirmed",
         "matches_role": "strong"}]}},
}


class TestRecorder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.run_dir = os.path.join(self.tmp, "run")
        os.makedirs(os.path.join(self.run_dir, "outdir"))
        self.fixtures = os.path.join(self.tmp, "fixtures")

    def _record(self):
        return record_bundle(self.run_dir, self.fixtures, "t001", "rec-x", "main")

    def test_sourcing_state_is_preferred_source(self):
        with open(os.path.join(self.run_dir, "outdir", "sourcing_state.json"), "w") as f:
            json.dump({"run_ids": {}, "pool": POOL, "verdicts": VERIFY_VERDICTS}, f)
        bundle = self._record()
        pool, verdicts = load_bundle(bundle)
        self.assertEqual(len(pool), 3)
        self.assertEqual(verdicts["li:alice-warden"]["exists"], "confirmed")
        with open(os.path.join(bundle, "meta.json")) as f:
            self.assertEqual(json.load(f)["source"], "sourcing_state")

    def test_http_log_fallback_attributes_grounding(self):
        with open(os.path.join(self.run_dir, "exa_http.jsonl"), "w") as f:
            f.write(json.dumps({"via": "curl", "kind": "exchange",
                                "response_body": json.dumps(COMPLETED_DISCOVERY)}) + "\n")
            f.write(json.dumps({"via": "urllib", "kind": "exchange",
                                "response_body": json.dumps(COMPLETED_VERIFY)}) + "\n")
            f.write(json.dumps({"via": "curl", "kind": "blocked", "argv": []}) + "\n")
            f.write("not json\n")
        bundle = self._record()
        pool, verdicts = load_bundle(bundle)
        self.assertEqual(len(pool), 2)
        dana = next(c for c in pool if c["name"] == "Dana Field")
        self.assertEqual(dana["_segment"], "seg01")
        self.assertEqual(dana["_sources"],
                         ["https://example.com/dana", "https://example.com/dana2"])
        self.assertNotIn("_sources", next(c for c in pool if c["name"] == "Eli Stone"))
        self.assertIn("li:dana-field", verdicts)

    def test_repeated_polls_of_same_run_harvest_once(self):
        # every poll of a completed run returns the same body; harvesting each
        # observation would duplicate candidates and inflate segment labels
        with open(os.path.join(self.run_dir, "exa_http.jsonl"), "w") as f:
            for _ in range(3):
                f.write(json.dumps({"via": "curl", "kind": "exchange",
                                    "response_body": json.dumps(COMPLETED_DISCOVERY)}) + "\n")
        pool, _ = load_bundle(self._record())
        self.assertEqual(len(pool), 2)
        self.assertEqual({c["_segment"] for c in pool}, {"seg01"})

    def test_transcript_fallback(self):
        event = {"type": "user", "message": {"content": [
            {"type": "tool_result", "content": json.dumps(COMPLETED_DISCOVERY)}]}}
        with open(os.path.join(self.run_dir, "transcript.jsonl"), "w") as f:
            f.write(json.dumps(event) + "\n")
        pool, _ = load_bundle(self._record())
        self.assertEqual(len(pool), 2)

    def test_nothing_captured_returns_none(self):
        self.assertIsNone(self._record())

    def test_latest_bundle_and_prepare_replay(self):
        with open(os.path.join(self.run_dir, "outdir", "sourcing_state.json"), "w") as f:
            json.dump({"pool": POOL, "verdicts": {}}, f)
        self._record()
        bundle = latest_bundle(self.fixtures, "t001")
        self.assertTrue(bundle.endswith("rec-x"))
        outdir = os.path.join(self.tmp, "replay-out")
        os.makedirs(outdir)
        target = prepare_replay(bundle, outdir)
        for name in ("pool.json", "verify_verdicts.json", "meta.json", "README.md"):
            self.assertTrue(os.path.isfile(os.path.join(target, name)))


if __name__ == "__main__":
    unittest.main()
