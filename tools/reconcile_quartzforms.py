"""Reconcile tools/quartzforms-harvest.json with slab-library (supplier
Quartzforms, all 100 entries engineered quartz -- no naturalStone here).
--report prints the match table and changes nothing; --apply downloads
originals, writes webps, updates slabs.json via hl.patch_library (bumps
`generated`), writes the two contact sheets + REPORT.md.

Matching is trivial (not name-fuzzy): the harvest manifest is keyed by
library entry `id` directly, since harvest_quartzforms.py fetched each
colour's own stored `productUrl`.

Rules (HARVEST-SPEC.md):
  - image.status == "slab" (98/100): main image is NOT replaced. Gallery
    (closeup/room), slabSizes, details, productUrl (already present) get
    filled/refreshed.
  - image.status in ("missing", "closeup-only", "representative"): if the
    page has a `slab` image, download it and upgrade status to "slab".
  - Per-colour take: 1 closeup (`detail`) + up to 2 rooms (`gallery01`,
    `gallery02`) -- see harvest_quartzforms.py docstring for why those three
    suffixes were chosen out of the page's fixed 6-image template.
"""
import os
import json
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Quartzforms"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "QUARTZFORMS")

apply_mode = "--apply" in sys.argv

manifest = {m["id"]: m for m in json.load(open(os.path.join(SCRATCH, "quartzforms-harvest.json"), encoding="utf-8"))}
lib = hl.load_library()
entries = [s for s in lib["slabs"] if s.get("supplier") == "Quartzforms"]
pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_new_main = n_upgraded = n_closeups = n_rooms = n_filled_meta = n_dl_fail = 0


def dl(url, colour, tag):
    if not apply_mode:
        return None
    fn = url.rsplit("/", 1)[-1]
    try:
        data, used_url = hl.fetch_best(url, supplier=SUPPLIER, cache_key=f"img-{colour}-{tag}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} [{tag}] <- {url}: {e}")
        return None
    used_fn = used_url.rsplit("/", 1)[-1].split("?")[0]
    return hl.save_original(data, DEST_ROOT, colour, used_fn)


def build_details(meta, pb_row):
    bits = []
    if meta.get("collection"):
        bits.append(f"{meta['collection']} range")
    if meta.get("finishes"):
        bits.append(f"Finishes: {meta['finishes']}")
    elif pb_row and pb_row["finishes"]:
        bits.append(f"Finishes: {', '.join(sorted(pb_row['finishes']))}")
    if meta.get("texture") and meta["texture"].lower() != "solid colour":
        bits.append(meta["texture"])
    if meta.get("description"):
        bits.append(meta["description"])
    return "; ".join(bits)[:300]


