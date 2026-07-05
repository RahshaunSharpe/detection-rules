# SOP-DE-001: Detection-as-Code Pipeline — Standard Operating Procedure

| Field | Value |
|---|---|
| Document ID | SOP-DE-001 |
| Version | 1.0 |
| Effective date | 2026-07-04 |
| Owner | Detection Engineering Lead |
| Review cycle | Quarterly |
| Companion doc | Detection-as-Code Implementation Guide |

---

## 1. Purpose

Define the repeatable procedures for creating, reviewing, testing, deploying, tuning, and retiring detection rules through the GitHub-based Detection-as-Code (DaC) pipeline. Anyone following this SOP should be able to stand up and operate the pipeline end-to-end.

## 2. Scope

Applies to all Sigma detection rules in the `detection-rules` repository and all SIEM/EDR platforms it deploys to. Out of scope: SIEM infrastructure administration, log source onboarding, incident response.

## 3. Roles & Responsibilities

| Role | Responsibilities |
|---|---|
| Detection Engineer (DE) | Authors rules, writes fixtures, opens PRs, tunes rules |
| Detection Reviewer (CODEOWNER) | Peer-reviews PRs against the review checklist (§8) |
| Detection Lead | Approves production deployments, owns pipeline config, quarterly review |
| SOC Analysts | Report FPs/gaps via GitHub Issues using the issue template |

## 4. Prerequisites (One-Time Pipeline Setup)

Perform once per organization. Estimated time: 1–2 days.

1. Create a private GitHub repository `detection-rules` using the structure in the Implementation Guide §3.
2. Configure branch protection on `main`: PR required, ≥1 CODEOWNER approval, required status check `validate`, no force pushes, no direct pushes.
3. Create `.github/CODEOWNERS` mapping `/rules/` to the detection-engineers team and `/pipelines/`, `/.github/`, deploy config to detection leads.
4. Create GitHub Environments `staging` (no gate) and `production` (required reviewer: Detection Lead). Store SIEM credentials as environment-scoped secrets; prefer OIDC federation over static tokens where supported.
5. Commit the CI workflow (`validate.yml`), metadata linter, and deploy workflow (`deploy.yml`) from the Implementation Guide.
6. Build the pySigma processing pipeline (`pipelines/prod_pipeline.yml`) with field mappings for your environment. Verify by converting a known rule and running the output manually in the SIEM.
7. Run one end-to-end test: trivial rule → PR → CI green → merge → staging deploy → prod approval → verify rule exists in SIEM. Document the run in the repo wiki.

**Setup is complete when:** a rule can go from PR to production without anyone touching the SIEM console.

## 5. Procedure A — Create a New Detection Rule

**Trigger:** new threat intel, red team finding, gap analysis, or incident lessons-learned.
**Estimated time:** 1–4 hours per rule.

1. Create a GitHub Issue describing the detection need; tag with ATT&CK technique.
2. Branch from `main`: `git checkout -b rule/<short-name>`.
3. Author the rule in `rules/<tactic>/<name>.yml` following the metadata policy (all required fields; new UUIDv4 for `id`; `status: experimental`).
4. Validate locally:
   ```bash
   yamllint rules/ && sigma check rules/ && python scripts/lint_metadata.py rules/
   sigma convert -t <backend> -p pipelines/prod_pipeline.yml rules/<tactic>/<name>.yml
   ```
5. Run the converted query manually against 7–30 days of historical data in the SIEM. Record hit count and FP assessment in the PR description.
6. Add at least one matching and one non-matching fixture to `tests/fixtures/<rule-id>/` (if fixture testing is enabled).
7. Open a PR using the template; link the Issue. CI must pass; request CODEOWNER review.
8. Address review feedback via commits (never force-push over review history).
9. On merge, the pipeline deploys to staging automatically. Confirm the rule appears in staging.

## 6. Procedure B — Promote a Rule (experimental → test → stable)

**Trigger:** rule has baked in the current stage for the minimum soak period.

