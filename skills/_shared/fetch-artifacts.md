# Fetch Artifacts From Drive (shared prerequisite)

Every workflow in this repo reads brand artifacts from the local `artifacts/` folder. That folder is **gitignored** — artifacts live in Google Drive and must be pulled before each workflow run.

Do this step **before** calling any workflow endpoint.

## Drive location

- Folder ID: `1LLmvyrvzc3JTS_FSqlcmxQcSTPaJ_C0f`
- URL: https://drive.google.com/drive/folders/1LLmvyrvzc3JTS_FSqlcmxQcSTPaJ_C0f

## Expected artifact files

The six files Claude should sync from the Drive folder into `artifacts/`:

- `workflow-context.md`
- `company-context.md`
- `writing-style.md`
- `audience-personas.md`
- `brand-guardrails.md`
- `products-and-services.md`

Each one corresponds to a Google Doc in the Drive folder with a matching name (the Doc name doesn't need the `.md` extension).

## Fetch steps

1. **List the Drive folder** using the Google Drive MCP. Confirm the six expected docs are present.
2. **Export each doc as Markdown** via the Drive MCP's export capability (MIME type `text/markdown`, or whichever the connector exposes for Markdown export).
3. **Write each exported doc** to the local file system at the project root:
   - `artifacts/workflow-context.md`
   - `artifacts/company-context.md`
   - `artifacts/writing-style.md`
   - `artifacts/audience-personas.md`
   - `artifacts/brand-guardrails.md`
   - `artifacts/products-and-services.md`
4. **Verify all six files wrote successfully.** If any are missing or empty, stop and ask the user before running the workflow — output quality degrades significantly without brand context.

## Caching

If you've already fetched artifacts in this conversation and the user hasn't said anything suggesting they updated Drive since, you can skip the fetch on subsequent workflow calls. If you're not sure whether Drive has changed, re-fetch — it's cheap.

## What not to do

- Do not commit anything from `artifacts/` to git. The `.gitignore` excludes it, but don't `git add -f` it. The repo is public.
- Do not edit artifact files locally. Edits won't survive — they'll be overwritten on the next fetch. All authoring happens in Drive.
