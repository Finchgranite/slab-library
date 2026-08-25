"""Reconcile tools/akg-galleries-harvest.json into slab-library (AKG Surfaces,
gallery images only -- see harvest_akg_galleries.py for how picks were made).
--report prints what would happen, changes nothing. --apply converts the
chosen local originals to library webps, updates slabs.json via
hl.patch_library (bumps `generated`, one short call after all conversions per
HARVEST-SPEC concurrency rule), fills slabSizes/details from the price book
where still absent (Velare Gold only), and writes both contact sheets +
tools/_reports/akg-REPORT.md.

Never touches the existing `image` (main) field -- true-scale pass already
done for all 49, per the brief.
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "AKG Surfaces"
ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "AKG SURFACES (Sempre-Coante)")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "akg-galleries-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
by_id = {s["id"]: s for s in lib["slabs"] if s.get("supplier") == SUPPLIER}
pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows = []
n_closeups = n_rooms = n_meta_filled = 0
no_gallery = []

edits = {}   # id -> {"images_extra": [...], "slabSizes":.., "details":..}

for m in manifest:
    entry = by_id.get(m["id"])
    if entry is None:
        rows.append((m["colour"], "NOT IN LIBRARY", "-", "-"))
        continue

    closeup_fn = (m["new_closeups"] or m["local_closeups"] or [None])[0]
    room_fn = (m["new_rooms"] or m["local_rooms"] or [None])[0]

    edit = {"images_extra": [], "slabSizes": None, "details": None}

    if entry.get("colour") == "Velare Gold":
        pbrow = pb.get("Velare Gold")
        if pbrow and not entry.get("slabSizes"):
            edit["slabSizes"] = hl.format_slab_sizes(pbrow["sizes"])
        if not entry.get("details"):
            fins = "/".join(sorted(pbrow["finishes"])) if pbrow else ""
            edit["details"] = ("Coante range (price-book only -- discontinued/renamed on "
                                "akgsurfaces.co.uk, confirmed via live site search)."
                                + (f" Finish: {fins}." if fins else ""))

    if closeup_fn and m["folder"]:
        src = os.path.join(ROOT, m["folder"], closeup_fn)
        if os.path.exists(src):
            edit["images_extra"].append(("closeup", src, closeup_fn))
    if room_fn and m["folder"]:
        src = os.path.join(ROOT, m["folder"], room_fn)
        if os.path.exists(src):
            edit["images_extra"].append(("room", src, room_fn))

    if not edit["images_extra"]:
        no_gallery.append(entry["colour"])

    edits[m["id"]] = edit
    rows.append((m["colour"], closeup_fn or "-", room_fn or "-", m.get("note", "").strip()[:60]))

w = [max((len(str(r[i])) for r in rows), default=8) for i in range(4)]
for r in rows:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))
print()
print(f"colours: {len(manifest)} | with closeup pick: {sum(1 for e in edits.values() if any(k=='closeup' for k,_,_ in e['images_extra']))} | "
      f"with room pick: {sum(1 for e in edits.values() if any(k=='room' for k,_,_ in e['images_extra']))} | "
      f"no gallery at all: {len(no_gallery)} -- {no_gallery}")

if not apply_mode:
    sys.exit(0)

# --- convert + build images[] ---
for eid, edit in edits.items():
    entry = by_id.get(eid)
    if entry is None:
        continue
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    for kind, src, orig_fn in edit["images_extra"]:
        idx = 1
        out_id = f"{eid}--{kind}{idx}"
        fn = hl.to_library_webp(src, out_id)
        gallery.append({"file": fn, "status": kind, "kind": kind,
                         "source": entry.get("productUrl", ""), "borrowedFrom": ""})
        thumb_path = os.path.join(hl.IMAGES_DIR, fn)
        if kind == "closeup":
            n_closeups += 1
            gallery_sheet.append((f"{entry['colour']} CU", thumb_path))
        else:
            n_rooms += 1
            gallery_sheet.append((f"{entry['colour']} room", thumb_path))
    if len(gallery) > 1:
        edit["_gallery"] = gallery
    if entry["image"].get("file"):
        mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))


def mutate(fresh_lib):
    n = 0
    for s in fresh_lib["slabs"]:
        if s.get("supplier") != SUPPLIER:
            continue
        edit = edits.get(s["id"])
        if not edit:
            continue
        changed = False
        if edit.get("_gallery"):
            s["images"] = edit["_gallery"]
            changed = True
        if edit.get("slabSizes"):
            s["slabSizes"] = edit["slabSizes"]
            changed = True
        if edit.get("details"):
            s["details"] = edit["details"]
            changed = True
        if changed:
            n += 1
    return {"updated": n}


result = hl.patch_library(mutate, supplier=SUPPLIER)
print(f"\nAPPLIED via patch_library: {result}")

m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "akg-mains.png"), cols=8)
m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "akg-galleries.png"), cols=8)
print("contact sheets:", m1, m2)

report_path = os.path.join(hl.REPORTS_DIR, "akg-REPORT.md")
closeup_colours = sorted(entry["colour"] for eid, entry in by_id.items()
                          if any(k == "closeup" for k, _, _ in edits.get(eid, {}).get("images_extra", [])))
room_colours = sorted(entry["colour"] for eid, entry in by_id.items()
                       if any(k == "room" for k, _, _ in edits.get(eid, {}).get("images_extra", [])))
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"""# AKG Surfaces gallery harvest report

