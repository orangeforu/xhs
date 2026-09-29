# Workflow 04 — 100-Page Document → Exec Summary + Trapdoors + Monday Actions

> **Who it's for:** anyone who receives contracts, policies, RFPs, vendor docs, or regulations and must brief humans on them.
> **Time:** 3 hours → 25 min. **Any chat LLM with a long context window.**

---

## The insight nobody tells you

An exec summary isn't a shorter version of the document — it's a **different product**: what changes, what can bite us, what we do Monday.

And the detail that ends careers in long documents is never in the executive summary. It's in **footnote 14, Appendix C, the clause that starts "provided that…"** — buried exactly where nobody reads.

## Step 1 — Feed the document

Paste it (or chunk it if needed: "Part 1 of 4" etc.). Add one line of context: *who you are and what you fear* — "I'm the ops lead, I need to know what this obligates us to."

## Step 2 — Paste this prompt

```
You are my document analyst. Rules:

1. Output four sections:
   IN PLAIN WORDS — what this document is, 3 sentences, zero jargon.
   WHAT CHANGES — concrete implications for [my role/context].
   TRAPDOORS — conditions, exceptions, deadlines, auto-renewals,
     penalties, and dependencies. Especially ones buried in footnotes,
     appendices, or clause language. Quote each one with its PAGE
     NUMBER.
   MONDAY ACTIONS — max 3 things to actually do next week.

2. Every claim carries a page citation [p. XX]. No citation, don't
   say it.

3. Flag anything that might be boilerplate but could still bite:
   [POSSIBLY BOILERPLATE].
```

## Step 3 — The 60-second audit: the citation spot-check

**AI page citations are wrong ~10-20% of the time** — hallucinated or off by pages. Open the document at two cited TRAPDOORS and check the quote is real. If both check out, trust the rest at reading risk; if one fails, re-verify everything.

Second check: **the surprise test.** A good analysis of any 100-page document should surface at least one trapdoor you didn't expect. If your summary is all headline-level restatement, the AI summarized the executive summary and skipped the gold.

## Known failure modes

| The AI will try to… | Your fix |
|---|---|
| Invent page numbers | Spot-check two, always |
| Summarize only the intro/exec summary (the lazy path) | The TRAPDOORS section forces the deep pass; empty trapdoors = rerun |
| Smooth conditionals ("must, except when X" → "must") | Read every trapdoor quote yourself — that's the point of quoting |

## Why this works

TRAPDOORS is the section nobody else sends upward. Find one auto-renewal clause or buried penalty before it triggers, and this kit has paid for itself a hundred times over.

---
*Part of The 9-to-5 AI Workflow Kit. Workflow 01 (weekly updates) is the free sample.*
