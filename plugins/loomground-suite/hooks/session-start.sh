#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
#
# Claude Code SessionStart hook for the loomground-suite plugin.
#
# The plugin's .mcp.json / plugin.json mcpServers block launches `loomground-mcp`
# unconditionally. If the loomground runtime has never been installed (or the
# active interpreter is outside its supported range), that MCP server start
# fails silently from the user's point of view. This hook gives an actionable
# message instead, without touching the mcpServers configuration itself.
#
# POSIX sh only (no bash-isms, no python): Claude Code on Windows runs plugin
# hooks through Git Bash, which does not guarantee a Python interpreter is
# present -- and "Python missing" is itself one of the cases this hook must
# report, so the hook cannot depend on Python to detect that.
#
# The "3.12" minimum-Python label below is a literal copy of the "minimum"
# entry in runtime/runtime-sources.json (the single source of truth for the
# supported runtime range). tests/test_suite_runtime_hook.py asserts this
# literal stays in sync with that file; update both together.
PYTHON_MINIMUM_LABEL="3.12"

# Silent, successful no-op when the runtime is already on PATH.
if command -v loomground-mcp >/dev/null 2>&1; then
  exit 0
fi

MESSAGE="Loomground runtime not installed: run \`loomground onboard\` (Python ${PYTHON_MINIMUM_LABEL} required)"

# SessionStart hook output shape per Claude Code's plugin-dev hook-development
# skill (Hook Output Format / SessionStart sections) and the shipped
# learning-output-style plugin's SessionStart hook, which both use
# hookSpecificOutput.additionalContext to feed context into the session, and
# the doc's "Standard Output (All Hooks)" schema, which carries systemMessage.
# Both are emitted here so the message reaches whichever channel Claude Code
# actually surfaces to the person (systemMessage) and to the model's context
# (additionalContext), rather than assuming a single field.
cat <<EOF
{"systemMessage": "${MESSAGE}", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "${MESSAGE}"}}
EOF

exit 0
