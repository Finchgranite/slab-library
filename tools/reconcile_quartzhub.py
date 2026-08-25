"""Reconcile tools/quartzhub-harvest.json with slab-library (supplier
"Quartz Hub", all 15 entries engineered -- no naturalStone rows for this
supplier). --report prints the match table and changes nothing; --apply
downloads originals, writes webps, updates slabs.json via hl.patch_library
(bumps `generated`), writes the two contact sheets + REPORT.md.

Rules for THIS supplier (per task brief, narrower than the general
HARVEST-SPEC default of "replace every main"):
  - 14 of the 15 mains are already good "slab" photos -- DO NOT REPLACE
    THEM. Only productUrl/slabSizes/details/gallery are filled in.
  - Onyx Crema is "closeup-only" -- if the harvest found a real slab-aspect
    photo for it (it did), download it and upgrade status to "slab".
  - productUrl: quartzhub.co.uk has no per-colour pages at all (confirmed
    via sitemap.xml -> only 5 pages exist site-wide); every entry's
    `?s=...` WordPress search-placeholder (or, for Arabescatta Oro, its
    empty productUrl) is replaced with the one real page that shows every
    colour, https://www.quartzhub.co.uk/gallery/.
  - slabSizes/details always come from the price book (material + finish +
    thickness), since the site itself carries no per-colour spec text
    (checked gallery/home/about-us/our-services/faq -- no size/finish copy
    anywhere, only photos).
"""
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Quartz Hub"
GALLERY_URL = "https://www.quartzhub.co.uk/gallery/"
DEST_QUARTZ = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "Quartz Hub Quartz")
DEST_CERAMIC = os.path.join(hl.BRANDS_ROOT, "3. CERAMIC- PORCELAIN", "Quartz hub Ceramic")

apply_mode = "--apply" in sys.argv

import json
manifest = json.load(open(os.path.join(SCRATCH, "quartzhub-harvest.json"), encoding="utf-8"))
by_colour = manifest["by_colour"]

lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER]

pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_upgraded = n_closeups = n_rooms = n_filled_meta = 0
dl_cache = {}


def dest_root(material):
    return DEST_CERAMIC if material.lower() == "ceramic" else DEST_QUARTZ


def dl(url, colour, material, apply_):
    if not apply_:
        return None
    if url in dl_cache:
        return dl_cache[url]
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="quartzhub", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        dl_cache[url] = None
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    p = hl.save_original(data, dest_root(material), colour, used_fn)
    dl_cache[url] = p
    return p


def build_details(colour):
    row = pb.get(colour)
    if not row:
        return None
    material = next((e["material"] for e in entries if e["colour"] == colour), "")
    finishes = "/".join(sorted(row["finishes"])) or "?"
    thicks = "/".join(f"{t}mm" for t in sorted(row["thicknesses"]))
    return f"Quartz Hub · {material} · {finishes} finish · {thicks}"


for entry in entries:
    colour = entry["colour"]
    material = entry["material"]
    cur_status = entry["image"]["status"]
    site = by_colour.get(colour)

    pb_row = pb.get(colour)
    slab_sizes = hl.format_slab_sizes(pb_row["sizes"]) if pb_row and pb_row["sizes"] else ""
    details = build_details(colour)

    will_upgrade_main = bool(site and site["slab"] and cur_status != "slab")
    n_cu = len(site["closeup"]) if site else 0
    n_rm = len(site["room"]) if site else 0
    rows_out.append((
        colour, material, "site-match" if site else "NO SITE PHOTO",
        f"{cur_status}->slab" if will_upgrade_main else cur_status,
        f"{n_cu}cu/{n_rm}rm", slab_sizes or "-",
    ))

    if not apply_mode:
        continue

    entry["productUrl"] = GALLERY_URL
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    if details:
        entry["details"] = details
    n_filled_meta += 1

    if not site:
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"])
                             if entry["image"].get("file") else None, "kept (no site match)"))
        continue

    # --- main slab image: ONLY Onyx Crema (closeup-only -> slab) ---
    if will_upgrade_main:
        best = max(site["slab"], key=lambda r: r["width"] * r["height"])
        p = dl(best["url"], colour, material, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            entry["image"] = {"file": fn, "status": "slab", "source": GALLERY_URL, "borrowedFrom": ""}
            n_upgraded += 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "UPGRADED"))
        else:
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    else:
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"])
                             if entry["image"].get("file") else None, "kept"))

    # --- gallery: closeups + rooms (existing main always included first) ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    ci = ri = 0
    for rec in site["closeup"][:2]:
        p = dl(rec["url"], colour, material, apply_mode)
        if not p or not os.path.exists(p):
            continue
        ci += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
        gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": GALLERY_URL, "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
        n_closeups += 1
    for rec in site["room"][:2]:
        p = dl(rec["url"], colour, material, apply_mode)
        if not p or not os.path.exists(p):
            continue
        ri += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
        gallery.append({"file": fn, "status": "representative", "kind": "room", "source": GALLERY_URL, "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

unmatched_site = manifest["unmatched_site"]
unmatched_pb = manifest["unmatched_pb"]

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))
print()
print(f"entries: {len(entries)} | site-matched: {sum(1 for r in rows_out if r[2]=='site-match')} | no-site-photo: {sum(1 for r in rows_out if r[2]!='site-match')}")
print(f"unmatched site products (extra Quartz Hub colours we don't stock): {list(unmatched_site.keys())}")
print(f"unmatched price-book/library colours (no site photo found): {unmatched_pb}")

