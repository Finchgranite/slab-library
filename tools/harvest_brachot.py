"""Brachot / Unistone / BQS (all www.brachot.com, Next.js/Storyblok) harvest.

One Belgian company, one site, three in-house brands sharing the same
product-page template (`/en/materials/{code}/{slug}-{suffix}/`, suffix
-uniceramica / -unistone / -bqs). Per HARVEST-SPEC.md + nourl-DISCOVERY.md,
discovery already resolved a productUrl for every one of the 111 colours
(35 Brachot porcelain, 33 Unistone quartz, 43 BQS quartz) --
tools/_reports/nourl-discovery.json. This script re-fetches each of those
111 pages directly (no sitemap crawl needed) and parses the embedded
`__NEXT_DATA__` JSON:
  - materialPim.images[]            -- cdn.pimber.ly full-res product photos
                                        (fullslab/chevalet flat shots, and
                                        kitchen/house/wall room photos)
  - materialStory.finishes[].image  -- a.storyblok.com ~1920x954 slab crop,
                                        ONE per finish sold -- the best main
                                        slab candidate (true aspect, no logo/
                                        watermark, dead flat).
A dozen BQS colours (see BQS_REFERENCE_URLS below, lifted from discovery's
image_kinds_seen notes) also have a dedicated /en/references/{id}/kitchen-
...-/ room page; fetched as a bonus for a better-captioned room shot.

Writes tools/_cache/brachot-harvest.json (one row per colour, tagged with
its supplier). reconcile_brachot.py consumes it, --report then --apply.
"""
import html as H
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER_TAG = "brachot"  # cache/report folder tag (all three brands share the site)
BASE = "https://www.brachot.com"

DISCOVERY_PATH = os.path.join(hl.REPORTS_DIR, "nourl-discovery.json")

LIMIT = int(os.environ.get("BR_LIMIT", "0")) or None  # for quick testing only

# One discovery URL 404s/empties out (Brachot Taj Mahal's primary code ksxtama has no
# images or finishes on brachot.com); its own notes flag a duplicate code, ksxtma, which
# resolves fine -- override just this one product_url before harvesting.
URL_OVERRIDES = {
    "brachot--taj-mahal": "https://www.brachot.com/en/materials/ksxtma/taj-mahal-uniceramica/",
}

# BQS colours with a known dedicated room-reference page (from nourl-discovery.json
# image_kinds_seen notes -- saves a blind search of the whole references section).
BQS_REFERENCE_URLS = {
    "bqs--avenza": ["https://www.brachot.com/en/references/119/kitchen-worktop-in-bqs-avenza/"],
    "bqs--bianco-fontana": ["https://www.brachot.com/en/references/504011/kitchen-worktop-in-bqs-bianco-fontana/"],
    "bqs--black-mirrorlux": ["https://www.brachot.com/en/references/395/kitchen-worktop-in-bqs-black-mirrorlux/"],
    "bqs--canaletto": ["https://www.brachot.com/en/references/512162/kitchen-worktop-and-splashback-in-bqs-canaletto/"],
    "bqs--capri": ["https://www.brachot.com/en/references/507177/quartz-kitchen-worktop-splashback-in-bqs-capri/"],
    "bqs--carrara-extra": ["https://www.brachot.com/en/references/512172/kitchen-worktop-in-bqs-carrara-extra/"],
    "bqs--crema-fiore": ["https://www.brachot.com/en/references/601073/kitchen-worktop-and-splashback-in-bqs-crema-fiore/"],
    "bqs--glacier": ["https://www.brachot.com/en/references/607092/kitchen-worktop-in-bqs-glacier/"],
    "bqs--neo-calacatta": ["https://www.brachot.com/en/references/396/kitchen-worktop-in-bqs-neo-calcatta/"],
    "bqs--siberia": ["https://www.brachot.com/en/references/512031/kitchen-worktop-and-splashback-in-bqs-siberia/"],
    "bqs--super-white-plus": ["https://www.brachot.com/en/references/397/kitchen-worktop-in-bqs-super-white-plus/"],
    "bqs--taj-mahal": ["https://www.brachot.com/en/references/606231/", "https://www.brachot.com/en/references/607091/"],
    "bqs--white-almond": ["https://www.brachot.com/en/references/398/kitchen-worktop-in-bqs-white-almond/"],
}

_ROOM_FN = re.compile(r'kitchen|bathroom|vanity|\bwall\b|\bhouse\b|getuigenis|testimon|project|install|WSOF', re.I)
_CLOSEUP_FN = re.compile(r'detail|close[-_]?up|\bcu[_-]|texture|zoom|swatch', re.I)
_SLAB_FN = re.compile(r'fullslab|chevalet|oncheval|full[-_]?slab', re.I)
_DIM_IN_FN = re.compile(r'(\d{3,4})x(\d{3,4})')


def load_discovery():
    d = json.load(open(DISCOVERY_PATH, encoding="utf-8"))
    out = [x for x in d if x["supplier"] in ("Brachot", "Unistone", "BQS")]
    for x in out:
        if x["library_id"] in URL_OVERRIDES:
            x["product_url"] = URL_OVERRIDES[x["library_id"]]
    return out


def get_next_data(html_text):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def fn_of(url):
    return url.split("/")[-1].split("?")[0]


