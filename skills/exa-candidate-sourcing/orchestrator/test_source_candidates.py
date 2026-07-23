import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import source_candidates as sc


def config(unknown_policy="exclude", description="Must not be a contractor"):
    return {
        "role": "Infrastructure Engineer",
        "locations": ["New York City"],
        "exclude_employer": "Hiring Co",
        "exclude_people": [],
        "contact_fields": [],
        "rubric_must_haves": ["Infrastructure engineering"],
        "rubric_signals": [],
        "dimensions": [{"key": "infrastructure", "scale": "capability"}],
        "segments": [{"label": "finance", "focus": "Finance infrastructure engineers"}],
        "hard_constraints": {
            "location_mode": "required",
            "excluded_current_employers": [],
            "excluded_current_employers_confirmed": False,
            "required_seniority_levels": [],
            "requirements": [{"key": "not_a_contractor", "description": description,
                              "unknown_policy": unknown_policy}],
        },
    }


def full_candidate(discovery_status="meets"):
    return {
        "name": "Test Person",
        "currentTitle": "Infrastructure Engineer",
        "currentCompany": "Example Finance",
        "location": "New York City",
        "linkedinUrl": "https://www.linkedin.com/in/test-person",
        "yearsRelevantExperience": 7,
        "currentlyAtExcludedEmployer": False,
        "hardConstraintChecks": {
            "not_a_contractor": {"status": discovery_status, "signals": ["Discovery signal"]},
        },
        "infrastructure": {"level": "strong", "signals": ["Kubernetes"]},
        "seniority": {"level": "ic_senior", "signals": ["Senior title"]},
        "overallFit": {"tier": "strong", "confidence": "high",
                       "signalsUsed": ["Kubernetes"], "concerns": []},
        "mobility": {"monthsInCurrentRole": 24, "monthsAtCurrentCompany": 24,
                     "avgMonthsPerPriorRole": 30, "seniorityVsRole": "aligned", "signals": []},
        "_segment": "finance",
    }


class CandidateStateTests(unittest.TestCase):
    def test_policy_change_reuses_verification_facts(self):
        strict = config("exclude")
        graded = config("allow")
        self.assertEqual(sc.verification_signature(strict), sc.verification_signature(graded))
        changed_fact = config("allow", "Must have no consulting work of any kind")
        self.assertNotEqual(sc.verification_signature(strict), sc.verification_signature(changed_fact))

    def test_verified_checks_override_discovery_checks(self):
        candidate = full_candidate("meets")
        candidate["_hard_checks"] = {
            "not_a_contractor": {"status": "fails", "signals": ["Verified consultant role"]},
        }
        self.assertFalse(sc.passes_hard_constraints(config("allow"), candidate))
        self.assertFalse(sc.eligible_after_verification(config("allow"), candidate))

    def test_calibration_record_is_not_full_candidate(self):
        provisional = {"name": "Test Person", "currentTitle": "Engineer",
                       "currentCompany": "Example", "location": "New York City"}
        self.assertFalse(sc.is_full_candidate(config(), provisional))
        self.assertTrue(sc.is_full_candidate(config(), full_candidate()))
        item = sc.build_enrichment_schema(config())["properties"]["candidates"]["items"]
        self.assertIn("sourceId", item["required"])
        self.assertIn("overallFit", item["required"])

    def test_new_unknown_policy_reapplies_to_verified_unknown(self):
        candidate = full_candidate("meets")
        sc.apply_verdict(candidate, {
            "exists": "confirmed",
            "matches_role": "strong",
            "currently_excluded": False,
            "hardConstraintChecks": {
                "not_a_contractor": {"status": "unknown", "signals": []},
            },
        })
        self.assertFalse(sc.eligible_after_verification(config("exclude"), candidate))
        self.assertTrue(sc.eligible_after_verification(config("allow"), candidate))

    def test_reuse_keeps_legacy_verified_failure_authoritative(self):
        old_cfg = config("exclude")
        new_cfg = config("allow")
        candidate = full_candidate("meets")
        key = sc._key(candidate)
        verified_failure = {
            "exists": "confirmed",
            "matches_role": "strong",
            "currently_excluded": False,
            "hardConstraintChecks": {
                "not_a_contractor": {"status": "fails", "signals": ["Verified consultant role"]},
            },
        }
        legacy_sig = sc.config_signature(old_cfg)
        state = {
            "version": 3,
            "config_signature": legacy_sig,
            "config_snapshot": old_cfg,
            "run_ids": {},
            "pool": [candidate],
            "verdicts_by_search": {legacy_sig: {key: verified_failure}},
        }

        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "config.json")
            state_path = os.path.join(tmp, "sourcing_state.json")
            with open(config_path, "w") as fh:
                json.dump(new_cfg, fh)
            with open(state_path, "w") as fh:
                json.dump(state, fh)
            argv = ["source_candidates.py", "--config", config_path, "--state", state_path, "--reuse"]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(sc, "write_outputs") as write:
                sc.main()
            final = write.call_args.args[1]
            self.assertEqual(final, [])
            with open(state_path) as fh:
                saved = json.load(fh)
            self.assertEqual(saved["verification_signature"], sc.verification_signature(new_cfg))
            self.assertEqual(saved["pool"][0]["_hard_checks"]["not_a_contractor"]["status"], "fails")


if __name__ == "__main__":
    unittest.main()
