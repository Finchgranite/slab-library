"""Reconcile tools/neolith-harvest.json with slab-library (supplier "Neolith",
45 sintered-stone colours, all engineered). --report prints the plan and
changes nothing; --apply downloads/converts, updates slabs.json via
hl.patch_library (bumps `generated`), writes contact sheets + REPORT.md.

Scope of this run (see harvest_neolith.py's docstring for the full diligence
trail):
  1. Fill the 4 `missing` mains (Black Obsession, Cappadocia Sunset,
     Calacatta Roma (BM), Everest Sunrise) with a real slab face -- 2 from
     the official Neolith UK 2026 asset zip already in the OneDrive Neolith
     folder, 2 fetched live from neolith.com (higher-res than the zip copy).
     The 41 existing slab mains are left untouched.
  2. Add one room image for Himalaya Crystal (brochure page, London private
     residence) -- the only >300px, colour-attributable, non-swatch photo
     found anywhere in the sources checked beyond what's already in the
     library. The 5 Thomas-Group-linked entries (Beton, Calacatta (BM),
     Calacatta Gold (BM), Estatuario (BM), Zaha Stone) already carry a TSC
     closeup from an earlier run -- left as-is, TSC has no room shots.
  3. `slabSizes` for every entry from hl.load_pricebook("Neolith") (exact
     1:1 name match against all 45 colours, verified before writing this --
     no Thomas Group fallback needed).
  4. One-line `details` for every entry that lacks one: collection name
     (parsed from productUrl's /collections/<slug>/ segment where known) +
     finish(es) + thickness range from the price book.
"""
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Neolith"
CACHE = os.path.join(hl.CACHE_ROOT, "neolith")
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "3. CERAMIC- PORCELAIN", "Neolith")

COLLECTION_LABEL = {"classtone": "Classtone", "colorfeel": "Colorfeel", "fusion": "Fusion",
                     "iron": "Iron", "steel": "Steel"}

apply_mode = "--apply" in sys.argv

harvest = json.load(open(os.path.join(SCRATCH, "neolith-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == "Neolith" and not r.get("naturalStone")]
pb = hl.load_pricebook(SUPPLIER)

by_colour = {e["colour"]: e for e in entries}
unmatched_pb = sorted(set(pb) - set(by_colour))
unmatched_lib = sorted(set(by_colour) - set(pb))


def details_for(entry):
    row = pb.get(entry["colour"])
    if not row:
        return None
    bits = []
    m = re.search(r'/collections/([a-z]+)/', entry.get("productUrl") or "")
    if m and m.group(1) in COLLECTION_LABEL:
        bits.append(f"Neolith {COLLECTION_LABEL[m.group(1)]} collection")
    else:
        bits.append("Neolith sintered stone")
    if row["finishes"]:
        bits.append("/".join(sorted(row["finishes"])) + " finish")
    if row["thicknesses"]:
        bits.append("/".join(str(t) for t in sorted(row["thicknesses"])) + "mm")
    return " · ".join(bits)


mains_sheet, gallery_sheet = [], []
rows_out = []
n_new_main = n_rooms = n_meta = 0

for e in entries:
    colour = e["colour"]
    row = pb.get(colour)
    changed_meta = []

    fill = harvest["missing_fills"].get(colour)
    will_fill_main = bool(fill and e["image"]["status"] == "missing")

    slab_sizes = hl.format_slab_sizes(row["sizes"]) if row and row["sizes"] else ""
    if slab_sizes and not e.get("slabSizes"):
        changed_meta.append("slabSizes")

    # use the productUrl this entry will have AFTER the fill (if any) so a
    # newly-discovered live URL (Calacatta Roma / Everest Sunrise) is
    # reflected in the collection name, not the pre-fill blank productUrl
    effective_url = (fill["productUrl"] if will_fill_main and fill.get("productUrl")
                      else e.get("productUrl"))
    details = details_for({**e, "productUrl": effective_url})
    if details and not e.get("details"):
        changed_meta.append("details")

    room = harvest["brochure_room"] if harvest["brochure_room"]["colour"] == colour else None

    rows_out.append((colour, e["image"]["status"], "NEW MAIN" if will_fill_main else "-",
                      "+room" if room else "-", ",".join(changed_meta) or "-"))

    if not apply_mode:
        continue

    if slab_sizes and not e.get("slabSizes"):
        e["slabSizes"] = slab_sizes
    if details and not e.get("details"):
        e["details"] = details
    if changed_meta:
        n_meta += 1

    if will_fill_main:
        src_path = os.path.join(CACHE, fill["cache_file"])
        data = open(src_path, "rb").read()
        p = hl.save_original(data, DEST_ROOT, colour, fill["fn"])
        webp_fn = hl.to_library_webp(p, e["id"])
        e["image"] = {"file": webp_fn, "status": "slab", "source": fill["source"], "borrowedFrom": ""}
        if fill["productUrl"]:
            e["productUrl"] = fill["productUrl"]
        n_new_main += 1
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, webp_fn), "NEW"))
    elif e["image"].get("file"):
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, e["image"]["file"]), "kept"))
    else:
        mains_sheet.append((colour, None, "still missing"))

    if room:
        src_path = os.path.join(CACHE, room["cache_file"])
        data = open(src_path, "rb").read()
        p = hl.save_original(data, DEST_ROOT, colour, room["cache_file"].split("__", 1)[1])
        room_fn = hl.to_library_webp(p, f"{e['id']}--room1")
        gallery = e.get("images") or ([dict(e["image"], kind="slab")] if e["image"].get("file") else [])
        gallery.append({"file": room_fn, "status": "representative", "kind": "room",
                         "source": room["source"], "borrowedFrom": "", "caption": room["caption"]})
        e["images"] = gallery
        n_rooms += 1
        gallery_sheet.append((f"{colour} room1", os.path.join(hl.IMAGES_DIR, room_fn)))

