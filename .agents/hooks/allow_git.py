"""PreToolUse hook to auto-allow read-only git commands."""
from __future__ import annotations

import json
import re
import sys

READONLY_GIT_PATTERN = re.compile(
    r"^git\s+(status|log|show|diff|branch|tag|rev-parse|describe|remote|check-ignore|ls-files)(\s.*)?$",
    re.IGNORECASE,
)


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            print(json.dumps({"decision": "ask"}))
            return

        payload = json.loads(raw_input)
        tool_call = payload.get("toolCall", {})
        command_line = tool_call.get("args", {}).get("CommandLine", "").strip()

        if READONLY_GIT_PATTERN.match(command_line):
            print(json.dumps({"decision": "allow", "reason": "Read-only git command authorized automatically."}))
        else:
            print(json.dumps({"decision": "ask"}))
    except Exception:
        print(json.dumps({"decision": "ask"}))


if __name__ == "__main__":
    main()
