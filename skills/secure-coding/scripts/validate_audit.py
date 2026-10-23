#!/usr/bin/env python3
"""Validate the audit files of the secure-coding skill: findings.json and coverage-ledger.json.

Usage:
  validate_audit.py findings FILE
  validate_audit.py ledger FILE

The formats are in references/findings-format.md. Exit 0 when the file is valid, 1 when it is not (the errors go to
standard error, at most 100), 2 for a usage error or a file that cannot be read. The checks cover structure and
consistency, not whether a claim is true. Python 3.9 or later, standard library only.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Set

MAX_BYTES = 5 * 1024 * 1024
MAX_DEPTH = 64
MAX_FINDINGS = 1000
MAX_UNITS = 10000
MAX_ERRORS = 100

FINGERPRINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
AGENT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CWE_RE = re.compile(r"^CWE-[1-9][0-9]*$")
WINDOWS_DEVICES = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
SCORES = ("low", "medium", "high")
OVERALL = ("informational", "low", "medium", "high", "critical")
OVERALL_LIMIT = {"low": "low", "medium": "medium", "high": "critical"}
PRIOR = {"new", "none", "prior_confirmed_same_source", "prior_confirmed_changed_source", "prior_needs_validation",
         "prior_deferred", "prior_blocked", "prior_out_of_scope", "prior_covered_same_source",
         "prior_covered_changed_source", "prior_rejected_claim_changed"}

COMMON = {"verdict", "fingerprint", "title", "description", "trace", "evidence"}
FIELDS = {
    "confirmed": COMMON | {"root_cause", "intended_behavior", "conditions", "execution", "remediation", "severity",
                           "confidence", "cwe", "asvs"},
    "needs_validation": COMMON | {"claimed_root_cause", "blockers", "validation_plan", "cwe", "asvs"},
    "rejected": COMMON | {"claimed_root_cause", "reason"},
}
REQUIRED = {
    "confirmed": COMMON | {"root_cause", "intended_behavior", "conditions", "execution", "remediation", "severity",
                           "confidence"},
    "needs_validation": COMMON | {"claimed_root_cause", "blockers", "validation_plan"},
    "rejected": COMMON | {"claimed_root_cause", "reason"},
}

UNIT_FIELDS = {"coverage_id", "canonical_refs", "surface", "boundary", "subsystem", "attack_class", "lifecycle",
               "starting_paths", "attack_class_block", "selected_blocks", "excluded_blocks", "prior_status", "wave",
               "status", "agent_id", "reviewed_paths", "local_checks", "result_fingerprints", "unresolved", "attempts"}
UNIT_REQUIRED = UNIT_FIELDS - {"lifecycle"}
STATUSES = {"planned", "not_applicable", "out_of_scope", "deferred", "in_progress", "blocked", "covered", "candidate"}
ARCHIVABLE = {"blocked", "covered", "candidate"}


class Errors:
    def __init__(self) -> None:
        self.items: List[str] = []

    def add(self, where: str, message: str) -> None:
        self.items.append(f"{where}: {message}")

    def __bool__(self) -> bool:
        return bool(self.items)


def depth(value: Any, level: int = 0) -> int:
    if level > MAX_DEPTH:
        return level
    if isinstance(value, dict):
        return max([depth(v, level + 1) for v in value.values()] or [level])
    if isinstance(value, list):
        return max([depth(v, level + 1) for v in value] or [level])
    return level


def text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def repo_path(value: Any) -> bool:
    if not text(value) or value.startswith("/") or value.startswith("\\") or re.match(r"^[A-Za-z]:", value):
        return False
    return ".." not in re.split(r"[\\/]", value)


def agent_id(value: Any) -> bool:
    return isinstance(value, str) and AGENT_RE.match(value) is not None and value not in WINDOWS_DEVICES


def check_keys(errors: Errors, where: str, obj: Dict[str, Any], allowed: Set[str], required: Set[str]) -> None:
    for key in sorted(set(obj) - allowed):
        errors.add(where, f"field {key!r} is not allowed here")
    for key in sorted(required - set(obj)):
        errors.add(where, f"field {key!r} is required")


def check_locations(errors: Errors, where: str, items: Any, name: str, with_kind: bool) -> None:
    if not isinstance(items, list) or not items:
        errors.add(where, f"{name} must be a non-empty array")
        return
    for index, item in enumerate(items):
        spot = f"{where}.{name}[{index}]"
        if not isinstance(item, dict):
            errors.add(spot, "must be an object")
            continue
        keys = {"kind", "file", "line", "scope", "description"} if with_kind else {"file", "line", "description"}
        check_keys(errors, spot, item, keys, keys)
        if "file" in item and not repo_path(item["file"]):
            errors.add(spot, "file must be a repository-relative path without '..'")
        if "line" in item and (not isinstance(item["line"], int) or isinstance(item["line"], bool) or item["line"] < 1):
            errors.add(spot, "line must be an integer of at least 1")
        for key in keys - {"file", "line"}:
            if key in item and not text(item[key]):
                errors.add(spot, f"{key} must be a non-empty string")
    if with_kind:
        kinds = [item.get("kind") for item in items if isinstance(item, dict)]
        if len(kinds) == 1:
            if kinds[0] not in ("entrypoint", "sink"):
                errors.add(f"{where}.trace", "a one-step trace is an entrypoint or a sink")
        elif kinds:
            expected = ["entrypoint"] + ["propagation"] * (len(kinds) - 2) + ["sink"]
            if kinds != expected:
                errors.add(f"{where}.trace", "a trace starts with entrypoint, ends with sink, and has propagation between")


def check_scored(errors: Errors, where: str, value: Any, scores: tuple) -> Optional[str]:
    if not isinstance(value, dict):
        errors.add(where, "must be an object with score and reason")
        return None
    check_keys(errors, where, value, {"score", "reason"}, {"score", "reason"})
    if value.get("score") not in scores:
        errors.add(where, f"score must be one of {', '.join(scores)}")
    if "reason" in value and not text(value["reason"]):
        errors.add(where, "reason must be a non-empty string")
    return value.get("score")


def check_finding(errors: Errors, index: int, record: Any) -> Optional[str]:
    where = f"findings[{index}]"
    if not isinstance(record, dict):
        errors.add(where, "must be an object")
        return None
    verdict = record.get("verdict")
    if verdict not in FIELDS:
        errors.add(where, "verdict must be confirmed, needs_validation, or rejected")
        return None
    check_keys(errors, where, record, FIELDS[verdict], REQUIRED[verdict])
    fingerprint = record.get("fingerprint")
    if not isinstance(fingerprint, str) or not FINGERPRINT_RE.match(fingerprint):
        errors.add(where, "fingerprint must match ^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
        fingerprint = None
    for key in ("title", "description", "root_cause", "intended_behavior", "claimed_root_cause", "reason"):
        if key in record and not text(record[key]):
            errors.add(where, f"{key} must be a non-empty string")
    check_locations(errors, where, record.get("trace"), "trace", True)
    check_locations(errors, where, record.get("evidence"), "evidence", False)
    if "cwe" in record and (not isinstance(record["cwe"], str) or not CWE_RE.match(record["cwe"])):
        errors.add(where, "cwe must look like CWE-89")
    if "asvs" in record and record["asvs"] not in ("L1", "L2", "L3"):
        errors.add(where, "asvs must be L1, L2, or L3")

    if verdict == "confirmed":
        conditions = record.get("conditions")
        if not isinstance(conditions, list):
            errors.add(where, "conditions must be an array")
        else:
            for c_index, condition in enumerate(conditions):
                spot = f"{where}.conditions[{c_index}]"
                if not isinstance(condition, dict):
                    errors.add(spot, "must be an object")
                    continue
                check_keys(errors, spot, condition, {"kind", "description"}, {"kind", "description"})
                if not text(condition.get("kind")) or not text(condition.get("description")):
                    errors.add(spot, "kind and description must be non-empty strings")
        execution = record.get("execution")
        keys = {"attacker_perspective", "payloads", "instructions", "observed_result"}
        if not isinstance(execution, dict):
            errors.add(where, "execution must be an object")
        else:
            check_keys(errors, f"{where}.execution", execution, keys, keys)
            for key in ("attacker_perspective", "observed_result"):
                if key in execution and not text(execution[key]):
                    errors.add(f"{where}.execution", f"{key} must be a non-empty string")
            for key in ("payloads", "instructions"):
                if key in execution and (not isinstance(execution[key], list) or not execution[key]
                                         or not all(text(x) for x in execution[key])):
                    errors.add(f"{where}.execution", f"{key} must be a non-empty array of non-empty strings")
        remediation = record.get("remediation")
        if not isinstance(remediation, dict):
            errors.add(where, "remediation must be an object")
        else:
            check_keys(errors, f"{where}.remediation", remediation, {"strategy", "code_changes", "regression_test"},
                       {"strategy"})
            if not text(remediation.get("strategy")):
                errors.add(f"{where}.remediation", "strategy must be a non-empty string")
            changes = remediation.get("code_changes", [])
            if not isinstance(changes, list):
                errors.add(f"{where}.remediation", "code_changes must be an array")
            else:
                for c_index, change in enumerate(changes):
                    spot = f"{where}.remediation.code_changes[{c_index}]"
                    if not isinstance(change, dict):
                        errors.add(spot, "must be an object")
                        continue
                    check_keys(errors, spot, change, {"file", "description"}, {"file", "description"})
                    if not repo_path(change.get("file")) or not text(change.get("description")):
                        errors.add(spot, "needs a repository-relative file and a description")
        severity = record.get("severity")
        if not isinstance(severity, dict):
            errors.add(where, "severity must be an object")
        else:
            check_keys(errors, f"{where}.severity", severity, {"likelihood", "impact", "overall_severity"},
                       {"likelihood", "impact", "overall_severity"})
            check_scored(errors, f"{where}.severity.likelihood", severity.get("likelihood"), SCORES)
            impact = check_scored(errors, f"{where}.severity.impact", severity.get("impact"), SCORES)
            overall = severity.get("overall_severity")
            if overall not in OVERALL:
                errors.add(f"{where}.severity", f"overall_severity must be one of {', '.join(OVERALL)}")
            elif impact in OVERALL_LIMIT and OVERALL.index(overall) > OVERALL.index(OVERALL_LIMIT[impact]):
                errors.add(f"{where}.severity", f"overall_severity {overall} exceeds the demonstrated impact {impact}")
        check_scored(errors, f"{where}.confidence", record.get("confidence"), SCORES)

    if verdict == "needs_validation":
        blockers = record.get("blockers")
        if not isinstance(blockers, list) or not blockers or not all(text(b) for b in blockers):
            errors.add(where, "blockers must be a non-empty array of non-empty strings")
        plan = record.get("validation_plan")
        if not isinstance(plan, dict):
            errors.add(where, "validation_plan must be an object")
        else:
            check_keys(errors, f"{where}.validation_plan", plan, {"local", "deployment"}, set())
            for key, value in plan.items():
                if key in ("local", "deployment") and not text(value):
                    errors.add(f"{where}.validation_plan", f"{key} must be a non-empty string when present")
            if not any(text(plan.get(key)) for key in ("local", "deployment")):
                errors.add(f"{where}.validation_plan", "needs a local or a deployment step")
    return fingerprint


def validate_findings(data: Any) -> Errors:
    errors = Errors()
    if not isinstance(data, list):
        errors.add("findings", "must be a JSON array")
        return errors
    if len(data) > MAX_FINDINGS:
        errors.add("findings", f"more than {MAX_FINDINGS} records")
        return errors
    fingerprints: List[str] = []
    for index, record in enumerate(data):
        fingerprint = check_finding(errors, index, record)
        if fingerprint is not None:
            fingerprints.append(fingerprint)
    seen: Set[str] = set()
    for fingerprint in fingerprints:
        if fingerprint in seen:
            errors.add("findings", f"fingerprint {fingerprint} appears more than once")
        seen.add(fingerprint)
    if fingerprints != sorted(fingerprints):
        errors.add("findings", "records must be sorted by fingerprint")
    return errors


# MARK: - Ledger


def canonical_ref_ok(value: Any) -> bool:
    if not isinstance(value, str) or value != value.strip() or not value.strip():
        return False
    if unicodedata.normalize("NFC", value) != value:
        return False
    for char in value:
        category = unicodedata.category(char)
        if category in ("Cc", "Cf", "Zl", "Zp", "Cs", "Co", "Cn"):
            return False
    return True


def encode_ref(value: str) -> str:
    safe = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    return "".join(chr(b) if b in safe else f"%{b:02X}" for b in value.encode("utf-8"))


def derive_id(refs: Dict[str, Any]) -> str:
    parts = [refs["surface"], refs["boundary"], refs["subsystem"], refs["attack_class"]]
    if "lifecycle" in refs:
        parts.append(refs["lifecycle"])
    return "::".join(encode_ref(p) for p in parts)


def check_evidence_state(errors: Errors, where: str, unit: Dict[str, Any], status: Any) -> None:
    owner = unit.get("agent_id")
    paths = unit.get("reviewed_paths")
    checks = unit.get("local_checks")
    prints = unit.get("result_fingerprints")
    unresolved = unit.get("unresolved")
    for key, value in (("reviewed_paths", paths), ("local_checks", checks), ("result_fingerprints", prints),
                       ("unresolved", unresolved)):
        if not isinstance(value, list):
            errors.add(where, f"{key} must be an array")
            return
    if status in ("planned", "not_applicable", "out_of_scope", "deferred"):
        if owner is not None or paths or checks or prints:
            errors.add(where, f"a {status} unit has no owner and no evidence")
        if status == "planned" and unresolved:
            errors.add(where, "a planned unit has nothing unresolved")
        if status != "planned" and not unresolved:
            errors.add(where, f"a {status} unit states its reason in unresolved")
    elif status == "in_progress":
        if not agent_id(owner):
            errors.add(where, "an in_progress unit has a valid agent_id")
        if paths or checks or prints or unresolved:
            errors.add(where, "an in_progress unit has no evidence yet")
    elif status in ARCHIVABLE:
        if not agent_id(owner):
            errors.add(where, f"a {status} unit has a valid agent_id")
        if not paths or not checks:
            errors.add(where, f"a {status} unit has reviewed_paths and local_checks")
        if status == "candidate" and not prints:
            errors.add(where, "a candidate unit links at least one fingerprint")
        if status != "candidate" and prints:
            errors.add(where, f"a {status} unit links no fingerprint")
        if status == "blocked" and not unresolved:
            errors.add(where, "a blocked unit states what is unresolved")
        if status == "covered" and unresolved:
            errors.add(where, "a covered unit has nothing unresolved")
    for p in paths:
        if not repo_path(p):
            errors.add(where, f"reviewed path {p!r} is not repository-relative")
    for fingerprint in prints:
        if not isinstance(fingerprint, str) or not FINGERPRINT_RE.match(fingerprint):
            errors.add(where, f"fingerprint {fingerprint!r} is not valid")
    union: Set[str] = set()
    for c_index, check in enumerate(checks):
        spot = f"{where}.local_checks[{c_index}]"
        if not isinstance(check, dict):
            errors.add(spot, "must be an object")
            continue
        keys = {"agent_id", "reviewed_paths", "invariant", "method", "result", "artifact"}
        check_keys(errors, spot, check, keys, keys)
        if not agent_id(check.get("agent_id")):
            errors.add(spot, "agent_id must be a lowercase id")
        check_paths = check.get("reviewed_paths")
        if not isinstance(check_paths, list) or not check_paths or not all(repo_path(p) for p in check_paths):
            errors.add(spot, "reviewed_paths must be a non-empty array of repository-relative paths")
        else:
            union.update(check_paths)
        for key in ("invariant", "result"):
            if not text(check.get(key)):
                errors.add(spot, f"{key} must be a non-empty string")
        method, artifact = check.get("method"), check.get("artifact")
        if method == "source":
            if artifact is not None:
                errors.add(spot, "a source check has artifact null")
        elif method == "local":
            prefix = f"agents/{check.get('agent_id')}/artifacts/"
            if not isinstance(artifact, str) or not artifact.startswith(prefix) or len(artifact) == len(prefix) \
                    or not repo_path(artifact):
                errors.add(spot, f"a local check names one file under {prefix}")
        else:
            errors.add(spot, "method must be source or local")
    if checks and isinstance(paths, list) and set(paths) != union:
        errors.add(where, "reviewed_paths must equal the union of the checks' reviewed_paths")


def check_unit(errors: Errors, index: int, unit: Any) -> Optional[str]:
    where = f"ledger[{index}]"
    if not isinstance(unit, dict):
        errors.add(where, "must be an object")
        return None
    check_keys(errors, where, unit, UNIT_FIELDS, UNIT_REQUIRED)
    refs = unit.get("canonical_refs")
    coverage_id = unit.get("coverage_id")
    keys = {"surface", "boundary", "subsystem", "attack_class"}
    if not isinstance(refs, dict):
        errors.add(where, "canonical_refs must be an object")
    else:
        check_keys(errors, f"{where}.canonical_refs", refs, keys | {"lifecycle"}, keys)
        if all(canonical_ref_ok(refs.get(k)) for k in keys) and ("lifecycle" not in refs or canonical_ref_ok(refs["lifecycle"])):
            if coverage_id != derive_id(refs):
                errors.add(where, f"coverage_id must be {derive_id(refs)!r}")
        else:
            errors.add(f"{where}.canonical_refs", "each reference is NFC text with visible content and no control "
                       "characters or surrounding whitespace")
        if ("lifecycle" in refs) != ("lifecycle" in unit):
            errors.add(where, "lifecycle is in both canonical_refs and the unit, or in neither")
    for key in ("surface", "boundary", "subsystem", "attack_class"):
        if key in unit and not text(unit[key]):
            errors.add(where, f"{key} must be a non-empty label")
    starting = unit.get("starting_paths")
    if not isinstance(starting, list) or not all(repo_path(p) for p in starting):
        errors.add(where, "starting_paths must be repository-relative paths")
    if unit.get("prior_status") not in PRIOR:
        errors.add(where, "prior_status is not a known value")
    block = unit.get("attack_class_block")
    if block is not None and not text(block):
        errors.add(where, "attack_class_block is a block reference or null")
    if not isinstance(unit.get("selected_blocks"), list) or not all(text(b) for b in unit.get("selected_blocks", [])):
        errors.add(where, "selected_blocks must be an array of block references")
    excluded = unit.get("excluded_blocks")
    if not isinstance(excluded, list) or not all(isinstance(e, dict) and text(e.get("block")) and text(e.get("reason"))
                                                 for e in excluded):
        errors.add(where, "excluded_blocks entries need a block and a reason")
    wave = unit.get("wave")
    if not isinstance(wave, int) or isinstance(wave, bool) or wave < 1:
        errors.add(where, "wave must be an integer of at least 1")
        wave = None
    status = unit.get("status")
    if status not in STATUSES:
        errors.add(where, "status is not a known value")
    else:
        check_evidence_state(errors, where, unit, status)
    attempts = unit.get("attempts")
    if not isinstance(attempts, list):
        errors.add(where, "attempts must be an array")
    else:
        last = 0
        for a_index, attempt in enumerate(attempts):
            spot = f"{where}.attempts[{a_index}]"
            if not isinstance(attempt, dict):
                errors.add(spot, "must be an object")
                continue
            allowed = {"wave", "status", "agent_id", "reviewed_paths", "local_checks", "result_fingerprints",
                       "unresolved", "reassignment_reason"}
            check_keys(errors, spot, attempt, allowed, allowed)
            if attempt.get("status") not in ARCHIVABLE:
                errors.add(spot, "only blocked, covered, or candidate attempts are archived")
            else:
                check_evidence_state(errors, spot, attempt, attempt.get("status"))
            a_wave = attempt.get("wave")
            if not isinstance(a_wave, int) or a_wave <= last or (wave is not None and a_wave >= wave):
                errors.add(spot, "attempt waves increase and stay below the unit's wave")
            else:
                last = a_wave
            if not text(attempt.get("reassignment_reason")):
                errors.add(spot, "reassignment_reason must be a non-empty string")
    return coverage_id if isinstance(coverage_id, str) else None


def validate_ledger(data: Any) -> Errors:
    errors = Errors()
    if not isinstance(data, list):
        errors.add("ledger", "must be a JSON array")
        return errors
    if len(data) > MAX_UNITS:
        errors.add("ledger", f"more than {MAX_UNITS} units")
        return errors
    ids: List[str] = []
    tuples: Dict[tuple, str] = {}
    for index, unit in enumerate(data):
        coverage_id = check_unit(errors, index, unit)
        if coverage_id is None:
            continue
        ids.append(coverage_id)
        labels = tuple(unit.get(k) for k in ("surface", "boundary", "subsystem", "attack_class", "lifecycle"))
        if labels in tuples and tuples[labels] != coverage_id:
            errors.add(f"ledger[{index}]", f"same unit as {tuples[labels]} under another coverage_id")
        tuples.setdefault(labels, coverage_id)
    seen: Set[str] = set()
    for coverage_id in ids:
        if coverage_id in seen:
            errors.add("ledger", f"coverage_id {coverage_id} appears more than once")
        seen.add(coverage_id)
    if ids != sorted(ids):
        errors.add("ledger", "units must be sorted by coverage_id")
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in ("findings", "ledger"):
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    kind, path = args
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
    except OSError as error:
        print(f"validate_audit: cannot read {path}: {error.strerror or error}", file=sys.stderr)
        return 2
    if len(raw) > MAX_BYTES:
        print(f"validate_audit: {path} is larger than {MAX_BYTES} bytes", file=sys.stderr)
        return 1
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as error:
        print(f"validate_audit: {path} is not JSON: {error}", file=sys.stderr)
        return 1
    if depth(data) > MAX_DEPTH:
        print(f"validate_audit: {path} nests deeper than {MAX_DEPTH} levels", file=sys.stderr)
        return 1
    errors = validate_findings(data) if kind == "findings" else validate_ledger(data)
    if errors:
        for item in errors.items[:MAX_ERRORS]:
            print(item, file=sys.stderr)
        if len(errors.items) > MAX_ERRORS:
            print(f"... and {len(errors.items) - MAX_ERRORS} more", file=sys.stderr)
        return 1
    count = len(data)
    print(f"{path}: valid {kind} file ({count} {'records' if kind == 'findings' else 'units'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
