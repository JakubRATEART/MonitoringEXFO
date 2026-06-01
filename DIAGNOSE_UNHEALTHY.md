# Diagnose Unhealthy Container Status

Run these commands on your server (kuba@fms-wsparcie):

## 1️⃣ Check Full Logs (including startup errors)

```bash
cd ~/Monitoring-2
docker-compose logs monitoring-app 2>&1 | tail -200
```

Look for:
- Any `ERROR` or `Exception` messages
- Database initialization failures
- Import errors
- Connection timeouts

---

## 2️⃣ Test If App Responds to Health Check

```bash
# SSH into container and test the health check directly
docker exec -it monitoring-app python3 << 'EOF'
import requests
try:
    response = requests.get('http://127.0.0.1:8484/api/status', timeout=5)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"ERROR: {e}")
EOF
```

If this fails, the health check is the problem.

---

## 3️⃣ Check What the Health Check Actually Sees

```bash
docker exec -it monitoring-app bash -c 'python -c "import requests; requests.get(\"http://127.0.0.1:8484/api/status\", timeout=5)" && echo "✅ Health check PASSED" || echo "❌ Health check FAILED"'
```

---

## 4️⃣ Check If Database Is Blocking

```bash
docker exec -it monitoring-app python3 << 'EOF'
import sqlite3
import os

DB_PATH = '/app/devices.db'

# Check if database exists and is readable
if os.path.exists(DB_PATH):
    print(f"✅ Database exists: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM devices')
        count = cur.fetchone()[0]
        print(f"✅ Database is readable: {count} devices")
        conn.close()
    except Exception as e:
        print(f"❌ Database error: {e}")
else:
    print(f"❌ Database does NOT exist: {DB_PATH}")
EOF
```

---

## 5️⃣ Check Container Process

```bash
# Is the app actually running?
docker exec -it monitoring-app ps aux | grep uvicorn
```

Should show:
```
python -m uvicorn app:app --host 0.0.0.0 --port 8484
```

---

## 6️⃣ Run This Full Diagnostic

```bash
echo "=== CONTAINER STATUS ==="
docker-compose ps monitoring-app

echo ""
echo "=== RECENT LOGS (last 50 lines) ==="
docker-compose logs monitoring-app 2>&1 | tail -50

echo ""
echo "=== TEST HEALTH CHECK ==="
docker exec monitoring-app python3 -c "import requests; print(requests.get('http://127.0.0.1:8484/api/status', timeout=5).status_code)" 2>&1 || echo "FAILED"

echo ""
echo "=== DATABASE STATUS ==="
docker exec monitoring-app python3 -c "import sqlite3; conn=sqlite3.connect('/app/devices.db'); print('DB OK'); conn.close()" 2>&1 || echo "FAILED"

echo ""
echo "=== PROCESS CHECK ==="
docker exec monitoring-app ps aux | grep -E "uvicorn|python" | grep -v grep
```

---

## What Each Result Means

| Test | Success | Failure |
|------|---------|---------|
| Health check response | `200` | Error or timeout |
| Database readable | `DB OK` | sqlite3 error |
| Process running | Shows `uvicorn` | No output |
| Logs show errors | None | ERROR messages |

---

**Run all 6 commands above and paste the output here. I can then pinpoint the exact problem.**
