"""Grid overlays (10% lines, labelled) for images needing manual corners."""
import json, os, re
import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
DEST = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\AKG SURFACES (Sempre-Coante)"

# colour -> source file in its folder (None = use main image source per slabify logic)
TARGETS = {
    "Barents": "955-Barents-2-scaled.jpg",
    "Bianco Carrara": "936-Bianco-Carrara-1-scaled.jpg",
    "Bianco Eclipsia": "02-Bianco-Eclipsia-PQ_226423fee.jpg",
    "Calacatta Lucia": None,
    "Calacatta Magnifico": "Calacatta Magnifico by Cimstone full slab view.jpg",
    "Calacatta Nuvo": "932-Calacatta-Nuvo-2-scaled.jpg",
    "Calacatta Venato": "920-Calacatta-Venato-2.jpg",
    "Calacatta Vicenza": "981-Calacatta-Vicenza-1-scaled.jpg",
    "Concrete Terreno": None,
    "Lapland": None,
    "Nebula": "925-Nebula-scaled.jpg",
    "Sierra": "160-Sierra-1-scaled.jpg",
    "Sineda": None,
    "Cortina": "143-Cortina-scaled.jpg",
    "Misterio Oro": "145-Misterio-Oro-HQ-scaled.jpg",
    "Misterio Oro 2": ("Misterio Oro", "145-Misterio-Oro-1-scaled.jpg"),
}

d = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
by_colour = {r["colour"]: r for r in d["slabs"] if r.get("supplier") == "AKG Surfaces"}

def source_for(colour, spec):
    if isinstance(spec, tuple):
        colour, spec = spec
    folder = os.path.join(DEST, colour)
    if spec:
        return os.path.join(folder, spec)
    r = by_colour[colour]
    src = r["image"].get("source", "")
    fn = os.path.basename(src.split("?")[0]) if src.startswith("http") else ""
    if fn and os.path.isdir(folder):
        stem = re.sub(r"\.(jpe?g|png|webp)$", "", fn, flags=re.I)
        for cand in os.listdir(folder):
            if cand == fn or cand.startswith(stem):
                return os.path.join(folder, cand)
    return os.path.join(LIB, "images", r["image"]["file"])

for label, spec in TARGETS.items():
    p = source_for(label, spec)
    if not os.path.exists(p):
        print("MISSING:", label, p)
        continue
    im = Image.open(p).convert("RGB")
    s = 1100 / im.width
    im = im.resize((1100, int(im.height * s)))
    dr = ImageDraw.Draw(im)
    w, h = im.size
    for i in range(1, 10):
        x = w * i // 10
        y = h * i // 10
        dr.line([(x, 0), (x, h)], fill=(255, 0, 0), width=1)
        dr.line([(0, y), (w, y)], fill=(255, 0, 0), width=1)
        dr.text((x + 3, 3), str(i * 10), fill=(255, 0, 0))
        dr.text((3, y + 3), str(i * 10), fill=(255, 0, 0))
    out = os.path.join(SCRATCH, "grid_" + re.sub(r"[^a-z0-9]+", "", label.lower()) + ".png")
    im.save(out)
    print("grid:", label, "->", os.path.basename(out), "| src:", os.path.basename(p))
