"""Reconcile tools/nilestone-harvest.json with slab-library (supplier "Nile Stone") +
the price book. --report prints the match table and changes nothing; --apply downloads
originals, writes webps, then applies field changes to slabs.json in ONE short
harvest_lib.patch_library() call (concurrency rule: all downloads/classification happen
first against a read-only snapshot, recorded into an `updates` dict keyed by entry id;
only the final patch_library callback touches the live/fresh-reloaded slabs.json).

Two lines under one supplier (HARVEST-SPEC Decisions, 2026-08-24 evening):
  - Quartz (41): own-brand "Nile Quartz Surfaces", one shared productUrl (SPA, no
    per-colour URL). Site images carry almost no filename/alt hints (only "KITCHEN"/
    "RENDER"), so classification here leans on aspect ratio (downloaded, checked via
    PIL) more than HARVEST-SPEC's usual filename-first rule -- see classify_quartz().
  - Porcelain (11): Marazzi "The Top" rebrand. harvest_nilestone.py already hand-resolved
    each colour to an exact marazzitile.co.uk product code (cross-checked against the
    price book), so every image in the manifest already carries a trustworthy "slab"/
    "room" hint -- trusted directly here, just aspect-sanity-checked before use as a main.

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": leave the main alone, still fill
    productUrl/slabSizes/details/gallery.
  - status "missing": if a slab image is found, download it and set status "slab".
  - Never a room/closeup shot as main -- aspect + filename verified.
"""
import json
import os
import re
import sys

from PIL import Image

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Nile Stone"
QUARTZ_DEST = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "Nile stone")
PORCELAIN_DEST = os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED", "NILE STONE (Marazzi)")

CLOSEUP_CAP = 4
ROOM_CAP = 6
RAW_CAP = 12  # per-colour cap on how many raw quartz image candidates we even download

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "nilestone-harvest.json"), encoding="utf-8"))
snapshot = hl.load_library()  # READ-ONLY snapshot for matching/classification only
all_entries = [s for s in snapshot["slabs"] if s.get("supplier") == SUPPLIER
               and not s.get("naturalStone") and s.get("material") in ("Quartz", "Porcelain")]
quartz_entries = [e for e in all_entries if e["material"] == "Quartz"]
porc_entries = [e for e in all_entries if e["material"] == "Porcelain"]
q_pool = [(e["colour"], e) for e in quartz_entries]
p_pool = [(e["colour"], e) for e in porc_entries]

pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_mains_new = n_mains_kept = n_closeups = n_rooms = 0
unmatched_site_quartz = []
updates = {}  # entry id -> dict of field overrides to apply in the final patch_library call


def dims(path):
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (None, None)


def aspect_ratio_n(w, h):
    if not w or not h:
        return None
    ar = w / h
    return max(ar, 1 / ar)


def classify_quartz(fn, w, h):
    """filename hint first (KITCHEN/RENDER -> room, both plausible kitchen-visualisation
    terms on this site since no other room keyword is ever used), then aspect."""
    if re.search(r'kitchen|render', fn, re.I):
        return "room"
    ar = aspect_ratio_n(w, h)
    if ar is None:
        return None
    if 1.6 <= ar <= 2.6:
        return "slab"
    if 0.8 <= ar <= 1.35:
        return "closeup"
    return "room"


def dl_and_classify_quartz(site_colour, images):
    """Downloads up to RAW_CAP candidates, classifies each, returns
    (slab_candidates, closeup_candidates, room_candidates) each a list of
    (path, width, height, filename, url) sorted largest-first."""
    slabs, closeups, rooms = [], [], []
    for im in images[:RAW_CAP]:
        fn = im["filename"]
        try:
            data, used_url = hl.fetch_best(im["url"], supplier="nile-stone",
                                            cache_key=f"q-{site_colour}-{fn}"[:150])
        except Exception as e:
            print(f"  DOWNLOAD FAIL {site_colour} <- {im['url']}: {e}")
            continue
        tmp_path = os.path.join(hl.CACHE_ROOT, "nile-stone", "_tmp_" + re.sub(r'[^A-Za-z0-9._-]', '_', fn))
        with open(tmp_path, "wb") as f:
            f.write(data)
        w, h = dims(tmp_path)
        kind = im.get("hint") or classify_quartz(fn, w, h)
        entry = (tmp_path, w, h, fn, im["url"])
        if kind == "slab":
            slabs.append(entry)
        elif kind == "closeup":
            closeups.append(entry)
        elif kind == "room":
            rooms.append(entry)
    slabs.sort(key=lambda e: (e[1] or 0) * (e[2] or 0), reverse=True)
    closeups.sort(key=lambda e: (e[1] or 0) * (e[2] or 0), reverse=True)
    rooms.sort(key=lambda e: (e[1] or 0) * (e[2] or 0), reverse=True)
    return slabs, closeups, rooms


