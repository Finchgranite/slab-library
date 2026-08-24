"""Nile Stone harvest: two distinct lines under one supplier (HARVEST-SPEC Decisions).

Quartz (41, own-brand "Nile Quartz Surfaces"): nilestone.co.uk is an Angular SPA -- curl
gets an empty shell, but the whole catalogue (id/title/images[]) is a JS object literal
baked into the compiled client/main.*.js bundle. Regex-extracted here (CL array, the one
starting "CALACATTA" id:1). Image assets serve fine directly from
nilestone.co.uk/assets/quartz-surfaces/{filename} despite the JS-only HTML.

Porcelain (11, Marazzi "The Top" rebrand -- Nile Trading UK Ltd is Marazzi's sole UK
distributor): primary source is marazzitile.co.uk's own Grande collection pages (better
photography + genuine room/project shots); nilestone.co.uk's own /top-marazzi SPA catalogue
(DL array in the same main.js bundle) is the fallback for colours marazzitile.co.uk doesn't
carry (Capraia, Limestone Sand -- confirmed absent from the Grande pages by the discovery
pass). Hand-mapped below: only 11 colours, already fully resolved by
tools/_reports/nourl-discovery.json, so a generic HTML parser would be pure overhead for
this few items -- see harvest_lib pattern doc / HARVEST-SPEC Budget rule.

Pages/bundle were already fetched+cached by the discovery pass under
tools/_cache/nile-stone/ and tools/_cache/marazzitile/ -- this script reads those caches
(re-fetches only if a cache file is missing). Writes tools/nilestone-harvest.json.
"""
import json
import os
import re
import urllib.parse

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER_CACHE = "nile-stone"
MARAZZI_CACHE = "marazzitile"

NILESTONE_BASE = "https://www.nilestone.co.uk"
MARAZZI_BASE = "https://www.marazzitile.co.uk"

MAIN_JS_URL = NILESTONE_BASE + "/main.js"
QUARTZ_PAGE_URL = NILESTONE_BASE + "/quartz-surfaces"
TOP_MARAZZI_PAGE_URL = NILESTONE_BASE + "/top-marazzi"

MARAZZI_PAGES = {
    "grande-marble-look": MARAZZI_BASE + "/collections/grande-marble-look-collections/",
    "grande-solid-color": MARAZZI_BASE + "/collections/grande-solid-color-collections/",
    "grande-stone-look": MARAZZI_BASE + "/collections/grande-stone-look-collections/",
    "the-top": MARAZZI_BASE + "/the-top/",
}
MARAZZI_CACHE_KEYS = {
    "grande-marble-look": "grande-marble-look-collections",
    "grande-solid-color": "grande-solid-color-collections",
    "grande-stone-look": "grande-stone-look-collections",
    "the-top": "the-top",
}


def get_main_js():
    # main.js has a content hash in its real filename; the discovery pass cached it as
    # main.js directly (found via the index page's <script src>). Reuse that cache; if
    # absent for some reason, that's a hard failure worth surfacing, not re-discovering.
    path = os.path.join(hl.CACHE_ROOT, SUPPLIER_CACHE, "main.js")
    if os.path.exists(path):
        return open(path, encoding="utf-8", errors="replace").read()
    raise RuntimeError("tools/_cache/nile-stone/main.js missing -- re-run the discovery "
                        "pass's bundle fetch first (index page <script src> -> curl it).")


_OBJ_PAT = re.compile(
    r'\{id:(\d+),title:"([^"]*)",description:"[^"]*",images:(?:"([^"]*)"|\[([^\]]*)\])\}')


def _parse_array(block):
    items = []
    for m in _OBJ_PAT.finditer(block):
        id_, title, single, arr = m.groups()
        imgs = [single] if single is not None else re.findall(r'"([^"]*)"', arr)
        items.append({"id": int(id_), "title": title.strip(), "images": imgs})
    return items


def get_quartz_and_topmarazzi_arrays():
    js = get_main_js()
    # CL = quartz-surfaces catalogue (starts "CALACATTA" id:1); DL = top-marazzi catalogue
    # (starts "MARBLE LOOK - ALTISSIMO" id:1) -- both are `this.modalobject=[{id:1,...`
    # array literals inside their own Angular component class. Locate by anchor title.
    cl_start = js.index('this.modalobject=[{id:1,title:"CALACATTA"')
    dl_start = js.index('this.modalobject=[{id:1,title:"MARBLE LOOK - ALTISSIMO"')
    # each array ends where the next `let X=(()=>` component starts
    next_lets = [m.start() for m in re.finditer(r'let \w+=\(\(\)=>', js)]
    cl_end = min([n for n in next_lets if n > cl_start], default=len(js))
    dl_end = min([n for n in next_lets if n > dl_start], default=len(js))
    cl = _parse_array(js[cl_start:cl_end])
    dl = _parse_array(js[dl_start:dl_end])
    return cl, dl


