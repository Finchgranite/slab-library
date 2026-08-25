"""RT Stone (quartzbyrtstone.co.uk, custom PHP site) harvest -- phase 2.

Site facts (confirmed this pass): despite the 38 existing library entries all
storing `productUrl` = the generic `/products` listing page, the site DOES
have per-colour pages at `product-details.php?title=<slug>` -- 111 of them,
linked straight off `/products` (a single static HTML page, no sitemap.xml/
robots.txt/wp-sitemap.xml -- all 404 via the custom LiteSpeed PHP site; no
AJAX pagination either, `/products` lists every product server-side in one
page, confirmed by grepping for a "load more"/pagination control and finding
none). The 111 slugs include natural-stone ranges (granite/marble/onyx --
Nero Marquina, Kuppam Green, River White Granite, Fior Di Bosco, etc.) that
are out of scope; 42 of our 44 price-book RT Stone (all quartz) colours have
a slug ("Eternal Calacatta" and -- until the SLUG_OVERRIDES fix below --
"Cararra Milano" don't token-match anything on the site: Eternal Calacatta
has no slug at all containing "eternal" anywhere in the listing page text,
Cararra Milano's price-book spelling is a typo for the site's "Carrara
Milano" so needed an explicit override).

Several price-book colours have MULTIPLE site pages (different slab sizes:
"-jumbo" vs "-super-jumbo-zero-silica" etc, an old/new SKU pair) -- one slug
per price-book colour was chosen (SLUG_OVERRIDES / prefer-zero-silica-or-
super-jumbo heuristic in pick_slug()), preferring the newer "zero silica"
formulation page where one exists (matches the site's own trend: several
colours, e.g. Sand Storm, now ONLY have a "-zero-silica" slug, the plain one
having been retired) and picking Calacatta Auric's "-jumbo" page over
"-super-jumbo" because it carries a 3-image gallery (slab+closeup+kitchen)
vs the super-jumbo page's 2 (spot-checked both).

Each product page's own gallery lives in `<img class="xzoom-gallery5" ...>`
tags inside `#magnific .xzoom-thumbs` (NOT the plain `<img>` tags further
down the page, which are OTHER colours' thumbnails in a "Related Products"
carousel -- every page embeds all ~111 of those, a false-positive trap for
generic extract_images()). Confirmed across 8 spot-checked pages: the FIRST
xzoom-gallery5 image is always the full slab face (~2:1, filename says "full
slab"/"FULL SLAB" or is just the plain product photo); when present, a 2nd
carries "close up"/"closeup"/"CloseUp" in its filename (texture crop); a 3rd
(when present) carries "kitchen"/"fitted" (installation room shot). One
colour, White Shimmer Supreme, has ONLY a closeup-labelled image in its
gallery -- the site itself has no slab face for it (library status was
already `closeup-only`; stays that way, reported not invented).

`details` blurb = the `<div class="prod_desc"><p>...</p>` text (per-product,
distinct from the much longer generic marketing paragraph that appears later
on the page as part of the same-colour "product info" repeat block -- both
were checked side by side on Arabescato Corchia; prod_desc is the shorter,
cleaner one and appears consistently right under the h1/product name).

Writes tools/rtstone-harvest.json. Re-run is cheap: pages are cached under
tools/_cache/rtstone/; delete that dir to force a re-fetch.
"""
import html as H
import json
import os
import re
import urllib.parse

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "rtstone"
BASE = "https://www.quartzbyrtstone.co.uk"
LISTING_URL = f"{BASE}/products"

# price-book colour -> exact site slug, for the handful the automatic
# guess_name()/match_colour() token match can't resolve unambiguously
# (typo in the price book, or a name that only matches by fuzzy substring
# to the WRONG colour -- see module docstring).
SLUG_OVERRIDES = {
    "Cararra Milano": "carrara-milano-jumbo",
}

