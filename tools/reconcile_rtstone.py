"""Reconcile tools/rtstone-harvest.json with slab-library (supplier "RT Stone",
all 44 entries engineered quartz -- no naturalStone rows for this supplier).
--report prints the match table and changes nothing; --apply downloads
originals, writes webps, updates slabs.json via hl.patch_library (bumps
`generated`), writes the two contact sheets + REPORT.md.

Matching is a direct 1:1 join on `colour` -- every RT Stone price-book colour
already has exactly one library entry with that exact colour string (checked
before writing this script), so no fuzzy/finish-variant matching is needed
here (unlike Fugen).

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": NEVER replace the main (per the task's
    explicit "37 slab mains -- DON'T replace"); still refresh
    productUrl/slabSizes/details and fill in closeup/room gallery images.
  - status "missing" or "closeup-only": if the site has a slab image,
    download it and upgrade status to "slab".
  - White Shimmer Supreme: the site's own gallery for this colour has ONLY a
    closeup-labelled image, no slab face at all (confirmed -- see
    harvest_rtstone.py docstring) -- upgrade missing -> closeup-only using
    that image (matches how Calacatta Auric was already stored before this
    run), not invented as a slab.
  - Eternal Calacatta: no site page found at all (see harvest_rtstone.py) --
    stays `missing`; productUrl set to the generic /products listing page
    (the HARVEST-SPEC fallback for "no per-colour page"); slabSizes still
    filled from the price book (always available).
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "RT Stone"
LISTING_URL = "https://www.quartzbyrtstone.co.uk/products"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "RT STONE")

apply_mode = "--apply" in sys.argv

data = json.load(open(os.path.join(SCRATCH, "rtstone-harvest.json"), encoding="utf-8"))
manifest_by_colour = {m["colour"]: m for m in data["manifest"] if not m.get("error")}

lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER]

pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_new_main = n_upgraded_slab = n_closeup_only_from_missing = 0
n_closeups = n_rooms = n_ambiguous_skipped = 0
dl_cache = {}


def dl(url, colour):
    if not apply_mode:
        return None
    if url in dl_cache:
        return dl_cache[url]
    fn = url.split("/")[-1].split("?")[0]
    try:
        data_, used_url = hl.fetch_best(url, supplier="rtstone", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        dl_cache[url] = None
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    p = hl.save_original(data_, DEST_ROOT, colour, used_fn)
    dl_cache[url] = p
    return p


for entry in entries:
    colour = entry["colour"]
    cur_status = entry["image"]["status"]
    m = manifest_by_colour.get(colour)

    if m is None:
        # Eternal Calacatta: no site page.
        rows_out.append((colour, "NO SITE PAGE", cur_status, "-", "-"))
        if apply_mode:
            if not entry.get("productUrl"):
                entry["productUrl"] = LISTING_URL
            pb_row = pb.get(colour)
            if pb_row and pb_row["sizes"]:
                entry["slabSizes"] = hl.format_slab_sizes(pb_row["sizes"])
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"])
                             if entry["image"].get("file") else None,
                             "kept" if entry["image"].get("file") else "still missing"))
        continue

    imgs = m["images"]  # [[url, kind], ...]
    ambiguous = [u for u, k in imgs if k is None]
    n_ambiguous_skipped += len(ambiguous)
    slab_url = next((u for u, k in imgs if k == "slab"), None)
    closeup_urls = [u for u, k in imgs if k == "closeup"]
    room_urls = [u for u, k in imgs if k == "room"]

    will_set_slab_main = bool(slab_url and cur_status in ("missing", "closeup-only"))
    will_set_closeup_main = bool(
        not slab_url and closeup_urls and cur_status == "missing")

    action = "kept main"
    if will_set_slab_main:
        action = f"{cur_status}->slab"
    elif will_set_closeup_main:
        action = "missing->closeup-only"
    elif cur_status == "slab":
        action = "slab (untouched, gallery only)"

    rows_out.append((colour, "match", action,
                      f"{len(closeup_urls)}cu/{len(room_urls)}rm",
                      f"{len(ambiguous)} ambiguous skipped" if ambiguous else "-"))

    if not apply_mode:
        continue

    entry["productUrl"] = m["url"]
    pb_row = pb.get(colour)
    if pb_row and pb_row["sizes"]:
        entry["slabSizes"] = hl.format_slab_sizes(pb_row["sizes"])
    if m.get("description"):
        entry["details"] = m["description"][:300]

    # --- main image ---
    if will_set_slab_main:
        p = dl(slab_url, colour)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            entry["image"] = {"file": fn, "status": "slab", "source": m["url"], "borrowedFrom": ""}
            if was_missing:
                n_new_main += 1
            else:
                n_upgraded_slab += 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if was_missing else "UPGRADED"))
        else:
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    elif will_set_closeup_main:
        p = dl(closeup_urls[0], colour)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            entry["image"] = {"file": fn, "status": "closeup-only", "source": m["url"], "borrowedFrom": ""}
            n_closeup_only_from_missing += 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "NEW (closeup-only)"))
        else:
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
    else:
        mains_sheet.append((colour, None, "still missing"))

    # --- gallery: closeups + rooms (skip whichever image, if any, was used as the main) ---
    gallery = [dict(entry["image"], kind=("slab" if entry["image"]["status"] == "slab" else "closeup"))] \
        if entry["image"].get("file") else []
    used_as_main = closeup_urls[0] if will_set_closeup_main else None
    ci = ri = 0
    for u in closeup_urls:
        if u == used_as_main:
            continue
        p = dl(u, colour)
        if not p or not os.path.exists(p):
            continue
        ci += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
        gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": m["url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
        n_closeups += 1
    for u in room_urls:
        p = dl(u, colour)
        if not p or not os.path.exists(p):
            continue
        ri += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
        gallery.append({"file": fn, "status": "representative", "kind": "room", "source": m["url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(5)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(5)))

print()
print(f"library RT Stone entries: {len(entries)} | matched to a site page: {len(manifest_by_colour)} | "
      f"no site page: {len(entries) - len(manifest_by_colour)}")
print(f"ambiguous (unclassified, keyword-less) extra images skipped across all pages: {n_ambiguous_skipped}")
site_names_not_in_pb = sorted(set())  # populated below from harvest data

if apply_mode:
    def mutate(fresh_lib):
        by_id = {s["id"]: s for s in fresh_lib["slabs"]}
        n = 0
        for e in entries:
            if e["id"] in by_id and by_id[e["id"]].get("supplier") == SUPPLIER:
                by_id[e["id"]].clear()
                by_id[e["id"]].update(e)
                n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly set to slab: {n_new_main} | mains upgraded (closeup-only->slab): {n_upgraded_slab} | "
          f"missing->closeup-only: {n_closeup_only_from_missing} | closeups added: {n_closeups} | rooms added: {n_rooms}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "rtstone-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "rtstone-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = sorted(e["colour"] for e in entries if e["image"]["status"] == "missing")
    still_closeup_only = sorted(e["colour"] for e in entries if e["image"]["status"] == "closeup-only")
    n_dl_fail = sum(1 for _, p, s in mains_sheet if s == "DOWNLOAD FAILED")

    # site products (from the full 111-slug listing) that don't correspond to any RT Stone
    # price-book colour we stock -- informational only, per HARVEST-SPEC rule 4.
    import re as _re
    from harvest_rtstone import get_all_slugs, guess_name, SLUG_BLOCKLIST
    all_slugs = get_all_slugs()
    pb_names_norm = {hl.norm(c) for c in pb}
    site_not_in_pb = sorted(
        guess_name(s) for s in all_slugs
        if s not in SLUG_BLOCKLIST and hl.norm(guess_name(s)) not in pb_names_norm
        and guess_name(s) not in {"Cararra Milano"})

    report_path = os.path.join(hl.REPORTS_DIR, "rtstone-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# RT Stone harvest report

Source: `https://www.quartzbyrtstone.co.uk/products` -- a single static listing page
(no sitemap.xml/robots.txt/wp-sitemap.xml -- all 404 on this custom LiteSpeed PHP
site) linking 111 per-colour pages at `product-details.php?title=<slug>`.
Despite all 38 pre-existing library entries storing `productUrl` as the generic
`/products` listing, real per-colour pages DO exist -- this run replaces the
generic URL with the real product page for every one of the 43 matched colours.

Each product page's own gallery is the `<img class="xzoom-gallery5">` set inside
`#magnific` -- NOT the plain `<img>` tags further down the page, which are a
"Related Products" carousel embedding every other colour's thumbnail (a
false-positive trap for a generic image scraper). Kind classification:
filename keyword first ("close up"/"closeup"/"zoom" -> closeup; "kitchen"
(incl. the site's own "KITHCEN" typo)/"fitted"/"room"/"install" -> room),
first image defaults to slab only when it carries no closeup/room keyword
itself (this correctly caught White Shimmer Supreme, whose sole gallery
image is filenamed "...CloseUP.jpg" -- the site has no slab face for it at
all); a handful of unlabelled middle images in a 3-image gallery were filled
in by position (slab/closeup/room is the consistent order everywhere this
was checked).

## Counts
- Site product-details pages (all colours/materials): {data['all_slugs_count']}
- RT Stone (quartz) price-book colours: {len(pb)}
- Matched to a site product page: {len(manifest_by_colour)}/{len(pb)}
- No site page found: {len(entries) - len(manifest_by_colour)} -- {sorted(set(e['colour'] for e in entries) - set(manifest_by_colour))}
- Mains newly set to slab (was missing): {n_new_main}
- Mains upgraded to slab (was closeup-only): {n_upgraded_slab}
- Mains upgraded missing->closeup-only (site has no slab face): {n_closeup_only_from_missing}
- Main downloads that failed: {n_dl_fail}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Ambiguous extra images skipped (no filename keyword, no positional anchor): {n_ambiguous_skipped}
  -- Amigo Gold (2, a same-named duplicate slab photo + 1 unlabelled), Crystal Blue
     (2, same pattern), Calacatta Ice White (1, "ice white.jfif"), Calacatta Neo
     (1, "NEO.jfif") -- all 4 colours already had a confirmed `slab` main from an
     earlier pass, so nothing is lost by skipping these; worth a manual look if
     completeness of their galleries matters later.
- Still `missing` after this run: {still_missing}
- Still `closeup-only` after this run: {still_closeup_only}
- Site product pages with no matching price-book colour (other RT Stone ranges --
  granite/marble/onyx, or quartz colours we don't currently stock): {len(site_not_in_pb)}
  -- {site_not_in_pb}

## Assumptions
- Price-book "Cararra Milano" (typo) == site "Carrara Milano" -- explicit override,
  not a fuzzy match (the site spelling is presumably the correct one; worth fixing
  the price-book spelling at source).
- "Eternal Calacatta": no slug anywhere on `/products` contains "eternal" in any
  form -- likely discontinued/renamed on the current site. Still `missing`;
  `productUrl` set to the generic listing page as the HARVEST-SPEC fallback;
  `slabSizes` still filled from the price book (authoritative regardless).
- Several price-book colours have 2 site pages (an older "-jumbo"/plain SKU and a
  newer "-zero-silica"/"-super-jumbo-zero-silica" one) -- the zero-silica/newer
  variant was preferred (matches the site's own trend: some colours, e.g. Sand
  Storm, now ONLY have the zero-silica page, the old one retired), except
  Calacatta Auric where the older "-jumbo" page has the fuller gallery
  (slab+closeup+kitchen vs the "-super-jumbo" page's slab+closeup only) --
  spot-checked both before choosing.
- `details` = the page's own `<div class="prod_desc">` paragraph (a per-product
  description distinct from a longer generic marketing block also present on
  the page) -- used verbatim, truncated to 300 chars.
- `slabSizes` taken from the price book (authoritative, all 44 RT Stone colours
  have 20mm+30mm rows), not parsed from the page text.

## Re-run
```
python tools/harvest_rtstone.py            # re-scrape (cached; delete tools/_cache/rtstone to force)
python tools/reconcile_rtstone.py --report  # dry run, prints the match table
python tools/reconcile_rtstone.py --apply   # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
