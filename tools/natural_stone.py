"""Natural-stone pass: ONE shared image per colour name across all suppliers.

Graham's rule (2026-07-19): natural stone (granite, quartzite, marble, limestone,
travertine, slate, obsidiana) needs just one representative image per colour name,
always displayed with the illustration-only warning (entries already carry
illustrationOnly: true from seeding).

Source priority per colour name:
 1. an existing natural entry with an image (any supplier)
 2. Cosentino Sensa/Scalea CDN (HD full slabs)
 3. istones.co.uk /images/{granite|quartzite|marble}/slabs/{slug}-320x160-crop.png
 4. local "GRANITE/Granite slabs" yard photos (real slabs)
 5. local "IQ Granite & Quartzite" per-colour folders
 6. local "Granite swatches" {slug}-actual.jpg (closeup-only)
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
GRANITE_DIR = Path(r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\2. GRANITE & NATURAL STONE")

SENSA_SCALEA = dict(p.split("=") for p in """black-beauty=BBT colonial-white=COW cristalo=ZIA
glacial-blue=GLA ice-blue=IBL indian-black=132 itara=TIZ marau=RUA moak-black=MCK nahoa=NAH
nilo=NIL oihana=OHN orinoco=JPB platino=PTN sant-angelo=SNL siberia=SBE taj-mahal=TAK
vancouver=VNC white-macaubas=181 andromeda=AND belvedere=BVD blanco-ibiza=9E calacatta-ice=CTI
calacatta-lincon=CLI caliza-capri=C1 caliza-nevada=CQ crema-marfil=CF crema-moca=DI
elegant-grey=EGY gris-pulpis=PU jura-blue-grey=JBG negresco=NEG perlado=PE""".split())

NOISE = {"block", "close", "up", "pol", "lot", "bd", "bl", "granite", "premium", "extra",
         "honed", "flamed", "leather", "polished", "cm", "mm", "slab", "slabs", "copy"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def name_key(raw):
    """Leading alphabetic words of a filename, noise/dims stripped."""
    words = []
    for w in re.split(r"[\s_\-.]+", raw.lower()):
        if re.search(r"\d", w) or w in NOISE or not w:
            break
        words.append(w)
    return norm(" ".join(words))


def save(im, fname):
    im = im.convert("RGB")
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    im.save(IMAGES_DIR / fname, "WEBP", quality=82)


def build_local_pools():
    slabs_pool, swatch_pool = {}, {}
    d = GRANITE_DIR / "GRANITE" / "Granite slabs"
    for f in sorted(d.iterdir()):
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        k = name_key(f.stem)
        if len(k) >= 4 and (k not in slabs_pool or f.stat().st_size > slabs_pool[k].stat().st_size):
            slabs_pool[k] = f
    d = GRANITE_DIR / "GRANITE" / "Granite swatches"
    if d.is_dir():
        for f in sorted(d.iterdir()):
            m = re.match(r"(.+?)-actual", f.stem.lower())
            if m:
                swatch_pool.setdefault(norm(m.group(1)), f)
    iq = GRANITE_DIR / "IQ Granite & Quartzite"
    iq_pool = {}
    if iq.is_dir():
        for sub in iq.iterdir():
            if sub.is_dir():
                imgs = [f for f in sub.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
                if imgs:
                    iq_pool[name_key(sub.name)] = max(imgs, key=lambda f: f.stat().st_size)
    return slabs_pool, swatch_pool, iq_pool


def main():
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    naturals = [s for s in db["slabs"] if s["naturalStone"]]
    have = {}
    for s in naturals:
        if s["image"]["file"]:
            have.setdefault(norm(s["colour"]), s)
    slabs_pool, swatch_pool, iq_pool = build_local_pools()
    print(f"pools: yard={len(slabs_pool)} swatches={len(swatch_pool)} iq={len(iq_pool)}")
    filled = Counter = {"existing": 0, "sensa": 0, "istones": 0, "yard": 0, "iq": 0, "swatch": 0, "none": 0}
    for e in naturals:
        if e["image"]["file"]:
            continue
        cn = norm(e["colour"])
        cn2 = norm(re.sub(r"\b(premium|extra|honed|flamed|leather(ed)?|polished|granite|quartzite|marble)\b", "", e["colour"], flags=re.I))
        src = None
        peer = have.get(cn) or have.get(cn2)
        if peer:
            e["image"] = {"file": peer["image"]["file"], "status": peer["image"]["status"],
                          "source": peer["image"]["source"], "borrowedFrom": f"{peer['supplier']} {peer['colour']}"}
            e["image"]["status"] = peer["image"]["status"]
            filled["existing"] += 1
            continue
        slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", e["colour"].lower())).strip("-")
        fname = f"natural--{slug}.webp"
        code = SENSA_SCALEA.get(slug) or SENSA_SCALEA.get(re.sub(r"-\d+$", "", slug))
        if code:
            try:
                r = requests.get(f"https://assetstools.cosentino.com/api/v1/bynder/color/{code}/tablahd/{code}-fullslab.jpg",
                                 timeout=90, headers=UA)
                r.raise_for_status()
                save(Image.open(BytesIO(r.content)), fname)
                e["image"] = {"file": fname, "status": "slab", "source": "cosentino.com", "borrowedFrom": ""}
                have.setdefault(cn, e)
                filled["sensa"] += 1
                time.sleep(0.3)
                continue
            except Exception:
                pass
        got = False
        for mat in ("granite", "quartzite", "marble", "limestone"):
            try:
                r = requests.get(f"https://www.istones.co.uk/images/{mat}/slabs/{slug}-320x160-crop.png",
                                 timeout=30, headers=UA)
                if r.status_code == 200 and len(r.content) > 5000:
                    save(Image.open(BytesIO(r.content)), fname)
                    e["image"] = {"file": fname, "status": "slab", "source": "istones.co.uk", "borrowedFrom": ""}
                    have.setdefault(cn, e)
                    filled["istones"] += 1
                    got = True
                    break
            except Exception:
                pass
        if got:
            continue
        f = slabs_pool.get(cn) or slabs_pool.get(cn2)
        pool = "yard"
        if not f:
            f = iq_pool.get(cn) or iq_pool.get(cn2)
            pool = "iq"
        if not f:
            f = swatch_pool.get(cn) or swatch_pool.get(cn2)
            pool = "swatch"
        if f:
            try:
                save(Image.open(f), fname)
                st = "closeup-only" if pool == "swatch" else "slab"
                e["image"] = {"file": fname, "status": st, "source": "onedrive-granite-folder", "borrowedFrom": ""}
                have.setdefault(cn, e)
                filled[pool] += 1
                continue
            except Exception:
                pass
        filled["none"] += 1
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print("natural-stone pass:", filled)


if __name__ == "__main__":
    main()
