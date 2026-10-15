# Workflow 09 — Read Your Manager's Mind (Pre-Loading the Questions That Kill You)

> **Who it's for:** anyone walking into a skip-level, a steering review, or any meeting with a senior person who has 15 seconds of context.
> **Time:** 45 min of dread → 10 min of armor. **Any chat LLM.**

---

## The insight nobody tells you

These meetings are lost in the **30 seconds after your update**, not during it. The killer question always comes right when you think you're done — and it's almost always *invited by your own content*: the number without a baseline, the win without context, the risk you mentioned without sizing it.

The good news: questions invited by your content are **predictable from your content.**

## Step 1 — Paste your update

Exactly what you plan to say — bullets, notes, the email you sent, whatever form it's in.

## Step 2 — Paste this prompt above it

```
You are preparing me for [MEETING TYPE: skip-level / steering review /
meeting my manager's manager]. This person has 15 seconds of context,
high skepticism, and no interest in being kind.

Here is what I plan to say:
[PASTE UPDATE]

Rules:

1. Attack my update like that person. Generate the 5 questions I
   LEAST want to hear — prioritize questions my own update invites.

2. For each question give:
   (a) why it gets asked
   (b) a 2-sentence answer using ONLY facts from my update
   (c) what to look up before the meeting to be safe

3. Flag anything in my update that invites a question I cannot
   answer. Suggest: cut it, or add the number that defuses it.
```

## Step 3 — The 60-second audit: the comfortable-question check

**If all 5 questions feel easy, the AI was polite, not adversarial** — rerun with: *"assume this leader thinks my work is trivial."* A good run should include at least one question that stings.

Second check: are the questions **derived from your specifics** ("you said onboarding dropped 12% — from what baseline?"), or generic templates ("what's the timeline?", "how's the budget?")? Generic means it skimmed your update — rerun.

Third: verify each 2-sentence answer against your source. The answer-drafting step is where AI quietly invents facts you never said, and you're about to say them out loud to a senior person.

## Known failure modes

| The AI will try to… | Your fix |
|---|---|
| Softball you (its default politeness setting) | The "thinks my work is trivial" rerun |
| Ask generic template questions | Specifics check above |
| Draft answers with facts not in your update | Read every answer against your own text |

## Why this works

You walk in having pre-answered the ambush — the meeting becomes a performance of preparation rather than improvisation. And rule 3 (*cut what invites unanswerable questions*) quietly teaches you presentation strategy: every claim you make is a question you're choosing to defend.

---
*Part of The 9-to-5 AI Workflow Kit. Workflow 01 (weekly updates) is the free sample.*
