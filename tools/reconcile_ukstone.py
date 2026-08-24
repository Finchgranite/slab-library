"""Reconcile tools/ukstone-harvest.json with slab-library (supplier
"UK Stone Company") + the price book. --report prints the match table and
changes nothing; --apply downloads originals, writes webps, updates
slabs.json (bumps `generated`) and writes the contact sheet + REPORT.md.

Every one of the 54 price-book colours already has a library entry (id ==
uk-stone-company--<slug>), so this is metadata/image fill-in only -- no new
entries are created. See harvest_ukstone.py's TARGETS dict for how each site
product page was matched to its price-book colour name (hand-built, not
token-subset -- the site's naming is too irregular for that).

Image-status rules (HARVEST-SPEC + this site's quirks):
  - existing image.status == "slab": main image untouched; productUrl/
    slabSizes/details still filled in from the found page.
  - "missing"/"closeup-only" + a genuine full-slab photo found: promote to
    "slab".
  - Grey Mirror Dark/Light: the only image found (2020 upload, "23-e.jpg"/
    "24-e2.jpg") is a cropped texture swatch, not a full slab -> promoted to
    "closeup-only" (matches the pattern the library already used for Blanco
    Lustre), not "slab".
  - Highlands Leathered / Highlands Shimmer Polished: the site serves the
    IDENTICAL file ("Highlands-Quartz-Supplier-Picture-.jpeg") for all three
    Highlands finish variants -- a genuine slab photo, but not each finish's
    own photo. Highlands Polished (the plain/default finish) gets it as
    "slab"; the other two get it as "representative" with borrowedFrom set.
"""
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "UK Stone Company"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "UK STONE COMPANY")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "ukstone-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER]
by_colour = {r["colour"]: r for r in entries}

pb = hl.load_pricebook(SUPPLIER)

# colour -> ("closeup-only" | "representative"), default is "slab"
STATUS_OVERRIDE = {
    "Grey Mirror Dark": "closeup-only",
    "Grey Mirror Light": "closeup-only",
    "Highlands Leathered": "representative",
    "Highlands Shimmer Polished": "representative",
}
BORROWED_FROM = {
    "Highlands Leathered": "Highlands Polished (UK Stone Company) -- site serves an identical "
                            "generic supplier photo for all 3 Highlands finish variants",
    "Highlands Shimmer Polished": "Highlands Polished (UK Stone Company) -- site serves an identical "
                                   "generic supplier photo for all 3 Highlands finish variants",
}

# Site products investigated and rejected (kept here for the report only)
REJECTED = {
    "krystallus-translucent": "Krystallo Translucent Polished Quartzite 2cm -- category Quartzite "
                               "(natural stone), not the pricebook's Emerald Green Translucent quartz",
    "moon-white": "Moon White Polished Granite 3cm -- category Granite (natural stone, Colour=Black "
                  "per its own attribute), not the pricebook's Blanco Luna",
    "mystic-waters-super-jumbo-quartz-2cm": "\"Mystic Waters\" (category Quartz) -- name does not match "
                                             "pricebook's \"Mystic Rivers\"; not assumed the same product",
}


def mm_from_metres(s):
    """'3.20m x 1.60m' -> '3200x1600'."""
    m = re.match(r'([\d.]+)m\s*x\s*([\d.]+)m', s, re.I)
    if not m:
        return None
    return f"{round(float(m.group(1)) * 1000)}x{round(float(m.group(2)) * 1000)}"


def dl(url, colour, apply_):
    if not apply_:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="ukstone", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data, DEST_ROOT, colour, used_fn)


rows_out = []
mains_sheet = []
n_upgraded = n_meta_only = n_closeup_only = n_representative = n_dl_fail = 0

for m in manifest:
    colour = m["colour"]
    entry = by_colour.get(colour)
    if entry is None:
        rows_out.append((colour, "NO LIBRARY ENTRY (unexpected)", "-", "-"))
        continue

    cur_status = entry["image"]["status"]
    target_status = STATUS_OVERRIDE.get(colour, "slab")
    will_change_main = cur_status not in ("slab",) or (cur_status == "slab" and False)
    # never touch an existing genuine slab main
    will_change_main = cur_status != "slab"

    pbrow = pb.get(colour)
    slab_sizes = ""
    if pbrow and pbrow.get("sizes"):
        slab_sizes = hl.format_slab_sizes(pbrow["sizes"])
    if not slab_sizes and m.get("attrs", {}).get("Sizes"):
        mmsz = mm_from_metres(m["attrs"]["Sizes"])
        thk = re.sub(r'[^\d]', '', m["attrs"].get("Thickness", "")) or "?"
        if mmsz:
            slab_sizes = f"{thk}mm: {mmsz}"

    finish = m.get("attrs", {}).get("Material Finishes", "")
    qsize = m.get("attrs", {}).get("Quartz Sizes", "")
    bits = ["UK Stone Company Quartz"]
    if finish:
        bits.append(f"{finish} finish")
    if qsize:
        bits.append(f"{qsize} format")
    details = " · ".join(bits)

    rows_out.append((colour, f"{cur_status}->{target_status}" if will_change_main else f"{cur_status} (kept)",
                      m["url"], slab_sizes or "-"))

    entry["productUrl"] = m["url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    if details:
        entry["details"] = details
    n_meta_only += 1

    if not apply_mode or not will_change_main:
        if not will_change_main and entry["image"].get("file"):
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
        continue

    p = dl(m["image"], colour, apply_mode)
    if not p or not os.path.exists(p):
        n_dl_fail += 1
        mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
        continue

    fn = hl.to_library_webp(p, entry["id"])
    entry["image"] = {"file": fn, "status": target_status, "source": m["url"], "borrowedFrom": ""}
    if target_status == "representative":
        entry["image"]["borrowedFrom"] = BORROWED_FROM.get(colour, "")
        n_representative += 1
    elif target_status == "closeup-only":
        n_closeup_only += 1
    else:
        n_upgraded += 1
    mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), target_status.upper()))

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

