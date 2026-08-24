"""Reconcile tools/thomasgroup-porcelain-harvest.json with slab-library.
Supplier "Thomas Group (Surfaces Collection)", Material "Porcelain" (Atlas
Plan). Every one of the 76 price-book colours is NEW (none exist in the
library yet) -- this always adds, never matches an existing entry. --report
prints the plan and changes nothing; --apply downloads originals, writes
webps, and applies via harvest_lib.patch_library (bumps `generated`).

Rules (HARVEST-SPEC.md + orchestrator Decisions 2026-08-24):
  - entry id = thomas-group-surfaces-collection--{colour-slug}
  - supplier = "Thomas Group (Surfaces Collection)" exactly; material = Porcelain
  - thicknesses/finishes/slabSizes come from the PRICE BOOK (naming/size
    authority); images + one-line blurb come from the site.
  - details = "Atlas Plan · <Look> · <finishes> [-- <site description>]"
  - 3 colours (Carrara Pure, Grigio Intenso, Kone Grey) have no confirmed
    image source anywhere (atlasplan.com direct-slug 404s/redirects to an
    unrelated product; absent from thesurfacecollection.co.uk's Atlas Plan
    catalogue too) -- still added (price book confirms them), image status
    "missing", productUrl left blank.
"""
import csv
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Thomas Group (Surfaces Collection)"
MATERIAL = "Porcelain"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED", "THOMAS GROUP (Atlas Plan)")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "thomasgroup-porcelain-harvest.json"), encoding="utf-8"))
manifest_by_colour = {m["colour"]: m for m in manifest}

pb = hl.load_pricebook(SUPPLIER)
pb_por = {c: info for c, info in pb.items()}  # load_pricebook already spans all materials for this supplier

# section ("Atlas Plan - Marble Look" -> "Marble Look") per colour, straight from the CSV
rows = list(csv.DictReader(open(hl.PRICEBOOK_CSV, encoding="utf-8-sig")))
section_by_colour = {}
for r in rows:
    if r.get("Supplier", "") == SUPPLIER and r.get("Material", "") == MATERIAL:
        section_by_colour[r["Colour"].strip()] = r.get("Price List Section", "").replace("Atlas Plan - ", "").strip()

por_colours = sorted(c for c in pb_por if c in section_by_colour)

lib = hl.load_library()
existing_ids = {s["id"] for s in lib["slabs"]}

mains_sheet, gallery_sheet = [], []
rows_out = []
plan = []  # (colour, entry_dict, slab_url, closeup_urls, room_urls) built in --report too


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


for colour in por_colours:
    pbinfo = pb_por[colour]
    rec = manifest_by_colour.get(colour)
    eid = f"thomas-group-surfaces-collection--{slugify(colour)}"
    look = section_by_colour.get(colour, "")
    finishes = ", ".join(sorted(pbinfo["finishes"])) if pbinfo["finishes"] else ""
    blurb = f"Atlas Plan · {look}" + (f" · {finishes}" if finishes else "")
    if rec and rec.get("description"):
        blurb += f" — {rec['description']}"

    already = eid in existing_ids
    slab_url = rec["slab"] if rec else None
    n_cu = len(rec["closeups"]) if rec else 0
    n_rm = len(rec["rooms"]) if rec else 0
    status = "SKIP (already in library!)" if already else ("NEW w/ slab" if slab_url else "NEW no-image")
    rows_out.append((colour, eid, status, rec["source"] if rec else "-", f"{n_cu}cu/{n_rm}rm",
                      hl.format_slab_sizes(pbinfo["sizes"])))

    if already:
        continue

    entry = {
        "id": eid, "supplier": SUPPLIER, "colour": colour, "material": MATERIAL,
        "naturalStone": False, "illustrationOnly": False,
        "thicknesses": sorted(pbinfo["thicknesses"]),
        "productUrl": (rec["url"] if rec else "") or "",
        "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""},
    }
    if pbinfo["sizes"]:
        entry["slabSizes"] = hl.format_slab_sizes(pbinfo["sizes"])
    entry["details"] = blurb[:400]
    plan.append((colour, entry, rec))

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))

