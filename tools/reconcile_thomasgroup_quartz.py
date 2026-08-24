"""Reconcile tools/thomasgroup-quartz-harvest.json with slab-library + price book.
QUARTZ + SINTERED STONE only (supplier "Thomas Group (Surfaces Collection)").
--report prints the match table and changes nothing; --apply downloads originals,
writes webps, updates slabs.json (via harvest_lib.patch_library, bumps `generated`)
and writes the two contact sheets + REPORT.md.

Rules (HARVEST-SPEC.md + orchestrator Decisions 2026-08-24):
  - Silkstone Quartz + Vadara Quartz: Thomas Group's own brands (or exclusive UK
    distribution) -> NEW library entries, supplier == "Thomas Group (Surfaces
    Collection)" exactly, `details` starts "Silkstone · " / "Vadara · ".
  - Neolith (Sintered Stone): a duplicate-brand case. Where an existing library
    entry under supplier "Neolith" already covers the colour (matched by SKU code
    embedded in its neolith.com productUrl, confirmed against the 16 Thomas Group
    colours -- see MATCH_TO_EXISTING_NEOLITH below), add "Thomas Group (Surfaces
    Collection)" to that entry's suppliers[] and the Thomas Group spelling to its
    aliases[] -- do NOT create a duplicate. Where no existing Neolith entry covers
    it, create one under supplier "Thomas Group (Surfaces Collection)" with
    details starting "Neolith · ".
  - Price book is the naming/size authority: slabSizes comes from
    hl.load_pricebook() sizes, not scraped text.
"""
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Thomas Group (Surfaces Collection)"
QUARTZ_DEST = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "THOMAS GROUP (Silkstone-Vadara)")
SINTERED_DEST = os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED", "THOMAS GROUP (Neolith)")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "thomasgroup-quartz-harvest.json"), encoding="utf-8"))

# Confirmed 2026-08-24 by matching each existing "Neolith" library entry's
# neolith.com productUrl SKU code (e.g. .../calacatta-c01-c01r/ -> C01) against
# the Thomas Group colour's own SKU suffix (Calacatta 01 -> 01). 5 of 16 match;
# the other 11 have no equivalent in the library (different SKUs) -> new entries.
MATCH_TO_EXISTING_NEOLITH = {
    "Neolith Beton": "Beton",                              # exact name, same SKU
    "Neolith Calacatta 01": "Calacatta (BM)",               # neolith.com .../calacatta-c01-c01r/
    "Neolith Calacatta Gold Cg01": "Calacatta Gold (BM)",   # .../calacatta-gold-cg01-cg01r/
    "Neolith Estatuario 01": "Estatuario (BM)",             # .../estatuario-e01-e01r/ (E01, NOT E04)
    "Neolith Zaha": "Zaha Stone",                           # .../zaha-stone/
}


# --------------------------------------------------------------------- helpers --
def norm_tokens(s):
    s = re.sub(r'[()]', ' ', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
    return re.sub(r'\s+', ' ', s)


def tsc_core(header):
    s = header
    s = re.sub(r'\d[\d,]*\s*[xX]\s*\d[\d,]*(\s*[xX]\s*\d+\s*mm)?', ' ', s)
    s = re.sub(r'\d+\s*mm', ' ', s, flags=re.I)
    s = re.sub(r'\b(satin|silk|silky|polished|pol|leathered|super\s*jumbo|group\s*\d)\b', ' ', s, flags=re.I)
    return norm_tokens(s)


def pb_core_silk_neolith(colour, strip_neolith_prefix=False):
    s = re.sub(r'\(end of line\)', '', colour, flags=re.I)
    if strip_neolith_prefix:
        s = re.sub(r'^neolith\s+', '', s, flags=re.I)
    return norm_tokens(s)


def dl(url, colour, dest_root, apply_):
    if not apply_ or not url:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="thomasgroup", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data, dest_root, colour, used_fn)


def is_placeholder(url):
    return bool(url) and "pitem-na" in url.lower()


