# Workflow 05 — Messy Spreadsheet → Clean Summary + Anomalies (AI Reads, You Verify Math)

> **Who it's for:** ops, finance, admin, analysts — anyone whose week includes "can you make sense of this export?"
> **Time:** 2 hours → 15 min. **Any chat LLM.**

---

## The insight nobody tells you

The two hours were never in Excel. They're in the gap between "raw export" and "thing I can present." AI is a spectacular **translation layer** for messy data — and a terrible **calculator**. Use it for exactly that: it reads chaos, you verify math.

## Step 1 — Paste the raw data

Headers included, messy as-is. Mixed date formats, half-empty columns, duplicate names — don't pre-clean. That was the whole 2 hours.

## Step 2 — Paste this prompt above the data

```
You are my data cleaner. Rules:

1. FIRST: restate the data as you understand it — columns, row count,
   what each row represents. Then STOP and ask me to confirm before
   producing anything.

2. After I confirm, output:
   CLEAN SUMMARY — the 5 numbers someone would actually ask about.
   ANOMALIES — rows that look wrong (duplicates, impossible values,
     gaps), quoted exactly as they appear.
   FORMAT ISSUES — what's inconsistent (dates, names, units).

3. NEVER fill in missing values, even obvious ones. List them under
   GAPS instead. Missing data is information.

4. Show your arithmetic for every summary number:
   (= 42 + 17 = 59).

5. Do not deduplicate unless I confirm the rows are truly the same.
```

## Step 3 — The 60-second audit: recompute one number

Pick one CLEAN SUMMARY number and reproduce it yourself (Excel, calculator, fingers). **If it doesn't reproduce, the AI touched the data** — not just the summary — and every other number is now suspect. Rerun.

Second check: **the gaps test.** Real-world data always has gaps. A summary with an empty GAPS section means the AI "helpfully" completed your missing values — which is data fabrication with a helpful face. That's the #1 sin in this workflow.

## Known failure modes

| The AI will try to… | Your fix |
|---|---|
| Fill gaps to make series complete | GAPS rule + the gaps test |
| Mix units (minutes/hours, RMB/USD, per-month/per-quarter) | Check FORMAT ISSUES before trusting any total |
| Merge two different people/things that look identical (two John Smiths) | "Do not deduplicate without confirmation" |

## Why this works

Step 1 — *restate and stop* — kills 80% of garbage-in errors before any output exists. It's the difference between a data assistant and a data fabricator, and it costs one extra round-trip.

---
*Part of The 9-to-5 AI Workflow Kit. Workflow 01 (weekly updates) is the free sample.*
