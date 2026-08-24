"""Thomas Group (Surfaces Collection) harvest -- QUARTZ + SINTERED STONE only
(Porcelain/Atlas Plan is a different agent's job; don't touch it).

Three sub-ranges, three parsing paths (see tools/_reports/thomasgroup-DISCOVERY.md):
  - Silkstone Quartz (Thomas Group's own label, 27 colours incl. End of Line) --
    single page thesurfacecollection.co.uk/products/silkstone-quartz/ embeds every
    SKU. Each product is a `data-bpopup='<div class="product-info">...'` lightbox:
    <h3 class="product-info__heading">NAME THICKNESSmm FINISH</h3>, a sizes table
    (`<td>3200*1600<td`), a swatch background-image (`lib/swatch/*.jpg`), and the
    card's own <img src="lib/photos/*.jpg"> (the slab image). No room shots.
  - Vadara Quartz (37 colours) -- primary source vadara.uk (WordPress, better
    photography): /designs/{slug}/ pages (slugs enumerated from
    /product-sitemap.xml, NOT the small homepage carousel). Main slab image
    `Vadara_{Name}[_{Vcode}]_(Web|HiRes).jpg`; room shots `VQ_INSTALL_*_H##.jpg`
    (older pages) or `Vadara_{Name}_{Vcode}_RenderNN.jpg` (newer pages, real
    kitchen/bathroom CGI renders); `*_STORY_*.jpg` are unrelated landscape mood
    photography -- excluded. No dedicated closeup exists on any page sampled.
    3 colours (the "Super Jumbo" SKUs: Braewind, Nomad Valley, Soraline) have NO
    vadara.uk page at all -- fall back to thesurfacecollection.co.uk's Vadara
    sub-collection pages (same lightbox structure as Silkstone).
  - Neolith by The Size (16 colours, Sintered Stone) -- same lightbox structure
    as Silkstone, single page thesurfacecollection.co.uk/products/neolith-by-the-size/
    (canonicalises to a "12mm-slab-standard-range" URL but embeds the 6mm/12mm/20mm
    sections together). neolith.com itself is bot-blocked (403) -- not attempted.

Writes tools/thomasgroup-quartz-harvest.json: {"silkstone": [...], "vadara": [...],
"neolith": [...]}. Run once (pages cached under tools/_cache/thomasgroup/);
reconcile_thomasgroup_quartz.py consumes the manifest, matches to the price book
+ library, downloads images, and applies.
"""
import html as H
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "thomasgroup"
TSC_BASE = "https://thesurfacecollection.co.uk"
VADARA_BASE = "https://www.vadara.uk"

SILKSTONE_URL = f"{TSC_BASE}/products/silkstone-quartz/"
NEOLITH_URL = f"{TSC_BASE}/products/neolith-by-the-size/"
VADARA_TSC_PAGES = {
    "divine": f"{TSC_BASE}/products/vadara-quartz/divine-natural-majesty/",
    "infusions": f"{TSC_BASE}/products/vadara-quartz/infusions/",
    "ebbs": f"{TSC_BASE}/products/vadara-quartz/ebbs-and-flows/",
    "hidden": f"{TSC_BASE}/products/vadara-quartz/hidden-inspiration/",
    "threads": f"{TSC_BASE}/products/vadara-quartz/threads-of-nature/",
}
VADARA_SITEMAP = f"{VADARA_BASE}/product-sitemap.xml"

# ---- known manual slug corrections (spelling/word-order drift vs price book) ----
VADARA_SLUG_OVERRIDES = {
    "calacatta dorado": "calacatta-dorada",
    "petro grigio": "petra-grigio",
    "white polar": "polar-white",
}
# Super Jumbo SKUs confirmed (2026-08-24) to have NO vadara.uk /designs/ page --
# harvested from thesurfacecollection.co.uk's Vadara sub-pages instead.
VADARA_TSC_ONLY = {"braewind", "nomad valley", "soraline"}


# --------------------------------------------------------------- TSC lightbox --
_TSC_ITEM_RE = re.compile(
    r'<div class="product__img x-content" data-bpopup=\'(?P<popup>.*?)\'>\s*'
    r'<div class="product__img-wrap">\s*<img src="(?P<mainimg>[^"]+)"[^>]*>\s*</div>\s*</div>'
    r'<div class="product-grid__details">\s*<h3 class="product-grid__header">(?P<header>.*?)</h3>',
    re.S)


