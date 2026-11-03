from fastapi import FastAPI, Request, HTTPException, Header, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import sqlite3
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
import logging
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from web_monitor import get_versions_for_map
from monitor_config import MONITORED_MAP

DB_PATH = os.getenv('DB_PATH', os.path.join(BASE_DIR, 'devices.db'))
API_KEY = os.getenv('API_KEY')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def _mask_key(k: str) -> str:
    if not k:
        return 'NONE'
    if len(k) <= 8:
        return k[:2] + '****'
    return k[:4] + '****' + k[-2:]


app = FastAPI(title="EXFO Version Monitor")
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
    """Initialize the SQLite database with required tables and initial monitored models."""
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


def cleanup_db(path: str = DB_PATH):
    """Remove any DB rows for models not in MONITORED_MAP."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    placeholders = ','.join('?' for _ in MONITORED_MAP.keys())
    cur.execute(f"DELETE FROM devices WHERE model NOT IN ({placeholders})", tuple(MONITORED_MAP.keys()))
    conn.commit()
    conn.close()


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
    cur.execute(
        'UPDATE devices SET stored_version=?, stored_release_date=?, acknowledged_version=?, acknowledged=1, last_checked=? WHERE model=?',
        (new_version, new_date, new_version, datetime.utcnow().date().isoformat(), model)
    )
    conn.commit()
    conn.close()


def store_version(model: str, version: str, release_date: str):
    """Store or update device version in database."""
    logging.info(f"[DB] store_version called: model='{model}', version='{version}', release_date='{release_date}'")
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d")

        cur.execute('SELECT stored_version FROM devices WHERE model=?', (model,))
        result = cur.fetchone()
        current_version = result[0] if result else None

        version_changed = current_version and current_version != version

        if result:
            if version_changed:
                cur.execute(
                    'UPDATE devices SET stored_version=?, stored_release_date=?, acknowledged=0, last_checked=? WHERE model=?',
                    (version, release_date, now, model)
                )
            else:
                cur.execute(
                    'UPDATE devices SET stored_version=?, stored_release_date=?, last_checked=? WHERE model=?',
                    (version, release_date, now, model)
                )
        else:
            cur.execute(
                'INSERT INTO devices (model, stored_version, stored_release_date, acknowledged, last_checked) VALUES (?, ?, ?, 0, ?)',
                (model, version, release_date, now)
            )

        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"[DB] Error in store_version: {e}", exc_info=True)
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


@app.on_event('startup')
def startup_event():
    logging.info(f"Starting EXFO Version Monitor with BASE_DIR={BASE_DIR}, DB_PATH={DB_PATH}")
    try:
        init_db()
        cleanup_db()
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


def build_status_dict(detected: Optional[Dict[str, Dict]] = None) -> List[dict]:
    """Fetch detected versions from EXFO website (if not passed) and merge with DB records."""
    if detected is None:
        try:
            detected = get_versions_for_map(MONITORED_MAP)
        except Exception as e:
            logging.warning(f"[STATUS] Web scraping EXFO website failed: {e}")
            detected = {}

    out = []
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for model in MONITORED_MAP.keys():
        cur.execute(
            'SELECT model, category, stored_version, stored_release_date, acknowledged_version, acknowledged, last_checked FROM devices WHERE model=?',
            (model,)
        )
        row = cur.fetchone()
        if row:
            stored = row[2]
            stored_date = row[3]
            acknowledged_version = row[4]
            acknowledged = bool(row[5])
            last_checked = row[6]
        else:
            stored = None
            stored_date = None
            acknowledged_version = None
            acknowledged = False
            last_checked = None

        det = detected.get(model) if detected else None
        detected_version = det.get('version') if det else None
        detected_date = None
        changed = False
        update_info = None

        # Compare detected version from EXFO with stored/acknowledged version
        if stored and stored != acknowledged_version:
            detected_version = stored
            detected_date = stored_date
            changed = True
            update_info = f"New version available: {stored}"
        elif det and (det.get('update_available', False) or (detected_version and stored and stored != detected_version)):
            changed = True
            update_info = det.get('latest_text') or f"New version available: {detected_version}"
        elif detected_version and not stored:
            changed = True
            update_info = f"New version detected: {detected_version}"

        out.append({
            'model': model,
            'category': None,
            'stored_version': acknowledged_version,
            'stored_release_date': stored_date if acknowledged_version else None,
            'detected_version': detected_version,
            'detected_release_date': detected_date,
            'changed': changed,
            'acknowledged': acknowledged,
            'url': MONITORED_MAP[model],
            'update_info': update_info,
            'last_checked': last_checked
        })
    conn.close()
    return out


@app.get('/api/health')
def api_health():
    """Lightweight health check - database connectivity check."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM devices')
        count = cur.fetchone()[0]
        conn.close()
        return JSONResponse(status_code=200, content={'status': 'healthy', 'devices_count': count})
    except Exception as e:
        logging.error(f"[HEALTH] Database check failed: {e}")
        return JSONResponse(status_code=200, content={'status': 'degraded', 'error': str(e)})


@app.get('/api/status')
def api_status():
    """Return status of all monitored EXFO devices."""
    try:
        status = build_status_dict()
        return JSONResponse(status_code=200, content={'devices': status})
    except Exception as e:
        logging.error(f"[API] /api/status endpoint error: {e}", exc_info=True)
        return JSONResponse(status_code=200, content={'devices': [], 'warning': 'Partial response due to error'})


def _require_api_key(x_credentials: Optional[str] = Header(None)):
    """FastAPI dependency to require a valid API key in X-Credentials header."""
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
    """Simple endpoint to validate the provided API key."""
    return JSONResponse(status_code=200, content={'valid': True})


@app.post('/api/refresh')
def api_refresh():
    """Fetch latest device version data from EXFO website."""
    try:
        logging.info("Manual refresh triggered for EXFO devices")
        detected = get_versions_for_map(MONITORED_MAP)
        now = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for model in MONITORED_MAP.keys():
            cur.execute('UPDATE devices SET last_checked=? WHERE model=?', (now, model))
        conn.commit()
        conn.close()

        status = build_status_dict(detected=detected)
        return JSONResponse(status_code=200, content={
            'status': 'ok',
            'devices': status
        })
    except Exception as e:
        logging.error(f"Refresh failed: {e}", exc_info=True)
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
        "INSERT INTO version_history (model, version, detected_date, stored_date) VALUES (?, ?, ?, ?)",
        (model, version, detected_date, stored_date)
    )
    conn.commit()
    conn.close()

    return JSONResponse(content={"message": "Version stored successfully!"})


@app.post('/api/acknowledge')
def api_acknowledge(payload: dict):
    model = payload.get('model')
    if not model:
        raise HTTPException(status_code=400, detail='model is required')
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT stored_version, stored_release_date FROM devices WHERE model=?', (model,))
        row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            # If stored_version is not yet set, check if detected version is available
            detected = get_versions_for_map({model: MONITORED_MAP[model]})
            det_ver = detected.get(model, {}).get('version')
            if det_ver:
                now = datetime.now().strftime("%Y-%m-%d")
                acknowledge_model(model, det_ver, now)
                return JSONResponse(status_code=200, content={'ok': True})
            raise HTTPException(status_code=404, detail='model not found or no version to acknowledge')

        stored_version = row[0]
        stored_date = row[1] or datetime.now().strftime("%Y-%m-%d")

        acknowledge_model(model, stored_version, stored_date)
        return JSONResponse(status_code=200, content={'ok': True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("Starting EXFO Version Monitor server...")
    print("Open http://127.0.0.1:8000 in your browser")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
