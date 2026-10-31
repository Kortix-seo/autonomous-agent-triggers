# Autonomous agent triggers: the run caps a scheduled agent needs

An open-source reference for the manifest that runs an autonomous agent unattended. It holds one `kortix.yaml` with a cron trigger, a signed webhook trigger, the run caps on each, and a stdlib checker that refuses a file where either cap is missing.

Kortix is the open-source CompanyOS: your agents, their skills, your company memory, and every connector in one git repo you own, with the agents working on real cloud computers. A trigger is a row in `kortix.yaml`, beside the agents and the sandbox image, so the schedule sits in the repo and a change to it is a diff, not a setting in another vendor's database ([triggers keys](https://kortix.com/docs/developers#triggers-keys), [automations](https://kortix.com/docs/guide#automations)).

## Why the caps are the interesting part

An unattended agent fails by repetition far more often than by one dramatic run: a broken sender retries, a poller prints the same line every minute, an event source replays a batch after an outage. Each of those turns one session into forty before anyone notices. Two keys bound that, and their defaults are worth reading as a pair:

- `max_runs_per_hour`, the runs a trigger starts in any 60 minutes, is 60 when unset.
- `max_runs_per_day`, the runs it starts in a UTC day, has no default.

So the hourly ceiling exists on day one and the daily one does not. A trigger that hits its hourly limit for 2 hours in a row pauses itself, and it stays **Paused** until someone selects **Resume** ([automations](https://kortix.com/docs/guide#automations)).

`overlap: skip` is the third bound: `skip` is the default for a schedule and `allow` for any other trigger, and it holds a fire while the previous run is still going instead of stacking sessions behind it.

## What is in this repository

| File | What it is |
|---|---|
| `kortix.example.yaml` | Two triggers, `daily-digest` (cron) and `pr-review` (signed webhook), each with both caps |
| `check_triggers.py` | A stdlib checker: 6-field cron, caps present and sane, a webhook with no signing secret refused |
| `policy.example.yaml` | The connector-policy block, with a rule set on the arguments a call carries |

## Run the checker

```sh
python3 check_triggers.py kortix.example.yaml
```

The parser is standard library only and refuses what it cannot read, so the script needs a Python 3 install and nothing else. Per trigger it reports:

- the cron expression's field count (six: second, minute, hour, day of month, month, weekday); five is refused, because five is what most schedulers take
- `max_runs_per_hour` and `max_runs_per_day` when present, flags them when absent, and rejects a value under 1
- a cron trigger with no `timezone`, whose expression would otherwise be read in the server's zone
- a `webhook` trigger with no `secret_env`; the platform wants one too, since a signed request is what fires a webhook
- `overlap` other than `skip` or `allow`

Exit code 0 when every trigger passes, 1 when one does not. The scope is deliberate: a lint small enough to audit by eye beats a second copy of the scheduler.

```sh
$ python3 check_triggers.py kortix.example.yaml
kortix.example.yaml: 2 triggers
  daily-digest      cron     max_runs_per_hour=4  max_runs_per_day=4      ok
  pr-review         webhook  max_runs_per_hour=20  max_runs_per_day=100   ok
```

## The cron field count catches people out

A cron trigger takes a 6-field expression, seconds first. Carry a five-field expression over from another scheduler and nothing complains: every value lands one position off, so `0 9 * * 1-5` reads as second 0, minute 9, hour `*`, and so on. Hence the refusal at five. And since a trigger fires at most once a minute, an expression finer than a minute buys nothing.

## What still has to happen after the run

A cap governs how much work arrives, not what lands. Each session boots its own isolated machine, called a sandbox, and the agent works there on a branch of the project's repository; by default the session may push to that branch and no other. The work reaches the shared repository when a person merges its change request, unless the agent's `kortix_permissions` in `kortix.yaml` include `project.gitops.merge`, which lets a session merge its own.

The block in `policy.example.yaml` is a second, separate decision, and it governs connector actions rather than the agent's own tools. Each rule matches an action such as `gmail.send_email` and sets `always_run`, `require_approval` or `block`, which the dashboard shows as Allow, Ask and Block. Rules are read top to bottom and the first one that fits decides. A rule's `conditions` match the arguments the call was given, so the file's `always_run` entry covers a send to `*@example.com` and the `require_approval` entry below it holds the rest. A held call expires after `approvals.ttl`, which the file sets to 4h.

`agents.<name>.permission` is the other mechanism, for the calls an agent makes through its tools: it sets allow, ask or deny per tool, as one action for all of them or as a map of key to action.

## What the caps do not cover

A cap bounds how many sessions start, and little beyond that. The bill still comes from how often the trigger fires and what each run spends, and a session that needs a person stops after 30 minutes of waiting. [What an autonomous agent run costs](https://autonomousaiagentsguide.com/what-an-autonomous-agent-run-costs) follows the money through both halves, and [Running an agent with nobody watching](https://autonomousaiagentsguide.com/running-an-agent-with-nobody-watching) tests this manifest against four conditions it can meet or miss: a real trigger, a branch of its own, calls that follow a rule, and a result someone may refuse. Both are pages of a guide from the Kortix team.

## Read more

Each of these pages covers one question this manifest raises:

- [What autonomous AI agents are](https://autonomousaiagentsguide.com/what-are-autonomous-ai-agents), with a test you can apply to any vendor's definition.
- [Autonomous vs human in the loop](https://autonomousaiagentsguide.com/autonomous-vs-human-in-the-loop) places the person at one of three levels and shows what each costs.
- [Open-source autonomous AI agents](https://autonomousaiagentsguide.com/open-source-autonomous-ai-agents) compares four projects on where their rules live.
- [Autonomous agent examples](https://autonomousaiagentsguide.com/autonomous-agent-examples) shows the work these runs hand back.
- [Triggers keys](https://kortix.com/docs/developers#triggers-keys) and [Kortix on GitHub](https://github.com/kortix-ai) for the keys and the repository behind the manifest.
