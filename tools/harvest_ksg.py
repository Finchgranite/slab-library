"""KSG (ksguk.co.uk, old ASP-style CMS) NATUREQ quartz range harvest.

KSG(UK) LTD's quartz range is branded "NATUREQ" on-site (the price book's "KSG
Quartz" is Finch's internal label). URL pattern is
`ksguk.co.uk/NATUREQ/quartz-{slug}`, one quirk: Avalanche is
`/NATUREQ/QuartzAvalanche` (no hyphen, no "quartz-" prefix). Seville and
Santorini are shown on-site as "Calacatta Light (Seville)" / "Calacatta Nero
(Santorini)".

Each product page carries `Size: 3.20 x 1.60` and `Origin: KSG Factory India`
directly in the "Product Information" block, plus:
  - a visible gallery `<img>` (the hero slab photo) -- EXCEPT White Shimmer,
    whose gallery shows "Image Coming Soon" (no <img> at all);
  - a schema.org JSON-LD `Product.image` field, which is often a DIFFERENT,
    close-up-cropped photo (filename contains "close-up") from the gallery
    hero -- and for White Shimmer is the ONLY photo the page has. A harvest
    must read both, not just <img> tags.
No room/kitchen photos exist anywhere on the site (confirmed in
tools/_reports/nourl-DISCOVERY.md "## KSG").

Colour list/slugs come from the NATUREQ index page (fetched once, see
_index.html in the cache) cross-checked against the price book. Calacatta
Gold Shimmer has no page on the site (404) -- left as None below, reported.

Writes tools/ksg-harvest.json. Run once (cached under tools/_cache/ksg/);
reconcile_ksg.py consumes the manifest.
"""
import html as H
import json
import os
import re
import urllib.parse

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "ksg"
BASE = "https://ksguk.co.uk/NATUREQ"

# price-book colour -> site slug. None = confirmed no page on site (404).
TARGETS = {
    "White Mirror": "quartz-white-mirror",
    "Grey Mirror": "quartz-grey-mirror",
    "White Shimmer": "quartz-white-shimmer",
    "Grey Shimmer": "quartz-grey-shimmer",
    "Dove Grey": "quartz-dove-grey",
    "Arctic White": "quartz-arctic-white",
    "Siberian White": "quartz-siberian-white",
    "Carrara Classic": "quartz-carrara-classic",
    "Carrara Sicilia": "quartz-carrara-sicilia",
    "Carrara Gold": "quartz-carrara-gold",
    "Carrara Vena": "quartz-carrara-vena",
    "Carrara Classic - Leather": "quartz-carrara-classic-leather",
    "Avalanche": "QuartzAvalanche",
    "Calacatta Gold": "quartz-calacatta-gold",
    "Amazon": "quartz-amazon",
    "Andes": "quartz-andes",
    "Arabesque": "quartz-arabesque",
    "Black Mist": "quartz-black-mist",
    "Inca": "quartz-inca",
    "Irini": "quartz-irini",
    "Portofino": "quartz-portofino",
    "Sahara": "quartz-sahara",
    "Santorini": "quartz-calacatta-nero-santorini",
    "Calacatta Shimmer": "quartz-calacatta-shimmer",
    "Calacatta Gold Shimmer": None,
    "Calacatta Sahara": "quartz-calacatta-sahara",
    "Desert Silver": "quartz-desert-silver",
    "Nevada": "quartz-nevada",
    "Sorrento": "quartz-sorrento",
    "Seville": "quartz-calacatta-light-seville",
    "Himalaya": "quartz-himalaya",
}

# on-site colours seen on the NATUREQ index (tools/_cache/ksg/_index.html)
# that the price book does NOT list -- kept here for the report only, not
# harvested/created as library entries (per spec: report, don't invent).
SITE_EXTRAS_NOT_IN_PRICEBOOK = {
    "quartz-calacatta-frost": "Calacatta Frost",
    "quartz-dove-2652": "Dove (2652)",
    "quartz-pluto-2600": "Pluto (2600)",
}


def _abs(u, base_url):
    u = H.unescape(u.strip())
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return urllib.parse.urljoin(base_url, u)
    return u


