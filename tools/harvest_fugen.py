"""Fugen (fugenstone.co.uk, WooCommerce) harvest -- phase 2.

Colour list comes from https://fugenstone.co.uk/product-sitemap.xml (Rank Math
SEO sitemap), filtered to /product/quartz-worktops/... (porcelain excluded --
none of our 46 engineered Fugen library entries are porcelain).

Every product page follows one of two Elementor templates but BOTH carry:
  - a filename containing "slab" (any case: "IMPERIUM_slab.jpg" /
    "Roma-Slab-2-1-scaled.jpg") for the true full-slab photo, always under an
    "Entire Slab"/"Entire slab" heading, NOT part of the WooCommerce JSON-LD
    gallery. Aspect is exactly/near 2:1.
  - a WooCommerce JSON-LD `"image":[...]` array (the product gallery) holding:
      * "*Tile*" (portrait ~0.67 ratio) or old-template "441_FUGENSTONE_*.jpg"
        / "..._R.jpg" (600x900 / 900x600) -- texture close-up crops.
      * "*-comp.jpg" / "©-Beth-Davis_...Flatlays..." -- styled flat-lay
        mood-board shots (props/fabric swatches on linen) -- NOT usable as
        slab/closeup/room, skipped.
      * "*Gallery*" or "*Gallery-1*" (no trailing number, or "-1") -- another
        texture close-up crop.
      * "*Gallery-2*", "*Gallery-3*", "*Set-1*" etc (trailing number >= 2, or
        "Set-N") -- real kitchen/room installation photos.
    (Verified visually against Celestial, Roma, Marfil Luxe, Matrix Leather,
    Imperium before writing this classifier -- see tools/_cache/fugen/preview*)
  - an info block of `text-editor.default">TEXT<` divs in a fixed order:
    [0]=blank, [1]="LxW mm" slab size, [2]=thickness note, [3]=finish text
    (e.g. "Leather or Polished", "Polished and Satin", "Leathered"),
    [4]=material. Price book remains the sizing authority; this is a fallback.
  - a JSON-LD Product `"description"` -- used verbatim as the one-line
    `details` blurb.

Finish-variant colours (price book splits "X Leather" / "X Polished" into
separate rows) map to ONE site product ("x") whose WooCommerce
`data-product_variations` image is IDENTICAL across finishes (confirmed on
Celestial) -- so both/all price-book finish rows for a core colour get the
same slab/closeup/room images, differentiated only by `details` finish text.
Matching is done on a finish-stripped "core" name (see strip_finish()).

Writes tools/fugen-harvest.json. Re-run is cheap: pages are cached under
tools/_cache/fugen/; delete that dir to force a re-fetch.
"""
import html as H
import json
import os
import re
import difflib

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "fugen"
BASE = "https://fugenstone.co.uk"
SITEMAP = BASE + "/product-sitemap.xml"

MOOD_BOARD_HINTS = re.compile(r'beth-davis|flatlay|-comp\.', re.I)
TILE_HINTS = re.compile(r'tile|^441_fugenstone_|_r\.jpg$', re.I)
GALLERY_RE = re.compile(r'gallery-?(\d*)', re.I)
SET_RE = re.compile(r'(?:^|[-_])set-?(\d*)', re.I)
FINISH_WORDS = {"leather", "polished", "satin"}


def get_product_urls():
    xml = hl.fetch_text(SITEMAP, supplier=SUPPLIER, cache_key="_product-sitemap")
    locs = sorted(set(re.findall(r'<loc>(https://fugenstone\.co\.uk/product/[^<]+)</loc>', xml)))
    return [u for u in locs if "/quartz-worktops/" in u]


def slug_and_name(url):
    slug = url.rstrip("/").split("/")[-1]
    name = slug.replace("-", " ").title()
    name = re.sub(r'\s+\d+$', '', name)                         # "Silver Drift 2" -> "Silver Drift"
    name = re.sub(r'\s+Polished And Satin$', '', name, flags=re.I)  # "Jasper Polished And Satin" -> "Jasper"
    return slug, name.strip()


def strip_finish(name):
    toks = name.split()
    while toks and toks[-1].lower() in FINISH_WORDS:
        toks.pop()
    return " ".join(toks) or name


