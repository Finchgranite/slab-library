"""Slab images for IQ's porcelain ranges from the manufacturers' own sites.

Materia (ABK Group): materiaslab.com/en/collection/{slug} -> collezioneCover image.
Florim: strategy added per-site (see FLORIM section).
"""
import json
import re
import sys
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

MATERIA = {  # price-book colour -> materiaslab.com slug
    "Antique White": "antique-white", "Bianco Vagli": "bianco-vagli",
    "Calacatta Borghini": "calacatta-borghini", "Calacatta Extra": "calacatta-extra",
    "Calacatta Gris": "calacatta-gris", "Corchia Gold": "corchia-gold",
    "Golden Spider": "golden-spider", "Grey Graphite": "grey-grafite",
    "Mont Blanc": "montblanc", "Noir Laurent": "noir-laurent",
    "Pulpis Ivory": "pulpis-ivory", "Quartzite Luna": "quarzite-luna",
    "Savoy Blue": "bleu-de-savoie", "Savoy Moon": "savoy-moon",
    "Statuario Select": "statuario-select-fullvein3d", "Statuario Superior": "statuario-superior",
    "Super White": "superwhite", "Black": "black", "White": "white",
    "Hyper White": "hyper-white", "Resin Grey": "resin-grey",
}

FLORIM = {}  # filled once florim.com structure is probed; colour -> (img_url, page_url)


def save_img(content, fname):
    im = Image.open(BytesIO(content)).convert("RGB")
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    im.save(IMAGES_DIR / fname, "WEBP", quality=82)
    return im


def main():
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    by_key = {}
    for s in db["slabs"]:
        if s["supplier"] == "International Stones (IQ)" and s["material"] == "Porcelain":
            by_key[s["colour"]] = s
    ok = miss = 0
    for colour, slug in MATERIA.items():
        e = by_key.get(colour)
        if e is None:
            continue
        page = f"https://materiaslab.com/en/collection/{slug}"
        try:
            r = requests.get(page, timeout=30, headers=UA)
            r.raise_for_status()
            m = re.search(r'(?:src|href)="\.\./(public/collezioneCover/[^"]+\.(?:jpg|jpeg|png|webp))"', r.text)
            if not m:
                print(f"no cover: {colour}")
                miss += 1
                continue
            img_url = "https://materiaslab.com/" + m.group(1)
            img = requests.get(img_url.replace(" ", "%20"), timeout=60, headers=UA)
            img.raise_for_status()
            fname = f"{e['id']}.webp"
            save_img(img.content, fname)
            e["image"] = {"file": fname, "status": "slab", "source": "materiaslab.com", "borrowedFrom": ""}
            e["productUrl"] = page
            ok += 1
            time.sleep(0.3)
        except Exception as ex:
            print(f"FAIL {colour}: {ex}")
            miss += 1
    for colour, (img_url, page) in FLORIM.items():
        e = by_key.get(colour)
        if e is None:
            continue
        try:
            img = requests.get(img_url.replace(" ", "%20"), timeout=60, headers=UA)
            img.raise_for_status()
            fname = f"{e['id']}.webp"
            save_img(img.content, fname)
            e["image"] = {"file": fname, "status": "slab", "source": "florim.com", "borrowedFrom": ""}
            e["productUrl"] = page
            ok += 1
            time.sleep(0.3)
        except Exception as ex:
            print(f"FAIL {colour}: {ex}")
            miss += 1
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"porcelain images: {ok} ok, {miss} missed")


if __name__ == "__main__":
    main()
