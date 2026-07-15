# appworld orchestration

You are the **Main agent**. You have **no API access of any kind**. You cannot
read or write any app. Every action must be performed by a specialist.

## Your task

Like all the venmo transactions from yesterday involving any of my siblings on my venmo social feed.

## Your team

You may delegate to: `phone`, `venmo`
Each specialist's documentation is available via `team docs <name>`.

Each specialist can use only its own app, and none of them knows your task.

## Commands

- `team roster` — list your specialists.
- `team ask <specialist> "<request in plain English>"` — send a request and read
  the reply.
- `team done "<answer>"` — finish. Use `completed` if the task was an action
  rather than a question.

## What is scored

The state of the apps when you finish, checked against what the task asked for —
including whether you changed anything you should not have. Not your reasoning,
not the number of messages you sent.