n_new_slab = sum(1 for _, _, s in plan if s and s.get("slab"))
n_new_noimg = sum(1 for _, _, s in plan if not (s and s.get("slab")))
print(f"\nprice-book colours: {len(por_colours)} | to add: {len(plan)} "
      f"(with slab image: {n_new_slab}, no image found: {n_new_noimg}) | "
      f"already in library (skipped): {sum(1 for r in rows_out if 'SKIP' in r[2])}")

if not apply_mode:
    print("\n--report only, nothing written. Re-run with --apply to write images/ + slabs.json.")
    sys.exit(0)


def dl(url, colour, tag):
    """Manifest URLs are already known-good (raw CDN urls straight off the
    live page, or a HEAD-verified "true original") -- a plain bounded fetch
    is enough, no need for fetch_best's slow original-guessing fallback."""
    if not url:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data = hl.fetch(url, supplier="thomasgroup", cache_key=f"img-{colour}-{tag}-{fn}"[:150],
                         binary=True, tries=2, delay=8)
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} {tag} <- {url}: {e}")
        return None
    return hl.save_original(data, DEST_ROOT, colour, fn)


n_added = n_closeups = n_rooms = n_dl_fail = 0
new_entries = []

for colour, entry, rec in plan:
    if rec and rec.get("slab"):
        p = dl(rec["slab"], colour, "slab")
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            img_status = "closeup-only" if rec.get("slab_is_closeup") else "slab"
            entry["image"] = {"file": fn, "status": img_status, "source": rec["url"], "borrowedFrom": ""}
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn),
                                 rec["source"] + (" (bookmatch)" if rec.get("slab_is_closeup") else "")))
        else:
            n_dl_fail += 1
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    else:
        mains_sheet.append((colour, None, "no source"))

    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    if rec:
        ci = ri = 0
        for u in rec.get("closeups", []):
            p = dl(u, colour, f"cu{ci+1}")
            if not p or not os.path.exists(p):
                continue
            ci += 1
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": rec["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
        for u in rec.get("rooms", []):
            p = dl(u, colour, f"room{ri+1}")
            if not p or not os.path.exists(p):
                continue
            ri += 1
            fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
            gallery.append({"file": fn, "status": "representative", "kind": "room", "source": rec["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
            n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

    new_entries.append(entry)
    n_added += 1


def apply(lib_):
    lib_["slabs"].extend(new_entries)
    return {"added": len(new_entries)}


result = hl.patch_library(apply, supplier=SUPPLIER)
print(f"\nAPPLIED via patch_library: {result}")
print(f"entries added: {n_added} | mains downloaded: {sum(1 for _,p,_ in mains_sheet if p)} | "
      f"main download failures: {n_dl_fail} | closeups: {n_closeups} | rooms: {n_rooms}")

m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "thomasgroup-porcelain-mains.png"), cols=8)
m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "thomasgroup-porcelain-galleries.png"), cols=8)
print("contact sheets:", m1, m2)

