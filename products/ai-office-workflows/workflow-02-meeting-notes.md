# Workflow 02 — Meeting Notes → Decisions, Owners, Deadlines (Not a Transcript)

> **Who it's for:** anyone who takes notes in meetings and then never reads them again.
> **Time:** 30 min → 8 min. **Any chat LLM.**

---

## The insight nobody tells you

Nobody rereads transcripts. The entire value of meeting notes is three lists: **what we decided, who owns what, when it's due.** Everything else is archaeology.

And the most valuable list is the one nobody keeps: the actions that *left the meeting without an owner*. That list is political gold.

## Step 1 — Dump everything raw

Paste in whatever you have: the call transcript, your scribbled half-sentences, the chat log. Order doesn't matter. Don't clean it.

## Step 2 — Paste this prompt above the dump

```
You are my meeting notes processor. Rules:

1. Output exactly three sections:
   DECIDED — only items where someone explicitly agreed. Include a
     short quote of the moment. No quote, no entry.
   OWNED — every action as: task + ONE named owner + one-line
     definition of done. If no owner was named, put it under
     "ORPHANED — needs an owner" instead of guessing one.
   DUE — only dates someone actually said out loud. No date stated →
     write "no date stated."
2. Kill all discussion that didn't end in a decision.
3. Mark anything you inferred rather than heard with [INFERRED].
```

## Step 3 — The 60-second audit: the invented consensus check

AI completes patterns. "We should probably revisit pricing" becomes *DECIDED: pricing revisited*. "That makes sense to me" becomes a decision. That's how meetings that decided nothing get minutes that decided everything — and someone gets blamed for "what we agreed."

Check every DECIDED item: **is there a real quote?** Would the person who "decided" it recognize themselves?

Second check: **the orphan count.** Real meetings are full of ownerless actions. A summary with zero ORPHANED items is a fabricated one — or your meeting was magical. Probably the first.

## Known failure modes

| The AI will try to… | Your fix |
|---|---|
| Invent owners ("Sarah seemed to agree" → Sarah owns it) | The ORPHANED rule catches this — don't override it |
| Turn "let's revisit next quarter" into DECIDED | No-quote-no-entry rule |
| Silently upgrade fuzzy dates ("soon" → "next Friday") | DUE section only takes spoken dates |

## Why this works

Your 60-minute meeting becomes one screen of accountability. And the ORPHANED list — which you send back as "these need owners" — quietly makes you the most organized person in the room, without ever saying so.

---
*Part of The 9-to-5 AI Workflow Kit. Workflow 01 (weekly updates) is the free sample.*