def classify(url):
    fn = urllib.parse.unquote((url or "").split("/")[-1]).lower()
    if re.search(r'close[-_ ]?up|closeup', fn):
        return "closeup"
    return "slab"


def parse_page(html_text, url):
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.S)
    title = H.unescape(re.sub('<[^>]+>', '', h1.group(1))).strip() if h1 else ""

    size_m = re.search(r'Size:</span>\s*([\d.]+)\s*x\s*([\d.]+)', html_text)
    page_slab_size = None
    if size_m:
        L = round(float(size_m.group(1)) * 1000)
        W = round(float(size_m.group(2)) * 1000)
        page_slab_size = f"{L}x{W}"

    origin_m = re.search(r'Origin:</span>\s*([^<]+)', html_text)
    origin = H.unescape(origin_m.group(1)).strip() if origin_m else ""
    material_m = re.search(r'(?:Type|Material):</span>\s*([^<]+)', html_text)
    material = H.unescape(material_m.group(1)).strip() if material_m else ""

    gallery = []
    for m in re.finditer(r'<img\b([^>]*)>', html_text, re.I):
        attrs = m.group(1)
        src_m = re.search(r'\bsrc\s*=\s*"([^"]+)"', attrs)
        if not src_m:
            continue
        src = src_m.group(1)
        if 'logo' in src.lower():
            continue
        alt_m = re.search(r'\balt\s*=\s*"([^"]*)"', attrs)
        alt = H.unescape(alt_m.group(1)) if alt_m else ""
        gallery.append({"url": _abs(src, url), "alt": alt})

    ld_image = None
    ld_m = re.search(r'"@type":\s*"Product".*?"image":\s*"([^"]*)"', html_text, re.S)
    if ld_m and ld_m.group(1):
        ld_image = _abs(ld_m.group(1).replace('\\/', '/'), url)

    return {
        "title": title, "page_slab_size": page_slab_size,
        "origin": origin, "material": material,
        "gallery": gallery, "ld_image": ld_image,
    }


def _base(u):
    if not u:
        return None
    return re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', u.split("/")[-1].lower())


def harvest_one(colour, slug):
    url = f"{BASE}/{slug}"
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=slug)
    except Exception as e:
        return {"colour": colour, "slug": slug, "url": url, "error": str(e)}

    p = parse_page(html_text, url)
    hero = p["gallery"][0]["url"] if p["gallery"] else None
    ld = p["ld_image"]

    main_url, closeup_url = None, None
    if hero and classify(hero) != "closeup":
        main_url = hero
    elif hero:
        closeup_url = hero

    if ld and _base(ld) != _base(hero):
        if classify(ld) == "closeup":
            closeup_url = closeup_url or ld
        elif main_url is None:
            main_url = ld

    p.update({"colour": colour, "slug": slug, "url": url,
              "main_url": main_url, "closeup_url": closeup_url})
    return p


def main():
    manifest = []
    items = [(c, s) for c, s in TARGETS.items() if s]
    print(f"{len(items)} targets ({len(TARGETS) - len(items)} confirmed no-page)", flush=True)
    for i, (colour, slug) in enumerate(items, 1):
        rec = harvest_one(colour, slug)
        manifest.append(rec)
        if rec.get("error"):
            print(f"[{i}/{len(items)}] FETCH FAIL {colour} <- {slug}: {rec['error']}", flush=True)
            continue
        print(f"[{i}/{len(items)}] {colour!r:26s} <- {slug:34s} "
              f"main={'Y' if rec['main_url'] else 'N'} closeup={'Y' if rec['closeup_url'] else 'N'} "
              f"size={rec['page_slab_size']} origin={rec['origin']!r}", flush=True)
    for colour, slug in TARGETS.items():
        if slug is None:
            manifest.append({"colour": colour, "slug": None, "url": None, "no_page": True})

    out_path = os.path.join(SCRATCH, "ksg-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error") and not m.get("no_page"))
    withmain = sum(1 for m in manifest if m.get("main_url"))
    withcu = sum(1 for m in manifest if m.get("closeup_url"))
    print(f"WROTE {out_path}: {len(manifest)} colours, {ok} fetched ok, "
          f"{withmain} with a main slab image, {withcu} with a closeup")


if __name__ == "__main__":
    main()
