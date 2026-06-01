#!/bin/bash
# Database Bridge Diagnostic - Quick Start

set -e

echo "════════════════════════════════════════════════════════════"
echo "  Database Bridge Diagnostic Tool"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if docker-compose is running
if ! docker-compose ps | grep -q "monitoring-app"; then
    echo "❌ ERROR: Container not running!"
    echo "   Run: docker-compose up -d"
    exit 1
fi

echo "✅ Container is running"
echo ""

# Step 1: Check latest extraction file
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Check Latest Extraction File"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

LATEST_FILE=$(docker exec monitoring-app ls -1 /app/extractions/*.json 2>/dev/null | tail -1 || echo "")

if [ -z "$LATEST_FILE" ]; then
    echo "⚠️  No extraction files found. Triggering extraction..."
    curl -s -X POST http://localhost:8484/api/refresh > /dev/null
    sleep 3
    LATEST_FILE=$(docker exec monitoring-app ls -1 /app/extractions/*.json 2>/dev/null | tail -1 || echo "")
fi

if [ -n "$LATEST_FILE" ]; then
    FILE_NAME=$(basename "$LATEST_FILE")
    echo "✅ Latest extraction: $FILE_NAME"
    echo ""

    # Show parsed_data count
    PARSED_COUNT=$(docker exec monitoring-app python3 << 'EOFPY'
import json
import glob
import os
latest = sorted(glob.glob('/app/extractions/*.json'))[-1]
with open(latest) as f:
    data = json.load(f)
print(len(data.get('parsed_data', [])))
EOFPY
)

    MAPPED_COUNT=$(docker exec monitoring-app python3 << 'EOFPY'
import json
import glob
latest = sorted(glob.glob('/app/extractions/*.json'))[-1]
with open(latest) as f:
    data = json.load(f)
print(len(data.get('extracted_individual_models', [])))
EOFPY
)

    echo "   Parsed items (from Ollama):    $PARSED_COUNT"
    echo "   Mapped items (to database):    $MAPPED_COUNT"

    if [ "$MAPPED_COUNT" -eq 0 ] && [ "$PARSED_COUNT" -gt 0 ]; then
        echo ""
        echo "   🔴 MAPPING FAILED: No models matched!"
        echo "      See: DEBUG_DATABASE_BRIDGE.md - Step 5"
    elif [ "$MAPPED_COUNT" -gt 0 ]; then
        echo ""
        echo "   ✅ Mapping successful!"
    fi
else
    echo "❌ No extraction files found"
    exit 1
fi

echo ""

# Step 2: Check database
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Check Database Content"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker exec monitoring-app python3 << 'EOFPY'
import sqlite3
conn = sqlite3.connect('/app/devices.db')
cur = conn.cursor()

# Count non-null versions
cur.execute('SELECT COUNT(*) FROM devices WHERE stored_version IS NOT NULL')
count = cur.fetchone()[0]

print(f"Devices with versions: {count}")

if count > 0:
    print("\nStored versions:")
    cur.execute('SELECT model, stored_version, stored_release_date FROM devices WHERE stored_version IS NOT NULL')
    for row in cur.fetchall():
        print(f"  - {row[0]:12} → v{row[1]} ({row[2]})")
else:
    print("\n⚠️  No versions in database!")

conn.close()
EOFPY

echo ""

# Step 3: Check logs for errors
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Check Recent Logs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "Last 20 lines (filtered):"
docker-compose logs monitoring-app 2>/dev/null | grep -E "\[UTILS\]|\[DB\]|\[EXTRACTION\]" | tail -20 || echo "No matching logs found"

echo ""

# Step 4: Quick recommendation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Recommendation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$MAPPED_COUNT" -eq 0 ]; then
    echo "❌ Problem: Mapping is failing"
    echo ""
    echo "Next steps:"
    echo "1. Check extracted text:"
    echo "   docker exec -it monitoring-app bash"
    echo "   cat /app/extractions/$FILE_NAME | jq '.parsed_data[0].model'"
    echo ""
    echo "2. Update DESCRIPTION_TO_MODEL in monitor_config.py"
    echo ""
    echo "3. Rebuild:"
    echo "   docker-compose down && docker-compose build --no-cache && docker-compose up -d"
elif [ "$count" -eq 0 ]; then
    echo "⚠️  Problem: Mapping works but database insert failed"
    echo ""
    echo "Next steps:"
    echo "1. Check database schema:"
    echo "   docker exec -it monitoring-app sqlite3 /app/devices.db '.schema devices'"
    echo ""
    echo "2. Check recent logs for [DB] errors"
else
    echo "✅ Everything looks good!"
    echo ""
    echo "Your database has been updated with extracted versions."
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "For detailed troubleshooting, see:"
echo "  - DATABASE_BRIDGE_FIX_SUMMARY.md"
echo "  - DEBUG_DATABASE_BRIDGE.md"
echo "  - ENHANCED_LOGGING_GUIDE.md"
echo "════════════════════════════════════════════════════════════"
