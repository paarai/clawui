#!/bin/bash
# Run e2e test and send result to user via openclaw agent
LOG="/tmp/e2e_test.log"
SCRIPT="/home/hung/.openclaw/workspace/test_e2e.py"

python3 "$SCRIPT" 2>&1 | tee "$LOG"
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    MSG="✅ E2E Test passed: AT-SPI and X11 backends working."
else
    MSG="❌ E2E Test failed (code $EXIT_CODE). See log: /tmp/e2e_test.log"
fi

# Send notification via openclaw (use system event to post to main session)
# Using openclaw system event to enqueue to main heartbeat
openclaw system event --mode now --text "$MSG" 2>/dev/null || true

exit $EXIT_CODE
