# Database Bridge Debug Guide

## The Issue Breakdown

```
✅ Vision/Ollama produces correct JSON
    ↓
✅ JSON saved to /app/extractions/
    ↓
❌ extract_individual_models() mapping fails silently
    ↓
❌ Returns [] (empty list)
    ↓
❌ store_version() is never called
    ↓
❌ Database stays EMPTY (null values)
```

---

## Step 1: Check Recent Extraction File

When you trigger extraction, a JSON file is created. Check the **last one created**:

```bash
# SSH into container
docker exec -it monitoring-app bash

# Find latest extraction file
ls -lart /app/extractions/ | tail -1

# View it
cat /app/extractions/extraction_[LATEST_TIMESTAMP].json | jq .
```

**What to look for:**
```json
{
  "parsed_data": [
    {
      "model": "High Definition Core Aligning Fusion Splicer",
      "version": "1.32",
      "release_date": "9 Jul, 2025"
    }
  ],
  "grouped_versions": [...],
  "extracted_individual_models": [
    {
      "model": "T-72C+",  // ← Should be mapped code, not description
      "version": "1.32"
    }
  ]
}
```

**If `extracted_individual_models` is empty `[]`:**
→ The mapping is FAILING (see Step 2)

**If it has correct models like `T-72C+`:**
→ Go to Step 3 (database insert is failing)

---

## Step 2: Test the Mapping Function

The mapping happens in `utils.py` → `extract_individual_models()`.

### Check DESCRIPTION_TO_MODEL Dictionary

```bash
docker exec -it monitoring-app python3 << 'EOF'
from monitor_config import DESCRIPTION_TO_MODEL

print("Available descriptions in DESCRIPTION_TO_MODEL:")
for desc, model in DESCRIPTION_TO_MODEL.items():
    print(f"  '{desc}' → '{model}'")
EOF
```

Expected output:
```
Available descriptions in DESCRIPTION_TO_MODEL:
  'High Definition Core Aligning Fusion Splicer' → 'T-72C+'
  'Core Alignment Fusion Splicer' → 'T-57C+'
  ...
```

### Test the Mapping Directly

```bash
docker exec -it monitoring-app python3 << 'EOF'
from utils import extract_individual_models
from monitor_config import DEVICES_TO_MONITOR

# Simulate what Ollama extracted
test_data = [
    {
        "model": "High Definition Core Aligning Fusion Splicer",
        "version": "1.32",
        "release_date": "9 Jul, 2025"
    }
]

result = extract_individual_models(test_data, DEVICES_TO_MONITOR)
print(f"\nInput: {test_data}")
print(f"\nOutput: {result}")
print(f"\nSuccess: {len(result) > 0}")
EOF
```

**If output is `[]`:**
→ The description string doesn't match. Check case sensitivity or exact text match in monitor_config.py

---

## Step 3: Test Database INSERT/UPDATE

Now with enhanced logging, every call to `store_version()` will log exactly what's happening.

### Trigger Manual Extraction

```bash
curl -X POST http://localhost:8484/api/refresh
```

### Check the Logs

```bash
docker-compose logs -f monitoring-app | grep -E "\[DB\]|\[EXTRACTION\]|\[UTILS\]"
```

**Look for:**

✅ **SUCCESS CASE:**
```
[UTILS] Item 0: model='High Definition Core Aligning Fusion Splicer', version='1.32'
[UTILS] ✅ MATCH: 'High Definition Core Aligning Fusion Splicer' -> 'T-72C+'
[UTILS] ✅ INSERTED into individual_models: model=T-72C+, version=1.32
[EXTRACTION] Processing: model='T-72C+', version='1.32'
[DB] ▶️  store_version() called: model='T-72C+', version='1.32'
[DB]   ✅ VERIFIED: model='T-72C+' now has version='1.32'
[DB]   ✅ COMMIT successful
```

