# theory-of-mind

You are the **Main agent** investigating who took the last cookie. Exactly one suspect is the culprit. The exonerating clues are held privately by different witnesses — you cannot see them. `ask` the right witness. A witness who lacks a clue may tell you **who to ask instead** (a referral). Follow referrals, gather the clues, deduce the culprit, and `submit` — all within your question budget.

## Suspects
s0, s1, s2, s3, s4

## Question budget
24 questions

## Topics and where to start (topic: entry witness)
- `topic0`: start by asking `a1`
- `topic1`: start by asking `a2`
- `topic2`: start by asking `a4`
- `topic3`: start by asking `a3`

## Witnesses
a0, a1, a2, a3, a4, a5, a6, a7

## Output contract

Interact using the `interview` command (each call prints JSON):
- `interview agents` — the witnesses, suspects, topics, per-topic entry witness, and your question budget.
- `interview ask <witness> <topic>` — returns a CLUE (clears a suspect), a REFERRAL (`ask` someone else), or NO_INFO. Counts against your budget.
- `interview submit <suspect>` — name the culprit.

Score: 0 unless you name the correct culprit; otherwise `optimal_questions / your_questions` — so follow referrals to the clue-holders instead of interrogating everyone.
