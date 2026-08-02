"""Generic slab-face-only TRUE-SCALE pass (generalised from akg_slabify.py).

Usage: python slabify_supplier.py "BQS" [--apply]
Reads/writes the supplier's mains in the slab-library; corners overrides in
slabify_overrides_<slug>.json next to this script. Source = the current main
webp (what's already approved as the main image).
"""
import json, os, re, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"

SUPPLIER = sys.argv[1]
slug = re.sub(r"[^a-z0-9]+", "", SUPPLIER.lower())
OV_PATH = os.path.join(SCRATCH, f"slabify_overrides_{slug}.json")
OVERRIDES = json.load(open(OV_PATH, encoding="utf-8")) if os.path.exists(OV_PATH) else {}

lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
rows = sorted([r for r in lib["slabs"] if r.get("supplier") == SUPPLIER and r["image"].get("file")],
              key=lambda r: r["colour"])
print(len(rows), "entries with images")

def target_aspect(r):
    m = re.search(r"(\d{3,4})x(\d{3,4})", r.get("slabSizes", ""))
    return (int(m.group(1)) / int(m.group(2))) if m else 2.0

def order_quad(pts):
    pts = pts.reshape(4, 2).astype(np.float64)
    s = pts.sum(1); dd = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(dd)], pts[np.argmax(s)], pts[np.argmax(dd)]], dtype=np.float32)

def find_slab_quad(img):
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
                    if qh == 0 or qw / qh < 1.2:
                        continue
                    cx, cy = q.mean(0)
                    pen = abs(cx - sw / 2) / sw + abs(cy - sh / 2) / sh
                    if a / (sw * sh) - pen > best_score:
                        best, best_score = q, a / (sw * sh) - pen
                    break
    return None if best is None else best / scale

def warp(img, quad, aspect):
    out_w = 1600
    out_h = round(out_w / aspect)
    dst = np.array([[0, 0], [out_w, 0], [out_w, out_h], [0, out_h]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    return cv2.warpPerspective(img, M, (out_w, out_h), flags=cv2.INTER_AREA)

apply_mode = "--apply" in sys.argv
results = []
for r in rows:
    ov = OVERRIDES.get(r["colour"])
    if ov == "skip":
        results.append((r, None, "SKIP", None)); continue
    forced = None
    if isinstance(ov, dict):
        forced = ov.get("scale")
        ov = ov.get("corners")
    sp = os.path.join(LIB, "images", r["image"]["file"])
    img = cv2.imdecode(np.fromfile(sp, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        results.append((r, None, "READ FAIL", None)); continue
    asp = target_aspect(r)
    quad = None
    if ov == "bandcrop":
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
        out, status, flag = warp(img, quad, asp), "warped", "true"
    else:
        ia = img.shape[1] / img.shape[0]
        if abs(ia - asp) / asp < 0.04:
            out, status, flag = cv2.resize(img, (1600, round(1600 / asp)), interpolation=cv2.INTER_AREA), \
                "edge-to-edge (aspect ok %.3f)" % ia, "true"
        else:
            out, status, flag = img, "edge-to-edge ASPECT OFF (%.2f vs %.2f)" % (ia, asp), "approx"
    if forced:
        flag = forced
        status += " (forced %s)" % forced
    results.append((r, out, status, flag))
    print(f"{r['colour']:<28} {status}")

CW, CH, LH = 400, 210, 26
for si in range(0, len(results), 8):
    grp = results[si:si + 8]
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
    sheet.save(os.path.join(SCRATCH, f"slabify_{slug}_{si//8+1}.png"))
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
          sum(1 for _, o, _, f in results if f == "approx"), "approx")
