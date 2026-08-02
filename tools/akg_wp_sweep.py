"""Sweep ALL AKG product pages for WordPress-direct images (missed by the
Cloudinary-only harvest) and download originals into each colour's folder.
Then set the 7 hand-picked slab mains in slabs.json."""
import json, os, re, time, urllib.request
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
DEST = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\AKG SURFACES (Sempre-Coante)"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()

lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
akg = [r for r in lib["slabs"] if r.get("supplier") == "AKG Surfaces" and r.get("productUrl", "").startswith("http")]

IMG_RE = re.compile(r'https?://[^"\s>)\\]+?\.(?:jpe?g|png|webp)[^"\s>)\\]*')
saved = 0
for r in akg:
    folder = os.path.join(DEST, r["colour"])
    if not os.path.isdir(folder):
        print("no folder:", r["colour"])
        continue
    try:
        html = get(r["productUrl"]).decode("utf-8", "replace")
    except Exception as e:
        print("fetch fail:", r["colour"], e)
        continue
    picks = {}
    for u in IMG_RE.findall(html):
        u = u.rstrip("',")
        if re.search(r"favicon|logo|cloudinary", u, re.I):
            continue  # cloudinary assets were harvested already
        fn = os.path.basename(u.split("?")[0])
        base = re.sub(r"-(scaled|\d+x\d+)(?=\.)", "", fn)
        rank = 2 if "-scaled" in fn else (1 if not re.search(r"-\d+x\d+\.", fn) else 0)
        if base not in picks or rank > picks[base][0]:
            picks[base] = (rank, u, fn)
    for base, (rank, u, fn) in picks.items():
        path = os.path.join(folder, fn)
        if os.path.exists(path) or os.path.exists(os.path.join(folder, base)):
            continue
        try:
            open(path, "wb").write(get(u))
            saved += 1
            print("saved", r["colour"], "<-", fn)
            time.sleep(0.3)
        except Exception as e:
            print("FAIL", r["colour"], fn, e)
print("new files:", saved)

# hand-picked slab mains (Graham 2026-08-02: kitchens replaced by slab shots)
MAINS = {
    "Bianco Carrara": "936-Bianco-Carrara-1-scaled.jpg",
    "Bianco Eclipsia": "02-Bianco-Eclipsia-PQ_226423fee.jpg",
    "Calacatta Nuvo": "932-Calacatta-Nuvo-2-scaled.jpg",
    "Calacatta Vicenza": "981-Calacatta-Vicenza-1-scaled.jpg",
    "Cemento Matte": "972-Cemento-Matte-2.jpg",
    "Nebula": "925-Nebula-scaled.jpg",
    "Sierra": "160-Sierra-1-scaled.jpg",
}
for r in lib["slabs"]:
    if r.get("supplier") != "AKG Surfaces" or r["colour"] not in MAINS:
        continue
    src = os.path.join(DEST, r["colour"], MAINS[r["colour"]])
    if not os.path.exists(src):
        print("MISSING PICK:", r["colour"], MAINS[r["colour"]])
        continue
    im = Image.open(src)
    if im.mode != "RGB":
        im = im.convert("RGB")
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    im.save(os.path.join(LIB, "images", r["image"]["file"] or (r["id"] + ".webp")), "WEBP", quality=85)
    if not r["image"]["file"]:
        r["image"]["file"] = r["id"] + ".webp"
    r["image"]["status"] = "slab"
    r["image"]["source"] = r["productUrl"]
    print("main set:", r["colour"], "->", MAINS[r["colour"]])

json.dump(lib, open(os.path.join(LIB, "slabs.json"), "w", encoding="utf-8"),
          indent=1, ensure_ascii=False)
print("slabs.json updated")