def persist(tmp_path, dest_root, colour, fn):
    data = open(tmp_path, "rb").read()
    return hl.save_original(data, dest_root, colour, fn)


def process_quartz():
    global n_mains_new, n_mains_kept, n_closeups, n_rooms
    site_items = [x for x in manifest if x["material"] == "Quartz"]
    matched_ids = set()
    for site in site_items:
        entry, score = hl.match_colour(site["site_colour"], q_pool)
        if not entry:
            unmatched_site_quartz.append(site["site_colour"])
            continue
        matched_ids.add(entry["id"])
        colour = entry["colour"]
        cur_status = entry["image"]["status"]
        need_main = cur_status != "slab"

        upd = {"productUrl": site["productUrl"], "details": "Nile Quartz Surfaces"}
        pbinfo = pb.get(colour, {})
        if pbinfo.get("sizes"):
            upd["slabSizes"] = hl.format_slab_sizes(pbinfo["sizes"])

        rows_out.append((colour, "match(quartz)", cur_status, f"{len(site['images'])} candidates"))
        if not apply_mode:
            updates[entry["id"]] = upd
            continue

        slabs, closeups, rooms = dl_and_classify_quartz(colour, site["images"])

        gallery = []
        if need_main:
            if slabs:
                p, w, h, fn, url = slabs[0]
                orig = persist(p, QUARTZ_DEST, colour, fn)
                webp = hl.to_library_webp(orig, entry["id"])
                upd["image"] = {"file": webp, "status": "slab", "source": site["productUrl"], "borrowedFrom": ""}
                mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, webp), "NEW"))
                n_mains_new += 1
                gallery.append(dict(upd["image"], kind="slab"))
            else:
                mains_sheet.append((colour, None, "NO SLAB FOUND"))
        else:
            if entry["image"].get("file"):
                mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
                n_mains_kept += 1
            gallery.append(dict(entry["image"], kind="slab"))

        ci = 0
        for p, w, h, fn, url in closeups[:CLOSEUP_CAP]:
            ci += 1
            orig = persist(p, QUARTZ_DEST, colour, fn)
            webp = hl.to_library_webp(orig, f"{entry['id']}--closeup{ci}")
            gallery.append({"file": webp, "status": "closeup", "kind": "closeup",
                             "source": site["productUrl"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, webp)))
            n_closeups += 1
        ri = 0
        for p, w, h, fn, url in rooms[:ROOM_CAP]:
            ri += 1
            orig = persist(p, QUARTZ_DEST, colour, fn)
            webp = hl.to_library_webp(orig, f"{entry['id']}--room{ri}")
            gallery.append({"file": webp, "status": "representative", "kind": "room",
                             "source": site["productUrl"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, webp)))
            n_rooms += 1
        if len(gallery) > 1:
            upd["images"] = gallery
        updates[entry["id"]] = upd
    return matched_ids


