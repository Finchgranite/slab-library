"""Reconcile Bloomstones (quartz+porcelain) against slabs.json + price book.

Ground truth is NOT scraped <img> tags -- it's the Wix "wix-warmup-data" CMS
collection JSON embedded in each product page (fields: QuartzSamples.mediaPics[]
/ PorcelaineSlabs.images[], each item with a real fileName/title, slug (wixstatic
media base), and true originWidth/originHeight). One quartz product page embeds
the FULL 51-item QuartzSamples collection (every colour, full galleries); each
porcelain page embeds only its own PorcelaineSlabs record but that record's own
"images[]" gallery is complete. kitchenName/range fields exist but are empty on
every record checked -- the site's old /kitchen-samples room-photo collection
(referenced by bloom_harvest.py) 404s site-wide now; there is no live room-photo
source. Filenames carry real hints ("X Full.jpg" / "X Close up N.JPG") so kind
classification does not need aspect-ratio guessing.

--report: prints the match/selection table, writes nothing.
--apply:  downloads winning images (skips ones already on disk), converts to
webp, writes slabs.json via harvest_lib.patch_library(supplier="Bloomstones").
"""
import csv
import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest_lib as hl

Image.MAX_IMAGE_PIXELS = None

CACHE = os.path.join(hl.CACHE_ROOT, "bloomstones2")
DEST_QUARTZ = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "Bloomstone quartz")
DEST_PORC = os.path.join(hl.BRANDS_ROOT, "3. CERAMIC- PORCELAIN", "Bloomstone")
DOMAIN = "https://www.bloomstoneslondon.com"

apply_mode = "--apply" in sys.argv


# ------------------------------------------------------------ CMS JSON pull --
def get_collection(text, collection_id):
    ri = text.find('"recordsByCollectionId"')
    if ri < 0:
        return {}
    j = text.find(f'"{collection_id}":{{', ri)
    if j < 0:
        return {}
    start = text.find('{', j + len(f'"{collection_id}":'))
    depth, k, n = 0, start, len(text)
    while k < n:
        c = text[k]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                break
        k += 1
    try:
        return json.loads(text[start:k + 1])
    except Exception:
        return {}


_SRC_RE = re.compile(r'wix:image://v1/([^/]+)/([^#]*)#originWidth=(\d+)&originHeight=(\d+)')


def gallery_items(record, key):
    """The 'slug' field sometimes lacks its file extension and 'settings'
    width/height is sometimes empty ({}); the 'src' field's own URL always
    carries both the extension-bearing media id AND originWidth/originHeight
    in its query fragment, so parse that as the primary source."""
    import urllib.parse
    out = []
    for it in record.get(key) or []:
        slug, w, h, fn_part = None, 0, 0, ""
        m = _SRC_RE.search(it.get("src") or "")
        if m:
            slug, fn_part, w, h = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
        if not slug:
            slug = it.get("slug")
        if not slug:
            continue
        if not re.search(r'\.(jpe?g|png|webp)$', slug, re.I):
            # bare hash with no extension -- default to jpg (the site's norm)
            slug = slug + ".jpg"
        if not w:
            w = (it.get("settings") or {}).get("width") or 0
            h = (it.get("settings") or {}).get("height") or 0
        name = it.get("title") or it.get("fileName") or urllib.parse.unquote(fn_part) or ""
        out.append({"slug": slug, "name": name, "w": w, "h": h})
    return out


def load_quartz_records():
    """Merge QuartzSamples records across every cached quartz page (any one
    page carries all 51, but merge defensively -- keep the richest gallery
    per title)."""
    best = {}
    for fn in os.listdir(CACHE):
        if not fn.startswith("quartz-samples-") or not fn.endswith(".html"):
            continue
        text = open(os.path.join(CACHE, fn), encoding="utf-8", errors="replace").read()
        recs = get_collection(text, "QuartzSamples")
        for rid, rec in recs.items():
            title = (rec.get("title") or "").strip()
            if not title:
                continue
            imgs = gallery_items(rec, "mediaPics")
            prev = best.get(title)
            if prev is None or len(imgs) > len(prev["images"]):
                best[title] = {
                    "title": title,
                    "productUrl": DOMAIN + rec.get("link-quartz-samples-title", ""),
                    "images": imgs,
                    "kind": "Quartz",
                }
    return best


