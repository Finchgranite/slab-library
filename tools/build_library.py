"""Build/refresh slabs.json from the price book + local brand image folders.

Usage:
  python tools/build_library.py --seed
      Seed slabs.json with one entry per supplier+colour from the price book
      (keeps any existing image assignments).

  python tools/build_library.py --supplier "Cosentino Silestone" --folder "<path>"
      Scan a brand folder, match images to that supplier's colours, pick the
      best full-slab shot, convert to images/*.webp, update slabs.json, and
      append match decisions to tools/match-report.csv for review.
"""
import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
PRICE_BOOK = Path(r"C:\Users\thefi\stone-worktop-quotes\materials\supplier-price-book.csv")
SLABS_JSON = REPO / "slabs.json"
IMAGES_DIR = REPO / "images"
REPORT_CSV = REPO / "tools" / "match-report.csv"

NATURAL_STONE = {"Granite", "Quartzite", "Marble", "Limestone", "Travertine", "Slate", "Obsidiana"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_WIDTH = 1600
WEBP_QUALITY = 82


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def load_price_book():
    with open(PRICE_BOOK, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_slabs():
    if SLABS_JSON.exists():
        return json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    return {"generated": "", "slabs": []}


def save_slabs(db):
    db["generated"] = date.today().isoformat()
    db["slabs"].sort(key=lambda s: (s["supplier"], s["colour"]))
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")


def seed(db):
    rows = load_price_book()
    by_id = {s["id"]: s for s in db["slabs"]}
    url_col = next((c for c in rows[0] if "URL" in c), None)
    groups = {}
    for r in rows:
        key = (r["Supplier"].strip(), r["Colour"].strip())
        g = groups.setdefault(key, {"material": r["Material"].strip(), "thicknesses": set(), "url": ""})
        try:
            g["thicknesses"].add(int(float(r["Thickness (mm)"])))
        except (ValueError, KeyError):
            pass
        if url_col and r.get(url_col, "").strip():
            g["url"] = r[url_col].strip()
    added = 0
    for (supplier, colour), g in groups.items():
        sid = f"{slug(supplier)}--{slug(colour)}"
        natural = g["material"] in NATURAL_STONE
        if sid in by_id:
            e = by_id[sid]
            e["thicknesses"] = sorted(g["thicknesses"])
            if g["url"] and not e.get("productUrl"):
                e["productUrl"] = g["url"]
        else:
            by_id[sid] = {
                "id": sid,
                "supplier": supplier,
                "colour": colour,
                "material": g["material"],
                "naturalStone": natural,
                "illustrationOnly": natural,
                "thicknesses": sorted(g["thicknesses"]),
                "productUrl": g["url"],
                "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""},
            }
            added += 1
    db["slabs"] = list(by_id.values())
    print(f"Seeded: {len(db['slabs'])} entries ({added} new)")


def score_file(path, rel_path):
    """Score an image file as a full-slab-shot candidate. Higher = better.

    rel_path must be relative to the brand folder being scanned — the OneDrive
    parent folder is named "...Kitchens-Website", which would otherwise mark
    every file as a kitchen shot.
    """
    name = norm(path.stem)
    rel = norm(str(rel_path))
    s = 0
    kind = "unclear"
    if "slab" in name:
        s += 100
        kind = "slab"
    if "fullslab" in name:
        s += 20
    if "kitchen" in rel:
        s -= 120
        kind = "kitchen"
    if "worktop" in name or "interior" in name:
        s -= 80
        if kind == "unclear":
            kind = "installed"
    if "close" in name or "detail" in name:
        s -= 60
        kind = "closeup"
    if "sample" in name:
        s += 10
    if "screenshot" in name:
        s -= 20
    try:
        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return None, None, None
    if w < 500:
        s -= 40
    ratio = w / h if h else 0
    if 1.5 <= ratio <= 2.6:
        s += 40  # slab-shaped
        if kind == "unclear":
            kind = "slab-shaped"
    elif kind == "unclear" and (0.8 <= ratio <= 1.25):
        kind = "square-ish"
    s += min(w, 3000) / 300  # mild preference for resolution
    return s, kind, (w, h)


def find_candidates(files, colour):
    """Match by full name, then progressively drop trailing tokens
    ("Blanco Maple14" -> "Blanco Maple", "Coral Clay Colour" -> "Coral Clay")."""
    tries = [colour, re.sub(r"\d+$", "", colour)]
    words = colour.split()
    while len(words) > 1:
        words = words[:-1]
        tries.append(" ".join(words))
    for i, t in enumerate(tries):
        tn = norm(t)
        if not tn or (i > 0 and len(tn) < 5):  # length guard on shortened variants only
            continue
        cands = [f for f in files if tn in norm(str(f))]
        if cands:
            return cands
    return []


def convert(src, dest):
    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > MAX_WIDTH:
            im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
        im.save(dest, "WEBP", quality=WEBP_QUALITY)


def scan(db, supplier, folder, only_missing=False):
    folder = Path(folder)
    if not folder.is_dir():
        sys.exit(f"Folder not found: {folder}")
    entries = [s for s in db["slabs"] if s["supplier"] == supplier]
    if only_missing:
        entries = [s for s in entries if not s["image"]["file"]]
    if not entries:
        sys.exit(f"No entries for supplier {supplier!r} — run --seed first")
    files = [p for p in folder.rglob("*") if p.suffix.lower() in IMG_EXTS]
    print(f"{supplier}: {len(entries)} colours, {len(files)} images in {folder.name}")

    report_rows = []
    matched = 0
    for e in entries:
        cands = find_candidates(files, e["colour"])
        best, best_score, best_kind, best_dims = None, None, None, None
        for f in cands:
            s, kind, dims = score_file(f, f.relative_to(folder))
            if s is None:
                continue
            if best_score is None or s > best_score:
                best, best_score, best_kind, best_dims = f, s, kind, dims
        if best is None:
            report_rows.append([supplier, e["colour"], "NO MATCH", "", "", ""])
            continue
        status = "slab" if best_kind in ("slab", "slab-shaped") else "closeup-only"
        fname = f"{e['id']}.webp"
        convert(best, IMAGES_DIR / fname)
        e["image"] = {"file": fname, "status": status, "source": "onedrive-brands-folder", "borrowedFrom": ""}
        matched += 1
        report_rows.append([supplier, e["colour"], status, best_kind,
                            f"{best_dims[0]}x{best_dims[1]}", str(best.relative_to(folder))])

    new_file = not REPORT_CSV.exists()
    with open(REPORT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["supplier", "colour", "status", "kind", "dims", "chosen_file"])
        w.writerows(report_rows)
    print(f"Matched {matched}/{len(entries)}; report appended to {REPORT_CSV.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--supplier")
    ap.add_argument("--folder")
    ap.add_argument("--only-missing", action="store_true",
                    help="only fill entries with no image (keep website scrapes)")
    args = ap.parse_args()
    db = load_slabs()
    if args.seed:
        seed(db)
    if args.supplier:
        if not args.folder:
            sys.exit("--supplier needs --folder")
        scan(db, args.supplier, args.folder, args.only_missing)
    save_slabs(db)


if __name__ == "__main__":
    main()
