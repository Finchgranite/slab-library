"""Thomas Group (Surfaces Collection) -- Porcelain (Atlas Plan) harvest.

76 price-book Porcelain colours under supplier "Thomas Group (Surfaces
Collection)" (sections "Atlas Plan - <Look>"). NONE exist in the library yet
-- every price-book colour becomes a new entry. Brand = Atlas Plan (an Atlas
Concorde brand); primary source atlasplan.com, per HARVEST-SPEC.md's
"Decisions" section ("New brands sold via a distributor").

Colour -> atlasplan.com slug resolution (66/76) was done by hand against the
site's own `/en/large-format-porcelain-slabs/` index page (which lists every
live product slug) -- see SLUG_MAP below. A further 7 colours have no live
atlasplan.com product page (the slug either 404s or soft-redirects to an
unrelated product) but ARE confirmed stocked on thesurfacecollection.co.uk's
single `/products/atlas-plan/` catalogue page (TSC_FALLBACK). The remaining 3
(Carrara Pure, Grigio Intenso, Kone Grey) are not found on either site --
confirmed via atlasplan.com direct-slug attempts (redirect to unrelated
pages), a full-text search of the TSC page, and a web search that only turned
up third-party distributor mentions (Gramaco) with no working atlasplan.com
URL. These 3 still get a library entry (price book is the naming authority)
but with no image (status "missing").

atlasplan.com page anatomy (curl OK, no bot protection):
  - CDN images live under storage.atlasplan.com/public/assets/large-slabs/{slug}/
    at *-clamp_WxH_Q.webp / *-clip_WxH_Q.webp (responsive variants) -- the
    unsuffixed filename (strip the trailing -clamp_###_###_##/-clip_###_###_##)
    is the true original and is directly fetchable (verified).
  - Main slab photo: filename `atlas-plan-epic-{slug}-{finish}-{size}-{thk}mm`
    (portrait orientation, slab is printed 162x324cm etc) -- NOT containing
    "-bookmatch". The "-bookmatch" sibling is the closeup/texture crop.
  - Numbered lifestyle shots `01-...`, `02-...` etc are room/kitchen photos;
    one of them (usually `04-...-surface-detail` or similar) is a closeup.
  - `{slug}-warehouse-...` is a generic warehouse photo -- always skipped.
  - Finish + thickness are in `data-filter="hammered"` / `data-filter="12mm"`
    radio inputs, but thicknesses/finishes/mm sizes are taken from the PRICE
    BOOK instead (it is the naming/size authority per HARVEST-SPEC and is
    already reconciled to real stock rows); the site is used only for
    images + a one-line blurb (meta description).

TSC fallback anatomy (thesurfacecollection.co.uk /products/atlas-plan/):
  each SKU is a `<div class="product-grid__item">` block: `<img
  src=".../lib/photos/{CODE}.jpg">` (main photo) preceding an `<h3
  class="product-grid__header">{Colour}</h3>` heading -- confirmed present for
  all 7 TSC_FALLBACK colours with a clean product code (e.g. Dolmen Pro Grigio
  -> AP-DPG-12.jpg). No closeup/room shots available this way -- slab-only
  entries.

Writes tools/thomasgroup-porcelain-harvest.json. Run once (cached under
tools/_cache/thomasgroup/); reconcile_thomasgroup_porcelain.py consumes it.
"""
import json
import os
import re
import subprocess

import harvest_lib as hl

SUPPLIER = "Thomas Group (Surfaces Collection)"
ATLAS_BASE = "https://www.atlasplan.com/en/large-format-porcelain-slabs/"
TSC_URL = "https://thesurfacecollection.co.uk/products/atlas-plan/"
SCRATCH = os.path.dirname(os.path.abspath(__file__))

