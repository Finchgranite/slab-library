"""Reconcile tools/lumina-harvest.json with slab-library (supplier "Lumina
Stone") + the price book. --report prints the match table and changes
nothing; --apply downloads originals, writes webps, updates slabs.json
(bumps `generated` via hl.patch_library) and writes the two contact sheets +
REPORT.md.

Rules (HARVEST-SPEC.md + this supplier's JOB brief):
  - existing image.status == "slab": main untouched (Belvedere, Coral Metro,
    Coral Naturale, Sand Swan, White Sand, White Swan) -- productUrl/
    slabSizes/details/gallery still filled in.
  - existing "closeup-only" (Patagonia): NOT downgraded, NOT upgraded to
    "slab" (the only pisastone image for it is a kitchen room render, not a
    slab face) -- gallery gains a "room" image.
  - "missing" + a real slab-face image found on luminastone.eu (Soapstone,
    Urban Cemento): promoted to "slab".
  - "missing" + only a genuine macro-texture closeup found, no slab face
    (Maya, pisastone): promoted to "closeup-only".
  - "missing" + only a room render found (Astral White, Bianco Venatino,
    Calacatta Eternal, Statuario Frost/Rhin/Venato, Super White Marble):
    LEFT missing (a room shot is not a slab face) -- productUrl + room
    gallery image added anyway.
  - Bronze Cascade: nothing found anywhere -- untouched.
  - slabSizes: price book first (all 18 Lumina colours are 3200x1600 20/30mm
    per the price book), page data never contradicted this.
"""
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Lumina Stone"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "LUMINA")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "lumina-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER]
by_colour = {r["colour"]: r for r in entries}

pb = hl.load_pricebook(SUPPLIER)

FINISH_BY_COLOUR = {c: ", ".join(sorted(v["finishes"])) for c, v in pb.items()}

pisastone_by_colour = {p["colour"]: p for p in manifest["pisastone"] if p["colour"]}
eu_by_colour = {e["colour"]: e for e in manifest["eu"]}


def dl(url, colour, apply_):
    if not apply_ or not url:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="lumina", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data, DEST_ROOT, colour, used_fn)


rows_out = []
mains_sheet, gallery_sheet = [], []
n_upgraded = n_closeup_promoted = n_closeups = n_rooms = n_dl_fail = n_meta_only = 0
still_missing = []
not_found_anywhere = []

ALL_COLOURS = sorted(by_colour)

