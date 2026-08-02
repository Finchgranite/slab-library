"""Phase 2 (AKG Surfaces): reconcile akg-harvest.json with slab-library + price book.
--report : match table only. --apply : merge legacy folders, write webps + slabs.json.
Sizes come from the SITE (Size/Thickness/Finishes lines); price book is a cross-check.
"""
import csv, difflib, json, os, re, shutil, sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
CSV = r"C:\Users\thefi\stone-worktop-quotes\materials\supplier-price-book.csv"
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\AKG SURFACES (Sempre-Coante)"

manifest = json.load(open(os.path.join(SCRATCH, "akg-harvest.json"), encoding="utf-8"))
lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
entries = {r["id"]: r for r in lib["slabs"] if r.get("supplier") == "AKG Surfaces"}

pb = {}
for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
    if r["Supplier"] != "AKG Surfaces":
        continue
    pb.setdefault(r["Colour"], {}).setdefault(
        r["Thickness (mm)"],
        f"{int(float(r['Slab Length (mm)']))}x{int(float(r['Slab Width (mm)']))}")

DROP = {"akg", "surfaces", "sempre", "coante", "arteo", "low", "silica", "p", "calacatta"}
# NOTE: 'calacatta' dropped ONLY for cross-matching prefixed/unprefixed variants
# (site 'Calacatta Aurora Gold' = pb 'Aurora Gold'); safe here because every
# remaining token pair stays distinctive within AKG's 48-colour range.
def toks(s):
    out = set()
    for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split():
        if w in DROP or w.isdigit():
            continue
        out.add({"gray": "grey"}.get(w, w))
    return out

def fuzzy_tok_subset(lib_t, site_t):
    for lt in lib_t:
        if lt not in site_t and not difflib.get_close_matches(lt, list(site_t), n=1, cutoff=0.8):
            return False
    return True

def best(site_name, pool):
    st = toks(site_name)
    top, top_score = None, (0, 0.0)
    for name, obj in pool:
        ts = toks(name)
        if ts and fuzzy_tok_subset(ts, st):
            ratio = difflib.SequenceMatcher(None, site_name.lower(), name.lower()).ratio()
            if (len(ts), ratio) > top_score:
                top, top_score = obj, (len(ts), ratio)
    return top

apply_mode = "--apply" in sys.argv
if apply_mode:
    from PIL import Image

lib_pool = [(v["colour"], v) for v in entries.values()]
pb_pool = [(k, k) for k in pb]

existing_dirs = [d for d in os.listdir(DEST_ROOT) if os.path.isdir(os.path.join(DEST_ROOT, d))]

rows, matched_ids = [], set()
for m in manifest:
    if m.get("error"):
        rows.append((m["url"], "ERROR", m["error"], "", ""))
        continue
    entry = best(m["colour"], lib_pool)
    pbc = best(m["colour"], pb_pool)

    info = m.get("info", {})
    size, thk, fin = info.get("Size", ""), info.get("Thickness", ""), info.get("Finishes", "")
    thks = sorted({int(x) for x in re.findall(r"(\d+)\s*mm", thk)}) if thk else []
    site_size = re.sub(r"\s*mm\s*$", "", size).replace(" ", "")
    slab_sizes = " / ".join(f"{t}mm: {site_size}" for t in thks) if site_size and thks else \
                 (f"{site_size}" if site_size else "")

    pb_sizes = pb.get(pbc, {}) if pbc else {}
    if not slab_sizes and pb_sizes:
        slab_sizes = " / ".join(f"{t}mm: {s}" for t, s in
                                sorted(pb_sizes.items(), key=lambda kv: int(kv[0]))) + " (price book)"
        thks = sorted(int(t) for t in pb_sizes)
    pb_note = ""
    if pbc and site_size:
        pbs = set(pb_sizes.values())
        if pbs and site_size not in pbs:
            pb_note = f"PB={'/'.join(sorted(pbs))} SITE={site_size}"

    rows.append((f"{m['colour']} [{m['range']}]",
                 "match" if entry else "NEW",
                 entry["colour"] if entry else "-",
                 pbc if pbc else "NO PRICEBOOK",
                 (slab_sizes or "-") + ((" | SIZE MISMATCH " + pb_note) if pb_note else "")))

    if not apply_mode:
        continue

    canonical = entry["colour"] if entry else m["colour"]
    if entry:
        matched_ids.add(entry["id"])
    else:
        entry = {"id": "akg-surfaces--" + re.sub(r"[^a-z0-9]+", "-", canonical.lower()).strip("-"),
                 "supplier": "AKG Surfaces", "colour": canonical, "material": "Quartz",
                 "naturalStone": False, "illustrationOnly": False, "thicknesses": [],
                 "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""}}
        lib["slabs"].append(entry)
        lib_pool.append((canonical, entry))
        matched_ids.add(entry["id"])

    # folder: canonical name; merge site-named and legacy numbered folders into it
    cdir = os.path.join(DEST_ROOT, canonical)
    for d in list(existing_dirs) + [m["colour"]]:
        src = os.path.join(DEST_ROOT, d)
        if d == canonical or not os.path.isdir(src):
            continue
        if fuzzy_tok_subset(toks(d), toks(canonical)) and fuzzy_tok_subset(toks(canonical), toks(d)):
            os.makedirs(cdir, exist_ok=True)
            for f in os.listdir(src):
                dst = os.path.join(cdir, f)
                if not os.path.exists(dst):
                    shutil.move(os.path.join(src, f), dst)
            try:
                os.rmdir(src)
            except OSError:
                pass
            if d in existing_dirs:
                existing_dirs.remove(d)

    entry["productUrl"] = m["url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    if thks:
        entry["thicknesses"] = thks
    det = [f"{m['range']} range"]
    if m["code"]:
        det.append(f"code {m['code']}")
    for k in ("Size", "Thickness", "Finishes"):
        if info.get(k):
            det.append(f"{k}: {info[k]}")
    entry["details"] = ". ".join([det[0] + (f" ({det[1]})" if m["code"] else "")] + det[2 if m["code"] else 1:])

    main_file = next((f["file"] for f in m["images"] if f.get("main")), None)
    if main_file:
        src = os.path.join(cdir, main_file)
        if os.path.exists(src):
            im = Image.open(src)
            if im.mode != "RGB":
                im = im.convert("RGB")
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            fn = entry["id"] + ".webp"
            im.save(os.path.join(LIB, "images", fn), "WEBP", quality=85)
            entry["image"] = {"file": fn, "status": "slab", "source": m["main"], "borrowedFrom": ""}

if apply_mode:
    json.dump(lib, open(os.path.join(LIB, "slabs.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    left = [v["colour"] for v in entries.values() if v["id"] not in matched_ids]
    print("slabs.json updated. Library AKG colours NOT on the site:", left)

w = [max((len(str(r[i])) for r in rows), default=10) for i in range(4)]
for r in rows:
    print(f"{r[0]:<{w[0]}} | {r[1]:<{w[1]}} | {r[2]:<{w[2]}} | {r[3]:<{w[3]}} | {r[4]}")