def process_porcelain():
    global n_mains_new, n_mains_kept, n_closeups, n_rooms
    site_items = [x for x in manifest if x["material"] == "Porcelain"]
    matched_ids = set()
    for site in site_items:
        entry, score = hl.match_colour(site["site_colour"], p_pool)
        if not entry:
            rows_out.append((site["site_colour"], "UNMATCHED(porcelain)", "-", "-"))
            continue
        matched_ids.add(entry["id"])
        colour = entry["colour"]
        cur_status = entry["image"]["status"]
        need_main = cur_status != "slab"

        upd = {"productUrl": site["productUrl"], "details": f"Marazzi The Top · {site['range_label']}"}
        pbinfo = pb.get(colour, {})
        if pbinfo.get("sizes"):
            upd["slabSizes"] = hl.format_slab_sizes(pbinfo["sizes"])

        rows_out.append((colour, "match(porcelain)", cur_status, f"{len(site['images'])} candidates"))
        if not apply_mode:
            updates[entry["id"]] = upd
            continue

        slab_imgs = [im for im in site["images"] if im["hint"] == "slab"]
        room_imgs = [im for im in site["images"] if im["hint"] == "room"]

        gallery = []
        new_main_image = None
        if need_main and slab_imgs:
            im = slab_imgs[0]
            cache_supplier = "marazzitile" if "marazzitile" in im["url"] else "nile-stone"
            try:
                data, used_url = hl.fetch_best(im["url"], supplier=cache_supplier,
                                                cache_key=f"p-{colour}-{im['filename']}"[:150])
            except Exception as e:
                print(f"  DOWNLOAD FAIL {colour} <- {im['url']}: {e}")
                data = None
            if data:
                tmp_path = os.path.join(hl.CACHE_ROOT, cache_supplier, "_tmp_" + re.sub(r'[^A-Za-z0-9._-]', '_', im["filename"]))
                open(tmp_path, "wb").write(data)
                w, h = dims(tmp_path)
                ar = aspect_ratio_n(w, h)
                if ar is not None and ar > 3.2:
                    mains_sheet.append((colour, None, f"REJECTED aspect {w}x{h}"))
                else:
                    orig = persist(tmp_path, PORCELAIN_DEST, colour, im["filename"])
                    webp = hl.to_library_webp(orig, entry["id"])
                    new_main_image = {"file": webp, "status": "slab", "source": site["productUrl"], "borrowedFrom": ""}
                    upd["image"] = new_main_image
                    mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, webp), "NEW"))
                    n_mains_new += 1
                    gallery.append(dict(new_main_image, kind="slab"))
            else:
                mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
        elif not need_main:
            if entry["image"].get("file"):
                mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
                n_mains_kept += 1
            gallery.append(dict(entry["image"], kind="slab"))
        else:
            mains_sheet.append((colour, None, "NO SLAB FOUND"))

        ri = 0
        for im in room_imgs[:ROOM_CAP]:
            try:
                data, used_url = hl.fetch_best(im["url"], supplier="marazzitile",
                                                cache_key=f"proom-{colour}-{im['filename']}"[:150])
            except Exception as e:
                print(f"  DOWNLOAD FAIL {colour} room <- {im['url']}: {e}")
                continue
            tmp_path = os.path.join(hl.CACHE_ROOT, "marazzitile", "_tmp_" + re.sub(r'[^A-Za-z0-9._-]', '_', im["filename"]))
            open(tmp_path, "wb").write(data)
            ri += 1
            orig = persist(tmp_path, PORCELAIN_DEST, colour, im["filename"])
            webp = hl.to_library_webp(orig, f"{entry['id']}--room{ri}")
            gallery.append({"file": webp, "status": "representative", "kind": "room",
                             "source": site["productUrl"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, webp)))
            n_rooms += 1
        if len(gallery) > 1:
            upd["images"] = gallery
        updates[entry["id"]] = upd
    return matched_ids


matched_q = process_quartz()
matched_p = process_porcelain()

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

unmatched_lib_q = sorted(e["colour"] for e in quartz_entries if e["id"] not in matched_q)
unmatched_lib_p = sorted(e["colour"] for e in porc_entries if e["id"] not in matched_p)
print()
print(f"quartz matched: {len(matched_q)}/41 | porcelain matched: {len(matched_p)}/11")
print(f"unmatched site quartz colours (no lib/pb match): {unmatched_site_quartz}")
print(f"unmatched library quartz colours (no site match): {unmatched_lib_q}")
print(f"unmatched library porcelain colours (no site match): {unmatched_lib_p}")

