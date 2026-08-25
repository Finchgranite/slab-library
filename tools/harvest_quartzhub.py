"""Quartz Hub (quartzhub.co.uk) harvest -- phase 2.

Quartz Hub has NO per-colour product pages (sitemap-pages.xml lists exactly
5 pages: home, /gallery/, /about-us/, /our-services/, /faq/ -- confirmed by
fetching every sub-sitemap in https://quartzhub.co.uk/sitemap.xml). All 15
colours previously stored a `?s=Colour+Name` WordPress *search* URL as their
productUrl -- those are placeholders, not real pages, per HARVEST-SPEC. The
one real, working page that shows every colour is https://quartzhub.co.uk/gallery/
(a Modula lightbox gallery) -- that becomes the new productUrl for all 15.

Image source: the gallery page's Modula gallery renders, for each photo, an
<a data-image-id=".." data-caption="Colour Name ..."></a> immediately followed
by an <img ... alt="Colour Name .." data-full="ORIGINAL_URL" width=".." height="..">
-- data-caption/alt give a clean colour name (no filename-slug guessing
needed) and width/height are the TRUE original dimensions (no HEAD request
needed for aspect classification). Parsed directly with a dedicated regex
(own_image_re) rather than harvest_lib.extract_images, which does not read
data-caption. The 4 non-gallery pages (home/about-us/our-services/faq) are
still fetched and run through hl.extract_images() as a belt-and-braces check
for stray colour photos used elsewhere (none found beyond duplicates already
in the gallery -- see harvest report).

Per colour there are 2 site photos (3 for Onyx Crema): a landscape "main"
photo (filename has no "swatch"/"-scaled" marker) and either
  - a perfectly square 2560x2560 crop (the 10 older "2024/08" colours), or
  - a "*-swatch-image-*" filename, still landscape-ish (~1.5:1) but always a
    texture/detail crop, not a second full-slab shot (verified against the
    live gallery: both slab-and-swatch pairs are visually a wide slab photo +
    a close macro crop).
Both forms are picked up as "closeup" by hl.classify_kind (square aspect
0.8-1.25, or the literal "swatch" keyword in _CLOSEUP_HINTS). Onyx Crema's
3rd photo ("...Lit-up-2.jpg", caption "... - Backlit") is a translucency/
backlit application shot -- not a kitchen/cabinets room photo, but the
closest thing Quartz Hub has to a "how it looks in use" shot, so it is
special-cased to kind "room" (hl.classify_kind alone returns None for it:
1.5:1 aspect misses both the slab and closeup aspect bands, and no keyword
hints match). Onyx Crema's main "1.Onyx-Creame-30mm-and-20mm.jpg" is
2387x1204 = 1.98:1 -- squarely in the slab aspect band -- and IS a genuine
full slab photo (library currently only has closeup-only for this colour;
HARVEST-SPEC says fill it with a real slab face).

The other 13 colours (14 minus Onyx Crema, minus Laurent which has no site
photos at all) already have a good "slab" main in the library -- per the
task brief those are NOT to be replaced, so their landscape "main" site photo
is deliberately never classified as "slab" here: it is either <1.8:1 (misses
the slab aspect band) or filename-unflagged, so it naturally falls out of
classify_kind as None and is simply not carried into the harvest manifest at
all (harvest_one() only records "slab"/"closeup"/"room" kinds). Confirmed
against a dry run: for these 13 colours only 1-2 "closeup" images are ever
produced, no "slab".

Name matching: colour names come from the gallery's own data-caption/alt
text (already clean, e.g. "Statuario Oro (Ceramic) 20mm", "Arabes-catta Oro
20mm and 30mm") -- stripped of "(Quartz)"/"(Ceramic)" and any "NNmm[ and
NNmm]" size suffix, then matched to the price-book colour by removing ALL
non-alphanumeric characters (so "Arabes-catta Oro" -> "arabescattaoro" ==
price-book "Arabescatta Oro" -> "arabescattaoro"). "Ultra White Shimmer"
(2 real site photos, same pattern as the other 2024/08 colours) has no
price-book/library row at all -- reported as an unmatched site product, no
entry invented for it. "Laurent" (Ceramic) is a price-book/library colour
with NO photos anywhere on the site (gallery, home, about-us, our-services,
faq all checked) -- reported as unmatched price-book colour, left untouched.

Writes tools/quartzhub-harvest.json. Re-run is cheap: pages are cached under
tools/_cache/quartzhub/; delete that dir to force a re-fetch.
"""
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "quartzhub"
BASE = "https://www.quartzhub.co.uk"
GALLERY_URL = "https://www.quartzhub.co.uk/gallery/"
PAGES = {
    "home": BASE + "/",
    "gallery": GALLERY_URL,
    "about-us": BASE + "/about-us/",
    "our-services": BASE + "/our-services/",
    "faq": BASE + "/faq/",
}

# <a data-image-id=".." ... data-caption="CAPTION" ...></a><img .. alt="ALT"
# .. data-full="URL" .. width="W" height="H" ..>
MODULA_ITEM_RE = re.compile(
    r'data-image-id="(\d+)"[^>]*data-caption="([^"]*)"[^>]*></a>'
    r'<img[^>]*alt="([^"]*)"[^>]*data-full="([^"]*)"[^>]*width="(\d+)" height="(\d+)"'
)

