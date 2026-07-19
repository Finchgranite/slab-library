"""Add 2-3 alternative slab images to each generic natural colour (Graham,
2026-07-19: show how much natural material varies — rotatable gallery).

Sources: UK fabricators with open WP media libraries. Strict filename match on
the colour name + slab-shaped aspect only; kitchen/room shots excluded.
Writes images/natural--{slug}--alt{n}.webp and an `images` array on the entry
(primary image first).
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
SITES = ["www.svws.co.uk", "mayfairgranite.co.uk", "www.affordablegranite.co.uk"]
BAD = ("kitchen", "worktop", "install", "room", "logo", "banner", "icon", "team",
       "showroom", "van", "template", "hero", "bathroom", "floor")


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def site_candidates(domain, colour):
    try:
        r = requests.get(f"https://{domain}/wp-json/wp/v2/media",
                         params={"search": colour, "per_page": 30}, timeout=20, headers=UA)
        items = r.json() if r.status_code == 200 else []
    except Exception:
        return []
    cn = norm(colour)
    out = []
    for m in items:
        u = m.get("source_url", "")
        det = m.get("media_details", {})
        w, h = det.get("width", 0), det.get("height", 0)
        fname = norm(u.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        if cn not in fname or any(b in fname for b in BAD):
            continue
        if not h or not (1.3 <= w / h <= 2.9) or w < 600:
            continue
        out.append((w * h, u))
    out.sort(reverse=True)
    return [u for _, u in out[:2]]


def main():
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    generics = [s for s in db["slabs"] if s["supplier"] == "Natural Stone"]
    added_total = colours_hit = 0
    for e in generics:
        base = re.sub(r"\(.*?\)", "", e["colour"]).strip()
        urls = []
        for site in SITES:
            for u in site_candidates(site, base):
                if len(urls) < 3:
                    urls.append((site, u))
            time.sleep(0.15)
        if not urls:
            continue
        slug = e["id"].removeprefix("natural--")
        gallery = [dict(e["image"])] if e["image"]["file"] else []
        n = 0
        for site, u in urls:
            try:
                r = requests.get(u, timeout=60, headers=UA)
                r.raise_for_status()
                im = Image.open(BytesIO(r.content)).convert("RGB")
                if im.width > MAX_WIDTH:
                    im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
                n += 1
                fname = f"natural--{slug}--alt{n}.webp"
                im.save(IMAGES_DIR / fname, "WEBP", quality=82)
                gallery.append({"file": fname, "status": "slab",
                                "source": site.replace("www.", ""), "borrowedFrom": ""})
            except Exception:
                continue
        if n:
            colours_hit += 1
            added_total += n
            e["images"] = gallery
            if not e["image"]["file"]:  # promote first alt to primary
                e["image"] = dict(gallery[0])
    # supplier-linked naturals inherit the (possibly new) primary
    by_id = {s["id"]: s for s in db["slabs"]}
    for s in db["slabs"]:
        gid = s.get("genericId")
        if gid and gid in by_id and by_id[gid]["image"]["file"] and not s["image"]["file"]:
            g = by_id[gid]
            s["image"] = {"file": g["image"]["file"], "status": g["image"]["status"],
                          "source": g["image"]["source"], "borrowedFrom": f"shared natural image ({gid})"}
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"galleries: {colours_hit} colours gained {added_total} alt images")


if __name__ == "__main__":
    main()
