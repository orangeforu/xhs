# Workflow 10 — Client Message Triage: Answer Now / Escalate / Later

> **Who it's for:** anyone with a client inbox: account managers, support leads, agencies, freelancers.
> **Time:** 90 min of flinching → 15 min. **Any chat LLM.**

---

## The insight nobody tells you

Client inbox overwhelm isn't a volume problem — it's an **unsorted mixed pile**: things to answer now, things that need someone else, things that need nothing. The sort *is* the work; the replies are easy.

And the dangerous sort error is always the same direction: **treating a commitment as a conversation.** Money, deadlines, promises, complaints — those aren't "quick replies." A machine can sort them; only you can commit.

## Step 1 — Paste the pile

Raw messages, in any order. Multiple clients fine — keep client names attached.

## Step 2 — Paste this prompt above them

```
You are my client-message triage assistant. Rules:

Classify each message into exactly one bucket:

  ANSWER NOW — factual, within my authority, low stakes. Draft a
    2-sentence reply for my review.
  ESCALATE — involves money, commitments, deadlines, complaints, or
    anything I'm not authorized to decide. State WHAT it needs
    (an approval / a call / my manager) — do NOT draft a reply.
  LATER — no deadline, no decision needed. Batch for [chosen day].

Rules:
1. When in doubt between ANSWER NOW and ESCALATE → ESCALATE.
   Optimism here costs real money.

2. For every message, quote the exact phrase that triggered its
   classification, so I can sanity-check your reasoning.

3. ANSWER NOW drafts may never commit to dates, prices, or outcomes.
   Those become [NEEDS MY DECISION] placeholders.

4. Polite phrasing hides deadlines ("before the quarter wraps up…").
   Any implicit deadline disqualifies LATER.
```

## Step 3 — The 60-second audit: the commitment sweep

Scan the ANSWER NOW pile for anything involving **money, dates, or promises** — this is the AI's bias zone. It wants to *resolve*, so it drafts replies for things that need a human decision. Every draft containing a commitment goes to ESCALATE.

Second check: **the trigger quotes.** The prompt forces a quoted phrase per message — actually read them. That's what makes this triage auditable: you check *why*, not just *what*. If a quote doesn't justify its bucket, re-sort that message yourself; don't trust the average.

## Known failure modes

| The AI will try to… | Your fix |
|---|---|
| Draft a reply to an angry client | All complaints route to ESCALATE — verify none leaked |
| Honor the surface tone instead of the content ("just a thought!" attached to a deadline) | Implicit-deadline rule |
| Sort by length instead of stakes (short = easy) | Trigger quotes expose length-based sorting instantly |

## Why this works

You stop flinching at the inbox because the pile becomes three piles with reasons attached. The escalation-first bias is the entire point: **machines sort, humans commit** — and nothing in the ANSWER NOW pile can hurt you.

---
*Part of The 9-to-5 AI Workflow Kit. Workflow 01 (weekly updates) is the free sample.*