def load_porcelain_records():
    out = {}
    for fn in os.listdir(CACHE):
        if not fn.startswith("porcelaine-slabs-") or not fn.endswith(".html"):
            continue
        text = open(os.path.join(CACHE, fn), encoding="utf-8", errors="replace").read()
        recs = get_collection(text, "PorcelaineSlabs")
        for rid, rec in recs.items():
            title = (rec.get("title") or "").strip()
            if not title:
                continue
            imgs = gallery_items(rec, "images")
            if not imgs:
                # fall back to the single 'range' field if the gallery is empty
                rng = rec.get("range") or ""
                m = re.search(r'v1/([^/]+)/([^#]+)#originWidth=(\d+)&originHeight=(\d+)', rng)
                if m:
                    imgs = [{"slug": m.group(1), "name": m.group(2), "w": int(m.group(3)), "h": int(m.group(4))}]
            prev = out.get(title)
            if prev is None or len(imgs) > len(prev["images"]):
                out[title] = {
                    "title": title,
                    "productUrl": DOMAIN + rec.get("link-porcelaine-slabs-title", ""),
                    "images": imgs,
                    "kind": "Porcelain",
                }
    return out


# --------------------------------------------------------------- classify --
_CLOSE = re.compile(r'close[\s_-]?up|closeup|detail|texture|zoom', re.I)
_SLAB = re.compile(r'\bfull\b|\bslab\b', re.I)
_ROOM = re.compile(r'kitchen|bathroom|\broom\b|install|vanity|lifestyle|project', re.I)


def classify(item):
    hay = item["name"] or ""
    if _ROOM.search(hay):
        return "room"
    if _CLOSE.search(hay):
        return "closeup"
    if _SLAB.search(hay):
        return "slab"
    w, h = item["w"], item["h"]
    if w and h:
        ar = w / h if h else 0
        ar_n = max(ar, 1 / ar) if ar else 0
        if 1.6 <= ar_n <= 2.4:
            return "slab"
        if 0.8 <= ar_n <= 1.3:
            return "closeup"
    return "slab" if not hay else None  # unnamed -> usually still the hero photo


def pick(images):
    """-> (main_or_None, [closeups up to 4], [rooms up to 6])."""
    slabs, closeups, rooms = [], [], []
    for it in images:
        k = classify(it)
        if k == "slab":
            slabs.append(it)
        elif k == "closeup":
            closeups.append(it)
        elif k == "room":
            rooms.append(it)
    slabs.sort(key=lambda x: -x["w"])
    closeups.sort(key=lambda x: -x["w"])
    rooms.sort(key=lambda x: -x["w"])
    return (slabs[0] if slabs else None), closeups[:4], rooms[:6]


# ------------------------------------------------------------- name match --
_DROP = {"", "the", "quartz", "porcelain", "leathered", "honed", "printed", "polished",
         "matt", "soft", "and", "full", "vein", "fullvein3d", "fullbody3d", "natural",
         "select2", "3d", "mm", "12mm", "20mm", "30mm"}
_QUIRK = {"calcutta": "calacatta", "calacutta": "calacatta", "gray": "grey"}


def toks(s):
    out = set()
    for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split():
        w = re.sub(r'^\d+mm$', '', w)
        if w in _DROP:
            continue
        out.add(_QUIRK.get(w, w))
    out.discard("")
    return out


def fuzzy_sub(a, b):
    import difflib
    for t in a:
        if t not in b and not difflib.get_close_matches(t, list(b), n=1, cutoff=0.82):
            return False
    return True


def best_match(site_name, pool):
    import difflib
    st = toks(site_name)
    top, score = None, (0, 0.0)
    if not st:
        return None
    for name, obj in pool:
        ct = toks(name)
        if ct and fuzzy_sub(ct, st):
            r = difflib.SequenceMatcher(None, site_name.lower(), str(name).lower()).ratio()
            if (len(ct), r) > score:
                top, score = obj, (len(ct), r)
    return top


# --------------------------------------------------------------- pricebook --
def load_pb():
    rows = list(csv.DictReader(open(hl.PRICEBOOK_CSV, encoding="utf-8-sig")))
    out = {"Quartz": {}, "Porcelain": {}}
    for r in rows:
        if r.get("Supplier") != "Bloomstones" or r.get("Material") not in ("Quartz", "Porcelain"):
            continue
        colour = r["Colour"].strip()
        mat = r["Material"]
        e = out[mat].setdefault(colour, {"thicknesses": set(), "finishes": set(), "sizes": {}})
        try:
            t = int(float(r["Thickness (mm)"]))
            e["thicknesses"].add(t)
        except Exception:
            t = None
        if r.get("Finish"):
            e["finishes"].add(r["Finish"])
        try:
            L = int(float(r["Slab Length (mm)"]))
            W = int(float(r["Slab Width (mm)"]))
            if t is not None:
                e["sizes"][t] = f"{L}x{W}"
        except Exception:
            pass
    return out