if apply_mode:
    def apply(lib_fresh):
        n = 0
        by_id = {s["id"]: s for s in lib_fresh["slabs"]}
        for eid, upd in updates.items():
            s = by_id.get(eid)
            if s is None:
                continue
            s.update(upd)
            n += 1
        return {"patched": n}

    result = hl.patch_library(apply, supplier=SUPPLIER)
    print(f"\nAPPLIED. entries patched: {result['patched']} | mains new: {n_mains_new} | "
          f"mains kept: {n_mains_kept} | closeups: {n_closeups} | rooms: {n_rooms}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "nilestone-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "nilestone-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = [c for c, p, s in mains_sheet if s in ("NO SLAB FOUND", "DOWNLOAD FAILED") or "REJECTED" in s]
    report_path = os.path.join(hl.REPORTS_DIR, "nilestone-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Nile Stone harvest report

Two lines under one supplier: Quartz (41, own-brand "Nile Quartz Surfaces",
nilestone.co.uk Angular SPA -- catalogue scraped from the compiled main.js bundle's
JS object literal, images served plain from /assets/quartz-surfaces/); Porcelain (11,
Marazzi "The Top" rebrand -- Nile Trading UK Ltd is Marazzi's sole UK distributor,
primary source marazzitile.co.uk's Grande collection pages, nilestone.co.uk/top-marazzi
as fallback for 2 colours (Capraia, Limestone Sand) absent from marazzitile.co.uk).

## Counts
- Engineered Nile Stone colours in scope: 52 (41 Quartz + 11 Porcelain)
- Quartz matched to site catalogue: {len(matched_q)}/41
- Porcelain matched to site catalogue: {len(matched_p)}/11
- Mains newly set (was missing): {n_mains_new}
- Mains kept (already status=slab, untouched): {n_mains_kept}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Still missing a main after this pass: {still_missing}
- Unmatched site quartz colours (site has, library/price book doesn't): {unmatched_site_quartz}
- Unmatched library colours (no site match this pass): {unmatched_lib_q + unmatched_lib_p}

## Assumptions / notes
- `productUrl`: quartz -> shared https://www.nilestone.co.uk/quartz-surfaces (SPA modal
  catalogue, no per-colour URL exists); porcelain -> the specific marazzitile.co.uk
  collection page the colour's product-detail block was found on (Capraia/Limestone Sand
  -> nilestone.co.uk/top-marazzi, the only source that carries them).
- `slabSizes` comes from the price book (naming/size authority per HARVEST-SPEC), not the
  site (Marazzi's Grande collection pages print 6mm/12mm TILE-range SKUs, e.g. 160x320cm,
  which are NOT the 3240x1620mm 12/20mm slab format Nile actually stocks -- price book
  wins on size for every colour).
- `details` = "Nile Quartz Surfaces" for quartz; "Marazzi The Top · <range>" for
  porcelain (Marble Look / Stone Look / Solid Color / Concrete Look) per HARVEST-SPEC
  Decisions (brand goes in details, supplier stays "Nile Stone").
- Porcelain "Black" resolves via price-book SKU code MNH9, which on marazzitile.co.uk sits
  under its "Concrete Look" range (not "Solid Color"/"Marble Look") -- confirmed by exact
  code match, a better/primary-source photo than the nilestone.co.uk fallback the
  discovery pass had flagged as the only option.
- Existing `image.status == "slab"` mains were left untouched even where the site had a
  same-or-different crop -- only "missing" mains were (re)set, per rule.
- Quartz images carry almost no filename hints (only "KITCHEN"/"RENDER" ever appear) --
  classification leans on aspect ratio (downloaded + PIL-measured) more than the usual
  filename-first rule; "RENDER" filenames are treated as room shots (kitchen-visualisation
  renders), consistent with what was actually downloaded.
- Originals: quartz -> `1. QUARTZ\\Nile stone\\<Colour>\\` (existing folder, reused);
  porcelain -> new `3. PORCELAIN & SINTERED\\NILE STONE (Marazzi)\\<Colour>\\`.
- Applied via harvest_lib.patch_library (concurrency-safe): all downloads/conversions ran
  against a read-only snapshot first; the live slabs.json was only touched once, at the
  end, re-loaded fresh inside the lock.

## Re-run
```
python tools/harvest_nilestone.py             # re-parse cached bundle/pages (delete tools/_cache/nile-stone or /marazzitile to force re-fetch)
python tools/reconcile_nilestone.py --report   # dry run, prints the match table
python tools/reconcile_nilestone.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
