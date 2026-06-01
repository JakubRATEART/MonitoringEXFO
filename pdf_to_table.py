import requests
import PyPDF2
import io
from typing import List, Dict


def download_pdf(url: str) -> io.BytesIO:
    """Download PDF file from URL and return the content as BytesIO."""
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content)


def extract_text_from_pdf(pdf_content: io.BytesIO) -> List[str]:
    """Extract text from PDF and return a list of cleaned lines."""
    pdf_reader = PyPDF2.PdfReader(pdf_content)
    text_data: List[str] = []
    for page in pdf_reader.pages:
        text = page.extract_text() or ""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text_data.extend(lines)
    return text_data


def parse_models_from_text(text_data: List[str], monitored_models: List[str]) -> Dict[str, Dict]:
    """Parse lines extracted from the PDF and return a mapping for monitored models.

    Returns a dict keyed by model name (as in monitored_models) with values:
      { 'category': str, 'model': str, 'version': str, 'release_date': str }
    Only models present in monitored_models are returned.
    """
    monitored_set = {m.strip(): m.strip() for m in monitored_models}
    data: Dict[str, Dict] = {}
    current_category = None
    models_buffer: List[str] = []
    last_version_date = None

    def clean(s: str) -> str:
        return ' '.join(s.split())

    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
              'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

    import re

    def parse_date(date_str: str):
        """Try to parse date strings like '16 May, 2024' or '9 Sep, 2020'. Return datetime or None."""
        if not date_str:
            return None
        # remove accidental spaces inside year like '202 5' -> '2025'
        s = re.sub(r"(?<=\d)\s+(?=\d)", "", date_str)
        # common pattern: day month, year
        m = re.search(r"(\d{1,2})\s+([A-Za-z]+),?\s*(\d{4})", s)
        if not m:
            return None
        day, month_name, year = m.group(1), m.group(2), m.group(3)
        try:
            month = months.index(month_name[:3].title()) + 1 if month_name[:3].title() in [x[:3].title() for x in months[:12]] else None
        except Exception:
            # fallback map
            try:
                month = {
                    'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12
                }[month_name[:3].title()]
            except Exception:
                month = None
        if not month:
            return None
        try:
            return __import__('datetime').datetime(int(year), month, int(day))
        except Exception:
            return None

    for line in text_data:
        line = clean(line)
        # Skip obvious header lines
        if not line or any(h in line for h in ['Latest software', 'Product', 'Version', 'Release date']):
            continue

        # Category detection
        if any(cat in line for cat in ['Core Aligning', 'Core Alignment', 'Active Clad', 'Ribbon', 'Handheld']):
            current_category = line
            models_buffer = []
            continue

        # If line contains both model and version/date (e.g. "TYPE-82M12  1.13 24 Jun, 2025")
        if any(m in line for m in months) and any(ch.isdigit() for ch in line):
            parts = line.split()
            version = None
            date = None
            # find first token that looks like a version (contains dot and digits)
            for i, token in enumerate(parts):
                if '.' in token and any(c.isdigit() for c in token):
                    version = token
                    date = ' '.join(parts[i+1:]) if i + 1 < len(parts) else ''
                    break

            # If we have models buffered, assign this version/date to them
            if version:
                target_models = models_buffer.copy()
                # also handle case where model appears at start of line
                if parts[0] and any(prefix in parts[0] for prefix in ['TYPE-', 'T-', 'Q', 'S1V', 'Z2C']):
                    model_name = ' '.join(parts[:i]) if i > 0 else parts[0]
                    if model_name:
                        target_models = [model_name]

                for m in target_models:
                    name = m.strip()
                    if name in monitored_set:
                        # if there's an existing entry, prefer the one with the newer release date
                        existing = data.get(name)
                        new_date_dt = parse_date(date)
                        if existing:
                            existing_date_dt = parse_date(existing.get('release_date', '') or '')
                            # if new_date_dt is newer, replace; if existing date missing but new present, replace
                            replace = False
                            if new_date_dt and existing_date_dt:
                                replace = new_date_dt > existing_date_dt
                            elif new_date_dt and not existing_date_dt:
                                replace = True
                            elif not new_date_dt and not existing_date_dt:
                                # fallback: choose the higher semantic version (simple numeric compare)
                                try:
                                    replace = float(version) > float(existing.get('version') or 0)
                                except Exception:
                                    replace = False
                            if replace:
                                data[name] = {
                                    'category': current_category,
                                    'model': name,
                                    'version': version,
                                    'release_date': date
                                }
                        else:
                            data[name] = {
                                'category': current_category,
                                'model': name,
                                'version': version,
                                'release_date': date
                            }
                models_buffer = []
            continue

        # If line contains a model-like token, buffer it
        if any(tok in line for tok in ['TYPE-', 'T-', 'Q', 'S1V', 'Z2C']):
            models_buffer.append(line)
            continue

    # Second pass: if some monitored models were not found using the line-by-line parse,
    # try a blob search to find model names and nearby version tokens.
    import re
    blob = ' '.join(text_data)
    for m in monitored_models:
        if m in data:
            continue
        # find model occurrence
        idx = blob.find(m)
        if idx == -1:
            # try relaxed matching (remove spaces/hyphens differences)
            alt = m.replace(' ', '')
            idx = blob.find(alt)
        if idx == -1:
            continue
        # look ahead up to 80 characters for a version-like token
        window = blob[idx: idx + 200]
        ver_match = re.search(r"(\d+\.\d+)", window)
        if ver_match:
            version = ver_match.group(1)
            # try to capture a nearby date (tokens after version)
            after = window[ver_match.end():]
            tokens = after.strip().split()
            date = ' '.join(tokens[:4]) if tokens else ''
            data[m] = {
                'category': current_category,
                'model': m,
                'version': version,
                'release_date': date
            }

    return data


def get_latest_versions(url: str, monitored_models: List[str]) -> Dict[str, Dict]:
    """Download PDF from url, parse it and return latest versions for monitored models.

    Returned dict keys are the monitored model names (exact strings provided in monitored_models). If a model
    wasn't found in the PDF it will simply not appear in the dict.
    """
    pdf_content = download_pdf(url)
    text = extract_text_from_pdf(pdf_content)
    parsed = parse_models_from_text(text, monitored_models)
    return parsed


if __name__ == '__main__':
    # Quick local test when run directly
    URL = "https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf"
    MONITORED = [
        'TYPE-72C+', 'T-57C+', 'T-57', 'T-502S', 'T-400S', 'T-402S', 'TYPE-72M12+', 'TYPE-72M12'
    ]
    latest = get_latest_versions(URL, MONITORED)
    import json
    print(json.dumps(latest, indent=2))