def parse_info_block(html_text):
    vals = [H.unescape(m.group(1)).strip()
            for m in re.finditer(r'text-editor\.default">([^<]*)<', html_text)]
    vals = [v for v in vals[:6]]
    dims = vals[1] if len(vals) > 1 else ""
    thickness_note = vals[2] if len(vals) > 2 else ""
    finish = vals[3] if len(vals) > 3 else ""
    material = vals[4] if len(vals) > 4 else ""
    return dims, thickness_note, finish, material


def parse_description(html_text):
    m = re.search(r'"@type":"Product".*?"description":"((?:[^"\\]|\\.)*)"', html_text, re.S)
    if not m:
        return ""
    try:
        decoded = json.loads('"' + m.group(1) + '"')   # proper JSON string decode (—, \/, \" etc.)
    except Exception:
        decoded = m.group(1).replace('\\/', '/').replace('\\"', '"')
    return H.unescape(decoded).strip()


def own_asset(fn_low, slug_tokens):
    """Guard against 'Related Designs' carousel thumbnails of OTHER colours
    that also appear on the page (verified present, e.g. Celestial's page
    embeds Black-Shimmer.jpg/Pietra-Grey.jpg for its related-products strip --
    those don't carry slab/tile/gallery/set keywords so classify() already
    skips them, but this is a second check for belt-and-braces)."""
    base = re.split(r'slab|tile|gallery|_r$|-set-?\d*|\d', fn_low)[0]
    base = re.sub(r'[^a-z]', ' ', base).strip()
    if not base:
        return True
    fn_toks = set(base.split())
    for t in slug_tokens:
        if t in fn_toks:
            return True
        if difflib.get_close_matches(t, fn_toks, n=1, cutoff=0.8):
            return True
    return False


def classify(url, slug_tokens):
    fn = url.split("/")[-1]
    fn_low = fn.lower()
    if MOOD_BOARD_HINTS.search(fn_low):
        return None
    if not own_asset(fn_low, slug_tokens):
        return None
    if "slab" in fn_low:
        return "slab"
    if TILE_HINTS.search(fn_low):
        return "closeup"
    m = SET_RE.search(fn_low)
    if m:
        return "room"
    m = GALLERY_RE.search(fn_low)
    if m:
        n = m.group(1)
        return "closeup" if n in ("", "1") else "room"
    return None


def harvest_one(url):
    slug, name = slug_and_name(url)
    cache_key = slug.replace("/", "_")
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key)
    except Exception as e:
        return {"url": url, "slug": slug, "error": str(e)}

    slug_tokens = set(re.sub(r'[^a-z ]', ' ', name.lower()).split())
    imgs = hl.extract_images(html_text, url)

    slab = closeups = rooms = None
    closeups, rooms = [], []
    for im in imgs:
        kind = classify(im["url"], slug_tokens)
        if kind == "slab" and slab is None:
            slab = im["url"]
        elif kind == "closeup":
            closeups.append(im["url"])
        elif kind == "room":
            rooms.append(im["url"])

    dims, thickness_note, finish, material = parse_info_block(html_text)
    description = parse_description(html_text)

    return {
        "url": url, "slug": slug, "name": name,
        "core": strip_finish(name),
        "dims": dims, "thickness_note": thickness_note, "finish": finish,
        "material": material, "description": description,
        "slab": slab, "closeups": closeups[:2], "rooms": rooms[:2],
    }


def main():
    urls = get_product_urls()
    print(len(urls), "quartz-worktops product pages", flush=True)
    manifest = []
    for i, url in enumerate(urls, 1):
        rec = harvest_one(url)
        manifest.append(rec)
        if rec.get("error"):
            print(f"[{i}/{len(urls)}] FETCH FAIL {url}: {rec['error']}", flush=True)
            continue
        print(f"[{i}/{len(urls)}] {rec['name']!r} (core={rec['core']!r}) | "
              f"slab={'Y' if rec['slab'] else 'N'} closeups={len(rec['closeups'])} "
              f"rooms={len(rec['rooms'])} finish={rec['finish']!r} dims={rec['dims']!r}",
              flush=True)

    out_path = os.path.join(SCRATCH, "fugen-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error"))
    withslab = sum(1 for m in manifest if m.get("slab"))
    print(f"WROTE {out_path}: {len(manifest)} pages, {ok} ok, {withslab} with a slab image")


if __name__ == "__main__":
    main()
