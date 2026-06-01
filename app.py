#from fastapi import FastAPI, Request, HTTPException, Header, Depends, status
#from fastapi.responses import HTMLResponse, JSONResponse
#from fastapi.staticfiles import StaticFiles
#from fastapi.middleware.cors import CORSMiddleware
#from fastapi.templating import Jinja2Templates
import sqlite3
import os
import sys
from datetime import datetime
from typing import List
#import logging
#import json
#import time
#from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from pdf_vision_extractor import extract_pdf_with_vision
from web_monitor import get_versions_for_map
from pdf_scheduler import PDFScheduler
from monitor_config import DEVICES_TO_MONITOR, MONITORED_MAP

DB_PATH = os.path.join(BASE_DIR, 'devices.db')


from utils import extract_individual_models


API_KEY = os.getenv('API_KEY')
PDF_URL = os.getenv('PDF_URL', 'http://example.com/latest_software.pdf')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def _mask_key(k: str) -> str:
    if not k:
        return 'NONE'
    if len(k) <= 8:
        return k[:2] + '****'
    return k[:4] + '****' + k[-2:]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'static')), name='static')
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'templates'))


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log each incoming request with a masked API key (if present) and attach timing header."""
    start_time = time.time()
    client = request.client.host if request.client else 'unknown'
    key = request.headers.get('X-Credentials')
    masked = _mask_key(key)
    logging.info(f"{client} -> {request.method} {request.url.path} api_key={masked}")
    response = await call_next(request)
    elapsed = time.time() - start_time
    response.headers['X-Process-Time'] = f"{elapsed:.4f}"
    logging.info(f"{client} <- {request.method} {request.url.path} status={response.status_code} time={elapsed:.3f}s")
    return response


def init_db(path: str = DB_PATH):
    # Ensure the directory exists
    db_dir = os.path.dirname(path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                model TEXT PRIMARY KEY,
                category TEXT,
                stored_version TEXT,
                stored_release_date TEXT,
                acknowledged_version TEXT,
                acknowledged INTEGER DEFAULT 0,
                last_checked TEXT
            )
            """
        )
        # Add migration for existing databases
        try:
            cur.execute('SELECT acknowledged_version FROM devices LIMIT 1')
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            cur.execute('ALTER TABLE devices ADD COLUMN acknowledged_version TEXT')

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS version_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT,
                version TEXT,
                detected_date TEXT,
                stored_date TEXT,
                FOREIGN KEY (model) REFERENCES devices(model)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT,
                version TEXT,
                notified_at TEXT
            )
            """
        )
        for m in MONITORED_MAP.keys():
            cur.execute('INSERT OR IGNORE INTO devices (model) VALUES (?)', (m,))
        conn.commit()
        conn.close()
        logging.info(f"Database initialized successfully at {path}")
    except Exception as e:
        logging.error(f"Failed to initialize database at {path}: {e}", exc_info=True)
        raise


def has_notification(model: str, version: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM notifications WHERE model=? AND version=? LIMIT 1', (model, version))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def record_notification(model: str, version: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO notifications (model, version, notified_at) VALUES (?, ?, ?)', (model, version, datetime.utcnow().date().isoformat()))
    conn.commit()
    conn.close()


def cleanup_db(path: str = DB_PATH):
    """Remove any DB rows for models not in MONITORED_MAP."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    placeholders = ','.join('?' for _ in MONITORED_MAP.keys())
    cur.execute(f"DELETE FROM devices WHERE model NOT IN ({placeholders})", tuple(MONITORED_MAP.keys()))
    conn.commit()
    conn.close()


def get_db_rows() -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT model, category, stored_version, stored_release_date, acknowledged_version, acknowledged, last_checked FROM devices')
    rows = cur.fetchall()
    conn.close()
    devices = []
    for r in rows:
        devices.append({
            'model': r[0],
            'category': r[1],
            'stored_version': r[2],
            'stored_release_date': r[3],
            'acknowledged_version': r[4],
            'acknowledged': bool(r[5]),
            'last_checked': r[6]
        })
    return devices


