# artifacts/

**This folder is populated at runtime. Do not commit files here.**

Brand artifacts (writing style, audience personas, guardrails, etc.) live in Google Drive:

https://drive.google.com/drive/folders/1LLmvyrvzc3JTS_FSqlcmxQcSTPaJ_C0f

## How it works

Before every workflow run, Claude fetches the latest artifact docs from Drive via the Google Drive MCP connector and writes them to this folder as `.md` files. The Python workflows read them from disk exactly like they would any local file.

This means:
- Drive is the source of truth for brand artifacts.
- Edits happen in Drive, not in this repo.
- This folder is gitignored. Artifacts never land in git history.

## Expected files

After a fetch, you should see:

- `workflow-context.md`
- `company-context.md`
- `writing-style.md`
- `audience-personas.md`
- `brand-guardrails.md`
- `products-and-services.md`

If these are missing when you run a workflow, the workflow will still run but without brand context — output quality will drop. Ask Claude to fetch artifacts before trying again.
