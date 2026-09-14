# subagent-model-gate

A Claude Code `PreToolUse` hook that blocks any subagent dispatch which does not
specify a model, so the calling model has to choose deliberately instead of
inheriting yours.

I ran it for 30 days and measured what it did. **It failed at the thing I built it
for.** This README is mostly that measurement, because the negative result turned
out to be more useful than the hook.

If you want automatic cost routing, you probably want
[claude-model-router-hook](https://github.com/tzachbon/claude-model-router-hook)
instead. Read on if you want the data.

---

## The problem

Subagents inherit the parent session's model. Claude Code resolves a subagent's
model in this documented order:

1. `CLAUDE_CODE_SUBAGENT_MODEL`
2. the per-invocation `model` parameter on the Agent call
3. the subagent definition's `model:` frontmatter
4. the main conversation's model

Sit in Opus, dispatch an agent to grep some files, and nothing in that chain
objects. Step 4 catches it and the grep runs on Opus.

The obvious fix is a silent default. Claude Code ships two: the env var and
frontmatter. My argument for building something else: nobody had decided, and a
silent default replaces an unconsidered Opus with an unconsidered Sonnet, silently
downgrading the calls that warranted Opus.

That argument sounded right to me for a month. The data says the second half of it
is wrong.

## What the 30 days actually show

Window: 2026-07-13 to 2026-08-12. Counted by streaming every session transcript and
filtering on each record's own timestamp. 501 raw Agent tool-use records.

A blocked dispatch and its retry are two records for one logical dispatch, so the
raw count needs deduplicating before it means anything. Deduplicated: **409 logical
dispatches**, of which 393 ended up with a model.

Of those 393, split by whether the model was chosen freely or only after a block:

| | Chose voluntarily | Only after a block | Total |
|---|---|---|---|
| sonnet | 294 | 67 | 361 |
| opus | **28** | **0** | 28 |
| haiku | 3 | 1 | 4 |
| **Total** | **325 (82.7%)** | **68 (17.3%)** | **393** |

**Zero of the 68 forced dispatches chose Opus.** All 28 Opus dispatches specified
Opus on the first attempt, with no block involved. The block path and the Opus path
are disjoint sets across the whole window.

The 68 forced dispatches came back as Sonnet 67 times and Haiku once. The single
divergence from what a Sonnet default would have produced was a downgrade, not an
escalation.

### The block message told it to pick Sonnet

I nearly published the paragraph above without this, and it is the most important
caveat in the piece.

The version that ran during the measurement was not the file in this repo. It was an
inline shell command in `settings.json`, which is why it left no file and no git
history. I recovered it from a Time Machine snapshot. It is preserved verbatim in
`measured-version.sh`, and its message said this:

```
  - model: "sonnet"  for research, triage, dump-summarization, codebase search (default for most subagent work)
  - model: "haiku"   for light dump processing, simple lookups
  - model: "opus"    for genuine multi-step reasoning only
```

It names Sonnet the default and confines Opus to "genuine multi-step reasoning
only". So "67 of 68 chose Sonnet" is substantially weaker evidence than it looks:
the prompt that produced those choices was steering toward Sonnet. A block that
tells the model what to pick is not measuring deliberation, it is measuring
compliance.

`agent-model-gate.py` in this repo carries different wording, rewritten to counter
exactly that ("Do not reflexively pick sonnet... that is a correct outcome of this
prompt, not a failure of it"). **That wording has never been measured.** Everything
in this README describes the old message. If you install the shipped version, you
are running something I have no data on.

One thing the recovery did settle in the data's favour: the hook was byte-identical
across snapshots on 2026-07-06, 07-14, 07-21, 07-28, 08-05 and 08-12, so the
intervention was constant for the whole window and the two-half comparison below is
not confounded by the tool changing under it.

## Why that refutes the design

The hook exits before any block logic the moment a model is present:

```python
if tool_input.get("model"):
    return 0
```

So the block and a hook-based silent default operate on the **identical
population**: dispatches that specified nothing. Neither can reach a call that
already made a choice. They differ only in what happens to that population.

- Block: the model re-decides. Measured outcome, 67 sonnet, 1 haiku, 0 opus.
- Silent default: sonnet, immediately, no round trip.

On 68 observations the re-decision produced the default's answer 67 times. The 28
Opus calls were never at risk from a hook-based default, because a default cannot
touch a dispatch that already specified. So the escalation-preserving argument I
built this on describes a danger that does not exist for this class of default.

It is a real danger for `CLAUDE_CODE_SUBAGENT_MODEL`, which is documented to
override the per-invocation parameter and the frontmatter both. That env var is an
absolute pin, not a default, and it cannot express "use this unless I say
otherwise." If you are choosing between the env var and a hook, that distinction is
the whole decision, and I conflated the two for a month.

## The one thing the block might have done

Across the window, the rate of dispatches arriving with no model fell and the rate
arriving with a deliberate choice rose:

| | Dispatches | Arrived modelless | Chose voluntarily |
|---|---|---|---|
| Jul 13 to 27 | 236 | 28.4% | 53.0% |
| Jul 28 to Aug 12 | 265 | 15.5% | 75.5% |

One day, Aug 6, contributed half the second half's modelless records. Removing it
drops the second-half rate to 10.1%, so the decline strengthens rather than depends
on that spike.

The tempting read is that the block taught the behaviour and then made itself
largely redundant. That would make it a transitional mechanism, worth running until
the rate plateaus and worth retiring after.

**I cannot show that from this data, and won't claim it.** A changing
mix of tasks across the two halves produces the same aggregate pattern, and a
transcript cannot separate the two. The honest statement is that the rate moved in
the direction the training story predicts, and that the training story is not the
only thing that predicts it.

Settling it needs an intervention rather than more observation: turn the block off
for a comparable window and see whether the modelless rate climbs back. That is
worth doing before anyone believes either version.

## Update, 2026-09-14: I turned the block off

On 2026-08-14 I replaced the block with a silent default. Any dispatch with no model
now gets `sonnet` injected, and every dispatch is logged. The model never sees a
message, so there is nothing to learn from. If the block had built a habit, the
habit should outlast it. If it was only correcting sessions as they ran, the
modelless rate should climb.

It climbed.

A fair comparison needs the same parent model on both sides, and the table above
does not have that. The parent switched from Opus 4.8 to Opus 5 on July 25 to 26,
two days before the halfway line, which I missed the first time. So the figures
below are main-session dispatches under Opus 5 only, leaving out agent types where
there is no choice to make. Forks are also left out: they always run on the
parent's model and ignore the override, and they barely existed before.

| | Dispatches | Arrived modelless |
|---|---|---|
| Block on, Jul 26 to Aug 12 | 203 | 10.3% |
| Block off, Aug 15 to Sep 14 | 668 | 32.5% |

The more telling cut is inside a session. I split sessions by whether their first
dispatch arrived without a model, then counted the dispatches that came after it.
Parallel calls from the same turn are grouped, so a burst of five counts once.

| First dispatch | Later bursts modelless, block on | Block off |
|---|---|---|
| Had no model | 1 of 38 (3%) | 82 of 165 (50%) |
| Had a model | 1 of 53 (2%) | 14 of 146 (10%) |

The block did not make sessions start better. The first dispatch arrived modelless
in 15 of 38 sessions with it on and 50 of 91 with it off, and at those sample sizes
the difference is weak. What the block did was stop a session repeating the
omission after being told once. Without it, a session that starts without a model
leaves it off half the time from then on.

So the answer to the question above is no. The block did not train anything that
lasted beyond the session. It corrected each session live, and the decline in the
first table was partly that and partly the model switch.

Two things make this less tidy.

**The rate did not stay up.** Broken down by Claude Code version, it fell across
the month: 56% on 2.1.241 and earlier (Aug 15 to 24), 34% on 2.1.243 to 2.1.251,
and 13% from 2.1.263 on (Sep 7 to 14). That is back at the block-on level, with no
block. I do not know why. I checked the Agent tool's model wording in the 2.1.251
and 2.1.263 binaries and found no relevant change, but prompt text served remotely
would not show up there. In late August I also added notes to my own skills telling
the model to always set one. And a handful of sessions a day is a small sample, so
daily figures swing hard. I am leaving the log running for another month.

**Version is a total confound.** Every block-on dispatch ran on an older Claude
Code build than every block-off dispatch. Nothing here separates "block removed"
from the dozens of other releases in between. The within-session split shows what
the block was doing while it ran. Whether its absence is what raised the rate
afterwards is exactly what the version confound leaves open.

A second reader re-derived these numbers from the raw transcripts with separate
scripts before seeing mine. The same-model rates matched to within one dispatch.
One figure did not reproduce: the Opus 4.8 first-half rate comes out anywhere from
23% to 28% depending on how blocked retries are collapsed, which is why none of
the tables above depend on it.

## What I would do now

Downgrade the block to a backstop. On second-half numbers it fires on about 15% of
dispatches and returns the default answer 99% of the time. Populate a silent-default
table for the common agent types and keep the block for whatever is left.

The hook in this repo is the version that produced the data above, unchanged.
`SILENT_DEFAULTS` is empty in it, which is what the measurement describes. Filling
it in is the change I am recommending, not one I made before publishing, so that
the numbers and the code match.

There is also a cost I did not anticipate and did not measure until I went looking.
In 8 cases the same prompt was blocked repeatedly before a model was finally set,
once **five times in 51 seconds**. A block does not reliably produce compliance on
the first try, and that tail does not show up in a per-day average.

## Install

1. Copy `agent-model-gate.py` to `~/.claude/hooks/`.
2. Make it executable.
3. Register it in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Agent",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/hooks/agent-model-gate.py" }
        ]
      }
    ]
  }
}
```

It fails open. A parse error, an unexpected payload or any exception all exit 0 and
let the dispatch through. A hook that gates every delegation must never be the reason
delegation stops working.

Two dicts at the top of the file control it:

- `SKIP_AGENT_TYPES` lists agent types whose model the harness already fixes. These
  are never blocked, because there is no decision to make.
- `SILENT_DEFAULTS` maps an agent type to a model. Those dispatches get the model
  injected via `updatedInput` rather than blocked. This dict ships empty, which is
  the state the measurement describes.

One note on the skip list. In the version published here it works, verified by unit
test and by confirming registration on the `Agent` matcher. During the measurement
window, two dispatches of a skip-listed type were blocked anyway, and the recovered
`measured-version.sh` explains why: it had no skip list at all and blocked every
modelless Agent call unconditionally. It also had no silent-default path, so nothing
was ever auto-filled and the counts above are not diluted by silent substitutions.

## Four things worth knowing before you write your own

Verified against Claude Code 2.1.232 unless noted.

**1. The Agent tool's `model` enum is strictly narrower than the session's.** The
tool schema is:

```js
model: Nr(["sonnet","opus","haiku","fable"]).optional()
```

while the session-level alias list also accepts `best`, `sonnet[1m]`, `opus[1m]`,
`fable[1m]` and `opusplan`. You cannot dispatch a subagent to `opus[1m]` or
`opusplan` even though both are valid models for your own session.

**2. There is no way to say "leave this one alone" by injecting a value.**
`updatedInput` is re-validated against the tool's input schema. Injecting
`"inherit"` or a full model ID does not pass through; it denies the spawn. To leave
a dispatch untouched, omit the field entirely.

Two attribution notes, kept separate because they are different strengths of
evidence. The re-validation behaviour is reported by `vietairs` in
[issue #43869](https://github.com/anthropics/claude-code/issues/43869), which is also
the best independent confirmation that `updatedInput` works on the Agent tool at all.
The enum in point 1 I verified directly against the binary.

**3. Use exit code 2, not `permissionDecision: "deny"`.** Exit 2 sends stderr back to
the model. The model reads it and re-issues the call with a choice. A deny returns no
such text, so it is a wall rather than a prompt to think.

**4. If more than one of your `PreToolUse` hooks returns `updatedInput` for the
same call, merge order is undocumented.** Flagged as a known limitation by
[claude-model-router-hook](https://github.com/tzachbon/claude-model-router-hook).

## A trap in shadowing built-in agents

Related, and the reason I went into the binary.

You can override a built-in agent by defining one with the same name in
`~/.claude/agents/`. The docs mention this exactly once, in an `Explore`-specific
example. What they do not say is that the override is wholesale: your definition
replaces the built-in's description, tools and system prompt together.

For most built-ins that is merely inconvenient. For the `claude` catch-all it is
worse, because that agent is the only built-in carrying an internal
`appendSystemPrompt` flag. In 2.1.232 the system-prompt assembly branches on it:

```js
// mainThreadAgentDefinition path
let a = e ? e.getSystemPrompt() : void 0;
if (a && e?.appendSystemPrompt) return Df([...base, a, ...]);  // base THEN agent prompt
return Df([...a ? [a] : base, ...]);                            // agent prompt INSTEAD OF base
```

The flag is the branch selector between appending to the base prompt and replacing
it. No frontmatter field reproduces it. A user-scope agent named `claude` takes the
second branch and silently drops the base prompt the built-in was appending to.

Scope this carefully if you repeat it: the parameter is `mainThreadAgentDefinition`,
so this is the main-thread agent path, not the subagent spawn path. And field names
in a minified bundle churn between releases, so the durable version of the finding
is the behaviour, which you can test. Shadow a built-in and check whether you kept
its base prompt.

I have not found this documented anywhere. It is absent from the most complete
public extraction of Claude Code internals I could find
([Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts),
515+ files), though that extraction's serializer emits a fixed field list which
structurally cannot include it, so its absence there is consistent with the finding
rather than independent proof of it.

## Why you have probably not read about any of this

I went looking for prior art. There is a cluster of issues on `anthropics/claude-code`
reporting versions of the subagent model problem, filed independently over roughly
nine months. Every one I checked has the same shape:

| Issue | State |
|---|---|
| [#13858](https://github.com/anthropics/claude-code/issues/13858) | closed, not planned, locked |
| [#16594](https://github.com/anthropics/claude-code/issues/16594) | closed, not planned, locked |
| [#24160](https://github.com/anthropics/claude-code/issues/24160) | closed, not planned, locked |
| [#25546](https://github.com/anthropics/claude-code/issues/25546) | closed as duplicate, locked |

The mechanism is automated. A bot detects duplicates against earlier issues, closes
in three days, locks after seven days of inactivity. #25546 was closed four days
after filing as a duplicate of #16594, which was itself already closed as not
planned.

The problem gets rediscovered every few weeks and no canonical thread accumulates.
This isn't obscurity. It's a venue that cannot hold a reference.

[#55144](https://github.com/anthropics/claude-code/issues/55144) is the closest
anyone came to proposing a sanctioned fix, a `PreAgentSpawn` hook returning a
routing decision. It argued the principle this hook was built on: "Claude treats the
response as advisory but must notify the caller when overriding and explain why.
Silent overrides defeat the purpose." Closed as not planned on 2026-05-31.

## How this differs from the model routers

[claude-model-router-hook](https://github.com/tzachbon/claude-model-router-hook) is
the only published project I found that actually routes subagent models per
dispatch. It classifies with heuristics first and falls back to a headless
`claude -p --model haiku` call for ambiguous cases, caching by prompt hash. If you
want automatic routing, start there.

[model-matchmaker](https://github.com/coyvalyss1/model-matchmaker) is more popular
but its Claude Code Agent hook is telemetry only. It classifies, writes an audit
line and exits without touching `tool_input.model`. Its stars belong to the Cursor
product bundled in the same repo.

Matchmaker states the opposing position plainly in its own README: "The classifier
is pure bash regex. Claude never decides its own model or effort level." That is a
defensible design, and on the evidence here it is the better one for cost. Every
router removes the model from the decision. This hook put the model into the
decision on purpose, and the decision it produced was the same one the router would
have made 99 times out of 100.

## Limits

- **One person, one workload, 30 days, no control group.** The 82.7% voluntary rate
  is my sessions, not a benchmark.
- **The training question now has an answer, but not a clean causal one.** Turning
  the block off answered "did it train anything durable" (no). The block-off month
  also ran on newer Claude Code builds than the block-on month, with no overlap, so
  the hook change and everything else in those releases cannot be separated.
- **I have not shown that a classifier would do worse than the model's own
  judgment.** My objection to prompt-string classification is that a classifier sees
  the prompt but not why the parent chose to delegate. That is reasoning, not
  measurement. Rayline's
  [Agent Router Bench](https://rayline.ai/agent-router-bench) is scoped to exactly
  this question and had not published results at the time of writing.
- **Version-bound.** Everything about internals is 2.1.232. Re-check before relying
  on it.
- **The shipped hook is not the measured hook.** See the block-message section. The
  data describes `measured-version.sh`; the installable file has different wording
  and no measurement behind it.
- **The measurement corrected itself three times.** My first count was 507
  dispatches; it double-counted block-and-retry pairs. My second attributed 92
  forced dispatches; the real figure is 68, because 8 prompts were blocked
  repeatedly before succeeding. My third error was assuming the hook was constant
  and that its wording was neutral, which I only checked by pulling old versions off
  a backup drive after the analysis was written. The first two inflated the hook's
  apparent activity. The third would have let me report a steered result as a
  finding. A measurement of your own tool, by you, fails in that direction.

## License

MIT.