print()
print(f"site colours targeted: {len(manifest)} | library colours (pricebook UK Stone Company): {len(entries)} | "
      f"main images changed: {sum(1 for r in rows_out if '->' in r[1])}")

if apply_mode:
    hl.save_library(lib)
    print(f"\nAPPLIED. mains -> slab: {n_upgraded} | -> closeup-only: {n_closeup_only} | "
          f"-> representative: {n_representative} | download failures: {n_dl_fail} | "
          f"metadata-only updates (productUrl/slabSizes/details): {n_meta_only}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "ukstone-mains.png"), cols=8)
    print("contact sheet:", m1)

    still_missing = sorted(c for c in pb if c not in {r["colour"] for r in manifest})
    unmatched_site = sorted(REJECTED)

    report_path = os.path.join(hl.REPORTS_DIR, "ukstone-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# UK Stone Company harvest report

Source: https://ukstonecompany.com (WordPress/WooCommerce/Avada). Colour list
came from `wp-sitemap-posts-product-1.xml` (273 product pages total, natural
stone -- granite/marble/quartzite -- excluded, out of scope this phase).
Each targeted product page has exactly ONE hero photo (no closeup/room
galleries anywhere on the site); it lives in the
`woocommerce-product-gallery__wrapper` figure as `data-large_image` (true px
size in `data-large_image_width/height`), alongside a `custom-attributes`
list (Material Finishes / Material Type / Quartz Sizes / Thickness / Sizes in
metres) and a `Category:` line used to reject natural-stone pages that share
a colour word (see Rejected below).

Because the site's title/slug naming is irregular (some titles fold in
"Jumbo"/"Super Jumbo" as a size descriptor, some finish variants collapse
onto one product page, one dark/light pair never got a Light page), matching
was done by hand (`harvest_ukstone.py`'s `TARGETS` dict, 42 site pages) built
from the sitemap's 273 slugs cross-checked against the 54 price-book colours,
rather than the generic token-subset matcher.

## Counts
- Library colours (price book "{SUPPLIER}"): {len(entries)}
- Site pages targeted / matched: {len(manifest)}
- Mains newly set to "slab" (was missing/closeup-only): {n_upgraded}
- Mains set to "closeup-only" (best image found is a texture crop, not a full slab): {n_closeup_only}
- Mains set to "representative" (borrowed image, see Assumptions): {n_representative}
- Main downloads that failed: {n_dl_fail}
- Existing "slab" mains left untouched, productUrl/slabSizes/details filled: {sum(1 for r in rows_out if '(kept)' in r[1])}
- Closeup/room gallery images: 0 (site has none -- single hero image per product)
- Still `missing` (no site page found for this price-book colour), {len(still_missing)}: {still_missing}
- Unmatched site products investigated and rejected (not this colour), {len(unmatched_site)}:
{chr(10).join(f"  - {s}: {REJECTED[s]}" for s in unmatched_site)}

## Assumptions / judgement calls
- **Grey Shimmer Dark vs Light**: the site carries only one "Grey Shimmer"
  product (no Dark/Light split in the slug or title); its photo reads as a
  mid/dark tone, so it was assigned to "Grey Shimmer Dark". "Grey Shimmer
  Light" stays `missing`. Worth a supplier check.
- **Carrara Vincenza**: site title is "Blanco Carrara Vincenza Jumbo Quartz"
  -- token-subset matching would reject this (extra "Blanco" token) so it was
  matched by hand to the price book's "Carrara Vincenza".
- **Highlands Polished/Leathered/Shimmer Polished**: the site serves the
  exact same file for all three finish variants' product pages. Polished
  (the plain/default finish this generic photo most plausibly shows) got
  `status: slab`; the other two got `status: representative` with
  `borrowedFrom` noted -- a real texture-specific photo would be better if
  the supplier can provide one.
- **Grey Mirror Dark/Light**: only image available (2020 upload, filenames
  "23-e.jpg"/"24-e2.jpg") is a cropped texture swatch on white padding, not a
  full slab -- promoted `missing -> closeup-only` (matching how the library
  already treated Blanco Lustre before this run), not `slab`.
- `slabSizes` comes from the price book first; the page's own `Sizes`
  attribute (metres, converted to mm) only as a fallback when the price book
  has no size row for that colour+thickness.
- `details` = "UK Stone Company Quartz · <Material Finishes> finish · <Quartz
  Sizes> format" from the page's own attributes. No distributor/other-brand
  name was found anywhere on any fetched page (no description/tab content,
  no brand text) -- these appear to be UK Stone Company's own-labelled range
  (product photos carry a "UK STONE COMPANY" logo watermark), so no brand
  prefix was added to `details`.
- No closeup/room gallery images exist anywhere on this site -- every product
  page has exactly one image in its WooCommerce gallery.

## Re-run
```
python tools/harvest_ukstone.py                 # re-scrape (cached; delete tools/_cache/ukstone to force)
python tools/reconcile_ukstone.py --report       # dry run, prints the match table
python tools/reconcile_ukstone.py --apply        # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