# -------------------------------------------------------------- price book pull --
import csv
rows = list(csv.DictReader(open(hl.PRICEBOOK_CSV, encoding="utf-8-sig")))
tg_rows = [r for r in rows if r.get("Supplier", "").strip() == SUPPLIER]
quartz_colours = sorted(set(r["Colour"].strip() for r in tg_rows if r["Material"] == "Quartz"))
sintered_colours = sorted(set(r["Colour"].strip() for r in tg_rows if r["Material"] == "Sintered Stone"))
vadara_colours = [c for c in quartz_colours if re.search(r'\bV\d{3}L?\b', c)]
silkstone_colours = [c for c in quartz_colours
                      if c not in vadara_colours and c != "St Annes White"]

pb = hl.load_pricebook(SUPPLIER)  # {colour: {thicknesses, finishes, sizes}}

lib = hl.load_library()
lib_slabs = lib["slabs"]
neolith_entries = {s["colour"]: s for s in lib_slabs if s.get("supplier") == "Neolith"}

# ---- build lookup tables from the manifest ----
silk_by_core = {}
for it in manifest["silkstone"]:
    silk_by_core.setdefault(tsc_core(it["header"]), []).append(it)

neolith_by_core = {}
for it in manifest["neolith"]:
    neolith_by_core.setdefault(tsc_core(it["header"]), []).append(it)

vadara_manifest = manifest["vadara"]

mains_sheet, gallery_sheet = [], []
rows_out = []
n_created_silk = n_created_vadara = n_created_neolith = n_linked_neolith = 0
n_closeups = n_rooms = n_notfound = 0


def pick_best_tsc_item(items):
    """Prefer an item with a real (non-placeholder) photo; among those, prefer
    the one whose swatch/photos differ (first is fine -- they're batch dupes)."""
    real = [it for it in items if not is_placeholder(it["photos"])]
    return (real or items)[0]


def slab_sizes_for(colour, pbinfo, tsc_sizes_text=None):
    if pbinfo and pbinfo.get("sizes"):
        return hl.format_slab_sizes(pbinfo["sizes"])
    if tsc_sizes_text:
        return " / ".join(sorted(set(s.replace("*", "x") for s in tsc_sizes_text)))
    return ""


def new_entry_id(colour):
    return SUPPLIER.lower().replace(" ", "-").replace("(", "").replace(")", "") \
        + "--" + re.sub(r"[^a-z0-9]+", "-", colour.lower()).strip("-")


def make_entry(colour, material, thicknesses, details_prefix):
    return {
        "id": new_entry_id(colour), "supplier": SUPPLIER, "colour": colour,
        "material": material, "naturalStone": False, "illustrationOnly": False,
        "thicknesses": thicknesses,
        "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""},
        "details": details_prefix,
    }


