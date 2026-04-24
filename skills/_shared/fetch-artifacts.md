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

## Verify steps

1. `ls artifacts/` and confirm the six expected files are present.
2. If any are missing or empty, **stop and tell the user** — they'll need to drop the file(s) into `artifacts/` manually. Output quality degrades significantly without brand context.
3. If all six are present, proceed with the workflow. No re-fetching is needed between runs.

## What not to do

- Do not call the Google Drive MCP to fetch or refresh these files. Drive sync is disabled for this project.
- Do not commit anything from `artifacts/` to git. The `.gitignore` excludes it, but don't `git add -f` it. The repo is public.
- Do not edit artifact files locally unless the user asks — authoring still happens outside this repo.
