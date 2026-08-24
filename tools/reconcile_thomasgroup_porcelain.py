"""Reconcile tools/thomasgroup-porcelain-harvest.json with slab-library.
Supplier "Thomas Group (Surfaces Collection)", Material "Porcelain" (Atlas
Plan). All 76 price-book colours belong to us (this script only ever
touches its own `thomas-group-surfaces-collection--*` ids) -- re-running
UPDATES an existing entry in place (fresh image/gallery/details/slabSizes
from the current manifest) rather than skipping it, so a harvest-logic fix
can be repaired with a plain re-run. --report prints the plan and changes
nothing; --apply downloads originals, writes webps, and applies via
harvest_lib.patch_library (bumps `generated`).

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
    status = ("UPDATE w/ slab" if slab_url else "UPDATE no-image") if already else \
             ("NEW w/ slab" if slab_url else "NEW no-image")
    rows_out.append((colour, eid, status, rec["source"] if rec else "-", f"{n_cu}cu/{n_rm}rm",
                      hl.format_slab_sizes(pbinfo["sizes"])))

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
    plan.append((colour, entry, rec, already))

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))

n_new_slab = sum(1 for _, e, s, already in plan if not already and s and s.get("slab"))
n_upd = sum(1 for _, e, s, already in plan if already)
n_noimg = sum(1 for _, e, s, already in plan if not (s and s.get("slab")))
print(f"\nprice-book colours: {len(por_colours)} | to add: {len(plan) - n_upd} | to update (repair pass): {n_upd} "
      f"| no image found: {n_noimg}")

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


n_added = n_updated = n_closeups = n_rooms = n_dl_fail = 0
new_entries = []
updated_entries = []  # (id, entry) to splice into existing lib['slabs'] positions

for colour, entry, rec, already in plan:
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

    if already:
        updated_entries.append(entry)
        n_updated += 1
    else:
        new_entries.append(entry)
        n_added += 1


def apply(lib_):
    by_id = {u["id"]: u for u in updated_entries}
    for i, s in enumerate(lib_["slabs"]):
        if s["id"] in by_id:
            lib_["slabs"][i] = by_id[s["id"]]
    lib_["slabs"].extend(new_entries)
    return {"added": len(new_entries), "updated": len(updated_entries)}


result = hl.patch_library(apply, supplier=SUPPLIER)
print(f"\nAPPLIED via patch_library: {result}")
print(f"entries added: {n_added} | entries updated (repair pass): {n_updated} | "
      f"mains downloaded: {sum(1 for _,p,_ in mains_sheet if p)} | "
      f"main download failures: {n_dl_fail} | closeups: {n_closeups} | rooms: {n_rooms}")

m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "thomasgroup-porcelain-mains.png"), cols=8)
m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "thomasgroup-porcelain-galleries.png"), cols=8)
print("contact sheets:", m1, m2)

report_path = os.path.join(hl.REPORTS_DIR, "thomasgroup-porcelain-REPORT.md")
no_image_colours = [c for c, e, r, a in plan if not (r and r.get("slab"))]
n_resolved_atlas = sum(1 for r in manifest if r.get("source") == "atlasplan.com")
n_resolved_tsc = sum(1 for r in manifest if r.get("source") == "thesurfacecollection.co.uk")
n_not_found = sum(1 for r in manifest if not r.get("source"))
not_found_names = sorted(r["colour"] for r in manifest if not r.get("source"))
n_closeup_only = sum(1 for _, e, r, a in plan if r and r.get("slab_is_closeup"))
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"""# Thomas Group (Surfaces Collection) -- Porcelain (Atlas Plan) harvest report

Supplier string: `{SUPPLIER}` | Material: Porcelain | Brand: Atlas Plan (an Atlas
Concorde brand), sold in the UK exclusively via Thomas Group / The Surface
Collection. All 76 price-book colours were ABSENT from the library before the
first run of this script; this pass touched {n_added + n_updated} of them
({n_added} newly added, {n_updated} updated in place -- a repair pass fixing
a slab/room-photo misclassification bug found via the mains contact sheet
after the first apply, see Assumptions).

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
- Library entries updated in place this pass (repair, see Assumptions): {n_updated}
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
- Slab-photo classification is a two-pass, order-independent scan: pass 1
  looks for a filename carrying a printed slab-size token (`162x324`,
  `160x320` etc) without "bookmatch" -- that is always the main `slab`;
  `-bookmatch` filenames are the `closeup` crop (or, for the 2 colours with
  no non-bookmatch size-tagged photo at all -- Calacatta Extra, Statuario
  Supremo -- the first bookmatch crop is promoted to `slab` with
  `image.status: "closeup-only"`). Pass 2 classifies everything left over as
  `closeup`/`room` by weaker filename/alt hints. **Fix (this repair pass):**
  the first apply used a single order-dependent pass whose fallback trusted
  `harvest_lib.classify_kind()`'s bare-word-"slab" filename match -- which
  wrongly picked numbered lifestyle photos as the main slab for a few
  colours (e.g. Appennino's `01-appennino-...-slab-atlas-plan` is actually a
  kitchen photo) whenever they preceded the real size-tagged photo in the
  page's DOM order. Caught via the mains contact sheet, not the numeric
  counts (all of which looked normal) -- **always eyeball
  `thomasgroup-porcelain-mains.png` before trusting a harvest, counts alone
  don't catch a wrong-but-present image.** The two-pass rewrite here fixes
  it for every colour, not just the ones spotted by eye.
- `{{slug}}-warehouse-...` generic photos are always skipped.
- Closeup/room gallery images use the raw CDN url straight off the live page
  (a `-clamp_W_H_Q`/`-clip_W_H_Q` responsive variant, 960-1920px -- already
  exceeding the library's max_w=1600 webp target, and guaranteed to exist
  since it's literally referenced in the page HTML). Only the main slab photo
  gets a quick HEAD-check upgrade attempt to its unsuffixed "true original"
  filename (succeeds for most colours; falls back to the same raw CDN url,
  no retry cost, when it 404s -- e.g. Appennino's original 404s but its CDN
  variant is still full quality).

## Re-run
```
python tools/harvest_thomasgroup_porcelain.py                # re-scrape (cached; delete tools/_cache/thomasgroup to force)
python tools/reconcile_thomasgroup_porcelain.py --report      # dry run, prints the add-plan
python tools/reconcile_thomasgroup_porcelain.py --apply       # writes images/ + slabs.json
```
""")
print("wrote", report_path)
