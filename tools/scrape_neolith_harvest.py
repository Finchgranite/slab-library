"""Apply the browser-harvested Neolith Storyblok URLs (2026-07-19).

The all-colours grid renders client-side, so slab-image URLs were collected by
driving Chrome through each colour page; this script just downloads them.
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
CDN = "https://a.storyblok.com/f/150360/"

HARVEST = """
classtone/abu-dhabi-white :: 1250x1824/a4f716895d/imagen_destacada.jpg/m/
classtone/amazonico :: 1250x1824/de6d9f93ae/imagen_destacada.jpg/m/
classtone/arabesque :: 1100x1600/4fc259f8d0/arabesque_hp_1.jpg
colorfeel/arctic-white :: 1250x1824/3454df2ae0/imagen_destacada.jpg/m/
fusion/basalt-black :: 1250x1824/5ebd9b5996/imagen_destacada.jpg/m/
fusion/basalt-grey :: 1250x1824/3ebaa32da3/imagen_destacada.jpg/m/
fusion/beton :: 1250x1824/52853cb9b6/imagen_destacada.jpg/m/
classtone/calacatta-c01-c01r :: 1250x1824/4e724b7ab3/imagen_destacada.jpg/m/
classtone/calacatta-gold-cg01-cg01r :: 1250x1824/0ec315745f/imagen_destacada.jpg/m/
classtone/calacatta-luxe-cl01-cl01r :: 1250x1824/30f4c9b87a/imagen_destacada.jpg/m/
classtone/calacatta-royale :: 1100x1600/e21c221a37/calacatta_royale_hp_1.jpg
classtone/calatorao :: 1250x1824/fd66057830/imagen_destacada.jpg/m/
classtone/colorado-dunes :: 1100x1600/6b867ece9c/colorado_dunes_hp_1.jpg
classtone/estatuario-e01-e01r :: 1250x1824/8953e29ce7/imagen_destacada.jpg/m/
classtone/himalaya-crystal :: 1250x1824/b3947b26f4/imagen_destacada.jpg/m/
iron/iron-copper :: 1250x1824/c5bce76a83/imagen_destacada.jpg/m/
iron/iron-corten :: 1250x1824/8640a96bf3/imagen_destacada.jpg/m/
iron/iron-grey :: 1250x1824/f5f7599a2b/imagen_destacada.jpg/m/
colorfeel/just-white :: 1250x1824/c0a4f72e7d/imagen_destacada.jpg/m/
classtone/layla :: 1250x1824/4e70578277/imagen_destacada.jpg/m/
steel/metropolitan :: 1250x1824/fcd90e1500/imagen_destacada.jpg/m/
classtone/mont-blanc :: 1250x1824/b40f1a3edc/imagen_destacada.jpg/m/
colorfeel/nero :: 1250x1824/fce782c065/imagen_destacada.jpg/m/
fusion/new-york-new-york :: 1250x1824/d01b785cda/imagen_destacada.jpg/m/
fusion/pietra-di-luna :: 1250x1824/d790973313/imagen_destacada.jpg/m/
fusion/pietra-di-osso :: 1250x1824/c728339536/imagen_destacada.jpg/m/
fusion/pietra-di-piombo :: 1250x1824/8c341f5ee2/imagen_destacada.jpg/m/
fusion/retrostone :: 1250x1824/4a1556ad37/imagen_destacada.jpg/m/
fusion/shilin :: 1250x1824/8bf0a83199/imagen_destacada.jpg/m/
classtone/strata-argentum :: 1250x1824/8d264ca993/neolith_strata-argentum_slab.jpg/m/
fusion/terrazo-ceppo :: 1250x1824/f5130944e2/imagen_destacada.jpg/m/
fusion/zaha-stone :: 1250x1824/057d6dedbf/imagen_destacada.jpg/m/
"""


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def main():
    paths = {}
    for line in HARVEST.strip().splitlines():
        path, url = [p.strip() for p in line.split("::")]
        slug = path.split("/")[1]
        base = re.sub(r"(-[a-z]{1,2}\d{2}[a-z0-9]*)+$", "", slug)
        paths[norm(base)] = (path, CDN + url.rstrip("/").removesuffix("/m") + ("/m/1600x0" if url.endswith("/m/") else ""))
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    ok = miss = 0
    for e in [s for s in db["slabs"] if s["supplier"] == "Neolith"]:
        if e["image"].get("source", "").endswith((".com", ".co.uk")):
            continue
        cn = norm(re.sub(r"\(.*?\)", "", e["colour"]))
        hit = paths.get(cn)
        if not hit:
            miss += 1
            continue
        path, url = hit
        try:
            r = requests.get(url, timeout=60, headers=UA)
            r.raise_for_status()
            im = Image.open(BytesIO(r.content)).convert("RGB")
            if im.width > MAX_WIDTH:
                im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
            fname = f"{e['id']}.webp"
            im.save(IMAGES_DIR / fname, "WEBP", quality=82)
            e["image"] = {"file": fname, "status": "slab", "source": "neolith.com", "borrowedFrom": ""}
            e["productUrl"] = f"https://www.neolith.com/en/collections/{path}/"
            ok += 1
            time.sleep(0.3)
        except Exception as ex:
            print(f"FAIL {e['colour']}: {ex}")
            miss += 1
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Neolith harvest: {ok} downloaded, {miss} still missing")


if __name__ == "__main__":
    main()
