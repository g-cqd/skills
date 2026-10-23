import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "validate_audit.py")
sys.path.insert(0, os.path.join(HERE, ".."))
import validate_audit as v  # noqa: E402

TRACE = [{"kind": "entrypoint", "file": "src/a.ts", "line": 1, "scope": "route", "description": "input"},
         {"kind": "propagation", "file": "src/b.ts", "line": 2, "scope": "svc", "description": "passes"},
         {"kind": "sink", "file": "src/c.ts", "line": 3, "scope": "db", "description": "writes"}]
EVIDENCE = [{"file": "src/b.ts", "line": 2, "description": "no owner check"}]

CONFIRMED = {
    "verdict": "confirmed", "fingerprint": "api:update:owner", "title": "t", "description": "d",
    "root_cause": "r", "intended_behavior": "i", "trace": TRACE, "evidence": EVIDENCE,
    "conditions": [{"kind": "authentication", "description": "any account"}],
    "execution": {"attacker_perspective": "user A", "payloads": ["PATCH"], "instructions": ["run fixture"],
                  "observed_result": "B changed"},
    "remediation": {"strategy": "check owner", "code_changes": [{"file": "src/b.ts", "description": "compare ids"}],
                    "regression_test": "403 for A on B"},
    "severity": {"likelihood": {"score": "high", "reason": "one request"},
                 "impact": {"score": "high", "reason": "takeover"}, "overall_severity": "high"},
    "confidence": {"score": "high", "reason": "reproduced"}, "cwe": "CWE-639",
}
NEEDS = {
    "verdict": "needs_validation", "fingerprint": "auth:reset:host", "title": "t", "description": "d",
    "claimed_root_cause": "host header in link", "trace": TRACE[:1], "evidence": EVIDENCE,
    "blockers": ["whether the proxy overwrites Host"], "validation_plan": {"deployment": "owner reads proxy config"},
}
REJECTED = {
    "verdict": "rejected", "fingerprint": "web:search:sqli", "title": "t", "description": "d",
    "claimed_root_cause": "concatenation", "trace": TRACE[-1:], "evidence": EVIDENCE, "reason": "bound parameter",
}


def unit(status="covered", **changes):
    refs = {"surface": "src/router.ts#POST /users/:id", "boundary": "src/authz.ts#requireOwner",
            "subsystem": "packages/api", "attack_class": "attack-classes.md#Access control"}
    base = {
        "coverage_id": v.derive_id(refs), "canonical_refs": refs, "surface": "users update", "boundary": "owner",
        "subsystem": "api", "attack_class": "access control", "starting_paths": ["src/router.ts"],
        "attack_class_block": "attack-classes.md#Access control", "selected_blocks": [],
        "excluded_blocks": [{"block": "domains/cloud.md#IAM", "reason": "no cloud code"}],
        "prior_status": "none", "wave": 1, "status": status, "agent_id": None, "reviewed_paths": [],
        "local_checks": [], "result_fingerprints": [], "unresolved": [], "attempts": [],
    }
    check = {"agent_id": "hunter-1", "reviewed_paths": ["src/router.ts"], "invariant": "owner checked",
             "method": "source", "result": "checked", "artifact": None}
    if status in ("covered", "blocked", "candidate", "in_progress"):
        base["agent_id"] = "hunter-1"
    if status in ("covered", "blocked", "candidate"):
        base["reviewed_paths"] = ["src/router.ts"]
        base["local_checks"] = [check]
    if status == "candidate":
        base["result_fingerprints"] = ["api:update:owner"]
    if status in ("blocked", "deferred", "out_of_scope", "not_applicable"):
        base["unresolved"] = ["reason"]
    base.update(changes)
    return base


