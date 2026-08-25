"""Picasso Surfaces harvest -- NEW site (picassosurfaces.co.uk, WordPress 7.1 +
WooCommerce 10.9.4, Elementor). Supersedes tools/harvest_picasso.py, which
harvested the OLD site (picassostones.com). Do not confuse the two -- caches,
outputs and reports live in a "picasso2"-suffixed namespace throughout.

Site structure (checked against annapurna/aqua-gold/arabescato-corchia/
arabescato-creme/cristallo/orella/jade-galcia before writing this):
  - Product sitemap: /wp-sitemap-posts-product-1.xml -- 40 <loc> entries,
    36 real colour pages + 4 "Symphony ... HD Print" pages (a new range not
    in the price book -- collected separately, reported, never added).
  - Every product page's <meta name="description" content="..."> holds BOTH
    the marketing blurb AND a fixed 3-line block, in order, separated by
    blank lines:
        <blurb text>

        Slab size available - LxWmm
        Slab thickness available - ...
        Slab finish(es) available - ...
    -- far cleaner than scraping visible text nodes. Used verbatim.
  - <title> is "<Name> - Picasso Surfaces" (&#8211; entity) -- the site's own
    spelling of the colour name (e.g. "Jade Galcia", "Himalayan Pink Onyx" --
    both differ from the price-book spelling; kept as aliases[] downstream).
  - Product images are NOT a standard WooCommerce gallery -- they're a single
    Elementor "gallery.default" widget (data-widget_type="gallery.default",
    exactly one per page in every page checked) whose items are
        <a class="e-gallery-item ... elementor-gallery-item ..."
           href="ORIGINAL_IMAGE_URL" ... data-width="W" data-height="H">
    2-5 images per product, filenames per-colour but NOT semantically named
    (anna1/anna2/anna3/anna4, jg1/jg2/jg3, cristall/cristall1/cristall2/
    cristall4 ...) and in RANDOM order on the page -- filename/order carries
    no kind signal, unlike Fugen/Compac. Every page also embeds a page-wide
    shared hero photo (PHOTO-2026-04-02-07-49-24*.jpg, identical URL on every
    product) and favicon variants (cropped-clean-*.png) -- both excluded here
    (not colour-specific).
  - Visual check (see tools/_cache/picasso2/preview_anna.png) of a 4-image
    product (Annapurna) showed: one real kitchen photo (room), one clean
    studio slab-on-plinth shot on black background (slab), one factory-floor
    full-slab-on-rack shot (also a real slab photo -- second slab candidate),
    one true edge-to-edge texture crop with no visible slab boundary
    (closeup). All images are ~1920x1200 (1.6:1) regardless of kind, so
    aspect ratio does NOT discriminate kind on this site (unlike the
    1.8-2.3:1 slab heuristic in harvest_lib.classify_kind) -- every image
    must be visually classified. Classification is done by hand from contact
    sheets (tools/_cache/picasso2/preview_*.png) and hardcoded into
    tools/reconcile_picasso2.py's KIND dict keyed by filename, NOT inferred
    here.

Writes tools/picasso2-harvest.json: [{url, slug, name, description,
slab_size, slab_thickness, slab_finish, images:[{url,w,h}]}, ...].
Re-run is cheap: pages cached under tools/_cache/picasso2/.
"""
import html as H
import json
import os
import re
import subprocess
import urllib.parse

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "picasso2"
BASE = "https://picassosurfaces.co.uk"
SITEMAP = BASE + "/wp-sitemap-posts-product-1.xml"

SHARED_HERO_HINT = "PHOTO-2026-04-02-07-49-24"
FAVICON_HINT = "cropped-clean"