# price-book Colour -> atlasplan.com slug (hand-resolved against the site's
# own index page, which lists every live product; see module docstring)
SLUG_MAP = {
    "Absolute Black": "absolute-black", "Absolute White": "absolute-white",
    "Alpinus": "alpinus", "Appennino": "appennino", "Baobab": "baobab",
    "Basaltina Volcano": "basaltina-volcano", "Bianco Dolomite": "bianco-dolomite",
    "Black Atlantis": "black-atlantis", "Black Lava": "black-lava",
    "Black Tempest": "black-tempest", "Blaze Iron": "blaze-iron",
    "Boost Ash Balance": "boost-balance-ash", "Boost Grey": "boost-grey",
    "Boost Icor Bone": "boost-icor-bone", "Boost Icor Dune": "boost-icor-dune",
    "Boost Mineral Grey": "boost-mineral-grey", "Boost Natural Ecru": "boost-natural-ecru",
    "Boost Smoke": "boost-smoke", "Boost Stone Ivory": "boost-stone-ivory",
    "Boost Tarmac": "boost-tarmac", "Boost Vision Camel": "boost-vision-camel",
    "Boost White": "boost-white", "Calacatta Antique": "calacatta-antique",
    "Calacatta Apuano": "calacatta-apuano", "Calacatta Bernini": "calacatta-bernini",
    "Calacatta Delicato": "calacatta-delicato", "Calacatta Extra": "calacatta-extra",
    "Calacatta Gold": "calacatta-gold", "Calacatta Imperial": "calacatta-imperiale",
    "Calacatta Imperiale": "calacatta-imperiale", "Calacatta Prestigo": "calacatta-prestigio",
    "Calacatta Viola": "calacatta-viola", "Calacattta Meraviglia": "calacatta-meraviglia",
    "Cream Prestige": "cream-prestige", "Crystal White": "crystal-white",
    "Desert Soul": "desert-soul", "Exotic Green": "exotic-green", "Exotic Wave": "exotic-wave",
    "Fior Di Bosco": "fior-di-bosco", "Grey Stone": "grey-stone", "Ice Crystal": "ice-crystal",
    "Kone Mix": "kone-mix", "Light Grey Stone": "light-grey-stone",
    "Natural Roots": "natural-roots", "Negresco": "negresco", "Nero Marquina": "nero-marquina",
    "Noce Canaletto": "noce-canaletto", "Onyx White": "onyx-white",
    "Precious Brown": "precious-brown", "Silver Root": "silver-root", "Sky Stone": "sky-stone",
    "Soapstone Dark": "soapstone-dark", "Statuario Supremo": "statuario-supremo",
    "Taj Mahal": "taj-mahal", "Taj Mahal (Atlas Plan)": "taj-mahal",
    "Taj Mahal Noisette": "taj-mahal-noisette", "Taj Mahal White": "taj-mahal-white",
    "Travertine Halo White": "travertino-halo-white", "Travertine Pearl": "travertino-pearl",
    "Travertine Romano Sand": "travertino-romano-sand",
    "Travertine Romano Silver": "travertino-romano-silver",
    "Travertine Sand": "travertino-sand", "Travertine White": "travertino-white",
    "Travertino Sand": "travertino-sand", "White Cloud": "white-cloud", "Zephyr": "zephyr",
}

# colour -> TSC product-photo code (thesurfacecollection.co.uk /lib/photos/{code}.jpg)
TSC_FALLBACK = {
    "Calacatta Royal": "AP-CRP-12", "Concrete Grey": "AP-CGS-12",
    "Dolmen Pro Grigio": "AP-DPG-12", "Kone Gypsum": "AP-KGYM-12",
    "Nero Zimbabwe": "AP-NZM-12_v2", "Statuario Select": "AP-SSP-12",
    "White Terrazzo": "AP-WTS-12",
}

NOT_FOUND = ["Carrara Pure", "Grigio Intenso", "Kone Grey"]

_WAREHOUSE_RE = re.compile(r'warehouse', re.I)
_BOOKMATCH_RE = re.compile(r'bookmatch', re.I)
# every printed-size token atlasplan.com uses across its slab formats
_SIZE_TOKEN_RE = re.compile(r'\b\d{3}x\d{3}\b', re.I)
_DETAIL_RE = re.compile(r'detail|texture|surface', re.I)
_ROOM_RE = re.compile(
    r'kitchen|dining|room|interior|shelves|wall|table|vanity|bathroom|cladding|island|space|living',
    re.I)


def _strip_clamp(url):
    """Strip the responsive -clamp_W_H_Q / -clip_W_H_Q suffix -- sometimes
    the true original upload (verified for some colours, e.g. Alpinus,
    Baobab) but NOT always (e.g. Appennino 404s) -- caller must verify."""
    return re.sub(r'-(?:clamp|clip)_\d+_\d+_\d+(?=\.[a-zA-Z0-9]+$)', '', url)


def _head_ok(url):
    """Cheap existence check (HEAD, single try, short timeout, uncached --
    this is a one-off metadata probe, not a download)."""
    try:
        r = subprocess.run(["curl", "-sI", "-A", hl.UA, "--max-time", "10", url],
                            capture_output=True, timeout=15)
        return r.returncode == 0 and b"200" in r.stdout.split(b"\r\n", 1)[0]
    except Exception:
        return False


def _best_slab_url(raw_url):
    """The raw CDN url (e.g. ...-clamp_960_1920_50.webp) straight from the
    page is ALWAYS valid (it's literally referenced in the live HTML) and,
    at 960-1920px, already exceeds the library's max_w=1600 webp target --
    so it's a perfectly good fallback. Only upgrade to the stripped "true
    original" filename when a quick HEAD check confirms it actually exists
    (no retry/backoff spent chasing a guess that 404s)."""
    stripped = _strip_clamp(raw_url)
    if stripped != raw_url and _head_ok(stripped):
        return stripped
    return raw_url