def quartz_asset_url(fn):
    fn = fn.split("/")[-1]
    return f"{NILESTONE_BASE}/assets/quartz-surfaces/{urllib.parse.quote(fn)}"


def topmarazzi_asset_url(fn):
    fn = fn.split("/")[-1]
    return f"{NILESTONE_BASE}/assets/top-marazzi/{urllib.parse.quote(fn)}"


_ROOM_FN_HINT = re.compile(r'kitchen|render|room|install|lifestyle', re.I)


def classify_quartz_image(fn):
    """Filename-hint classification for Nile Quartz assets (no closeup-word filenames
    observed in the catalogue -- 'KITCHEN'/'RENDER' are the only signal words; everything
    else is judged by aspect ratio downstream in reconcile)."""
    if re.search(r'kitchen', fn, re.I):
        return "room"
    if re.search(r'render', fn, re.I):
        return None  # ambiguous -- let aspect ratio decide (often still a slab render)
    return None


def build_quartz_manifest(cl_items):
    out = []
    for it in cl_items:
        colour = it["title"].strip()
        if not colour:
            continue
        images = []
        for u in it["images"]:
            fn = u.split("/")[-1]
            images.append({"url": quartz_asset_url(fn), "filename": fn,
                            "hint": classify_quartz_image(fn)})
        out.append({
            "material": "Quartz",
            "site_colour": colour,
            "site_id": it["id"],
            "productUrl": QUARTZ_PAGE_URL,
            "images": images,
        })
    return out


# ---- Porcelain: hand-mapped from tools/_reports/nourl-discovery.json's Nile Stone
# section, cross-checked directly against the cached marazzitile.co.uk collection pages
# (11 colours only -- see module docstring for why this isn't generic-parsed). Each entry:
# marazzi_code = the Grande product-detail-block <p>Code:</p> value (see PORCELAIN_BLOCKS
# below, parsed straight off the cached pages) or None if only the nilestone.co.uk fallback
# is available. room_caption_kw = substring(s) to match in a the-top.html room-photo
# data-caption.
PORCELAIN_MAP = {
    "Black": {"marazzi_code": "MNH9", "marazzi_page": "the-top",
              "range_label": "Concrete Look", "fallback_id": 53, "room_kw": []},
    "Calacatta Extra": {"marazzi_code": "M0ZK", "marazzi_page": "grande-marble-look",
                         "range_label": "Marble Look", "fallback_id": 5,
                         "room_kw": ["Stone Look Calacatta Extra"]},
    "Calacatta Vena Vecchia": {"marazzi_code": "M7GF", "marazzi_page": "grande-marble-look",
                                "range_label": "Marble Look", "fallback_id": 6, "room_kw": []},
    "Capraia": {"marazzi_code": None, "marazzi_page": None,
                "range_label": "Marble Look", "fallback_id": 7,
                "room_kw": ["Marble Look Capraia", "Solid Color White"]},
    "Golden White": {"marazzi_code": "M8AD", "marazzi_page": "grande-marble-look",
                      "range_label": "Marble Look", "fallback_id": 14,
                      "room_kw": ["Marble Look Golden White"]},
    "Limestone Sand": {"marazzi_code": None, "marazzi_page": None,
                        "range_label": "Stone Look", "fallback_id": 40, "room_kw": []},
    "Saint Laurent": {"marazzi_code": "M0FS", "marazzi_page": "grande-marble-look",
                       "range_label": "Marble Look", "fallback_id": 25,
                       "room_kw": ["Marble Look Saint Laurent"]},
    "Silver Root Grey": {"marazzi_code": "MM19", "marazzi_page": "grande-stone-look",
                          "range_label": "Stone Look", "fallback_id": 58, "room_kw": []},
    "Silver Root White": {"marazzi_code": "MQ6N", "marazzi_page": "grande-stone-look",
                           "range_label": "Stone Look", "fallback_id": 58, "room_kw": []},
    "Travertino Classico": {"marazzi_code": "MJWU", "marazzi_page": "grande-stone-look",
                             "range_label": "Stone Look", "fallback_id": 45, "room_kw": []},
    "White": {"marazzi_code": "M11Z", "marazzi_page": "grande-solid-color",
              "range_label": "Solid Color", "fallback_id": 54,
              "room_kw": ["Solid Color White"]},
}