# existing galleries (already-populated closeups) also go on the gallery contact sheet for review
for e in entries:
    for im in e.get("images", []):
        if im.get("kind") == "closeup":
            gallery_sheet.append((f"{e['colour']} {im.get('kind')}", os.path.join(hl.IMAGES_DIR, im["file"])))

w = [max((len(str(r[i])) for r in rows_out), default=6) for i in range(5)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(5)))
print()
print(f"Neolith library entries: {len(entries)} | price-book colours: {len(pb)} | "
      f"unmatched lib->pb: {unmatched_lib} | unmatched pb->lib: {unmatched_pb}")

if apply_mode:
    ids_touched = {e["id"]: e for e in entries}

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, edited in ids_touched.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == "Neolith" and not s.get("naturalStone"):
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly filled: {n_new_main} | rooms added: {n_rooms} | entries with new slabSizes/details: {n_meta}")

    m1 = hl.contact_sheet([(e["colour"], os.path.join(hl.IMAGES_DIR, e["image"]["file"])
                             if e["image"].get("file") else None) for e in entries],
                           os.path.join(hl.REPORTS_DIR, "neolith-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "neolith-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = sorted(r["colour"] for r in entries if r["image"]["status"] == "missing")
    no_gallery = sorted(r["colour"] for r in entries if not r.get("images"))
    blocked_note = (
        "Every colour whose gallery is still empty (all 45 minus the 5 Thomas-Group-linked "
        "ones, plus Himalaya Crystal's new room) has NO curl-fetchable closeup/room source: "
        "neolith.com's product pages (and their Nuxt static state.js/payload.js sidecars) "
        "carry exactly one photo -- the slab -- with the rest of the gallery hydrated by a "
        "live runtime API call; thesurfacecollection.co.uk's Neolith page only covers 16 "
        "different colourways of which 5 already overlap our library. A claude-in-chrome "
        "pass on neolith.com product pages (or the /en/neolith-projects/ grid, JS-rendered) "
        "is the only way to get closeup/room images for the other ~39 colours."
    )
    report_path = os.path.join(hl.REPORTS_DIR, "neolith-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Neolith harvest report (galleries pass)

Sources used this run (see `harvest_neolith.py` docstring for full diligence trail):
1. **Neolith UK official asset zip** (already in OneDrive
   `3. CERAMIC- PORCELAIN\\Neolith\\laurelcomms_full-uk-neolith-colour-collection_2026-03-31_0945.zip`,
   dated Jan 2026) -- slab photos for Black Obsession and Cappadocia Sunset,
   which are confirmed DELISTED from the current neolith.com `/en/all-colours`
   (no "black"/"cappadocia" string anywhere in that page's data payload) --
   the zip is the only source, `productUrl` left blank for these two.
2. **neolith.com live fetch** (curl, NOT bot-blocked -- returns 200 SSR HTML,
   contrary to the 2026-08-24 Thomas Group discovery note) -- Calacatta Roma
   and Everest Sunrise DO still have live pages (`classtone/calacatta-roma/`,
   `classtone/everest-sunrise/`) that the library had simply never recorded;
   their Storyblok full-res originals were fetched directly (2000x3945 and
   1250x1824) rather than using the zip's lower-res copies.
3. **Brochure PDF** (inside the same zip) -- one room photo, Himalaya
   Crystal, London private residence (1009x771, page 7 of 17). Everything
   else image-sized in the brochure is either an awards-logo montage or a
   swatch grid under 300px wide (skipped per spec rule 3).
4. **Price book** (`hl.load_pricebook("Neolith")`) -- exact 1:1 match against
   all 45 library colours (no unmatched names either direction) -- supplied
   `slabSizes` and (with the collection parsed from `productUrl`) `details`
   for every entry that lacked one.

## Counts
- Neolith library entries: {len(entries)} (all engineered, none touched outside this supplier)
- Mains newly filled (was `missing`): {n_new_main} / 4 -- {sorted(harvest['missing_fills'])}
- Still `missing` after this run: {still_missing or 'none'}
- Room images added: {n_rooms} (Himalaya Crystal)
- Closeup images already present (unchanged, from an earlier Thomas Group run): 5
  (Beton, Calacatta (BM), Calacatta Gold (BM), Estatuario (BM), Zaha Stone)
- Entries with `slabSizes`/`details` newly filled: {n_meta}
- Entries with no gallery (`images[]`) at all after this run: {len(no_gallery)} / {len(entries)}

## Image source per new asset
- Black Obsession, Cappadocia Sunset: Neolith UK official asset zip (slab)
- Calacatta Roma (BM), Everest Sunrise: neolith.com live Storyblok fetch (slab)
- Himalaya Crystal: Neolith UK Brochure PDF, page 7 (room)

## Blocked / unavailable for galleries (orchestrator browser-pass candidates)
{blocked_note}

## Assumptions
- Black Obsession and Cappadocia Sunset have no confirmed current
  neolith.com collection (their live pages 403 on every `classtone/<slug>/`
  guess tried, and they don't appear in `/en/all-colours` at all) -- their
  `details` line omits a collection name ("Neolith sintered stone" instead
  of e.g. "Neolith Classtone collection"); worth confirming with Neolith UK
  whether these are simply discontinued.
- Price book is the sizing/naming authority throughout; no Thomas Group
  fallback was needed since all 45 Neolith price-book rows matched the
  library 1:1.

## Re-run
```
python tools/harvest_neolith.py             # re-extract/fetch (cached under tools/_cache/neolith/)
python tools/reconcile_neolith.py --report   # dry run, prints the plan
python tools/reconcile_neolith.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
