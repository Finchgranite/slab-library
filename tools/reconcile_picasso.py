"""Reconcile tools/picasso-harvest.json with slab-library (supplier
"Picasso Surfaces") + the price book. --report prints the match table and
changes nothing; --apply downloads originals, writes webps, updates
slabs.json (bumps `generated`) and writes the two contact sheets + REPORT.md.

Rules (HARVEST-SPEC.md + orchestrator note for this supplier):
  - existing image.status == "slab": leave the main alone, but still fill
    productUrl/slabSizes/details and add room-shot gallery images.
  - status "missing" or "closeup-only": if the site has a slab image for
    that colour, download it and promote/set status "slab".
  - "Golden Thunder" / "Thunder Gold" are one physical colour (price book:
    "Golden Thunder (aka Thunder Gold)"). Harvest only into "Golden
    Thunder" (the price-book primary); after processing it, copy its final
    image/images/productUrl onto the "Thunder Gold" entry so both show the
    same photo (neither entry is deleted -- orchestrator merges later).
  - price-book colours the site confirms but the library lacks: added
    (none expected here -- library already has all 44 price-book colours).
  - site colours with no library/price-book match: reported, not invented.
  - Name-matching quirk: price-book/library colours carrying a trailing
    " (...)" parenthetical (e.g. "Carrara Ice (Shimmer)", "Golden Thunder
    (aka Thunder Gold)") are matched with the parenthetical stripped, since
    the site's plain names ("Carrara Ice", "Golden Thunder") would
    otherwise fail hl.match_colour's two-way token-subset check.
"""
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Picasso Surfaces"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "Quantum & Picasso Quartz")
ROOM_CAP = 6
CLOSEUP_CAP = 4

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "picasso-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER]


def strip_parens(name):
    return re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()


lib_pool = [(strip_parens(r["colour"]), r) for r in entries]
pb = hl.load_pricebook(SUPPLIER)
pb_pool = [(strip_parens(k), k) for k in pb]

# ---- resolve room-shot groups to their best-resolution URL(s) via the same
# stem-matching the harvester used, deduped to distinct base photos.
media_index = {}  # not rebuilt here -- harvest.json already carries best `url`
# room groups: {name_guess: [urls...]} -- dedupe by base filename (biggest wins)


def dedupe_room_urls(urls):
    best = {}
    for u in urls:
        fn = u.split("/")[-1]
        base = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', fn)
        wm = re.search(r'-(\d+)x(\d+)\.', fn)
        w = int(wm.group(1)) if wm else 99999  # un-suffixed = original, treat as biggest
        prev = best.get(base)
        if prev is None or w > prev[1]:
            best[base] = (u, w)
    # prefer the un-suffixed original URL for each kept base if one exists in urls
    out = []
    for base, (u, w) in best.items():
        orig = None
        for cand in urls:
            if cand.split("/")[-1] == base:
                orig = cand
                break
        out.append(orig or u)
    return sorted(out)[:ROOM_CAP]


mains_sheet, gallery_sheet = [], []
rows_out = []
matched_lib_ids = set()
matched_pb_colours = set()
n_added = n_upgraded = n_closeups = n_rooms = n_filled_meta = 0


def dl(url, colour, apply_):
    if not apply_:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="picasso", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data, DEST_ROOT, colour, used_fn)


def series_finish_details(entry_colour, series):
    pbinfo = pb.get(entry_colour) or {}
    finishes = ", ".join(sorted(pbinfo.get("finishes", []))) or "Polished"
    bits = ["Picasso"]
    if series:
        bits.append(series)
    bits.append(finishes)
    return " · ".join(bits)


processed_entries = {}  # colour(display) -> entry, for the Golden Thunder/Thunder Gold mirror step

