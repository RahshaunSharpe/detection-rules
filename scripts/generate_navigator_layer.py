#!/usr/bin/env python3
"""Generate a MITRE ATT&CK Navigator layer from stable Sigma rules.

Usage: python scripts/generate_navigator_layer.py rules/ coverage/navigator_layer.json
"""
import json
import pathlib
import sys

import yaml


def main(rules_dir: str, out_path: str) -> None:
    techniques: dict[str, int] = {}
    for path in pathlib.Path(rules_dir).rglob("*.yml"):
        rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(rule, dict) or rule.get("status") != "stable":
            continue
        for tag in rule.get("tags") or []:
            tag = str(tag)
            if tag.startswith("attack.t"):
                tid = tag.split(".", 1)[1].upper()  # "t1547.001" -> "T1547.001"
                techniques[tid] = techniques.get(tid, 0) + 1

    layer = {
        "name": "Detection Coverage (stable rules)",
        "domain": "enterprise-attack",
        "versions": {"layer": "4.5", "navigator": "5.0"},
        "description": "Auto-generated from detection-rules repo",
        "techniques": [
            {"techniqueID": tid, "score": count, "comment": f"{count} stable rule(s)"}
            for tid, count in sorted(techniques.items())
        ],
        "gradient": {"colors": ["#ffe766", "#8ec843"], "minValue": 0, "maxValue": 5},
    }
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(layer, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({len(techniques)} techniques)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
