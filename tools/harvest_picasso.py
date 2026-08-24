"""Picasso Surfaces (www.picassostones.com, WordPress/Elementor) harvest.

The site has NO per-colour product pages and NO products/portfolio sitemap --
colours live only as images inside five "series" gallery pages
(marble-series, designer-series, mirror-series, plain-series,
stellar-seriessmall-sparkles), an aggregate "our-products" grid, and a
"gallery" page of room/kitchen photos. Per HARVEST-SPEC lesson (b), the WP
REST API (`/wp-json/wp/v2/media`) is open and gives the full 390-item media
library as clean JSON (title, alt_text, source_url, true width/height, and
each image's own auto-generated permalink `link` e.g. .../aspen) -- richer
and far cheaper than scraping <img> tags across 7 HTML pages, so it is the
source of truth for image dimensions/originals. The HTML pages are still
scraped once each (cheap, cached) to know WHICH colour a given filename
prefix means (captions) and which series/room each belongs to, since the
REST API alone doesn't say "this is the Marble Series photo of Calacatta
Gold" or "this is a kitchen room shot of Arctic Storm".

Colour name resolution ("Golden Thunder" vs price-book's "Golden Thunder
(aka Thunder Gold)", "Carrara Ice" vs "Carrara Ice (Shimmer)") is handled by
stripping a trailing " (...)" parenthetical off both price-book and library
colour strings before token-matching (hl.match_colour ignores parenthetical
survivors otherwise since it demands a two-way token-subset match).

Writes tools/picasso-harvest.json. Run once (HTML + REST pages cached under
tools/_cache/picasso/); reconcile_picasso.py consumes the manifest.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "picasso"
BASE = "https://www.picassostones.com"

SERIES_PAGES = {
    "marble-series": "Marble Series",
    "designer-series": "Designer Series",
    "mirror-series": "Mirror Series",
    "plain-series": "Plain Series",
    "stellar-seriessmall-sparkles": "Stellar Series",
}
OTHER_PAGES = ["our-products", "gallery"]

_ROOM_SUFFIX = re.compile(
    r'\s*[-_]?\s*(Kitchen|Island|Worktop|Table[- ]?top|Table|Countertop|Dinning|Dining|'
    r'Showroom|Backlit|Application|Vanity)\b.*$', re.I)


def fetch_page(slug):
    return hl.fetch_text(f"{BASE}/{slug}", supplier=SUPPLIER, cache_key=f"page-{slug}")


def get_media_library():
    """Full WP media library via REST API (390 items, 5 pages of 100)."""
    items = []
    for p in range(1, 6):
        url = (f"{BASE}/wp-json/wp/v2/media?per_page=100&page={p}"
               f"&_fields=id,title,alt_text,slug,mime_type,source_url,link,media_details")
        js = hl.fetch_text(url, supplier=SUPPLIER, cache_key=f"media-p{p}")
        try:
            items.extend(json.loads(js))
        except Exception:
            pass
    return [i for i in items if i.get("mime_type", "").startswith("image")]


def parse_our_products(html_text):
    """our-products grid: <h3><a href=IMG>Name</a></h3><strong>Series</strong>."""
    out = []
    blocks = re.split(r'(?=<div class="col-xl-4)', html_text)
    for b in blocks:
        m_href = re.search(r'port_popup img-fluid" href="([^"]+)"', b)
        m_name = re.search(r'<h3>\s*<a[^>]*>\s*([\s\S]*?)</a></h3>', b)
        m_series = re.search(r'<strong>([^<]*)</strong>', b)
        if m_href and m_name:
            name = H.unescape(re.sub(r'<[^>]+>', '', m_name.group(1))).strip()
            name = re.sub(r'^\*New\*\s*', '', name).strip()
            out.append({"name": name, "url": m_href.group(1),
                        "series": m_series.group(1).strip() if m_series else ""})
    return out


def parse_fastgallery(html_text, series_label):
    """<div data-src='URL' class='fg-gallery-item'>...alt="Name"...caption</div>."""
    out = []
    blocks = re.split(r"(?=<div data-src=)", html_text)
    for b in blocks:
        m_datasrc = re.match(r"<div data-src='([^']+)'", b)
        if not m_datasrc:
            continue
        m_alt = re.search(r'alt="([^"]*)"', b)
        m_cap = re.search(r"fg-wp-caption-text[^>]*>\s*<div class='caption-container'>\s*([\s\S]*?)\s*</div>", b)
        name = (m_cap.group(1).strip() if m_cap else "") or (m_alt.group(1) if m_alt else "")
        name = H.unescape(re.sub(r'^\*New\*\s*', '', name).strip())
        if name:
            out.append({"name": name, "url": m_datasrc.group(1), "series": series_label})
    return out


def parse_gallery_rooms(html_text):
    """gallery page: room/kitchen photo filenames like Arctic-storm-Kitchen.jpg.
    Returns [{"name_guess": <colour prefix>, "url": <img url>}]."""
    out = []
    for u in set(re.findall(r'https://www\.picassostones\.com/wp-content/uploads/[^"\'\s)]+\.(?:jpg|jpeg|png|webp)', html_text, re.I)):
        fn = u.split("/")[-1]
        base = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', fn)
        stem = re.sub(r'\.[a-zA-Z0-9]+$', '', base)
        if not _ROOM_SUFFIX.search(stem):
            continue
        name_guess = _ROOM_SUFFIX.sub('', stem).replace('-', ' ').replace('_', ' ').strip()
        name_guess = re.sub(r'\s+\d+$', '', name_guess).strip()  # trailing "...-5714"
        if len(name_guess) < 3:
            continue
        out.append({"name_guess": name_guess, "url": u})
    return out


def main():
    print("fetching series/product/gallery pages...", flush=True)
    site_slabs = []
    site_slabs += parse_our_products(fetch_page("our-products"))
    for slug, label in SERIES_PAGES.items():
        site_slabs += parse_fastgallery(fetch_page(slug), label)
    gallery_html = fetch_page("gallery")
    room_shots = parse_gallery_rooms(gallery_html)

    print(f"  our-products + series pages: {len(site_slabs)} name/image pairs "
          f"({len(set(s['name'].lower() for s in site_slabs))} distinct names)")
    print(f"  gallery room shots: {len(room_shots)}")

    print("fetching WP media library (REST API, 5 pages)...", flush=True)
    media = get_media_library()
    print(f"  {len(media)} image media items")

    def _norm_stem(url_or_fn):
        fn = url_or_fn.split("/")[-1]
        stem = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', fn)
        stem = re.sub(r'\.[a-zA-Z0-9]+$', '', stem)
        stem = re.sub(r'-scaled$', '', stem, flags=re.I)
        return stem.lower()

    # index by filename (no size suffix, no "-scaled", no extension) -> best media record
    media_by_stem = {}
    for m in media:
        stem = _norm_stem(m["source_url"])
        w = (m.get("media_details") or {}).get("width") or 0
        prev = media_by_stem.get(stem)
        if prev is None or w > prev[1]:
            media_by_stem[stem] = (m, w)
    media_by_stem = {k: v[0] for k, v in media_by_stem.items()}

    def best_original(url):
        """Resolve a page-referenced image URL to its best-known media record
        (true width/height, canonical link) via the REST media index; falls
        back to the URL itself with no metadata."""
        return media_by_stem.get(_norm_stem(url))

    # ---- group site_slabs by colour name -> best slab image + series/link
    by_name = {}
    for s in site_slabs:
        key = s["name"].strip().lower()
        rec = best_original(s["url"])
        w = (rec.get("media_details") or {}).get("width", 0) if rec else 0
        best_url = rec["source_url"] if rec else s["url"]
        entry = by_name.setdefault(key, {"name": s["name"], "series": s["series"],
                                          "url": best_url, "link": rec.get("link") if rec else "",
                                          "w": w})
        if w > entry["w"]:
            entry.update({"url": best_url, "link": rec.get("link") if rec else "", "w": w})
        if not entry.get("series"):
            entry["series"] = s["series"]

    # ---- group room shots by guessed colour name
    rooms_by_guess = {}
    for r in room_shots:
        rooms_by_guess.setdefault(r["name_guess"].strip().lower(), []).append(r["url"])

    manifest = {
        "slabs": list(by_name.values()),
        "rooms_by_guess": {k: sorted(set(v)) for k, v in rooms_by_guess.items()},
    }
    out_path = os.path.join(SCRATCH, "picasso-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"WROTE {out_path}: {len(manifest['slabs'])} distinct site colours, "
          f"{len(manifest['rooms_by_guess'])} room-shot name groups")


if __name__ == "__main__":
    main()
