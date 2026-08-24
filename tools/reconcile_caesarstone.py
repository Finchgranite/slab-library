"""Reconcile tools/caesarstone-harvest.json with slab-library (supplier
Caesarstone) + the price book. --report prints the match table and changes
nothing; --apply downloads originals, writes webps, updates slabs.json
(bumps `generated`) and writes the two contact sheets + REPORT.md.

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": leave the main alone (don't clobber a
    good existing image), but still fill productUrl/slabSizes/details/gallery.
  - status "missing" or "closeup-only": if the site has a `full` slab image,
    download it and promote/set status "slab".
  - price-book colours the site confirms but the library lacks: added.
  - site colours with no library/price-book match: reported, not invented.
"""
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Caesarstone"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "CAESARSTONE- 26")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "caesarstone-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER]
lib_pool = [(r["colour"], r) for r in entries]

pb = hl.load_pricebook(SUPPLIER)
pb_pool = [(k, k) for k in pb]

mains_sheet, gallery_sheet = [], []
rows_out = []
matched_lib_ids = set()
matched_pb_colours = set()
n_added = n_upgraded = n_closeups = n_rooms = n_filled_meta = 0


def dl(url, colour, apply_):
    """Download (or reuse cache) -> returns local path or None. Tries the
    true original over any -WxH/-scaled thumbnail referenced in the HTML
    (harvest_lib.fetch_best) since the server usually still has it."""
    if not apply_:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier=SUPPLIER, cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data, DEST_ROOT, colour, used_fn)


for m in manifest:
    if m.get("error"):
        rows_out.append((m["url"], "FETCH-FAIL", m["error"], "-", "-"))
        continue

    site_name = m["colour"]
    entry, escore = hl.match_colour(site_name, lib_pool)
    pbc, pscore = hl.match_colour(site_name, pb_pool)

    pb_sizes = pb.get(pbc, {}).get("sizes", {}) if pbc else {}
    slab_sizes = hl.format_slab_sizes(pb_sizes) if pb_sizes else ""
    if not slab_sizes and m.get("full") and m["full"].get("size"):
        sz = m["full"]["size"]
        if sz and sz.get("width") and sz.get("height"):
            slab_sizes = f"{sz['width']}x{sz['height']}"

    action = "match" if entry else ("NEW (pricebook confirms)" if pbc else "UNMATCHED")
    cur_status = entry["image"]["status"] if entry else "-"
    will_set_main = bool(m.get("full") and m["full"].get("src") and (not entry or cur_status != "slab"))
    rows_out.append((
        site_name, action, entry["colour"] if entry else "-", pbc or "NO PRICEBOOK",
        f"{cur_status}->slab" if will_set_main else cur_status,
        f"{len(m.get('closeups', []))}cu/{len(m.get('rooms', []))}rm",
    ))

    if pbc:
        matched_pb_colours.add(pbc)
    if not apply_mode:
        continue

    if entry is None:
        if not pbc:
            continue  # don't invent entries the price book doesn't confirm
        colour_name = pbc
        pbinfo = pb[pbc]
        entry = {
            "id": "caesarstone--" + re.sub(r"[^a-z0-9]+", "-", colour_name.lower()).strip("-"),
            "supplier": SUPPLIER, "colour": colour_name,
            "material": "Porcelain" if "porcelain" in m["url"] else "Quartz",
            "naturalStone": False, "illustrationOnly": False,
            "thicknesses": sorted(pbinfo["thicknesses"]) or m.get("thicknesses", []),
            "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""},
        }
        lib["slabs"].append(entry)
        lib_pool.append((colour_name, entry))
        matched_lib_ids.add(entry["id"])
        n_added += 1
    matched_lib_ids.add(entry["id"])

    entry["productUrl"] = m["url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    blurb_bits = []
    if m.get("description"):
        blurb_bits.append(m["description"])
    elif m.get("finish"):
        blurb_bits.append(m["finish"])
    if blurb_bits:
        entry["details"] = "; ".join(blurb_bits)[:300]
    if m.get("thicknesses") and not entry.get("thicknesses"):
        entry["thicknesses"] = m["thicknesses"]
    n_filled_meta += 1

    # --- main slab image ---
    if will_set_main:
        full = m["full"]
        p = dl(full["src"], entry["colour"], apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            entry["image"] = {"file": fn, "status": "slab", "source": m["url"], "borrowedFrom": ""}
            if full.get("ratio"):
                entry["image"]["scale"] = "true" if full.get("size") else "approx"
            n_upgraded += 0 if was_missing else 1
            mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if was_missing else "UPGRADED"))
        else:
            mains_sheet.append((entry["colour"], None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))

    # --- gallery: closeups + rooms ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    ci = ri = 0
    for u in m.get("closeups", []):
        p = dl(u, entry["colour"], apply_mode)
        if not p or not os.path.exists(p):
            continue
        ci += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
        gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": m["url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{entry['colour']} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
        n_closeups += 1
    for u in m.get("rooms", []):
        p = dl(u, entry["colour"], apply_mode)
        if not p or not os.path.exists(p):
            continue
        ri += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
        gallery.append({"file": fn, "status": "representative", "kind": "room", "source": m["url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{entry['colour']} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

unmatched_lib = sorted(r["colour"] for r in entries if r["id"] not in matched_lib_ids) if apply_mode else []
unmatched_pb = sorted(set(pb) - matched_pb_colours)

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))

print()
print(f"site pages: {len(manifest)} | matched to library: {sum(1 for r in rows_out if r[1]=='match')} | "
      f"NEW (pb-confirmed): {sum(1 for r in rows_out if 'NEW' in r[1])} | "
      f"unmatched (neither): {sum(1 for r in rows_out if r[1]=='UNMATCHED')}")
print(f"unmatched price-book Caesarstone colours (not seen on site): {unmatched_pb}")

if apply_mode:
    hl.save_library(lib)
    print(f"\nAPPLIED. library entries added: {n_added} | closeups: {n_closeups} | rooms: {n_rooms}")
    print("library Caesarstone colours not touched this run (no site match):", unmatched_lib)

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "caesarstone-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "caesarstone-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "caesarstone-REPORT.md")
    n_new_mains = sum(1 for _, _, s in mains_sheet if s == "NEW")
    n_upg_mains = sum(1 for _, _, s in mains_sheet if s == "UPGRADED")
    n_dl_fail = sum(1 for _, p, s in mains_sheet if s == "DOWNLOAD FAILED")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Caesarstone harvest report

