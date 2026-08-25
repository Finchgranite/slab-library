"""Reconcile tools/ksg-harvest.json with slab-library (supplier "KSG",
naturalStone == False only -- the 71 natural-stone KSG entries are OUT OF
SCOPE and never touched) + the price book. --report prints the match table
and changes nothing; --apply downloads originals, writes webps, updates
slabs.json via harvest_lib.patch_library (bumps `generated`) and writes the
two contact sheets + REPORT.md.

Image-status rules (HARVEST-SPEC.md):
  - existing image.status == "slab": main image left untouched; productUrl/
    slabSizes/details/aliases still filled in, and a closeup gallery image is
    still added if the site has one this main didn't already carry.
  - "missing"/"closeup-only" + a genuine full-slab photo found on-site:
    downloaded and promoted to "slab".
  - "missing" + only a close-up crop found (no full-slab photo at all --
    White Shimmer, Carrara Gold): promoted to "closeup-only", the crop is
    used AS the main image (not duplicated into the gallery too).
  - Calacatta Gold Shimmer: confirmed no page on ksguk.co.uk (404) -- left
    untouched, reported to ask KSG.
"""
import json
import os
import re
import sys
import urllib.parse

import harvest_lib as hl
from harvest_ksg import TARGETS, SITE_EXTRAS_NOT_IN_PRICEBOOK

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "KSG"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "KSG Quartz")

apply_mode = "--apply" in sys.argv

manifest = {m["colour"]: m for m in json.load(open(os.path.join(SCRATCH, "ksg-harvest.json"), encoding="utf-8"))}
lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER and not r.get("naturalStone")]
by_colour = {r["colour"]: r for r in entries}

pb = hl.load_pricebook(SUPPLIER)

ALIASES = {
    "Seville": ["Calacatta Light (Seville)"],
    "Santorini": ["Calacatta Nero (Santorini)"],
}

ODDITIES = []  # noted for the report, not blocking


def dl(url, colour, apply_):
    if not apply_:
        return None
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="ksg", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = urllib.parse.unquote(used_url.split("/")[-1].split("?")[0])
    return hl.save_original(data, DEST_ROOT, colour, used_fn)


def check_aspect(path, want):
    """want: 'slab' (~1.8-2.3) or 'closeup' (anything). Returns a warning
    string or None."""
    try:
        from PIL import Image
        im = Image.open(path)
        w, h = im.size
        ar = max(w, h) / min(w, h) if min(w, h) else 0
        if want == "slab" and not (1.5 <= ar <= 2.6):
            return f"aspect {w}x{h} ({ar:.2f}:1) outside slab range"
    except Exception as e:
        return f"could not check aspect: {e}"
    return None


rows_out = []
mains_sheet, gallery_sheet = [], []
n_new_main = n_upgraded = n_closeup_only = n_closeups = n_dl_fail = n_meta_only = 0
aspect_warnings = []