if apply_mode:
    ids_touched = {e["id"]: e for e in entries}

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, edited in ids_touched.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == SUPPLIER:
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains upgraded: {n_upgraded} | closeups: {n_closeups} | rooms: {n_rooms} | meta filled: {n_filled_meta}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "quartzhub-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "quartzhub-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "quartzhub-REPORT.md")
    urls_fixed = sum(1 for e in entries)  # every entry's productUrl was a placeholder or empty
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Quartz Hub harvest report

Source: https://www.quartzhub.co.uk/sitemap.xml -> every sub-sitemap fetched
(home/posts/pages/categories/tags/archives). Confirmed the site has NO
per-colour product pages at all -- sitemap-pages.xml lists exactly 5 pages
(home, /gallery/, /about-us/, /our-services/, /faq/). All colour photography
lives in one Modula lightbox gallery at /gallery/, which is now every entry's
`productUrl` (replacing the 14 `?s=...` WordPress search-query placeholders
and Arabescatta Oro's empty productUrl -- {urls_fixed} URLs fixed in total).

Gallery items expose a clean `data-caption`/`alt` colour name and the true
original `data-full` URL + width/height directly in the HTML (no filename
guessing or HEAD requests needed). Per colour: a landscape "main" photo and
either a perfectly square 2560x2560 crop (10 older colours) or a
`*-swatch-image-*` detail crop (Taj Mahal, Arabescatta Oro, the 4 Ceramic
colours, Onyx Crema) -- both classified "closeup" by `hl.classify_kind`
(square aspect / "swatch" keyword). Onyx Crema alone has a 3rd photo, a
backlit translucency shot (caption "... - Backlit"), classified "room" by a
one-off keyword override (no kitchen/cabinets photo exists on the whole
site, so this is the closest thing to an in-use photo Quartz Hub has for any
colour).

## Counts
- Site colours found (gallery + home/about-us/our-services/faq checked): {len(by_colour)}
- Price-book Quartz Hub colours: {len(pb)}
- Library entries (all engineered, all Quartz Hub): {len(entries)}
- productUrls fixed (placeholder/empty -> real https://www.quartzhub.co.uk/gallery/): {urls_fixed}
- Mains upgraded (closeup-only -> slab): {n_upgraded} -- Onyx Crema only, per task brief (the
  other 14 mains were already good "slab" photos and were deliberately left untouched)
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- slabSizes/details filled from the price book (site has no spec text at all): {n_filled_meta}
- Site colour with real photos but no price-book/library row: {list(unmatched_site.keys())} --
  "Ultra White Shimmer" (2 photos, same 2024/08 batch as Black Marquina etc.) -- an extra Quartz
  Hub quartz colour we evidently don't currently stock; no entry invented for it.
- Price-book/library colour with NO site photo anywhere: {unmatched_pb} -- "Laurent" (Ceramic).
  productUrl/slabSizes/details still filled (real gallery page + price book), but no image
  could be added -- ask Quartz Hub whether Laurent has been discontinued or just never
  photographed for the current site.

## Assumptions
- "DO NOT replace the 14 good mains" (task brief) takes precedence over the general
  HARVEST-SPEC default of always fetching the best available main -- even though every one of
  those 13 non-Onyx-Crema colours also has a landscape site photo, it is deliberately never
  picked up as a "slab" kind here (see harvest_quartzhub.py docstring: those photos are <1.8:1
  aspect and carry no slab-hinting filename/keyword, so `hl.classify_kind` naturally returns
  None for them and they are simply not in the harvest manifest).
- `details` is built purely from the price book (material + finish + thickness) because the
  live site carries zero per-colour spec/blurb text anywhere (gallery/home/about-us/
  our-services/faq all checked) -- only photos.
- Onyx Crema's new main is the gallery's own "1.Onyx-Creame-30mm-and-20mm.jpg", 2387x1204
  (1.98:1) -- a genuine full-slab photo, not a crop.

## Re-run
```
python tools/harvest_quartzhub.py             # re-scrape (cached; delete tools/_cache/quartzhub to force)
python tools/reconcile_quartzhub.py --report   # dry run, prints the match table
python tools/reconcile_quartzhub.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
