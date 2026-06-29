# Recommendation Guardrails (template)

Copy this file to `artifacts/recommendation-guardrails.md`. It's the "stop telling me that"
list — a running record of recommendation types the team has found unhelpful or flat-out
wrong. It's injected into the page-audit and refresh workflows' evaluation and synthesis
steps, and those prompts are instructed to **suppress any finding matching a rule below**.

> Lives in the gitignored `artifacts/` folder once copied. Safe to keep brand-neutral
> rules here, but treat it like the other artifacts: don't commit anything confidential.

## How to maintain it (the feedback loop)

When the tool keeps surfacing a kind of recommendation that isn't useful, you don't have to
keep ignoring it run after run. Either:

1. **Edit this file** — add a one-line rule under the right heading, or
2. **Ask Claude in your project**, e.g. *"The audit keeps flagging X and it's not useful —
   add a guardrail so it stops."* Claude has access to this artifact and will append the
   rule for you.

Be specific about *what* to suppress and *why*, so a rule doesn't accidentally silence a
genuinely useful finding. Prefer "suppress X when Y" over a blanket "never mention X."

## Suppression rules

### Pricing
- Do not flag a difference between a single-line price on a pricing card and a multi-line
  price in the body copy — that's expected on Navi pages. (Built into the prompts already;
  listed here for visibility.)

### Structure / metadata
- _Example:_ Don't recommend adding a coverage map to coverage articles — they already
  embed one via a component that doesn't show up in the crawl.

### Brand / voice
- _Add team-specific rules here._

### Anything else
- _Add team-specific rules here._
