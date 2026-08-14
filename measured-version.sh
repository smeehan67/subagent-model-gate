#!/bin/bash
# THE VERSION THE 30-DAY MEASUREMENT ACTUALLY RAN.
#
# Recovered from a Time Machine snapshot on 2026-08-14. It was never a file: it
# lived as an inline `command` string in ~/.claude/settings.json under a PreToolUse
# hook with matcher "Agent", which is why it left no trace in the hooks directory
# and no git history.
#
# Verified byte-identical (sha256 prefix 57f3073d42f3, 619 bytes) across snapshots
# dated 2026-07-06, 07-14, 07-21, 07-28, 08-05 and 08-12, so it was unchanged for
# the whole measurement window and for a week before it.
#
# READ THE MESSAGE BELOW BEFORE TRUSTING THE HEADLINE RESULT. It names sonnet as
# "default for most subagent work" and restricts opus to "genuine multi-step
# reasoning only". The measurement found 67 of 68 forced dispatches chose sonnet
# and none chose opus. This wording is a plausible cause of that, and the README
# says so. The shipped agent-model-gate.py carries deliberately different wording
# that has NOT been measured.
#
# Differences from the shipped version, all of which matter for reading the data:
#   - no skip list, so it blocked every modelless Agent call including
#     claude-code-guide and statusline-setup
#   - no silent-default path, so nothing was ever auto-filled
#   - a message that steers toward sonnet rather than warning against reflexive
#     sonnet
#
# The last line of the message refers to a private note that is not part of this
# repository. It is kept because this file is a verbatim recovery and editing it
# would defeat the purpose of preserving it.

model=$(jq -r '.tool_input.model // empty')
if [ -z "$model" ]; then
    printf '
*** SUBAGENT MODEL NOT SPECIFIED. DISPATCH BLOCKED. ***

No `model` parameter was set on this Agent call, so it would inherit the parent (Opus). That is wasteful for most subagent work.

Pick a model and re-issue the Agent tool call:
  - model: "sonnet"  for research, triage, dump-summarization, codebase search (default for most subagent work)
  - model: "haiku"   for light dump processing, simple lookups
  - model: "opus"    for genuine multi-step reasoning only

See memory: subagent-dispatch-defaults.md.
' >&2
    exit 2
fi
