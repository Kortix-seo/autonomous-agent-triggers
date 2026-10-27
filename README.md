# Autonomous agent triggers: the run caps a scheduled agent needs

An open-source reference for the manifest that starts an autonomous agent with nobody at the keyboard: one `kortix.yaml` with a cron trigger, a signed webhook trigger, the run caps on each, and a stdlib checker that refuses a trigger file missing them.

Kortix is the open-source AI Operating System this example is written for. Its triggers are rows in `kortix.yaml`, next to the agents and the sandbox image, so a schedule is a file you can diff rather than a setting in someone else's database ([triggers reference](https://kortix.com/docs/connect/triggers)).

## Why the caps are the interesting part

An unattended agent fails by repetition far more often than by one dramatic run: a broken sender retries, a monitor command prints the same line every minute, an event source replays a batch after an outage. Each of those turns one session into forty while nobody is at the keyboard.

The documentation states the defaults, and they are worth reading as a pair:

- A trigger starts at most `max_runs_per_hour` runs in any 60 minutes, 60 when unset.
- A trigger starts at most `max_runs_per_day` runs in a UTC day, no cap when unset.

So the hourly ceiling exists on day one and the daily one does not. A fire past a limit starts no session and sends no prompt; it is recorded as a skipped run whose reason names the limit. Two full hours at the hourly limit pause the trigger by itself, and the daily limit never does.

`overlap: skip` is the third bound, and the default for a cron trigger: a fire waits out the previous run instead of stacking sessions behind it.

## What is in this repository

| File | What it is |
|---|---|
| `kortix.example.yaml` | Two triggers, `daily-digest` (cron) and `pr-review` (signed webhook), each with both caps |
| `check_triggers.py` | A stdlib checker: 6-field cron, caps present and sane, a webhook with no signing secret refused |
| `policy.example.yaml` | The tool-policy block that decides which calls a run may make without a person |

## Run the checker

```sh
python3 check_triggers.py kortix.example.yaml
```

It reads YAML without a third-party parser, so it needs nothing but Python 3. It reports, per trigger:

- the cron expression's field count (six: second, minute, hour, day of month, month, weekday) and rejects five, which is the field count most schedulers use
- `max_runs_per_hour` and `max_runs_per_day` when present, flags them when absent, and rejects a value under 1
- a `webhook` trigger with no `secret_env`, which the platform refuses anyway: there is no unsigned webhook
- `overlap` other than `skip` or `allow`

Exit code 0 when every trigger passes, 1 when one does not. It is deliberately small: a lint you can read in one sitting, not a second implementation of the platform.

```sh
$ python3 check_triggers.py kortix.example.yaml
kortix.example.yaml: 2 triggers
  daily-digest      cron     max_runs_per_hour=4  max_runs_per_day=4  ok
  pr-review         webhook  max_runs_per_hour=20 max_runs_per_day=100 ok
1 warning: daily-digest sets no overlap; the cron default is skip
```

## The cron field count catches people out

A cron trigger takes a 6-field expression, seconds first. A five-field expression carried over from another scheduler does not fail loudly: every value lands one position off, so `0 9 * * 1-5` is read as second 0, minute 9, hour `*`, and so on. The checker refuses five fields for that reason. A trigger also fires at most once a minute, so an expression finer than that buys nothing.

## What still has to happen after the run

A cap governs how much work arrives, not what lands. A session runs one agent in its own sandbox, the sandbox clones the repo and works on a new branch, and the agent commits, pushes that branch, and opens a change request against the default branch. Work reaches the default branch through a change request a person approves, unless an admin granted the merge capability.

`policy.example.yaml` is the other half of the same decision: which tool calls a run may make on its own. Rule each tool call allow, ask or block, down to the arguments it was given, with a held call expiring after its time to live.

## Read more

Each of these pages covers one question this manifest raises, in order:

- [What an autonomous agent run costs](https://autonomousaiagentsguide.com/what-an-autonomous-agent-run-costs), and how the caps above bound the bill.
- [What autonomous AI agents are](https://autonomousaiagentsguide.com/what-are-autonomous-ai-agents), with a test you can apply to any vendor's definition.
- [Running an agent with nobody watching](https://autonomousaiagentsguide.com/running-an-agent-with-nobody-watching) walks the trigger types one by one and what each needs before the first fire.
- [Autonomous vs human in the loop](https://autonomousaiagentsguide.com/autonomous-vs-human-in-the-loop) places the person at one of three levels and shows what each costs.
- [Open-source autonomous AI agents](https://autonomousaiagentsguide.com/open-source-autonomous-ai-agents) compares four projects on where their rules live.
- [Autonomous agent examples](https://autonomousaiagentsguide.com/autonomous-agent-examples) shows the work these runs hand back.
- [Triggers reference](https://kortix.com/docs/connect/triggers) and [Kortix on GitHub](https://github.com/kortix-ai/suna) for the platform behind the manifest.
