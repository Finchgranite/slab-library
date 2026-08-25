"""Reconcile tools/wws-harvest.json (see harvest_wws.py) with the library
(supplier "World Wide Stones", 54 engineered entries -- 41 quartz + 13
porcelain; no natural stone for this supplier). --report prints the match
table and changes nothing; --apply downloads originals, writes webps, then
patches slabs.json in ONE short harvest_lib.patch_library() call (per
HARVEST-SPEC.md's concurrency rule), and writes the two contact sheets +
REPORT.md.

Rules (HARVEST-SPEC.md):
  - image.status == "slab" (42 entries): main image is NEVER replaced.
    productUrl/slabSizes/details/gallery are still filled in.
  - status "missing" or "closeup-only" (12 entries: Ambient Cemento, Borini,
    Brooklyn "25", Calacatta Light, Crimson Frost, Grey Coconut Sparkle,
    Levante Grey, New Calacatta Gold, New Carrara Frost, Noir St Laurent,
    Raw Concrete, Sahara Waves): if harvest_wws found a slab image, download
    it and set/promote status to "slab". If not (Borini's site pages only
    have square texture crops, no ~landscape/portrait slab shot), status is
    left as-is and it's reported "still no slab".
  - slabSizes always taken from the price book (authority); site "Slab size:"
    text is not used (price book had every WWS colour/thickness covered).
  - 45 of 54 existing productUrls are `?s=` search-query placeholders -- every
    one matched by MANUAL_MAP gets replaced with the real product URL.
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "World Wide Stones"
QUARTZ_DEST = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "World wide stones")
PORCELAIN_DEST = os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED", "WORLD WIDE STONES")

apply_mode = "--apply" in sys.argv

data = json.load(open(os.path.join(SCRATCH, "wws-harvest.json"), encoding="utf-8"))
manifest = data["manifest"]
unmatched_site = data["unmatched_site"]

lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER and not r.get("naturalStone")]
by_colour = {e["colour"]: e for e in entries}

pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_new_main = n_upgraded = n_closeups = n_rooms = n_filled_meta = n_dl_fail = 0
dl_cache = {}


def dest_for(entry):
    return PORCELAIN_DEST if entry["material"] == "Porcelain" else QUARTZ_DEST


def dl(url, colour, dest_root):
    if not apply_mode:
        return None
    if url in dl_cache:
        return dl_cache[url]
    fn = url.split("/")[-1].split("?")[0]
    try:
        data_, used_url = hl.fetch_best(url, supplier="wws", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        dl_cache[url] = None
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    p = hl.save_original(data_, dest_root, colour, used_fn)
    dl_cache[url] = p
    return p


for colour, entry in sorted(by_colour.items()):
    rec = manifest.get(colour)
    if not rec or rec.get("error"):
        rows_out.append((colour, "NO SITE PAGE" if not rec else f"FETCH-FAIL {rec['error']}", "-", "-"))
        continue

    pb_row = pb.get(colour)
    slab_sizes = hl.format_slab_sizes(pb_row["sizes"]) if pb_row and pb_row["sizes"] else ""
    cur_status = entry["image"]["status"]
    will_set_main = bool(rec.get("slab") and cur_status in ("missing", "closeup-only"))
    action = f"{cur_status}->slab" if will_set_main else cur_status
    rows_out.append((colour, "match", action, f"{len(rec.get('closeups', []))}cu/{len(rec.get('rooms', []))}rm"))

    if not apply_mode:
        continue

    entry["productUrl"] = rec["url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    finishes = ", ".join(sorted(pb_row["finishes"])) if pb_row and pb_row["finishes"] else ""
    range_label = "Techlam range" if "techlam" in (rec.get("h1") or "").lower() else entry["material"]
    bits = [range_label]
    if slab_sizes:
        bits.append(f"Slab size(s): {slab_sizes}")
    if finishes:
        bits.append(f"Finish: {finishes}")
    entry["details"] = ". ".join(bits)
    site_name = rec.get("index_name") or rec.get("h1")
    if site_name and site_name.lower() != colour.lower():
        aliases = entry.setdefault("aliases", [])
        if site_name not in aliases:
            aliases.append(site_name)
    n_filled_meta += 1

    dest_root = dest_for(entry)

    if will_set_main:
        p = dl(rec["slab"], colour, dest_root)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            entry["image"] = {"file": fn, "status": "slab", "source": rec["url"], "borrowedFrom": ""}
            if was_missing:
                n_new_main += 1
            else:
                n_upgraded += 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "NEW" if was_missing else "UPGRADED"))
        else:
            n_dl_fail += 1
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
    else:
        mains_sheet.append((colour, None, "still missing"))

    # gallery: current main (as kind=slab if it's a real slab) + closeups + rooms
    gallery = []
    if entry["image"].get("file") and entry["image"]["status"] == "slab":
        gallery.append(dict(entry["image"], kind="slab"))
    ci = ri = 0
    for u in rec.get("closeups", []):
        p = dl(u, colour, dest_root)
        if not p or not os.path.exists(p):
            continue
        ci += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
        gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": rec["url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
        n_closeups += 1
    for u in rec.get("rooms", []):
        p = dl(u, colour, dest_root)
        if not p or not os.path.exists(p):
            continue
        ri += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
        gallery.append({"file": fn, "status": "representative", "kind": "room", "source": rec["url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

still_missing = sorted(c for c, e in by_colour.items() if e["image"]["status"] != "slab")
unmatched_pb = sorted(set(pb.keys()) - set(manifest.keys()) - {c for c, r in manifest.items() if r.get("error")})

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))
print()
print(f"library colours: {len(entries)} | matched to a site page: {sum(1 for r in rows_out if r[1] == 'match')}")
print(f"unmatched extra site products (not in price book): {len(unmatched_site)}")
print(f"still not status=slab after this run (site has no usable slab shot): {still_missing}")

if apply_mode:
    ids_touched = {e["id"]: e for e in entries}

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, edited in ids_touched.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == SUPPLIER and not s.get("naturalStone"):
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly set: {n_new_main} | mains upgraded: {n_upgraded} | closeups: {n_closeups} | "
          f"rooms: {n_rooms} | download failures: {n_dl_fail}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "wws-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "wws-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "wws-REPORT.md")
    unmatched_lines = "\n".join(
        f"- `{u['slug']}` ({u['url']}) -- {u['note'] or 'no price-book match'}" for u in unmatched_site)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# World Wide Stones harvest report

Source: `wp-sitemap-posts-page-1.xml` (site's live sitemap endpoint started
404-ing mid-discovery -- a full URL snapshot taken just before that is used
instead, `tools/_cache/wws/_all_urls.txt`; site structure is static WordPress
pages so this is safe) + the `/quartz-slabs/` and `/porcelain-slabs/` index
pages, which are the authority for display name + canonical URL per colour
(several slugs are stale, e.g. `/quartz-slabs/irini-classic/` displays
"Sahara Waves"). 45 of 54 stored productUrls were `www.worldwidestones.co.uk/
?s=...` search-query placeholders, not real pages; all matched colours get
the real product URL from this run.

Each colour page is a bare Elementor page (H1 name, "Slab size: LxWxTmm -
In stock" text, 1-4 photos) with NO consistent slab/closeup/room filename
convention -- classified by filename hint first (few pages: "slab",
"close-up"), then real downloaded-pixel aspect ratio (WWS "slab" photos run
1.3-2.8:1 landscape OR ~0.6-0.85:1 portrait "whole slab stood in the yard"
shots -- both accepted as slab candidates, portrait only when it's the first
photo on the page). The index page's own "*close*"-named thumbnail is always
added as a bonus closeup when found.

## Counts
- Library colours (World Wide Stones, engineered): {len(entries)}
- Matched to a real site page: {sum(1 for r in rows_out if r[1] == 'match')}
- Mains newly set (was missing): {n_new_main}
- Mains upgraded (was closeup-only): {n_upgraded}
- Main downloads that failed: {n_dl_fail}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Still not status=slab after this run: {still_missing}
- Price-book colours with no site match this run: {unmatched_pb}
- Extra site products with no price-book match ({len(unmatched_site)}):
{unmatched_lines}

## Assumptions to confirm with the supplier
- "Calacatta Oro Frost" (pb, was missing productUrl) matched to site page
  `/quartz-slabs/calacatta-oro-duplicate-941/` which displays as "Calacatta
  Oro Claro" -- name doesn't literally say "Frost"; closest available site
  product by process of elimination (a separate orphaned `calacatta-oro-nuevo`
  page ["Calacatta Oro Nuevo"] also exists and was NOT used). Worth a supplier
  check.
- "New Carrara Frost" (pb) matched to `/quartz-slabs/carrara-frost/`, which
  displays as "Carrara Frost (Shimmer)" -- dropped the site's "New"/kept pb
  naming; token overlap + process of elimination (no plain "Carrara Frost" pb
  row exists).
- "Noir St Laurent" (pb, porcelain, was fully missing) matched to
  `/porcelain-slabs/noir/`, which displays as "Techlam Noir" -- NOT literally
  named "Noir St Laurent" anywhere on site. `/porcelain-slabs/noir-st-laurent/`
  (the slug you'd expect) actually displays "St Laurent" and was used for the
  *other* pb row instead (already had a slab main, confirmed by H1). This pair
  is the least confident match in the run -- please confirm both with WWS.
- Porcelain "Taj Mahal": the price book has a distinct Porcelain Taj Mahal row
  (Matt finish) separate from the Quartz Taj Mahal row, and the site confirms
  a real `/porcelain-slabs/taj-mahal/` page -- but the library only has ONE
  "Taj Mahal" entry (material Quartz). No new entry was created this run
  (out of scope per this job's fixed 54-entry brief); flagging for the
  orchestrator to decide whether to add a Porcelain Taj Mahal entry.
- `slabSizes` always taken from the price book, not the site's own "Slab
  size:" text (price book had every colour/thickness covered already).

## Site products confirmed NOT in our price book (no entry created)
{len(unmatched_site)} extra ranges/variants -- see list above. Notable:
Techlam Alhambra/Bellagio/Bronze (whole extra Techlam sub-lines), several
"Super Jumbo"/"Extra"/"Y2"/"Nuevo" size-variant duplicate pages for colours
we already stock in the standard size, and Patagonia Gris (site says
"discontinuing in 2026").

## Re-run
```
python tools/harvest_wws.py             # re-scrape (cached; delete tools/_cache/wws to force)
python tools/reconcile_wws.py --report  # dry run, prints the match table
python tools/reconcile_wws.py --apply   # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
