"""Caesarstone (www.caesarstone.co.uk, WordPress/WooCommerce) harvest.

Colour list comes from /catalog-sitemap.xml (74 catalogue pages -- the visible
/catalogue/ index only lists ~10 "new" tiles, the rest are JS-rendered).

Each colour page embeds a `const fullView = {"ratio":..,"src":"<full slab
image>","size":{"width":W,"height":H,"unit":"mm"|""}}` JS blob -- this IS the
true full-slab render (2:1-ish) and, when `size` is non-null, the real slab
dimensions in mm. Close-ups are filenames containing "_CU_" (portrait crops,
e.g. `<code>_<Colour>_CU_275X454_...`); room shots are "Kitchen_Render" /
"...-bathroom-vanity-render-..." / "...-kitchen-render-...". Every colour page
also embeds thumbnails for ~8 *other* related colours (a "you may also like"
carousel) -- these are filtered out by requiring the asset filename/URL to
contain the page's product code or normalised colour slug.

Writes tools/caesarstone-harvest.json. Run this once (results are cached under
tools/_cache/caesarstone/); reconcile_caesarstone.py consumes the manifest.
"""
import html as H
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "caesarstone"
BASE = "https://www.caesarstone.co.uk"
SITEMAP = BASE + "/catalog-sitemap.xml"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "CAESARSTONE- 26")

LIMIT = int(os.environ.get("CS_LIMIT", "0")) or None  # for quick testing only


def get_sitemap_urls():
    xml = hl.fetch_text(SITEMAP, supplier=SUPPLIER, cache_key="_catalog-sitemap")
    return sorted(set(re.findall(r'<loc>(https://www\.caesarstone\.co\.uk/catalogue/[^<]+)</loc>', xml)))


def product_code_and_slug(url):
    slug = url.rstrip("/").split("/")[-1]
    m = re.match(r'^(\d+)-(.+?)-(?:quartz|porcelain|fusion)-worktop$', slug)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r'^(\d+)-(.+)$', slug)
    return (m.group(1), m.group(2)) if m else ("", slug)


def page_title_colour(html_text, fallback):
    m = re.search(r'"name":"([^"]+?)\s*-\s*(?:Quartz|Porcelain|Fusion|ICON Fusion)\s*Worktop"', html_text)
    if m:
        return H.unescape(m.group(1)).strip()
    m = re.search(r'<title>(.*?)(?:\s*[–-]\s*Caesarstone)?</title>', html_text, re.S)
    if m:
        t = H.unescape(m.group(1)).strip()
        t = re.split(r'\s*[–-]\s*(?:Quartz|Porcelain|Fusion|ICON)', t)[0].strip()
        return t or fallback
    return fallback


def parse_full_view(html_text):
    m = re.search(r'const fullView\s*=\s*(\{.*?\});', html_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def parse_description(html_text):
    m = re.search(r'"@type":"Product".*?"description":"((?:[^"\\]|\\.)*)"', html_text)
    if not m:
        return ""
    return H.unescape(m.group(1).replace('\\/', '/').replace('\\"', '"')).strip()


def parse_finish(html_text):
    m = re.search(r'<span class="type">Finish</span>\s*<span class="value">\s*<span[^>]*>\s*(.*?)\s*</span>',
                   html_text, re.S)
    return H.unescape(m.group(1)).strip() if m else ""


def parse_thicknesses(html_text):
    return sorted(set(int(x) for x in re.findall(r'>\s*(\d{2})\s*mm\s*<', html_text)))


CODE_TOKEN_RE = None


def own_asset(url, code, slug_norm):
    """True if this image URL/filename plausibly belongs to THIS colour page
    (not one of the ~8 'related colours' carousel thumbnails also embedded in
    the HTML)."""
    fn = url.split("/")[-1].lower()
    if code and re.search(r'(?<![0-9])' + re.escape(code) + r'(?![0-9])', fn):
        return True
    fn_n = re.sub(r'[^a-z0-9]', '', fn)
    if slug_norm and slug_norm in fn_n:
        return True
    return False


def harvest_one(url):
    code, slug = product_code_and_slug(url)
    cache_key = f"{code or 'nc'}-{slug}"
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key)
    except Exception as e:
        return {"url": url, "error": str(e)}

    colour = page_title_colour(html_text, slug.replace("-", " ").title())
    fv = parse_full_view(html_text)
    finish = parse_finish(html_text)
    description = parse_description(html_text)
    thicknesses = parse_thicknesses(html_text)
    slug_norm = re.sub(r'[^a-z0-9]', '', slug)

    imgs = hl.extract_images(html_text, url)
    closeups, rooms, extra_slabs = [], [], []
    for im in imgs:
        if not own_asset(im["url"], code, slug_norm):
            continue
        kind = hl.classify_kind(im["url"], im["alt"], im["context"], im["width"], im["height"])
        fn_low = im["url"].lower()
        if re.search(r'_cu_|_cu\d|closeup|close-up', fn_low):
            kind = "closeup"
        elif re.search(r'kitchen[_-]?render|vanity[_-]?render|bathroom', fn_low):
            kind = "room"
        elif re.search(r'full[_-]?slab|_full_srgb|_full_\d{3,4}x\d{3,4}', fn_low):
            kind = "slab"
        if kind == "closeup":
            closeups.append(im["url"])
        elif kind == "room":
            rooms.append(im["url"])
        elif kind == "slab":
            extra_slabs.append(im["url"])

    def dedupe(seq):
        seen, out = set(), []
        for u in seq:
            base = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', u.split("/")[-1])
            if base in seen:
                continue
            seen.add(base)
            out.append(u)
        return out

    return {
        "url": url, "code": code, "slug": slug, "colour": colour,
        "finish": finish, "description": description, "thicknesses": thicknesses,
        "full": fv,  # {"ratio":.., "src":.., "size": {"width":.,"height":.,"unit":..} | None} | None
        "closeups": dedupe(closeups)[:4],
        "rooms": dedupe(rooms)[:4],
        "extra_slabs": dedupe(extra_slabs)[:2],
    }


def main():
    urls = get_sitemap_urls()
    if LIMIT:
        urls = urls[:LIMIT]
    print(len(urls), "catalogue pages", flush=True)
    manifest = []
    for i, url in enumerate(urls, 1):
        rec = harvest_one(url)
        manifest.append(rec)
        if rec.get("error"):
            print(f"[{i}/{len(urls)}] FETCH FAIL {url}: {rec['error']}", flush=True)
            continue
        print(f"[{i}/{len(urls)}] {rec['colour']} ({rec['code']}) | "
              f"full={'Y' if rec['full'] else 'N'} closeups={len(rec['closeups'])} "
              f"rooms={len(rec['rooms'])} finish={rec['finish']!r} thk={rec['thicknesses']}",
              flush=True)

    out_path = os.path.join(SCRATCH, "caesarstone-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error"))
    withfull = sum(1 for m in manifest if m.get("full"))
    print(f"WROTE {out_path}: {len(manifest)} pages, {ok} ok, {withfull} with a full-slab image")


if __name__ == "__main__":
    main()