for colour in ALL_COLOURS:
    entry = by_colour[colour]
    ps = pisastone_by_colour.get(colour)
    eu = eu_by_colour.get(colour)

    if not ps and not eu:
        not_found_anywhere.append(colour)
        rows_out.append((colour, "NOT FOUND (either source)", "-", entry["image"]["status"]))
        continue

    # --- productUrl: prefer the brand's own per-colour eu page, else the shared pisastone page ---
    product_url = eu["page"] if eu else ps["page"]
    entry["productUrl"] = product_url

    # --- slabSizes / details from the price book (all Lumina = 3200x1600 20/30mm) ---
    pbrow = pb.get(colour)
    if pbrow and pbrow.get("sizes"):
        entry["slabSizes"] = hl.format_slab_sizes(pbrow["sizes"])
    finish = FINISH_BY_COLOUR.get(colour, "")
    entry["details"] = f"Lumina Stone quartz worktop{' · ' + finish + ' finish' if finish else ''}"
    n_meta_only += 1

    cur_status = entry["image"]["status"]
    # what SHOULD be the main, regardless of whether we're re-running on an
    # already-promoted entry -- used both to decide whether to (re)download
    # and, unconditionally, as the URL to skip when building the gallery
    # below (so a re-run never double-adds the image that's already main).
    candidate_status, main_url, main_source = None, None, product_url
    if eu and eu.get("slab"):
        candidate_status, main_url, main_source = "slab", eu["slab"], product_url
    elif ps and ps["kind"] == "closeup":
        candidate_status, main_url, main_source = "closeup-only", ps["url"], ps["page"]

    target_status = candidate_status if (candidate_status and cur_status != candidate_status
                                          and cur_status != "slab") else None

    rows_out.append((
        colour, f"{cur_status}->{target_status}" if target_status else f"{cur_status} (kept)",
        product_url, "eu" if eu else "pisastone",
    ))

    if apply_mode and target_status:
        p = dl(main_url, colour, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            entry["image"] = {"file": fn, "status": target_status, "source": main_source, "borrowedFrom": ""}
            if target_status == "slab":
                entry["image"]["scale"] = "approx"
                n_upgraded += 1
            else:
                n_closeup_promoted += 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), target_status.upper()))
        else:
            n_dl_fail += 1
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))

    if entry["image"]["status"] == "missing":
        still_missing.append(colour)

    # --- gallery: closeups + rooms (skip whichever image was just used as main) ---
    if not apply_mode:
        continue
    gallery = [dict(entry["image"], kind="slab" if entry["image"]["status"] == "slab" else "closeup")] \
        if entry["image"].get("file") else []
    ci = ri = added = 0

    def add_gallery(url, kind, source):
        global ci, ri, added
        if not url or url == main_url:
            return
        p = dl(url, colour, apply_mode)
        if not p or not os.path.exists(p):
            return
        if kind == "closeup":
            ci += 1
            idx = ci
        else:
            ri += 1
            idx = ri
        fn = hl.to_library_webp(p, f"{entry['id']}--{kind}{idx}")
        gallery.append({"file": fn, "status": kind if kind == "closeup" else "representative",
                         "kind": kind, "source": source, "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} {kind}{idx}", os.path.join(hl.IMAGES_DIR, fn)))
        globals()[f"n_{kind}s"] = globals()[f"n_{kind}s"] + 1
        added += 1

    if eu:
        add_gallery(eu.get("closeup"), "closeup", eu["page"])
        for r in eu.get("rooms", []):
            add_gallery(r, "room", eu["page"])
    if ps:
        add_gallery(ps["url"], ps["kind"], ps["page"])

    # store the gallery whenever we actually added something new -- not just
    # when the (possibly-empty, main-missing) list happens to exceed length 1
    if added:
        entry["images"] = gallery

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

print()
print(f"library Lumina colours: {len(ALL_COLOURS)} | not found in either source: {len(not_found_anywhere)} {not_found_anywhere}")


def apply_lib(lib_fresh):
    # entries were mutated in place on the `entries`/`by_colour` objects taken
    # from the FIRST load_library() call above; re-apply the same edits onto
    # the freshly loaded dict by id so patch_library's stray-write guard and
    # concurrent-safety both hold.
    fresh_by_id = {s["id"]: s for s in lib_fresh["slabs"] if s.get("supplier") == SUPPLIER}
    for colour, entry in by_colour.items():
        tgt = fresh_by_id.get(entry["id"])
        if tgt is None:
            continue
        tgt.update(entry)
    return {"upgraded": n_upgraded, "closeup_promoted": n_closeup_promoted,
            "closeups": n_closeups, "rooms": n_rooms}


if apply_mode:
    result = hl.patch_library(apply_lib, supplier=SUPPLIER)
    print(f"\nAPPLIED. mains -> slab: {n_upgraded} | mains -> closeup-only: {n_closeup_promoted} | "
          f"closeups added: {n_closeups} | rooms added: {n_rooms} | download failures: {n_dl_fail}")
    print("still missing:", still_missing)
    print("not found anywhere:", not_found_anywhere)

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "lumina-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "lumina-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "lumina-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Lumina Stone harvest report