# ============================================================== SILKSTONE =====
for colour in silkstone_colours:
    core = pb_core_silk_neolith(colour)
    items = silk_by_core.get(core)
    if not items:
        rows_out.append(("Silkstone", colour, "NOT FOUND", "-", "-"))
        n_notfound += 1
        continue
    it = pick_best_tsc_item(items)
    has_photo = not is_placeholder(it["photos"])
    rows_out.append(("Silkstone", colour, "NEW" if has_photo else "NEW (no photo on site)",
                      it["header"], "slab+closeup" if it.get("swatch") else "slab only"))
    if not apply_mode:
        continue

    pbinfo = pb.get(colour, {})
    entry = make_entry(colour, "Quartz", sorted(pbinfo.get("thicknesses", [])) or [20, 30],
                        "Silkstone · Thomas Group's own-label quartz range")
    entry["productUrl"] = "https://thesurfacecollection.co.uk/products/silkstone-quartz/"
    sizes = slab_sizes_for(colour, pbinfo, it.get("sizes"))
    if sizes:
        entry["slabSizes"] = sizes
    lib_slabs.append(entry)
    n_created_silk += 1

    gallery = []
    if has_photo:
        p = dl(it["photos"], colour, QUARTZ_DEST, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            entry["image"] = {"file": fn, "status": "slab", "source": entry["productUrl"], "borrowedFrom": ""}
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "Silkstone"))
            gallery.append(dict(entry["image"], kind="slab"))
    else:
        mains_sheet.append((colour, None, "NO PHOTO ON SITE"))

    if it.get("swatch"):
        p = dl(it["swatch"], colour, QUARTZ_DEST, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup1")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup",
                             "source": entry["productUrl"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU1", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
    if len(gallery) > 1:
        entry["images"] = gallery

# ================================================================= VADARA =====
for colour in vadara_colours:
    rec = vadara_manifest.get(colour, {})
    src = rec.get("source")
    if src == "vadara.uk" and rec.get("slab"):
        slab_url, closeup_url, rooms_urls = rec["slab"], None, rec.get("rooms", [])
        product_url = f"https://www.vadara.uk/designs/{rec['slug']}/"
        sizes_text = rec.get("tsc_sizes")
    elif src == "tsc-only" and rec.get("tsc_photos"):
        slab_url, closeup_url, rooms_urls = rec["tsc_photos"], rec.get("tsc_swatch"), []
        product_url = "https://thesurfacecollection.co.uk/products/vadara-quartz/"
        sizes_text = rec.get("tsc_sizes")
    else:
        rows_out.append(("Vadara", colour, "NOT FOUND", "-", "-"))
        n_notfound += 1
        continue

    rows_out.append(("Vadara", colour, "NEW", product_url, f"slab, {len(rooms_urls)} room(s)"))
    if not apply_mode:
        continue

    pbinfo = pb.get(colour, {})
    entry = make_entry(colour, "Quartz", sorted(pbinfo.get("thicknesses", [])) or [20, 30],
                        "Vadara Quartz · UK distributed by Thomas Group (Jan 2025)")
    entry["productUrl"] = product_url
    sizes = slab_sizes_for(colour, pbinfo, sizes_text)
    if sizes:
        entry["slabSizes"] = sizes
    lib_slabs.append(entry)
    n_created_vadara += 1

    gallery = []
    p = dl(slab_url, colour, QUARTZ_DEST, apply_mode)
    if p and os.path.exists(p):
        fn = hl.to_library_webp(p, entry["id"])
        entry["image"] = {"file": fn, "status": "slab", "source": product_url, "borrowedFrom": ""}
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "Vadara"))
        gallery.append(dict(entry["image"], kind="slab"))
    else:
        mains_sheet.append((colour, None, "DOWNLOAD FAILED"))

    if closeup_url:
        p = dl(closeup_url, colour, QUARTZ_DEST, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup1")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup",
                             "source": product_url, "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU1", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
    for i, u in enumerate(rooms_urls, 1):
        p = dl(u, colour, QUARTZ_DEST, apply_mode)
        if not p or not os.path.exists(p):
            continue
        fn = hl.to_library_webp(p, f"{entry['id']}--room{i}")
        gallery.append({"file": fn, "status": "representative", "kind": "room",
                         "source": product_url, "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} room{i}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

# ================================================================ NEOLITH =====
for colour in sintered_colours:
    linked_colour = MATCH_TO_EXISTING_NEOLITH.get(colour)
    core = pb_core_silk_neolith(colour, strip_neolith_prefix=True)
    items = neolith_by_core.get(core)
    if not items:
        rows_out.append(("Neolith", colour, "NOT FOUND", linked_colour or "-", "-"))
        n_notfound += 1
        continue
    it = pick_best_tsc_item(items)
    tsc_url = "https://thesurfacecollection.co.uk/products/neolith-by-the-size/"

    if linked_colour:
        existing = neolith_entries.get(linked_colour)
        rows_out.append(("Neolith", colour, f"LINK -> Neolith {linked_colour!r}",
                          it["header"], "existing img kept" if existing and existing.get("image", {}).get("status") == "slab" else "needs image"))
        if not apply_mode or not existing:
            continue
        if SUPPLIER not in (existing.get("suppliers") or []):
            existing.setdefault("suppliers", [])
            if existing["suppliers"] != [] or True:
                existing["suppliers"] = list(dict.fromkeys(existing.get("suppliers", []) + [SUPPLIER]))
        existing.setdefault("aliases", [])
        if colour not in existing["aliases"]:
            existing["aliases"].append(colour)
        n_linked_neolith += 1
        # fill gaps only -- never clobber an existing good image/gallery
        if existing.get("image", {}).get("status") != "slab" and not is_placeholder(it["photos"]):
            p = dl(it["photos"], linked_colour, SINTERED_DEST, apply_mode)
            if p and os.path.exists(p):
                fn = hl.to_library_webp(p, existing["id"])
                existing["image"] = {"file": fn, "status": "slab", "source": tsc_url, "borrowedFrom": ""}
                mains_sheet.append((linked_colour, os.path.join(hl.IMAGES_DIR, fn), "Neolith(linked)"))
        if not existing.get("images") and it.get("swatch"):
            p = dl(it["swatch"], linked_colour, SINTERED_DEST, apply_mode)
            if p and os.path.exists(p):
                fn = hl.to_library_webp(p, f"{existing['id']}--closeup1")
                existing["images"] = ([dict(existing["image"], kind="slab")] if existing.get("image", {}).get("file") else []) + \
                    [{"file": fn, "status": "closeup", "kind": "closeup", "source": tsc_url, "borrowedFrom": ""}]
                gallery_sheet.append((f"{linked_colour} CU1", os.path.join(hl.IMAGES_DIR, fn)))
                n_closeups += 1
        if not existing.get("productUrl"):
            existing["productUrl"] = tsc_url
        continue

    # no existing Neolith entry -> new one under Thomas Group
    has_photo = not is_placeholder(it["photos"])
    rows_out.append(("Neolith", colour, "NEW" if has_photo else "NEW (no photo)",
                      it["header"], "slab+closeup" if it.get("swatch") else "slab only"))
    if not apply_mode:
        continue
    pbinfo = pb.get(colour, {})
    entry = make_entry(colour, "Sintered Stone", sorted(pbinfo.get("thicknesses", [])) or [6, 12],
                        "Neolith · by The Size; sold in the UK via Thomas Group (Surfaces Collection)")
    entry["productUrl"] = tsc_url
    sizes = slab_sizes_for(colour, pbinfo, it.get("sizes"))
    if sizes:
        entry["slabSizes"] = sizes
    lib_slabs.append(entry)
    n_created_neolith += 1

    gallery = []
    if has_photo:
        p = dl(it["photos"], colour, SINTERED_DEST, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            entry["image"] = {"file": fn, "status": "slab", "source": tsc_url, "borrowedFrom": ""}
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "Neolith(new)"))
            gallery.append(dict(entry["image"], kind="slab"))
    else:
        mains_sheet.append((colour, None, "NO PHOTO ON SITE"))
    if it.get("swatch"):
        p = dl(it["swatch"], colour, SINTERED_DEST, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup1")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": tsc_url, "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU1", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
    if len(gallery) > 1:
        entry["images"] = gallery


# --------------------------------------------------------------------- report --
w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(5)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(5)))

print()
print(f"TOTAL rows: {len(rows_out)} | not found: {n_notfound}")
print(f"Silkstone created: {n_created_silk} | Vadara created: {n_created_vadara} | "
      f"Neolith created: {n_created_neolith} | Neolith linked to existing: {n_linked_neolith}")
print(f"closeups: {n_closeups} | rooms: {n_rooms}")

if apply_mode:
    # patch_library reloads slabs.json fresh and needs the SAME mutated list we
    # already built in-process (built against the snapshot we loaded above) --
    # since no other Thomas Group entries can exist yet (verified: 0 before this
    # run) and Neolith edits are additive (suppliers[]/aliases[]/gap-fill only),
    # re-apply our exact same edits against a freshly loaded copy for safety.
    def mutate(fresh_lib):
        fresh_by_id = {s["id"]: s for s in fresh_lib["slabs"]}
        fresh_neolith_by_colour = {s["colour"]: s for s in fresh_lib["slabs"] if s.get("supplier") == "Neolith"}
        added = 0
        for s in lib_slabs:
            if s.get("supplier") == SUPPLIER and s["id"] not in fresh_by_id:
                fresh_lib["slabs"].append(s)
                added += 1
        for colour, linked_colour in MATCH_TO_EXISTING_NEOLITH.items():
            existing_snapshot = neolith_entries.get(linked_colour)
            fresh_existing = fresh_neolith_by_colour.get(linked_colour)
            if not existing_snapshot or not fresh_existing:
                continue
            if SUPPLIER not in (fresh_existing.get("suppliers") or []):
                fresh_existing["suppliers"] = list(dict.fromkeys(fresh_existing.get("suppliers", []) + [SUPPLIER]))
            fresh_existing.setdefault("aliases", [])
            if colour not in fresh_existing["aliases"]:
                fresh_existing["aliases"].append(colour)
            if existing_snapshot.get("image", {}).get("file") and fresh_existing.get("image", {}).get("status") != "slab":
                fresh_existing["image"] = existing_snapshot["image"]
            if existing_snapshot.get("images") and not fresh_existing.get("images"):
                fresh_existing["images"] = existing_snapshot["images"]
            if existing_snapshot.get("productUrl") and not fresh_existing.get("productUrl"):
                fresh_existing["productUrl"] = existing_snapshot["productUrl"]
        return {"added": added}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "thomasgroup-quartz-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "thomasgroup-quartz-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "thomasgroup-quartz-REPORT.md")
    not_found_list = [r[1] for r in rows_out if r[2] == "NOT FOUND"]
    no_photo_list = [r[1] for r in rows_out if "no photo" in r[2].lower()]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Thomas Group (Surfaces Collection) -- Quartz + Sintered Stone harvest report

