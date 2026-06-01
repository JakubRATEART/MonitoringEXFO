import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json
from pathlib import Path
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, 'devices.db')

from pdf_vision_extractor import extract_pdf_with_vision
import sqlite3
from monitor_config import DEVICES_TO_MONITOR
from utils import extract_individual_models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFScheduler:
    def __init__(self, pdf_url: str, output_dir: str = "./extractions"):
        """
        Initialize the PDF extraction scheduler.

        Args:
            pdf_url: URL of the PDF to download daily
            output_dir: Directory to save extraction results
        """
        self.pdf_url = pdf_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.scheduler = BackgroundScheduler()

    def extraction_job(self):
        """Daily extraction job - runs at scheduled time and updates the devices DB."""
        try:
            logger.info(f"Starting PDF extraction from {self.pdf_url}")

            result = extract_pdf_with_vision(
                pdf_url=self.pdf_url,
                prompt="Extract the table into JSON."
            )

            # Save raw result to file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"extraction_{timestamp}.json"

            try:
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Extraction saved to {output_file}")
            except Exception as e:
                logger.warning(f"Failed to save extraction file: {e}")

            # --- Parse the Ollama response (robust JSON extraction) ---
            response_text = result.get('response', '{}')
            def _extract_json_block_scheduler(s: str):
                if not s:
                    return None
                if "```json" in s:
                    try:
                        return json.loads(s.split("```json",1)[1].split("```",1)[0].strip())
                    except Exception:
                        pass
                try:
                    return json.loads(s)
                except Exception:
                    pass
                start = None
                for i, ch in enumerate(s):
                    if ch in "[{}":
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

            extracted_data = _extract_json_block_scheduler(response_text) or {}

            # 6. Extract and flatten versions from response
            versions_list = []

            # Handle different response formats from Ollama
            if isinstance(extracted_data, list):
                versions_list = extracted_data
            elif isinstance(extracted_data, dict):
                if "model" in extracted_data and isinstance(extracted_data.get("model"), list):
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
                elif "product_category" in extracted_data and isinstance(extracted_data["product_category"], dict):
                    product_category = extracted_data["product_category"]
                    for category, item in product_category.items():
                        if isinstance(item, dict) and 'model' in item:
                            versions_list.append(item)
                elif "versions" in extracted_data:
                    versions_list = extracted_data["versions"]
                elif 'model' in extracted_data and 'version' in extracted_data:
                    versions_list = [extracted_data]

            # Parse grouped models into individual device models
            try:
                individual_models = extract_individual_models(versions_list, DEVICES_TO_MONITOR)
                logger.info(f"[SCHEDULER] Extracted {len(individual_models)} individual models from {len(versions_list)} entries")
                logger.info(f"[SCHEDULER] Models extracted: {[m.get('model') + ' v' + m.get('version') for m in individual_models]}")
                print(f"[SCHEDULER] ✅ extract_individual_models returned {len(individual_models)} models", flush=True)
            except Exception as e:
                logger.error(f"[SCHEDULER] ❌ extract_individual_models FAILED: {e}", exc_info=True)
                print(f"[SCHEDULER] ❌ extract_individual_models FAILED: {e}", flush=True)
                individual_models = []
            for m in individual_models:
                logger.info(f"[SCHEDULER]   - {m.get('model')} v{m.get('version')}")
                print(f"[SCHEDULER] Processed model {m.get('model')} v{m.get('version')}", flush=True)

            # 7. Store extracted versions in shared devices.db
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                stored_count = 0

                logger.info(f"[SCHEDULER] ╔════════════════════════════════════════════════════════════")
                logger.info(f"[SCHEDULER] ║ About to store {len(individual_models)} items in database")
                logger.info(f"[SCHEDULER] ╚════════════════════════════════════════════════════════════")
                print(f"[SCHEDULER] About to store {len(individual_models)} items in database", flush=True)

                for item in individual_models:
                    model = item.get('model')
                    version = item.get('version')
                    release_date = item.get('release_date', datetime.utcnow().date().isoformat())

                    logger.info(f"[SCHEDULER] Processing: model='{model}', version='{version}'")

                    if model and version:
                        try:
                            now = datetime.now().strftime("%Y-%m-%d")
                            cur.execute(
                                """
                                INSERT INTO devices (model, stored_version, stored_release_date, last_checked)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(model) DO UPDATE SET
                                    stored_version = excluded.stored_version,
                                    stored_release_date = excluded.stored_release_date,
                                    last_checked = excluded.last_checked
                                """,
                                (model, version, release_date, now)
                            )

                            cur.execute('SELECT id FROM version_history WHERE model = ? AND version = ?', (model, version))
                            existing_entry = cur.fetchone()
                            if existing_entry:
                                cur.execute('UPDATE version_history SET detected_date = ? WHERE id = ?', (datetime.utcnow().date().isoformat(), existing_entry[0]))
                            else:
                                cur.execute('INSERT INTO version_history (model, version, detected_date, stored_date) VALUES (?, ?, ?, ?)', (model, version, datetime.utcnow().date().isoformat(), datetime.now().strftime("%Y-%m-%d")))

                            logger.info(f"[SCHEDULER] ✅ Stored {model} v{version}")
                            print(f"[SCHEDULER] ✅ Stored {model} v{version} in database", flush=True)
                            stored_count += 1
                        except Exception as e:
                            logger.error(f"[SCHEDULER] ❌ Failed to store {model}: {e}", exc_info=True)
                            print(f"[SCHEDULER] ❌ Failed to store {model}: {e}", flush=True)

                conn.commit()
                conn.close()
                logger.info(f"[SCHEDULER] ✅ COMMIT successful: {stored_count} versions stored")
                print(f"[SCHEDULER] ✅ Scheduler DB update complete: {stored_count} versions stored", flush=True)
            except Exception as e:
                logger.error(f"[SCHEDULER] ❌ Scheduler DB update failed: {e}", exc_info=True)
                print(f"[SCHEDULER] ❌ Scheduler DB update failed: {e}", flush=True)

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)

    def start(self, hour: int = 9, minute: int = 0):
        """
        Start the scheduler.

        Args:
            hour: Hour to run daily (0-23, default: 9 for 9 AM)
            minute: Minute to run (0-59, default: 0)
        """
        # Add job to run daily at specified time
        self.scheduler.add_job(
            self.extraction_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='pdf_extraction',
            name='Daily PDF Extraction',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(f"Scheduler started. Next run: {self.scheduler.get_job('pdf_extraction').next_run_time}")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    def trigger_now(self):
        """Manually trigger extraction immediately (useful for testing)."""
        logger.info("Manual trigger requested")
        self.extraction_job()


# Usage example
if __name__ == "__main__":
    # Initialize scheduler
    scheduler = PDFScheduler(
        pdf_url="http://example.com/latest_software.pdf",
        output_dir="./extractions"
    )

    # Start scheduler to run daily at 9 AM
    scheduler.start(hour=9, minute=0)

    # Keep the script running
    try:
        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()
