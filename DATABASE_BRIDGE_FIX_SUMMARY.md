# Database Bridge Debug - Complete Solution

## The Problem You Identified ✅

**Extraction works → JSON is saved → Database stays EMPTY**

This is a classic **mapping/bridge failure** where:
1. ✅ Ollama Vision extracts data correctly
2. ✅ JSON is saved to `/app/extractions/`
3. ❌ The mapping from description to model code fails
4. ❌ Database never gets called
5. ❌ `devices.db` remains empty

---

## What I Fixed

### 1. **Enhanced Logging in `utils.py`**
   - Shows EXACTLY which descriptions match/fail
   - Logs every comparison attempt
   - Shows final count of mapped models

### 2. **Enhanced Logging in `app.py` → `store_version()`**
   - Shows every INSERT/UPDATE call
   - Verifies data was written
   - Confirms COMMIT succeeded

### 3. **Enhanced Logging in `app.py` → `/api/refresh` endpoint**
   - Shows how many models at each stage
   - Logs success/failure for each insert

### 4. **Enhanced Logging in `pdf_scheduler.py`**
   - Same detailed logging for scheduled extractions

---

## How to Use the Fix

### Step 1: Deploy the Enhanced Code

```bash
cd ~/Monitoring-2

# Rebuild container with new logging
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify it's running
docker-compose ps
```

### Step 2: Trigger an Extraction

```bash
curl -X POST http://localhost:8484/api/refresh
```

### Step 3: Watch the Logs (Real-time)

**Terminal 1:**
```bash
docker-compose logs -f monitoring-app | grep -E "\[UTILS\]|\[DB\]|\[EXTRACTION\]|\[SCHEDULER\]"
```

### Step 4: Identify the Problem

Based on the logs, one of these is happening:

#### **Case A: Mapping Failed (UTILS shows ❌)**

**Logs will show:**
```
[UTILS] ⚠️  NO DESCRIPTION MATCH for: 'High Def Splicer'
[UTILS] ❌ FAILED TO MATCH
[UTILS] FINAL: Returning 0 models
```

**Fix:**
1. Get the EXACT text from logs: `'High Def Splicer'`
2. Add to `monitor_config.py`:
```python
DESCRIPTION_TO_MODEL = {
    'High Definition Core Aligning Fusion Splicer': 'T-72C+',  # Original
    'High Def Splicer': 'T-72C+',  # ADD THIS (exact match from logs)
}
```
3. Rebuild: `docker-compose down && docker-compose build --no-cache && docker-compose up -d`

#### **Case B: Mapping Succeeds but Database Fails (DB shows ❌)**

**Logs will show:**
```
[UTILS] ✅ MATCH: 'High Def...' -> 'T-72C+'
[UTILS] FINAL: Returning 1 models
[DB] ❌ CRITICAL ERROR in store_version: [SQL error]
```

**Fix:** Check database schema
```bash
docker exec -it monitoring-app bash
sqlite3 /app/devices.db ".schema devices"
```

Verify these columns exist:
```
model (PRIMARY KEY)
stored_version
stored_release_date
last_checked
acknowledged
```

#### **Case C: Everything Works (All ✅)**

**Logs will show:**
```
[UTILS] ✅ MATCH: 'High Def...' -> 'T-72C+'
[UTILS] FINAL: Returning 1 models
[EXTRACTION] ✅ Successfully stored: T-72C+ -> 1.32
[DB] ✅ VERIFIED: model='T-72C+' now has version='1.32'
[DB] ✅ COMMIT successful
```

**Verify in database:**
```bash
curl http://localhost:8484/api/status | jq '.devices[] | select(.model == "T-72C+")'
```

Should return your data!

---

## Log Interpretation Guide

### SUCCESS Indicator (✅)
```
[UTILS] ✅ MATCH
[EXTRACTION] ✅ Successfully stored
[DB] ✅ VERIFIED
[DB] ✅ COMMIT successful
```

### FAILURE Indicator (❌)
```
[UTILS] ❌ FAILED TO MATCH          ← Mapping problem
[DB] ❌ CRITICAL ERROR              ← Database problem
[EXTRACTION] About to store 0 models ← No models after mapping
```

### Log Format Quick Reference

```
[UTILS]       → Mapping/extraction logic
[DB]          → Database INSERT/UPDATE operations
[EXTRACTION]  → Top-level extraction flow
[SCHEDULER]   → Scheduled job (daily 9 AM)
```

---

## Complete Debugging Workflow

### Step 1: Check Raw Extraction File
```bash
docker exec -it monitoring-app bash
ls -lart /app/extractions/ | tail -1
cat /app/extractions/extraction_[TIMESTAMP].json | jq '.parsed_data[0]'
```

Look for: `"model": "exact text from Ollama"`

