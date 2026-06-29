# Verify Local Artifacts (shared prerequisite)

Every workflow in this repo reads brand artifacts from the local `artifacts/` folder. That folder is **gitignored** and is managed manually on each user's machine.

> Google Drive sync is currently **disabled** for Navi's workspace. Do not call the Google Drive MCP — just use whatever is already in `artifacts/`.

Do this step **before** calling any workflow endpoint.

## Expected artifact files

Claude should confirm these six files exist under `artifacts/` (project root):

- `artifacts/workflow-context.md`
- `artifacts/company-context.md`
- `artifacts/writing-style.md`
- `artifacts/audience-personas.md`
- `artifacts/brand-guardrails.md`
- `artifacts/products-and-services.md`

## Optional artifacts (recommended, not required)

These two are picked up automatically when present and improve accuracy. The workflows run
fine without them — do **not** block a run if they're missing.

- `artifacts/plans-and-pricing.md` — current plan names and prices. Without it, the
  workflows fall back to the model's training data, which is often a year+ out of date.
  Template + format: `templates/artifacts/plans-and-pricing.template.md`.
- `artifacts/recommendation-guardrails.md` — the team's "stop telling me that" suppression
  list. Append a rule whenever a kind of recommendation keeps being unhelpful (or ask Claude
  to). Template: `templates/artifacts/recommendation-guardrails.template.md`.

## Verify steps

1. `ls artifacts/` and confirm the six expected files are present.
2. If any of the **six required** files are missing or empty, **stop and tell the user** — they'll need to drop the file(s) into `artifacts/` manually. Output quality degrades significantly without brand context.
3. The two optional artifacts above are a bonus — note if they're absent but proceed regardless.
4. If all six required files are present, proceed with the workflow. No re-fetching is needed between runs.

## What not to do

- Do not call the Google Drive MCP to fetch or refresh these files. Drive sync is disabled for this project.
- Do not commit anything from `artifacts/` to git. The `.gitignore` excludes it, but don't `git add -f` it. The repo is public.
- Do not edit artifact files locally unless the user asks — authoring still happens outside this repo.
