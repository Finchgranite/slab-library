"""AKG Surfaces (Coante quartz) -- gallery harvest, phase 2 (2026-08-25).

All 49 AKG entries already have a good true-scale slab `image` (main) -- DO NOT
replace it. This script only adds `closeup`/`room` gallery images.

Step 1 (this file): most colours were already fully crawled by the earlier
akg_harvest.py/akg_wp_sweep.py passes -- their OneDrive colour folders
(BRANDS_ROOT/1. QUARTZ/AKG SURFACES (Sempre-Coante)/<Colour>/) already hold
every image AKG's product page offers. Classify what's there by filename
first (AKG's own naming: Kitchen/K/Composition/Render/Marketing = room;
Close-Up/Bookmatch/PQ/Pattern/Detail = closeup) -- confirmed by eyeballing
samples of each keyword across several colours before writing this classifier.
NOTE: AKG also publishes near-square (1:1) crops of the SAME full-slab photo
for social media (e.g. Cortina/Sierra/Brittanica/Nuvo/Venato/Vicenza "-2" or
"-1" files at 2560x2560) -- verified visually these are NOT texture closeups,
just re-cropped slab shots, so aspect ratio is NOT used as a fallback
classifier here (unlike other suppliers) -- keyword match or nothing.

Step 2: for colours whose folder lacks a closeup and/or room after that pass,
fetch the live productUrl page (cached under tools/_cache/akg/) and look for
NEW images (Cloudinary CDN + plain wp-content, per the akg_wp_sweep LESSON)
not already downloaded, classify them the same way, and download any found
into the OneDrive folder.

Velare Gold: productUrl was a placeholder search-query URL (never a real
product page). Confirmed via a live site search (?s=Velare+Gold and
?s=Velare) that AKG Surfaces no longer lists this colour at all ("Sorry, but
nothing matched your search terms" / "No results") -- likely discontinued/
renamed since the price book row was added. No folder, no page, no gallery
possible; left as closeup/room = none, flagged in the report.

Writes tools/akg-galleries-harvest.json (per-colour: local closeup/room file
picks + any newly downloaded files + notes). Re-run tools/reconcile_akg_galleries.py
--report / --apply to convert + write into slabs.json.
"""
import json
import os
import re

import harvest_lib as hl

SUPPLIER = "akg"
ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "AKG SURFACES (Sempre-Coante)")
SCRATCH = os.path.dirname(os.path.abspath(__file__))

MAIN_PAIR_RE = re.compile(r'^.+ - AKG Surfaces\.(jpg|webp)$', re.I)
SKIP_RE = re.compile(r'\.(mp4|mov)$|design[- ]?for[- ]?sm|slab (in rack|with sizes|& sizes)|slab sizes', re.I)
ROOM_RE = re.compile(r'kitchen|(?:^|[-_])k[-_.]|composition|render|marketing|install|ambient|vanity|bathroom', re.I)
CLOSEUP_RE = re.compile(r'close[-_ ]?up|bookmatch|\bpq\b|pattern|texture|detail|\bcu\b', re.I)
# priority within a kind -- lower index wins when there are several candidates
ROOM_PRIORITY = ["kitchen", "composition", "render", "marketing", "install", "ambient", "vanity", "bathroom"]
CLOSEUP_PRIORITY = ["close-up", "closeup", "bookmatch", "pq", "pattern", "detail", "texture"]


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def classify(fn):
    if MAIN_PAIR_RE.match(fn) or SKIP_RE.search(fn):
        return None
    if ROOM_RE.search(fn):
        return "room"
    if CLOSEUP_RE.search(fn):
        return "closeup"
    return None


def priority_rank(fn, kind):
    low = fn.lower()
    order = ROOM_PRIORITY if kind == "room" else CLOSEUP_PRIORITY
    for i, kw in enumerate(order):
        if kw.replace("-", "") in low.replace("-", "").replace("_", ""):
            return i
    return len(order)


def local_folder_for(colour):
    folders = [d for d in os.listdir(ROOT)
               if os.path.isdir(os.path.join(ROOT, d)) and not d.startswith("A1-")]
    key = norm(colour)
    for d in folders:
        if norm(d) == key:
            return d
    return None


def scan_local(colour):
    """Returns (folder_or_None, closeups[], rooms[]) -- filenames only."""
    fold = local_folder_for(colour)
    if not fold:
        return None, [], []
    fpath = os.path.join(ROOT, fold)
    files = [f for f in os.listdir(fpath) if re.search(r'\.(jpe?g|png|webp)$', f, re.I)]
    closeups, rooms = [], []
    for f in files:
        k = classify(f)
        if k == "room":
            rooms.append(f)
        elif k == "closeup":
            closeups.append(f)
    closeups.sort(key=lambda f: priority_rank(f, "closeup"))
    rooms.sort(key=lambda f: priority_rank(f, "room"))
    return fold, closeups, rooms


# ------------------------------------------------------------- site fetch --
CLOUDINARY_RE = re.compile(r'https://res\.cloudinary\.com/[^"\s>\\]+')


