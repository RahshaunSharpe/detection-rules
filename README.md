# detection-rules

Enterprise-grade, free Detection-as-Code pipeline: Sigma rules versioned in Git,
validated in CI, deployed to the SIEM through GitHub Actions.

## How it works

```
PR (feature branch) ──► CI: yamllint + sigma check + metadata lint + conversion test
        │ CODEOWNER review + required checks
        ▼
merge to main ──► deploy to staging ──► manual approval gate ──► deploy to production
```

Rollback = `git revert` + merge. Console edits are prohibited (see SOP.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install sigma-cli yamllint pyyaml
sigma plugin install splunk        # or your backend

# validate everything
yamllint -c .yamllint.yml rules/
sigma check rules/
python scripts/lint_metadata.py rules/

# convert a rule
sigma convert -t splunk -p pipelines/prod_pipeline.yml rules/persistence/win_persistence_registry_run_key.yml
```

## Setup after pushing this repo (one time)

1. Branch protection on `main`: require PR, 1 CODEOWNER approval, required check `validate`, no direct pushes.
2. Edit `.github/CODEOWNERS` with your real teams.
3. Create Environments: `staging` (no gate) and `production` (required reviewer). Add `SIEM_URL` / `SIEM_TOKEN` secrets per environment.
4. Customize `pipelines/prod_pipeline.yml` with YOUR index names and field mappings — this is the critical step.
5. Pick a deploy pattern in `.github/workflows/deploy.yml`: `scripts/deploy.py` (Splunk REST, included) or [droid](https://github.com/certeu/droid) (`droid_config.toml`).

## Rule lifecycle

`experimental` (staging only) → `test` (prod, non-alerting) → `stable` (prod alerting) → `deprecated` (removed, archived in `rules-deprecated/`).

Full procedures: see `SOP.md`. Architecture rationale: see the implementation guide.

## Layout

| Path | Purpose |
|---|---|
| `rules/<tactic>/` | One Sigma rule per file, UUID immutable |
| `filters/` | Org-specific tuning filters (prefer over editing rule logic) |
| `pipelines/` | pySigma field/index mappings per environment |
| `scripts/` | CI linter, deploy script, ATT&CK coverage generator |
| `tests/fixtures/` | Sample matching/non-matching events per rule |
| `rules-deprecated/` | Retired rules (never delete, never reuse UUIDs) |
