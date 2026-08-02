"""Reconcile compac-harvest.json with slab-library (supplier Compac) + price book.
Main = Cabecera_* (their full-slab render), else Tablero non-regla, never the
tilted regla shot. Target aspect per colour from the price book (Standard
3030x1440 / Giant 3250x1630). --report / --apply.
"""
import csv, difflib, json, os, re, sys
import cv2
import numpy as np
from PIL import Image

def order_quad(pts):
    pts = pts.reshape(4, 2).astype(np.float64)
    s = pts.sum(1); dd = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(dd)], pts[np.argmax(s)], pts[np.argmax(dd)]], dtype=np.float32)

def find_slab_quad(img):
    h, w = img.shape[:2]
    scale_f = 1200 / w
    small = cv2.resize(img, (1200, int(h * scale_f)))
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    best, best_score = None, 0
    for lo in (10, 20, 40):
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), lo, lo * 3)
        edges = cv2.dilate(edges, np.ones((7, 7), np.uint8))
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            hull = cv2.convexHull(c)
            a = cv2.contourArea(hull)
            if not (0.18 * sw * sh < a < 0.985 * sw * sh):
                continue
            ap = None
            for eps in (0.01, 0.02, 0.03, 0.05, 0.08):
                cand = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
                if len(cand) == 4:
                    ap = cand
                    break
                if len(cand) < 4:
                    break
            if ap is None:
                continue
            q = order_quad(ap)
            qw = np.linalg.norm(q[1] - q[0]); qh = np.linalg.norm(q[3] - q[0])
            if qh == 0 or qw / qh < 1.2:
                continue
            if a / (sw * sh) > best_score:
                best, best_score = q, a / (sw * sh)
    return None if best is None else best / scale_f

Image.MAX_IMAGE_PIXELS = None
SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
CSV = r"C:\Users\thefi\stone-worktop-quotes\materials\supplier-price-book.csv"
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\COMPAC"

manifest = json.load(open(os.path.join(SCRATCH, "compac-harvest.json"), encoding="utf-8"))
lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
entries = [r for r in lib["slabs"] if r.get("supplier") == "Compac"]

pb = {}
for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
    if r["Supplier"] != "Compac":
        continue
    pb.setdefault(r["Colour"], {})[int(r["Thickness (mm)"])] = \
        f"{int(float(r['Slab Length (mm)']))}x{int(float(r['Slab Width (mm)']))}"

DROP = {"zero", "obsidiana", "hps", "tm"}
MAP = {"dimtm": "dim", "michelangelo": "michelangelo"}
def toks(s):
    out = set()
    for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split():
        w = MAP.get(w, w)
        if w in DROP:
            continue
        out.add(w)
    return out

def fuzzy_sub(a, b):
    for t in a:
        if t not in b and not difflib.get_close_matches(t, list(b), n=1, cutoff=0.8):
            return False
    return True

def best(name, pool):
    st = toks(name)
    top, score = None, (0, 0.0)
    for nm, obj in pool:
        ts = toks(nm)
        if ts and fuzzy_sub(ts, st) and fuzzy_sub(st, ts):   # two-way: names are exact-ish here
            r_ = difflib.SequenceMatcher(None, name.lower(), nm.lower()).ratio()
            if (len(ts), r_) > score:
                top, score = obj, (len(ts), r_)
    return top

# hand-set warp sources+corners (TL,TR,BR,BL fractions) where detection fails
MANUAL = {
 "Alaska": ("Alaska-COMPAC-tablero.png", [[0.148,0.15],[0.845,0.15],[0.978,0.768],[0.032,0.768]]),
 "Ice Ink": ("INK_TABLERO_SIN_REGLA.jpg", [[0.19,0.12],[0.862,0.115],[0.985,0.79],[0.028,0.795]]),
 "Ice Max Black": ("Tablero_CR_ICEMAXBLACK.jpg", [[0.150,0.385],[0.842,0.381],[0.938,0.559],[0.051,0.571]]),
 "Ice Viola": ("TABLERO_VIOLA_SREGLA.jpg", [[0.19,0.12],[0.862,0.115],[0.985,0.79],[0.028,0.795]]),
 "Luxury Borghini": ("Tablero_Luxury_Borghini_LOW-scaled.jpeg", [[0.115,0.07],[0.905,0.065],[0.985,0.74],[0.02,0.745]]),
 "Luxury Vagli Oro": ("COMPAC┬-Tablero_U-CALACATTA-VAGLI-scaled.jpg", [[0.13,0.06],[0.90,0.06],[0.985,0.79],[0.02,0.79]]),
 "Luxury Vagli Macchia Vecchia": ("COMPAC┬-Tablero_U-CALACATTA-VAGLI-scaled.jpg", [[0.13,0.06],[0.90,0.06],[0.985,0.79],[0.02,0.79]]),
 "Absolute Blanc": ("absolute_blanc_referencia1.jpg", [[0.125,0.415],[0.895,0.415],[0.975,0.575],[0.025,0.578]]),
 "Plomo": ("Plomo-referencia.jpg", [[0.142,0.42],[0.863,0.418],[0.972,0.585],[0.028,0.587]]),
}

lib_pool = [(r["colour"], r) for r in entries]
pb_pool = [(k, k) for k in pb]
apply_mode = "--apply" in sys.argv
rows_out, matched = [], set()