def extract_site_candidates(html_text, base_url):
    """Broad scan (per akg_harvest.py's proven approach -- AKG's gallery
    markup isn't always plain <img>, so scan the whole page text for any
    Cloudinary asset URL, plus hl.extract_images for plain wp-content <img>
    sources missed by the Cloudinary-only pass)."""
    out = {}
    for m in CLOUDINARY_RE.finditer(html_text):
        u = m.group(0).rstrip("',")
        bm = re.search(r'/v\d+/([^/]+)/', u)
        base = bm.group(1) if bm else u.split("/")[-1]
        if re.search(r'favicon|logo|akg[-_]?surfaces|cropped-favicon', base, re.I):
            continue
        wm = re.search(r'w_(\d+)', u)
        w = int(wm.group(1)) if wm else 0
        prev = out.get(base)
        if prev is None or w > prev[1]:
            out[base] = (u, w)
    for im in hl.extract_images(html_text, base_url):
        if "wp-content" in im["url"] and "res.cloudinary.com" not in im["url"]:
            base = im["url"].split("/")[-1].split("?")[0]
            base = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', base)
            if re.search(r'favicon|logo', base, re.I):
                continue
            prev = out.get(base)
            w = im.get("width") or 0
            if prev is None or w > prev[1]:
                out[base] = (im["url"], w)
    return [{"base": b, "url": u} for b, (u, w) in out.items()]


def main():
    lib = hl.load_library()
    akg = [s for s in lib["slabs"] if s.get("supplier") == "AKG Surfaces"]

    manifest = []
    for s in akg:
        colour, eid, url = s["colour"], s["id"], s.get("productUrl", "")
        fold, closeups, rooms = scan_local(colour)
        rec = {"colour": colour, "id": eid, "folder": fold, "productUrl": url,
               "local_closeups": closeups, "local_rooms": rooms,
               "new_closeups": [], "new_rooms": [], "note": ""}

        need_closeup = not closeups
        need_room = not rooms
        if not (need_closeup or need_room):
            manifest.append(rec)
            print(f"{colour:<28} local only: closeup={closeups[0] if closeups else '-'}  room={rooms[0] if rooms else '-'}")
            continue

        if colour == "Velare Gold":
            rec["note"] = ("Product not found on akgsurfaces.co.uk -- confirmed via live "
                            "site search (?s=Velare+Gold and ?s=Velare both return "
                            "'nothing matched your search terms'). No folder, no page, "
                            "likely discontinued/renamed since price-book row was added. "
                            "Main image (from an earlier crawl) kept; no gallery possible.")
            manifest.append(rec)
            print(f"{colour:<28} SKIP -- not on site (see note)")
            continue

        if not url or not url.startswith("http"):
            rec["note"] = "no productUrl -- cannot fetch"
            manifest.append(rec)
            print(f"{colour:<28} SKIP -- no productUrl")
            continue

        try:
            html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=norm(colour))
        except Exception as e:
            rec["note"] = f"fetch failed: {e}"
            manifest.append(rec)
            print(f"{colour:<28} FETCH FAIL {e}")
            continue

        known_bases = {re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', f).rsplit(".", 1)[0].lower()
                       for f in (closeups + rooms + (os.listdir(os.path.join(ROOT, fold)) if fold else []))}
        cands = extract_site_candidates(html_text, url)
        new_close, new_room = [], []
        for c in cands:
            base_key = c["base"].lower()
            if any(base_key in kb or kb in base_key for kb in known_bases):
                continue
            k = classify(c["base"])
            if k == "closeup":
                new_close.append(c)
            elif k == "room":
                new_room.append(c)
        new_close.sort(key=lambda c: priority_rank(c["base"], "closeup"))
        new_room.sort(key=lambda c: priority_rank(c["base"], "room"))

        downloaded_close = downloaded_room = None
        if need_closeup and new_close:
            pick = new_close[0]
            try:
                data, used_url = hl.fetch_best(pick["url"], supplier=SUPPLIER,
                                                cache_key=f"img-{norm(colour)}-closeup")
                fn = used_url.split("/")[-1].split("?")[0]
                if not fold:
                    fold = colour
                p = hl.save_original(data, ROOT, fold, fn)
                downloaded_close = os.path.basename(p)
                rec["new_closeups"].append(downloaded_close)
            except Exception as e:
                rec["note"] += f" | closeup dl fail: {e}"
        if need_room and new_room:
            pick = new_room[0]
            try:
                data, used_url = hl.fetch_best(pick["url"], supplier=SUPPLIER,
                                                cache_key=f"img-{norm(colour)}-room")
                fn = used_url.split("/")[-1].split("?")[0]
                if not fold:
                    fold = colour
                p = hl.save_original(data, ROOT, fold, fn)
                downloaded_room = os.path.basename(p)
                rec["new_rooms"].append(downloaded_room)
            except Exception as e:
                rec["note"] += f" | room dl fail: {e}"

        rec["folder"] = fold
        if need_closeup and not downloaded_close:
            rec["note"] += " | no closeup found on site"
        if need_room and not downloaded_room:
            rec["note"] += " | no room found on site"
        manifest.append(rec)
        print(f"{colour:<28} site: new_closeup={downloaded_close or '-'}  new_room={downloaded_room or '-'}"
              f"  ({len(cands)} candidates){rec['note']}")

    out_path = os.path.join(SCRATCH, "akg-galleries-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nWROTE {out_path}: {len(manifest)} colours")


if __name__ == "__main__":
    main()