for colour, slug in TARGETS.items():
    entry = by_colour.get(colour)
    if slug is None:
        rows_out.append((colour, "NO PAGE ON SITE (404)", "-", "ask KSG"))
        continue
    m = manifest.get(colour)
    if entry is None:
        rows_out.append((colour, "NO LIBRARY ENTRY (unexpected)", m["url"] if m else "-", "-"))
        continue
    if m.get("error"):
        rows_out.append((colour, f"FETCH FAIL: {m['error']}", "-", "-"))
        continue

    cur_status = entry["image"]["status"]
    main_url, closeup_url = m.get("main_url"), m.get("closeup_url")
    target_status = "slab" if main_url else ("closeup-only" if closeup_url else cur_status)
    will_change_main = cur_status != "slab" and (main_url or closeup_url)
    closeup_used_as_main = bool(will_change_main and target_status == "closeup-only" and closeup_url)

    pbrow = pb.get(colour, {})
    slab_sizes = hl.format_slab_sizes(pbrow.get("sizes", {})) if pbrow.get("sizes") else (m.get("page_slab_size") or "")
    finishes = sorted(pbrow.get("finishes", set()))
    bits = ["NATUREQ"]
    if m.get("origin"):
        bits.append(m["origin"])
    if finishes:
        bits.append(f"{'/'.join(finishes)} finish")
    details = " · ".join(bits)

    rows_out.append((colour, f"{cur_status}->{target_status}" if will_change_main else f"{cur_status} (kept)",
                      m["url"], slab_sizes or "-"))

    if colour == "Calacatta Shimmer" and main_url and "gold-shimmer" in main_url.lower().replace(" ", "-").replace("%20", "-"):
        ODDITIES.append("Calacatta Shimmer's site photo filename is 'Calacatta Gold Shimmer_r_...' -- "
                         "appears to be a leftover/reused filename on KSG's own Calacatta Shimmer page; "
                         "used as-is since it IS what that page serves.")

    entry["productUrl"] = m["url"]
    if slab_sizes:
        entry["slabSizes"] = slab_sizes
    if details:
        entry["details"] = details
    if colour in ALIASES:
        existing_aliases = set(entry.get("aliases", []))
        new_aliases = sorted(existing_aliases | set(ALIASES[colour]))
        if new_aliases != entry.get("aliases", []):
            entry["aliases"] = new_aliases
    n_meta_only += 1

    if not apply_mode:
        continue

    # --- main image ---
    if will_change_main:
        src_url = main_url if target_status == "slab" else closeup_url
        p = dl(src_url, colour, apply_mode)
        if p and os.path.exists(p):
            warn = check_aspect(p, "slab" if target_status == "slab" else "closeup")
            if warn:
                aspect_warnings.append(f"{colour}: {warn} (source: {src_url})")
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            entry["image"] = {"file": fn, "status": target_status, "source": m["url"], "borrowedFrom": ""}
            if target_status == "slab":
                (n_new_main if was_missing else None)
                if was_missing:
                    n_new_main += 1
                else:
                    n_upgraded += 1
            else:
                n_closeup_only += 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if was_missing else target_status.upper()))
        else:
            n_dl_fail += 1
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))

    # --- gallery: closeup (only if not already used as the main this run) ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    if closeup_url and not closeup_used_as_main:
        p = dl(closeup_url, colour, apply_mode)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup1")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": m["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU1", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
    if len(gallery) > 1:
        entry["images"] = gallery

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

print()
print(f"targets: {len(TARGETS)} | library entries (engineered KSG): {len(entries)} | "
      f"main images changing this run: {sum(1 for r in rows_out if '->' in r[1])}")
print("site colours seen but NOT in price book (not harvested):", SITE_EXTRAS_NOT_IN_PRICEBOOK)

if apply_mode:
    def apply(lib_fresh):
        # entries were mutated on the objects already loaded from `lib`; since
        # patch_library reloads fresh, re-apply the same mutations onto the
        # freshly loaded dict's matching entries by id.
        fresh_by_id = {r["id"]: r for r in lib_fresh["slabs"]}
        n = 0
        for r in entries:
            fr = fresh_by_id.get(r["id"])
            if fr is None:
                continue
            fr.clear()
            fr.update(r)
            n += 1
        return {"entries_written": n}

    result = hl.patch_library(apply, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains -> slab (new): {n_new_main} | mains -> slab (upgraded): {n_upgraded} | "
          f"mains -> closeup-only: {n_closeup_only} | download failures: {n_dl_fail} | "
          f"closeup gallery images added: {n_closeups} | metadata-only updates: {n_meta_only}")
    if aspect_warnings:
        print("ASPECT WARNINGS (check contact sheet):")
        for a in aspect_warnings:
            print(" -", a)

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "ksg-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "ksg-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = sorted(c for c in TARGETS if TARGETS[c] is None)
    report_path = os.path.join(hl.REPORTS_DIR, "ksg-REPORT.md")
    n_no_main = sum(1 for r in rows_out if r[1] == "closeup-only (kept)" or "closeup-only" in r[1])
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# KSG harvest report

Source: https://ksguk.co.uk/NATUREQ (old ASP-style CMS, curl-friendly). Quartz
range is branded "NATUREQ" on-site. Colour list cross-checked against the
NATUREQ index page and the 31 engineered (naturalStone: false) KSG price-book
colours; the 71 natural-stone KSG entries were never touched.

Each product page's "Product Information" block gives `Size:`/`Origin:`
directly. The main slab photo is the page's one visible gallery `<img>`;
close-up crops come from the page's own schema.org JSON-LD `Product.image`
field (which is frequently a DIFFERENT, closer-cropped photo than the gallery
hero) -- for White Shimmer and Carrara Gold the gallery has NO photo at all
("Image Coming Soon" / a mislabelled close-up-only hero) so the JSON-LD /
close-up-named photo was used as the main image instead, with status set to
`closeup-only` rather than `slab`.

## Counts
- Engineered KSG price-book colours: {len(TARGETS)} (natural-stone KSG entries out of scope, untouched)
- Site pages fetched ok: {sum(1 for m in manifest.values() if not m.get('error'))}
- No page on site (404): 1 -- Calacatta Gold Shimmer
- Mains newly set to "slab" (was missing): {n_new_main}
- Mains upgraded to "slab" (was closeup-only/other): {n_upgraded}
- Mains set to "closeup-only" (only a close-up crop exists, no full slab photo): {n_closeup_only}
- Main downloads that failed: {n_dl_fail}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: 0 (site has none anywhere, confirmed in discovery)
- Metadata-only updates (productUrl/slabSizes/details/aliases): {n_meta_only}
- Still missing after this run: 1 -- Calacatta Gold Shimmer (recommend asking KSG directly)

## Price-book colours NOT found on the site
- Calacatta Gold Shimmer -- confirmed 404, no dedicated page exists even though
  the price book lists it distinctly from "Calacatta Shimmer". Ask KSG.

## Site colours seen but NOT in the price book (not harvested, not invented)
{chr(10).join(f"- {name} (`/NATUREQ/{slug}`)" for slug, name in SITE_EXTRAS_NOT_IN_PRICEBOOK.items())}

## Assumptions / judgement calls
- **Carrara Gold**: the page's own gallery hero image is itself filename
  "Carrara Gold close up.jpg" (1280x853, 1.5:1) -- not a full slab shot despite
  being the only visible gallery photo. Treated as `closeup-only`, not `slab`.
- **White Shimmer**: gallery shows "Image Coming Soon"; the page's JSON-LD
  `Product.image` still resolves to a working close-up photo. Used as the
  main image with status `closeup-only` (matches the discovery note).
{chr(10).join(f"- {o}" for o in ODDITIES)}
- `slabSizes` comes from the price book first; the page's own `Size:` line
  (metres, converted to mm) only as a fallback when the price book has no
  size row for that colour.
- `details` = "NATUREQ · <Origin> · <Finish> finish" from the page's own
  Product Information block + price-book Finish column.
- Existing `image.status == "slab"` mains are left untouched even where the
  site now has a close-up too -- the close-up is still added to `images[]`.
- Seville / Santorini: on-site names "Calacatta Light (Seville)" / "Calacatta
  Nero (Santorini)" recorded in `aliases[]`.
{f"- Aspect-ratio warnings (outside ~1.5-2.6:1), check contact sheet: {'; '.join(aspect_warnings)}" if aspect_warnings else "- No aspect-ratio warnings -- every main image fell inside slab range."}

## Re-run
```
python tools/harvest_ksg.py                 # re-scrape (cached; delete tools/_cache/ksg to force)
python tools/reconcile_ksg.py --report       # dry run, prints the match table
python tools/reconcile_ksg.py --apply        # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
