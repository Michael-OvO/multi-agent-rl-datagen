# failure-recovery

You are the **Main agent** coordinating a team of sub-agents. Dispatch every subtask to a worker via the `coord` CLI and drive them all to SUCCESS. The roster shows who *can attempt* each task, but some workers will **fail** — detect failures and re-route to another capable worker. You have a limited dispatch budget, so do not waste attempts.

## Subtasks (id: depends-on)
- `t0`: deps=—
- `t1`: deps=—
- `t2`: deps=t0, t1
- `t3`: deps=—
- `t4`: deps=t3

## Roster (subtask: workers that may attempt it)
- `t0`: w0, w1, w2
- `t1`: w0, w1, w2
- `t2`: w0, w1
- `t3`: w0, w1
- `t4`: w1, w2

## Output contract

Interact using the `coord` command (each call prints JSON):
- `coord dag` — the subtask dependency graph.
- `coord roster` — which workers may attempt each subtask.
- `coord dispatch <task> <worker>` — attempt a subtask; returns SUCCESS / FAILURE / ERROR. A subtask may be dispatched only after its dependencies are done.
- `coord status` — progress and remaining budget.
- `coord submit` — finalize.

Score: 0 unless every subtask is complete within budget; otherwise `optimal_dispatches / your_dispatches` — so recover efficiently and never retry a worker you have already seen fail.
