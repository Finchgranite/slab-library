"""Neolith (neolith.com, supplier 'Neolith') harvest -- phase 2 galleries pass.

Diligence done before writing this (2026-08-25, see tools/_cache/neolith/ for the
raw evidence):
  - neolith.com is NOT bot-blocked to curl (200 OK, real SSR HTML) -- that
    differs from the 2026-08-24 Thomas Group discovery note. BUT each colour's
    product page (and its Nuxt static state.js/payload.js sidecars) carries
    exactly ONE product photo (the slab -- Storyblok filename usually
    "neolith_<slug>_slab.jpg" or "<slug>_NxNpx.jpg"). No closeup/texture crop
    and no room/application photo exists anywhere in the static payload for a
    product page; the "NEOLITH GALLERY"/kitchens/projects grids are hydrated
    by a live runtime API call this curl-only agent cannot reach. This matches
    tools/scrape_neolith_harvest.py's docstring (a human had to drive Chrome
    page-by-page to collect even the ONE slab URL per colour) -- there simply
    is no second image to find via curl on neolith.com itself.
  - thesurfacecollection.co.uk's single /products/neolith-by-the-size/ page
    (Thomas Group's "Neolith by The Size" line) carries exactly ONE photo +
    ONE matching swatch crop per SKU via data-bpopup lightbox HTML, for 16
    colours -- only 5 of which match existing "Neolith" library entries
    (Beton, Calacatta (BM), Calacatta Gold (BM), Estatuario (BM), Zaha Stone);
    those 5 already carry that TSC closeup in images[] from an earlier run.
    The other 11 TSC names (Avorio, Nieve, Pierre Bleue, Phedra, Cement,
    Basalt Beige, Bianco Carrara, La Boheme, Nero Marquina x2, Iron Moss) are
    NOT in our 45-colour Neolith scope (different colourways) -- out of scope
    per the brief ("work only on Neolith entries").
  - The OneDrive Neolith folder already held an un-extracted official asset
    pack, `laurelcomms_full-uk-neolith-colour-collection_2026-03-31_0945.zip`
    (Jan 2026 Neolith UK brochure + full slab-photo set, one JPG per colour,
    "<NAME>_<dims>_low.jpg"/plain "<Name>.jpg"). This covers ALL 45 colours
    including the 4 that were `missing`, so it is the primary source for
    those 4 real slab-face fills. Filenames for the 4 missing:
      Black Obsession   -> BLACK-OBSESSION_3200X1600X12-20_low.jpg
      Calacatta Roma    -> CALACATTA ROMA.jpg              (low-res, ~1623KB)
      Cappadocia Sunset -> CAPADOCIA-SUNSET-CS-01_3200x1500x6_low.jpg
      Everest Sunrise   -> EVEREST-SUNRISE-ES-01_3200X1600X12-20_low.jpg
    Two of those four DO still have a live neolith.com page (confirmed by
    curl, 200 + correct <title>) even though the library never recorded a
    productUrl for them -- classtone/calacatta-roma/ and
    classtone/everest-sunrise/ -- and their Storyblok originals are much
    higher-res than the zip copy, so those two are fetched live instead.
    Black Obsession and Cappadocia Sunset are confirmed ABSENT from the
    current /en/all-colours payload (no "black"/"cappadocia" string anywhere
    in it) -- i.e. genuinely delisted from the live site, not a guessing
    failure -- so the zip is the only source and productUrl stays blank for
    those two.
  - The brochure PDF (inside the same zip) has exactly one usable >300px
    "room" photo across its whole 17 pages: page 7 (0-indexed 6), a London
    private-residence kitchen captioned "Neolith Himalaya Crystal"
    (1009x771). Everything else image-sized in the brochure is either an
    award-logo montage or a <300px swatch grid -- skipped per spec rule 3.

This script does the local zip/PDF extraction + the 2 live Storyblok fetches
and writes tools/neolith-harvest.json for reconcile_neolith.py to apply.
Colour->pricebook slabSizes/details are computed in reconcile_neolith.py
directly from hl.load_pricebook("Neolith") (1:1 name match against all 45
library colours, verified before writing this).
"""
import json
import os
import re
import zipfile

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "neolith"
CACHE = os.path.join(hl.CACHE_ROOT, SUPPLIER)
os.makedirs(CACHE, exist_ok=True)

ZIP_PATH = os.path.join(
    hl.BRANDS_ROOT, "3. CERAMIC- PORCELAIN", "Neolith",
    "laurelcomms_full-uk-neolith-colour-collection_2026-03-31_0945.zip")
ZIP_ROOT = "FULL UK NEOLITH COLOUR COLLECTION"

