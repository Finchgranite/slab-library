"""Reconcile tools/technistone-harvest.json with slab-library (supplier
Technistone, engineered colours only). --report prints the match table and
changes nothing; --apply converts the local OneDrive originals (found by
harvest_technistone.py's scan of BRANDS_ROOT/1. QUARTZ/TECHNISTONE/
"Sample,slab & kitchen images"/<Colour>/) into library webps, updates
slabs.json via hl.patch_library (bumps `generated`), writes the two contact
sheets + REPORT.md.

Per the task brief: all 49 entries already have a good slab main -- this
run NEVER touches `image` (the main), only adds `images[]` gallery entries
(closeup/room), fills `slabSizes` (price book, authoritative) and `details`
(collection + finish + site blurb) where those fields are absent.
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Technistone"

apply_mode = "--apply" in sys.argv

data = json.load(open(os.path.join(SCRATCH, "technistone-harvest.json"), encoding="utf-8"))
manifest = data["entries"]
site_slugs = data.get("site_slugs", [])

lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == "Technistone" and not r.get("naturalStone")]
by_id = {e["id"]: e for e in entries}

pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_closeups = n_rooms = n_filled_sizes = n_filled_details = 0
no_gallery = []
edited = {}   # id -> mutated dict, applied via patch_library at the end


def build_details(rec):
    bits = []
    if rec.get("collection"):
        bits.append(rec["collection"])
    if rec.get("finishes"):
        bits.append(f"{'/'.join(rec['finishes'])} finish")
    if rec.get("description"):
        bits.append(rec["description"])
    text = ". ".join(b.rstrip(".") for b in bits if b)
    return text[:400]


for rec in manifest:
    entry = by_id.get(rec["id"])
    if not entry:
        rows_out.append((rec["colour"], "NOT IN LIBRARY (unexpected)", "-", "-"))
        continue

    pb_row = pb.get(entry["colour"])
    slab_sizes = hl.format_slab_sizes(pb_row["sizes"]) if pb_row and pb_row["sizes"] else ""
    details = build_details(rec)

    cu = len(rec.get("closeups", []))
    rm = len(rec.get("rooms", []))
    if cu == 0 and rm == 0:
        no_gallery.append(entry["colour"])

    will_fill_sizes = bool(slab_sizes) and not entry.get("slabSizes")
    will_fill_details = bool(details) and not entry.get("details")

    rows_out.append((
        entry["colour"],
        "error:" + rec["error"] if rec.get("error") else "ok",
        f"cu={cu} rm={rm}",
        f"sizes{'+' if will_fill_sizes else '='} details{'+' if will_fill_details else '='}",
    ))

    if not apply_mode:
        continue

    ed = dict(entry)   # shallow copy to mutate; entry itself left alone until patch time
    if will_fill_sizes:
        ed["slabSizes"] = slab_sizes
        n_filled_sizes += 1
    if will_fill_details:
        ed["details"] = details
        n_filled_details += 1

    # --- gallery: closeups + rooms (main image/status untouched) ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    for i, p in enumerate(rec.get("closeups", []), 1):
        if not os.path.exists(p):
            continue
        fn = hl.to_library_webp(p, f"{entry['id']}--closeup{i}")
        gallery.append({"file": fn, "status": "closeup", "kind": "closeup",
                         "source": rec.get("url", "technistone.com"), "borrowedFrom": ""})
        gallery_sheet.append((f"{entry['colour']} CU{i}", os.path.join(hl.IMAGES_DIR, fn)))
        n_closeups += 1
    for i, p in enumerate(rec.get("rooms", []), 1):
        if not os.path.exists(p):
            continue
        fn = hl.to_library_webp(p, f"{entry['id']}--room{i}")
        gallery.append({"file": fn, "status": "representative", "kind": "room",
                         "source": rec.get("url", "technistone.com"), "borrowedFrom": ""})
        gallery_sheet.append((f"{entry['colour']} room{i}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        ed["images"] = gallery

    edited[entry["id"]] = ed
    mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))

# --- price-book / site cross-check ---
unmatched_pb = sorted(set(pb) - {e["colour"] for e in entries if e["id"] in by_id})
site_extra = []
for slug in site_slugs:
    name_guess = slug.replace("-", " ").title()
    m, score = hl.match_colour(name_guess, [(c, c) for c in pb])
    if not m:
        site_extra.append(slug)

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

print()
print(f"library Technistone engineered entries: {len(entries)} | harvest records: {len(manifest)}")
print(f"colours with NO local closeup and NO local room found: {no_gallery}")
print(f"price-book Technistone colours with no library entry: {unmatched_pb}")
print(f"site sitemap slugs with no price-book match (site colours we don't stock -- sitemap is "
      f"stale/incomplete, lower bound only): {len(site_extra)} -> {site_extra}")

if apply_mode:
    def mutate(fresh_lib):
        n = 0
        for s in fresh_lib["slabs"]:
            sid = s.get("id")
            if s.get("supplier") == "Technistone" and sid and sid in edited:
                s.clear()
                s.update(edited[sid])
                n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"slabSizes filled: {n_filled_sizes} | details filled: {n_filled_details} | "
          f"closeups added: {n_closeups} | rooms added: {n_rooms}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "technistone-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "technistone-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "technistone-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Technistone harvest report (galleries pass)

Source: all 49 library entries already had a good slab main + productUrl
(`https://www.technistone.com/gbr/color/<slug>`) from an earlier pass --
this run is galleries-only.

**Key finding**: an earlier pass had already downloaded a near-complete
media package per colour into OneDrive under
`1. QUARTZ\\TECHNISTONE\\Sample,slab & kitchen images\\<Colour>\\`, usually a
`<slug>-mediaPackage-lowRes\\` folder with `<slug>-detail.jpg` (closeup),
`<slug>-fullSlab.jpg` (slab, unused -- mains were not replaced),
`<slug>-moodboard.jpg` (styled prop shot, skipped -- not slab/closeup/room),
and `realizations\\<slug>-realization-N.jpg` (room/installation photos).
A few colours (Badal Grey, Crystal Diamond, Duna Beige, Elysian Gold,
Mistral White, Taj Mahal Gold) had a flatter layout with `slab-detail.jpg` +
`realization-N.jpg` directly in the colour folder. Every one of the 49 had
at least a room gallery locally; all but Crystal Diamond also had a
closeup. This run therefore used those local originals directly (per
HARVEST-SPEC.md's "check that folder first" rule) rather than re-fetching
images from the live site -- only page TEXT was fetched over the network
(2s/request, cached under `tools/_cache/technistone/`), for the
"<Collection> Collection" subtitle, meta-description blurb and
Specifications-table Finish value used to build `details`.

Up to 2 closeups and 3 rooms were converted per colour (files already on
disk in far greater number for many colours, e.g. Noble Areti Bianco had 46
room candidates locally -- capped to keep the library/contact sheets sane).

## Counts
- Library Technistone engineered entries: {len(entries)}
- Colours with a local closeup found: {sum(1 for m in manifest if m.get('closeups'))}
- Colours with a local room photo found: {sum(1 for m in manifest if m.get('rooms'))}
- Colours with NEITHER (no gallery material found): {len(no_gallery)} -> {no_gallery}
- Closeup images added: {n_closeups}
- Room images added: {n_rooms}
- slabSizes filled from price book: {n_filled_sizes}
- details filled (collection + finish + site blurb): {n_filled_details}
- Mains: unchanged for all 49 (all already had a good slab main; not replaced per task brief)
- Price-book Technistone colours with no library entry: {len(unmatched_pb)} -> {unmatched_pb}
- Site sitemap slugs with no price-book match (site colours we don't stock): {len(site_extra)}
  -> {site_extra}
  NOTE: technistone.com/sitemap.xml is dated 2023 and is missing several
  colours whose product pages return 200 today (e.g. badal-grey,
  duna-beige, elysian-gold, morning-daisy, taj-mahal-gold, wedding-lily,
  wild-yucca) -- it is a lower bound, not a full site colour list. The
  OneDrive folder also held originals for further site colours not in our
  price book: Ambiente-Light, Calacatta Pastino, Country Rose, Crystal
  Vulcano, Gobi Grey, Imagine Grey, Romano Ricco, Taurus Terazzo Grey.

## Assumptions
- slabSizes taken from the price book (authoritative per HARVEST-SPEC.md);
  confirmed matching the site's own Specifications "Size" row on Altamonte
  (Jumbo 165: 3300x1650mm both places).
- `details` built as "<Collection> Collection. <Finish> finish.
  <site meta-description>" -- only filled where the field was previously
  absent (all 49, this run).
- Local "moodboard"/"mood board" files (styled prop/flat-lay shots) and
  "*_SLAB*"/"*fullSlab*"/"*-by-Technistone*" files (duplicates of the
  existing main) were excluded from the gallery -- not real closeup/room
  content per the spec's own classifier intent.
- Room photos capped at 3/colour, closeups at 2/colour, picked by natural
  filename order (realizations) / largest-file-first (closeups) -- plenty
  more exist on disk locally for most colours if a deeper gallery is wanted
  later (just re-run harvest_technistone.py with the cap raised).

## Re-run
```
python tools/harvest_technistone.py            # re-scrape page text (cached; delete tools/_cache/technistone to force)
python tools/reconcile_technistone.py --report  # dry run, prints the match table
python tools/reconcile_technistone.py --apply   # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
