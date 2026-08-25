"""Reconcile tools/bstone-harvest.json with slab-library (supplier B-Stone,
engineered colours only -- 100 naturalStone B-Stone entries are never touched).
--report prints the match table and changes nothing; --apply downloads
originals, writes webps, updates slabs.json via hl.patch_library (bumps
`generated`), writes the two contact sheets + REPORT.md.

Site has no per-colour product pages: every BQuartz colour is one lightbox
tile on https://bstoneuk.co.uk/material/bquartz/, every Techlam (sintered)
colour one tile on https://bstoneuk.co.uk/material/techlam/ -- so productUrl
is that shared listing page for every matched colour (there is nothing more
specific). Room/kitchen photos come from separate /inspiration/bquartz-*
posts (BQuartz only -- no Techlam inspiration posts exist). No closeup/
texture content exists anywhere on the site for either material.

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": leave the main alone, still fill
    productUrl/slabSizes/details/gallery.
  - status "missing"/"closeup-only"/"representative": if the site has a slab
    image, download it and set/upgrade status to "slab".
  - price-book colours the site doesn't show (or we have no page for) stay
    untouched/missing -- reported, not invented.
  - 4 price-book B-Stone engineered colours with no library entry yet
    (Cadiz, Colossal Cream, Forest, Salina Ivory) are CREATED here because
    the site confirms all 4 (Cadiz explicitly marked "NEW - arriving end of
    August 2026").
"""
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "B-Stone"
DEST_QUARTZ = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "B-Stone  quartz")
DEST_SINTERED = os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED", "B-STONE")

NEW_COLOURS = {
    # colour -> (material, id-slug)
    "Cadiz": "Quartz",
    "Colossal Cream": "Sintered Stone",
    "Forest": "Sintered Stone",
    "Salina Ivory": "Sintered Stone",
}

apply_mode = "--apply" in sys.argv

harvest = json.load(open(os.path.join(SCRATCH, "bstone-harvest.json"), encoding="utf-8"))
products = harvest["products"]
rooms = harvest["rooms"]

lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER and not r.get("naturalStone")]
pb = hl.load_pricebook(SUPPLIER)

UPGRADE_STATUSES = {"missing", "closeup-only", "representative"}


def slug(s):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s.lower())).strip('-')


def dest_for(material):
    return DEST_QUARTZ if material == "Quartz" else DEST_SINTERED


mains_sheet, gallery_sheet = [], []
rows_out = []
matched_lib_ids = set()
matched_pb_colours = set()
n_new_main = n_upgraded = n_rooms = n_filled_meta = n_created = 0
dl_cache = {}


def dl(url, colour, material, apply_):
    if not apply_:
        return None
    if url in dl_cache:
        return dl_cache[url]
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="bstone", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        dl_cache[url] = None
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    p = hl.save_original(data, dest_for(material), colour, used_fn)
    dl_cache[url] = p
    return p


# ------------------------------------------------------------------ match --
existing_by_name = {e["colour"].strip().lower(): e for e in entries}

unmatched_site = []
plan = []   # (entry_dict_or_None, product, is_new)

for p in products:
    name = p["clean_name"]
    key = name.strip().lower()
    entry = existing_by_name.get(key)
    if entry is None and name in NEW_COLOURS:
        # create it
        material = NEW_COLOURS[name]
        pbrow = pb.get(name, {})
        thicknesses = sorted(pbrow.get("thicknesses") or ({20, 30} if material == "Quartz" else {12, 20}))
        entry = {
            "id": f"b-stone--{slug(name)}",
            "supplier": SUPPLIER,
            "colour": name,
            "material": material,
            "naturalStone": False,
            "illustrationOnly": False,
            "thicknesses": thicknesses,
            "productUrl": "",
            "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""},
        }
        plan.append((entry, p, True))
        continue
    if entry is None:
        unmatched_site.append((p["material"], p["raw_title"], name))
        continue
    plan.append((entry, p, False))

matched_names = {name.strip().lower() for (e, p, isnew) in plan for name in [p["clean_name"]]}
unmatched_lib = sorted(e["colour"] for e in entries if e["colour"].strip().lower() not in matched_names)