def parse_tsc_lightbox_page(html_text):
    """Every product card on a thesurfacecollection.co.uk /products/... page.
    Returns [{"header": "Tuscan Grey 20mm", "popup_heading": "TUSCAN GREY 20MM",
    "photos": url, "swatch": url|None, "sizes": ["3200*1600", ...]}, ...]."""
    out = []
    for m in _TSC_ITEM_RE.finditer(html_text):
        popup = m.group("popup")
        header = H.unescape(re.sub(r'\s+', ' ', m.group("header"))).strip()
        hh = re.search(r'<h3 class="product-info__heading">(.*?)</h3>', popup)
        popup_heading = H.unescape(re.sub(r'\s+', ' ', hh.group(1))).strip() if hh else header
        sw = re.search(r'background-image:\s*url\(([^)]+)\)', popup)
        swatch = H.unescape(sw.group(1).strip()) if sw else None
        sizes = sorted(set(re.findall(r'<td>(\d+\*\d+)<td', popup)))
        mainimg = H.unescape(m.group("mainimg").strip())
        out.append({"header": header, "popup_heading": popup_heading,
                    "photos": mainimg, "swatch": swatch, "sizes": sizes})
    return out


def fetch_tsc(url, cache_key):
    return hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key)


# ------------------------------------------------------------------- Silkstone --
def harvest_silkstone():
    html_text = fetch_tsc(SILKSTONE_URL, "silkstone-top")
    items = parse_tsc_lightbox_page(html_text)
    print(f"Silkstone: {len(items)} product cards on {SILKSTONE_URL}", flush=True)
    return items


# --------------------------------------------------------------------- Neolith --
def harvest_neolith():
    html_text = fetch_tsc(NEOLITH_URL, "neolith-top")
    items = parse_tsc_lightbox_page(html_text)
    # drop obvious non-slab accessory items (sinks etc.)
    items = [it for it in items if "sink" not in it["header"].lower()]
    print(f"Neolith: {len(items)} product cards on {NEOLITH_URL}", flush=True)
    return items


# ---------------------------------------------------------------------- Vadara --
def vadara_sitemap_slugs():
    xml = hl.fetch_text(VADARA_SITEMAP, supplier=SUPPLIER, cache_key="vadara-product-sitemap")
    slugs = sorted(set(re.findall(r'https://www\.vadara\.uk/designs/([a-z0-9-]+)/', xml)))
    return slugs


def _core_name(pricebook_colour):
    s = re.sub(r'\(.*?\)', '', pricebook_colour)
    s = re.sub(r'\bV\d{3}L?\b', '', s, flags=re.I)
    s = re.sub(r'\bSuper Jumbo\b', '', s, flags=re.I)
    s = re.sub(r'\bLeathered\b', '', s, flags=re.I)
    s = re.sub(r'\bGroup\s*\d\b', '', s, flags=re.I)
    s = re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
    return re.sub(r'\s+', ' ', s)


def _vcode(pricebook_colour):
    m = re.search(r'\bV(\d{3})L?\b', pricebook_colour, flags=re.I)
    return f"V{m.group(1)}" if m else None


