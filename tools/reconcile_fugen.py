"""Reconcile tools/fugen-harvest.json with slab-library (supplier Fugen,
engineered colours only -- naturalStone entries are never touched).
--report prints the match table and changes nothing; --apply downloads
originals, writes webps, updates slabs.json via hl.patch_library (bumps
`generated`), writes the two contact sheets + REPORT.md.

Finish-variant colours (price book splits "X Leather" / "X Polished" into
separate rows) share ONE Fugen product page/photo set -- matched on a
finish-stripped "core" name (see harvest_fugen.strip_finish). Both/all
matching entries get the SAME slab/closeup/room images; `details` states
each entry's own finish.

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": leave the main alone, still fill
    productUrl/slabSizes/details/gallery.
  - status "missing" or "closeup-only": if the site has a slab image,
    download it and set/upgrade status to "slab".
  - price-book colours the site doesn't show a slab image for (or doesn't
    have a page for) stay untouched/missing -- reported, not invented.
"""
import json
import os
import re
import sys

import harvest_lib as hl
from harvest_fugen import strip_finish

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Fugen"
DEST_ROOT_QUARTZ = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "FUGEN")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "fugen-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == "Fugen" and not r.get("naturalStone")]

pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
matched_lib_ids = set()
matched_pb_colours = set()
n_upgraded = n_new_main = n_closeups = n_rooms = n_filled_meta = 0
dl_cache = {}   # url -> local path (avoid re-downloading shared images for finish-pair entries)


def dl(url, colour, apply_):
    if not apply_:
        return None
    if url in dl_cache:
        return dl_cache[url]
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="fugen", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        dl_cache[url] = None
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    p = hl.save_original(data, DEST_ROOT_QUARTZ, colour, used_fn)
    dl_cache[url] = p
    return p


def targets_for(core):
    st = hl._toks(core)
    out = []
    for e in entries:
        ct = hl._toks(strip_finish(e["colour"]))
        if ct and st and hl._fuzzy_subset(ct, st) and hl._fuzzy_subset(st, ct):
            out.append(e)
    return out


def finish_suffix(entry_colour, core):
    extra = entry_colour[len(core):].strip() if entry_colour.lower().startswith(core.lower()) else ""
    return extra


for m in manifest:
    if m.get("error"):
        rows_out.append((m["url"], "FETCH-FAIL", m["error"], "-", "-", "-"))
        continue

    targets = targets_for(m["core"])
    pbc, pscore = hl.match_colour(m["name"], [(k, k) for k in pb]) if not targets else (None, (0, 0))
    if not targets:
        action = "UNMATCHED (not in our library)"
        rows_out.append((m["name"], action, "-", pbc or "-", "-", f"{len(m.get('closeups', []))}cu/{len(m.get('rooms', []))}rm"))
        continue

    for entry in targets:
        matched_lib_ids.add(entry["id"])
        pb_row = pb.get(entry["colour"])
        pb_sizes = pb_row["sizes"] if pb_row else {}
        slab_sizes = hl.format_slab_sizes(pb_sizes) if pb_sizes else ""
        if not slab_sizes and m.get("dims"):
            dm = re.match(r'(\d+)\s*x\s*(\d+)', m["dims"], re.I)
            if dm:
                slab_sizes = f"{dm.group(1)}x{dm.group(2)}"

        cur_status = entry["image"]["status"]
        will_set_main = bool(m.get("slab") and cur_status in ("missing", "closeup-only"))
        rows_out.append((
            entry["colour"], "match", entry["colour"], entry["colour"],
            f"{cur_status}->slab" if will_set_main else cur_status,
            f"{len(m.get('closeups', []))}cu/{len(m.get('rooms', []))}rm",
        ))

        if not apply_mode:
            continue

        entry["productUrl"] = m["url"]
        if slab_sizes:
            entry["slabSizes"] = slab_sizes
        fsuffix = finish_suffix(entry["colour"], m["core"])
        blurb_bits = []
        if m.get("description"):
            blurb_bits.append(m["description"])
        if fsuffix:
            blurb_bits.append(f"Finish: {fsuffix}")
        elif m.get("finish"):
            blurb_bits.append(f"Finish: {m['finish']}")
        if blurb_bits:
            entry["details"] = "; ".join(blurb_bits)[:300]
        if m["name"].lower() != entry["colour"].lower():
            aliases = entry.setdefault("aliases", [])
            if m["name"] not in aliases:
                aliases.append(m["name"])
        n_filled_meta += 1

        # --- main slab image ---
        if will_set_main:
            p = dl(m["slab"], entry["colour"], apply_mode)
            if p and os.path.exists(p):
                fn = hl.to_library_webp(p, entry["id"])
                was_missing = cur_status == "missing"
                entry["image"] = {"file": fn, "status": "slab", "source": m["url"], "borrowedFrom": ""}
                if was_missing:
                    n_new_main += 1
                else:
                    n_upgraded += 1
                mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, fn),
                                     "NEW" if was_missing else "UPGRADED"))
            else:
                mains_sheet.append((entry["colour"], None, "DOWNLOAD FAILED"))
        elif entry["image"].get("file"):
            mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
        else:
            mains_sheet.append((entry["colour"], None, "still missing"))

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

    if pbc:
        matched_pb_colours.add(pbc)
    for t in targets:
        if t["colour"] in pb:
            matched_pb_colours.add(t["colour"])

unmatched_lib = sorted(r["colour"] for r in entries if r["id"] not in matched_lib_ids)
engineered_pb_colours = {r["colour"] for r in entries}  # our 46 engineered rows are the pb-relevance scope
unmatched_pb = sorted(engineered_pb_colours - matched_pb_colours)
unmatched_site = sorted(set(m["name"] for m in manifest if not m.get("error") and not targets_for(m["core"])))

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))

