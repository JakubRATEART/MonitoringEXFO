#!/bin/bash
# Test script to verify extraction and database insertion works in Docker

echo "=== Testing Sumitomo Device Version Extraction ==="
echo ""

# 1. Check database before
echo "1. Database state BEFORE extraction:"
docker exec version-monitor2 sqlite3 /app/devices.db ".mode column" ".headers on" "SELECT model, stored_version, stored_release_date FROM devices WHERE model LIKE 'T-%';"

echo ""
echo "2. Running extraction trigger..."
docker exec version-monitor2 python -c "
from pdf_scheduler import PDFScheduler
import sys
s = PDFScheduler('https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf')
try:
    s.trigger_now()
    print('Extraction completed')
    sys.stdout.flush()
except Exception as e:
    print(f'Extraction failed: {e}', file=sys.stderr)
    sys.stderr.flush()
" 2>&1

echo ""
echo "3. Database state AFTER extraction:"
docker exec version-monitor2 sqlite3 /app/devices.db ".mode column" ".headers on" "SELECT model, stored_version, stored_release_date FROM devices WHERE model LIKE 'T-%';"

echo ""
echo "4. Checking if data was inserted:"
docker exec version-monitor2 sqlite3 /app/devices.db "SELECT COUNT(*) as total_with_versions FROM devices WHERE stored_version IS NOT NULL;"