for entry, p, is_new in plan:
    matched_lib_ids.add(entry["id"])
    if entry["colour"] in pb:
        matched_pb_colours.add(entry["colour"])

    pb_row = pb.get(entry["colour"])
    pb_sizes = pb_row["sizes"] if pb_row else {}
    slab_sizes = hl.format_slab_sizes(pb_sizes) if pb_sizes else ""

    cur_status = entry["image"]["status"]
    will_set_main = cur_status in UPGRADE_STATUSES or is_new

    range_label = "BQuartz" if p["material"] == "Quartz" else "Techlam"
    blurb = f"B-Stone {range_label} · {p['material']} · {p['finish']} finish"
    if p.get("description"):
        blurb += f". {p['description']}"
    if p.get("note"):
        blurb += f" ({p['note']})"

    rows_out.append((
        entry["colour"], "NEW" if is_new else "match", p["raw_title"],
        f"{cur_status}->slab" if will_set_main else cur_status,
        f"{len(rooms.get(p['clean_name'], []))}rm",
    ))

    if not apply_mode:
        continue

    entry["productUrl"] = p["page_url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    entry["details"] = blurb[:300]
    n_filled_meta += 1

    if will_set_main:
        path = dl(p["slab_url"], entry["colour"], p["material"], apply_mode)
        if path and os.path.exists(path):
            fn = hl.to_library_webp(path, entry["id"])
            was_missing = cur_status in ("missing",) or is_new
            entry["image"] = {"file": fn, "status": "slab", "source": p["page_url"], "borrowedFrom": ""}
            if was_missing:
                n_new_main += 1
            else:
                n_upgraded += 1
            mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if is_new else ("FILLED" if was_missing else "UPGRADED")))
        else:
            mains_sheet.append((entry["colour"], None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
    else:
        mains_sheet.append((entry["colour"], None, "still missing"))

    # --- gallery: room photos only (no closeup content exists on this site) ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    room_urls = rooms.get(p["clean_name"], [])
    ri = 0
    for u in room_urls:
        path = dl(u, entry["colour"], p["material"], apply_mode)
        if not path or not os.path.exists(path):
            continue
        ri += 1
        fn = hl.to_library_webp(path, f"{entry['id']}--room{ri}")
        gallery.append({"file": fn, "status": "representative", "kind": "room", "source": p["page_url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{entry['colour']} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

    if is_new:
        n_created += 1
        lib["slabs"].append(entry)

# ------------------------------------------------------------------ print --
engineered_pb_colours = {e["colour"] for e in entries} | set(NEW_COLOURS)
unmatched_pb = sorted(engineered_pb_colours - matched_pb_colours - {n for n, p, isnew in plan if False})
unmatched_pb = sorted((engineered_pb_colours) - {e["colour"] for e, p, isnew in plan})

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(5)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(5)))

print()
print(f"site products: {len(products)} | matched/created rows: {len(plan)} | "
      f"new entries: {sum(1 for e,p,n in plan if n)}")
print(f"library B-Stone engineered colours not matched by any site product: {unmatched_lib}")
print(f"site engineered products with no library/price-book claim: {len(unmatched_site)} -> {unmatched_site}")

if apply_mode:
    def mutate(fresh_lib):
        # re-key onto a freshly loaded library (concurrency-safe pattern)
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        edited_by_id = {e["id"]: e for e, p, isnew in plan}
        n_updated = n_added = 0
        touched_ids = set()
        for eid, edited in edited_by_id.items():
            existing_list = [s for s in by_id.get(eid, [])
                              if s.get("supplier") == SUPPLIER and not s.get("naturalStone")]
            if existing_list:
                for s in existing_list:
                    s.clear()
                    s.update(edited)
                    n_updated += 1
                touched_ids.add(eid)
            elif eid not in touched_ids:
                fresh_lib["slabs"].append(edited)
                n_added += 1
                touched_ids.add(eid)
        return {"updated": n_updated, "added": n_added}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly set: {n_new_main} | mains upgraded: {n_upgraded} | rooms: {n_rooms} | created: {n_created}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "bstone-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "bstone-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = sorted(e["colour"] for e, p, isnew in plan if e["image"]["status"] != "slab")
    report_path = os.path.join(hl.REPORTS_DIR, "bstone-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# B-Stone harvest report

Source: bstoneuk.co.uk has NO per-colour product pages. Every BQuartz colour is
one lightbox tile on `https://bstoneuk.co.uk/material/bquartz/` (25 tiles);
every Techlam (sintered stone) colour one tile on
`https://bstoneuk.co.uk/material/techlam/` (12 tiles). Each tile's full-res
`href` is the true slab photo (verified ~2:1 aspect, e.g. 2560x1280,
1920x960) -- not a swatch. `productUrl` for every matched colour is therefore
that shared listing page; there is nothing more specific to link to. No
texture/closeup imagery exists anywhere on the site for either material.

Room/kitchen photos come from a separate post type: `/inspiration-sitemap.xml`
lists individual project posts, many slugged `bquartz-<colour>[-N]` (matched
via `harvest_lib.match_colour`). No Techlam/sintered inspiration posts exist.
Up to 2 posts per BQuartz colour were fetched, 1 photo taken from each.

## Counts
- Site engineered tiles: {len(products)} (25 BQuartz + 12 Techlam)
- Library/price-book colours matched or created: {len(plan)}
- New entries created (site+price-book confirmed, no prior library row): {n_created} -- {sorted(NEW_COLOURS)}
- Mains newly set (was missing/new): {n_new_main}
- Mains upgraded (was closeup-only/representative): {n_upgraded}
- Room gallery images added: {n_rooms}
- Metadata-only fills (productUrl/slabSizes/details) on rows whose main was kept: {n_filled_meta - n_new_main - n_upgraded}
- Library B-Stone engineered colours the site has no matching tile for (untouched): {unmatched_lib}
- Site engineered tiles with no library/price-book claim (extra B-Stone ranges we don't stock): {len(unmatched_site)} -- {[f"{m}:{t}" for m,t,n in unmatched_site]}
- Still not status=slab after this run: {still_missing}

## Assumptions
- `productUrl` = the shared bquartz/techlam listing page for every matched
  colour (site has no deeper per-colour URL structure to link to).
- BQuartz "polished" is the library's implicit default (no "polished" suffix
  in our colour names) so it is stripped when matching; "matt" IS kept
  because our library genuinely holds separate "X matt" entries. Techlam
  finish words (Matt/3D Textured) are always stripped -- our sintered colour
  names never carry a finish suffix; finish is recorded in `details` instead.
- Cadiz (BQuartz) is explicitly captioned "NEW (arriving end of August 2026)"
  on the site and confirmed by the price book (`_pb_missing.json`, stock=No)
  -- created with a real slab photo despite not yet being in stock.
- Colossal Cream, Forest, Salina Ivory (Techlam) are on the site and in the
  price book's missing list -- created.
- "Bianco Bello" (library BQuartz colour) has no matching tile on the current
  bquartz page -- left untouched (existing slab image kept), reported above;
  may be discontinued on the supplier's site or renamed.
- "Fior Di Bosco" and "Taj Mahal" (Techlam tiles) are not in the price book
  under any B-Stone row and have no library entry -- not created per the
  "only create entries the price book confirms" rule; reported as extra
  ranges we don't currently stock.
- No closeup/texture imagery exists anywhere on bstoneuk.co.uk for either
  material -- 0 closeups added (not a gap in this harvest, a gap on the
  supplier's site).
- Room photos exist only for BQuartz (17 of 25 matched colours had at least
  one `/inspiration/bquartz-*` post); Techlam/sintered colours have none.
- Price book remains the sizing authority; `slabSizes` from
  `hl.load_pricebook("B-Stone")` where available.

## Re-run
```
python tools/harvest_bstone.py             # re-scrape (cached; delete tools/_cache/bstone to force)
python tools/reconcile_bstone.py --report   # dry run, prints the match table
python tools/reconcile_bstone.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