_DETAIL_PAT = re.compile(
    r'<img[^>]+src="(https://www\.marazzitile\.co\.uk/app/uploads/collezioni/[^"]+\.jpg)"'
    r'[^>]*class="attachment-full size-full"[^>]*>\s*</figure>\s*</div>\s*'
    r'<div class="col-8">\s*<p class="fs-sm text-uppercase mb-0">([^<]+)</p>'
    r'.*?Size:</p>\s*<p class="fs-sm mb-0">([^<]*)</p>'
    r'.*?Code:</p>\s*<p class="fs-sm mb-0">([^<]*)</p>'
    r'.*?Thickness:</p>\s*<p class="fs-sm mb-0">([^<]*)</p>',
    re.S)

_ROOM_PAT = re.compile(
    r'href="(https://www\.marazzitile\.co\.uk/app/uploads/[^"]+\.jpg)" data-fancybox="slider-[^"]*"'
    r'\s*data-caption="([^"]*)"', re.S)


def get_marazzi_page(key):
    path = os.path.join(hl.CACHE_ROOT, MARAZZI_CACHE, MARAZZI_CACHE_KEYS[key] + ".html")
    if os.path.exists(path):
        return open(path, encoding="utf-8", errors="replace").read()
    return hl.fetch_text(MARAZZI_PAGES[key], supplier=MARAZZI_CACHE, cache_key=MARAZZI_CACHE_KEYS[key])


def build_porcelain_manifest():
    cl, dl = get_quartz_and_topmarazzi_arrays()
    dl_by_id = {it["id"]: it for it in dl}

    # index every product-detail block (code -> (page_key, img_url, title, size, thickness))
    by_code = {}
    page_cache = {}
    for key in MARAZZI_PAGES:
        html_text = get_marazzi_page(key)
        page_cache[key] = html_text
        for img_url, title, size, code, thick in _DETAIL_PAT.findall(html_text):
            if code and code not in by_code:
                by_code[code] = {"page": key, "img_url": img_url, "title": title.strip(),
                                  "size": size.strip(), "thickness": thick.strip()}

    # room photos live on the-top.html
    room_photos = _ROOM_PAT.findall(page_cache["the-top"])

    out = []
    for colour, spec in PORCELAIN_MAP.items():
        images = []
        code = spec["marazzi_code"]
        block = by_code.get(code) if code else None
        source = "-"
        if block:
            images.append({"url": block["img_url"], "filename": block["img_url"].split("/")[-1],
                            "hint": "slab"})
            source = MARAZZI_PAGES[block["page"]]
        else:
            fb = dl_by_id.get(spec["fallback_id"])
            if fb:
                for u in fb["images"]:
                    fn = u.split("/")[-1]
                    images.append({"url": topmarazzi_asset_url(fn), "filename": fn, "hint": "slab"})
                source = TOP_MARAZZI_PAGE_URL
        # rooms: caption keyword match (case-sensitive substrings as they appear on-site)
        for u, caption in room_photos:
            if any(kw in caption for kw in spec["room_kw"]):
                images.append({"url": u, "filename": u.split("/")[-1], "hint": "room",
                               "caption": caption})
        out.append({
            "material": "Porcelain",
            "site_colour": colour,
            "range_label": spec["range_label"],
            "marazzi_code": code,
            "productUrl": source if source != "-" else TOP_MARAZZI_PAGE_URL,
            "size_text": block["size"] if block else "",
            "thickness_text": block["thickness"] if block else "",
            "images": images,
        })
    return out


def main():
    cl, dl = get_quartz_and_topmarazzi_arrays()
    print(f"quartz catalogue (CL): {len(cl)} items | top-marazzi catalogue (DL): {len(dl)} items")
    quartz_manifest = build_quartz_manifest(cl)
    porcelain_manifest = build_porcelain_manifest()
    manifest = quartz_manifest + porcelain_manifest
    out_path = os.path.join(SCRATCH, "nilestone-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n_img = sum(len(m["images"]) for m in manifest)
    print(f"WROTE {out_path}: {len(quartz_manifest)} quartz + {len(porcelain_manifest)} porcelain "
          f"site colours, {n_img} image candidates total")


if __name__ == "__main__":
    main()
