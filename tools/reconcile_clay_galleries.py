"""Reconcile tools/clay-galleries-harvest.json with slab-library (supplier Clay
International). --report prints the match table and changes nothing; --apply
converts the chosen closeup/room originals to library webps, fills productUrl/
slabSizes/details for the 3 Vein Tech rows, writes slabs.json via
hl.patch_library (bumps `generated`), and writes the two contact sheets + REPORT.md.

Does NOT touch the 75 existing slab mains (never replaces `image`) and does NOT
invent entries for Antibes/Bercy/Gordes (confirmed not on the live site -- see
harvest_clay_galleries.py docstring).
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Clay International"

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "clay-galleries-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
entries = {s["colour"]: s for s in lib["slabs"] if s.get("supplier") == SUPPLIER}

mains_sheet, gallery_sheet = [], []
rows_out = []
n_closeups = n_rooms = n_meta_filled = 0

for m in manifest:
    colour = m["colour"]
    entry = entries.get(colour)
    if entry is None:
        rows_out.append((colour, "NOT IN LIBRARY (unexpected)", "-", "-"))
        continue

    if m["status"] == "not-on-site":
        rows_out.append((colour, "not on live site", "-", "still " + entry["image"]["status"]))
        mains_sheet.append((colour, None, "missing (not on site)"))
        continue

    cu, rm = m.get("closeup"), m.get("room")
    rows_out.append((colour, "ok", cu["name"] if cu else "-", rm["name"] if rm else "-"))

    mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"])
                         if entry.get("image", {}).get("file") else None,
                         entry["image"]["status"]))

    if not apply_mode:
        continue

    # Vein Tech rows: fill productUrl/slabSizes/details (never had them)
    if m.get("vein_tech_of"):
        if m.get("productUrl"):
            entry["productUrl"] = m["productUrl"]
        if m.get("slabSizes"):
            entry["slabSizes"] = m["slabSizes"]
        if m.get("details"):
            entry["details"] = m["details"]
        n_meta_filled += 1

    gallery = [dict(entry["image"], kind="slab")] if entry.get("image", {}).get("file") else []
    if cu:
        fn = hl.to_library_webp(cu["path"], f"{entry['id']}--closeup1")
        gallery.append({"file": fn, "status": "closeup", "kind": "closeup",
                         "source": "onedrive-brands-folder", "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} CU", os.path.join(hl.IMAGES_DIR, fn)))
        n_closeups += 1
    if rm:
        fn = hl.to_library_webp(rm["path"], f"{entry['id']}--room1")
        gallery.append({"file": fn, "status": "representative", "kind": "room",
                         "source": "onedrive-brands-folder", "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} room", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

n_ok = sum(1 for r in rows_out if r[1] == "ok")
n_not_site = sum(1 for r in rows_out if r[1] == "not on live site")
n_no_gallery = sum(1 for m in manifest if m["status"] == "ok" and not m.get("closeup") and not m.get("room"))
print(f"\nentries: {len(manifest)} | ok: {n_ok} | not-on-site: {n_not_site} | "
      f"with no gallery candidate at all: {n_no_gallery}")

if apply_mode:
    entries_touched = entries  # colour -> mutated dict, same objects as loaded above

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for colour, edited in entries_touched.items():
            for s in by_id.get(edited["id"], []):
                if s.get("supplier") == SUPPLIER:
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"closeups added: {n_closeups} | rooms added: {n_rooms} | vein-tech rows filled: {n_meta_filled}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "clay-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "clay-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    no_gallery_colours = sorted(m["colour"] for m in manifest
                                 if m["status"] == "ok" and not m.get("closeup") and not m.get("room"))
    not_on_site = sorted(m["colour"] for m in manifest if m["status"] == "not-on-site")
    no_closeup_only = sorted(m["colour"] for m in manifest
                              if m["status"] == "ok" and m.get("room") and not m.get("closeup"))
    report_path = os.path.join(hl.REPORTS_DIR, "clay-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Clay International gallery harvest report

Source: images ALREADY downloaded by the phase-1 `tools/clay_harvest.py` crawl into
OneDrive `3. CERAMIC- PORCELAIN/Infinity porcelain - clay international/<Colour>/`
(one folder per colour, populated from each product page's own WooCommerce gallery).
This run classifies what's already there rather than re-fetching -- confirmed via the
live `product-sitemap.xml` (72 URLs) that nothing new has been added to the 6 colours
whose folder only ever held the single product-master image (see below), so no
network re-fetch was needed for this pass.

## Counts
- Clay International library entries: {len(manifest)}
- Matched to a folder and processed: {n_ok}
- Not on the live site (no productUrl, no gallery possible): {n_not_site} -- {not_on_site}
- Closeup images added: {n_closeups}
- Room images added: {n_rooms}
- Colours with a room but no closeup candidate: {len(no_closeup_only)} -- {no_closeup_only}
- Colours with NO gallery candidates at all (main-only, confirmed against the live
  page too): {n_no_gallery} -- {no_gallery_colours}
- Vein Tech rows (productUrl/slabSizes/details filled, reusing the base colour's
  photos): Calacatta Hermitage Vein Tech, Calacatta Magnifico Vein Tech, Statuario
  Principe Vein Tech
- Mains: unchanged (75 already `slab`, 3 still `missing` -- see below)

## Assumptions
- Filename origin story: OneDrive folder contents were literally scraped from each
  colour's own `data-large_image` WooCommerce gallery links, however oddly named
  (Italian marketing terms, WhatsApp exports, batch "Screenshot-2025-02-10-*"
  captures, phone "original-<GUID>" exports) -- spot-checked ~15 images across
  colours to confirm they are genuine, colour-appropriate site photography, not
  swatches or unrelated colours reused by mistake.
- Classification: keyword hints first (bagno/cucina/dining/ambiente/living/install
  -> room; dettaglio/detail/thumb/texture -> closeup), then a position fallback for
  unlabelled numbered extras (first -> room, second -> closeup). No aspect-ratio
  signal was reliable on this dataset (both room and closeup shots run ~1.4-2.0:1
  here) -- verified visually before relying on the fallback.
- Any image file whose name exactly matches the current main's own source basename
  is excluded from gallery candidates (same file as the main, not new content) --
  this mattered most for the Arkeon range (Fossil/Plaster/Sandstone), Buxy Select,
  Verde France, Travertine Grey, where the site reuses the main's filename inside
  the product's own gallery listing too.
- Antibes, Bercy, Gordes: confirmed absent from `product-sitemap.xml` (72 URLs) and
  from a site search for each name -- not currently sold on clayinternational.co.uk.
  Left `missing`, no productUrl added; cannot fabricate a slab face. Worth asking
  Clay International directly whether these 3 Infinity colours were discontinued or
  renamed.
- Chianca Di Ostuni, Milan Stone, Pulpis Brown, Terrazzo White, Total Grey, Total
  White: their live product pages carry only the single product-master image --
  re-checked directly against the current page, not just the OneDrive folder. No
  closeup/room photography exists on the site for these 6.
- Vein Tech trio: price book confirms these are the 20mm/bookmatched SKU of their
  base colour (same MB-code), not a separate product -- reused the base colour's
  productUrl and OneDrive photos; `slabSizes` set to the 20mm price-book size only
  (their 6/12mm sizes belong to the base-colour rows).

## Re-run
```
python tools/harvest_clay_galleries.py            # re-classify OneDrive folders (no network unless a folder is new/empty)
python tools/reconcile_clay_galleries.py --report  # dry run, prints the match table
python tools/reconcile_clay_galleries.py --apply   # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
