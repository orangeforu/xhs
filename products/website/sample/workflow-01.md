# Workflow 01 — The Weekly Update That Writes Itself (Without AI Making Things Up)

> **Who it's for:** anyone who reports to a manager — ops, PM, admin, finance, marketing coordinators.
> **Time:** 40 min → 10 min.
> **You need:** any chat LLM (ChatGPT / Claude / Gemini — doesn't matter).

---

## The insight nobody tells you

Your weekly update isn't read by your manager. It's skimmed by **your manager's manager** — 15 seconds, eyes hunting for names and numbers. So the winning format is deliberately "ugly": short lines, numbers, zero adjectives.

Most people lose the week not in *writing*, but in *remembering and organizing*. This workflow deletes that step entirely.

## Step 1 — Prepare nothing (this is the actual trick)

Open a chat with your LLM and dump your raw week, unsorted:

- Slack/Teams messages you sent
- tickets you closed
- half-finished sentences from your notes app
- meeting titles you sat through
- that 2am thought you typed into your phone

Don't clean it up. Don't group it. **Organizing is 80% of the time cost — that's the machine's job, not yours.**

## Step 2 — Paste this prompt *above* your dump

```
You are my weekly update assistant. Rules:

1. Group everything into three sections: DONE / IN PROGRESS / NEEDS HELP.
   Maximum 3 lines per item.
2. Keep only items with a result or a number. Delete process words:
   "aligned," "touched base," "followed up," "monitoring."
3. Write each line as: what I did + the result or number + who it helps.
4. Never add anything I did not say. If something is uncertain, mark it
   [VERIFY] instead of guessing.
5. End with at most 2 asks — decisions or resources I actually need.

Banned words: synergy, leverage, circle back, bandwidth, deep dive,
move the needle, low-hanging fruit.
```

## Step 3 — The 60-second audit (the part that saves your job)

Before you hit send, do two checks:

**Check A — the [VERIFY] flags.** Resolve every one: delete it or confirm it. Half a minute.

**Check B — fabricated logic.** This is the trap nobody warns you about.

Real example from my week: Tuesday, a client requested a rework. Friday, an unrelated project slipped its schedule. Two separate facts. The AI merged them into:

> *"Issue summary: the project slip was caused by the client rework."*

Neither happened because of the other. **AI doesn't invent content — it invents causality.** It wires your facts into cause-and-effect chains that never happened, because chains read better than lists.

Skim every sentence containing *because / due to / caused by / as a result / impacted*. That's where it fabricates.

## Known failure modes

| The AI will try to… | Your fix |
|---|---|
| Inflate weak items with jargon ("Drove alignment across stakeholders") | The banned-words list catches most; delete the rest on sight |
| Invent causality between unrelated events | Check B above — always |
| Pad with next-week filler ("Continue monitoring…") | Delete. Silence is fine. |
| Round your numbers up ("about 50" → "50+") | Never let it. Your numbers are your credibility. |

## Why this format works (manager psychology)

- **Three sections** → your skip-level reader finds NEEDS HELP in 5 seconds
- **Numbers everywhere** → you read as someone who knows what "done" means
- **Max 2 asks** → you read as someone who solves, not escalates
- **No adjectives** → nothing for a stressed reader to distrust

---

*Part of The 9-to-5 AI Workflow Kit. This is the free sample — the full kit has 9 more, each with its own audit checklist.*
