# Navi Marketing — Content Ops

Claude-powered content workflows (page audits, rewrites, metadata, internal links, content briefs) for the Navi marketing team.

## What this is

You ask Claude (in Cowork) to do content work. Claude runs the workflows, reads the latest brand context from your shared Google Drive folder, and hands you back the finished output as a link you can save anywhere. You don't touch terminals or files in this repo.

## What you need before you start

- Either **Cowork** (Claude desktop app) or **Claude Code** (CLI) installed and signed in
- Python 3.10+ on your Mac (the installer will check)
- An **Anthropic** API key ([get one](https://console.anthropic.com/settings/keys))
- A **Firecrawl** API key ([get one](https://firecrawl.dev))
- An **OpenAI** API key ([get one](https://platform.openai.com/api-keys)) — only for the internal-link workflow; skip if you don't plan to use it
- The Google Drive MCP connector enabled in Cowork (so Claude can read the shared brand docs)

## One-time setup

Clone this repo somewhere on your Mac. Then:

1. Open Terminal, `cd` into the folder, and run: **`bash start.sh`**
2. On first run, it'll walk you through Python setup and ask for your API keys. Paste them when prompted.
3. Once setup finishes, it starts the workflow server. Leave the Terminal window open.
4. In Cowork, ask Claude to connect to the repo folder (or drag the folder in). Claude Code users can skip this — it's already connected.

## Every work session

1. Open Terminal, `cd` into the folder, run **`bash start.sh`**. Leave it open.
2. Talk to Claude. Examples:

- "Audit this page: https://www.yournavi.com/posts/best-prepaid-unlimited-plans"
- "Give me refresh recommendations for [URL]"
- "Write a content brief for 'best eSIM plans for international travel'"
- "Find internal linking opportunities for [URL]"

Claude will:

1. Pull the latest brand artifacts from Google Drive.
2. Call the workflow server running on your Mac (that Terminal window from step 1).
3. Run the workflow (usually 2–5 minutes, up to ~8 for a full article draft).
4. **Show you the finished output as a link in chat.** Outputs also land in `outputs/` on your Mac, so you can open them in Finder anytime.

## Where brand artifacts live

**In Google Drive, not in this repo.**

Folder: https://drive.google.com/drive/folders/1LLmvyrvzc3JTS_FSqlcmxQcSTPaJ_C0f

The six source-of-truth docs:

- `workflow-context`
- `company-context`
- `writing-style`
- `audience-personas`
- `brand-guardrails`
- `products-and-services`

When you want to update voice, personas, guardrails, or any other brand context, edit the Doc directly in Drive. The next workflow Claude runs will pick up your changes automatically.

**Do not edit files in the local `artifacts/` folder.** They get overwritten every run.

## Saving outputs

Every workflow produces at least one Markdown file (some produce two — e.g., internal-link recommendations produces both a report and a linked version). Files land in `outputs/` in this repo on your Mac. Claude will also share a link in chat so you can open it immediately.

## What if something breaks

**Claude says "connection refused" or "can't reach the server"**
Your Terminal window with `bash start.sh` isn't running. Open Terminal, `cd` into the repo, run `bash start.sh`, then ask Claude to try again.

**Claude says it can't find the brand artifacts**
The Google Drive connector probably isn't connected in Cowork. Open Cowork settings, connect Google Drive, and ask Claude to try again.

**Workflow says it failed and mentions an API key**
Your `.env` file is missing a key or has a typo. Open `.env` in any editor and fix it, then restart `bash start.sh`.

**Output looks generic or off-brand**
Artifacts probably weren't fetched before the workflow ran. Ask Claude: "Re-fetch artifacts from Drive and run this again."

**Something else**
Ask Claude. It has access to the server logs (in the Terminal window) and can diagnose most issues.

## For whoever maintains the code

See `CLAUDE.md` for the technical overview — architecture, endpoints, how Claude orchestrates runs, how to add new workflows.
