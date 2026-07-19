"""Probe a page for image references (absolute or relative) matching an optional pattern."""
import re
import sys

import requests

url = sys.argv[1]
pat = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None
r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"})
print(r.status_code, r.url, len(r.text))
refs = set(re.findall(r"""(?:src|href|data-src|content)=["']([^"']+\.(?:jpg|jpeg|png|webp|avif)[^"']*)["']""", r.text, re.I))
refs |= set(re.findall(r"""url\(["']?([^"')]+\.(?:jpg|jpeg|png|webp))""", r.text, re.I))
for u in sorted(refs):
    if not pat or pat.search(u):
        print(u)