### Step 2: Check Mapping Dictionary
```bash
docker exec -it monitoring-app python3 << 'EOF'
from monitor_config import DESCRIPTION_TO_MODEL
for k, v in DESCRIPTION_TO_MODEL.items():
    print(f"  '{k}' → '{v}'")
EOF
```

Look for: Does your exact Ollama text match one of these?

### Step 3: Test Mapping Function
```bash
docker exec -it monitoring-app python3 << 'EOF'
from utils import extract_individual_models
from monitor_config import DEVICES_TO_MONITOR

# Use YOUR exact text from extraction file
test_input = [{"model": "High Definition Core Aligning Fusion Splicer", "version": "1.32"}]
result = extract_individual_models(test_input, DEVICES_TO_MONITOR)
print(f"Input:  {test_input[0]['model']}")
print(f"Output: {result}")
print(f"Success: {len(result) > 0}")
EOF
```

Look for: Does result contain mapped model like `'T-72C+'`?

### Step 4: Test Database Insert
```bash
docker exec -it monitoring-app python3 << 'EOF'
from app import store_version
store_version('T-72C+', '1.32', '2025-07-09')
# Check logs for [DB] messages
EOF
```

Then verify:
```bash
curl http://localhost:8484/api/status
```

---

## If You Find A Mismatch

**Example: Ollama returns `"Core Aligning Splicer"` but we have `"High Definition Core Aligning Fusion Splicer"`**

Fix in `monitor_config.py`:

```python
DESCRIPTION_TO_MODEL = {
    'High Definition Core Aligning Fusion Splicer': 'T-72C+',  # What we thought
    'Core Aligning Splicer': 'T-72C+',  # What Ollama actually returns
    'Core Alignment Fusion Splicer': 'T-57C+',
    # Add more as you discover them...
}
```

Then rebuild:
```bash
cd ~/Monitoring-2
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Test again
curl -X POST http://localhost:8484/api/refresh
docker-compose logs -f monitoring-app | grep "\[UTILS\]"
```

---

## Files Modified

| File | Changes |
|------|---------|
| `utils.py` | Added detailed mapping logs with ✅/❌ indicators |
| `app.py` → `store_version()` | Added DB verification & commit logging |
| `app.py` → `/api/refresh` | Added stage-by-stage extraction logging |
| `pdf_scheduler.py` | Added scheduler-specific logging |

---

## Command Reference

| Task | Command |
|------|---------|
| **Start container** | `docker-compose up -d` |
| **Rebuild** | `docker-compose build --no-cache` |
| **View logs (all)** | `docker-compose logs -f monitoring-app` |
| **View logs (filtered)** | `docker-compose logs -f monitoring-app \| grep "\[UTILS\]\|\[DB\]"` |
| **Trigger extraction** | `curl -X POST http://localhost:8484/api/refresh` |
| **Check status** | `curl http://localhost:8484/api/status` |
| **Enter container** | `docker exec -it monitoring-app bash` |
| **Check database** | `docker exec -it monitoring-app sqlite3 /app/devices.db "SELECT * FROM devices;"` |

---

## Expected Timeline

1. **Deploy enhanced code:** 1 minute
2. **Trigger extraction:** 30 seconds
3. **Review logs:** 1-2 minutes
4. **Identify issue:** 30 seconds - 2 minutes (depending on case)
5. **Apply fix:** 1-5 minutes (mapping update or rebuild)
6. **Verify:** 1 minute

**Total: 5-15 minutes** depending on complexity

---

## What Each Log Level Shows

```
[UTILS] Processing Item #0: ...           ← Each extraction item
[UTILS]   Comparing: 'desc' (match_1=T)   ← Each mapping attempt
[UTILS] ✅ MATCH: 'X' -> 'Y'               ← Successful match
[UTILS] ❌ FAILED TO MATCH: 'X'            ← No match found
[UTILS] FINAL: Returning N models          ← Summary

[EXTRACTION] Processing: model='X'         ← Each model to store
[EXTRACTION] ✅ Successfully stored        ← Storage succeeded
[EXTRACTION] About to store N models       ← How many total

[DB] ▶️  store_version() called            ← DB function entry
[DB]   Current DB state: version='X'       ← What was there
[DB]   ✅ VERIFIED                         ← Write confirmed
[DB]   ✅ COMMIT successful                ← Transaction confirmed
```

---

## Support Files

I've created detailed debugging guides:

1. **ENHANCED_LOGGING_GUIDE.md** - How to read the new logs
2. **DEBUG_DATABASE_BRIDGE.md** - Step-by-step troubleshooting
3. **DOCKER_INTEGRATION_REPORT.md** - Complete architecture overview

Refer to these for detailed diagnostics!

---

## Quick Summary

✅ **Code has been enhanced with detailed logging**
✅ **Logs now show EXACTLY where the disconnect happens**
✅ **You can now see mapping matches/failures in real-time**
✅ **Database operations are verified before/after**

Next step: Deploy and watch the logs! 🚀
