"""Reconcile tools/cosentino-harvest.json with slab-library (Cosentino Dekton +
Cosentino Silestone) + the price book. --report prints the match table and
changes nothing; --apply downloads originals from the assetstools.cosentino.com
CDN, writes webps, updates slabs.json (bumps `generated`), writes contact
sheets + REPORT.md.

Images: assetstools.cosentino.com/api/v1/bynder/color/<CODE>/tablahd/... (full
slab) and .../detalle/... (closeup) -- confirmed unprotected/unrated-limited,
unlike www.cosentino.com itself (Sucuri + Crawl-delay:10, see harvest_cosentino.py
docstring). No CDN room-shot pattern was found this run, so no room images.

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": leave the main alone; only "missing"/
    "closeup-only" entries get a new main.
  - productUrl filled for any entry with a known brand/slug, confirmed or not
    (legacy slugs came from a real 2026-07-19 catalogue-card scrape).
  - slabSizes/details filled from the price book (thicknesses, finishes, sizes)
    for every entry that lacks them, regardless of image outcome.
  - site "site_only" rows (colour on the widget, no library/price-book match)
    are reported, never turned into new entries.
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
DEST_ROOT = {
    "Cosentino Dekton": os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED", "COSENTINO DEKTON"),
    "Cosentino Silestone": os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "COSENTINO SILESTONE"),
}

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "cosentino-harvest.json"), encoding="utf-8"))
lib = hl.load_library()
by_id = {e["id"]: e for e in lib["slabs"]}

pb = {"Cosentino Dekton": hl.load_pricebook("Cosentino Dekton"),
      "Cosentino Silestone": hl.load_pricebook("Cosentino Silestone")}

mains_sheet, gallery_sheet = [], []
rows_out = []
site_only_rows = []
n_new_main = n_upgraded_main = n_closeups = n_urls_filled = n_sizes_filled = n_details_filled = 0
dl_fail = []


def dl(url, colour, supplier, tag):
    if not apply_mode:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="cosentino", cache_key=f"{tag}-{colour}-{fn}"[:150],
                                        polite_delay=1.5)
    except Exception as e:
        dl_fail.append(f"{colour} <- {url}: {e}")
        return None
    return hl.save_original(data, DEST_ROOT[supplier], colour, fn)


for r in manifest:
    if r.get("site_only"):
        site_only_rows.append(r)
        continue

    e = by_id[r["id"]]
    supplier = r["supplier"]
    code = r.get("code")
    will_set_main = bool(code and r["status"] != "slab")
    rows_out.append((
        e["colour"], supplier, code or "-",
        f"{r['status']}->slab" if will_set_main else r["status"],
        "confirmed" if r.get("url_confirmed") else ("legacy" if code else "-"),
        "Y" if e.get("productUrl") else "N",
    ))

    if not apply_mode:
        continue

    # productUrl
    if not e.get("productUrl") and r.get("slug"):
        e["productUrl"] = f"https://www.cosentino.com/en-gb/colours/{r['brand']}/{r['slug']}/"
        n_urls_filled += 1

    # slabSizes + details from price book
    pbinfo = pb[supplier].get(e["colour"])
    if pbinfo:
        if not e.get("slabSizes") and pbinfo["sizes"]:
            e["slabSizes"] = hl.format_slab_sizes(pbinfo["sizes"])
            n_sizes_filled += 1
        if not e.get("details") and pbinfo["finishes"]:
            brand_label = "Dekton" if supplier == "Cosentino Dekton" else "Silestone"
            fins = ", ".join(sorted(pbinfo["finishes"]))
            plural = "finish" if len(pbinfo["finishes"]) == 1 else "finishes"
            e["details"] = f"{brand_label} · {fins} {plural}"
            n_details_filled += 1

    if not code:
        if e["image"].get("file"):
            mains_sheet.append((e["colour"], os.path.join(hl.IMAGES_DIR, e["image"]["file"]), "kept"))
        continue

    # --- main slab image ---
    if will_set_main:
        url = f"https://assetstools.cosentino.com/api/v1/bynder/color/{code}/tablahd/{code}-fullslab.jpg"
        p = dl(url, e["colour"], supplier, "slab")
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, e["id"])
            was_missing = r["status"] == "missing"
            e["image"] = {"file": fn, "status": "slab", "source": "cosentino.com", "borrowedFrom": ""}
            if was_missing:
                n_new_main += 1
            else:
                n_upgraded_main += 1
            mains_sheet.append((e["colour"], os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if was_missing else "UPGRADED"))
        else:
            mains_sheet.append((e["colour"], None, "DOWNLOAD FAILED"))
    elif e["image"].get("file"):
        mains_sheet.append((e["colour"], os.path.join(hl.IMAGES_DIR, e["image"]["file"]), "kept"))

    # --- closeup gallery (skip if one already present) ---
    existing_gallery = e.get("images") or []
    has_closeup = any(g.get("kind") == "closeup" for g in existing_gallery)
    if not has_closeup:
        curl = f"https://assetstools.cosentino.com/api/v1/bynder/color/{code}/detalle/{code}-detail.jpg"
        p = dl(curl, e["colour"], supplier, "closeup")
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{e['id']}--closeup1")
            gallery = [dict(e["image"], kind="slab")] if e["image"].get("file") else []
            gallery += existing_gallery
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup",
                             "source": "cosentino.com", "borrowedFrom": ""})
            e["images"] = gallery
            gallery_sheet.append((f"{e['colour']} CU1", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))

n_missing_no_code = sum(1 for r in rows_out if r[2] == "-" and r[3] not in ("slab",) and "->slab" not in r[3])
print()
print(f"rows: {len(rows_out)} | with code: {sum(1 for r in rows_out if r[2] != '-')} | "
      f"still missing (no code found): {sum(1 for m in manifest if not m.get('site_only') and not m.get('code') and m.get('status') != 'slab')}")
print(f"site colours seen but no library/price-book match: {len(site_only_rows)}")
for r in site_only_rows:
    print("  SITE-ONLY:", r["supplier"], r["colour"], r["code"], r["slug"])

if apply_mode:
    for supplier in ("Cosentino Dekton", "Cosentino Silestone"):
        def apply(lib_, supplier=supplier):
            for i, s in enumerate(lib_["slabs"]):
                if s.get("supplier") == supplier and s["id"] in by_id:
                    lib_["slabs"][i] = by_id[s["id"]]
            return {}
        hl.patch_library(apply, supplier=supplier)

    print(f"\nAPPLIED. mains new: {n_new_main} | mains upgraded: {n_upgraded_main} | closeups: {n_closeups} | "
          f"productUrl filled: {n_urls_filled} | slabSizes filled: {n_sizes_filled} | details filled: {n_details_filled}")
    if dl_fail:
        print("DOWNLOAD FAILURES:")
        for f in dl_fail:
            print(" ", f)

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "cosentino-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "cosentino-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = [(m["supplier"], m["colour"]) for m in manifest
                      if not m.get("site_only") and not m.get("code") and m.get("status") != "slab"]
    report_path = os.path.join(hl.REPORTS_DIR, "cosentino-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Cosentino (Dekton + Silestone) harvest report

Source: www.cosentino.com/en-gb (Sucuri CloudProxy-protected, `Crawl-delay: 10` --
curl gets a JS-challenge stub, not real pages). A real browser pass on
/en-gb/colours/dekton/ found a cross-brand "all colours" widget (div.inspiration
cards, ~157 across all 5 Cosentino brands) whose `data-lazy-src` embeds each
colour's asset CODE. That gave 65 Dekton + 49 Silestone codes with CONFIRMED
live hrefs in one page load. Same-origin fetch() from inside that tab was tried
next to look up the ~28 colours the widget didn't surface, but cosentino.com
started hard-failing requests (net error / AbortError) after roughly 10 rapid
fetches -- consistent with the `Crawl-delay: 10` in robots.txt. Per HARVEST-SPEC
("never hammer a site" / bot-blocked-site guidance), that lookup was stopped
rather than retried in a loop.

The image CDN -- assetstools.cosentino.com -- is a separate, unprotected host:
given any CODE, `tablahd/<CODE>-fullslab.jpg` (full slab, ~20-30MB) and
`detalle/<CODE>-detail.jpg` (texture closeup) both resolve directly, no
rate-limiting seen. No CDN pattern for room/kitchen shots was found (ambiente/
cocina/kitchen/room/textura sub-paths all 400) -- real per-colour room photos
exist in the (rate-limited) product-page HTML, e.g. `dekton-kitchen-laurent.jpg`,
so room images are OUT OF SCOPE this run.

## Counts
- Cosentino Dekton library entries: 94 | Cosentino Silestone: 74
- Colour codes resolved (widget-confirmed or 2026-07-19-pilot legacy): {sum(1 for r in rows_out if r[2] != '-')} / {len(rows_out)}
- Mains newly set (was missing): {n_new_main}
- Mains upgraded (was closeup-only): {n_upgraded_main}
- Closeup gallery images added: {n_closeups}
- productUrl filled: {n_urls_filled}
- slabSizes filled (from price book): {n_sizes_filled}
- details filled (from price book finishes): {n_details_filled}
- Download failures: {len(dl_fail)}

## Still missing (no code found this run -- price book confirms all of these as
currently sold; a slow, individually-throttled (10s+ apart) product-page pass
is the recommended follow-up)
Dekton (24): Blaze, Daze, Galema, Kairos, Kairos22, Laguna, Limbo, Liquid Embers,
Liquid Shell22, Malibu, Micron, Milar, Nayla, Nilium, Nilium22, Olimpo, Opera,
Orix, Sasea, Sirocco, Splendor, Strato, Vegha, Vigil
Silestone (4): Et Noir (currently closeup-only, left as-is), Helix, Liguria
Black Marble, Polaris Marble

## Site colours seen (widget) with no library/price-book match -- NOT added
- Dekton: Akara (KCK), Grekk (KTA), Talma (KRW), Nordal (NOK), Kobuk (RHN),
  Borealis (BOK) -- none of these six names are in supplier-price-book.csv
  under "Cosentino Dekton"; genuinely new colours we don't currently stock.
- Dekton: Grafite (P5C) and Aura (AKC) -- the site's *generic* colour pages;
  price book only has "Vk04 Grafite" and "Aura15"/"Aura22" (thickness/line
  suffixed), which the name-matcher correctly refused to merge automatically
  (different token sets = different product identity per HARVEST-SPEC). These
  may be the same physical colour under a refreshed listing, or a genuinely
  different current SKU -- flagging for a human/orchestrator visual check
  rather than guessing.
- Silestone: "White Zeus" (BZJ) -- already resolved historically as library
  colour "Blanco Zeus" (alias, productUrl + image already set); no action
  needed, listed here only because the automated matcher doesn't see the
  Spanish/English naming link.

## Assumptions
- Price book is the naming/size authority; `slabSizes`/`details` are price-book
  only this run (no per-page finish/series text -- see Crawl-delay note above).
- Existing `image.status == "slab"` entries were left alone.
- No entries were added or deleted -- only existing library rows were enriched.

## Re-run
```
python tools/harvest_cosentino.py            # rebuild manifest (pure computation, no network)
python tools/reconcile_cosentino.py --report # dry run, prints the match table
python tools/reconcile_cosentino.py --apply  # writes images/ + slabs.json
```
To chase the 28 still-missing colours: fetch each product page individually
from a real browser tab with 10+ seconds between requests (see docstring of
harvest_cosentino.py), or wait for cosentino.com's rate-limit window to clear
and retry the same same-origin-fetch approach in small batches.
""")
    print("wrote", report_path)
