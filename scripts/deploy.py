#!/usr/bin/env python3
"""Idempotent Sigma -> Splunk saved-search deployment (Pattern B).

Converts rules with sigma-cli, then upserts each as a Splunk saved search
keyed by the Sigma rule UUID (update-or-create; deprecated rules deleted).

Adapt deploy_rule()/delete_rule() for Sentinel (az rest against the
Analytics Rules API) or Elastic (Detection Engine API) as needed.

Env: SIEM_URL (e.g. https://splunk.example.com:8089), SIEM_TOKEN
Usage: python scripts/deploy.py --env staging --rules rules/ --pipeline pipelines/prod_pipeline.yml
"""
import argparse
import os
import pathlib
import subprocess
import sys

import requests
import yaml

# status -> behavior per environment
DEPLOY_MATRIX = {
    "staging": {"experimental": "enabled", "test": "enabled", "stable": "enabled"},
    "production": {"experimental": "skip", "test": "audit", "stable": "enabled"},
}
CRON_BY_LEVEL = {
    "critical": "*/5 * * * *",
    "high": "*/15 * * * *",
    "medium": "*/30 * * * *",
    "low": "0 * * * *",
    "informational": "0 */4 * * *",
}


def convert(rule_path: pathlib.Path, pipeline: str) -> str:
    result = subprocess.run(
        ["sigma", "convert", "-t", "splunk", "-p", pipeline, str(rule_path)],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def deploy_rule(base: str, token: str, rule: dict, spl: str, mode: str) -> None:
    """Upsert saved search named by rule UUID. mode: enabled|audit."""
    name = f"DaC - {rule['id']}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "search": spl,
        "description": f"{rule['title']} | {rule['description']}",
        "is_scheduled": "1",
        "cron_schedule": CRON_BY_LEVEL.get(rule["level"], "*/30 * * * *"),
        "dispatch.earliest_time": "-35m",
        "dispatch.latest_time": "now",
        # audit mode: schedule the search but do not fire alert actions
        "alert.track": "0" if mode == "audit" else "1",
        "disabled": "0",
    }
    url = f"{base}/servicesNS/nobody/search/saved/searches/{requests.utils.quote(name, safe='')}"
    r = requests.get(url, headers=headers, params={"output_mode": "json"}, verify=True)
    if r.status_code == 404:
        payload["name"] = name
        r = requests.post(f"{base}/servicesNS/nobody/search/saved/searches",
                          headers=headers, data=payload, verify=True)
    else:
        r = requests.post(url, headers=headers, data=payload, verify=True)
    r.raise_for_status()
    print(f"  upserted [{mode}] {name}")


def delete_rule(base: str, token: str, rule_id: str) -> None:
    name = f"DaC - {rule_id}"
    url = f"{base}/servicesNS/nobody/search/saved/searches/{requests.utils.quote(name, safe='')}"
    r = requests.delete(url, headers={"Authorization": f"Bearer {token}"}, verify=True)
    if r.status_code not in (200, 404):
        r.raise_for_status()
    print(f"  removed {name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", choices=["staging", "production"], required=True)
    ap.add_argument("--rules", default="rules/")
    ap.add_argument("--deprecated", default="rules-deprecated/")
    ap.add_argument("--pipeline", default="pipelines/prod_pipeline.yml")
    args = ap.parse_args()

    base, token = os.environ["SIEM_URL"], os.environ["SIEM_TOKEN"]
    matrix = DEPLOY_MATRIX[args.env]
    failures = 0

    for path in sorted(pathlib.Path(args.rules).rglob("*.yml")):
        rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        action = matrix.get(rule["status"], "skip")
        if action == "skip":
            print(f"  skip [{rule['status']}] {rule['title']}")
            continue
        try:
            spl = convert(path, args.pipeline)
            deploy_rule(base, token, rule, spl, mode=action)
        except Exception as e:  # keep deploying remaining rules; fail the job at the end
            print(f"::error::{path}: {e}")
            failures += 1

    dep_dir = pathlib.Path(args.deprecated)
    if dep_dir.exists():
        for path in sorted(dep_dir.rglob("*.yml")):
            rule = yaml.safe_load(path.read_text(encoding="utf-8"))
            try:
                delete_rule(base, token, rule["id"])
            except Exception as e:
                print(f"::error::{path}: {e}")
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