Scope: 65 Quartz + 16 Sintered Stone price-book colours under supplier
"Thomas Group (Surfaces Collection)" (Porcelain/Atlas Plan is a separate agent's job).

Sources:
- Silkstone Quartz (27 colours, Thomas Group's own label) --
  thesurfacecollection.co.uk/products/silkstone-quartz/ (single page, all SKUs
  incl. End of Line). `lib/photos/*.jpg` = slab, `lib/swatch/*.jpg` = closeup.
- Vadara Quartz (37 colours) -- primary vadara.uk /designs/{{slug}}/ pages (34 of
  37; slugs from /product-sitemap.xml, not the small homepage carousel).
  `Vadara_{{Name}}_(Web|HiRes).jpg` = slab (HiRes preferred), `VQ_INSTALL_*`/
  `*_RenderNN.jpg` = room. `*_STORY_*.jpg` excluded (unrelated landscape mood
  photography, not product shots). No dedicated closeup exists on any page.
  3 "Super Jumbo" SKUs (Braewind, Nomad Valley, Soraline) have no vadara.uk page
  at all -- sourced from thesurfacecollection.co.uk's Vadara sub-pages instead
  (same lightbox pattern as Silkstone).
- Neolith by The Size (16 colours, Sintered Stone) --
  thesurfacecollection.co.uk/products/neolith-by-the-size/ (single page, all
  16). neolith.com is bot-blocked (HTTP 403 to curl) -- not attempted, per spec.

## Neolith reconciliation (Decisions: entry identity = one physical product)
5 of the 16 already exist in the library under plain supplier "Neolith"
(harvested from neolith.com directly) -- confirmed by matching the SKU code
embedded in each existing entry's neolith.com productUrl against the Thomas
Group colour's own SKU suffix:
| Thomas Group colour | -> existing Neolith entry | SKU evidence |
|---|---|---|
| Beton | Beton | exact name |
| Calacatta 01 | Calacatta (BM) | .../calacatta-**c01**-c01r/ |
| Calacatta Gold Cg01 | Calacatta Gold (BM) | .../calacatta-gold-**cg01**-cg01r/ |
| Estatuario 01 | Estatuario (BM) | .../estatuario-**e01**-e01r/ |
| Zaha | Zaha Stone | .../zaha-stone/ |

These 5 got "Thomas Group (Surfaces Collection)" added to `suppliers[]` and the
Thomas Group spelling added to `aliases[]` -- NOT duplicated. Note "Estatuario
E04" is a genuinely different Neolith SKU (E04, not E01) and got its own new
entry, not linked to "Estatuario (BM)".

The other 11 (Avorio, Basalt Beige, Bianco Carrara Bc02, Cement, Estatuario E04,
Iron Moss, La Boheme, Nero Marquina, Nieve, Phedra, Pierre Bleue) have no
equivalent existing entry (checked all 16 against all 45 existing Neolith
colours/productUrl SKU codes) -- new entries under supplier "Thomas Group
(Surfaces Collection)".

## Counts
- Silkstone: {len(silkstone_colours)} price-book colours | created: {n_created_silk} | not found: {sum(1 for r in rows_out if r[0]=='Silkstone' and r[2]=='NOT FOUND')} ({[r[1] for r in rows_out if r[0]=='Silkstone' and r[2]=='NOT FOUND']})
- Vadara: {len(vadara_colours)} price-book colours | created: {n_created_vadara} | not found: {sum(1 for r in rows_out if r[0]=='Vadara' and r[2]=='NOT FOUND')}
- Neolith: {len(sintered_colours)} price-book colours | created: {n_created_neolith} | linked to existing: {n_linked_neolith} | not found: {sum(1 for r in rows_out if r[0]=='Neolith' and r[2]=='NOT FOUND')}
- St Annes White (Architectural Material - Morris Homes, 1 colour) -- SKIPPED,
  not attempted. Bespoke housebuilder-contract SKU; not found anywhere on
  thesurfacecollection.co.uk, vadara.uk, or a plain web search (closest hit:
  Radianz "St Helens White", a different name/product). Recommend asking
  Thomas Group directly.
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- No-photo-on-site colours (placeholder `pitem-na.jpg` on Silkstone page):
  {no_photo_list}

## Assumptions
- `slabSizes` comes from the price book (`hl.load_pricebook`) first; scraped
  page text only as a fallback when the price book has no size for that colour.
- Silkstone/Neolith TSC matching: normalise both sides (strip thickness "NNmm",
  finish words satin/silk/polished/leathered, dimension pairs "NNNN X NNNN"),
  then exact-match. "(End of Line)"/"Neolith " prefixes stripped from the
  price-book side only (site doesn't show them).
- Vadara own-asset filtering uses each design page's own `<h1 class="...
  post_title...">` text (not the price-book name) to pick which images belong
  to it -- the price book's spelling drifts from the site's in a few cases
  (Calacatta Dorad**o** vs site's Dorad**a**; Petr**o** Grigio vs site's
  Petr**a** Grigio) and the on-page title is authoritative for its own assets.
- Two Silkstone colours ("Desert Silver (Silestone)", "Honed Angelo White")
  resolve to a genuine product card but the site itself serves a
  `pitem-na.jpg` placeholder instead of a photo -- entries created with
  productUrl/details/sizes filled in, image left `status: "missing"`.
- Two Silkstone colours confirmed NOT on the site at all (checked again this
  pass, same as the discovery report): Venato Royale, Smokey Taupe.

## Re-run
```
python tools/harvest_thomasgroup_quartz.py             # re-scrape (cached; delete tools/_cache/thomasgroup to force)
python tools/reconcile_thomasgroup_quartz.py --report   # dry run, prints the match table
python tools/reconcile_thomasgroup_quartz.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