class FindingsTests(unittest.TestCase):
    def errors(self, records):
        return v.validate_findings(records).items

    def test_valid_records_of_each_verdict_pass(self):
        self.assertEqual(self.errors(sorted([CONFIRMED, NEEDS, REJECTED], key=lambda r: r["fingerprint"])), [])

    def assertRejects(self, record, fragment):
        found = self.errors([record])
        self.assertTrue(any(fragment in e for e in found), (fragment, found))

    def test_severity_on_a_needs_validation_record_is_refused(self):
        self.assertRejects(dict(NEEDS, severity=CONFIRMED["severity"]), "'severity' is not allowed")

    def test_overall_severity_cannot_exceed_the_impact(self):
        record = copy.deepcopy(CONFIRMED)
        record["severity"]["impact"]["score"] = "medium"
        record["severity"]["overall_severity"] = "high"
        self.assertRejects(record, "exceeds the demonstrated impact")
        record["severity"]["impact"]["score"] = "high"
        record["severity"]["overall_severity"] = "critical"
        self.assertEqual(self.errors([record]), [])

    def test_a_needs_validation_record_needs_a_blocker_and_a_plan(self):
        self.assertRejects(dict(NEEDS, blockers=[]), "blockers")
        self.assertRejects(dict(NEEDS, validation_plan={}), "needs a local or a deployment step")
        self.assertRejects(dict(NEEDS, validation_plan={"local": ""}), "must be a non-empty string")

    def test_verdict_fields_do_not_mix(self):
        self.assertRejects(dict(CONFIRMED, claimed_root_cause="x"), "'claimed_root_cause' is not allowed")
        self.assertRejects(dict(REJECTED, remediation={"strategy": "x"}), "'remediation' is not allowed")
        record = dict(CONFIRMED)
        del record["execution"]
        self.assertRejects(record, "'execution' is required")

    def test_trace_order_and_paths(self):
        bad = copy.deepcopy(CONFIRMED)
        bad["trace"] = [TRACE[2], TRACE[0]]
        self.assertRejects(bad, "starts with entrypoint")
        bad = copy.deepcopy(CONFIRMED)
        bad["trace"][0]["file"] = "/etc/passwd"
        self.assertRejects(bad, "repository-relative")
        bad["trace"][0]["file"] = "src/../../x"
        self.assertRejects(bad, "repository-relative")
        bad = copy.deepcopy(CONFIRMED)
        bad["trace"][1]["line"] = 0
        self.assertRejects(bad, "line must be an integer")
        bad["trace"][1]["line"] = True
        self.assertRejects(bad, "line must be an integer")

    def test_fingerprints_are_valid_unique_and_sorted(self):
        self.assertRejects(dict(CONFIRMED, fingerprint="-bad"), "fingerprint must match")
        found = self.errors([CONFIRMED, CONFIRMED])
        self.assertTrue(any("more than once" in e for e in found))
        found = self.errors([REJECTED, CONFIRMED])
        self.assertTrue(any("sorted" in e for e in found))

    def test_cwe_and_asvs_formats(self):
        self.assertRejects(dict(CONFIRMED, cwe="89"), "cwe")
        self.assertRejects(dict(CONFIRMED, asvs="L4"), "asvs")
        self.assertRejects(dict(REJECTED, cwe="CWE-89"), "'cwe' is not allowed")