| Transition | Minimum soak | Promotion criteria |
|---|---|---|
| experimental → test | 7 days in staging | Fires correctly; FP volume understood |
| test → stable | 14 days in prod (non-alerting) | FP rate acceptable to SOC; triage guidance written |

1. Review alert volume and FP data for the soak period; attach numbers to the PR.
2. Open a PR changing only `status:` and `modified:` fields (plus any tuning filters).
3. On merge to `stable`, Detection Lead approves the production deployment gate.
4. Notify SOC of the new alerting rule with triage guidance.

## 7. Procedure C — Tune a Rule (False-Positive Reduction)

**Trigger:** SOC files an FP Issue.

1. Reproduce: confirm the FP against the offending events.
2. Prefer a filter in `filters/` over editing rule logic (keeps upstream/community rules diffable). Edit rule logic only when the detection itself is wrong.
3. Update `modified:` date. Open PR; link the FP Issue; include before/after hit counts from historical search.
4. Standard review + merge + auto-deploy. Close the Issue with a summary.

**SLA guidance:** critical-severity noisy rule = same business day (use Procedure E if needed); otherwise within 5 business days.

## 8. Rule Review Checklist (Reviewer Must Verify)

- [ ] All required metadata fields present; `id` is a new UUID; ATT&CK tactic + technique tags present
- [ ] Detection logic matches the described threat behavior (not just an IOC that will age out)
- [ ] Log source exists in our environment and field names match the processing pipeline
- [ ] Historical search evidence attached (hit counts, FP assessment)
- [ ] `falsepositives` section is honest and specific
- [ ] `level` is justified relative to confidence + impact
- [ ] Fixtures added/updated (if applicable)
- [ ] No secrets, internal hostnames, or sensitive data leaked in the rule or PR
- [ ] CI green

## 9. Procedure D — Deprecate a Rule

**Trigger:** superseded rule, retired log source, or permanently unacceptable FP rate.

1. Open PR: set `status: deprecated`, add `related:` entry pointing to any replacement rule ID, move file to `rules-deprecated/`.
2. Deployment job removes/disables the rule in the SIEM (by rule UUID).
3. Never delete the file or reuse the UUID — audit history must survive.

## 10. Procedure E — Emergency / Break-Glass Deployment

**Trigger:** active incident requires an immediate detection, or a rule is causing SIEM performance harm.

1. Branch `hotfix/<name>`; author or modify the rule.
2. Open PR titled `[EMERGENCY]`; ping the Detection Lead directly.
3. One Lead approval satisfies review; CI must still pass (do not bypass `validate`).
4. Lead approves the production gate immediately after staging deploy.
5. **Console edits are prohibited even in emergencies.** If the SIEM console was touched during an incident, file a drift Issue and reconcile to Git within 24 hours.
6. Post-incident: within 3 business days, follow up with a normal PR adding fixtures, references, and full documentation.

## 11. Procedure F — Rollback

1. Identify the offending commit: `git log --oneline rules/`.
2. `git revert <commit>` on a branch; open PR titled `[ROLLBACK]`.
3. Expedited single-approval review; merge; pipeline redeploys previous state.
4. File an Issue documenting root cause.

## 12. Maintenance Cadence

| Frequency | Activity | Owner |
|---|---|---|
| Weekly | Triage FP/gap Issues; review coverage layer diff | DE on rotation |
| Monthly | Review `experimental`/`test` rules for promotion or kill | Detection Lead |
| Monthly | Sync review of new SigmaHQ community rules worth importing | DE on rotation |
| Quarterly | Metrics review: lead time, FP rate, coverage delta; SOP review | Detection Lead |
| Quarterly | Rotate SIEM credentials / verify OIDC config; dependency updates (sigma-cli, backends) | Detection Lead |

## 13. Metrics (Reported Quarterly)

Commit-to-production lead time; rules by status; FP rate per rule (top 10 noisiest); ATT&CK technique coverage count and delta; number of emergency deployments; drift incidents (target: 0).

## 14. Revision History

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-07-04 | SDOGEneral | Initial release |
