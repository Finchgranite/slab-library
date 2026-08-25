"""International Stones (IQ) harvest -- www.istones.co.uk (57 existing quartz
productUrls already point here; this pass also discovers it has a *complete*,
uniform product-page template for PORCELAIN too, at /porcelain/<slug>.html,
which the price book/library didn't previously know about).

Site pattern (same template for quartz.html and porcelain.html catalogues):
  - Listing page /quartz.html or /porcelain.html: <a href="quartz/<slug>.html">
    for every colour (some colours only listed under a "-matte"/"-soft"/
    "-satin"/"-natural"/"-<year>" finish-suffixed slug -- there is no
    sitemap.xml on this host).
  - Per-colour page /quartz/<slug>.html or /porcelain/<slug>.html:
      * slab main: images/<material>/slabs/<slug>-320x160-crop.png (despite
        the filename, the served asset is actually ~1120x560 -- a real photo,
        not a 320x160 thumb).
      * closeup/texture: the "actual size" viewer's 2nd background-image url,
        images/<material>/<slug>-actual.jpg (large near-1:1 texture crop).
      * room shots: QUARTZ ONLY -- images/quartz/insitu/<slug>-N.jpg (an
        #insitu lightSlider). Porcelain pages have no #insitu section at all.
      * dimensions-new / thickness-new / finish-new text nodes in the
        #stock-new block give real cm slab size + thickness + finish; the
        details-column svg titles give material type + Origin.
  - A commented-out <!-- TEMPLATE --> block reuses the literal placeholder
    "MATERIAL-TYPE"/"MATERIAL" in its img src -- excluded automatically since
    we only accept slab/closeup/room URLs containing the page's own exact
    slug.

9 porcelain colours (Black, Cement Ivory, Cement Light Gray, Golden Spider,
Grey Gray i.e. "Marble Gray", Stone Gris, Super White, White, Yamuna) and 3
quartz colours (Calacatta Magma Gold, Calacatta Skylight, Vienne) have NO
istones.co.uk page (checked both the listing and direct slug guesses) --
these are left out of the manifest; reconcile_iq.py reports them as
"no istones.co.uk page found" and leaves their existing (already-good, status
"slab") main/productUrl untouched.

Writes tools/iq-harvest.json. Re-run: cached under tools/_cache/iq/.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "iq"
BASE = "https://www.istones.co.uk"

# colour -> forced slug, for cases the automatic token-subset matcher can't
# resolve (year-suffixed "dated" variants where the plain slug means a
# DIFFERENT still-current colour, or a colour that only exists in a
# finish-suffixed slug on the listing).
OVERRIDES = {
    "Argenti '25": "argenti-2025",
    "Iron Flux '22": "iron-flux-2022",
    "Roma '24": "roma-2024",
    "Onyx Opaque '20": "onyx-opaque-2020",
    "Grey Graphite": "grey-grafite-soft",
    "Solid Clay": "solid-clay-matte",
    "Pure White": "pure-white-matte",
    "Marble Calacatta Velvet": "marble-calacatta-velvet-matte",
    "Stone Alpine Brown": "stone-alpine-brown-matte",
}

# colours confirmed (listing scan + direct slug probes) to have NO
# istones.co.uk page at all -- don't waste a fetch trying.
KNOWN_ABSENT = {
    "Black", "Cement Ivory", "Cement Light Gray", "Golden Spider", "Marble Gray",
    "Stone Gris", "Super White", "White", "Yamuna",
    "Calacatta Magma Gold", "Calacatta Skylight", "Vienne",
}

_FINISH_SUFFIX = re.compile(r'-(matte|soft|natural|satin|fullvein3d|fullbody3d|3d)$')


def slug_to_bare(slug):
    s = slug
    while True:
        m = _FINISH_SUFFIX.search(s)
        if not m:
            break
        s = s[:m.start()]
    return s.replace('-', ' ')


def get_listing_slugs(material):
    path = "quartz.html" if material == "Quartz" else "porcelain.html"
    key = "quartz" if material == "Quartz" else "porcelain"
    html_text = hl.fetch_text(f"{BASE}/{path}", supplier=SUPPLIER, cache_key=f"_{key}-listing")
    sub = "quartz" if material == "Quartz" else "porcelain"
    return sorted(set(re.findall(rf'href="{sub}/([a-z0-9-]+)\.html"', html_text)))


def build_slug_map(entries):
    """{entry_colour: (material, slug)} for every colour we can resolve."""
    qslugs = get_listing_slugs("Quartz")
    pslugs = get_listing_slugs("Porcelain")
    # the 4 colours only reachable via a direct -matte guess (not linked from
    # the porcelain.html nav, but the pages exist -- see OVERRIDES).
    for extra in ("solid-clay-matte", "pure-white-matte",
                  "marble-calacatta-velvet-matte", "stone-alpine-brown-matte"):
        if extra not in pslugs:
            pslugs.append(extra)
    qpool = [(slug_to_bare(s), s) for s in qslugs]
    ppool = [(slug_to_bare(s), s) for s in pslugs]

    out = {}
    for e in entries:
        colour = e["colour"]
        if colour in KNOWN_ABSENT:
            continue
        if colour in OVERRIDES:
            out[colour] = (e["material"], OVERRIDES[colour])
            continue
        pool = qpool if e["material"] == "Quartz" else ppool
        m, score = hl.match_colour(colour, pool)
        if m:
            out[colour] = (e["material"], m)
    return out


def parse_field(html_text, cls):
    m = re.search(rf'class="{cls}">(.*?)</div>', html_text, re.S)
    if not m:
        return ""
    txt = re.sub(r'<[^>]+>', ' ', m.group(1))
    return H.unescape(re.sub(r'\s+', ' ', txt)).strip()


def harvest_one(colour, material, slug):
    sub = "quartz" if material == "Quartz" else "porcelain"
    url = f"{BASE}/{sub}/{slug}.html"
    cache_key = f"{sub}-{slug}"
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key)
    except Exception as e:
        return {"colour": colour, "material": material, "slug": slug, "url": url, "error": str(e)}

    # strip the commented-out <!-- TEMPLATE STOCK LISTINGS --> block -- it has
    # its own literal "FINISH"/"WIDTH"/"HEIGHT" placeholders AND a hardcoded
    # "3 cm & 2 cm" thickness-new div that otherwise wins re.search's
    # first-match (it appears before the page's real stock block).
    html_text = re.sub(r'<!--.*?-->', '', html_text, flags=re.S)

    slab = None
    # most colours: <slug>-320x160-crop.png; some have an -a/-b photo-set
    # suffix (e.g. antique-white-soft-a-...) or omit "-crop" entirely
    # (e.g. quarzite-luna-soft-3d-320x160.png). The slabs/ filename (but not
    # the closeup/room ones) also sometimes abbreviates "fullvein3d"/
    # "fullbody3d" to "fv3d"/"fb3d" (e.g. statuario-select-soft-fv3d-a-...).
    slug_slab_re = re.escape(slug).replace(re.escape("fullvein3d"), "(?:fullvein3d|fv3d)") \
        .replace(re.escape("fullbody3d"), "(?:fullbody3d|fb3d)")
    m = re.search(rf'images/{sub}/slabs/{slug_slab_re}(?:-[ab])?-320x160(?:-crop)?\.png', html_text)
    if m:
        slab = BASE + "/" + m.group(0)

    closeup = None
    m = re.search(rf'images/{sub}/{re.escape(slug)}-actual\.jpg', html_text)
    if m:
        closeup = BASE + "/" + m.group(0)

    rooms = []
    if material == "Quartz":
        rooms = [BASE + "/images/quartz/insitu/" + fn
                 for fn in re.findall(rf'images/quartz/insitu/({re.escape(slug)}-\d+\.jpg)', html_text)]
        seen, dedup = set(), []
        for r in rooms:
            if r not in seen:
                seen.add(r)
                dedup.append(r)
        rooms = dedup

    dims_m = re.search(r'class="dimensions-new">\s*<span class="numbers">(\d+)</span>\s*x\s*'
                        r'<span class="numbers">(\d+)</span>', html_text)
    dims_mm = None
    if dims_m:
        w, h = int(dims_m.group(1)) * 10, int(dims_m.group(2)) * 10
        dims_mm = f"{w}x{h}"

    thicknesses_mm = []
    for block in re.findall(r'class="thickness-new">(.*?)</div>', html_text, re.S):
        for n in re.findall(r'class="numbers">([\d.]+)</span>', block):
            thicknesses_mm.append(round(float(n) * 10))
    thicknesses_mm = sorted(set(thicknesses_mm))

    finish = parse_field(html_text, "finish-new")
    origin_m = re.search(r'pin-icon.*?</svg>\s*([A-Z][A-Za-z ]+?)\s*</div>', html_text, re.S)
    origin = H.unescape(origin_m.group(1)).strip() if origin_m else ""

    return {
        "colour": colour, "material": material, "slug": slug, "url": url,
        "slab": slab, "closeup": closeup, "rooms": rooms,
        "dims_mm": dims_mm, "thicknesses_mm": thicknesses_mm,
        "finish": finish, "origin": origin,
    }


def main():
    lib = hl.load_library()
    entries = [s for s in lib["slabs"] if s.get("supplier") == "International Stones (IQ)"
               and not s.get("naturalStone")]
    print(len(entries), "engineered IQ library entries", flush=True)

    slug_map = build_slug_map(entries)
    print(len(slug_map), "resolved to an istones.co.uk page;",
          len(entries) - len(slug_map), "not found (see KNOWN_ABSENT / report)", flush=True)

    manifest = []
    for i, e in enumerate(entries, 1):
        colour = e["colour"]
        if colour not in slug_map:
            continue
        material, slug = slug_map[colour]
        rec = harvest_one(colour, material, slug)
        manifest.append(rec)
        if rec.get("error"):
            print(f"[{i}] FETCH FAIL {colour}: {rec['error']}", flush=True)
        else:
            print(f"[{i}] {colour} ({material}) slug={slug} slab={'Y' if rec['slab'] else 'N'} "
                  f"closeup={'Y' if rec['closeup'] else 'N'} rooms={len(rec['rooms'])} "
                  f"dims={rec['dims_mm']} thk={rec['thicknesses_mm']}", flush=True)

    out_path = os.path.join(SCRATCH, "iq-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    unmatched_colours = sorted(e["colour"] for e in entries if e["colour"] not in slug_map)
    print(f"\nWROTE {out_path}: {len(manifest)} pages harvested")
    print("colours with NO istones.co.uk page:", unmatched_colours)


if __name__ == "__main__":
    main()
