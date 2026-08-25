"""World Wide Stones (worldwidestones.co.uk, WordPress/Elementor) harvest -- phase 2.

Site layout: no product-sitemap; wp-sitemap-posts-page-1.xml lists every page,
filtered to /quartz-slabs/<slug>/ and /porcelain-slabs/<slug>/ (granite-slabs/
excluded -- out of scope, natural stone). Each colour page is a simple
Elementor page: H1 = colour name, 1-2 `text-editor` paragraphs
"Slab size: 3200x1600x30mm - In stock", and 1-4 `elementor-widget-image`
photos (no consistent slab/closeup/room filename convention -- classify by
filename hint first, then real downloaded-pixel aspect ratio; WWS "slab"
photos run 1.3-2.8:1 landscape OR ~0.6-0.85:1 portrait "whole slab stood up in
the yard" shots, not the tidy 2:1 this site's own filenames sometimes claim).

The /quartz-slabs/ and /porcelain-slabs/ INDEX pages are the authority for
site DISPLAY NAME + canonical URL per colour (each is an `image-box` widget:
thumbnail marked "*close*"/"*Close*" = guaranteed closeup + <h3><a> = name +
href = canonical product URL) -- several URL slugs are stale/misleading
(e.g. /quartz-slabs/irini-classic/ displays "Sahara Waves"; the index H3 text
is trusted over the slug). Several sitemap pages are NOT linked from the
index (orphaned -- old/discontinued SKUs); these are still fetched (cheap)
but only used if MANUAL_MAP claims them.

MANUAL_MAP (site slug -> price-book Colour) was built by fetching every
candidate page and comparing its H1/index-title against the 54-colour price
book -- see tools/_reports/wws-REPORT.md "Assumptions" for the handful of
non-obvious ones (Calacatta Oro Claro -> Calacatta Oro Frost, Techlam Noir ->
Noir St Laurent, Carrara Frost (Shimmer) -> New Carrara Frost, etc.) flagged
there for the supplier to confirm.

Writes tools/wws-harvest.json (keyed by price-book Colour). Re-run is cheap:
pages/images cached under tools/_cache/wws/; delete that dir to force re-fetch.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "wws"
BASE = "https://www.worldwidestones.co.uk"
SITEMAP = BASE + "/wp-sitemap-posts-page-1.xml"

# site slug -> price-book Colour (material implied by /quartz-slabs//porcelain-slabs/ prefix)
MANUAL_MAP = {
    "quartz-slabs/ambient-cemento-polished": "Ambient Cemento",
    "quartz-slabs/arabescato-bianco-2": "Arabescato Bianco",
    "quartz-slabs/arabescato-corchia-3": "Arabescato Corchia",
    "quartz-slabs/avalanche": "Avalanche",
    "quartz-slabs/borini": "Borini",
    "quartz-slabs/brooklyn-25": 'Brooklyn "25"',
    "quartz-slabs/calacatta-borghini-3d": "Calacatta Borghini",
    "quartz-slabs/calacatta-emerald": "Calacatta Emerald",
    "quartz-slabs/calacatta-gold": "Calacatta Gold",
    "quartz-slabs/calacatta-light": "Calacatta Light",
    "quartz-slabs/calacatta-oro": "Calacatta Oro",
    "quartz-slabs/calacatta-oro-duplicate-941": "Calacatta Oro Frost",       # ASSUMPTION (see report)
    "quartz-slabs/new-carrara": "New Carrara",
    "quartz-slabs/carrara-extra": "Carrara",                                # ASSUMPTION: pb "Carrara" is 3500x2000
                                                                              # (jumbo) vs "New Carrara" 3200x1600 --
                                                                              # site's "Carrara New (Super Jumbo)" fits.
    "quartz-slabs/carrara-flowery": "Carrara Flowery",
    "quartz-slabs/carrara-flowery-extra": "Carrara Flowery Extra",
    "quartz-slabs/carrara-frost": "New Carrara Frost",                      # ASSUMPTION (see report)
    "quartz-slabs/carrara-onyx": "Carrara Onyx",
    "quartz-slabs/colorado": "Colorado",
    "quartz-slabs/cosmic-gold-polished": "Cosmic Gold",
    "quartz-slabs/carrara-frost-duplicate-12515": "Crimson Frost",          # confirmed via index H3 text
    "quartz-slabs/cristallino-supreme": "Cristallino Supreme",
    "quartz-slabs/desert-silver": "Desert Silver",
    "quartz-slabs/embers": "Embers",
    "quartz-slabs/grey-coconut-reflex": "Grey Coconut Sparkle",
    "quartz-slabs/irini": "Irini",
    "quartz-slabs/levante-grey": "Levante Grey",
    "quartz-slabs/levante-gold": "Levante Gold",
    "quartz-slabs/calacatta-gold-duplicate-973": "New Calacatta Gold",      # confirmed via index H3 text
    "quartz-slabs/pacific-white": "Pacific White",
    "quartz-slabs/patagonia-oro-2": "Patagonia Oro",
    "quartz-slabs/perla-venato": "Perla Venato",
    "quartz-slabs/raw-concrete-textured": "Raw Concrete",
    "quartz-slabs/rosa-bulgari": "Rosa Bulgari",
    "quartz-slabs/irini-classic": "Sahara Waves",                          # confirmed via index H3 text
    "quartz-slabs/super-white": "Super White",
    "quartz-slabs/taj-mahal": "Taj Mahal",
    "quartz-slabs/taj-mahal-extra-3d": "Taj Mahal Extra",
    "quartz-slabs/tuscan-gold": "Tuscan Gold",
    "quartz-slabs/white-frost": "White Frost",
    "quartz-slabs/white-sparkle": "White Sparkle",
    "porcelain-slabs/arabescato": "Arabescato",
    "porcelain-slabs/breccia-brown-2": "Breccia Brown",
    "porcelain-slabs/calacatta-antique": "Calacatta Antique",
    "porcelain-slabs/calacatta-classic": "Calacatta Classic",
    "porcelain-slabs/calacatta-grey": "Calacatta Grey",
    "porcelain-slabs/statuary-venato": "Calacatta Viola",                  # confirmed via index H3 text
    "porcelain-slabs/essential-gold-2": "Essential Gold",
    "porcelain-slabs/fior-di-bosco": "Fior Di Bosco",
    "porcelain-slabs/marvellous-gold": "Marvel Gold",
    "porcelain-slabs/mont-blanc-2": "Mont Blanc",
    "porcelain-slabs/noir": "Noir St Laurent",                             # ASSUMPTION (see report)
    "porcelain-slabs/noir-st-laurent": "St Laurent",                       # confirmed via page H1 (slug is stale)
    "porcelain-slabs/patagonia": "Patagonia",
}
# not price-book colours -- extra site ranges we don't currently stock (report only)
KNOWN_UNMATCHED_HINT = {
    "quartz-slabs/amazon-green": "Amazon Green -- not in price book",
    "quartz-slabs/ambient-cemento-leathered": "Leathered finish variant -- pb only has Polished",
    "quartz-slabs/avalanche-extra": "orphaned page, no H1/content",
    "quartz-slabs/calacatta-oro-nuevo": "Calacatta Oro Nuevo -- orphaned, distinct from Oro Claro",
    "quartz-slabs/carrara-extra": "Carrara New (Super Jumbo) -- size variant of New Carrara",
    "quartz-slabs/carrara-y2": "Carrara Y2 -- not in price book",
    "quartz-slabs/cosmic-gold-leather": "Leathered finish variant -- pb only has Polished",
    "quartz-slabs/golden-flowery": "Golden Flowery -- not in price book",
    "quartz-slabs/patagonia-gris-2": "Patagonia Gris -- not in price book (site says discontinuing 2026)",
    "quartz-slabs/statuary-1st": "Statuary 1st (Super Jumbo) -- not in price book",
    "quartz-slabs/brooklyn": 'Brooklyn "24" -- not in price book (only "25" is)',
    "porcelain-slabs/bronze-matte": "Bronze -- not in price book",
    "porcelain-slabs/techlam-bellagio": "Techlam Alhambra -- not in price book",
    "porcelain-slabs/reggio-2": "Techlam Bellagio -- not in price book",
    "porcelain-slabs/taj-mahal": "Taj Mahal (Porcelain) -- price book HAS a Porcelain Taj Mahal row but "
                                  "the library has no porcelain entry (only the Quartz one) -- reported, not created",
}

_SKIP_FILE_HINTS = re.compile(r'warranty|logo|favicon|banner|surface.?care', re.I)
_ROOM_HINTS = re.compile(r'kitchen|bathroom|\broom\b|install|ambient|inspiration|project|vanity|interior|lifestyle', re.I)
_CLOSEUP_HINTS = re.compile(r'close[-_]?up|closeup|\bclose\b|detail|texture|zoom|swatch', re.I)
_SLAB_HINTS = re.compile(r'\bslab\b', re.I)


def get_sitemap_urls():
    # The live wp-sitemap endpoint started 404-ing (WAF) during discovery; a full
    # sitemap snapshot was already captured to _all_urls.txt beforehand -- reuse
    # it rather than re-hit a flagged endpoint (site structure is stable).
    seed = os.path.join(hl.CACHE_ROOT, SUPPLIER, "_all_urls.txt")
    if os.path.exists(seed):
        locs = sorted(set(l.strip() for l in open(seed, encoding="utf-8") if l.strip()))
    else:
        xml = hl.fetch_text(SITEMAP, supplier=SUPPLIER, cache_key="_sitemap-page-1")
        locs = sorted(set(re.findall(r'<loc>(https://www\.worldwidestones\.co\.uk/[^<]+)</loc>', xml)))
    out = []
    for u in locs:
        for pfx in ("quartz-slabs", "porcelain-slabs"):
            m = re.match(rf'{re.escape(BASE)}/{pfx}/([^/]+)/$', u)
            if m:
                out.append((f"{pfx}/{m.group(1)}", u))
    return out


def get_index_names():
    """{slug_path: (display_name, close_thumb_url)} from the two index pages."""
    out = {}
    pat = re.compile(
        r'<a href="(https://www\.worldwidestones\.co\.uk/(?:quartz|porcelain)-slabs/[^"]+)"[^>]*>'
        r'<img[^>]*src="([^"]+)"[^>]*/></a></figure><div class="elementor-image-box-content">'
        r'<h3[^>]*><a href="[^"]*">([^<]*(?:<br\s*/?>[^<]*)?)</a></h3>', re.S)
    for pfx in ("quartz-slabs", "porcelain-slabs"):
        html_text = hl.fetch_text(f"{BASE}/{pfx}/", supplier=SUPPLIER, cache_key=f"_index-{pfx}")
        for url, img, name in pat.findall(html_text):
            m = re.match(rf'{re.escape(BASE)}/{pfx}/([^/]+)/$', url)
            if not m:
                continue
            slug = f"{pfx}/{m.group(1)}"
            clean = H.unescape(re.sub(r'<br\s*/?>', ' ', name)).strip()
            out[slug] = (clean, hl._absolutize(img, url))
    return out


def real_dims(url, colour, cache_tag):
    try:
        data, used = hl.fetch_best(url, supplier=SUPPLIER, cache_key=f"dim-{colour}-{cache_tag}"[:150])
    except Exception:
        return None, None, None
    try:
        from io import BytesIO
        from PIL import Image
        im = Image.open(BytesIO(data))
        return im.width, im.height, used
    except Exception:
        return None, None, used


def classify(url, is_first, w, h):
    fn = url.split("/")[-1].lower()
    if _SKIP_FILE_HINTS.search(fn):
        return None
    if _ROOM_HINTS.search(fn):
        return "room"
    if _CLOSEUP_HINTS.search(fn):
        return "closeup"
    if _SLAB_HINTS.search(fn):
        return "slab"
    if not w or not h:
        return None
    if min(w, h) < 300:          # too small to be a usable main/gallery photo (icon/tiny thumb)
        return None
    ar = w / h
    ar_n = max(ar, 1 / ar)
    if 1.3 <= ar_n <= 2.8 and ar >= 1:
        return "slab"
    if 0.8 <= ar_n <= 1.25:
        return "closeup"
    if 0.5 <= ar <= 0.85:
        return "slab" if is_first else "closeup"
    return None


def parse_slab_sizes(html_text):
    """[(dims 'LxW', thickness_mm, stock_status), ...] from 'Slab size: 3200x1600x30mm - In stock'."""
    out = []
    for m in re.finditer(r'Slab size:\s*(\d+)\s*x\s*(\d+)\s*x\s*(\d+)\s*mm\s*[–-]\s*([A-Za-z ]+)', html_text):
        out.append((f"{m.group(1)}x{m.group(2)}", int(m.group(3)), m.group(4).strip()))
    return out


def harvest_page(slug, url, colour, index_name, index_close):
    cache_key = slug.replace("/", "_")
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key)
    except Exception as e:
        return {"slug": slug, "url": url, "colour": colour, "error": str(e)}

    h1m = re.search(r'<h1[^>]*>([^<]*)</h1>', html_text)
    h1 = H.unescape(h1m.group(1)).strip() if h1m else ""

    # restrict to entry-content region so header/footer logo+social icons are excluded
    body_m = re.search(r'<div class="entry-content clear".*?</article>', html_text, re.S)
    body = body_m.group(0) if body_m else html_text

    seen, order = set(), []
    for m in re.finditer(r'<img\b([^>]*)>', body, re.I):
        attrs = m.group(1)
        src = hl._attr(attrs, "src")
        if not src or "wp-content/uploads" not in src:
            continue
        src = hl._absolutize(src, url)
        fn_key = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', src.split("/")[-1])
        if fn_key in seen:
            continue
        seen.add(fn_key)
        order.append(src)

    if colour != "Borini":
        # site bug, verified: /quartz-slabs/irini/ literally embeds Borini's own
        # photos (Borini.jpg/-1/-2) -- drop any Borini-named asset on any other page.
        order = [u for u in order if not u.split("/")[-1].lower().startswith("borini")]

    slab = None
    closeups, rooms = [], []
    candidates = []
    for i, src in enumerate(order):
        w, h, used = real_dims(src, colour, f"p{i}")
        if used is None:
            continue
        kind = classify(used, i == 0, w, h)
        candidates.append({"url": used, "kind": kind, "w": w, "h": h, "tag": f"p{i}"})
        if kind == "slab" and slab is None:
            slab = used
        elif kind == "closeup":
            closeups.append(used)
        elif kind == "room":
            rooms.append(used)

    if index_close:
        w, h, used = real_dims(index_close, colour, "idxclose")
        if used:
            candidates.append({"url": used, "kind": "closeup(index)", "w": w, "h": h, "tag": "idxclose"})
            if used not in closeups:
                closeups.insert(0, used)

    sizes = parse_slab_sizes(html_text)

    return {
        "slug": slug, "url": url, "colour": colour, "h1": h1, "index_name": index_name,
        "sizes": sizes, "slab": slab, "closeups": closeups[:2], "rooms": rooms[:2],
        "candidates": candidates,
    }


def main():
    sitemap_pairs = get_sitemap_urls()
    sitemap_by_slug = dict(sitemap_pairs)
    index_names = get_index_names()
    print(f"{len(sitemap_pairs)} sitemap product pages, {len(index_names)} index-listed", flush=True)

    manifest = {}
    for i, (slug, colour) in enumerate(MANUAL_MAP.items(), 1):
        url = sitemap_by_slug.get(slug) or f"{BASE}/{slug}/"
        idx_name, idx_close = index_names.get(slug, (None, None))
        rec = harvest_page(slug, url, colour, idx_name, idx_close)
        manifest[colour] = rec
        if rec.get("error"):
            print(f"[{i}/{len(MANUAL_MAP)}] FAIL {colour!r} <- {slug}: {rec['error']}", flush=True)
        else:
            print(f"[{i}/{len(MANUAL_MAP)}] {colour!r} <- {slug} | h1={rec['h1']!r} "
                  f"slab={'Y' if rec['slab'] else 'N'} cu={len(rec['closeups'])} rm={len(rec['rooms'])} "
                  f"sizes={rec['sizes']}", flush=True)

    unmatched_site = [(slug, url) for slug, url in sitemap_pairs if slug not in MANUAL_MAP]

    out = {
        "manifest": manifest,
        "unmatched_site": [{"slug": s, "url": u, "note": KNOWN_UNMATCHED_HINT.get(s, "")} for s, u in unmatched_site],
    }
    out_path = os.path.join(SCRATCH, "wws-harvest.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    ok = sum(1 for r in manifest.values() if not r.get("error"))
    withslab = sum(1 for r in manifest.values() if r.get("slab"))
    print(f"WROTE {out_path}: {len(manifest)} mapped colours, {ok} ok, {withslab} with a slab image, "
          f"{len(unmatched_site)} unmatched site pages")


if __name__ == "__main__":
    main()