# colour -> zip member (relative to ZIP_ROOT) for the 4 missing-main colours
MISSING_ZIP_MEMBERS = {
    "Black Obsession": "slabs/BLACK-OBSESSION_3200X1600X12-20_low.jpg",
    "Cappadocia Sunset": "slabs/CAPADOCIA-SUNSET-CS-01_3200X1500X6_low.jpg",
}
# live neolith.com pages confirmed 200 + correct <title> for these 2 (missing
# `productUrl` in the library despite being live) -- fetch full-res original
LIVE_MISSING = {
    "Calacatta Roma (BM)": "https://www.neolith.com/en/collections/classtone/calacatta-roma/",
    "Everest Sunrise": "https://www.neolith.com/en/collections/classtone/everest-sunrise/",
}
STORYBLOK_SLAB_RE = re.compile(r'(?:a\.storyblok\.com)(/f/150360/\d+x\d+/[a-f0-9]+/[^"\'\s]+\.(?:jpe?g|png))', re.I)

# brochure PDF: page index (0-based), colour, bbox of the one usable room photo
BROCHURE_ROOM = {"colour": "Himalaya Crystal", "page": 6, "xref": 261,
                  "caption": "Private residence, London, UK -- Neolith Himalaya Crystal"}


def safe(colour):
    return re.sub(r'\W+', '_', colour)


def extract_zip_image(colour, member):
    z = zipfile.ZipFile(ZIP_PATH)
    name = f"{ZIP_ROOT}/{member}"
    data = z.read(name)
    fn = os.path.basename(member)
    return data, fn


def fetch_live_slab(colour, url):
    cache_key = re.sub(r'\W+', '_', colour)
    html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key, delay=10, polite_delay=10)
    m = STORYBLOK_SLAB_RE.search(html_text)
    if not m:
        return None, None
    img_url = "https://a.storyblok.com" + m.group(1)
    data = hl.fetch(img_url, supplier=SUPPLIER, cache_key=cache_key + "_img", binary=True, polite_delay=2)
    fn = img_url.rsplit("/", 1)[-1]
    return data, fn


def extract_brochure_room():
    import fitz
    pdf_cache = os.path.join(CACHE, "brochure.pdf")
    if not os.path.exists(pdf_cache):
        z = zipfile.ZipFile(ZIP_PATH)
        data = z.read(f"{ZIP_ROOT}/UK brochure/Neolith_UK_Brochure_kitchen_bath_2026.pdf")
        open(pdf_cache, "wb").write(data)
    doc = fitz.open(pdf_cache)
    page = doc[BROCHURE_ROOM["page"]]
    xref = BROCHURE_ROOM["xref"]
    pix = fitz.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    png_bytes = pix.tobytes("png")
    return png_bytes, "himalaya-crystal-room-london.png"


def main():
    manifest = {}

    cache_files = {}
    for colour, member in MISSING_ZIP_MEMBERS.items():
        try:
            data, fn = extract_zip_image(colour, member)
            cf = f"missing__{safe(colour)}__{fn}"
            open(os.path.join(CACHE, cf), "wb").write(data)
            manifest[colour] = {"source": "Neolith UK official asset pack (2026 zip)", "productUrl": "", "fn": fn}
            cache_files[colour] = cf
            print(f"zip OK: {colour} <- {member} ({len(data)} bytes)")
        except KeyError as e:
            print(f"ZIP MEMBER MISSING for {colour}: {member} ({e})")

    for colour, url in LIVE_MISSING.items():
        data, fn = fetch_live_slab(colour, url)
        if data:
            cf = f"live__{safe(colour)}__{fn}"
            open(os.path.join(CACHE, cf), "wb").write(data)
            manifest[colour] = {"source": "neolith.com", "productUrl": url, "fn": fn}
            cache_files[colour] = cf
            print(f"live OK: {colour} <- {url} -> {fn} ({len(data)} bytes)")
        else:
            print(f"LIVE FETCH FAILED (no storyblok match) for {colour}: {url}")

    room_data, room_fn = extract_brochure_room()
    room_cache_file = f"room__{room_fn}"
    open(os.path.join(CACHE, room_cache_file), "wb").write(room_data)
    print(f"brochure room OK: {BROCHURE_ROOM['colour']} -> {room_fn} ({len(room_data)} bytes)")

    out = {
        "missing_fills": {c: {"cache_file": cache_files[c], "source": v["source"],
                               "productUrl": v["productUrl"], "fn": v["fn"]}
                          for c, v in manifest.items()},
        "brochure_room": {"colour": BROCHURE_ROOM["colour"], "cache_file": room_cache_file,
                           "caption": BROCHURE_ROOM["caption"],
                           "source": "Neolith UK Brochure (kitchen & bath, Jan 2026)"},
    }
    out_path = os.path.join(SCRATCH, "neolith-harvest.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("WROTE", out_path)


if __name__ == "__main__":
    main()
