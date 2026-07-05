#!/usr/bin/env python3
"""CI gate: enforce org metadata policy on all Sigma rules.

Usage: python scripts/lint_metadata.py rules/
Exits 1 with a list of violations if any rule fails policy.
"""
import pathlib
import sys
import uuid

import yaml

REQUIRED = [
    "title", "id", "status", "description", "author",
    "date", "tags", "logsource", "detection", "falsepositives", "level",
]
STATUSES = {"experimental", "test", "stable", "deprecated"}
LEVELS = {"informational", "low", "medium", "high", "critical"}
MAX_TITLE = 110


def lint(rules_dir: str) -> list[str]:
    errors = []
    paths = sorted(pathlib.Path(rules_dir).rglob("*.yml"))
    if not paths:
        return [f"{rules_dir}: no .yml rules found"]
    for path in paths:
        try:
            rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            errors.append(f"{path}: unparseable YAML: {e}")
            continue
        if not isinstance(rule, dict):
            errors.append(f"{path}: not a mapping")
            continue
        for field in REQUIRED:
            if field not in rule:
                errors.append(f"{path}: missing required field '{field}'")
        if len(str(rule.get("title", ""))) > MAX_TITLE:
            errors.append(f"{path}: title exceeds {MAX_TITLE} chars")
        try:
            uuid.UUID(str(rule.get("id")))
        except (ValueError, AttributeError):
            errors.append(f"{path}: 'id' is not a valid UUID")
        if rule.get("status") not in STATUSES:
            errors.append(f"{path}: invalid status '{rule.get('status')}'")
        if rule.get("level") not in LEVELS:
            errors.append(f"{path}: invalid level '{rule.get('level')}'")
        tags = rule.get("tags") or []
        if not any(str(t).startswith("attack.t") for t in tags):
            errors.append(f"{path}: missing ATT&CK technique tag (attack.tXXXX)")
        if not any(str(t).startswith("attack.") and not str(t).startswith("attack.t")
                   for t in tags):
            errors.append(f"{path}: missing ATT&CK tactic tag (e.g. attack.persistence)")
    return errors


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    problems = lint(sys.argv[1])
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("Metadata policy: PASS")
