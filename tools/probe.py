import re
import sys

import requests

url = sys.argv[1]
r = requests.get(
    url,
    timeout=30,
    allow_redirects=True,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    },
)
print(r.status_code, r.url, len(r.text))
imgs = sorted(set(re.findall(r"https?://[^\"'\s\\)]+\.(?:jpg|jpeg|png|webp)[^\"'\s\\)]*", r.text)))
pat = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None
for u in imgs:
    if not pat or pat.search(u):
        print(u)
