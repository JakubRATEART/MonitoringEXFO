import requests
from bs4 import BeautifulSoup
import re
from typing import Dict


def fetch_page_text(url: str) -> str:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def find_version_near_text(text: str, target: str) -> str:
    """Search the blob text for the target and try to extract a nearby version token."""
    blob = ' '.join(text.split())
    idx = blob.lower().find(target.lower())
    if idx == -1:
        return None
    window = blob[idx: idx + 200]
    m = re.search(r"v(?:ersion)?\s*[: ]?\s*(\d+(?:\.\d+){0,2})", window, flags=re.I)
    if m:
        return m.group(1)
    m2 = re.search(r"(\d+\.\d+(?:\.\d+)?)", window)
    if m2:
        return m2.group(1)
    return None


def find_version_in_soup(soup: BeautifulSoup, target: str) -> dict:
    """Look for elements containing the product name and scan siblings/parents for version-like text."""
    version = None
    update_available = False
    latest_text = None

    if target.lower() == "exfo exchange":
        version_elem = soup.find('span', id='lblFullVersion', class_='longVersion')
        if version_elem:
            version = version_elem.text.strip()
    
    if 'AXS' in target:
        version_elem = soup.find('span', id='lnkSoftwareVersion', class_='softVersion')
        if version_elem:
            version_text = version_elem.text.strip()
            m = re.search(r'version\s+(\d+\.\d+)', version_text, re.I)
            if m:
                version = m.group(1)

    if not version:
        target_l = target.lower()
        target_pattern = target_l.replace('xx', r'\d+').replace('x', r'\d')
        
        for tag in soup.find_all(text=True):
            t = tag.strip()
            if not t:
                continue
            
            if target_l in t.lower() or re.search(target_pattern, t.lower(), re.I):
                parent = tag.parent
                search_nodes = [parent]
                if parent and parent.parent:
                    search_nodes.append(parent.parent)
                    search_nodes.extend(parent.find_next_siblings())
                    search_nodes.extend(parent.find_previous_siblings())
                
                for node in search_nodes:
                    if not node:
                        continue
                    node_text = ' '.join(node.get_text(separator=' ').split())
                    
                    update_indicators = ['new version', 'update available', 'latest version', 'new release']
                    if any(indicator in node_text.lower() for indicator in update_indicators):
                        update_available = True
                        latest_text = node_text
                    
                    if not version:
                        m = re.search(r"v(?:ersion)?\s*[: ]?\s*(\d+(?:\.\d+){0,2})", node_text, flags=re.I)
                        if m:
                            version = m.group(1)
                            continue
                        
                        m2 = re.search(r"(?:^|[^\d])(\d+\.\d+(?:\.\d+)?)(?:[^\d]|$)", node_text)
                        if m2:
                            version = m2.group(1)
                            continue

    return {
        'version': version,
        'update_available': update_available,
        'latest_text': latest_text
    }


def get_versions_for_map(target_map: Dict[str, str]) -> Dict[str, Dict]:
    """Given a map of product display name -> url, return {product: {version, url}} found on each page.

    This uses a few heuristics: look for the product text in the page and for version tokens nearby.
    """
    out = {}
    for product, url in target_map.items():
        try:
            html = fetch_page_text(url)
        except Exception as e:
            out[product] = {'version': None, 'url': url, 'error': str(e)}
            continue

        try:
            soup = BeautifulSoup(html, 'lxml')
        except Exception:
            soup = BeautifulSoup(html, 'html.parser')

        result = find_version_in_soup(soup, product)
        if not result['version']:
            ver = find_version_near_text(html, product)
            result['version'] = ver

        out[product] = {
            'version': result['version'],
            'url': url,
            'update_available': result.get('update_available', False),
            'latest_text': result.get('latest_text', None)
        }

    return out


if __name__ == '__main__':
    demo = {
        'FastReporter 3': 'https://apps.exfo.com/en/exfo-apps/?platform=PC&platformCategory=PC%20Software',
    }
    print(get_versions_for_map(demo))
