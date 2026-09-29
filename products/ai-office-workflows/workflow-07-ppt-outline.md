# Workflow 07 — Blank Page → PPT Outline (Every Slide Makes ONE Claim)

> **Who it's for:** anyone who opens PowerPoint before knowing what they're arguing.
> **Time:** 2 hours of decorating → 10 min of structure. **Any chat LLM.**

---

## The insight nobody tells you

AI makes slides exactly the way bad presenters do: **bullets with no claim.** Twelve slides of "Key Considerations" is a tour, not an argument.

The fix is one rule: every slide has exactly ONE takeaway sentence. Content serves the claim — never the other way around. And business audiences get the **conclusion on slide 1**, not the agenda.

## Step 1 — Three inputs, one line each

Topic, audience (and what *they* care about), and slide count. Resist adding more.

## Step 2 — Paste this prompt

```
You are my presentation outliner. Rules:

1. Topic: [X]. Audience: [Y]. Length: [N slides].

2. FIRST, give me the SPINE: one takeaway sentence per slide, in
   order. The spine alone must tell the complete story if read with
   nothing else. STOP after the spine; wait for my approval.

3. After I approve the spine, for each slide give:
   - the takeaway sentence (max 15 words)
   - 2-4 supporting bullets
   - "NOT ABOUT:" one line of explicit scope control

4. Slide 1 = the conclusion, not the agenda.

5. One idea per slide. If a slide needs two ideas, it's two slides.

6. You may not invent statistics to fill a "proof" slide. If I gave
   no number for something, write [NEED DATA] and I'll find it.
```

## Step 3 — The 60-second audit: the spine test

Read only the takeaway sentences, in order, with nothing else. **If those N sentences don't form a complete argument, the deck is a tour** — fix the spine before any formatting happens. That's the entire point of forcing the spine first: you review the *story* in 60 seconds, before it costs you two hours of design.

Second check: the NOT ABOUT lines. If they feel unnecessary, the AI scope-crept anyway — check each slide for a hidden second idea ("and also…", "additionally…").

## Known failure modes

| The AI will try to… | Your fix |
|---|---|
| Produce bullet dumps with no claims | The spine-first structure makes this impossible to miss |
| Hide a second idea mid-slide | The NOT ABOUT line exposes it |
| Invent a plausible statistic for a proof slide | [NEED DATA] rule — verify every number in the final deck |

## Why this works

You will never again spend two hours decorating a deck that argues nothing. Spine first, slides second, design last — the same order your audience's attention actually works in.

---
*Part of The 9-to-5 AI Workflow Kit. Workflow 01 (weekly updates) is the free sample.*
