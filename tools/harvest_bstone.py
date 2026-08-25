"""B-Stone (bstoneuk.co.uk) harvest -- phase 2.

Site structure is NOT per-colour product pages (no WooCommerce/WP shop here):
every BQuartz colour lives as one lightbox tile on a single listing page
https://bstoneuk.co.uk/material/bquartz/ , every Techlam (sintered) colour on
https://bstoneuk.co.uk/material/techlam/ . Each tile is:
    <div class="grid-item" data-element="1">
        <a data-gallery="designs" href="<full-res jpg>" data-toggle="lightbox"
           data-caption="<strong>Name [| 20mm only] [- NEW ...]</strong>Description text">
Verified the `href` full-res jpg IS the true slab photo (~2:1 aspect, e.g.
2560x1280) for every sampled colour -- not a swatch/thumbnail. There are no
separate texture/closeup crops anywhere on the site (checked both pages).
productUrl for every engineered colour = the shared material listing page
(there is nothing more specific to link to).

Room/kitchen photos come from a SEPARATE post type: /inspiration-sitemap.xml
lists individual project posts, many slugged "bquartz-<colour>[-N]" (no
techlam/sintered inspiration posts exist -- checked). Each inspiration page
has real installation photos under class="inspiration-image" (phone-camera
kitchen shots, portrait/landscape, not the studio slab photo). Matched to a
library colour via harvest_lib.match_colour on the slug-derived name; up to 2
posts per colour are fetched (sorted so the bare slug, e.g. "bquartz-veridian"
before "-2","-3"...), and 1 photo taken from each.

Writes tools/bstone-harvest.json. Re-run is cheap: pages cached under
tools/_cache/bstone/; delete that dir to force a re-fetch.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "bstone"
BASE = "https://bstoneuk.co.uk"
BQUARTZ_URL = BASE + "/material/bquartz/"
TECHLAM_URL = BASE + "/material/techlam/"
INSPIRATION_SITEMAP = BASE + "/inspiration-sitemap.xml"

GRID_ITEM_RE = re.compile(
    r'<div class="grid-item"[^>]*>\s*<a data-gallery="([^"]*)"\s*href="([^"]+)"\s*'
    r'data-toggle="lightbox"\s*data-caption="([^"]*)">', re.S)

INSPIRATION_IMG_RE = re.compile(
    r'<a class="inspiration-image" href="([^"]+)"', re.I)


def parse_grid_items(html_text, page_url, material_label):
    out = []
    for gal, href, cap in GRID_ITEM_RE.findall(html_text):
        cap = H.unescape(cap)
        m = re.match(r'<strong>(.*?)</strong>\s*(.*)', cap, re.S)
        title = (m.group(1).strip() if m else cap).strip()
        desc = (m.group(2).strip() if m else "")
        out.append({
            "raw_title": title, "description": desc,
            "slab_url": hl._absolutize(href, page_url),
            "page_url": page_url, "material": material_label,
        })
    return out


def clean_quartz_title(raw):
    """BQuartz: strip NEW/thickness-only notes; strip a trailing 'polished'
    (implicit default, not part of our colour names) but KEEP a trailing
    'matt' (our library genuinely names those colours "X matt")."""
    t = raw
    note = ""
    m = re.search(r'-\s*NEW\b.*$', t, re.I)
    if m:
        note = t[m.start():].strip(" -")
        t = t[:m.start()].strip()
    t = re.sub(r'\s*\|\s*\d+mm only\s*$', '', t, flags=re.I).strip()
    finish = "Polished"
    if re.search(r'\bmatt\b\s*$', t, re.I):
        finish = "Matt"
    else:
        t = re.sub(r'\s*\bpolished\b\s*$', '', t, flags=re.I).strip()
    return t, finish, note


def clean_sintered_title(raw):
    """Techlam: strip a leading 'Techlam ' brand prefix, trailing dims block,
    trailing '- stock colour', and always strip the trailing finish word
    (our library sintered colour names never carry a finish suffix)."""
    t = re.sub(r'^Techlam\s+', '', raw, flags=re.I).strip()
    t = re.sub(r'\s*-\s*\d{3,4}\s*x\s*\d{3,4}(?:\s*x\s*\d+)?\s*mm.*$', '', t, flags=re.I).strip()
    t = re.sub(r'\s*-\s*stock colour\s*$', '', t, flags=re.I).strip()
    finish = ""
    fm = re.search(r'\b(3d textured|textured|matt|matte|polished)\s*$', t, re.I)
    if fm:
        finish = fm.group(1).strip()
        t = t[:fm.start()].strip(" -")
    if t.isupper():
        t = t.title()
    finish = finish.title() if finish and finish.lower() != "3d textured" else ("3D Textured" if finish else "")
    return t.strip(), finish, ""


def get_inspiration_slugs():
    xml = hl.fetch_text(INSPIRATION_SITEMAP, supplier=SUPPLIER, cache_key="_inspiration-sitemap")
    locs = sorted(set(re.findall(r'<loc>(https://bstoneuk\.co\.uk/inspiration/[^<]+)</loc>', xml)))
    slugs = []
    for u in locs:
        slug = u.rstrip("/").split("/")[-1]
        if slug.startswith("bquartz-"):
            slugs.append((slug, u))
    return slugs


def slug_base_and_name(slug):
    """'bquartz-calacatta-royale-7' -> ('calacatta-royale', 'Calacatta Royale')."""
    core = slug[len("bquartz-"):]
    core = re.sub(r'-\d+$', '', core)
    name = core.replace("-", " ").title()
    return core, name


def harvest_room_photos(quartz_colours):
    """quartz_colours: [colour_name,...] (our 25 BQuartz library colours, incl.
    Cadiz once created). Returns {colour_name: [room_img_url,...]} (<=2)."""
    slugs = get_inspiration_slugs()
    candidates = [(name, name) for name in quartz_colours]
    grouped = {}
    for slug, url in sorted(slugs):
        base, derived_name = slug_base_and_name(slug)
        match, score = hl.match_colour(derived_name, candidates)
        if not match:
            continue
        grouped.setdefault(match, []).append((slug, url))

    result = {}
    for colour, posts in grouped.items():
        posts = sorted(posts)[:2]
        urls = []
        for slug, page_url in posts:
            try:
                html_text = hl.fetch_text(page_url, supplier=SUPPLIER, cache_key=slug)
            except Exception as e:
                print(f"  inspiration FETCH FAIL {slug}: {e}", flush=True)
                continue
            imgs = INSPIRATION_IMG_RE.findall(html_text)
            imgs = [hl._absolutize(u, page_url) for u in imgs]
            if imgs:
                urls.append(imgs[0])
        if urls:
            result[colour] = urls
    return result


def main():
    bq_html = hl.fetch_text(BQUARTZ_URL, supplier=SUPPLIER, cache_key="_material-bquartz")
    tl_html = hl.fetch_text(TECHLAM_URL, supplier=SUPPLIER, cache_key="_material-techlam")

    bq_items = parse_grid_items(bq_html, BQUARTZ_URL, "Quartz")
    tl_items = parse_grid_items(tl_html, TECHLAM_URL, "Sintered Stone")
    print(f"BQuartz tiles: {len(bq_items)} | Techlam tiles: {len(tl_items)}", flush=True)

    products = []
    for it in bq_items:
        name, finish, note = clean_quartz_title(it["raw_title"])
        it.update(clean_name=name, finish=finish, note=note)
        products.append(it)
    for it in tl_items:
        name, finish, note = clean_sintered_title(it["raw_title"])
        it.update(clean_name=name, finish=finish, note=note)
        products.append(it)

    for p in products:
        print(f"  [{p['material']}] {p['raw_title']!r} -> name={p['clean_name']!r} "
              f"finish={p['finish']!r} note={p['note']!r}", flush=True)

    quartz_colours = [p["clean_name"] for p in products if p["material"] == "Quartz"]
    print("Fetching inspiration (room) pages for BQuartz colours...", flush=True)
    rooms = harvest_room_photos(quartz_colours)
    for colour, urls in rooms.items():
        print(f"  room photos: {colour!r} -> {len(urls)}", flush=True)

    out = {"products": products, "rooms": rooms}
    out_path = os.path.join(SCRATCH, "bstone-harvest.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"WROTE {out_path}: {len(products)} products, {len(rooms)} colours with room photos")


if __name__ == "__main__":
    main()
