"""CRL: use the official "Full Slab" image on each /surfaces/{slug}/ page.

Colour pages come from the WP 'collection' post type; each page embeds
{Name}-full-slab.jpg (largest variant has no -WxH suffix). Replaces any
previously assigned CRL image (Graham asked for these specifically).
"""
import json
import re
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parent.parent
SLABS_JSON = REPO / "slabs.json"
IMAGES_DIR = REPO / "images"
MAX_WIDTH = 1600
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def collection_links():
    links = {}
    for page in (1, 2, 3):
        r = requests.get("https://crlstone.co.uk/wp-json/wp/v2/collection",
                         params={"per_page": 100, "page": page, "_fields": "slug,link"},
                         timeout=30, headers=UA)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        for x in batch:
            links[norm(x["slug"])] = x["link"]
        if len(batch) < 100:
            break
    return links


def main():
    links = collection_links()
    print(f"{len(links)} CRL colour pages")
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    ok = miss = 0
    misses = []
    for e in [s for s in db["slabs"] if s["supplier"] == "CRL"]:
        cn = norm(e["colour"])
        link = links.get(cn) or links.get(re.sub(r"\d+$", "", cn))
        if not link:
            # try "ceralsio-" prefix or contains-match
            cands = [l for k, l in links.items() if cn in k or k in cn]
            link = cands[0] if len(cands) == 1 else None
        if not link:
            miss += 1
            misses.append(e["colour"])
            continue
        try:
            r = requests.get(link, timeout=30, headers=UA)
            r.raise_for_status()
            urls = set(re.findall(r"https://crlstone\.co\.uk/content/uploads/[^\"'\s]*slab[^\"'\s]*\.(?:jpg|jpeg|png|webp)", r.text, re.I))
            urls = {u for u in urls if not re.search(r"kitchen|roomset|lifestyle", u, re.I)}
            if not urls:
                miss += 1
                misses.append(e["colour"] + " (no full-slab img)")
                continue
            masters = {re.sub(r"-\d+x\d+(?=\.\w+$)", "", u) for u in urls}

            def rank(u):  # prefer explicit full-slab, then plain _Slab, then _Slab_Zoom
                lu = u.lower()
                return (0 if "full-slab" in lu or "full_slab" in lu else
                        2 if "zoom" in lu else 1, len(u))
            url = sorted(masters, key=rank)[0]
            img = requests.get(url, timeout=60, headers=UA)
            img.raise_for_status()
            im = Image.open(BytesIO(img.content)).convert("RGB")
            if im.width > MAX_WIDTH:
                im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
            fname = f"{e['id']}.webp"
            im.save(IMAGES_DIR / fname, "WEBP", quality=82)
            e["image"] = {"file": fname, "status": "slab", "source": "crlstone.co.uk", "borrowedFrom": ""}
            e["productUrl"] = link
            ok += 1
            time.sleep(0.3)
        except Exception as ex:
            miss += 1
            misses.append(f"{e['colour']} (ERR {ex})")
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"CRL full-slab pass: {ok} updated, {miss} missed")
    if misses:
        print("Missed:", "; ".join(misses[:30]))


if __name__ == "__main__":
    main()