report_path = os.path.join(hl.REPORTS_DIR, "thomasgroup-porcelain-REPORT.md")
no_image_colours = [c for c, e, r in plan if not (r and r.get("slab"))]
n_resolved_atlas = sum(1 for r in manifest if r.get("source") == "atlasplan.com")
n_resolved_tsc = sum(1 for r in manifest if r.get("source") == "thesurfacecollection.co.uk")
n_not_found = sum(1 for r in manifest if not r.get("source"))
not_found_names = sorted(r["colour"] for r in manifest if not r.get("source"))
n_closeup_only = sum(1 for _, e, r in plan if r and r.get("slab_is_closeup"))
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"""# Thomas Group (Surfaces Collection) -- Porcelain (Atlas Plan) harvest report

Supplier string: `{SUPPLIER}` | Material: Porcelain | Brand: Atlas Plan (an Atlas
Concorde brand), sold in the UK exclusively via Thomas Group / The Surface
Collection. Every one of these 76 price-book colours was ABSENT from the
library before this run -- all {n_added} are new entries.

Primary source: atlasplan.com per-colour pages (`/en/large-format-porcelain-slabs/{{slug}}/`,
storage.atlasplan.com CDN, curl OK, no bot protection). Colour->slug mapping
was hand-resolved against atlasplan.com's own `/en/large-format-porcelain-slabs/`
index page, which lists every currently-live product slug (66/76 resolved this
way). 7 colours (Calacatta Royal, Concrete Grey, Dolmen Pro Grigio, Kone
Gypsum, Nero Zimbabwe, Statuario Select, White Terrazzo) have no live
atlasplan.com page (direct slug guesses either 404 or soft-redirect to an
unrelated product) but ARE confirmed stocked on thesurfacecollection.co.uk's
single `/products/atlas-plan/` catalogue page, used as fallback (slab photo
only, `lib/photos/{{code}}.jpg` -- lower resolution than atlasplan.com's own
photography, no closeup/room shots available that way).

3 colours (Carrara Pure, Grigio Intenso, Kone Grey) were NOT resolved on
either site: atlasplan.com's own site search/direct-slug attempts
(carrara-pure, grigio-intenso, kone-grey, kone-gray) all soft-redirect to an
unrelated product page (Bianco Dolomite / Grey Stone / Kone Mix / 404
respectively), and a full-text search of the TSC Atlas Plan catalogue page
found no mention of any of the three. A web search only surfaced third-party
distributor pages (e.g. Gramaco) referencing them with no working
atlasplan.com URL. These 3 are still added as price-book-confirmed library
entries (`image.status: "missing"`, no `productUrl`) since the price book is
the naming authority -- flagging here for a possible manual/browser-driven
follow-up later.

Thicknesses, finishes and `slabSizes` all come from the price book (rounded
mm slab sizes, e.g. `12mm: 3200x1600`), not the site's printed cm sizes
(`162x324` etc) -- consistent with the price book being the sizing authority
per HARVEST-SPEC.md. `details` = `"Atlas Plan · <Look> · <finishes>"` (Look =
the price-book "Price List Section" with the "Atlas Plan - " prefix
stripped), plus the site's one-line meta description where available.

## Counts
- Price-book Porcelain colours (Thomas Group (Surfaces Collection)): {len(por_colours)}
- Resolved to a live atlasplan.com product page: {n_resolved_atlas}
- Resolved via thesurfacecollection.co.uk fallback (slab photo only): {n_resolved_tsc}
- Not found on either site: {n_not_found} -- {not_found_names}
- Library entries added: {n_added}
- Mains (slab) downloaded: {sum(1 for _,p,_ in mains_sheet if p)}
- Main download failures: {n_dl_fail}
- Mains sourced from a bookmatch crop (no separate full-slab photo existed; `image.status: "closeup-only"`): {n_closeup_only}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Entries with no image at all (status "missing"): {len(no_image_colours)} -- {no_image_colours}

## Assumptions
- Duplicate-looking price-book colours that are genuinely separate rows
  (`Calacatta Imperial` / `Calacatta Imperiale`, `Taj Mahal` / `Taj Mahal
  (Atlas Plan)`, `Travertine Sand` / `Travertino Sand`) each get their OWN
  library entry pointing at the same underlying atlasplan.com product page --
  the price book, not the site, is the naming authority, and these are kept
  as distinct SKUs/rows rather than merged.
- atlasplan.com's numbered lifestyle photos (`01-...`, `02-...` etc) are
  classified as `room`; the `-bookmatch` slab crop and any filename containing
  "detail"/"texture"/"surface" as `closeup`; the un-suffixed `atlas-plan-epic-
  {{slug}}-{{finish}}-{{size}}-{{thickness}}mm` file as the main `slab`; a
  `{{slug}}-warehouse-...` generic photo is always skipped.
- Images are fetched at their true original resolution by stripping the
  responsive `-clamp_W_H_Q`/`-clip_W_H_Q` CDN suffix (verified the unsuffixed
  original is directly fetchable on storage.atlasplan.com).

## Re-run
```
python tools/harvest_thomasgroup_porcelain.py                # re-scrape (cached; delete tools/_cache/thomasgroup to force)
python tools/reconcile_thomasgroup_porcelain.py --report      # dry run, prints the add-plan
python tools/reconcile_thomasgroup_porcelain.py --apply       # writes images/ + slabs.json
```
""")
print("wrote", report_path)
