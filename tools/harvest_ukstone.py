"""UK Stone Company (ukstonecompany.com, WordPress/WooCommerce/Avada) harvest.

Site has NO closeup/room galleries -- each product page carries exactly one
hero slab photo (in the `woocommerce-product-gallery__wrapper` figure,
`data-large_image` = full-res original, `data-large_image_width/height` =
true px size) plus a WooCommerce `custom-attributes` list giving Material
Finishes / Material Type / Quartz Sizes / Thickness / Sizes (metres, e.g.
"3.20m x 1.60m") and a `Category:` line (Quartz / Granite / Marble /
Quartzite -- used to reject natural-stone pages that share a colour word).

Colour name matching is NOT done by generic token-subset here: the site
mixes a size-descriptor "Jumbo"/"Super Jumbo" into some titles but not others
and dark/light finish variants sometimes collapse to one product page, so a
hand-built slug->pricebook-colour map (built from tools/_cache/ukstone/
all-product-slugs.txt via wp-sitemap-posts-product-1.xml, cross-checked
against supplier-price-book.csv) is used instead -- see TARGETS below and the
report's Assumptions section for the two judgement calls (Carrara Vincenza,
Grey Shimmer Dark).

Writes tools/ukstone-harvest.json. Run once (cached under tools/_cache/ukstone/);
reconcile_ukstone.py consumes the manifest.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "ukstone"
BASE = "https://ukstonecompany.com"

# slug -> price-book colour name. One representative page per colour/finish
# variant (2cm chosen over 3cm where both exist -- same hero photo either way
# on every page we sampled). Bare (no "quartz" in slug) product pages used
# where no "-quartz-" tagged slug exists (site's older upload batch).
TARGETS = {
    "black-shimmer-jumbo-quartz-2cm": "Black Shimmer",
    "blanco-carrara-super-jumbo-quartz-2cm": "Blanco Carrara",
    "blanco-carrara-light-super-jumbo-quartz-2cm": "Blanco Carrara Light",
    "blanco-carrara-shimmer-super-jumbo-quartz-2cm": "Blanco Carrara Shimmer",
    "blanco-carrara-vincenza-jumbo-quartz-2cm": "Carrara Vincenza",
    "blanco-lustre-super-jumbo-quartz-2cm": "Blanco Lustre",
    "calacatta-atlantic-jumbo-quartz-2cm": "Calacatta Atlantic",
    "calacatta-bergamo-super-jumbo-quartz-2cm": "Calacatta Bergamo",
    "calacatta-castano-jumbo-quartz-2cm": "Calacatta Castano Polished",
    "calacatta-castano-jumbo-quartz-2cm-leather-finish": "Calacatta Castano Leathered",
    "calacatta-catania-jumbo-quartz-2cm": "Calacatta Catania",
    "calacatta-giotto": "Calacatta Giotto",
    "calacatta-glacier-jumbo-quartz-2cm": "Calacatta Glacier",
    "calacatta-gold": "Calacatta Gold",
    "calacatta-himalaya-quartz-2cm": "Calacatta Himalaya",
    "calacatta-lazio-jumbo-quartz-2cm": "Calacatta Lazio",
    "calacatta-lucca-super-jumbo-quartz-2cm": "Calacatta Lucca",
    "calacatta-navara-jumbo-quartz-2cm": "Calacatta Navara",
    "calacatta-santorini-quartz-2cm": "Calacatta Santorini",
    "calacatta-supreme-jumbo-quartz-2cm": "Calacatta Supreme",
    "calacatta-tuscany-jumbo-quartz-2cm": "Calacatta Tuscany",
    "calacatta-venice-jumbo-quartz-2cm": "Calacatta Venice",
    "casablanca": "Casablanca",
    "dark-concrete-jumbo-quartz-2cm": "Concrete Dark",
    "cream-mirror-jumbo-quartz-3cm": "Cream Mirror",
    "crema-marfil-jumbo-quartz-2cm": "Crema Marfil",
    "elegant-frost-jumbo-quartz-2cm": "Elegant Frost",
    "grey-mirror-dark": "Grey Mirror Dark",
    "grey-mirror-light": "Grey Mirror Light",
    # Site carries only ONE "Grey Shimmer" product (no dark/light slugs) --
    # image is a mid/dark tone -> assigned to "Dark"; "Light" stays missing.
    # See REPORT.md Assumptions.
    "grey-shimmer-jumbo-quartz-2cm": "Grey Shimmer Dark",
    "highlands-jumbo-quartz-2cm": "Highlands Polished",
    "highlands-jumbo-quartz-2cm-leather-finish": "Highlands Leathered",
    "highlands-shimmer-jumbo-quartz-2cm": "Highlands Shimmer Polished",
    "oceano-gold-super-jumbo-quartz-2cm": "Oceano Gold",
    "pure-white-super-jumbo-quartz-2cm": "Pure White",
    "rio-dourado-super-jumbo-quartz-2cm": "Rio Dourado",
    "statuario-gold-extra-jumbo-quartz-2cm": "Statuario Gold Extra",
    "statuario-gold-extra-jumbo-quartz-2cm-leather-finish": "Statuario Gold Extra Leathered",
    "super-white-jumbo-quartz-2cm": "Super White",
    "taj-mahal-jumbo-quartz-2cm": "Taj Mahal Polished",
    "taj-mahal-jumbo-quartz-2cm-leather-finish": "Taj Mahal Leathered",
    "white-galactica-mirror-jumbo-quartz-2cm": "White Galactica Mirror",
}

# Site products investigated and explicitly rejected as NOT this colour
# (different material or different named product) -- kept here so a re-run
# doesn't re-fetch them looking for a match:
#   krystallus-translucent   -> Quartzite (natural stone, category=Quartzite)
#   moon-white               -> Granite (natural stone, category=Granite, Colour=Black)
#   mystic-waters-*          -> "Mystic Waters" != "Mystic Rivers" (pricebook), not assumed same


def parse_page(html_text, url):
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.S)
    title = H.unescape(re.sub('<[^>]+>', '', h1.group(1))).strip() if h1 else ""
    cat = re.search(r'Category:\s*<a[^>]*>([^<]+)</a>', html_text)
    category = H.unescape(cat.group(1)).strip() if cat else ""
    attrs = dict(re.findall(
        r'<span class="attribute-label-text">([^<]+)</span>:\s*</span>\s*'
        r'<span class="attribute-value"><a[^>]*>([^<]+)</a>', html_text))
    attrs = {k.strip(): H.unescape(v).strip() for k, v in attrs.items()}
    large = re.search(r'data-large_image="([^"]+)"', html_text)
    lw = re.search(r'data-large_image_width="(\d+)"', html_text)
    lh = re.search(r'data-large_image_height="(\d+)"', html_text)
    img = large.group(1) if large else None
    if not img:
        og = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html_text)
        img = og.group(1) if og else None
    return {
        "url": url, "title": title, "category": category, "attrs": attrs,
        "image": img,
        "image_w": int(lw.group(1)) if lw else None,
        "image_h": int(lh.group(1)) if lh else None,
    }


def main():
    manifest = []
    for i, (slug, colour) in enumerate(sorted(TARGETS.items()), 1):
        url = f"{BASE}/product/{slug}/"
        try:
            html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=slug)
        except Exception as e:
            print(f"[{i}/{len(TARGETS)}] FETCH FAIL {slug}: {e}", flush=True)
            manifest.append({"slug": slug, "colour": colour, "url": url, "error": str(e)})
            continue
        rec = parse_page(html_text, url)
        rec["slug"] = slug
        rec["colour"] = colour
        manifest.append(rec)
        print(f"[{i}/{len(TARGETS)}] {colour!r:35s} <- {slug:50s} "
              f"cat={rec['category']!r:10s} img={'Y' if rec['image'] else 'N'} "
              f"{rec['image_w']}x{rec['image_h']} attrs={rec['attrs']}", flush=True)

    out_path = os.path.join(SCRATCH, "ukstone-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error"))
    print(f"WROTE {out_path}: {len(manifest)} targets, {ok} ok")


if __name__ == "__main__":
    main()
