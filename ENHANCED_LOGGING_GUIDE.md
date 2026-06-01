# Enhanced Logging Summary - Database Bridge Debug

## What Was Changed

### 1. `utils.py` → `extract_individual_models()`

**Added detailed logging at each step:**

```
[UTILS] Processing Item #0: 'High Definition Core Aligning Fusion Splicer' v1.32
[UTILS] Model string (lowercase): 'high definition core aligning fusion splicer'
[UTILS] Attempting DESCRIPTION_TO_MODEL mapping...
[UTILS]   Comparing: 'high definition core aligning fusion splicer' (match_1=True, match_2=False)
[UTILS] ✅ MATCH: 'High Definition Core Aligning Fusion Splicer' -> 'T-72C+'
[UTILS] ✅ INSERTED into individual_models: model=T-72C+, version=1.32
```

**Logs show:**
- ✅ Each item being processed
- ✅ Each description comparison (which ones match)
- ✅ Whether mapping succeeded or failed
- ✅ Final count of matched models

### 2. `app.py` → `store_version()`

**Added database verification logging:**

```
[DB] ▶️  store_version() called: model='T-72C+', version='1.32', release_date='9 Jul, 2025'
[DB]   Current DB state: model='T-72C+' -> version='1.10'
[DB]   Version changed! Updating: 1.10 -> 1.32
[DB]   UPDATE executed, rows affected: 1
[DB]   ✅ VERIFIED: model='T-72C+' now has version='1.32', date='2025-07-09'
[DB]   ✅ COMMIT successful
```

**Logs show:**
- ✅ What version was previously stored
- ✅ Whether it's INSERT or UPDATE
- ✅ How many rows were affected
- ✅ Verification that the write succeeded
- ✅ Whether commit succeeded

### 3. `app.py` → `/api/refresh` endpoint

**Added extraction flow summary:**

```
[EXTRACTION] ╔════════════════════════════════════════════════════════════
[EXTRACTION] ║ About to store 2 models in database
[EXTRACTION] ╚════════════════════════════════════════════════════════════
[EXTRACTION] Processing: model='T-72C+', version='1.32'
[EXTRACTION] ✅ Successfully stored: T-72C+ -> 1.32
[EXTRACTION] Processing: model='T-57C+', version='1.10'
[EXTRACTION] ✅ Successfully stored: T-57C+ -> 1.10
```

**Logs show:**
- ✅ How many models are about to be stored
- ✅ Each model being processed
- ✅ Success or failure for each one

---

## How to Use the Enhanced Logging

### Run an Extraction and Watch Logs

**Terminal 1: Trigger extraction**
```bash
curl -X POST http://localhost:8484/api/refresh
```

**Terminal 2: Watch logs (REAL-TIME)**
```bash
docker-compose logs -f monitoring-app | grep -E "\[UTILS\]|\[DB\]|\[EXTRACTION\]"
```

### Example Output (SUCCESS)
```
[UTILS] ═══════════════════════════════════════════════════════════
[UTILS] Processing Item #0: 'High Definition Core Aligning Fusion Splicer' v1.32
[UTILS] Model string (lowercase): 'high definition core aligning fusion splicer'
[UTILS] Attempting DESCRIPTION_TO_MODEL mapping...
[UTILS] ✅ MATCH: 'High Definition Core Aligning Fusion Splicer' -> 'T-72C+'
[UTILS] ✅ INSERTED into individual_models: model=T-72C+, version=1.32
[UTILS] FINAL: Returning 1 models (from 1 input items)
[EXTRACTION] Processing: model='T-72C+', version='1.32'
[DB] ▶️  store_version() called: model='T-72C+', version='1.32'
[DB]   ✅ VERIFIED: model='T-72C+' now has version='1.32'
[DB]   ✅ COMMIT successful
[EXTRACTION] ✅ Successfully stored: T-72C+ -> 1.32
```

