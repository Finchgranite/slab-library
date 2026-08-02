"""Re-pick the main slab image for AKG entries whose current main isn't ~2:1.
Priority: slab/plaka filename -> aspect closest to 2.0 (only if within 1.85-2.15).
Falls back to keeping the current image."""
import json, os, re
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\AKG SURFACES (Sempre-Coante)"

manifest = json.load(open(os.path.join(SCRATCH, "akg-harvest.json"), encoding="utf-8"))
url_of = {}
for m in manifest:
    for f in m.get("images", []):
        url_of[f["file"]] = f["url"]

lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
changed = 0
for r in lib["slabs"]:
    if r.get("supplier") != "AKG Surfaces" or not r["image"].get("file"):
        continue
    cur = os.path.join(LIB, "images", r["image"]["file"])
    im = Image.open(cur)
    if 1.85 <= im.width / im.height <= 2.15:
        continue
    folder = os.path.join(DEST_ROOT, r["colour"])
    if not os.path.isdir(folder):
        print("no folder:", r["colour"])
        continue
    cands = []
    for fn in os.listdir(folder):
        if not re.search(r"\.(jpe?g|png|webp)$", fn, re.I):
            continue
        try:
            with Image.open(os.path.join(folder, fn)) as t:
                ar = t.width / t.height
        except Exception:
            continue
        named = bool(re.search(r"slab|plaka", fn, re.I))
        good_ar = 1.85 <= ar <= 2.15
        cands.append((named, good_ar, -abs(ar - 2.0), fn))
    cands.sort(reverse=True)
    if not cands or not (cands[0][0] or cands[0][1]):
        print(f"KEEP (no better candidate): {r['colour']}")
        continue
    pick = cands[0][3]
    im2 = Image.open(os.path.join(folder, pick))
    if im2.mode != "RGB":
        im2 = im2.convert("RGB")
    if im2.width > 1600:
        im2 = im2.resize((1600, round(im2.height * 1600 / im2.width)), Image.LANCZOS)
    im2.save(cur, "WEBP", quality=85)
    r["image"]["source"] = url_of.get(pick, r["image"]["source"])
    changed += 1
    print(f"FIXED {r['colour']}: -> {pick}")

json.dump(lib, open(os.path.join(LIB, "slabs.json"), "w", encoding="utf-8"),
          indent=1, ensure_ascii=False)
print("changed:", changed)
