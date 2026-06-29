# Plans and Pricing (template)

Copy this file to `artifacts/plans-and-pricing.md`, fill it in with **current** plan and
pricing data, and keep it updated. When present, it is bundled into the page-audit,
refresh, rewrite, and net-new-brief workflows so they stop citing plans/prices from the
model's training data (which are often a year or more out of date).

> This file lives in the gitignored `artifacts/` folder once you copy it there. **Never
> commit real pricing** — the repo is public. Keep only the template here.

## How the workflows use this

- Plan names and prices below are treated as the source of truth for accuracy checks.
- If a plan/price isn't listed here, the workflow will say "could not verify current
  pricing" rather than asserting something is outdated from memory.
- **Single-line vs. multi-line pricing:** on-page pricing cards show single-line pricing
  only; article bodies often cite multi-line (per-line) pricing. That difference is
  expected and is never flagged as a mismatch. List both bases here when they differ so
  the workflow can check each against the right number.

## Last updated

`YYYY-MM-DD` — <who updated it>

## Current plans

| Plan | Single-line / mo | 2 lines (per line) | 3 lines (per line) | 4+ lines (per line) | Data | Key features | Status |
|------|------------------|--------------------|--------------------|---------------------|------|--------------|--------|
| Example Unlimited | $XX | $XX | $XX | $XX | Unlimited | Hotspot, taxes incl. | current |
| Example Value     | $XX | $XX | $XX | $XX | XX GB     | …                    | current |

## Recently discontinued plans (flag if still referenced in content)

| Old plan | Replaced by | Discontinued | Notes |
|----------|-------------|--------------|-------|
| Example Go 5G | Example Unlimited | 2024 | Should no longer appear as a current plan |

## Notes / caveats

- Promotional pricing, autopay discounts, taxes-and-fees handling, etc.
