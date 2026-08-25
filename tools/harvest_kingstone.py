"""Kingstone Quartz (kingstonequartz.co.uk, WordPress/Elementor) harvest.

Site facts (confirmed this pass): ALL 35 colours sit on ONE listing page,
https://kingstonequartz.co.uk/quartz-collection/ (an Elementor image-gallery
widget) -- there are no per-colour product pages. Each gallery item is a
single <a href="...full-size-image"><img alt="<Colour> <SKU> [Kingstone
Quartz Collection]"></a>; the href is the WP "-scaled" (i.e. near-original,
max ~2560px) upload -- no separate closeup/room files exist anywhere on the
site (checked /collection/, the sitemap, and the "portfolio" post type --
that's unused Avada theme demo content, not real product photography).

IMPORTANT quirk: several filenames/alts say "...with close up" or
"...Close-up..." (e.g. "Artic-Frost-253-WebP..." whose alt is plain, but
"Calacatta-Eclipse-236-with-close-up..."). Downloading and inspecting one
(Artic Frost, 1280x2560px) confirms this is NOT a separate closeup photo --
it is a single portrait-orientation photo of the WHOLE slab face (slabs are
3200x1600mm; this supplier photographs them tall) with a small circled
detail-zoom inset baked into the same image. So classify_kind()'s generic
"close-up" filename hint would wrongly tag these as kind=closeup; every
gallery image on this site is instead the slab main (there is no separate
closeup/room asset to harvest). aspect ok is confirmed by classify_kind's
symmetric ar_n = max(w/h, h/w) test (0.5 -> 2.0, within the 1.8-2.3 slab
band) once the closeup-keyword override below is bypassed.

22 of 35 price-book colours already had a "slab" main in slabs.json from an
earlier (undocumented) pass -- spot-checked (Artic Frost) byte-for-byte
against this run's re-download: identical source image. Those are left
untouched; this script/reconcile only fills the currently-`missing` ones
and refreshes productUrl/slabSizes/details for all 35 (the existing
productUrl values are dead WordPress `?s=` search-result links, not real
product pages -- replaced with the real listing page for every entry).

Writes tools/kingstone-harvest.json. Run once (cached under
tools/_cache/kingstone/); reconcile_kingstone.py consumes the manifest.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "kingstone"
BASE = "https://kingstonequartz.co.uk"
LISTING_URL = f"{BASE}/quartz-collection/"

# alt-text colour name -> price-book colour name, for the handful the
# generic "strip trailing SKU digits + boilerplate" parse can't handle
# cleanly (aliasing, a parenthetical, or an extra descriptive word).
ALT_TO_PRICEBOOK = {
    "Ivory Fantasy": "Ivory Fantasy (Irini)",
}

# Site gallery items with NO matching price-book colour (not this phase's
# job to invent an entry for a product we don't sell) -- kept here so a
# re-run doesn't treat them as an unexplained gap.
UNMATCHED_SITE_PRODUCTS = {
    "Platinum Grey 113": "https://kingstonequartz.co.uk/wp-content/uploads/2023/07/"
                          "CL1024-Grey-Shimmer-scaled-e1690278626632.jpg",
}


def parse_listing(html_text):
    """Returns [{alt, sku, name_guess, url}, ...] for every gallery item."""
    out = []
    for m in re.finditer(r'<a\b([^>]*)>\s*<img\b([^>]*)>', html_text):
        a_attrs, img_attrs = m.group(1), m.group(2)
        href = re.search(r'href="([^"]*)"', a_attrs)
        alt = re.search(r'alt="([^"]*)"', img_attrs)
        if not href or not alt:
            continue
        url = H.unescape(href.group(1))
        if not re.search(r'\.(jpe?g|png|webp)$', url, re.I):
            continue
        raw_alt = H.unescape(alt.group(1)).strip()
        # strip site boilerplate / quoted marketing words / trailing SKU digits
        name = re.sub(r'\s*Kingstone Quartz Collection\s*$', '', raw_alt).strip()
        name = re.sub(r'\s*"[^"]*"\s*$', '', name).strip()
        skum = re.search(r'^(.*?)\s+(\d+)$', name)
        if skum:
            name_guess, sku = skum.group(1).strip(), skum.group(2)
        else:
            name_guess, sku = name, ""
        out.append({"alt": raw_alt, "name_guess": name_guess, "sku": sku, "url": url})
    return out


def main():
    html_text = hl.fetch_text(LISTING_URL, supplier=SUPPLIER, cache_key="quartz-collection")
    items = parse_listing(html_text)
    print(f"parsed {len(items)} gallery items from {LISTING_URL}")

    pb_colours = set(hl.load_pricebook("Kingstone").keys())
    manifest, unmatched = [], []
    for it in items:
        colour = ALT_TO_PRICEBOOK.get(it["name_guess"], it["name_guess"])
        if colour in pb_colours:
            manifest.append({
                "colour": colour, "sku": it["sku"], "alt": it["alt"],
                "image_url": it["url"], "source": LISTING_URL,
            })
        else:
            unmatched.append(it)

    matched_colours = {m["colour"] for m in manifest}
    still_missing_pb = sorted(pb_colours - matched_colours)

    out = {
        "listing_url": LISTING_URL,
        "manifest": manifest,
        "unmatched_site_items": [{"alt": it["alt"], "url": it["url"]} for it in unmatched],
        "pricebook_colours_not_on_site": still_missing_pb,
    }
    out_path = os.path.join(SCRATCH, "kingstone-harvest.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    print(f"matched {len(manifest)}/{len(pb_colours)} price-book colours")
    print("unmatched site items:", [it["alt"] for it in unmatched])
    print("price-book colours not found on site:", still_missing_pb)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