print()
print(f"site pages: {len(manifest)} | matched rows: {sum(1 for r in rows_out if r[1]=='match')} | "
      f"unmatched site->library: {sum(1 for r in rows_out if 'UNMATCHED' in r[1])}")
print(f"unmatched price-book Fugen (engineered) colours (not filled this run): {unmatched_pb}")
print(f"unmatched site products (no library/pricebook claim -- extra Fugen ranges we don't stock): {len(unmatched_site)}")

if apply_mode:
    # NOTE: entries were mutated in place on objects from hl.load_library() called
    # earlier in THIS process, not inside a patch_library callback -- re-apply the
    # same mutations against a freshly loaded library so concurrent writers are safe.
    ids_touched = {e["id"]: e for e in entries}

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, edited in ids_touched.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == "Fugen" and not s.get("naturalStone"):
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly set: {n_new_main} | mains upgraded: {n_upgraded} | closeups: {n_closeups} | rooms: {n_rooms}")
    print("library Fugen engineered colours not touched this run:", unmatched_lib)

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "fugen-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "fugen-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "fugen-REPORT.md")
    n_dl_fail = sum(1 for _, p, s in mains_sheet if s == "DOWNLOAD FAILED")
    still_missing_colours = sorted(r["colour"] for r in entries if r["image"]["status"] != "slab")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Fugen harvest report

Source: https://fugenstone.co.uk/product-sitemap.xml -> product-sitemap ({len(manifest)}
`/quartz-worktops/` colour pages; porcelain pages excluded, no porcelain in our
46-entry Fugen scope). Real product domain is `fugenstone.co.uk` (no `www`) --
the `www.fugenstone.co.uk/?s=...` search-query URLs previously stored as
`productUrl` on ~33 entries were placeholders, not real product pages; this
run replaces them with the real WooCommerce product URL for every matched
colour.

Main slab image: every page carries a filename containing "slab" under an
"Entire Slab"/"Entire slab" heading (2:1 aspect), separate from the
WooCommerce product gallery. Close-ups: "*Tile*" / old-template
"441_FUGENSTONE_*"/"..._R.jpg" / unnumbered "*Gallery*"/"*Gallery-1*".
Rooms: "*Gallery-2*"/"*Gallery-3*" (numbered >=2) / "*Set-N*". Styled
flat-lay mood-board shots ("*-comp.jpg", "Beth-Davis...Flatlays...") are
skipped -- verified visually, not real slab/closeup/room content.

## Counts
- Site `/quartz-worktops/` pages: {len(manifest)} (fetch failures: {sum(1 for m in manifest if m.get('error'))})
- Site pages with a slab image found: {sum(1 for m in manifest if m.get('slab'))}
- Library rows matched (finish-variant colours count once per row): {sum(1 for r in rows_out if r[1]=='match')}
- Mains newly set (was missing): {n_new_main}
- Mains upgraded (was closeup-only): {n_upgraded}
- Main downloads that failed: {n_dl_fail}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Library Fugen engineered colours not touched this run (no site match): {unmatched_lib}
- Price-book Fugen engineered colours still unfilled: {unmatched_pb}
- Site products with no library/price-book claim (Fugen ranges we don't currently stock): {len(unmatched_site)} -- {unmatched_site}
- Still not status=slab after this run: {still_missing_colours}

## Assumptions
- Finish-variant price-book rows ("X Leather"/"X Polished"/"Jasper Leather"+
  "Jasper Polished") map to ONE Fugen product page; the WooCommerce
  `data-product_variations` image is identical across finishes on every
  product checked (verified on Celestial) so both/all rows get the same
  slab/closeup/room images, `details` states each row's own finish.
- Site finish wording sometimes differs from our price-book finish word --
  e.g. Imperium's page says "Polished and Satin" (not "Leather"); Jasper's
  page says "Polished or Satin" (not "Leather"). Treated as the same
  Leather<->Satin low-sheen finish family per colour so "Imperium Leather"/
  "Jasper Leather" still map to this product -- worth confirming with Fugen
  whether their "Leather" SKUs are literally labelled "Satin" on the current
  site, or a genuinely different finish.
- "Light Grey" (price book, Polished): no matching product on the site --
  only "Dark Grey" exists, no mention of "Light Grey" anywhere on that page.
  Likely renamed/discontinued online. Still `missing`; ask Fugen.
- Niagara site page states slab size "3200 x 1260 mm" (odd width vs the
  price book's 3200x1600) -- price book size kept as authority per the
  existing sizing rule, site figure ignored as a likely site typo.
- Price book remains the sizing/naming authority; `slabSizes` from price book
  first, the page's parsed "LxW mm" text only as a fallback.
- 7 pages have an empty "Entire Slab" image widget (no asset uploaded):
  Black Shimmer, Silver Drift, Cotswold Gold, Valley White, Dune Frost,
  Gilded Chalk, Sunbeams -- of these, Black Shimmer/Silver Drift/
  Cotswold Gold/Valley White are in our library; metadata (productUrl,
  slabSizes, details, closeups) still filled where matched, but their main
  image is unchanged (Black Shimmer/Valley White already had a good "slab"
  main; Silver Drift/Cotswold Gold remain "closeup-only" -- the site itself
  has no slab photo for them).

## Re-run
```
python tools/harvest_fugen.py            # re-scrape (cached; delete tools/_cache/fugen to force)
python tools/reconcile_fugen.py --report  # dry run, prints the match table
python tools/reconcile_fugen.py --apply   # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
