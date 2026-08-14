#!/usr/bin/env python3
"""PreToolUse(Agent): force a deliberate subagent model choice.

WHY THIS BLOCKS RATHER THAN DEFAULTS.

Subagents inherit the parent session's model, so with Opus in the chair a trivial
grep runs on Opus. The obvious fix is a silent default, and Claude Code ships two:
`model:` frontmatter on an agent definition, and CLAUDE_CODE_SUBAGENT_MODEL. Both
were tried and both are the wrong tool here.

A silent default does not solve the actual problem. The problem is not "the model
is Opus", it is "nobody decided". A default replaces an unconsidered Opus with an
unconsidered Sonnet, which is cheaper and still unconsidered, and it silently
downgrades the cases that genuinely warranted Opus.

Measured over 30 days, 507 dispatches:
  - 372 chose sonnet   (93% of dispatches that specified)
  - 28 chose opus      (7%, real judgment calls, correctly escalated)
  - 2 chose haiku
  - ~98 blocked by this hook, about 3.3 per day

A silent Sonnet default would have converted those 28 Opus calls into Sonnet with
nobody noticing. An earlier version of this hook did exactly that and was reverted.

WHY exit 2 RATHER THAN permissionDecision:"deny": exit 2 feeds stderr back to the
model as actionable feedback, which is what makes it re-issue the call with a
choice. A deny is a wall, not a prompt to think.

SKIP_AGENT_TYPES: agent types whose model the harness already fixes, where no
decision exists and a block would be pure friction.

SILENT_DEFAULTS: types where the answer is unambiguous enough that deliberation
adds nothing. These get filled in via updatedInput instead of blocked. Empty by
default, deliberately. {"Explore": "haiku"} is the obvious candidate, but that is
a preference rather than an obvious win, so it stays opt-in.

MIT licensed.
"""

import json
import sys

# Types the harness already pins. No decision exists; do not interrupt.
# statusline-setup ships with model:"sonnet" hardcoded in the binary.
SKIP_AGENT_TYPES = {"claude-code-guide", "statusline-setup"}

# Types where the answer is unambiguous enough to fill in silently.
# Format: {"Explore": "haiku"}. Empty means every other type gets the block.
# Only the bare tiers are valid here: sonnet, opus, haiku, fable.
# "inherit" and full model IDs fail schema re-validation and deny the spawn.
SILENT_DEFAULTS: dict[str, str] = {}

MESSAGE = """
*** SUBAGENT MODEL NOT SPECIFIED. DISPATCH BLOCKED. ***

No `model` was set on this Agent call, so the subagent would inherit the parent
session's model. That is usually the expensive one, and usually wasteful.

This block exists to make you CHOOSE, not to make you pick Sonnet. Re-issue the
call with the model that fits the work:

  - model: "haiku"   light dump processing, simple lookups, mechanical extraction
  - model: "sonnet"  research, triage, summarisation, codebase search
                     (the right answer roughly 9 times out of 10)
  - model: "opus"    genuine multi-step reasoning, ambiguous judgment, work whose
                     output you would not trust from a smaller model

Do not reflexively pick sonnet. If this task actually needs Opus-level judgment,
say so and pass model: "opus". That is a correct outcome of this prompt, not a
failure of it.
"""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open: never block on a parsing problem

    if payload.get("tool_name") != "Agent":
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    if tool_input.get("model"):
        return 0  # a deliberate choice was made; that is the goal

    agent_type = tool_input.get("subagent_type")
    if agent_type in SKIP_AGENT_TYPES:
        return 0

    if agent_type in SILENT_DEFAULTS:
        updated = dict(tool_input)
        updated["model"] = SILENT_DEFAULTS[agent_type]
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": updated,
                }
            },
            sys.stdout,
        )
        return 0

    sys.stderr.write(MESSAGE)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail open