def harvest_atlas_colour(colour, slug):
    url = ATLAS_BASE + slug + "/"
    try:
        html_text = hl.fetch_text(url, supplier="thomasgroup", cache_key=f"atlas-{slug}")
    except Exception as e:
        return {"colour": colour, "url": url, "error": str(e)}

    m = re.search(r'<meta name="description" content="([^"]*)"', html_text)
    description = hl.H.unescape(m.group(1)).strip() if m else ""

    imgs = hl.extract_images(html_text, url)
    own = []  # [(url, filename, im)] for this colour's own (deduped, non-warehouse) images
    seen_base = set()
    for im in imgs:
        u = im["url"]
        if f"/large-slabs/{slug}/" not in u:
            continue
        fn = u.rsplit("/", 1)[-1]
        base = re.sub(r'-(?:clamp|clip)_\d+_\d+_\d+(?=\.[a-zA-Z0-9]+$)', '', fn)
        if base in seen_base or _WAREHOUSE_RE.search(fn):
            continue
        seen_base.add(base)
        own.append((u, fn, im))

    # Pass 1 -- order-independent, high-confidence signals only. A filename
    # carrying a printed slab-size token (162x324, 160x320 etc) without
    # "bookmatch" is the branded full-slab photo; iteration order matters
    # (numbered lifestyle shots like "01-..." often appear earlier in the
    # DOM and, being marketing copy, frequently contain the bare word
    # "slab" too -- e.g. "01-appennino-...-slab-atlas-plan" is actually a
    # KITCHEN photo -- so this pass must scan every image for the strong
    # size-token signal before any weaker fallback gets a chance to claim
    # `slab` first).
    slab = None
    bookmatches = []
    for u, fn, im in own:
        if _BOOKMATCH_RE.search(fn):
            bookmatches.append(u)
        elif _SIZE_TOKEN_RE.search(fn) and not slab:
            slab = _best_slab_url(u)

    slab_is_closeup = False
    if not slab and bookmatches:
        # some colours only have bookmatch shots, no separate non-bookmatch
        # full-slab photo -- promote the first bookmatch crop to `slab` (it
        # is still a genuine photo of the physical slab) and mark it so the
        # reconciler can set image.status "closeup-only" rather than "slab"
        slab = bookmatches.pop(0)
        slab_is_closeup = True

    # Pass 2 -- everything not already claimed as slab/bookmatch-closeup.
    # closeups/rooms use the raw CDN url as-is (960-1920px, already exceeds
    # the library's max_w=1600 webp target, and it's directly off the live
    # page so it's guaranteed to exist -- no guessing needed here).
    closeups, rooms = list(bookmatches), []
    for u, fn, im in own:
        if _BOOKMATCH_RE.search(fn) or _SIZE_TOKEN_RE.search(fn):
            continue  # already handled in pass 1 (the slab pick, or a
                       # redundant second size-labelled dupe -- skip either way)
        if _DETAIL_RE.search(fn):
            closeups.append(u)
        elif _ROOM_RE.search(im["alt"] + " " + fn):
            rooms.append(u)
        else:
            kind = hl.classify_kind(u, im["alt"], "", im["width"], im["height"])
            if kind == "closeup":
                closeups.append(u)
            elif kind == "room":
                rooms.append(u)
            # deliberately NOT trusting a "slab" classify_kind() fallback
            # here -- harvest_lib's SLAB_HINTS matches the bare word "slab"
            # in filenames that are actually room/lifestyle photos (see
            # Appennino above); `slab` is only ever set in pass 1.

    return {
        "colour": colour, "slug": slug, "url": url, "source": "atlasplan.com",
        "description": description,
        "slab": slab, "slab_is_closeup": slab_is_closeup,
        "closeups": closeups[:4], "rooms": rooms[:6],
    }


def harvest_tsc_page():
    return hl.fetch_text(TSC_URL, supplier="thomasgroup", cache_key="tsc-atlas-plan")


def harvest_tsc_colour(colour, code, tsc_html):
    slab = f"https://thesurfacecollection.co.uk/lib/photos/{code}.jpg"
    return {
        "colour": colour, "slug": None, "url": TSC_URL, "source": "thesurfacecollection.co.uk",
        "description": "", "slab": slab, "closeups": [], "rooms": [],
    }


def main():
    pb = hl.load_pricebook(SUPPLIER)
    por_colours = sorted(c for c, info in pb.items())
    print(len(por_colours), "price-book colours for", SUPPLIER, flush=True)

    manifest = []
    for colour in por_colours:
        if colour in SLUG_MAP:
            rec = harvest_atlas_colour(colour, SLUG_MAP[colour])
        elif colour in TSC_FALLBACK:
            rec = harvest_tsc_colour(colour, TSC_FALLBACK[colour], None)
        elif colour in NOT_FOUND:
            rec = {"colour": colour, "slug": None, "url": "", "source": "",
                   "description": "", "slab": None, "closeups": [], "rooms": []}
        else:
            print("!! unmapped colour, skipping:", colour, flush=True)
            continue
        manifest.append(rec)
        print(f"{colour:32s} src={rec['source'] or '-':22s} slab={'Y' if rec['slab'] else 'N'} "
              f"cu={len(rec['closeups'])} rm={len(rec['rooms'])}", flush=True)

    out_path = os.path.join(SCRATCH, "thomasgroup-porcelain-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nWROTE {out_path}: {len(manifest)} colours "
          f"({sum(1 for r in manifest if r['slab'])} with a slab image)")


if __name__ == "__main__":
    main()