# site slugs that token-match a price-book colour by fuzzy accident but are
# actually a different, unstocked colour -- never candidates.
SLUG_BLOCKLIST = {"calacatta-orio"}

# suffixes stripped off a slug (in this order, twice, to catch combos like
# "-super-jumbo-zero-silica") to recover the bare colour name for matching.
_STRIP_RE = re.compile(
    r'-(super-jumbo|jumbo|zero-silica|low-silica|new-colour|granite|polished|honed|silk)\b')

# preference order when a price-book colour has multiple site pages (slab
# size / SKU variants) -- highest-priority substring wins.
_VARIANT_PRIORITY = ["zero-silica", "super-jumbo", "jumbo", ""]


def guess_name(slug):
    s = slug.rstrip("-")
    for _ in range(2):
        s = _STRIP_RE.sub("", s)
    return s.strip("-").replace("-", " ").title()


def get_all_slugs():
    html_text = hl.fetch_text(LISTING_URL, supplier=SUPPLIER, cache_key="products")
    slugs = sorted(set(re.findall(r'product-details\.php\?title=([a-z0-9-]+)', html_text)))
    return slugs


def pick_slug_for_colour(colour, candidates):
    """candidates: list of slugs that token-matched `colour`. Pick the best
    single page per SLUG_OVERRIDES / _VARIANT_PRIORITY, special-cased for
    Calacatta Auric (see module docstring: -jumbo has the fuller gallery)."""
    if colour in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[colour]
    if colour == "Calacatta Auric" and "calacatta-auric-jumbo" in candidates:
        return "calacatta-auric-jumbo"
    if len(candidates) == 1:
        return candidates[0]
    for pref in _VARIANT_PRIORITY:
        for c in candidates:
            if pref and pref in c:
                return c
    return sorted(candidates)[0]


def build_colour_to_slug(pb_colours, slugs):
    by_guess = {}
    for slug in slugs:
        if slug in SLUG_BLOCKLIST:
            continue
        by_guess.setdefault(guess_name(slug), []).append(slug)

    colour_to_slug, unmatched_pb = {}, []
    for colour in pb_colours:
        if colour in SLUG_OVERRIDES:
            colour_to_slug[colour] = SLUG_OVERRIDES[colour]
            continue
        candidates = []
        for guess, slist in by_guess.items():
            obj, score = hl.match_colour(guess, [(colour, colour)])
            if obj:
                candidates.extend(slist)
        if candidates:
            colour_to_slug[colour] = pick_slug_for_colour(colour, candidates)
        else:
            unmatched_pb.append(colour)
    return colour_to_slug, unmatched_pb


_CLOSEUP_RE = re.compile(r'close[\s_-]?up|\bzoom\b', re.I)
_ROOM_RE = re.compile(r'kit\w*chen|kithcen|fitted|room|install|bathroom|lifestyle', re.I)


