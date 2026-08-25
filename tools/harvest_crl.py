"""CRL (crlstone.co.uk) harvest -- phase 2.

Colour pages are the WP 'collection' post type (fetched once via the REST API
with per_page=100, page=1/2 -- cheaper than one curl per colour page since
`_fields=slug,link,title,content,excerpt` returns the FULL rendered HTML body
in the listing itself, no per-page fetch needed for the 102 still-live pages).

Each live page's content HTML carries (verified visually on Arabescato Vagli,
Antonella, Monte Bianco before writing this):
  - `collection-slides` panel `style="background-image:url(...)"` -- 2-3
    lifestyle/installation photos credited to a fitter/photographer -- ROOM.
  - first 1-3 `<p class="has-text-align-center">` paragraphs right after the
    title section -- used verbatim (joined, truncated) as the `details` blurb.
  - `finish-wrapper` / `finish_expand` blocks: `data-type="full-slab"` image
    (no size suffix, PNG/JPG under content/uploads) -- the true main SLAB;
    `data-type="zoom"` image -- CLOSEUP. (Same pattern scrape_crl.py already
    exploited via a plain "slab-in-filename, not kitchen/roomset/lifestyle"
    regex on the spec-image widget -- reused here for consistency with the 91
    mains already in the library so we don't flip-flop on which crop is
    "the" full-slab file.)
  - `collection-specification` table -- thickness/finish rows (cross-check
    only; `slabSizes` comes from the price book, which already has all 109
    CRL colours with slab dims -- see harvest_lib.load_pricebook("CRL")).

18 library colours (12 closeup-only + 6 missing) do NOT appear in the current
102-page listing and return "no results" on-site search -- discontinued /
delisted. `http://archive.org/wayback/available` finds a snapshot for 12 of
these; the *media files* (content/uploads/...) usually still resolve directly
on the LIVE crlstone.co.uk domain even though the product page was removed
(verified: Materia-Gris-Slab-image-*.jpg -> HTTP 200 on crlstone.co.uk while
the /surfaces/matteria-gris/ page itself 404s) -- so those are fetched from
the live domain first, wayback image proxy as fallback. The other 6 (no
wayback snapshot either) stay `missing`/`closeup-only`, reported as such.

Writes tools/crl-harvest.json. Re-run is cheap: WP listing + wayback snapshots
are cached under tools/_cache/crl/; delete that dir to force a re-fetch.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SUPPLIER = "crl"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
BASE = "https://crlstone.co.uk"

# 18 closeup-only/missing colours confirmed absent from the live /collection
# listing (checked against all 102 slugs) -- candidate slugs to try via wayback.
DISCONTINUED_SLUGS = {
    "dual-blanco": "Dual Blanco", "dual-negro": "Dual Negro",
    "dukhan-marron": "Dukhan Marron", "jasper-moka": "Jasper Moka",
    "kaizen-bronce": "Kaizen Bronce", "korten-corten": "Korten Corten",
    "larsen-super-blanco-gris": "Larsen Super Blanco Gris",
    "lyra-gris": "Lyra Gris", "masai-blanco-plus": "Masai Blanco Plus",
    "masai-piedra": "Masai Piedra", "matteria-antracita": "Matteria Antracita",
    "matteria-gris": "Matteria Gris", "matteria-muschio": "Matteria Muschio",
    "matteria-taupe": "Matteria Taupe", "silk-blanco": "Silk Blanco",
    "silk-gris": "Silk Gris", "the-new-blacks-muschio": "The New Blacks Muschio",
    "the-new-blacks-prugna": "The New Blacks Prugna",
}

KITCHEN_ROOM_HINTS = re.compile(r"kitchen|roomset|lifestyle", re.I)


def get_collection_records():
    recs = []
    for page in (1, 2):
        js = hl.fetch_text(
            f"{BASE}/wp-json/wp/v2/collection?per_page=100&page={page}"
            "&_fields=slug,link,title,content,excerpt",
            supplier=SUPPLIER, cache_key=f"_collection_p{page}")
        batch = json.loads(js)
        if not batch:
            break
        recs.extend(batch)
    return recs


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def extract_full_slab(html_text):
    urls = set(re.findall(
        r'content/uploads/[^"\'\s]*slab[^"\'\s]*\.(?:jpg|jpeg|png)', html_text, re.I))
    urls = {u for u in urls if not KITCHEN_ROOM_HINTS.search(u)}
    if not urls:
        return None
    masters = {re.sub(r"-\d+x\d+(?=\.\w+$)", "", u) for u in urls}

    def rank(u):
        lu = u.lower()
        return (0 if "full-slab" in lu or "full_slab" in lu else
                2 if "zoom" in lu else 1, len(u))
    best = sorted(masters, key=rank)[0]
    return best if best.startswith("http") else BASE + "/" + best.lstrip("/")


def extract_zoom(html_text):
    urls = sorted(set(re.findall(
        r'content/uploads/[^"\'\s]*zoom[^"\'\s]*\.(?:jpg|jpeg|png)', html_text, re.I)))
    out = []
    for u in urls:
        out.append(u if u.startswith("http") else BASE + "/" + u.lstrip("/"))
    return out[:2]


def extract_rooms(html_text):
    urls = re.findall(r'class="panel[^"]*"\s+style="background-image:url\(([^)]+)\);?"',
                       html_text, re.I)
    out = []
    for u in urls:
        u = H.unescape(u.strip())
        if u and u not in out:
            out.append(u)
    return out[:3]


def extract_blurb(html_text):
    m = re.search(r'</section>(.*?)(?:collection-icons|finish-wrapper|<figure)', html_text, re.S)
    chunk = m.group(1) if m else html_text[:4000]
    paras = re.findall(r'<p[^>]*>(.*?)</p>', chunk, re.S)
    bits = []
    for p in paras:
        t = H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        if t and "silica free collection" not in t.lower():
            bits.append(t)
        if len(" ".join(bits)) > 220:
            break
    return " ".join(bits)[:320]


def extract_surface_brand(html_text):
    m = re.search(r'class="surface-brand">\s*([^<]+?)\s*</span>', html_text)
    return H.unescape(m.group(1)).strip() if m else ""


def harvest_active(rec):
    slug = rec["slug"]
    link = rec["link"]
    name = H.unescape(rec["title"]["rendered"]).strip()
    content = rec["content"]["rendered"]
    return {
        "slug": slug, "url": link, "name": name, "status": "live",
        "slab": extract_full_slab(content),
        "closeups": extract_zoom(content),
        "rooms": extract_rooms(content),
        "blurb": extract_blurb(content),
        "range": extract_surface_brand(content),
    }


def harvest_discontinued(slug, name):
    try:
        avail_js = hl.fetch_text(
            f"http://archive.org/wayback/available?url=crlstone.co.uk/surfaces/{slug}/",
            supplier=SUPPLIER, cache_key=f"_wb-avail-{slug}", polite_delay=1.0)
        avail = json.loads(avail_js)
    except Exception as e:
        return {"slug": slug, "name": name, "status": "no-wayback", "error": str(e)}
    snap = (avail.get("archived_snapshots") or {}).get("closest")
    if not snap or not snap.get("available"):
        return {"slug": slug, "name": name, "status": "no-wayback"}
    ts = snap["timestamp"]
    wb_url = f"http://web.archive.org/web/{ts}/https://crlstone.co.uk/surfaces/{slug}/"
    try:
        html_text = hl.fetch_text(wb_url, supplier=SUPPLIER, cache_key=f"wb-{slug}", polite_delay=1.0)
    except Exception as e:
        return {"slug": slug, "name": name, "status": "wayback-fetch-fail", "error": str(e)}
    slab = extract_full_slab(html_text)
    closeups = extract_zoom(html_text)
    rooms = extract_rooms(html_text)
    blurb = extract_blurb(html_text)
    return {
        "slug": slug, "name": name, "status": "discontinued-wayback",
        "url": f"https://web.archive.org/web/{ts}/https://crlstone.co.uk/surfaces/{slug}/",
        "wayback_ts": ts, "slab": slab, "closeups": closeups, "rooms": rooms,
        "blurb": blurb, "range": "",
    }


def main():
    recs = get_collection_records()
    print(f"{len(recs)} live CRL collection pages", flush=True)
    manifest = []
    for r in recs:
        try:
            manifest.append(harvest_active(r))
        except Exception as e:
            manifest.append({"slug": r.get("slug"), "url": r.get("link"),
                              "name": r.get("title", {}).get("rendered", ""),
                              "status": "error", "error": str(e)})

    for slug, name in DISCONTINUED_SLUGS.items():
        rec = harvest_discontinued(slug, name)
        manifest.append(rec)
        print(f"discontinued {name!r}: {rec['status']} slab={'Y' if rec.get('slab') else 'N'}",
              flush=True)

    out_path = os.path.join(SCRATCH, "crl-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    live = sum(1 for m in manifest if m.get("status") == "live")
    withslab = sum(1 for m in manifest if m.get("slab"))
    disc_ok = sum(1 for m in manifest if m.get("status") == "discontinued-wayback" and m.get("slab"))
    print(f"WROTE {out_path}: {len(manifest)} records, {live} live, {withslab} with a slab image, "
          f"{disc_ok} discontinued colours recovered via wayback")


if __name__ == "__main__":
    main()