class LedgerTests(unittest.TestCase):
    def errors(self, units):
        return v.validate_ledger(units).items

    def assertRejects(self, item, fragment):
        found = self.errors([item])
        self.assertTrue(any(fragment in e for e in found), (fragment, found))

    def test_each_state_passes_when_it_follows_the_table(self):
        for status in sorted(v.STATUSES):
            with self.subTest(status=status):
                self.assertEqual(self.errors([unit(status)]), [])

    def test_the_id_is_derived_from_the_canonical_references(self):
        self.assertRejects(unit(coverage_id="users-update"), "coverage_id must be")
        self.assertIn("%2F", v.derive_id({"surface": "a/b", "boundary": "c", "subsystem": "d", "attack_class": "e"}))
        self.assertTrue(v.derive_id({"surface": "é", "boundary": "c", "subsystem": "d",
                                     "attack_class": "e"}).startswith("%C3%A9::"))

    def test_canonical_references_must_be_clean_text(self):
        refs = dict(unit()["canonical_refs"], surface=" padded")
        self.assertRejects(unit(canonical_refs=refs), "NFC text")
        refs = dict(unit()["canonical_refs"], surface="e\u0301")
        self.assertRejects(unit(canonical_refs=refs), "NFC text")
        refs = dict(unit()["canonical_refs"], surface="zero\u200bwidth")
        self.assertRejects(unit(canonical_refs=refs), "NFC text")

    def test_state_table_violations(self):
        self.assertRejects(unit("planned", agent_id="hunter-1"), "no owner and no evidence")
        self.assertRejects(unit("deferred", unresolved=[]), "states its reason")
        self.assertRejects(unit("covered", unresolved=["x"]), "nothing unresolved")
        self.assertRejects(unit("covered", result_fingerprints=["a:b"]), "links no fingerprint")
        self.assertRejects(unit("candidate", result_fingerprints=[]), "links at least one fingerprint")
        self.assertRejects(unit("blocked", unresolved=[]), "states what is unresolved")
        self.assertRejects(unit("covered", agent_id="Hunter"), "valid agent_id")
        self.assertRejects(unit("covered", agent_id="con"), "valid agent_id")

    def test_paths_must_be_the_union_of_the_checks(self):
        self.assertRejects(unit("covered", reviewed_paths=["src/router.ts", "src/extra.ts"]), "union")

    def test_check_methods_and_artifacts(self):
        local = {"agent_id": "hunter-1", "reviewed_paths": ["src/router.ts"], "invariant": "i", "method": "local",
                 "result": "r", "artifact": "agents/hunter-1/artifacts/out.txt"}
        self.assertEqual(self.errors([unit("covered", local_checks=[local])]), [])
        self.assertRejects(unit("covered", local_checks=[dict(local, artifact="agents/other/artifacts/x")]),
                           "a local check names one file")
        self.assertRejects(unit("covered", local_checks=[dict(local, artifact="agents/hunter-1/artifacts/../x")]),
                           "a local check names one file")
        self.assertRejects(unit("covered", local_checks=[dict(local, method="source")]), "artifact null")

    def test_attempts_archive_earlier_waves_only(self):
        attempt = {"wave": 1, "status": "covered", "agent_id": "hunter-1", "reviewed_paths": ["src/router.ts"],
                   "local_checks": unit("covered")["local_checks"], "result_fingerprints": [], "unresolved": [],
                   "reassignment_reason": "critic found a parallel path"}
        self.assertEqual(self.errors([unit("in_progress", wave=2, agent_id="hunter-2", attempts=[attempt])]), [])
        self.assertRejects(unit("in_progress", wave=1, agent_id="hunter-2", attempts=[attempt]), "attempt waves")
        self.assertRejects(unit("in_progress", wave=2, agent_id="hunter-2", attempts=[dict(attempt, status="planned")]),
                           "only blocked, covered, or candidate")

    def test_ids_are_unique_sorted_and_one_tuple_has_one_id(self):
        other = unit()
        found = self.errors([other, copy.deepcopy(other)])
        self.assertTrue(any("more than once" in e for e in found))
        refs = dict(other["canonical_refs"], boundary="src/authz.ts#requireOwner2")
        alias = unit(canonical_refs=refs, coverage_id=v.derive_id(refs))
        found = self.errors(sorted([other, alias], key=lambda u: u["coverage_id"]))
        self.assertTrue(any("another coverage_id" in e for e in found))


class CommandLineTests(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=60)

    def write(self, data, raw=None):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        handle.write(raw if raw is not None else json.dumps(data))
        handle.close()
        self.addCleanup(os.remove, handle.name)
        return handle.name

    def test_exit_codes(self):
        self.assertEqual(self.run_script("findings", self.write([CONFIRMED])).returncode, 0)
        self.assertEqual(self.run_script("ledger", self.write([unit()])).returncode, 0)
        bad = self.run_script("findings", self.write([dict(NEEDS, severity={})]))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("severity", bad.stderr)
        self.assertEqual(self.run_script("findings", self.write(None, raw="{nope")).returncode, 1)
        self.assertEqual(self.run_script("other", "x").returncode, 2)
        self.assertEqual(self.run_script("findings", "/nonexistent/file.json").returncode, 2)

    def test_deep_nesting_and_error_cap(self):
        deep = self.write(None, raw="[" * 70 + "]" * 70)
        self.assertEqual(self.run_script("findings", deep).returncode, 1)
        many = self.run_script("findings", self.write([{"verdict": "x"}] * 150))
        self.assertEqual(many.returncode, 1)
        self.assertIn("and 50 more", many.stderr)


if __name__ == "__main__":
    unittest.main()
