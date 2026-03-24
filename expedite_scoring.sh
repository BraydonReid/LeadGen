#!/bin/bash
# Expedite AI scoring — calls the score-leads endpoint in a tight loop
# Runs batches of 500 concurrently until all leads are scored
# Usage: bash expedite_scoring.sh
# Stop with Ctrl+C

BATCH=500
URL="http://localhost:8000/api/internal/score-leads?batch_size=$BATCH"

echo "[$(date)] Starting expedite scoring loop (batch=$BATCH)"

while true; do
    RESULT=$(curl -s -X POST "$URL")
    SCORED=$(echo "$RESULT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('scored',0))" 2>/dev/null)

    if [ "$SCORED" = "0" ]; then
        echo "[$(date)] All leads scored! Done."
        break
    fi

    # Check total remaining
    STATUS=$(curl -s http://localhost:8000/api/internal/status)
    TOTAL=$(echo "$STATUS" | python -c "import sys,json; d=json.load(sys.stdin); print(d['leads']['total'])" 2>/dev/null)
    DONE=$(echo "$STATUS" | python -c "import sys,json; d=json.load(sys.stdin); print(d['leads']['ai_scored'])" 2>/dev/null)
    PCT=$(echo "$STATUS" | python -c "import sys,json; d=json.load(sys.stdin); print(d['leads']['ai_scored_pct'])" 2>/dev/null)

    echo "[$(date)] Scored $SCORED this batch | $DONE/$TOTAL total ($PCT%)"
    sleep 2
done
