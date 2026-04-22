# Navi Marketing — Content Ops

Claude-powered content workflows (page audits, rewrites, metadata, internal links, content briefs) for the Navi marketing team.

## What this is

You ask Claude (in Cowork) to do content work. Claude runs the workflows, reads the latest brand context from your shared Google Drive folder, and hands you back the finished output as a link you can save anywhere. You don't touch terminals or files in this repo.

## What you need before you start

- Cowork (the Claude desktop app) installed and signed in
- An **Anthropic** API key ([get one](https://console.anthropic.com/settings/keys))
- A **Firecrawl** API key ([get one](https://firecrawl.dev))
- An **OpenAI** API key ([get one](https://platform.openai.com/api-keys)) — only for the internal-link workflow; skip if you don't plan to use it
- The Google Drive MCP connector enabled in Cowork (so Claude can read the shared brand docs)

## One-time setup

Clone this repo somewhere on your Mac, then in Cowork:

1. Ask Claude to connect to the repo folder (or drag the folder into Cowork).
2. Paste your API keys when Claude asks for them — it'll set up the `.env` file for you.

That's it. You don't need to open Terminal.

## Every time you want to run a workflow

Just ask Claude. Examples:

- "Audit this page: https://www.yournavi.com/posts/best-prepaid-unlimited-plans"
- "Give me refresh recommendations for [URL]"
- "Write a content brief for 'best eSIM plans for international travel'"
- "Find internal linking opportunities for [URL]"

Claude will:

1. Start the workflow server if it isn't already running.
2. Pull the latest brand artifacts from Google Drive.
3. Run the workflow (usually 2–5 minutes, up to ~8 for a full article draft).
4. **Show you the finished output as a link in chat.** Click to preview, then save it wherever you want — Desktop, a Drive folder, a shared drive, etc.

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

Every workflow produces at least one Markdown file (some produce two — e.g., internal-link recommendations produces both a report and a linked version of the article). Claude will show you each one as a link in chat. Click it to preview, then save it wherever the team keeps finished work.

Outputs live on Claude's side until you save them — don't expect to find them by browsing Finder.

## What if something breaks

**Claude says it can't find the brand artifacts**
The Google Drive connector probably isn't connected in Cowork. Open Cowork settings, connect Google Drive, and ask Claude to try again.

**Workflow says it failed and mentions an API key**
Your `.env` file is missing a key or has a typo. Ask Claude to open it and fix the key.

**Output looks generic or off-brand**
Artifacts probably weren't fetched before the workflow ran. Ask Claude: "Re-fetch artifacts from Drive and run this again."

**Something else**
Ask Claude. It has access to the logs and can diagnose most issues.

## Advanced: running the server yourself

If you want workflow outputs to land directly in `~/repos/navi-marketing/outputs/` on your Mac (so you can browse them in Finder later), you can start the server yourself instead of letting Claude start it:

```
cd ~/repos/navi-marketing
python3 py/server.py
```

Leave that Terminal window open while you work. Stop it with `Ctrl+C` when you're done.

Most people don't need this — saving from the chat links works fine.

## For whoever maintains the code

See `CLAUDE.md` for the technical overview — architecture, endpoints, how Claude orchestrates runs, how to add new workflows.