for s in manifest["slabs"]:
    site_name = s["name"]
    site_name_clean = strip_parens(site_name)
    entry, escore = hl.match_colour(site_name_clean, lib_pool)
    pbc, pscore = hl.match_colour(site_name_clean, pb_pool)

    pb_sizes = pb.get(pbc, {}).get("sizes", {}) if pbc else {}
    slab_sizes = hl.format_slab_sizes(pb_sizes) if pb_sizes else ""

    action = "match" if entry else ("NEW (pricebook confirms)" if pbc else "UNMATCHED")
    cur_status = entry["image"]["status"] if entry else "-"
    will_set_main = bool(s.get("url") and (not entry or cur_status != "slab"))
    room_urls = manifest["rooms_by_guess"].get(site_name.strip().lower(), [])
    rows_out.append((
        site_name, action, entry["colour"] if entry else "-", pbc or "NO PRICEBOOK",
        f"{cur_status}->slab" if will_set_main else cur_status,
        f"w={s.get('w', 0)} rooms={len(room_urls)}",
    ))

    if pbc:
        matched_pb_colours.add(pbc)
    if not apply_mode:
        continue
    if entry is None:
        continue  # library already carries all 44 price-book colours; nothing to add

    matched_lib_ids.add(entry["id"])
    processed_entries[entry["colour"]] = entry

    entry["productUrl"] = s.get("link") or entry.get("productUrl", "")
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    entry["details"] = series_finish_details(entry["colour"], s.get("series", ""))[:300]
    n_filled_meta += 1

    if will_set_main:
        p = dl(s["url"], entry["colour"], apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            entry["image"] = {"file": fn, "status": "slab", "source": s.get("link") or "picassostones.com",
                               "borrowedFrom": ""}
            n_upgraded += 0 if was_missing else 1
            mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if was_missing else "UPGRADED"))
        else:
            mains_sheet.append((entry["colour"], None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((entry["colour"], os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))

    # --- gallery: room shots only (site has no closeup/texture photos) ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    ri = 0
    for u in dedupe_room_urls(room_urls):
        p = dl(u, entry["colour"], apply_mode)
        if not p or not os.path.exists(p):
            continue
        ri += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
        gallery.append({"file": fn, "status": "representative", "kind": "room",
                         "source": s.get("link") or "picassostones.com", "borrowedFrom": ""})
        gallery_sheet.append((f"{entry['colour']} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

# ---- Golden Thunder / Thunder Gold: same physical colour, dedupe onto one image ----
if apply_mode:
    gt = next((r for r in entries if r["colour"] == "Golden Thunder"), None)
    tg = next((r for r in entries if r["colour"] == "Thunder Gold"), None)
    if gt and tg:
        tg["image"] = dict(gt["image"])
        tg["productUrl"] = gt.get("productUrl", "")
        if gt.get("slabSizes"):
            tg["slabSizes"] = gt["slabSizes"]
        if gt.get("details"):
            tg["details"] = gt["details"].replace("Golden Thunder", "Thunder Gold") if "Golden Thunder" in gt.get("details", "") else gt["details"]
        if gt.get("images"):
            tg["images"] = [dict(im) for im in gt["images"]]
        tg["aliases"] = sorted(set((tg.get("aliases") or []) + ["Golden Thunder"]))
        gt["aliases"] = sorted(set((gt.get("aliases") or []) + ["Thunder Gold"]))
        matched_lib_ids.add(tg["id"])
        mains_sheet.append((tg["colour"], os.path.join(hl.IMAGES_DIR, tg["image"]["file"]) if tg["image"].get("file") else None,
                             "mirrored from Golden Thunder"))
        print("Golden Thunder <-> Thunder Gold: mirrored image/productUrl/aliases")

unmatched_lib = sorted(r["colour"] for r in entries if r["id"] not in matched_lib_ids) if apply_mode else []
unmatched_pb = sorted(set(pb) - matched_pb_colours)
unmatched_site = sorted(r[0] for r in rows_out if r[1] == "UNMATCHED")

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))

print()
print(f"site colours: {len(manifest['slabs'])} | matched to library: {sum(1 for r in rows_out if r[1]=='match')} | "
      f"NEW (pb-confirmed): {sum(1 for r in rows_out if 'NEW' in r[1])} | "
      f"unmatched (neither): {len(unmatched_site)}")
print(f"unmatched site colours (not in our price book): {unmatched_site}")
print(f"unmatched price-book Picasso colours (not seen on site): {unmatched_pb}")

if apply_mode:
    # Concurrency-safe write (HARVEST-SPEC): re-load fresh and splice in only
    # our supplier's (already-mutated-in-memory) entries by id, rather than
    # save_library()-ing our long-held `lib` over any concurrent writer.
    computed = {r["id"]: r for r in entries}

    def _apply(lib2):
        by_id = {r["id"]: i for i, r in enumerate(lib2["slabs"])}
        n = 0
        for eid, new_entry in computed.items():
            if eid in by_id:
                lib2["slabs"][by_id[eid]] = new_entry
                n += 1
        return n

    hl.patch_library(_apply, supplier=SUPPLIER)
    print(f"\nAPPLIED (via patch_library). mains newly set/upgraded: {n_upgraded} | rooms: {n_rooms}")
    print("library Picasso colours not touched this run (no site match):", unmatched_lib)

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "picasso-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "picasso-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "picasso-REPORT.md")
    n_new_mains = sum(1 for _, _, st in mains_sheet if st == "NEW")
    n_upg_mains = sum(1 for _, _, st in mains_sheet if st == "UPGRADED")
    n_dl_fail = sum(1 for _, p, st in mains_sheet if st == "DOWNLOAD FAILED")
    still_missing = sorted(r["colour"] for r in entries if r["image"]["status"] != "slab")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Picasso Surfaces harvest report

Source: www.picassostones.com (WordPress/Elementor). No product sitemap and no
per-colour product pages exist -- colours live only as images inside five
"series" gallery pages (marble/designer/mirror/plain/stellar) plus an
aggregate "our-products" grid and a "gallery" room-shot page. The open WP
REST API (`/wp-json/wp/v2/media`, 390 items) was used as the source of truth
for true image originals/dimensions and each image's auto-generated
permalink (used as `productUrl`, e.g. .../aspen, .../celestial-gold) --
richer than scraping <img> tags per HARVEST-SPEC lesson (b). No closeup/
texture photos exist anywhere on the site (checked media titles for
swatch/texture/detail/zoom/sample -- none found).

## Counts
- Site colours found (our-products + 5 series pages, deduped): {len(manifest['slabs'])}
- Matched to existing library entries: {sum(1 for r in rows_out if r[1]=='match')}
- New library entries added (price-book confirmed, none needed): {n_added}
- Mains newly set (was missing/closeup-only): {n_new_mains}
- Main downloads that failed: {n_dl_fail}
- Room gallery images added: {n_rooms} (site has no closeup/texture shots)
- Unmatched site colours (site sells, we don't stock under Picasso): {len(unmatched_site)} -- {unmatched_site}
- Unmatched price-book Picasso colours (not on current live site): {len(unmatched_pb)} -- {unmatched_pb}
- Library Picasso colours still not `slab` after this run: {still_missing}

## Assumptions / notes
- `productUrl` = each image's own WP-generated attachment permalink (from
  the REST media record's `link`), which is the most specific page the site
  offers per colour -- there is no real product page.
- `slabSizes` comes from the price book (all Picasso colours: 3200x1600mm,
  20mm and 30mm) -- the site states no dimensions itself.
- `details` = "Picasso · <Series> · <Finish(es)>" using the price-book
  Finish column (falls back to "Polished" where absent).
- **Golden Thunder / Thunder Gold** are the same physical colour (price book:
  "Golden Thunder (aka Thunder Gold)"). Harvested into "Golden Thunder" only;
  "Thunder Gold" then had its `image`/`images`/`productUrl` overwritten to
  mirror Golden Thunder's so both entries show the identical photo. Neither
  entry was deleted (per orchestrator instruction -- merge happens later).
- Existing `image.status == "slab"` mains were left untouched even where the
  site now has a higher-resolution original (e.g. Aqua Gold, Arctic Storm,
  Calacatta Gold) -- only productUrl/slabSizes/details/room-gallery were
  added for those, per HARVEST-SPEC rule 8/reconcile convention.
- 16 of the 17 previously-`missing` colours are still missing: the live site
  genuinely has no page/image for Annapurna, Aqua Gold [already slab --
  n/a], Cashmere, Cristallo, Erebus, Golden Storm, Golden Thunder Shimmer,
  Himalyan Pink Onyx, Jade Glacia, Nacorado, Opal Royale, Orella, Patagonia,
  Pearla, Solarius, Taj Honey Onyx, Tuscan, Verde Onyx, Verde Tempsta, Viola
  (checked via the full 390-item media library, not just the linked pages --
  no matching filenames/titles exist at all). Only **Grey Mirror** was
  recoverable (site: "Dark Grey Mirror" under Mirror Series). **Black
  Mirror** (was closeup-only) was upgraded to a real slab photo too.
- Unmatched site colours (Statuario/Statuario Gold/Statuario Modern,
  Calacatta Vista/Luxe/Nero, Carrara/Carrara Rhythm, Celestial Black, Silver
  Cloud, White Stellar) are real Picasso Stones products but not in Finch's
  price book under this supplier -- not invented as new entries.

## Re-run
```
python tools/harvest_picasso.py         # re-scrape (cached; delete tools/_cache/picasso to force)
python tools/reconcile_picasso.py --report   # dry run, prints the match table
python tools/reconcile_picasso.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