def get_product_urls():
    # The sitemap XML is served with a WordPress "soft 404" status even though
    # the body is a real, valid sitemap (verified: HTTP/1.1 404 Not Found,
    # Content-Type application/xml, 4915-byte well-formed <urlset> body) --
    # hl.fetch()'s `curl --fail-with-body` treats any non-2xx as an error, so
    # fetch this one without -f and cache it by hand.
    cache_path = os.path.join(hl.CACHE_ROOT, SUPPLIER, "_sitemap.xml")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        xml = open(cache_path, encoding="utf-8").read()
    else:
        r = subprocess.run(["curl", "-sL", "-A", hl.UA, "--max-time", "90", SITEMAP],
                            capture_output=True)
        xml = r.stdout.decode("utf-8", "replace")
        if not xml.strip().startswith("<?xml"):
            raise RuntimeError(f"sitemap fetch looked wrong: {xml[:200]!r}")
        open(cache_path, "w", encoding="utf-8").write(xml)
    locs = sorted(set(re.findall(r'<loc>(https://picassosurfaces\.co\.uk/product/[^<]+)</loc>', xml)))
    symphony = [u for u in locs if "/symphony-" in u]
    colours = [u for u in locs if "/symphony-" not in u]
    return colours, symphony


def parse_name(html_text):
    m = re.search(r'<title>(.*?)</title>', html_text, re.S)
    if not m:
        return ""
    t = H.unescape(m.group(1)).strip()
    t = re.sub(r'\s*[–-]\s*Picasso Surfaces\s*$', '', t)
    return t.strip()


def parse_meta(html_text):
    m = re.search(r'<meta name="description" content="(.*?)">\s*<noscript', html_text, re.S)
    if not m:
        return "", "", "", ""
    content = H.unescape(m.group(1)).replace("&nbsp;", " ")
    lines = [l.strip() for l in content.split("\n")]
    lines = [l for l in lines if l]
    desc_lines, meta_lines = [], []
    for l in lines:
        if re.match(r'Slab (size|thickness|finish)', l, re.I):
            meta_lines.append(l)
        else:
            desc_lines.append(l)
    description = " ".join(desc_lines).strip()
    size = thickness = finish = ""
    for l in meta_lines:
        v = re.sub(r'^Slab \w+(?:es)? available\s*[-–:]\s*', '', l, flags=re.I).strip()
        if re.match(r'Slab size', l, re.I):
            size = v
        elif re.match(r'Slab thickness', l, re.I):
            thickness = v
        elif re.match(r'Slab finish', l, re.I):
            finish = v
    return description, size, thickness, finish


def parse_gallery(html_text, page_url):
    out = []
    seen = set()
    for m in re.finditer(
            r'<a class="e-gallery-item[^"]*"\s+href="([^"]+)"[^>]*>.*?data-width="(\d+)"\s+data-height="(\d+)"',
            html_text, re.S):
        href, w, h = m.group(1), int(m.group(2)), int(m.group(3))
        if SHARED_HERO_HINT in href or FAVICON_HINT in href:
            continue
        url = urllib.parse.urljoin(page_url, H.unescape(href))
        url = urllib.parse.quote(url, safe=':/?&=%')
        if url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "w": w, "h": h})
    return out


def harvest_one(url):
    slug = url.rstrip("/").split("/")[-1]
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=slug)
    except Exception as e:
        return {"url": url, "slug": slug, "error": str(e)}
    name = parse_name(html_text)
    description, size, thickness, finish = parse_meta(html_text)
    images = parse_gallery(html_text, url)
    return {
        "url": url, "slug": slug, "name": name,
        "description": description, "slab_size": size,
        "slab_thickness": thickness, "slab_finish": finish,
        "images": images,
    }


def main():
    colour_urls, symphony_urls = get_product_urls()
    print(f"{len(colour_urls)} colour pages, {len(symphony_urls)} Symphony pages", flush=True)
    manifest = []
    for i, url in enumerate(colour_urls, 1):
        rec = harvest_one(url)
        manifest.append(rec)
        if rec.get("error"):
            print(f"[{i}/{len(colour_urls)}] FETCH FAIL {url}: {rec['error']}", flush=True)
            continue
        print(f"[{i}/{len(colour_urls)}] {rec['name']!r} (slug={rec['slug']!r}) | "
              f"images={len(rec['images'])} size={rec['slab_size']!r}", flush=True)

    out_path = os.path.join(SCRATCH, "picasso2-harvest.json")
    json.dump({"colours": manifest, "symphony": symphony_urls}, open(out_path, "w", encoding="utf-8"),
               indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error"))
    total_imgs = sum(len(m.get("images", [])) for m in manifest)
    print(f"WROTE {out_path}: {len(manifest)} pages, {ok} ok, {total_imgs} gallery images total")


if __name__ == "__main__":
    main()