Source: https://www.caesarstone.co.uk/catalog-sitemap.xml ({len(manifest)} colour pages).
Main slab image + true mm dimensions come from each page's embedded
`fullView` JS var; close-ups from `_CU_`-tagged filenames; room shots from
`Kitchen_Render`/`vanity-render` filenames -- all filtered to the page's own
product code so the "related colours" carousel on every page isn't harvested
as extra images.

## Counts
- Site colour pages: {len(manifest)} (fetch failures: {sum(1 for m in manifest if m.get('error'))})
- Matched to existing library entries: {sum(1 for r in rows_out if r[1]=='match')}
- New library entries added (price-book confirmed): {n_added}
- Mains newly set (was missing): {n_new_mains}
- Mains upgraded (was closeup-only): {n_upg_mains}
- Main downloads that failed: {n_dl_fail}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Unmatched site->library (neither library nor price book claims it): {sum(1 for r in rows_out if r[1]=='UNMATCHED')}
- Unmatched price-book Caesarstone colours (not seen on site): {len(unmatched_pb)} -- {unmatched_pb}
- Library Caesarstone colours not touched this run: {unmatched_lib}

## Assumptions
- Price book is the naming/size authority; `slabSizes` comes from the price
  book first, the page's `fullView.size` only as a fallback when the price
  book has no row for that colour.
- `details` = the page's JSON-LD product `description` (one line), else the
  `Finish` field text.
- Existing `image.status == "slab"` entries are left alone (not re-downloaded)
  even if the site has a differently-cropped full image -- only "missing" and
  "closeup-only" are (re)set.
- 74 colour pages on the sitemap vs 76 library entries: a couple of library
  colours may be discontinued on the current UK site (see "not touched" list
  above); nothing was deleted.

## Re-run
```
python tools/harvest_caesarstone.py        # re-scrape (cached; delete tools/_cache/caesarstone to force)
python tools/reconcile_caesarstone.py --report   # dry run, prints the match table
python tools/reconcile_caesarstone.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