for entry in entries:
    m = manifest.get(entry["id"])
    if not m or m.get("error"):
        rows_out.append((entry["colour"], "FETCH-FAIL", m.get("error") if m else "not in manifest", "-", "-"))
        continue

    imgs = m["images"]
    meta = m["meta"]
    pb_row = pb.get(entry["colour"])
    slab_sizes = hl.format_slab_sizes(pb_row["sizes"]) if pb_row and pb_row["sizes"] else ""
    if not slab_sizes and meta.get("dims"):
        slab_sizes = meta["dims"]

    cur_status = entry["image"]["status"]
    will_set_main = cur_status != "slab" and bool(imgs.get("slab"))
    closeup_src = imgs.get("detail") or imgs.get("gallery04") or imgs.get("gallery03")
    room_srcs = [u for k, u in (("gallery01", imgs.get("gallery01")), ("gallery02", imgs.get("gallery02"))) if u]

    rows_out.append((
        entry["colour"],
        f"{cur_status}->slab" if will_set_main else cur_status,
        "Y" if closeup_src else "N",
        f"{len(room_srcs)}",
        slab_sizes or "-",
    ))

    if not apply_mode:
        continue

    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    details = build_details(meta, pb_row)
    if details:
        entry["details"] = details
    n_filled_meta += 1

    # --- main slab image (only the 2 non-slab entries) ---
    if will_set_main:
        p = dl(imgs["slab"], entry["colour"], "slab")
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            entry["image"] = {"file": fn, "status": "slab", "source": m["url"], "borrowedFrom": ""}
            if was_missing:
                n_new_main += 1
            else:
                n_upgraded += 1
            mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if was_missing else "UPGRADED"))
        else:
            n_dl_fail += 1
            mains_sheet.append((entry["colour"], None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
    else:
        mains_sheet.append((entry["colour"], None, "still missing"))

    # --- gallery: closeup + rooms ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    if closeup_src:
        p = dl(closeup_src, entry["colour"], "closeup1")
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup1")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": m["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{entry['colour']} CU1", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
    for ri, u in enumerate(room_srcs, 1):
        p = dl(u, entry["colour"], f"room{ri}")
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
            gallery.append({"file": fn, "status": "representative", "kind": "room", "source": m["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{entry['colour']} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
            n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(5)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(5)))

fetch_fail = [r[0] for r in rows_out if r[1] == "FETCH-FAIL"]
print()
print(f"entries: {len(entries)} | fetch failures: {len(fetch_fail)} {fetch_fail}")
print(f"mains to upgrade this run: {sum(1 for r in rows_out if '->slab' in r[1])}")
print(f"colours with closeup slot: {sum(1 for r in rows_out if r[2]=='Y')}")
print(f"colours with 0 room slot: {sum(1 for r in rows_out if r[3]=='0')}")

if apply_mode:
    ids_touched = {e["id"]: e for e in entries}

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, edited in ids_touched.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == "Quartzforms":
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly set: {n_new_main} | mains upgraded: {n_upgraded} | closeups: {n_closeups} | rooms: {n_rooms} | download fails: {n_dl_fail}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "quartzforms-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "quartzforms-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = sorted(r["colour"] for r in entries if r["image"]["status"] != "slab")
    no_gallery_site = sorted(r[0] for r in rows_out if r[2] == "N" and r[3] == "0")
    report_path = os.path.join(hl.REPORTS_DIR, "quartzforms-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Quartzforms harvest report (galleries pass)

Source: each of the 100 library entries' own stored `productUrl`
(quartzforms.com), fetched directly -- no sitemap crawl needed, all 100 URLs
were already correct. Every product page uses ONE fixed 6-image template
(verified visually against Absolute White + Planet Halley before writing
the classifier): `_slab` (clean full-slab render) / `_gallery01` +
`_gallery02` (real CGI kitchen scenes, wide) / `_gallery03` + `_gallery04`
(styled countertop vignettes with props) / `_detail` (pure texture crop,
no props). This pass took `_detail` as the one closeup and
`_gallery01`+`_gallery02` as up to two rooms; `_gallery03`/`_gallery04`
were skipped as redundant with `_detail`/rooms to keep the request count
sane. `details` built from the page's Collection name + Finishes +
overview paragraph; `slabSizes` from the price book (authority), page
Dimensions table as fallback.

The OneDrive brands folder (`1. QUARTZ\\QUARTZFORMS\\<Series>\\<Colour>`)
already held a large cache of images from an earlier, unfinished pass --
checked first, but NOT used directly: filenames there are inconsistent
(own showroom photos, an AI-mockup or two, legacy site-template exports)
and not reliably auto-classifiable, whereas fetching each colour's own
current page guarantees an accurate, consistent kind label. New downloads
this run go into flat `QUARTZFORMS\\<price-book colour name>\\` folders
per HARVEST-SPEC (existing `<Series>\\<Colour>` folders untouched, not
reorganised).

## Counts
- Library Quartzforms entries: {len(entries)}
- Page fetch failures: {len(fetch_fail)} {fetch_fail}
- Mains newly set (was missing): {n_new_main}
- Mains upgraded (was representative/closeup-only): {n_upgraded}
- Main downloads that failed: {n_dl_fail}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Colours with 0 gallery images added (no closeup AND no room slot found): {len(no_gallery_site)} {no_gallery_site}
- Still not status=slab after this run: {still_missing}

## Assumptions
- `_gallery01`/`_gallery02` = room, `_gallery03`/`_gallery04`/`_detail` =
  closeup: derived from actually viewing the downloaded images for 2
  colours (Absolute White, Planet Halley), not guessed from filenames.
  Solid-colour/plain products (e.g. Absolute White) still get 2 room shots
  (generic CGI kitchen renders) even though there's little colour-specific
  content to see in them -- kept anyway since they ARE the site's own
  "room" gallery images for that product.
- Price book remains the sizing authority; site `Dimensions` text used only
  when a colour has no price-book size (shouldn't happen -- all 100
  Quartzforms price-book colours matched 1:1 to library entries).
- Existing 98 "slab" mains were left untouched, only metadata added.

## Re-run
```
python tools/harvest_quartzforms.py             # re-scrape (cached; delete tools/_cache/quartzforms to force)
python tools/reconcile_quartzforms.py --report   # dry run, prints the match table
python tools/reconcile_quartzforms.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
