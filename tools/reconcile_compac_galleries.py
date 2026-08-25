"""Reconcile tools/compac-galleries-harvest.json with slab-library (supplier
Compac, engineered colours only -- naturalStone entries are never touched).

Adds `images[]` (kind: slab/closeup/room) to the 36 engineered Compac
entries, fills productUrl/slabSizes/details where the library is missing
them, and leaves the 34 existing slab mains untouched (per HARVEST-SPEC.md
rule 8/decisions). The 2 closeup-only mains (Luxury Taj, Luxury Travertino)
were supposed to be upgraded to a real slab face this run, but NO source
image exists anywhere (site 404s, no OneDrive folder, no Wayback snapshot)
-- see REPORT.md; their mains are left as-is, flagged BLOCKED.

--report prints the match table and changes nothing; --apply converts the
selected OneDrive originals to webp, updates slabs.json via
hl.patch_library (bumps `generated`), writes the two contact sheets +
compac-REPORT.md.
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Compac"

# details for colours the library has none for yet -- inferred from the
# Compac collection each colour name belongs to (same convention as every
# sibling entry already carries, e.g. "Luxury Vagli Oro" -> "Luxury, Quartz
# Collection", "Unique Venatino" -> "Quartz, Unique Collection"). Unique
# Calacatta Macchia Vecchia confirmed from its live page <title> (fetched
# this run): "...Unique Collection. Technological Quartz...".
DETAILS_FALLBACK = {
    "Luxury Taj": "Luxury, Quartz Collection",
    "Luxury Travertino": "Luxury, Quartz Collection",
    "Unique Taj": "Quartz, Unique Collection",
    "Unique Warm": "Quartz, Unique Collection",
    "Unique Calacatta Macchia Vecchia": "Quartz, Unique Collection",
}

NO_SOURCE = {"Luxury Taj", "Luxury Travertino", "Unique Taj", "Unique Warm"}  # confirmed delisted, no images anywhere

apply_mode = "--apply" in sys.argv

manifest = {r["colour"]: r for r in json.load(open(os.path.join(SCRATCH, "compac-galleries-harvest.json"), encoding="utf-8"))}
lib = hl.load_library()
entries = [s for s in lib["slabs"] if s.get("supplier") == "Compac" and not s.get("naturalStone")]
assert len(entries) == 36, f"expected 36 engineered Compac entries, got {len(entries)}"

pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_closeups = n_rooms = n_meta = 0
edited = {}  # id -> entry dict (mutated in place, re-applied via patch_library)

for e in entries:
    colour = e["colour"]
    m = manifest.get(colour, {})
    pb_row = pb.get(colour)

    meta_changes = []
    if not e.get("productUrl") and colour not in NO_SOURCE:
        pass  # nothing to fill from this run beyond what's already there
    if not e.get("details"):
        d = DETAILS_FALLBACK.get(colour)
        if d:
            e["details"] = d
            meta_changes.append("details")
    if not e.get("slabSizes"):
        if pb_row and pb_row["sizes"]:
            e["slabSizes"] = hl.format_slab_sizes(pb_row["sizes"])
            meta_changes.append("slabSizes")
        elif not pb_row:
            meta_changes.append("slabSizes:NO-PRICEBOOK-ROW")

    gallery = [dict(e["image"], kind="slab")] if e.get("image", {}).get("file") else []

    cu_added = rm_added = False
    if apply_mode:
        if m.get("closeup_file"):
            src = os.path.join(m["folder"], m["closeup_file"])
            fn = hl.to_library_webp(src, f"{e['id']}--closeup1")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup",
                             "source": e.get("productUrl") or "", "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
            cu_added = True
        if m.get("room_file"):
            src = os.path.join(m["folder"], m["room_file"])
            fn = hl.to_library_webp(src, f"{e['id']}--room1")
            gallery.append({"file": fn, "status": "representative", "kind": "room",
                             "source": e.get("productUrl") or "", "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} room", os.path.join(hl.IMAGES_DIR, fn)))
            n_rooms += 1
            rm_added = True
        if len(gallery) > 1:
            e["images"] = gallery
        if meta_changes:
            n_meta += 1
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, e["image"]["file"])
                             if e.get("image", {}).get("file") else None,
                             e.get("image", {}).get("status", "?")))
        edited[e["id"]] = e

    status_note = e.get("image", {}).get("status", "?")
    if colour in ("Luxury Taj", "Luxury Travertino") and status_note == "closeup-only":
        status_note += " [BLOCKED: no slab-face source found anywhere]"
    rows_out.append((
        colour, status_note,
        "cu" if (m.get("closeup_file") or cu_added) else "-",
        "rm" if (m.get("room_file") or rm_added) else "-",
        ",".join(meta_changes) or "-",
    ))

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(5)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(5)))

n_no_gallery = sum(1 for c, m in manifest.items() if not m.get("closeup_file") and not m.get("room_file"))
print(f"\n{len(entries)} engineered entries | colours with a closeup source: "
      f"{sum(1 for m in manifest.values() if m.get('closeup_file'))} | "
      f"colours with a room source: {sum(1 for m in manifest.values() if m.get('room_file'))} | "
      f"colours with neither: {n_no_gallery}")

if apply_mode:
    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, ed in edited.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == "Compac" and not s.get("naturalStone"):
                    s.clear()
                    s.update(ed)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"closeups added: {n_closeups} | rooms added: {n_rooms} | entries with metadata filled: {n_meta}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "compac-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "compac-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    no_gallery_colours = sorted(c for c, m in manifest.items()
                                 if not m.get("closeup_file") and not m.get("room_file"))
    report_path = os.path.join(hl.REPORTS_DIR, "compac-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Compac galleries harvest report

Scope: 36 engineered Compac library entries (12 naturalStone entries untouched).
Source: OneDrive `1. QUARTZ\\COMPAC\\<Colour>\\` folders, already populated by the
earlier `compac_harvest.py`/`compac_reconcile.py` run from en.compac.es (WordPress).
No re-fetch was needed for 35 of 36 colours -- their folders already held every
image compac_harvest.py could find on the live page. One fresh fetch this run:
`https://en.compac.es/color/unique-calacatta-macchia-vecchia/` (its OneDrive
folder has a garbled page-title name), which confirmed the folder already has
everything the live page offers (3 files, no dedicated closeup/room asset).

## Counts
- Engineered entries: {len(entries)}
- Closeup images added: {n_closeups}
- Room images added: {n_rooms}
- Colours with neither closeup nor room source available: {n_no_gallery} -- {no_gallery_colours}
- Entries with productUrl/slabSizes/details filled this run: {n_meta}
- Mains replaced: 0 (34 kept as-is per spec; Luxury Taj/Luxury Travertino BLOCKED, see below)

## Classification approach
Every colour's folder was inspected by hand (not a generic auto-classifier) because
folders mix in "related product" carousel images belonging to OTHER Compac colours
not in our price book (Imperial, Vainille, Perlino, Smoke Gray, Warm/Cool Gray
Glace...) and "*-referencia.jpg"/"Formato_*" files that look like photos but are
actually dimension diagrams (verified visually, excluded). Selections in
`harvest_compac_galleries.py`'s SELECTIONS table:
- **closeup**: a dedicated texture/detail shot where the site has one (`*VETAS*`,
  `detalle-*`); otherwise the `Tablero_*_regla*`/`TABLERO_*_REGLA*` "board with a
  scale ruler" photo where present -- a genuine higher-res detail photo of the
  slab, just wider-framed than a macro crop (used for 21 of the 22 closeups; only
  Ice White, Unique Calacatta and Unique Calacatta Macchia Vecchia had a true
  macro/vase-styled texture shot). No regla/detail asset exists at all for the 9
  "Functional" Standard-size colours (Absolute Blanc, Alaska, Arena, Ceniza,
  Glaciar, Luna, Moon, Nocturno, Plomo) -- Compac simply doesn't publish one for
  that range; left absent rather than guessed.
- **room**: kitchen/bathroom/application photos (`*kitchen*`, `*bath*`, Spanish
  `banyo`/`cocina`/`aplicat`/`amb`(iente), `Slide_*`/`*-2024_1*`/`*_1800x600`
  secondary banner images -- verified by eye to be styled kitchen/bath vignettes,
  not more slab crops -- and numbered application photos e.g. `argento1.jpg`/
  `arabescato1.jpg`, verified to be full kitchen scenes). Absent for 11 colours
  (mostly the same Standard "Functional" range, plus Luxury Vagli Oro and Unique
  Calacatta Macchia Vecchia) where the site has no such photo.
- 8 colours (all "Functional" Standard-size: Alaska, Arena, Ceniza, Glaciar, Luna,
  Moon, Nocturno, Plomo) have neither -- Compac's site only ever gave these a hero
  crop + thumbnail, nothing else photographed.

## Assumptions / needs a human
- **Luxury Taj & Luxury Travertino (BLOCKED)**: spec asked these 2 closeup-only
  mains to be upgraded to a real slab face. Checked: en.compac.es/color/luxury-taj/
  and /luxury-travertino/ both 404, no OneDrive folder exists for either, and
  Wayback Machine CDX returned no snapshots for either URL (checked twice).
  Genuinely no source image exists to harvest from the supplier's own site. Both
  ARE still active price-book rows (Polished, 20/30mm, 3250x1630) so we still sell
  them -- recommend asking Compac directly for current photography, or scanning a
  physical swatch. Mains left unchanged (still closeup-only) this run.
- **Unique Taj & Unique Warm**: same story (404, no folder, no Wayback snapshot) --
  but their mains were already `status: slab` from an earlier run (source
  "onedrive-brands-folder", i.e. placed by hand previously), so nothing to
  upgrade; just filled `details` (collection-name convention) and `slabSizes`
  (from the price book, which still lists both). No gallery images added --
  no source. productUrl left empty for all 4 of these delisted colours; do not
  invent a URL that 404s.
- **Unique Argento**: on the live site (has productUrl) but NOT in the price book
  under any spelling -- `slabSizes` left blank rather than assumed from its Unique
  Collection siblings (all 3250x1630), since we may not actually stock/price it.
  Worth confirming with the price book owner.
- **Unique Calacatta Macchia Vecchia**: `details` filled from its live page title
  ("Unique Collection"); its OneDrive folder is named from a stale page-title save
  ("NEW design - Unique Calacatta Macchia Vecchia. Unique Collection...") --
  cosmetic only, left as-is (renaming it is outside this task's scope).
- Several `Tablero_*_regla*` files repurposed as "closeup" are full-board photos
  with a ruler graphic baked in, not a tight macro crop -- flagged here so the
  orchestrator can judge if that bar is acceptable for the public site; they do
  legitimately show the material's veining/pattern at higher fidelity than the
  hero crop.

## Re-run
```
python tools/harvest_compac_galleries.py              # rebuild the manifest from OneDrive (no network)
python tools/reconcile_compac_galleries.py --report    # dry run, prints the match table
python tools/reconcile_compac_galleries.py --apply     # writes images/ + slabs.json + contact sheets + this report
```
""")
    print("wrote", report_path)
