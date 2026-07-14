# parallel-scheduling

You are the **Main agent** coordinating a team of specialist sub-agents. Produce an execution schedule that assigns every subtask to a worker and a start time, **minimizing the overall finish time (makespan)**.

## Team roster (worker: skills)
- `w0`: test, code
- `w1`: code
- `w2`: code

## Subtasks (id: skill, duration, depends-on)
- `t000`: skill=code, dur=10, deps=—
- `t100`: skill=test, dur=2, deps=—
- `t101`: skill=test, dur=2, deps=t100
- `t102`: skill=test, dur=3, deps=t101
- `t103`: skill=test, dur=3, deps=t102
- `t200`: skill=code, dur=2, deps=—
- `t201`: skill=code, dur=2, deps=t200

## Output contract

Write your schedule to `/app/schedule.json` — a JSON array of objects `{"subtask": "<id>", "worker": "<id>", "start": <int>}`.

Rules (any violation scores 0):
- Schedule every subtask exactly once.
- A subtask may start only after all its dependencies have finished.
- A worker may only run a task whose skill it has.
- A worker runs one task at a time (no overlapping intervals).

Your score is `optimal_makespan / your_makespan` — so parallelize independent work across the team.