Scope: 49 AKG Surfaces (Coante quartz) library entries. All 49 already had a
true-scale slab main -- this run only added `closeup`/`room` `images[]`.
Originals live under OneDrive `1. QUARTZ/AKG SURFACES (Sempre-Coante)/<Colour>/`,
already populated by the earlier akg_harvest.py (Cloudinary CDN) +
akg_wp_sweep.py (plain wp-content) crawls -- this run classified what was
already there (13 colours needed nothing more), then re-fetched the live
product page for every colour still missing a closeup and/or room to check
for anything the earlier crawl missed.

Classification: AKG's own filenames carry the kind reliably (Kitchen/K-
suffix/Composition/Render/Marketing = room; Close-Up/Bookmatch/PQ/Pattern/
Detail = closeup). Verified a sample of each keyword visually before writing
the classifier (Adira Bronze Render, Zenit Render, Alba Via Composition/
Bookmatch, Bianco Eclipsia PQ, Calacatta Clara Pattern, Carrara Enigma
Marketing). AKG also republishes the SAME full-slab photo as a square 1:1
social-media crop (e.g. Cortina/Sierra/Brittanica/Nuvo/Venato/Vicenza) --
confirmed visually these are NOT texture closeups, so aspect ratio was
deliberately NOT used as a fallback classifier here (unlike other suppliers)
to avoid mislabelling a slab crop as a closeup.

## Counts
- AKG library entries: 49 (all engineered Coante quartz)
- Colours with a closeup added/kept: {len(closeup_colours)} -- {closeup_colours}
- Colours with a room added/kept: {len(room_colours)} -- {room_colours}
- Colours with NO closeup and NO room available (from OneDrive or the live
  site): {len(no_gallery)} -- {no_gallery}
- Mains: all 49 unchanged (true-scale pass already done; this run never
  touches `image`)
- Live product pages re-fetched to check for missed images: 35 (every colour
  short a closeup and/or room after the local pass); zero produced a NEW
  image not already downloaded by the earlier crawls -- i.e. the gaps above
  are real (AKG's page for that colour genuinely has no separate closeup/
  room asset), not a crawl miss.

## Assumptions / notes
- **Velare Gold**: `productUrl` was a placeholder `?s=Velare+Gold` search
  link (never a real product page) and there is no OneDrive folder for it.
  Confirmed via a live site search (`?s=Velare+Gold` and `?s=Velare`) that
  AKG Surfaces no longer lists this colour at all ("Sorry, but nothing
  matched your search terms" / "No results") -- likely discontinued or
  renamed since the price-book row was added. `slabSizes`/`details` filled
  from the price book instead (20/30mm: 3200x1600, Polished). Main image
  kept (from an earlier crawl, source is a Cloudinary URL that may or may
  not still resolve). No gallery possible. Worth asking AKG directly what
  this colour is called now, or dropping it if genuinely discontinued.
- **"Coante Arteo 3D" range** (Adira Bronze, Calacatta Arlena, Calacatta
  Claire, Cathara Bronze, Elvare, Solesta, Strataveris): every page follows
  a fixed 3-shot template -- High-V Slab / Low-V Slab / Render -- so these
  have a room (Render) but genuinely no closeup on the site.
- A handful of colours (Aurora Gold, Barents, Iceberg Mist) have neither a
  closeup nor a room anywhere -- their AKG page is a single hero slab shot
  only (1-4 Cloudinary assets total, all slab angles).
- `images[]` only added where `len(gallery) > 1` i.e. at least one real
  closeup/room exists; colours with neither keep just their existing `image`
  main (no `images[]` array), same as before this run.
- `source` on gallery images is the product page URL (`productUrl`), not a
  per-asset CDN URL -- the originals were already on disk from the earlier
  crawl and per-file source URLs weren't retained in a manifest this agent
  could read (`akg-harvest.json` no longer present in `tools/`).

## Re-run
```
python tools/harvest_akg_galleries.py            # re-scan OneDrive + re-check site (cached under tools/_cache/akg/)
python tools/reconcile_akg_galleries.py --report  # dry run, prints the match table
python tools/reconcile_akg_galleries.py --apply   # writes images/ + slabs.json
```
""")
print("wrote", report_path)