def parse_product_page(html_text, colour, slug):
    page_url = f"{BASE}/product-details.php?title={slug}"
    m = re.search(r'<h1>([^<]*)</h1>', html_text)
    title = H.unescape(m.group(1)).strip() if m else ""

    gallery = []
    thumbs_m = re.search(r'class="xzoom-thumbs".*?</div>\s*</div>', html_text, re.S)
    block = thumbs_m.group(0) if thumbs_m else ""
    for m in re.finditer(r'<a href="([^"]+)"><img class="xzoom-gallery5"[^>]*>', block):
        # gallery hrefs are DOCUMENT-relative ("images/Foo.jpg", no leading
        # "/") -- MUST be resolved against the page URL with urljoin; curl
        # cannot fetch a relative path, and hl._absolutize() only handles
        # root-relative ("/x") and protocol-relative ("//host/x") forms, not
        # this plain-relative one. The site's raw filenames also contain
        # literal spaces/parens ("Alaska FULL SLAB.jpg", "CARRARA BIANCO
        # (1).jpg") which curl refuses outright (rc=3, "URL using bad/
        # illegal format") unless percent-encoded. Both were real bugs this
        # pass: every single download failed until both fixes -- see
        # tools/_reports/rtstone-REPORT.md.
        url = urllib.parse.urljoin(page_url, H.unescape(m.group(1)))
        gallery.append(url)

    # classify on the RAW (unencoded) filename -- "close up"/"KITCHEN" etc
    # keyword regexes expect literal spaces, not "%20" -- then percent-encode
    # each url for fetching only after classification is done.
    kinds = []
    for i, url in enumerate(gallery):
        fn = url.rsplit("/", 1)[-1]
        if _CLOSEUP_RE.search(fn):
            kinds.append("closeup")
        elif _ROOM_RE.search(fn):
            kinds.append("room")
        elif i == 0:
            kinds.append("slab")   # default only when the file's own name gives no other hint
        else:
            kinds.append(None)     # unclassified -- keyword hint absent, don't guess yet

    # positional elimination: a 3-image gallery is slab/closeup/room in order
    # on every colour where all 3 are keyword-classified (confirmed across
    # 20+ pages this pass) -- so an unclassified middle slot with a known
    # slab at 0 and room at 2 is the closeup.
    if len(kinds) == 3 and kinds[0] == "slab" and kinds[1] is None and kinds[2] == "room":
        kinds[1] = "closeup"

    # NOW percent-encode (curl refuses a literal space/paren in the URL, rc=3).
    gallery = [urllib.parse.quote(u, safe="/:%") for u in gallery]

    desc_m = re.search(r'class="prod_desc">\s*<p>(.*?)</p>', html_text, re.S)
    desc = ""
    if desc_m:
        desc = re.sub(r'<[^>]+>', ' ', desc_m.group(1))
        desc = H.unescape(desc)
        desc = re.sub(r'\s+', ' ', desc).strip()

    size_m = re.search(r'(\d{2,4}\s*(?:cm|mm)\s*x\s*\d{2,4}\s*(?:cm|mm))', html_text, re.I)
    size_text = size_m.group(1) if size_m else ""

    return {
        "colour": colour, "slug": slug, "url": f"{BASE}/product-details.php?title={slug}",
        "title": title, "images": list(zip(gallery, kinds)), "description": desc,
        "size_text": size_text,
    }


def main():
    pb = hl.load_pricebook("RT Stone")
    pb_colours = sorted(pb.keys())
    slugs = get_all_slugs()
    print(f"{len(slugs)} product-details slugs on {LISTING_URL}")

    colour_to_slug, unmatched_pb = build_colour_to_slug(pb_colours, slugs)
    print(f"matched {len(colour_to_slug)}/{len(pb_colours)} price-book colours to a site page")
    print("price-book colours with no site page found:", unmatched_pb)

    manifest = []
    for i, (colour, slug) in enumerate(sorted(colour_to_slug.items()), 1):
        try:
            html_text = hl.fetch_text(
                f"{BASE}/product-details.php?title={slug}", supplier=SUPPLIER, cache_key=slug)
        except Exception as e:
            manifest.append({"colour": colour, "slug": slug, "error": str(e)})
            print(f"[{i}/{len(colour_to_slug)}] FETCH FAIL {colour} ({slug}): {e}", flush=True)
            continue
        rec = parse_product_page(html_text, colour, slug)
        manifest.append(rec)
        kinds_summary = [k or "?" for _, k in rec["images"]]
        print(f"[{i}/{len(colour_to_slug)}] {colour!r} ({slug}) title={rec['title']!r} "
              f"images={kinds_summary}", flush=True)

    out = {
        "listing_url": LISTING_URL,
        "all_slugs_count": len(slugs),
        "manifest": manifest,
        "pricebook_colours_no_site_page": unmatched_pb,
    }
    out_path = os.path.join(SCRATCH, "rtstone-harvest.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