❌ **FAILURE CASE #1: No mapping match**
```
[UTILS] Item 0: model='High Definition Core Aligning Fusion Splicer', version='1.32'
[UTILS] ⚠️  NO DESCRIPTION MATCH for: 'High Definition Core Aligning Fusion Splicer'
[UTILS] ❌ FAILED TO MATCH: 'High Definition Core Aligning Fusion Splicer'
[EXTRACTION] ║ About to store 0 models in database
```
→ Fix: Update `DESCRIPTION_TO_MODEL` in monitor_config.py

❌ **FAILURE CASE #2: Database error**
```
[EXTRACTION] Processing: model='T-72C+', version='1.32'
[DB] ▶️  store_version() called: model='T-72C+', version='1.32'
[DB]   ❌ CRITICAL ERROR in store_version: [SQL error message]
```
→ Check database schema and permissions

---

## Step 4: Manual Database Test

Insert data directly to test the database layer:

```bash
docker exec -it monitoring-app python3 << 'EOF'
import sqlite3
import os

DB_PATH = '/app/devices.db'
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Insert test
cur.execute(
    'INSERT INTO devices (model, stored_version, stored_release_date, last_checked) VALUES (?, ?, ?, ?)',
    ('T-72C+', '1.32', '2025-07-09', '2026-04-28')
)
conn.commit()

# Verify
cur.execute('SELECT * FROM devices WHERE model = ?', ('T-72C+',))
result = cur.fetchone()
print(f"Inserted: {result}")

conn.close()
EOF
```

Then check:
```bash
curl http://localhost:8484/api/status | jq '.devices[] | select(.model == "T-72C+")'
```

---

## Step 5: The Fix (If Mapping is the Problem)

If descriptions don't match, update `monitor_config.py`:

```python
# Get the EXACT description from Ollama logs
# Then add it to DESCRIPTION_TO_MODEL

DESCRIPTION_TO_MODEL = {
    'High Definition Core Aligning Fusion Splicer': 'T-72C+',
    'YOUR_EXACT_OLLAMA_TEXT_HERE': 'T-57C+',  # Add missing mappings
    # ...
}
```

Then rebuild:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## Step 6: Enable SQL Debug (Optional)

For SQL-level debugging, add this to store_version():

```python
# Enable SQL tracing
conn.set_trace_callback(logging.debug)
```

---

## Quick Diagnostic Script

Run this to get instant feedback:

```bash
docker exec -it monitoring-app python3 << 'EOF'
import sqlite3
import json
from pathlib import Path

print("\n=== DATABASE BRIDGE DIAGNOSTIC ===\n")

# 1. Check latest extraction
extractions_dir = Path('/app/extractions')
if extractions_dir.exists():
    latest = sorted(extractions_dir.glob('*.json'))[-1]
    with open(latest) as f:
        data = json.load(f)
    
    print(f"Latest extraction: {latest.name}")
    print(f"  Parsed items: {len(data.get('parsed_data', []))}")
    print(f"  Mapped items: {len(data.get('extracted_individual_models', []))}")
    
    if data.get('extracted_individual_models'):
        print("\n  Mapped models:")
        for item in data.get('extracted_individual_models', []):
            print(f"    - {item['model']} v{item['version']}")
    else:
        print("\n  ❌ MAPPING FAILED: No models extracted")
else:
    print("No extractions directory")

# 2. Check database
db_path = '/app/devices.db'
if Path(db_path).exists():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT model, stored_version FROM devices WHERE stored_version IS NOT NULL')
    rows = cur.fetchall()
    
    print(f"\nDatabase: {len(rows)} devices with versions")
    if rows:
        for model, version in rows:
            print(f"  - {model}: v{version}")
    else:
        print("  ⚠️  No versions stored!")
    
    conn.close()

print("\n=== END DIAGNOSTIC ===\n")
EOF
```

---

## Summary: The Three Likely Culprits

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Mapping mismatch** | `extracted_individual_models: []` in JSON file | Add exact Ollama output to `DESCRIPTION_TO_MODEL` |
| **Database schema** | SQL error in logs | Check table structure with `PRAGMA table_info(devices);` |
| **Permission issue** | "attempt to write a readonly database" | Check `/app/devices.db` permissions (should be 666) |

Run the diagnostic script above to identify which one applies to you.
