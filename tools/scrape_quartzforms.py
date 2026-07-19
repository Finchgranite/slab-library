"""Download official full-slab images from quartzforms.com product pages.

Each product page serves `<Colour>_<code>_slab.webp` (1950x850 render).
Uses the per-colour URLs already seeded into slabs.json from the price book.
"""
import json
import re
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SLABS_JSON = REPO / "slabs.json"
IMAGES_DIR = REPO / "images"
MAX_WIDTH = 1600
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def main():
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    targets = [s for s in db["slabs"] if s["supplier"] == "Quartzforms" and s["productUrl"]]
    print(f"{len(targets)} Quartzforms colours with product URLs")
    ok = no_slab_img = fail = 0
    for i, e in enumerate(targets, 1):
        cn = norm(e["colour"])
        try:
            r = requests.get(e["productUrl"], timeout=30, headers=UA)
            r.raise_for_status()
            # allow spaces in filenames (e.g. "Terrazzo_Casanova_235_ 305x140.png") — stop at quotes only
            urls = {u.strip() for u in re.findall(r"https?://[^\"'<>]+\.(?:jpg|jpeg|png|webp)[^\"'<>]*", r.text)}
            # this colour's own slab render (pages also show other colours' thumbnails);
            # "305x140" (slab cm) marks slab shots on pages that don't use "_slab" naming
            def is_slab(u):
                tail = u.rsplit("/", 1)[-1].lower()
                return "_slab" in tail or "305x140" in tail
            slab_urls = [u for u in urls if is_slab(u) and cn in norm(u.rsplit("/", 1)[-1])]
            if not slab_urls:
                base = re.sub(r"\d+$", "", cn)  # "MA Beige 100" file may omit the code
                slab_urls = [u for u in urls if is_slab(u) and base and base in norm(u.rsplit("/", 1)[-1])]
            if not slab_urls:
                print(f"  [{i}] {e['colour']}: no _slab image on page")
                no_slab_img += 1
                continue
            # prefer the largest cached size, e.g. ".1950x850."
            def size_of(u):
                m = re.search(r"\.(\d+)x(\d+)\.", u)
                return int(m.group(1)) * int(m.group(2)) if m else 0
            url = max(slab_urls, key=size_of)
            img = requests.get(url.replace(" ", "%20"), timeout=60, headers=UA)
            img.raise_for_status()
            im = Image.open(BytesIO(img.content)).convert("RGB")
            if im.width > MAX_WIDTH:
                im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
            fname = f"{e['id']}.webp"
            im.save(IMAGES_DIR / fname, "WEBP", quality=82)
            e["image"] = {"file": fname, "status": "slab", "source": "quartzforms.com", "borrowedFrom": ""}
            ok += 1
            time.sleep(0.4)
        except Exception as ex:
            print(f"  [{i}] {e['colour']}: FAILED {ex}")
            fail += 1
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Done: {ok} downloaded, {no_slab_img} pages without slab image, {fail} failed")


if __name__ == "__main__":
    main()
