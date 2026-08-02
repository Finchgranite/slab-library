"""Phase 2: reconcile harvest.json with slab-library slabs.json + price book.
--report : print the match table only, change nothing.
--apply  : convert main images to webp and update slabs.json.
"""
import csv, difflib, json, os, re, sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\thefi\slab-library"
CSV = r"C:\Users\thefi\stone-worktop-quotes\materials\supplier-price-book.csv"
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\3. CERAMIC- PORCELAIN\Infinity porcelain - clay international"

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())

manifest = json.load(open(os.path.join(SCRATCH, "harvest.json"), encoding="utf-8"))
lib = json.load(open(os.path.join(LIB, "slabs.json"), encoding="utf-8"))
clay_entries = {norm(r["colour"]): r for r in lib["slabs"] if r.get("supplier") == "Clay International"}

# price book: colour -> {thickness: LxW}
pb = {}
for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
    if "Clay" not in r["Supplier"]:
        continue
    key = norm(r["Colour"])
    thk = r["Thickness (mm)"]
    size = f"{int(float(r['Slab Length (mm)']))}x{int(float(r['Slab Width (mm)']))}"
    pb.setdefault(key, {"colour": r["Colour"], "sizes": {}})["sizes"].setdefault(thk, size)

DROP = {"holos", "arkeon", "0c09"}
def toks(s):
    out = set()
    for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split():
        if w in DROP:
            continue
        out.add({"gray": "grey"}.get(w, w))
    return out

def fuzzy_tok_subset(lib_t, site_t):
    # every library token must fuzzily appear among the site tokens
    for lt in lib_t:
        if lt not in site_t and not difflib.get_close_matches(lt, list(site_t), n=1, cutoff=0.8):
            return False
    return True

def best_entry(site_name, pool):
    """pool: {normkey: (tokset, obj)} -> obj with most tokens whose tokens all
    (fuzzily) appear in the site name's tokens."""
    st = toks(site_name)
    best, best_score = None, (0, 0.0)
    for tokset, obj in pool.values():
        if tokset and fuzzy_tok_subset(tokset, st):
            ratio = difflib.SequenceMatcher(
                None, site_name.lower(), obj["colour"].lower()).ratio()
            score = (len(tokset), ratio)
            if score > best_score:
                best, best_score = obj, score
    return best

apply_mode = "--apply" in sys.argv
if apply_mode:
    from PIL import Image

rows_out, new_count = [], 0
for m in manifest:
    if m.get("error") or m.get("skipped"):
        rows_out.append((m.get("colour", m["url"]), "SKIP", m.get("skipped") or m.get("error"), "", ""))
        continue
    lib_pool = {k: (toks(v["colour"]), v) for k, v in clay_entries.items()}
    pb_pool = {k: (toks(v["colour"]), v) for k, v in pb.items()}
    entry = best_entry(m["colour"], lib_pool)
    pbe = best_entry(m["colour"], pb_pool)
    sizes = pbe["sizes"] if pbe else {}

    # slabSizes text: annotate rectified info from the details rows if present
    rect = {}
    for row in m["details_rows"]:
        mm_m = re.match(r"(\d+)mm:", row)
        if mm_m:
            tag = "Rectified" if re.search(r"\(Rectified\)", row) else \
                  ("Non-Rectified" if "Non-Rectified" in row else "")
            rect[mm_m.group(1)] = tag
    slab_sizes = " / ".join(
        f"{t}mm: {s}" + (f" ({rect[t]})" if rect.get(t) else "")
        for t, s in sorted(sizes.items(), key=lambda kv: int(kv[0])))

    details = (f"Infinity {m['code']}. " if m["code"] else "") + "; ".join(m["details_rows"])

    status = "match" if entry else "NEW"
    rows_out.append((m["colour"], status,
                     entry["colour"] if entry else "-",
                     pbe["colour"] if pbe else "NO PRICEBOOK",
                     slab_sizes or "-"))

    if not apply_mode:
        continue

    # canonicalise the OneDrive folder to the library colour name
    folder_name = m["colour"]
    if entry and entry["colour"] != m["colour"]:
        src_dir = os.path.join(DEST_ROOT, m["colour"])
        dst_dir = os.path.join(DEST_ROOT, entry["colour"])
        if os.path.isdir(src_dir) and not os.path.isdir(dst_dir):
            os.rename(src_dir, dst_dir)
        folder_name = entry["colour"]

    if entry is None:
        new_count += 1
        entry = {"id": "clay-international--" + re.sub(r"[^a-z0-9]+", "-", m["colour"].lower()).strip("-"),
                 "supplier": "Clay International", "colour": m["colour"],
                 "material": "Porcelain", "naturalStone": False, "illustrationOnly": False,
                 "thicknesses": sorted(int(t) for t in sizes) or [],
                 "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""}}
        lib["slabs"].append(entry)
        clay_entries[norm(m["colour"])] = entry

    entry["productUrl"] = m["url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    if details:
        entry["details"] = details
    if sizes:
        entry["thicknesses"] = sorted(int(t) for t in sizes)

    if m["main"]:
        src = os.path.join(DEST_ROOT, folder_name, os.path.basename(m["main"].split("?")[0]))
        if os.path.exists(src):
            im = Image.open(src)
            if im.mode in ("RGBA", "P"):
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[3])
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            fn = entry["id"] + ".webp"
            im.save(os.path.join(LIB, "images", fn), "WEBP", quality=85)
            entry["image"] = {"file": fn, "status": "slab", "source": m["main"], "borrowedFrom": ""}

if apply_mode:
    json.dump(lib, open(os.path.join(LIB, "slabs.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print("slabs.json updated;", new_count, "new entries;",
          len(lib["slabs"]), "total entries")

w = [max(len(str(r[i])) for r in rows_out) for i in range(4)]
for r in rows_out:
    print(f"{r[0]:<{w[0]}} | {r[1]:<{w[1]}} | {r[2]:<{w[2]}} | {r[3]:<{w[3]}} | {r[4]}")