BACKLIT_HINT = re.compile(r'backlit|lit[-_ ]?up', re.I)
SIZE_SUFFIX_RE = re.compile(r'\b\d{2}mm\b(\s*and\s*\d{2}mm\b)?', re.I)
MATERIAL_TAG_RE = re.compile(r'\((?:quartz|ceramic)\)', re.I)


def clean_caption(caption):
    """'Statuario Oro (Ceramic) 20mm' / 'Arabes-catta Oro 20mm and 30mm' /
    'Onyx Crema (Quartz) 20mm and 30mm - Backlit ' -> 'Statuario Oro' /
    'Arabescatta Oro' / 'Onyx Crema'."""
    c = caption
    c = MATERIAL_TAG_RE.sub('', c)
    c = re.sub(r'-\s*Backlit\s*', '', c, flags=re.I)
    c = SIZE_SUFFIX_RE.sub('', c)
    c = c.replace('-', ' ')
    c = re.sub(r'\s+', ' ', c).strip()
    return c


def norm_all(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def match_pb_colour(caption, pb_colours):
    """Exact match on norm_all() (strip every non-alnum char, no spaces) --
    handles 'Arabes-catta Oro' -> 'arabescattaoro' == price-book
    'Arabescatta Oro' -> 'arabescattaoro'."""
    name = clean_caption(caption)
    key = norm_all(name)
    for pbc in pb_colours:
        if norm_all(pbc) == key:
            return pbc, name
    return None, name


def parse_gallery_items(html_text):
    return MODULA_ITEM_RE.findall(html_text)


def classify(url, alt, caption, width, height):
    if BACKLIT_HINT.search(alt) or BACKLIT_HINT.search(caption) or BACKLIT_HINT.search(url):
        return "room"
    return hl.classify_kind(url, alt, "", int(width) if width else None, int(height) if height else None)


def harvest():
    pb = hl.load_pricebook("Quartz Hub")
    pb_colours = list(pb.keys())

    pages_html = {}
    for key, url in PAGES.items():
        pages_html[key] = hl.fetch_text(url, supplier=SUPPLIER, cache_key=key)

    by_colour = {}   # matched pb colour -> {"slab":[..], "closeup":[..], "room":[..]}
    unmatched_site = {}   # cleaned caption -> [urls] (no pb match)
    seen_urls = set()

    # Primary source: the Modula gallery's own data-caption/data-full pairs.
    items = parse_gallery_items(pages_html["gallery"])
    for image_id, caption, alt, url, w, h in items:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        kind = classify(url, alt, caption, w, h)
        if not kind:
            continue
        pbc, cleaned = match_pb_colour(caption, pb_colours)
        rec = {"url": url, "width": int(w), "height": int(h), "caption": caption.strip(),
               "kind": kind, "source": PAGES["gallery"]}
        if pbc:
            by_colour.setdefault(pbc, {"slab": [], "closeup": [], "room": []})[kind].append(rec)
        else:
            unmatched_site.setdefault(cleaned, []).append(rec)

    # Belt-and-braces: any colour photo used elsewhere on the small site
    # (home/about-us/our-services/faq) that the gallery loop missed.
    extra_hits = []
    for key in ("home", "about-us", "our-services", "faq"):
        imgs = hl.extract_images(pages_html[key], PAGES[key])
        for im in imgs:
            if im["url"] in seen_urls:
                continue
            kind = hl.classify_kind(im["url"], im["alt"], im["context"], im["width"], im["height"])
            if not kind:
                continue
            # try to recover a colour name from the filename (alt is often blank here)
            fn = im["url"].rsplit("/", 1)[-1]
            guess = re.sub(r'-(scaled|e\d+|image|close[-_ ]?up)\b.*$', '', fn, flags=re.I)
            guess = re.sub(r'\.[a-z]+$', '', guess, flags=re.I).replace('-', ' ')
            pbc, cleaned = match_pb_colour(guess, pb_colours)
            if not pbc:
                continue
            seen_urls.add(im["url"])
            rec = {"url": im["url"], "width": im["width"], "height": im["height"],
                   "caption": im["alt"] or guess, "kind": kind, "source": PAGES[key]}
            by_colour.setdefault(pbc, {"slab": [], "closeup": [], "room": []})[kind].append(rec)
            extra_hits.append((key, pbc, kind, im["url"]))

    unmatched_pb = sorted(set(pb_colours) - set(by_colour.keys()))

    manifest = {
        "productUrl": GALLERY_URL,
        "by_colour": by_colour,
        "unmatched_site": unmatched_site,
        "unmatched_pb": unmatched_pb,
        "extra_hits_non_gallery_pages": extra_hits,
    }
    out_path = os.path.join(SCRATCH, "quartzhub-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    print(f"pages fetched: {list(PAGES.keys())}")
    print(f"gallery items parsed: {len(items)}")
    for pbc, kinds in sorted(by_colour.items()):
        print(f"  {pbc:22s} slab={len(kinds['slab'])} closeup={len(kinds['closeup'])} room={len(kinds['room'])}")
    print(f"unmatched site captions (no price-book row): {list(unmatched_site.keys())}")
    print(f"unmatched price-book colours (no site photo found): {unmatched_pb}")
    print(f"extra hits from non-gallery pages: {extra_hits}")
    print(f"WROTE {out_path}")


if __name__ == "__main__":
    harvest()