def guess_aspect(url):
    """Storyblok/pimber.ly filenames often embed WxH (e.g. _1920x954_); use it
    to pre-check aspect without downloading."""
    m = _DIM_IN_FN.search(fn_of(url))
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if not h:
        return None
    return w / h


def classify_pim_image(url):
    fn = fn_of(url)
    if _ROOM_FN.search(fn):
        return "room"
    if _CLOSEUP_FN.search(fn):
        return "closeup"
    if _SLAB_FN.search(fn):
        return "slab"
    ar = guess_aspect(url)
    if ar:
        ar_n = max(ar, 1 / ar)
        if 1.6 <= ar_n <= 2.4:
            return "slab"
        if 0.8 <= ar_n <= 1.25:
            return "closeup"
    # No filename hint and no embedded dims to judge aspect: a real check (spot-checking
    # the contact sheets) showed most of these generic/hashed-filename images are actually
    # customer kitchen/installation photos, not product texture shots -- so, unlike a
    # filename that says "kitchen", these give no reliable signal for EITHER bucket.
    # Drop them rather than mislabel them into whichever bucket looks safe.
    return None


def harvest_one(rec):
    url = rec["product_url"]
    code = url.rstrip("/").split("/")[-2]
    cache_key = code
    try:
        html_text = hl.fetch_text(url, supplier=SUPPLIER_TAG, cache_key=cache_key)
    except Exception as e:
        return {"discovery": rec, "url": url, "error": str(e)}

    data = get_next_data(html_text)
    if not data:
        return {"discovery": rec, "url": url, "error": "no __NEXT_DATA__"}
    try:
        d = data["props"]["pageProps"]["data"]
        pim = d["materialPim"]
        story = d.get("materialStory") or {}
    except Exception as e:
        return {"discovery": rec, "url": url, "error": f"unexpected JSON shape: {e}"}

    title = H.unescape((pim.get("title") or "").strip())
    origin = pim.get("origin") or ""
    description = H.unescape((pim.get("description") or "").strip())

    finishes = []
    for f in story.get("finishes") or []:
        img = f.get("image") or {}
        src = img.get("filename") or ""
        if not src:
            continue
        finishes.append({"name": f.get("name", ""), "src": src})

    slab_imgs, closeup_imgs, room_imgs = [], [], []
    for im in pim.get("images") or []:
        src = im.get("src") or ""
        if not src:
            continue
        kind = classify_pim_image(src)
        if kind == "slab":
            slab_imgs.append(src)
        elif kind == "closeup":
            closeup_imgs.append(src)
        elif kind == "room":
            room_imgs.append(src)
        # kind is None (no reliable signal either way) -- dropped, not guessed into a bucket

    # bonus bookmatch/batch-variant photos (openBookMaterials) -- extra slab-adjacent shots
    book_imgs = [b["imageSrc"] for b in (pim.get("openBookMaterials") or []) if b.get("imageSrc")]

    ref_rooms = []
    for ref_url in BQS_REFERENCE_URLS.get(rec["library_id"], []):
        try:
            rid = ref_url.rstrip("/").split("/")[-2]
            rhtml = hl.fetch_text(ref_url, supplier=SUPPLIER_TAG, cache_key=f"ref-{rid}")
        except Exception:
            continue
        rdata = get_next_data(rhtml)
        if not rdata:
            continue
        try:
            imgs = hl.extract_images(rhtml, ref_url)
        except Exception:
            imgs = []
        for im in imgs:
            u = im["url"]
            if re.search(r'\.(jpe?g|png|webp)(?:[?#]|$)', u, re.I) and not re.search(r'logo|icon', u, re.I):
                ref_rooms.append(u)

    def dedupe(seq):
        seen, out = set(), []
        for u in seq:
            k = fn_of(u)
            if k in seen:
                continue
            seen.add(k)
            out.append(u)
        return out

    return {
        "discovery": rec, "url": url, "code": code, "title": title,
        "origin": origin, "description": description,
        "finishes": finishes,
        "slab_imgs": dedupe(slab_imgs), "book_imgs": dedupe(book_imgs),
        "closeup_imgs": dedupe(closeup_imgs)[:6],
        "room_imgs": dedupe(room_imgs + ref_rooms)[:8],
    }


def main():
    recs = load_discovery()
    if LIMIT:
        recs = recs[:LIMIT]
    print(len(recs), "colour pages to harvest (Brachot+Unistone+BQS combined)", flush=True)
    manifest = []
    for i, rec in enumerate(recs, 1):
        row = harvest_one(rec)
        manifest.append(row)
        if row.get("error"):
            print(f"[{i}/{len(recs)}] FETCH FAIL {rec['library_id']}: {row['error']}", flush=True)
            continue
        print(f"[{i}/{len(recs)}] {rec['supplier']:8s} {rec['library_colour']!r:32s} "
              f"finishes={len(row['finishes'])} slab_imgs={len(row['slab_imgs'])} "
              f"closeups={len(row['closeup_imgs'])} rooms={len(row['room_imgs'])}", flush=True)

    out_path = os.path.join(SCRATCH, "brachot-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error"))
    with_main = sum(1 for m in manifest if not m.get("error") and (m.get("finishes") or m.get("slab_imgs")))
    print(f"WROTE {out_path}: {len(manifest)} pages, {ok} ok, {with_main} with a slab-candidate image")


if __name__ == "__main__":
    main()