### Example Output (MAPPING FAILURE)
```
[UTILS] Processing Item #0: 'High Def Core Aligning Splicer' v1.32
[UTILS] Model string (lowercase): 'high def core aligning splicer'
[UTILS] Attempting DESCRIPTION_TO_MODEL mapping...
[UTILS]   Comparing: 'high definition core aligning fusion splicer' (match_1=False, match_2=False)
[UTILS] ⚠️  NO DESCRIPTION MATCH for: 'High Def Core Aligning Splicer'
[UTILS] Trying fallback: VARIANT matching...
[UTILS] ❌ FAILED TO MATCH: 'High Def Core Aligning Splicer' - No description or variant match found!
[UTILS] FINAL: Returning 0 models (from 1 input items)
[EXTRACTION] ║ About to store 0 models in database
```

---

## Finding the Exact Problem

### If "No models extracted" (Mapping Failed)

1. **Find what Ollama actually returned:**
```bash
docker exec -it monitoring-app bash
cat /app/extractions/extraction_[LATEST].json | jq '.parsed_data[0].model'
```

2. **Compare to your mapping dictionary:**
```bash
python3 << 'EOF'
from monitor_config import DESCRIPTION_TO_MODEL
print("Expected descriptions:")
for desc in DESCRIPTION_TO_MODEL.keys():
    print(f"  - {desc}")
EOF
```

3. **If they don't match exactly**, update `monitor_config.py`:
```python
DESCRIPTION_TO_MODEL = {
    'High Definition Core Aligning Fusion Splicer': 'T-72C+',  # ← EXACT TEXT from Ollama
    'High Def Core Aligning Splicer': 'T-72C+',  # ← ADD THIS if Ollama returns this
    # ...
}
```

### If Models Are Mapped But Database is Empty

Check database layer:
```bash
docker exec -it monitoring-app python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('/app/devices.db')
cur = conn.cursor()

# Check if T-72C+ exists
cur.execute('SELECT stored_version FROM devices WHERE model = ?', ('T-72C+',))
result = cur.fetchone()
print(f"T-72C+ in database: {result}")

# Check table structure
cur.execute('PRAGMA table_info(devices);')
print("\nTable structure:")
for row in cur.fetchall():
    print(f"  {row}")

conn.close()
EOF
```

---

## Rebuilding Container with Changes

```bash
# Stop
docker-compose down

# Remove old images (optional, for clean rebuild)
docker-compose build --no-cache

# Start with enhanced logging
docker-compose up -d

# View logs
docker-compose logs -f monitoring-app
```

---

## Key Log Prefixes

| Prefix | Means | Look for |
|--------|-------|----------|
| `[UTILS]` | Mapping/model extraction | ✅ MATCH or ❌ FAILED TO MATCH |
| `[DB]` | Database operations | ✅ VERIFIED and COMMIT or ❌ ERROR |
| `[EXTRACTION]` | Overall extraction flow | How many items at each stage |

---

## What These Logs Will Reveal

**✅ All working:**
```
[UTILS] FINAL: Returning 3 models
[EXTRACTION] About to store 3 models in database
[DB] ✅ VERIFIED for all 3 models
```

**❌ Mapping broken:**
```
[UTILS] FINAL: Returning 0 models  ← RED FLAG
[EXTRACTION] About to store 0 models in database
```

**❌ Database broken:**
```
[UTILS] FINAL: Returning 3 models  ← Good so far
[DB] ❌ CRITICAL ERROR: [SQL error]  ← Problem here
```

---

## Next Steps

1. **Rebuild container:**
   ```bash
   cd ~/Monitoring-2
   docker-compose down
   docker-compose build
   docker-compose up -d
   ```

2. **Trigger extraction and check logs:**
   ```bash
   curl -X POST http://localhost:8484/api/refresh
   docker-compose logs -f monitoring-app | grep -E "\[UTILS\]|\[DB\]|\[EXTRACTION\]"
   ```

3. **Look for the ✅ or ❌ symbols in the output**

4. **Based on what you see, follow DEBUG_DATABASE_BRIDGE.md for fixes**

The enhanced logging will show you EXACTLY where the disconnect happens! 🎯
