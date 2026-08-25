"""Reconcile tools/kingstone-harvest.json with slab-library (supplier
"Kingstone"). --report prints the match table and changes nothing; --apply
downloads originals for the currently-`missing` colours, writes webps,
updates slabs.json (bumps `generated` via hl.patch_library), and writes the
contact sheets + REPORT.md.

All 35 price-book colours already have a library entry -- metadata/image
fill-in only, no new entries created.

Image-status rules (see harvest_kingstone.py docstring for the full site
investigation):
  - Every gallery image on kingstonequartz.co.uk/quartz-collection/ is a
    single hero slab photo (portrait or landscape orientation, sometimes
    with a small circled detail-zoom baked in) -- there is no separate
    closeup/room asset anywhere on the site, so every match here is used as
    the `image` (main), never `images[]` kind=closeup/room.
  - Existing image.status == "slab": left completely untouched (22 entries;
    spot-checked one -- Artic Frost -- byte-identical to this run's
    download, so these are already sourced from this same site).
  - image.status == "missing" + a matched site photo: promoted to "slab".
  - productUrl, slabSizes, details are refreshed for ALL 35 matched entries
    (the pre-existing productUrl values were dead `?s=` WordPress search
    links, not real product pages).
  - Nero Calacatta: no matching product on the site -- stays `missing`.
  - "Platinum Grey 113" (site item, old CL1024-Grey-Shimmer filename): not a
    price-book colour -- no entry created, reported for Graham to ask
    Kingstone about (possibly a discontinued/renamed SKU).
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Kingstone"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "KINGSTONE")

apply_mode = "--apply" in sys.argv

data = json.load(open(os.path.join(SCRATCH, "kingstone-harvest.json"), encoding="utf-8"))
manifest = data["manifest"]
LISTING_URL = data["listing_url"]

lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER]
by_colour = {r["colour"]: r for r in entries}
pb = hl.load_pricebook(SUPPLIER)


def dl(url, colour, apply_):
    if not apply_:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data_, used_url = hl.fetch_best(url, supplier="kingstone", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data_, DEST_ROOT, colour, used_fn)


rows_out = []
mains_sheet = []
n_upgraded = n_meta_only = n_dl_fail = 0

for m in manifest:
    colour = m["colour"]
    entry = by_colour.get(colour)
    if entry is None:
        rows_out.append((colour, "NO LIBRARY ENTRY (unexpected)", "-", "-"))
        continue

    cur_status = entry["image"]["status"]
    will_change_main = cur_status != "slab"  # never touch an existing genuine slab main

    slab_sizes = hl.format_slab_sizes(pb[colour]["sizes"]) if pb.get(colour) else ""
    sku_bit = f" {m['sku']}" if m["sku"] else ""
    details = f"Kingstone Quartz{sku_bit} · engineered quartz surface · Polished finish"

    entry["productUrl"] = LISTING_URL
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    entry["details"] = details
    n_meta_only += 1

    rows_out.append((colour, f"{cur_status}->slab" if will_change_main else f"{cur_status} (kept)",
                      m["image_url"].split("/")[-1], slab_sizes or "-"))

    if not apply_mode or not will_change_main:
        if not will_change_main and entry["image"].get("file"):
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
        continue

    p = dl(m["image_url"], colour, apply_mode)
    if not p or not os.path.exists(p):
        n_dl_fail += 1
        mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
        continue

    fn = hl.to_library_webp(p, entry["id"])
    entry["image"] = {"file": fn, "status": "slab", "source": LISTING_URL, "borrowedFrom": ""}
    n_upgraded += 1
    mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "SLAB (new)"))

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

print()
print(f"site colours matched: {len(manifest)} | library colours (pricebook Kingstone): {len(entries)} | "
      f"mains changed: {sum(1 for r in rows_out if '->' in r[1])}")

if apply_mode:
    def apply(lib_fresh):
        # entries dict objects above were mutated on the FIRST load_library().
        # Re-apply the same field values onto the freshly (lock-protected)
        # reloaded lib so a concurrently-running other-supplier agent's
        # writes aren't clobbered.
        fresh_by_colour = {r["colour"]: r for r in lib_fresh["slabs"] if r.get("supplier") == SUPPLIER}
        for colour, entry in by_colour.items():
            fresh = fresh_by_colour.get(colour)
            if fresh is None:
                continue
            fresh["productUrl"] = entry["productUrl"]
            if "slabSizes" in entry:
                fresh["slabSizes"] = entry["slabSizes"]
            if "details" in entry:
                fresh["details"] = entry["details"]
            fresh["image"] = entry["image"]
        return {"upgraded": n_upgraded, "meta_only": n_meta_only, "dl_fail": n_dl_fail}

    result = hl.patch_library(apply, supplier=SUPPLIER)
    print(f"\nAPPLIED. mains -> slab: {n_upgraded} | download failures: {n_dl_fail} | "
          f"metadata-only updates (productUrl/slabSizes/details) on: {n_meta_only}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "kingstone-mains.png"), cols=8)
    print("contact sheet:", m1)
    # galleries sheet: no closeup/room images exist on this site -- write an
    # (empty) placeholder sheet so the file exists per HARVEST-SPEC rule 5.
    m2 = hl.contact_sheet([], os.path.join(hl.REPORTS_DIR, "kingstone-galleries.png"), cols=8)
    print("galleries contact sheet (empty -- site has no closeup/room images):", m2)

    still_missing = sorted(set(data["pricebook_colours_not_on_site"]))
    unmatched_site = data["unmatched_site_items"]

    report_path = os.path.join(hl.REPORTS_DIR, "kingstone-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Kingstone Quartz harvest report

Source: https://kingstonequartz.co.uk (WordPress/Elementor). **All 35 colours sit on ONE
listing page**, `{LISTING_URL}` (an Elementor image-gallery widget, no per-colour product
pages anywhere on the site -- confirmed via `/collection/` (empty stub), the WP sitemap
(only 7 static pages + unused Avada demo "portfolio" posts), and the gallery itself).
Each gallery item is one `<a href="...-scaled.<ext>"><img alt="<Colour> <SKU>"></a>` --
the href is the WP near-original ("-scaled", ~2560px) upload. **No separate closeup or
room images exist anywhere on the site** -- some filenames/alts say "with close up" but
downloading and inspecting one (Artic Frost, 1280x2560px) confirmed this just means the
single photo is a portrait full-slab shot with a small circled detail-zoom baked into the
same image, not a second file -- so `images[]` galleries stay empty for every entry.

22 of 35 price-book colours already had a `"slab"` main in `slabs.json` from an earlier,
undocumented pass; Artic Frost was spot-checked byte-for-byte against this run's fresh
download and is identical, confirming those 22 are already correctly sourced from this
same site -- left untouched this run except for productUrl/slabSizes/details (their old
productUrl values were dead `?s=` WordPress search-result links, not real product pages;
replaced with the real listing page for all 35 matched entries).

## Counts
- Price-book colours (Kingstone): {len(entries)}
- Site gallery items: 35 total ({len(manifest)} matched a price-book colour, {len(unmatched_site)} did not)
- Mains newly set to "slab" (was missing): {n_upgraded}
- Main downloads that failed: {n_dl_fail}
- Existing "slab" mains left untouched (productUrl/slabSizes/details refreshed): {sum(1 for r in rows_out if '(kept)' in r[1])}
- Closeup gallery images: 0 | Room gallery images: 0 (site has neither -- single hero photo per colour)
- Still `missing` (no matching site product), {len(still_missing)}: {still_missing}
- Unmatched site gallery items (no price-book colour), {len(unmatched_site)}:
{chr(10).join(f"  - {u['alt']!r} -> {u['url']}" for u in unmatched_site)}

## Assumptions / judgement calls
- **Portrait "with close-up" photos are the slab main, not a closeup crop.** Several
  filenames (`Artic-Frost-253-...`, `Calacatta-Eclipse-236-with-close-up-...`,
  `Carrara-Michelanglo-211-Slab-with-Close-Up-...`) suggested a texture closeup at first
  glance; downloading and viewing one showed a single portrait-orientation photo of the
  WHOLE slab face (this supplier photographs 3200x1600mm slabs standing tall) with a small
  circled detail-zoom inset drawn onto the same image -- there is no separate closeup file
  to harvest, so every matched item was applied as the `image` main, never as an
  `images[]` closeup/room entry. HARVEST-SPEC's generic slab-aspect check (1.8-2.3:1)
  still holds here once you invert the ratio (1280x2560 -> 0.5 -> 1/0.5 = 2.0), matching
  `harvest_lib.classify_kind`'s symmetric `ar_n` test -- this script does not call
  `classify_kind` at all though, because its filename-hint pass would wrongly tag
  "with-close-up" filenames as kind=closeup before the aspect check ever ran.
- **"Ivory Fantasy 751"** on-site -> price book's **"Ivory Fantasy (Irini)"** (hand-mapped;
  the site drops the "(Irini)" alias the price book carries).
- **"Nabula 611"**: site filename is `Nebula611-...` (their own typo) but the visible page
  alt text reads "Nabula 611", matching the price book's "Nabula" exactly -- used as-is.
- **"Platinum Grey 113"**: a 35th gallery item with no price-book match. Filename
  (`CL1024-Grey-Shimmer-scaled-...`) sits between the price book's "Grey Shimmer" (site
  item "Grey Shimmer 612", filename `grey-shimmer-2.jpg`) and "White Shimmer" (site item
  "White Shimmer 111", filename `CL1022-White-Shimmer-...`) in upload order/naming --
  looks like an older/renamed SKU rather than a genuinely different colour we stock. Not
  assumed to be either; no entry created or touched. **Worth asking Kingstone directly.**
- **Nero Calacatta**: the only price-book colour with no matching product anywhere on the
  site (checked by name and by "Nero"/"Calacatta" substring search across the whole
  listing page HTML -- only "Nero Marquina" and various "Calacatta X" appear, no
  "Nero Calacatta"). Stays `missing`. Worth a supplier check -- possible the price book
  entry is discontinued or renamed.
- `slabSizes` is uniform across all 35 Kingstone price-book rows (20mm and 30mm, both
  3200x1600) -- taken from the price book, not the site (the site states no dimensions).
- `details` = "Kingstone Quartz &lt;SKU&gt; · engineered quartz surface · Polished
  finish" -- SKU from the site's own alt text; "Polished" per the price book's Finish
  column for every Kingstone row (a few site captions say "(Matt Surface)" for 2-3 colours,
  e.g. Artic Frost -- not carried into `details` since the price book, the naming
  authority, lists Polished only; flagged here in case Graham wants a Matt SKU added).

## Re-run
```
python tools/harvest_kingstone.py                  # re-scrape (cached; delete tools/_cache/kingstone to force)
python tools/reconcile_kingstone.py --report        # dry run, prints the match table
python tools/reconcile_kingstone.py --apply         # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
