import os
import requests

def ddg_image_search(query, max_results=3, timeout=10):
    """DuckDuckGo image JSON search. Returns list of image urls."""
    results = []
    try:
        session = requests.Session()
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = session.get('https://duckduckgo.com/', headers=headers, timeout=timeout)
        params = {'q': query}
        url = 'https://duckduckgo.com/i.js'
        while len(results) < max_results:
            r = session.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code != 200:
                break
            data = r.json()
            items = data.get('results') or data.get('items') or []
            for it in items:
                if 'image' in it:
                    results.append(it['image'])
                    if len(results) >= max_results:
                        break
            if 'next' in data and data['next']:
                url = data['next']
                params = {}
            else:
                break
    except Exception:
        pass
    return results

def download_image(url, dest_path, timeout=15):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, stream=True, timeout=timeout)
        if r.status_code == 200:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False
