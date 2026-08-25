"""Quartzforms (quartzforms.com) GALLERIES harvest -- phase 2.

All 100 Quartzforms library entries already carry a working `productUrl`
(https://www.quartzforms.com/gb/surfaces/<slug>/) and 98/100 already have a
good slab main -- this pass is about closeup + room images (galleries),
plus slabSizes/details metadata. Mains are left alone except the 2 non-slab
entries (Planet Interstellar Gold 2050 = missing, QF Light Grey 125 =
representative/borrowed).

Every quartzforms.com product page (verified visually against Absolute White
and Planet Halley, 2026-08-25) uses ONE fixed 6-image template, always the
same suffixes on '.../storage/cache/<hash>.<W>x<H>.webp/<Colour>_<code>_<suffix>.webp':
  - _slab       (1950x850) -- clean full-slab render, no props        -> slab
  - _gallery01  (1950x850) -- real CGI kitchen scene, wide             -> room
  - _gallery02  (1950x850) -- second CGI kitchen scene                 -> room
  - _gallery03  (1150x650) -- styled countertop vignette (props, wide) -> closeup
  - _gallery04  (600x600)  -- styled flat-lay closeup (props, square)  -> closeup
  - _detail     (600x600)  -- pure texture crop, no props              -> closeup
This holds regardless of whether the OneDrive brands folder already has
files with these exact names cached from an earlier pass -- confirmed by
fetching the live pages directly, so this script fetches each colour's own
product page (cached under tools/_cache/quartzforms/) rather than trusting
old local files, which mix in non-supplier photos (own showroom shots,
AI mockups, etc.) that aren't reliable to auto-classify.

To keep the request count sane (100 colours x 1 page + up to 3 images each
still 2s-paced per HARVEST-SPEC), this pass takes ONE closeup (`_detail`,
the cleanest texture crop) and TWO rooms (`_gallery01` + `_gallery02`) per
colour -- `_gallery03`/`_gallery04` are skipped (redundant styled shots).

`details` is built from the page's Collection name + Finishes + the overview
paragraph. `slabSizes` comes from the price book (authority per spec), the
page's own Dimensions/Thickness table only as a fallback.

Writes tools/quartzforms-harvest.json. Re-run is cheap: pages/images are
cached under tools/_cache/quartzforms/; delete that dir to force a re-fetch.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "quartzforms"

IMG_RE = re.compile(
    r'storage/cache/[a-f0-9]{20,50}\.(\d+)x(\d+)\.webp/([A-Za-z0-9_]+?)\.webp')
SUFFIX_KIND = {
    "slab": "slab", "gallery01": "room", "gallery02": "room",
    "gallery03": "closeup", "gallery04": "closeup", "detail": "closeup",
}


def parse_images(html_text):
    """{'slab': url, 'gallery01': url, ...} -- first occurrence of each
    suffix wins (all appear at least once as an <img src>, some also as an
    <a href> lightbox link to the identical asset)."""
    out = {}
    for m in re.finditer(r'https://www\.quartzforms\.com/[^"\'<>]+\.webp', html_text):
        u = m.group(0)
        im = IMG_RE.search(u)
        if not im:
            continue
        w, h, fn = im.groups()
        suf = fn.rsplit("_", 1)[-1].lower()
        if suf not in SUFFIX_KIND:
            continue
        if suf not in out:
            out[suf] = u
    return out


def parse_meta(html_text):
    collection = ""
    m = re.search(r'class="col-12 parent">([^<]*)</div>', html_text)
    if m:
        collection = H.unescape(m.group(1)).replace("Collection", "").strip()

    finishes = ""
    m = re.search(
        r'<div class="info-name">Finishes</div>\s*<div class="info-value">([^<]*)</div>',
        html_text)
    if m:
        finishes = H.unescape(m.group(1)).strip()

    texture = ""
    m = re.search(
        r'<div class="info-name">Texture</div>\s*<div class="info-value">([^<]*)</div>',
        html_text)
    if m:
        texture = H.unescape(m.group(1)).strip()

    description = ""
    m = re.search(
        r'class="bg-color-white product overview section.*?<div class="col-md-6">\s*(.*?)\s*</div>',
        html_text, re.S)
    if m:
        description = H.unescape(re.sub(r'\s+', ' ', m.group(1))).strip()

    dims = ""
    m = re.search(
        r'<div class="info-name">Dimensions</div>\s*<div class="info-value">\s*([^<]*?)\s*</div>',
        html_text)
    if m:
        dims = H.unescape(re.sub(r'\s+', ' ', m.group(1))).strip()

    return {"collection": collection, "finishes": finishes, "texture": texture,
            "description": description, "dims": dims}


def harvest_one(entry):
    url = entry["productUrl"]
    cache_key = entry["id"]
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key)
    except Exception as e:
        return {"id": entry["id"], "colour": entry["colour"], "url": url, "error": str(e)}

    imgs = parse_images(html_text)
    meta = parse_meta(html_text)
    return {
        "id": entry["id"], "colour": entry["colour"], "url": url,
        "images": imgs, "meta": meta,
    }


def main():
    lib = hl.load_library()
    entries = [s for s in lib["slabs"] if s.get("supplier") == "Quartzforms" and s.get("productUrl")]
    print(f"{len(entries)} Quartzforms colours with product URLs", flush=True)
    manifest = []
    for i, e in enumerate(entries, 1):
        rec = harvest_one(e)
        manifest.append(rec)
        if rec.get("error"):
            print(f"[{i}/{len(entries)}] {e['colour']!r} FETCH FAIL: {rec['error']}", flush=True)
            continue
        found = sorted(rec["images"].keys())
        print(f"[{i}/{len(entries)}] {e['colour']!r} slots={found}", flush=True)

    out_path = os.path.join(SCRATCH, "quartzforms-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error"))
    with_room = sum(1 for m in manifest if not m.get("error") and
                     ("gallery01" in m["images"] or "gallery02" in m["images"]))
    with_closeup = sum(1 for m in manifest if not m.get("error") and
                        ("detail" in m["images"] or "gallery04" in m["images"] or "gallery03" in m["images"]))
    print(f"WROTE {out_path}: {len(manifest)} pages, {ok} ok, "
          f"{with_room} with a room slot, {with_closeup} with a closeup slot")


if __name__ == "__main__":
    main()