def harvest_vadara(vadara_colours):
    """vadara_colours: list of price-book Colour strings for the Vadara section.
    Returns {colour: {"source": "vadara.uk"|"tsc", "slug"/"page": .., "slab": url|None,
    "rooms": [url,...], "closeup": None}}."""
    slugs = vadara_sitemap_slugs()
    slug_norm = {re.sub(r'[^a-z0-9]', '', s): s for s in slugs}
    print(f"Vadara: {len(slugs)} /designs/ pages on sitemap", flush=True)

    out = {}
    for colour in vadara_colours:
        core = _core_name(colour)
        core = VADARA_SLUG_OVERRIDES.get(core, core)
        key = re.sub(r'[^a-z0-9]', '', core)
        slug = slug_norm.get(key)
        if not slug and core in VADARA_TSC_ONLY:
            out[colour] = {"source": "tsc-only", "slug": None}
            continue
        if not slug:
            out[colour] = {"source": "unresolved", "slug": None}
            continue
        out[colour] = {"source": "vadara.uk", "slug": slug}

    for colour, rec in out.items():
        if rec["source"] != "vadara.uk":
            continue
        slug = rec["slug"]
        url = f"{VADARA_BASE}/designs/{slug}/"
        try:
            html_text = fetch_tsc(url, f"design-{slug}")
        except Exception as e:
            print(f"  FETCH FAIL {colour} <- {url}: {e}", flush=True)
            rec["error"] = str(e)
            continue
        vcode = _vcode(colour)
        core_n = re.sub(r'[^a-z]', '', _core_name(colour))
        h1 = re.search(r'<h1[^>]*class="[^"]*post_title[^"]*"[^>]*>(.*?)</h1>', html_text, re.S)
        if h1:
            page_name_n = re.sub(r'[^a-z]', '', H.unescape(h1.group(1)).lower())
            if page_name_n:
                core_n = page_name_n  # the page's own on-page name is authoritative for
                                       # matching its own asset filenames (site spelling can
                                       # drift from the price-book name, e.g. Dorado/Dorada)
        imgs = re.findall(
            r'https://www\.vadara\.uk/wp-content/uploads/[^"\'\s)]+\.(?:jpe?g|png)', html_text, re.I)
        imgs = sorted(set(H.unescape(u) for u in imgs))

        def own(u):
            fn = u.split("/")[-1].lower()
            if vcode and vcode.lower() in fn:
                return True
            fn_n = re.sub(r'[^a-z]', '', fn)
            return bool(core_n) and core_n in fn_n

        excl = re.compile(r'story|logo|favicon|float|subscribe|certlogo|kosher', re.I)
        own_imgs = [u for u in imgs if own(u) and not excl.search(u)]

        def dedupe(seq):
            seen, res = set(), []
            for u in seq:
                base = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', u.split("/")[-1])
                if base in seen:
                    continue
                seen.add(base)
                res.append(u)
            return res

        slabs = dedupe([u for u in own_imgs if re.search(r'_(hires|web)\.', u, re.I)])
        # prefer HiRes over Web when both exist
        slabs.sort(key=lambda u: 0 if re.search(r'_hires\.', u, re.I) else 1)
        rooms = dedupe([u for u in own_imgs
                         if re.search(r'install|_render\d*\.', u, re.I)
                         and not re.search(r'-\d+x\d+\.', u)])[:6]
        rec["slab"] = slabs[0] if slabs else None
        rec["slab_alt"] = slabs[1:3]
        rec["rooms"] = rooms
        rec["closeup"] = None
        print(f"  {colour}: slug={slug} slab={'Y' if rec['slab'] else 'N'} rooms={len(rooms)}",
              flush=True)

    # TSC fallback pages for Super-Jumbo-only colours + as a general verifier source
    tsc_items_by_page = {}
    for key, url in VADARA_TSC_PAGES.items():
        try:
            html_text = fetch_tsc(url, f"vadara-tsc-{key}")
        except Exception as e:
            print(f"  FETCH FAIL vadara-tsc-{key} <- {url}: {e}", flush=True)
            continue
        tsc_items_by_page[key] = parse_tsc_lightbox_page(html_text)

    all_tsc_items = [it for items in tsc_items_by_page.values() for it in items]

    def tsc_match(colour):
        core = _core_name(colour)
        core_n = re.sub(r'[^a-z0-9]', '', core)
        vcode = _vcode(colour)
        best = None
        for it in all_tsc_items:
            hn = re.sub(r'[^a-z0-9]', '', it["header"].lower())
            if vcode and vcode.lower() in hn:
                return it
            if core_n and core_n in hn:
                best = best or it
        return best

    for colour, rec in out.items():
        if rec["source"] == "tsc-only":
            it = tsc_match(colour)
            if it:
                rec["tsc_photos"] = it["photos"]
                rec["tsc_swatch"] = it["swatch"]
                rec["tsc_sizes"] = it["sizes"]
                rec["tsc_header"] = it["header"]
                print(f"  {colour}: TSC fallback matched -> {it['header']!r}", flush=True)
            else:
                print(f"  {colour}: TSC fallback NOT FOUND", flush=True)
        elif rec["source"] == "vadara.uk":
            # verifier / size text fallback
            it = tsc_match(colour)
            if it:
                rec["tsc_sizes"] = it["sizes"]
                rec["tsc_header"] = it["header"]

    return out


def main():
    silkstone = harvest_silkstone()
    neolith = harvest_neolith()

    # price-book Vadara colour list (kept in sync with reconcile script's own load,
    # but harvest needs it too to know which /designs/ slugs to fetch)
    import csv
    rows = list(csv.DictReader(open(hl.PRICEBOOK_CSV, encoding="utf-8-sig")))
    tg = [r for r in rows if r.get("Supplier", "").strip() == "Thomas Group (Surfaces Collection)"]
    quartz_colours = sorted(set(r["Colour"].strip() for r in tg if r["Material"] == "Quartz"))
    vadara_colours = [c for c in quartz_colours if re.search(r'\bV\d{3}L?\b', c)]
    print(f"Quartz colours in price book: {len(quartz_colours)} | Vadara-coded: {len(vadara_colours)}",
          flush=True)

    vadara = harvest_vadara(vadara_colours)

    manifest = {"silkstone": silkstone, "neolith": neolith, "vadara": vadara,
                "vadara_colours": vadara_colours, "quartz_colours": quartz_colours}
    out_path = os.path.join(SCRATCH, "thomasgroup-quartz-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"WROTE {out_path}: silkstone={len(silkstone)} neolith={len(neolith)} vadara={len(vadara)}")


if __name__ == "__main__":
    main()