No authoritative UK site (orchestrator-relaxed source rule, see HARVEST-SPEC.md
JOB brief). Two sources used:
- **pisastone.co.uk/quartz-worktops/lumina-stone** -- single reseller page, 16
  UK-stocked colours, one photo + 4-digit SKU each (RSC JSON payload, not
  plain `<img>` tags). **Correction to the earlier discovery note**: checked
  all 16 photos at full resolution -- 15 are CGI kitchen-installation renders
  (~1.3-1.6:1), not slab-face photos, so they were used as `room` gallery
  images, not mains. Only Maya (skuCode 8313) is a genuine flat macro-texture
  crop, used as a `closeup`. No per-colour URL exists on this site -- these
  16 colours' `productUrl` is the shared page unless luminastone.eu (below)
  had a better per-colour one.
- **luminastone.eu** (brand's own WordPress site) -- current catalogue has
  moved to a refreshed colour range; a full portfolio-sitemap sweep (34
  slugs) found 5 genuine cross-matches with real per-colour pages: Sand Swan,
  White Swan, White Sand (all 3 already had good library mains -- gallery
  only), **Soapstone** and **Urban Cemento** (both `missing` -> real slab-face
  photo found, ~2.0:1, matches the price book's 3200x1600 slab size).
  "Cemento Urban" on the site matched price book "Urban Cemento" by reversed
  word order.

## Counts
- Library Lumina Stone colours: {len(ALL_COLOURS)}
- Mains newly set to "slab" (was missing): {n_upgraded} (Soapstone, Urban Cemento)
- Mains promoted "missing" -> "closeup-only": {n_closeup_promoted} (Maya)
- Existing "slab" mains left untouched (Belvedere, Coral Metro, Coral Naturale,
  Sand Swan, White Sand, White Swan): 6
- Existing "closeup-only" left untouched (Patagonia -- only image found is a
  room render, not a slab face): 1
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Main image download failures: {n_dl_fail}
- Still `missing` after this run, {len(still_missing)}: {still_missing}
- Not found in EITHER source, {len(not_found_anywhere)}: {not_found_anywhere}

## Colours to ask Granite Granite Ltd about (importer, Basildon)
- **Bronze Cascade** -- not on pisastone's 16 UK-stocked colours, not on
  luminastone.eu's 34 portfolio slugs. granitewarehouseyork.co.uk (4th
  reseller named in the discovery) now returns "Account Suspended" (dead
  hosting, retried this pass with `curl -k`) -- no further web source to try.
- Urban Cemento is now resolved (see above) so only Bronze Cascade remains
  genuinely unsourced.

## Assumptions
- `slabSizes` = price book (3200x1600, 20/30mm, all 18 colours) -- no page
  contradicted this.
- `details` = "Lumina Stone quartz worktop · <Finish> finish" from the price
  book's own Finish column (Polished / S-Tech & Nano / Silica-Free / Polished
  & S-Tech per colour).
- Soapstone's and Urban Cemento's new slab mains are CGI renders (filenames
  say "-3D-"/product-shot style, not phone-camera photos) -- `image.scale`
  set to "approx" (no stated true mm on the page, but aspect matches the
  price-book 3200x1600 ratio closely).
- Urban Cemento's room-shot images on luminastone.eu were **excluded** --
  their own filenames are tagged "...FakeIA-..." (the site's own admission
  they are AI-generated marketing images, not real photography/CGI of the
  actual product).
- Patagonia's only pisastone image is a kitchen room render (dramatic
  black/gold veining) -- added as a `room` gallery image but NOT used to
  promote the existing `closeup-only` main to `slab` (it is not a slab face).
- Astral White, Bianco Venatino, Calacatta Eternal, Statuario Frost/Rhin/
  Venato, Super White Marble: only image found on either source is a pisastone
  kitchen room render -- `productUrl` + `room` gallery image added, main
  correctly left `missing` (no slab-face photo exists for these on the web
  this pass).

## Re-run
```
python tools/harvest_lumina.py           # re-scrape (cached; delete tools/_cache/lumina to force)
python tools/reconcile_lumina.py --report   # dry run, prints the match table
python tools/reconcile_lumina.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