for m in manifest:
    colour = re.sub(r"^NEW design\s*-\s*", "", m["colour"], flags=re.I).split(".")[0].strip()
    entry = best(colour, lib_pool)
    pbc = best(colour, pb_pool)
    sizes = pb.get(pbc, {}) if pbc else {}
    slab_sizes = " / ".join(f"{t}mm: {s}" for t, s in sorted(sizes.items()))
    ms = re.search(r"(\d{3,4})x(\d{3,4})", slab_sizes)
    tgt = (int(ms.group(1)) / int(ms.group(2))) if ms else 3250 / 1630

    folder = os.path.join(DEST_ROOT, re.sub(r'[<>:"/\\|?*]', "", colour).strip())
    cands = []
    for f in m["files"]:
        if f.get("error"):
            continue
        p = os.path.join(folder, f["file"])
        if not os.path.exists(p):
            continue
        fl = f["file"].lower()
        if re.search(r"isotipo|aplicaciones|formato_|logo", fl):
            continue
        try:
            with Image.open(p) as im:
                w, h = im.size
        except Exception:
            continue
        if w < 800:
            continue
        ar = w / h
        regla = "regla" in fl
        tab = ("tablero" in fl) and not regla
        tab_regla = ("tablero" in fl) and regla
        cab = "cabecera" in fl
        ctoks = [t for t in re.sub(r"[^a-z0-9 ]", " ", colour.lower()).split() if len(t) > 3]
        fn_n = re.sub(r"[^a-z0-9]", "", fl)
        name_hit = any(t in fn_n for t in ctoks) if ctoks else True
        good = (1.8 <= ar <= 2.3) or (ar > 0 and 1.8 <= 1 / ar <= 2.3)
        cands.append(((name_hit, tab, tab_regla, cab, good, w), f["file"], ar))
    cands.sort(reverse=True, key=lambda c: c[0])
    main = cands[0] if cands else None
    rows_out.append((f"{colour} [{m['range']}]", "match" if entry else "NEW",
                     entry["colour"] if entry else "-", pbc or "NO PRICEBOOK",
                     (f"{main[1]} ar={main[2]:.2f}" if main else "NO IMAGE") +
                     (f" | tgt={tgt:.2f}" if main else "")))
    if not apply_mode:
        continue
    if entry is None:
        entry = {"id": "compac--" + re.sub(r"[^a-z0-9]+", "-", colour.lower()).strip("-"),
                 "supplier": "Compac", "colour": colour,
                 "material": "Obsidiana" if "obsidiana" in (m["range"] or "").lower() else "Quartz",
                 "naturalStone": False, "illustrationOnly": False,
                 "thicknesses": sorted(sizes) if sizes else [20, 30],
                 "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""}}
        lib["slabs"].append(entry)
        lib_pool.append((colour, entry))
    matched.add(entry["id"])
    entry["productUrl"] = m["url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
        entry["thicknesses"] = sorted(sizes)
    if m.get("range"):
        entry["details"] = m["range"]
    if colour in MANUAL:
        mf, mc = MANUAL[colour]
        # the Vagli assets live in the 'Luxury Vagli Oro' folder for both colours
        mfold = folder if os.path.exists(os.path.join(folder, mf)) else \
            os.path.join(DEST_ROOT, "Luxury Vagli Oro")
        raw = cv2.imdecode(np.fromfile(os.path.join(mfold, mf), dtype=np.uint8), cv2.IMREAD_COLOR)
        h, w = raw.shape[:2]
        quad = np.array([[x * w, y * h] for x, y in mc], dtype=np.float32)
        ow, oh = 1600, round(1600 / tgt)
        dst = np.array([[0, 0], [ow, 0], [ow, oh], [0, oh]], dtype=np.float32)
        out = cv2.warpPerspective(raw, cv2.getPerspectiveTransform(quad, dst), (ow, oh), flags=cv2.INTER_AREA)
        im2 = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
        fn = entry["id"] + ".webp"
        im2.save(os.path.join(LIB, "images", fn), "WEBP", quality=87)
        entry["image"] = {"file": fn, "status": "slab", "source": m["url"],
                          "borrowedFrom": "", "scale": "true"}
        continue
    if main:
        fname = main[1]
        p = os.path.join(folder, fname)
        scale = None
        im = None
        if "tablero" in fname.lower():
            raw = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
            if raw is not None:
                quad = find_slab_quad(raw)
                if quad is not None:
                    ow, oh = 1600, round(1600 / tgt)
                    dst = np.array([[0, 0], [ow, 0], [ow, oh], [0, oh]], dtype=np.float32)
                    out = cv2.warpPerspective(raw, cv2.getPerspectiveTransform(quad.astype(np.float32), dst),
                                              (ow, oh), flags=cv2.INTER_AREA)
                    im = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
                    scale = "true"
        if im is None:
            im = Image.open(p)
            if im.mode != "RGB":
                im = im.convert("RGB")
            ar = im.width / im.height
            if ar < 1 and abs((1 / ar) - tgt) / tgt < 0.05:
                im = im.transpose(Image.Transpose.ROTATE_90)
                ar = im.width / im.height
            if abs(ar - tgt) / tgt < 0.05:
                im = im.resize((1600, round(1600 / tgt)), Image.LANCZOS)
                scale = "true"
            else:
                if im.width > 1600:
                    im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
                scale = "approx"
        fn = entry["id"] + ".webp"
        im.save(os.path.join(LIB, "images", fn), "WEBP", quality=87)
        entry["image"] = {"file": fn, "status": "slab",
                          "source": m["url"], "borrowedFrom": "", "scale": scale}

if apply_mode:
    import datetime
    lib["generated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(lib, open(os.path.join(LIB, "slabs.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    left = sorted(r["colour"] for r in entries if r["id"] not in matched)
    print("APPLIED. Library Compac colours NOT on the site:", left)

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(f"{r[0]:<{w[0]}} | {r[1]:<{w[1]}} | {r[2]:<{w[2]}} | {r[3]:<{w[3]}} | {r[4]}")
