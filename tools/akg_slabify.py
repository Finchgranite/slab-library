"""Make every AKG main image a slab-face-only, TRUE-SCALE image.

Photos with background: detect the slab's 4 corners, perspective-warp exactly
that quad to the slab's real aspect (from slabSizes) -> scale correct by
construction. Edge-to-edge images: keep, classify by how close their aspect
is to the real slab. Writes image.scale = 'true'|'approx' on each entry.
Produces before/after contact sheets; --apply writes webps + slabs.json.
"""
import json, os, re, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
DEST = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\AKG SURFACES (Sempre-Coante)"

# manual corner overrides (fractions of width/height: TL,TR,BR,BL), set after review
OVERRIDES = json.load(open(os.path.join(SCRATCH, "slabify_overrides.json"), encoding="utf-8")) \
    if os.path.exists(os.path.join(SCRATCH, "slabify_overrides.json")) else {}

lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
akg = sorted([r for r in lib["slabs"] if r.get("supplier") == "AKG Surfaces" and r["image"].get("file")],
             key=lambda r: r["colour"])

def target_aspect(r):
    m = re.search(r"(\d{3,4})x(\d{3,4})", r.get("slabSizes", ""))
    if m:
        return int(m.group(1)) / int(m.group(2))
    return 3200 / 1600

def source_path(r):
    src = r["image"].get("source", "")
    fn = os.path.basename(src.split("?")[0]) if src.startswith("http") else ""
    folder = os.path.join(DEST, r["colour"])
    if fn and os.path.isdir(folder):
        # exact, then fuzzy (-scaled etc.), then base-name match
        for cand in os.listdir(folder):
            if cand == fn:
                return os.path.join(folder, cand)
        stem = re.sub(r"\.(jpe?g|png|webp)$", "", fn, flags=re.I)
        for cand in os.listdir(folder):
            if cand.startswith(stem):
                return os.path.join(folder, cand)
    return os.path.join(LIB, "images", r["image"]["file"])

def order_quad(pts):
    pts = pts.reshape(4, 2).astype(np.float64)
    s = pts.sum(1); d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)

def find_slab_quad(img):
    """Return quad (TL,TR,BR,BL) in image coords, or None if edge-to-edge."""
    h, w = img.shape[:2]
    scale = 1200 / w
    small = cv2.resize(img, (1200, int(h * scale)))
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    best, best_score = None, 0
    for canny_lo in (30, 60):
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), canny_lo, canny_lo * 3)
        edges = cv2.dilate(edges, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            a = cv2.contourArea(c)
            if not (0.20 * sw * sh < a < 0.97 * sw * sh):
                continue
            for eps in (0.01, 0.02, 0.03):
                ap = cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True)
                if len(ap) == 4 and cv2.isContourConvex(ap):
                    q = order_quad(ap)
                    qw = np.linalg.norm(q[1] - q[0]); qh = np.linalg.norm(q[3] - q[0])
                    if qh == 0 or qw / qh < 1.2:      # slabs are landscape
                        continue
                    cx, cy = q.mean(0)
                    center_pen = abs(cx - sw / 2) / sw + abs(cy - sh / 2) / sh
                    score = a / (sw * sh) - center_pen
                    if score > best_score:
                        best, best_score = q, score
                    break
    if best is None:
        return None
    return best / scale

def warp(img, quad, aspect):
    out_w = 1600
    out_h = round(out_w / aspect)
    dst = np.array([[0, 0], [out_w, 0], [out_w, out_h], [0, out_h]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    return cv2.warpPerspective(img, M, (out_w, out_h), flags=cv2.INTER_AREA)

apply_mode = "--apply" in sys.argv
results = []
for r in akg:
    ov = OVERRIDES.get(r["colour"])
    if ov == "skip":
        results.append((r, None, "SKIP (override)", None)); continue
    forced_flag = None
    if isinstance(ov, dict):
        src = ov.get("src")
        if src == "webp":
            sp = os.path.join(LIB, "images", r["image"]["file"])
        elif src:
            sp = os.path.join(DEST, r["colour"], src)
        else:
            sp = source_path(r)
        forced_flag = ov.get("scale")
        ov = ov.get("corners")
    else:
        sp = source_path(r)
    data = np.fromfile(sp, dtype=np.uint8)     # np.fromfile handles unicode paths
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        results.append((r, None, "READ FAIL", None)); continue
    asp = target_aspect(r)
    quad = None
    if ov == "bandcrop":
        # strip a uniform grey band from the bottom of a render; no detection
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h = img.shape[0]
        cut = h
        while cut > h * 0.7:
            row = g[cut - 1]
            if row.std() < 6 and 90 < row.mean() < 190:
                cut -= 1
            else:
                break
        img = img[:max(1, cut - round(img.shape[0] * 0.012))]
    elif isinstance(ov, list):
        h, w = img.shape[:2]
        quad = np.array([[x * w, y * h] for x, y in ov], dtype=np.float32)
    else:
        quad = find_slab_quad(img)
    if quad is not None:
        out = warp(img, quad, asp)
        status = "warped"
        scale_flag = "true"
    else:
        out = img
        ia = img.shape[1] / img.shape[0]
        if abs(ia - asp) / asp < 0.04:
            status, scale_flag = "edge-to-edge (aspect ok %.3f)" % ia, "true"
            out = cv2.resize(img, (1600, round(1600 / asp)), interpolation=cv2.INTER_AREA)
        else:
            status, scale_flag = "edge-to-edge ASPECT OFF (%.2f vs %.2f)" % (ia, asp), "approx"
            if img.shape[1] > 1600:
                out = cv2.resize(img, (1600, round(1600 * img.shape[0] / img.shape[1])), interpolation=cv2.INTER_AREA)
    if forced_flag:
        scale_flag = forced_flag
        status += " (flag forced %s)" % forced_flag
    results.append((r, out, status, scale_flag))
    print(f"{r['colour']:<28} {status}")

# contact sheets: before | after
CW, CH, LH = 400, 210, 26
per = 8
for si in range(0, len(results), per):
    grp = results[si:si + per]
    sheet = Image.new("RGB", (2 * CW + 30, len(grp) * (CH + LH)), (240, 240, 244))
    dr = ImageDraw.Draw(sheet)
    for i, (r, out, status, flag) in enumerate(grp):
        y = i * (CH + LH)
        try:
            b = Image.open(os.path.join(LIB, "images", r["image"]["file"])).convert("RGB")
            s = min(CW / b.width, CH / b.height); b = b.resize((int(b.width * s), int(b.height * s)))
            sheet.paste(b, ((CW - b.width) // 2, y + (CH - b.height) // 2))
        except Exception:
            pass
        if out is not None:
            a = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
            s = min(CW / a.width, CH / a.height); a = a.resize((int(a.width * s), int(a.height * s)))
            sheet.paste(a, (CW + 30 + (CW - a.width) // 2, y + (CH - a.height) // 2))
        dr.text((6, y + CH + 4), f"{r['colour']}  |  {status}  |  scale={flag}", fill=(0, 0, 0))
    sheet.save(os.path.join(SCRATCH, f"slabify_{si//per+1}.png"))
print("sheets written")

if apply_mode:
    import datetime
    for r, out, status, flag in results:
        if out is None:
            continue
        Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)).save(
            os.path.join(LIB, "images", r["image"]["file"]), "WEBP", quality=87)
        r["image"]["scale"] = flag
    lib["generated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(lib, open(os.path.join(LIB, "slabs.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print("APPLIED:", sum(1 for _, o, _, f in results if o is not None), "images;",
          sum(1 for _, o, _, f in results if f == "approx"), "flagged approx")
