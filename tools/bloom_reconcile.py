"""Reconcile bloom-harvest.json with slab-library (Bloomstones Quartz) + price book.
--report: table only. --apply: pick main slab image (VK/~2:1, resampled to the
true 3230x1630 aspect), write webps + productUrl + slabSizes + image.scale.
"""
import csv, difflib, json, os, re, sys
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
CSV = r"C:\Users\thefi\stone-worktop-quotes\materials\supplier-price-book.csv"
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\Bloomstone quartz"

manifest = json.load(open(os.path.join(SCRATCH, "bloom-harvest.json"), encoding="utf-8"))
lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
entries = [r for r in lib["slabs"] if r.get("supplier") == "Bloomstones" and r.get("material") == "Quartz"]

pb = {}
for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
    if r["Supplier"] != "Bloomstones" or r["Material"] != "Quartz":
        continue
    pb.setdefault(r["Colour"], {})[int(r["Thickness (mm)"])] = \
        f"{int(float(r['Slab Length (mm)']))}x{int(float(r['Slab Width (mm)']))}"

DROP = {"leathered", "honed", "printed", "quartz", "polished"}
def toks(s):
    out = set()
    for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split():
        if w in DROP:
            continue
        out.add({"calcutta": "calacatta", "calacutta": "calacatta", "gray": "grey"}.get(w, w))
    return out

def fuzzy_sub(a, b):
    for t in a:
        if t not in b and not difflib.get_close_matches(t, list(b), n=1, cutoff=0.8):
            return False
    return True

def best(site_name, pool):
    st = toks(site_name)
    top, score = None, (0, 0.0)
    for name, obj in pool:
        ts = toks(name)
        if ts and fuzzy_sub(ts, st):
            r_ = difflib.SequenceMatcher(None, site_name.lower(), name.lower()).ratio()
            if (len(ts), r_) > score:
                top, score = obj, (len(ts), r_)
    return top

lib_pool = [(r["colour"], r) for r in entries]
pb_pool = [(k, k) for k in pb]
apply_mode = "--apply" in sys.argv
rows_out, matched = [], set()

for m in manifest:
    colour = m["colour"].strip().rstrip("-").strip()
    entry = best(colour, lib_pool)
    pbc = best(colour, pb_pool)
    sizes = pb.get(pbc, {}) if pbc else {}
    slab_sizes = " / ".join(f"{t}mm: {s}" for t, s in sorted(sizes.items()))
    m_asp = None
    folder = os.path.join(DEST_ROOT, re.sub(r'[<>:"/\\|?*]', "", m["colour"]).strip())

    # choose main: quartz-page images, real dims, prefer VK name then aspect ~2:1
    cands = []
    for f in m["files"]:
        if f.get("error"):
            continue
        p = os.path.join(folder, f["file"])
        if not os.path.exists(p):
            continue
        try:
            with Image.open(p) as im:
                w, h = im.size
        except Exception:
            continue
        if w < 800:
            continue
        ar = w / h
        vk = bool(re.search(r"\bVK\b|virtual", f["file"], re.I))
        good = 1.85 <= ar <= 2.15
        cands.append((f["kind"] == "quartz", vk, good, w, f["file"], ar))
    cands.sort(reverse=True)
    main = cands[0] if cands else None
    status = "match" if entry else "NEW"
    rows_out.append((colour, status, entry["colour"] if entry else "-",
                     pbc or "NO PRICEBOOK",
                     (f"{main[4]} ar={main[5]:.2f}" if main else "NO IMAGE")))
    if not apply_mode:
        continue

    if entry is None:
        entry = {"id": "bloomstones--" + re.sub(r"[^a-z0-9]+", "-", colour.lower()).strip("-"),
                 "supplier": "Bloomstones", "colour": colour, "material": "Quartz",
                 "naturalStone": False, "illustrationOnly": False,
                 "thicknesses": sorted(sizes) if sizes else [20, 30],
                 "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""}}
        lib["slabs"].append(entry)
        lib_pool.append((colour, entry))
    matched.add(entry["id"])
    entry["productUrl"] = m["urls"].get("quartz") or m["urls"].get("kitchen", "")
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
        entry["thicknesses"] = sorted(sizes)
    if main:
        p = os.path.join(folder, main[4])
        im = Image.open(p)
        if im.mode != "RGB":
            im = im.convert("RGB")
        tgt = 3230 / 1630
        ar = im.width / im.height
        if abs(ar - tgt) / tgt < 0.04:
            im = im.resize((1600, round(1600 / tgt)), Image.LANCZOS)
            scale = "true"
        else:
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            scale = "approx"
        fn = entry["id"] + ".webp"
        im.save(os.path.join(LIB, "images", fn), "WEBP", quality=87)
        entry["image"] = {"file": fn, "status": "slab",
                          "source": "https://static.wixstatic.com/media/" +
                                    next(f["base"] for f in m["files"] if f["file"] == main[4]),
                          "borrowedFrom": "", "scale": scale}

if apply_mode:
    import datetime
    lib["generated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(lib, open(os.path.join(LIB, "slabs.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    left = sorted(r["colour"] for r in entries if r["id"] not in matched)
    print("APPLIED. Library Bloomstones Quartz colours NOT on the site:", left)

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(f"{r[0]:<{w[0]}} | {r[1]:<{w[1]}} | {r[2]:<{w[2]}} | {r[3]:<{w[3]}} | {r[4]}")