# -------------------------------------------------------------- download --
def download_and_save(slug, dest_root, colour_folder, out_id, is_main, main_target_ar=None):
    url = "https://static.wixstatic.com/media/" + slug
    data, used_url = hl.fetch_best(url, supplier="bloomstones2", cache_key="img-" + slug)
    folder = os.path.join(dest_root, re.sub(r'[<>:"/\\|?*]', "", colour_folder).strip())
    os.makedirs(folder, exist_ok=True)
    orig_path = os.path.join(folder, re.sub(r'[<>:"/\\|?*]', "_", slug))
    if not os.path.exists(orig_path) or os.path.getsize(orig_path) == 0:
        open(orig_path, "wb").write(data)
    im = Image.open(orig_path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    scale = None
    if is_main and main_target_ar:
        ar = im.width / im.height
        if ar < 1 and abs((1 / ar) - main_target_ar) / main_target_ar < 0.05:
            im = im.transpose(Image.Transpose.ROTATE_90)
            ar = im.width / im.height
        if abs(ar - main_target_ar) / main_target_ar < 0.05:
            im = im.resize((1600, round(1600 / main_target_ar)), Image.LANCZOS)
            scale = "true"
        else:
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            scale = "approx"
    else:
        if im.width > 1600:
            im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    fn = out_id if out_id.lower().endswith(".webp") else out_id + ".webp"
    im.save(os.path.join(hl.IMAGES_DIR, fn), "WEBP", quality=87)
    return fn, url, scale


def main():
    quartz_recs = load_quartz_records()
    porc_recs = load_porcelain_records()
    print(f"Loaded {len(quartz_recs)} quartz CMS records, {len(porc_recs)} porcelain CMS records", flush=True)

    lib = hl.load_library()
    q_entries = [r for r in lib["slabs"] if r.get("supplier") == "Bloomstones" and r.get("material") == "Quartz"]
    p_entries = [r for r in lib["slabs"] if r.get("supplier") == "Bloomstones" and r.get("material") == "Porcelain"]
    pb = load_pb()

    rows = []
    to_apply = []  # (entry_or_None, material, site_rec, main_item, closeups, is_new_entry, pbc)

    for mat, recs, entries, pb_pool_mat, dest_root, tgt_ar in (
            ("Quartz", quartz_recs, q_entries, pb["Quartz"], DEST_QUARTZ, 3230 / 1630),
            ("Porcelain", porc_recs, p_entries, pb["Porcelain"], DEST_PORC, 3200 / 1600)):
        lib_pool = [(r["colour"], r) for r in entries]
        pb_pool = [(k, k) for k in pb_pool_mat]
        for title, rec in sorted(recs.items()):
            entry = best_match(title, lib_pool)
            pbc = best_match(title, pb_pool)
            main_item, closeups, rooms = pick(rec["images"])
            status = "match" if entry else ("NEW(pb)" if pbc else "UNMATCHED")
            rows.append((mat, title, status, entry["colour"] if entry else "-", pbc or "-",
                         f"{main_item['name'] or '(unnamed)'} {main_item['w']}x{main_item['h']}" if main_item else "NO IMAGE",
                         len(closeups)))
            if status == "UNMATCHED":
                continue
            to_apply.append((entry["id"] if entry else None, rec["title"].strip(), mat, rec, main_item,
                             closeups, pbc, pb_pool_mat, dest_root, tgt_ar))

    w = [max((len(str(r[i])) for r in rows), default=8) for i in range(7)]
    for r in rows:
        print(f"{r[0]:<{w[0]}} | {r[1]:<{w[1]}} | {r[2]:<{w[2]}} | {r[3]:<{w[3]}} | {r[4]:<{w[4]}} | {r[5]:<{w[5]}} | closeups={r[6]}")

    site_titles_all = {t for t, _ in quartz_recs.items()} | {t for t, _ in porc_recs.items()}
    unmatched_site = [r for r in rows if r[2] == "UNMATCHED"]
    print(f"\n{len(rows)} site colours total | {sum(1 for r in rows if r[2]=='match')} matched | "
          f"{sum(1 for r in rows if r[2]=='NEW(pb)')} new-from-pricebook | {len(unmatched_site)} unmatched")

    if not apply_mode:
        # also report library entries the site does NOT confirm (still missing)
        all_lib_colours_matched = {r[0]["id"] for r in [t for t in []]}  # placeholder, computed below in apply too
        return

    mains_changed = []
    galleries_added = []
    new_entries = 0
    matched_ids = set()

    def apply(lib):
        nonlocal mains_changed, galleries_added, new_entries
        by_id = {s["id"]: s for s in lib["slabs"]}
        for entry_id, colour_title, mat, rec, main_item, closeups, pbc, pb_pool_mat, dest_root, tgt_ar in to_apply:
            entry = by_id.get(entry_id) if entry_id else None
            if entry is None:
                colour = colour_title
                eid = entry_id or ("bloomstones--" + re.sub(r"[^a-z0-9]+", "-", colour.lower()).strip("-"))
                if eid in by_id:
                    entry = by_id[eid]
                else:
                    sizes = pb_pool_mat.get(pbc, {}) if pbc else {}
                    entry = {"id": eid, "supplier": "Bloomstones", "colour": colour, "material": mat,
                              "naturalStone": False, "illustrationOnly": False,
                              "thicknesses": sorted(sizes.get("thicknesses", [])) or ([20, 30] if mat == "Quartz" else [12, 20]),
                              "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""}}
                    lib["slabs"].append(entry)
                    by_id[eid] = entry
                    new_entries += 1
            matched_ids.add(entry["id"])
            colour_folder = entry["colour"]

            if not entry.get("productUrl"):
                entry["productUrl"] = rec["productUrl"]
            pbinfo = pb_pool_mat.get(pbc) if pbc else None
            if pbinfo and not entry.get("slabSizes"):
                entry["slabSizes"] = hl.format_slab_sizes(pbinfo["sizes"]) if pbinfo["sizes"] else ""
                if pbinfo["thicknesses"]:
                    entry["thicknesses"] = sorted(pbinfo["thicknesses"])
            if not entry.get("details"):
                fins = sorted(pbinfo["finishes"]) if pbinfo else []
                entry["details"] = "Bloomstones · " + mat + (" · " + "/".join(fins) if fins else "")

            main_is_missing = entry.get("image", {}).get("status") == "missing"
            images_arr = entry.get("images") or []
            existing_slugs = {im.get("source", "").rsplit("/", 1)[-1] for im in images_arr}
            if entry.get("image", {}).get("source"):
                existing_slugs.add(entry["image"]["source"].rsplit("/", 1)[-1])

            new_images_arr = []
            if main_is_missing and main_item:
                fn, src, scale = download_and_save(main_item["slug"], dest_root, colour_folder,
                                                     entry["id"], True, tgt_ar)
                entry["image"] = {"file": fn, "status": "slab", "source": src, "borrowedFrom": ""}
                if scale:
                    entry["image"]["scale"] = scale
                mains_changed.append(entry["id"])
                new_images_arr.append({"file": fn, "status": "slab", "kind": "slab", "source": src, "borrowedFrom": ""})
            elif entry.get("image", {}).get("file"):
                new_images_arr.append(dict(entry["image"], kind="slab"))

            added_any_gallery = False
            for i, cu in enumerate(closeups, 1):
                if cu["slug"] in existing_slugs:
                    continue
                out_id = f"{entry['id']}--closeup{i}"
                fn, src, _ = download_and_save(cu["slug"], dest_root, colour_folder, out_id, False)
                new_images_arr.append({"file": fn, "status": "closeup", "kind": "closeup", "source": src, "borrowedFrom": ""})
                added_any_gallery = True
            if added_any_gallery:
                galleries_added.append(entry["id"])

            if len(new_images_arr) > 1 or (new_images_arr and not entry.get("images")):
                entry["images"] = new_images_arr

        return {"mains": len(mains_changed), "galleries": len(galleries_added), "new": new_entries}

    result = hl.patch_library(apply, supplier="Bloomstones")
    print("\nAPPLIED:", result)
    print("Mains filled:", mains_changed)
    print("Galleries added to:", galleries_added)

    still_missing = sorted(r["colour"] for r in (q_entries + p_entries)
                            if r.get("image", {}).get("status") == "missing" and r["id"] not in matched_ids)
    print(f"\nStill missing ({len(still_missing)}):", still_missing)


if __name__ == "__main__":
    main()