def acknowledge_model(model: str, new_version: str, new_date: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('UPDATE devices SET stored_version=?, stored_release_date=?, acknowledged_version=?, acknowledged=1, last_checked=? WHERE model=?',
                (new_version, new_date, new_version, datetime.utcnow().date().isoformat(), model))
    conn.commit()
    conn.close()


def store_version(model: str, version: str, release_date: str):
    """Store or update device version in database with detailed logging."""
    logging.info(f"[DB] ▶️  store_version() called: model='{model}', version='{version}', release_date='{release_date}'")

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d")

        # Check current version
        cur.execute('SELECT stored_version FROM devices WHERE model=?', (model,))
        result = cur.fetchone()
        current_version = result[0] if result else None

        logging.info(f"[DB]   Current DB state: model='{model}' -> version='{current_version}'")

        # If version is different from current, reset acknowledged flag
        version_changed = current_version and current_version != version

        if result:
            # Update existing record
            if version_changed:
                logging.info(f"[DB]   Version changed! Updating: {current_version} -> {version}")
                cur.execute(
                    'UPDATE devices SET stored_version=?, stored_release_date=?, acknowledged=0, last_checked=? WHERE model=?',
                    (version, release_date, now, model)
                )
                rows_affected = cur.rowcount
                logging.info(f"[DB]   UPDATE executed, rows affected: {rows_affected}")
            else:
                logging.info(f"[DB]   Version unchanged, updating metadata only")
                cur.execute(
                    'UPDATE devices SET stored_version=?, stored_release_date=?, last_checked=? WHERE model=?',
                    (version, release_date, now, model)
                )
                rows_affected = cur.rowcount
                logging.info(f"[DB]   UPDATE executed, rows affected: {rows_affected}")
        else:
            # Insert new record
            logging.info(f"[DB]   Record not found, INSERTING new: model='{model}', version='{version}'")
            cur.execute(
                'INSERT INTO devices (model, stored_version, stored_release_date, acknowledged, last_checked) VALUES (?, ?, ?, 0, ?)',
                (model, version, release_date, now)
            )
            rows_affected = cur.rowcount
            logging.info(f"[DB]   INSERT executed, rows affected: {rows_affected}")

        # Verify the write succeeded
        cur.execute('SELECT stored_version, stored_release_date FROM devices WHERE model=?', (model,))
        verify = cur.fetchone()
        if verify:
            logging.info(f"[DB]   ✅ VERIFIED: model='{model}' now has version='{verify[0]}', date='{verify[1]}'")
        else:
            logging.error(f"[DB]   ❌ VERIFICATION FAILED: Could not find '{model}' after INSERT/UPDATE!")

        conn.commit()
        logging.info(f"[DB]   ✅ COMMIT successful")
        conn.close()

    except Exception as e:
        logging.error(f"[DB]   ❌ CRITICAL ERROR in store_version: {e}", exc_info=True)
        raise


def insert_or_update_version(model: str, version: str, detected_date: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT * FROM version_history WHERE model = ? AND version = ?', (model, version))
    existing_entry = cur.fetchone()
    if existing_entry:
        cur.execute('UPDATE version_history SET detected_date = ? WHERE id = ?', (detected_date, existing_entry[0]))
    else:
        cur.execute('INSERT INTO version_history (model, version, detected_date, stored_date) VALUES (?, ?, ?, ?)', (model, version, detected_date, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()


pdf_scheduler = None

@app.on_event('startup')
def startup_event():
    global pdf_scheduler
    logging.info(f"Starting app with BASE_DIR={BASE_DIR}, DB_PATH={DB_PATH}")
    try:
        init_db()
        cleanup_db()
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}", exc_info=True)
        raise

    # Initialize and start PDF scheduler
    try:
        pdf_scheduler = PDFScheduler(
            pdf_url=PDF_URL,
            output_dir=os.path.join(BASE_DIR, "extractions")
        )
        pdf_scheduler.start(hour=9, minute=0)  # Run daily at 9 AM
        logging.info(f"PDF scheduler started successfully for URL: {PDF_URL}")
    except Exception as e:
        logging.error(f"Failed to start PDF scheduler: {e}", exc_info=True)

@app.on_event('shutdown')
def shutdown_event():
    global pdf_scheduler
    if pdf_scheduler:
        pdf_scheduler.stop()
        logging.info("PDF scheduler stopped")


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


def build_status_dict() -> List[dict]:
    # Try to get detected versions, but don't crash if web scraping fails
    try:
        detected = get_versions_for_map(MONITORED_MAP)
    except Exception as e:
        logging.warning(f"[STATUS] Web scraping failed (non-critical): {e}")
        detected = {}  # Empty dict - use database values only

    out = []
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for model in MONITORED_MAP.keys():
        cur.execute('SELECT model, category, stored_version, stored_release_date, acknowledged_version, acknowledged, last_checked FROM devices WHERE model=?', (model,))
        row = cur.fetchone()
        if row:
            stored = row[2]
            stored_date = row[3]
            acknowledged_version = row[4]
            acknowledged = bool(row[5])
        else:
            stored = None
            stored_date = None
            acknowledged_version = None
            acknowledged = False
        det = detected.get(model)
        detected_version = det.get('version') if det else None
        detected_date = None
        changed = False
        update_info = None

        # Show detected version if stored is different from what was acknowledged
        if stored and stored != acknowledged_version:
            detected_version = stored
            detected_date = stored_date
            changed = True
            update_info = f"New version available: {stored}"
        elif det and (det.get('update_available', False) or (detected_version and stored and stored != detected_version)):
            changed = True
            update_info = det.get('latest_text') or "New version available"

        out.append({
            'model': model,
            'category': None,
            'stored_version': acknowledged_version,  # Show what user acknowledged as "stored"
            'stored_release_date': stored_date if acknowledged_version else None,
            'detected_version': detected_version,
            'detected_release_date': detected_date,
            'changed': changed,
            'acknowledged': acknowledged,
            'url': MONITORED_MAP[model],
            'update_info': update_info
        })
    conn.close()
    return out


@app.get('/api/health')
def api_health():
    """Lightweight health check - database only, no web scraping. Must complete within 5 seconds."""
    try:
        # Just check database connectivity
        conn = sqlite3.connect(DB_PATH, timeout=2)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM devices')
        count = cur.fetchone()[0]
        conn.close()

        return JSONResponse(status_code=200, content={'status': 'healthy', 'devices_count': count})
    except Exception as e:
        logging.error(f"[HEALTH] Database check failed: {e}")
        # Still return 200 so container doesn't restart
        return JSONResponse(status_code=200, content={'status': 'degraded', 'error': str(e)})


@app.get('/api/status')
def api_status():
    try:
        status = build_status_dict()
        return JSONResponse(status_code=200, content={'devices': status})
    except Exception as e:
        logging.error(f"[HEALTH] /api/status endpoint error: {e}", exc_info=True)
        # Return minimal response so health check doesn't fail
        # This is critical - health checks must not crash
        return JSONResponse(status_code=200, content={'devices': [], 'warning': 'Partial response due to error'})


def _require_api_key(x_credentials: Optional[str] = Header(None)):
    """FastAPI dependency to require a valid API key in X-Credentials header.

    Returns the provided key on success or raises HTTP 401 on failure.
    If the server is not configured with API_KEY, returns HTTP 500 to indicate server misconfiguration.
    """
    if not API_KEY:
        raise HTTPException(status_code=500, detail='Server API key not configured. Set API_KEY in environment.')
    if not x_credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing X-Credentials header')
    if x_credentials != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid API key')
    return x_credentials


@app.get('/api/v1/devices')
def api_v1_devices(api_key: str = Depends(_require_api_key)):
    """Protected endpoint returning the devices status JSON. Requires X-Credentials header."""
    try:
        devices = build_status_dict()
        return JSONResponse(status_code=200, content={'devices': devices})
    except Exception as e:
        logging.error(f"[API] /api/v1/devices failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/v1/keys/validate')
def api_key_validate(api_key: str = Depends(_require_api_key)):
    """Simple endpoint to validate the provided API key (for testing)."""
    return JSONResponse(status_code=200, content={'valid': True})

@app.get('/api/sumitomo-devices')
def api_sumitomo_devices():
    """Get status of Sumitomo Electric splicer devices being monitored"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        devices = []

        for device_name in DEVICES_TO_MONITOR.keys():
            cur.execute('SELECT model, stored_version, stored_release_date, acknowledged_version, last_checked FROM devices WHERE model=?', (device_name,))
            row = cur.fetchone()

            if row:
                # Show acknowledged version if available, otherwise stored
                version_to_show = row[3] if row[3] else row[1]
                devices.append({
                    'model': device_name,
                    'variants': DEVICES_TO_MONITOR[device_name],
                    'version': version_to_show,
                    'release_date': row[2],
                    'last_checked': row[4],
                    'has_version': version_to_show is not None
                })
            else:
                devices.append({
                    'model': device_name,
                    'variants': DEVICES_TO_MONITOR[device_name],
                    'version': None,
                    'release_date': None,
                    'last_checked': None,
                    'has_version': False
                })

        conn.close()
        return JSONResponse(status_code=200, content={'devices': devices, 'total': len(devices)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/refresh')
def api_refresh():
    try:
        # 1. Get the current URL
        pdf_url = PDF_URL

        # 2. Fetch and process PDF
        logging.info(f"Manual refresh triggered for: {pdf_url}")
        extraction_result = extract_pdf_with_vision(
            pdf_url=pdf_url,
            model="qwen2.5vl:3b",
            dpi=100  # Balanced: good quality without excessive memory
        )

        # 3. Parse the Ollama response
        response_text = extraction_result.get('response', '{}')
        logging.info(f"Extraction response: {response_text}")

        # Try to parse as JSON - Ollama might return wrapped response
        def _extract_json_block(s: str):
            if not s:
                return None
            # 1) triple-backtick JSON block
            if "```json" in s:
                try:
                    return json.loads(s.split("```json", 1)[1].split("```", 1)[0].strip())
                except Exception:
                    pass
            # 2) direct JSON parse (best-effort)
            try:
                return json.loads(s)
            except Exception:
                pass
            # 3) find first JSON-like block ([ or {) and extract balanced substring
            start = None
            for i, ch in enumerate(s):
                if ch in "[{":
                    start = i
                    break
            if start is None:
                return None
            stack = []
            pairs = {"{": "}", "[": "]"}
            for i in range(start, len(s)):
                ch = s[i]
                if ch in pairs:
                    stack.append(pairs[ch])
                elif stack and ch == stack[-1]:
                    stack.pop()
                    if not stack:
                        try:
                            return json.loads(s[start:i+1])
                        except Exception:
                            return None
            return None

        extracted_data = _extract_json_block(response_text) or {}

        # 6. Extract and flatten versions from response
        versions_list = []

        # Handle different response formats from Ollama
        if isinstance(extracted_data, list):
            # Simple array format (expected from new prompt)
            versions_list = extracted_data
        elif isinstance(extracted_data, dict):
            # Check for tabular format (lists as values)
            if "model" in extracted_data and isinstance(extracted_data.get("model"), list):
                # Tabular format: lists of equal length
                models = extracted_data.get("model", [])
                versions = extracted_data.get("version", [])
                release_dates = extracted_data.get("release_date", [])

                for i, model in enumerate(models):
                    version = versions[i] if i < len(versions) else None
                    release_date = release_dates[i] if i < len(release_dates) else None
                    if model and version:
                        versions_list.append({
                            'model': model,
                            'version': version,
                            'release_date': release_date
                        })
            # Check for nested product_category structure (from Ollama vision model)
            elif "product_category" in extracted_data and isinstance(extracted_data["product_category"], dict):
                product_category = extracted_data["product_category"]
                for category, item in product_category.items():
                    if isinstance(item, dict) and 'model' in item:
                        versions_list.append(item)
            # Check for versions list
            elif "versions" in extracted_data:
                versions_list = extracted_data["versions"]
            # Check if it's a flat dict with model/version keys
            elif 'model' in extracted_data and 'version' in extracted_data:
                versions_list = [extracted_data]

        # Parse grouped models into individual device models
        logging.info(f"DEBUG: About to call extract_individual_models with {len(versions_list)} items")
        logging.info(f"DEBUG: versions_list = {versions_list}")
        try:
            individual_models = extract_individual_models(versions_list, DEVICES_TO_MONITOR)
            logging.info(f"extract_individual_models returned {len(individual_models)} models")
            logging.info(f"DEBUG: individual_models = {individual_models}")
        except Exception as e:
            logging.error(f"extract_individual_models FAILED: {e}", exc_info=True)
            individual_models = []

        # 5. Save raw extraction to file for audit/debugging
        extraction_file = os.path.join(BASE_DIR, "extractions", f"extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            os.makedirs(os.path.dirname(extraction_file), exist_ok=True)
            with open(extraction_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'pdf_url': pdf_url,
                    'raw_response': response_text,
                    'parsed_data': extracted_data,
                    'grouped_versions': versions_list,
                    'extracted_individual_models': individual_models
                }, f, indent=2)
            logging.info(f"Saved extraction to {extraction_file}")
        except Exception as e:
            logging.warning(f"Failed to save extraction file: {e}")

        # 6. Store extracted versions in database
        logging.info(f"[EXTRACTION] ╔════════════════════════════════════════════════════════════")
        logging.info(f"[EXTRACTION] ║ About to store {len(individual_models)} models in database")
        logging.info(f"[EXTRACTION] ╚════════════════════════════════════════════════════════════")

        for item in individual_models:
            model = item.get('model')
            version = item.get('version')
            release_date = item.get('release_date', datetime.utcnow().date().isoformat())

            logging.info(f"[EXTRACTION] Processing: model='{model}', version='{version}'")

            if model and version:
                try:
                    store_version(model, version, release_date)
                    insert_or_update_version(model, version, datetime.utcnow().date().isoformat())
                    logging.info(f"[EXTRACTION] ✅ Successfully stored: {model} -> {version}")
                except Exception as e:
                    logging.error(f"[EXTRACTION] ❌ Failed to store version for {model}: {e}", exc_info=True)
            else:
                logging.warning(f"[EXTRACTION] ⚠️  Skipped: model={model}, version={version} (missing required fields)")

        # 7. Build and return updated status
        status = build_status_dict()
        return JSONResponse(status_code=200, content={
            'devices': status,
            'extraction': 'complete',
            'extracted_count': len(individual_models),
            'grouped_count': len(versions_list)
        })

    except Exception as e:
        logging.error(f"Refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/store_version')
def api_store_version(payload: dict):
    model = payload.get('model')
    version = payload.get('version')
    if not model or not version:
        raise HTTPException(status_code=400, detail='model and version are required')
    
    try:
        now = datetime.utcnow().date().isoformat()
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO version_history (model, version, detected_date, stored_date) VALUES (?, ?, ?, ?)',
            (model, version, now, now)
        )
        cur.execute(
            'INSERT INTO devices (model, stored_version, stored_release_date, last_checked) VALUES (?, ?, ?, ?) '
            'ON CONFLICT(model) DO UPDATE SET stored_version = excluded.stored_version, stored_release_date = excluded.stored_release_date, last_checked = excluded.last_checked',
            (model, version, now, now)
        )
        conn.commit()
        conn.close()
        return JSONResponse(status_code=200, content={'ok': True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/acknowledge')
def api_acknowledge(payload: dict):
    model = payload.get('model')
    if not model:
        raise HTTPException(status_code=400, detail='model is required')
    try:
        # Get the current stored version and acknowledge it
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT stored_version, stored_release_date FROM devices WHERE model=?', (model,))
        row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            raise HTTPException(status_code=404, detail='model not found or no version to acknowledge')

        stored_version = row[0]
        stored_date = row[1]

        # Acknowledge the current stored version
        acknowledge_model(model, stored_version, stored_date)
        return JSONResponse(status_code=200, content={'ok': True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/store_version')
async def store_version_from_request(request: Request):
    data = await request.json()
    model = data.get('model')
    version = data.get('version')
    detected_date = datetime.now().strftime("%Y-%m-%d")
    stored_date = datetime.now().strftime("%Y-%m-%d")

    if not model or not version:
        raise HTTPException(status_code=400, detail="Model and version are required.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO version_history (model, version, detected_date, stored_date) VALUES (?, ?, ?, ?)" ,
        (model, version, detected_date, stored_date)
    )
    conn.commit()
    conn.close()

    return JSONResponse(content={"message": "Version stored successfully!"})


@app.post('/api/extraction/trigger')
def api_extraction_trigger():
    """Manually trigger PDF extraction immediately"""
    global pdf_scheduler
    if not pdf_scheduler:
        raise HTTPException(status_code=500, detail="PDF scheduler not initialized")
    try:
        pdf_scheduler.trigger_now()
        return JSONResponse(status_code=200, content={'status': 'extraction triggered'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/extraction/status')
def api_extraction_status():
    """Get next scheduled extraction time"""
    global pdf_scheduler
    if not pdf_scheduler:
        raise HTTPException(status_code=500, detail="PDF scheduler not initialized")
    try:
        job = pdf_scheduler.scheduler.get_job('pdf_extraction')
        return JSONResponse(status_code=200, content={
            'next_run': str(job.next_run_time) if job else "Not scheduled",
            'job_id': 'pdf_extraction',
            'current_url': PDF_URL
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/extraction/update-url')
def api_extraction_update_url(payload: dict):
    """Update PDF URL for extraction (requires restart of scheduler)"""
    global PDF_URL, pdf_scheduler
    new_url = payload.get('url')

    if not new_url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    try:
        PDF_URL = new_url
        logging.info(f"PDF URL updated to: {new_url}")

        # Restart scheduler with new URL
        if pdf_scheduler:
            pdf_scheduler.stop()

        pdf_scheduler = PDFScheduler(
            pdf_url=PDF_URL,
            output_dir=os.path.join(BASE_DIR, "extractions")
        )
        pdf_scheduler.start(hour=9, minute=0)

        return JSONResponse(status_code=200, content={
            'status': 'URL updated and scheduler restarted',
            'new_url': PDF_URL
        })
    except Exception as e:
        logging.error(f"Failed to update PDF URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("Starting Version Monitor server...")
    print("Open http://127.0.0.1:8484 in your browser")
    uvicorn.run("app:app", host="127.0.0.1", port=8484, reload=True)
