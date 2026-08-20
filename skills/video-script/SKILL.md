# Video Script Skill

Generates 2–3 short-form video script variations (distinct angles and hooks) from a source article, local draft, or written brief — in the voice of either the **Navi** or **Save On Wireless** brand. Voice rules come from the brand's video style guide artifact, distilled from the team's produced-script corpus.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. In addition to the six standard files, this workflow uses the **video style guides**:
   - `artifacts/video-style-guide.md` (Navi)
   - `artifacts/video-style-guide-save-on-wireless.md` (Save On Wireless)

   If the guide for the requested brand is missing, warn the user — the workflow still runs, but scripts lose the brand's voice contract. Templates live in `templates/artifacts/video-style-guide.template.md`.
3. **GSC (optional).** Only useful when the source is a `yournavi.com` article: pull the page's top queries (last 90 days) so scripts can lean on what viewers actually search for. See `skills/_shared/fetch-gsc.md`. Skip for Save On Wireless and for brief-only runs.

## What to Ask the User

1. **Brand** (required): "Navi or Save On Wireless?" — defaults to Navi if unspecified. The two brands have different voices, hooks, and CTAs; never mix them.
2. **Source** (required, one of):
   - **URL** — an article to base the scripts on (e.g., a `yournavi.com/posts/...` piece)
   - **source_path** — a local Markdown/text file
   - **notes** — a written brief pasted straight into the request
3. **Topic** (required): Short label, e.g., "TCO explainer".
4. **Script count** (optional): 2 or 3. Defaults to 3.
5. **Audience / notes** (optional): extra direction, e.g., "focus on families" or "deal-comparison video, not an explainer".

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
curl -sS -X POST http://localhost:8100/api/video_script \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "<short label>" \
        --arg url "<source article URL>" \
        --arg brand "navi" \
        --arg notes "<user direction>" \
        '{topic: $topic, url: $url, brand: $brand, notes: $notes, script_count: 3}')"
```

For a brief-only run (no URL), pass the brief text as `notes` and omit `url`.

Expected runtime: **2–4 minutes**. Poll every 15–30s.

## What the Workflow Does (7 steps)

1. Get source content (URL scrape, local file, or notes-as-brief)
2. Load artifacts + the brand's video style guide
3. Distill source into facts, numbers, and catches (Haiku)
4. Pick N distinct angles mapped to the style guide's hook patterns (Sonnet)
5. Write N full voiceover scripts with `[HOOK]/[BODY]/[LIMITATIONS]/[CTA]` beats (Opus)
6. Compliance review — brand voice, guardrails, unsupported facts, missing disclosures (Sonnet)
7. Final assembly — angles, review notes, and scripts in one report

## Outputs

- `outputs/video_script/<timestamp>-<slug>.md` — the report (angles → compliance review → scripts)
- `outputs/video_script/<timestamp>-<slug>.json` — sidecar with intermediate step outputs
- `tracking/runs.md` — run log entry

## Presenting Results

Lead with the scripts — that's the deliverable. Then surface the compliance review: call out any `needs_edits` verdicts, `[CONFIRM: ...]` markers (facts the source didn't provide), and human-review items. Every script is a first draft for a human editor, not a publish-ready asset — especially Navi short-form, which is an inferred format (Navi's corpus is long-form; see the note in `artifacts/video-style-guide.md`).

## The feedback loop

If the workflow keeps making the same unhelpful move (e.g., always picking the same angle, or flagging something the team doesn't care about), add a rule to `artifacts/recommendation-guardrails.md` — it's injected into the generation and review prompts. For voice corrections, edit the brand's video style guide artifact directly; it is the voice contract.
