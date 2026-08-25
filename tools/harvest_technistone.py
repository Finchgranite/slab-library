"""Technistone (technistone.com) harvest -- phase 2 galleries pass.

All 49 Technistone library entries already have a good slab main and a
productUrl (https://www.technistone.com/gbr/color/<slug>) from an earlier
pass -- this run is galleries-only: closeup + room images, slabSizes,
details.

KEY FINDING: an earlier pass had already downloaded a near-complete media
package per colour into OneDrive
  BRANDS_ROOT/1. QUARTZ/TECHNISTONE/Sample,slab & kitchen images/<Colour>/
Most colours have a "<slug>-mediaPackage-lowRes/" subfolder (sometimes
"(1)"-suffixed, sometimes with the site's own weird spelling) containing:
  - "<slug>-detail.jpg" / "* close up *"          -> closeup candidate
  - "<slug>-fullSlab.jpg" / "*_SLAB*" / "*full Slab*" -> slab (already have
    a good main for all 49; per HARVEST-SPEC.md/task instructions we do NOT
    replace it, so these are ignored)
  - "<slug>-moodboard.jpg" / "* mood board *"     -> styled prop shot, SKIP
    (not a real slab/closeup/room per the spec's own classifier intent)
  - "realizations/<slug>-realization-N.{jpg,png}" (sometimes flat, no
    subfolder) -> room/installation photo candidates
A handful of colours (Badal Grey, Crystal Diamond, Duna Beige, Elysian Gold,
Mistral White, Taj Mahal Gold) have a flatter layout directly in the colour
folder: "slab-detail.jpg"/"slab-default.jpg" + "realization-N.jpg".
Per HARVEST-SPEC.md ("CHECK THAT FOLDER FIRST for originals an earlier pass
already downloaded; classify/convert those before fetching more") this
script uses ONLY those local originals for images -- no network image
fetching needed, and every one of the 49 has at least 1 closeup + several
room candidates locally.

Network fetch (2s/request, curl via harvest_lib, cached under
tools/_cache/technistone/) is used ONLY for page TEXT: the site's
"<Collection> Collection" subtitle, meta-description blurb, and the
Specifications table's Finish row -- used to build the one-line `details`.
slabSizes comes from the price book (authoritative per HARVEST-SPEC.md;
confirmed identical to the site's own Size row on Altamonte).

Also fetches sitemap.xml once to compare site colour slugs against the 49
price-book colours (reported, not acted on -- sitemap is stale/incomplete,
missing several live pages like badal-grey, so treated as a lower-bound
list of "site colours the price book doesn't have").

Writes tools/technistone-harvest.json. Re-run is cheap (page cache); delete
tools/_cache/technistone/ to force a re-fetch of text.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "technistone"
GALLERY_BASE = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "TECHNISTONE", "Sample,slab & kitchen images")

MOODBOARD_HINTS = re.compile(r'mood.?board', re.I)
SLAB_HINTS = re.compile(r'full.?slab|_slab\b|slab.?default|slab image|-by-technistone|^\d', re.I)
CLOSEUP_HINTS = re.compile(r'detail|close.?up', re.I)
SKIP_EXT = re.compile(r'\.(psd|zip|url)$', re.I)
IMG_EXT = re.compile(r'\.(jpe?g|png|webp)$', re.I)


def _natural_key(path):
    fn = os.path.basename(path)
    m = re.search(r'(\d+)', fn)
    return (int(m.group(1)) if m else -1, fn.lower())


def find_gallery_folder(colour, folder_map):
    folder = folder_map.get(colour)
    if not folder:
        return None
    return os.path.join(GALLERY_BASE, folder)


def scan_local_assets(fpath):
    """Walk a colour's OneDrive folder, return (closeup_paths, room_paths)
    sorted best-first. See module docstring for the classification rules."""
    closeups, rooms = [], []
    for root, dirs, files in os.walk(fpath):
        in_realizations = os.path.basename(root).lower() == "realizations"
        for f in files:
            if SKIP_EXT.search(f) or not IMG_EXT.search(f):
                continue
            if MOODBOARD_HINTS.search(f):
                continue
            full = os.path.join(root, f)
            low = f.lower()
            if in_realizations or re.search(r'realization', low):
                rooms.append(full)
            elif CLOSEUP_HINTS.search(low) and not SLAB_HINTS.search(low):
                closeups.append(full)
            elif re.search(r'kitchen|kitchens|kaboodle', low) and not SLAB_HINTS.search(low):
                rooms.append(full)
            # else: fullSlab/_SLAB/sample/-by-Technistone/etc -- not a gallery asset, skip
    closeups = sorted(set(closeups), key=lambda p: (-os.path.getsize(p),))
    rooms = sorted(set(rooms), key=_natural_key)
    return closeups, rooms


def parse_page(html_text):
    subtitle = ""
    m = re.search(r'<h1 class="noPad withLine">\s*([^<]*?)\s*</h1>\s*<p class="subtitle">\s*([^<]*?)\s*</p>',
                  html_text, re.S)
    if m:
        subtitle = H.unescape(m.group(2)).strip()

    desc = ""
    m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html_text, re.I)
    if m:
        desc = H.unescape(m.group(1)).strip()

    finishes = []
    for m in re.finditer(
            r'<div class="cell title"><span>\s*Finish\s*</span></div>\s*'
            r'<div class="cell"><span>\s*([^<]*?)\s*</span>',
            html_text, re.S):
        v = H.unescape(m.group(1)).strip()
        if v and v not in finishes:
            finishes.append(v)

    size_text = ""
    m = re.search(
        r'<div class="cell title"><span>\s*Size\s*</span></div>\s*'
        r'<div class="cell"><span>\s*([^<]*?)\s*</span>',
        html_text, re.S)
    if m:
        size_text = H.unescape(m.group(1)).strip()

    return {"collection": subtitle, "description": desc, "finishes": finishes, "site_size": size_text}


def main():
    lib = hl.load_library()
    entries = [s for s in lib["slabs"] if s.get("supplier") == "Technistone" and not s.get("naturalStone")]
    folder_map = json.load(open(os.path.join(SCRATCH, "technistone_foldermap.json"), encoding="utf-8"))

    # sitemap -- best-effort, for the "site colours not in price book" report only
    site_slugs = []
    try:
        xml = hl.fetch_text("https://www.technistone.com/sitemap.xml", supplier=SUPPLIER, cache_key="_sitemap")
        site_slugs = sorted(set(re.findall(r'<loc>https://www\.technistone\.com/color/([a-z0-9-]+)</loc>', xml)))
    except Exception as e:
        print("sitemap fetch failed (non-fatal):", e)

    manifest = []
    for i, e in enumerate(entries, 1):
        colour = e["colour"]
        url = e.get("productUrl", "")
        rec = {"colour": colour, "id": e["id"], "url": url}
        try:
            cache_key = e["id"].replace("technistone--", "")
            html_text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=cache_key)
            rec.update(parse_page(html_text))
        except Exception as ex:
            rec["error"] = str(ex)

        fpath = find_gallery_folder(colour, folder_map)
        if fpath and os.path.isdir(fpath):
            closeups, rooms = scan_local_assets(fpath)
            rec["closeups"] = closeups[:2]
            rec["rooms"] = rooms[:3]
        else:
            rec["closeups"], rec["rooms"] = [], []
            rec["no_local_folder"] = True

        manifest.append(rec)
        print(f"[{i}/{len(entries)}] {colour!r} | collection={rec.get('collection','')!r} "
              f"finishes={rec.get('finishes')} closeups={len(rec['closeups'])} rooms={len(rec['rooms'])}",
              flush=True)

    out_path = os.path.join(SCRATCH, "technistone-harvest.json")
    json.dump({"site_slugs": site_slugs, "entries": manifest}, open(out_path, "w", encoding="utf-8"),
               indent=1, ensure_ascii=False)
    ok = sum(1 for m in manifest if not m.get("error"))
    print(f"WROTE {out_path}: {len(manifest)} colours, {ok} page-fetch ok, "
          f"{sum(1 for m in manifest if m['closeups'])} with local closeups, "
          f"{sum(1 for m in manifest if m['rooms'])} with local rooms")
    print(f"site sitemap slugs: {len(site_slugs)}")


if __name__ == "__main__":
    main()
