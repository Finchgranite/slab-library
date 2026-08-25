"""Reconcile tools/picasso2-harvest.json with slab-library (supplier
"Picasso Surfaces", engineered colours only -- the new picassosurfaces.co.uk
site). --report prints the match table and changes nothing; --apply
downloads originals, writes webps, updates slabs.json via hl.patch_library
(bumps `generated`), writes the two contact sheets + REPORT.md.

Every image on this site is served at a uniform ~1920x1200 (1.6:1) crop
regardless of content -- slab, closeup and room shots are visually
indistinguishable by aspect ratio (unlike Fugen/Compac), and gallery item
order on the page is not semantically meaningful either (filenames are
per-colour but arbitrary: anna1/anna2/anna3/anna4, jg1/jg2/jg3 ...). Every
one of the 102 gallery images across the 36 colour pages was therefore
opened and hand-classified from contact sheets
(tools/_cache/picasso2/preview_part[123].png) BEFORE writing this file --
see PICKS below, keyed by 1-based position in picasso2-harvest.json's
per-colour images[] list (the order the page HTML presented them in, which
IS stable/reproducible for a given cached page, just not meaningful).

Two site data-quality issues found while classifying, both handled here:
  - Celestial Grey's and Celestial White's product pages embed the EXACT
    SAME three image URLs (.../cw1.png, cw2.png, cw3.png -- literally
    identical bytes). Applied to Celestial White only (filename prefix
    "cw" and the page's own name both point that way); Celestial Grey's
    gallery is left untouched this run (existing main kept) -- flagged in
    the report to ask Carl which product the photos actually belong to.
  - Taj Honey Onyx / Verde Onyx (translucent "onyx-look" ranges) each have
    TWO visually different studio slab shots on their page: a dramatic
    backlit version (glows amber/gold) and a true-daylight version (pale
    cream / muted teal respectively). The backlit shot was NOT used as
    `image` (misleading at a glance -- "Verde"/green backlit looks yellow);
    the daylight/true-colour studio shot was used as the main instead.
  - Taj Honey Onyx image #3 and Cristallo image #1 look like they may not
    depict the product at all (much paler than every other image on the
    same page) -- excluded from both main and gallery, flagged in the report.

Colours with NO clean plinth/rack "whole slab" photo on their page
(Cristallo, Erebus, Himalayan Pink Onyx has one so is fine -- actually just
Cristallo and Erebus) had their best full-bleed texture crop promoted to
`image` instead, since HARVEST-SPEC just requires "a real slab-face image",
not specifically a plinth photo -- flagged as an assumption in the report.
"""
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Picasso Surfaces"
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "Quantum & Picasso Quartz")

apply_mode = "--apply" in sys.argv

# slug -> [library colour name(s)] (golden-thunder covers two price-book rows)
SITE_TO_COLOURS = {
    "annapurna": ["Annapurna"], "aqua-gold": ["Aqua Gold"],
    "arabescato-corchia": ["Arabescato Corchia"], "arabescato-creme": ["Arabescato Creme"],
    "arctic-storm": ["Arctic Storm"], "aspen-gold": ["Aspen Gold"], "aspen": ["Aspen"],
    "calacatta-oro": ["Calacatta Oro"], "carrara-ice": ["Carrara Ice (Shimmer)"],
    "carrara-neo": ["Carrara Neo"], "carrara-white": ["Carrara White"], "cashmere": ["Cashmere"],
    "celestial-gold": ["Celestial Gold"], "celestial-grey": ["Celestial Grey"],
    "celestial-white": ["Celestial White"], "crema-royal": ["Crema Royal"], "cristallo": ["Cristallo"],
    "erebus": ["Erebus"], "golden-storm": ["Golden Storm"],
    "golden-thunder": ["Golden Thunder", "Thunder Gold"],
    "himalayan-pink-onyx": ["Himalyan Pink Onyx"], "jade-galcia": ["Jade Glacia"],
    "moonlight": ["Moonlight"], "nacorado": ["Nacorado"], "opal-royale": ["Opal Royale"],
    "orella": ["Orella"], "patagonia": ["Patagonia"], "pearla": ["Pearla"], "snowdale": ["Snowdale"],
    "solarius": ["Solarius"], "sunlight": ["Sunlight"], "super-white": ["Super White"],
    "taj-honey-onyx": ["Taj Honey Onyx"], "taj-mahal-extra": ["Taj Mahal Extra"],
    "verde-onyx": ["Verde Onyx"], "white-lake": ["White Lake"],
}
# site's own spelling, only where it differs from the price-book colour name
SITE_ALIAS = {
    "himalayan-pink-onyx": "Himalayan Pink Onyx", "jade-galcia": "Jade Galcia",
    "carrara-ice": "Carrara Ice",
}
# hand-classified picks: 1-based indices into that colour's images[] list.
# "main": promote to `image` (only for colours currently missing a slab).
PICKS = {
    "annapurna": {"closeups": [4], "rooms": [3]},
    "aqua-gold": {"closeups": [2], "rooms": [3]},
    "arabescato-corchia": {"closeups": [1], "rooms": [3]},
    "arabescato-creme": {"closeups": [1], "rooms": [2]},
    "arctic-storm": {"closeups": [3], "rooms": [1, 2]},
    "aspen-gold": {"closeups": [2], "rooms": []},
    "aspen": {"closeups": [1], "rooms": []},
    "calacatta-oro": {"closeups": [2], "rooms": [1]},
    "carrara-ice": {"closeups": [1], "rooms": []},
    "carrara-neo": {"closeups": [3], "rooms": [1, 2]},
    "carrara-white": {"closeups": [], "rooms": [1, 2]},
    "cashmere": {"main": 2, "closeups": [1], "rooms": [3]},
    "celestial-gold": {"closeups": [3], "rooms": [1, 2]},
    "celestial-grey": {"skip_gallery": True, "closeups": [], "rooms": []},  # site bug: shares White's photos
    "celestial-white": {"closeups": [2], "rooms": [1, 3]},
    "crema-royal": {"closeups": [3], "rooms": [2]},
    "cristallo": {"main": 2, "closeups": [3], "rooms": [4]},
    "erebus": {"main": 1, "closeups": [], "rooms": []},
    "golden-storm": {"closeups": [2], "rooms": [3]},
    "golden-thunder": {"closeups": [1], "rooms": [2, 3]},
    "himalayan-pink-onyx": {"main": 3, "closeups": [1], "rooms": [2]},
    "jade-galcia": {"main": 2, "closeups": [1], "rooms": [3]},
    "moonlight": {"closeups": [1], "rooms": [2, 3]},
    "nacorado": {"main": 1, "closeups": [2], "rooms": []},
    "opal-royale": {"main": 3, "closeups": [2], "rooms": [1]},
    "orella": {"main": 1, "closeups": [2], "rooms": [4]},
    "patagonia": {"main": 3, "closeups": [1], "rooms": [2]},
    "pearla": {"main": 3, "closeups": [2], "rooms": [1]},
    "snowdale": {"closeups": [1], "rooms": []},
    "solarius": {"main": 1, "closeups": [3], "rooms": [2]},
    "sunlight": {"closeups": [2], "rooms": [3, 4]},
    "super-white": {"closeups": [1], "rooms": []},
    "taj-honey-onyx": {"main": 1, "closeups": [2], "rooms": [4]},
    "taj-mahal-extra": {"closeups": [], "rooms": [1, 2]},
    "verde-onyx": {"main": 4, "closeups": [1], "rooms": [3]},
    "white-lake": {"closeups": [], "rooms": [3]},
}

import json
manifest = json.load(open(os.path.join(SCRATCH, "picasso2-harvest.json"), encoding="utf-8"))
by_slug = {r["slug"]: r for r in manifest["colours"] if not r.get("error")}
symphony = manifest["symphony"]

lib = hl.load_library()
entries = [r for r in lib["slabs"] if r.get("supplier") == SUPPLIER and not r.get("naturalStone")]
by_colour = {e["colour"]: e for e in entries}
pb = hl.load_pricebook(SUPPLIER)

mains_sheet, gallery_sheet = [], []
rows_out = []
n_new_main = n_upgraded = n_closeups = n_rooms = n_filled_meta = n_dl_fail = 0
touched_colours = set()


# Jade Glacia's OneDrive folder already held an official asset zip (found
# per HARVEST-SPEC's "check the OneDrive folder first" rule) with full-res
# originals of the SAME three site photos (jg2/jg3/jg1 downscaled to 1920x
# 1200 on the live site) -- use the better local originals instead of
# re-downloading the compressed site copies. Maps picks index -> local path.
_JADE_DIR = os.path.join(DEST_ROOT, "Jade Glacia", "_extracted", "Jade Glacia")
JADE_LOCAL_OVERRIDE = {
    1: os.path.join(_JADE_DIR, "Jade Galicia.jpg"),          # closeup (matches jg2.png)
    2: os.path.join(_JADE_DIR, "JADE GLACIA rack.JPG"),      # slab/main (matches jg3.png)
    3: os.path.join(_JADE_DIR, "Application of  JADE GLACIA.png"),  # room (matches jg1.png)
}


def dl(url, colour, i, pick_idx=None, slug=None):
    if not apply_mode:
        return None
    if slug == "jade-galcia" and pick_idx in JADE_LOCAL_OVERRIDE:
        p = JADE_LOCAL_OVERRIDE[pick_idx]
        if os.path.exists(p):
            return p
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="picasso2", cache_key=f"apply-{colour}-{i}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data, DEST_ROOT, colour, used_fn)


def parse_dims(size_text):
    m = re.search(r'(\d+)\s*[x×]\s*(\d+)', size_text or "")
    return f"{m.group(1)}x{m.group(2)}" if m else None


def parse_thicknesses(text):
    return [int(n) for n in re.findall(r'(\d+)\s*mm', text or "")]


def build_slab_sizes(rec, colour):
    dims = parse_dims(rec.get("slab_size", ""))
    ths = parse_thicknesses(rec.get("slab_thickness", ""))
    if dims and ths:
        return hl.format_slab_sizes({t: dims for t in ths})
    pb_row = pb.get(colour)
    if pb_row and pb_row["sizes"]:
        return hl.format_slab_sizes(pb_row["sizes"])
    return ""


for slug, colours in SITE_TO_COLOURS.items():
    rec = by_slug.get(slug)
    if not rec:
        rows_out.append((slug, "NO-PAGE-DATA", "-", "-"))
        continue
    picks = PICKS.get(slug, {"closeups": [], "rooms": []})
    imgs = rec["images"]

    def img_at(idx):
        return imgs[idx - 1] if idx and 1 <= idx <= len(imgs) else None

    main_im = img_at(picks.get("main"))
    closeup_ims = [(idx, img_at(idx)) for idx in picks.get("closeups", [])]
    closeup_ims = [(idx, i) for idx, i in closeup_ims if i]
    room_ims = [(idx, img_at(idx)) for idx in picks.get("rooms", [])]
    room_ims = [(idx, i) for idx, i in room_ims if i]
    skip_gallery = picks.get("skip_gallery", False)

    for colour in colours:
        entry = by_colour.get(colour)
        if not entry:
            rows_out.append((slug, "LIB-ENTRY-MISSING", colour, "-"))
            continue
        touched_colours.add(colour)
        cur_status = entry["image"]["status"]
        will_set_main = bool(main_im and cur_status in ("missing", "closeup-only"))
        rows_out.append((slug, colour, f"{cur_status}->slab" if will_set_main else cur_status,
                          f"{len(closeup_ims)}cu/{len(room_ims)}rm" + (" SKIP" if skip_gallery else "")))

        if not apply_mode:
            continue

        entry["productUrl"] = rec["url"]
        slab_sizes = build_slab_sizes(rec, colour)
        if slab_sizes:
            entry["slabSizes"] = slab_sizes
        blurb = rec.get("description", "")
        finish = rec.get("slab_finish", "")
        details = blurb
        if finish:
            details = f"{blurb} Finish: {finish}." if blurb else f"Finish: {finish}."
        if details:
            entry["details"] = details.strip()[:320]
        alias = SITE_ALIAS.get(slug)
        if not alias and rec["name"].lower() != colour.lower():
            alias = rec["name"]
        if alias:
            aliases = entry.setdefault("aliases", [])
            if alias not in aliases:
                aliases.append(alias)
        n_filled_meta += 1

        if will_set_main:
            p = dl(main_im["url"], colour, "main", pick_idx=picks.get("main"), slug=slug)
            if p and os.path.exists(p):
                fn = hl.to_library_webp(p, entry["id"])
                was_missing = cur_status == "missing"
                entry["image"] = {"file": fn, "status": "slab", "source": rec["url"], "borrowedFrom": ""}
                if was_missing:
                    n_new_main += 1
                else:
                    n_upgraded += 1
                mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "NEW" if was_missing else "UPGRADED"))
            else:
                mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
                n_dl_fail += 1
        elif entry["image"].get("file"):
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
        else:
            mains_sheet.append((colour, None, "still missing"))

        if skip_gallery:
            continue

        gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
        for ci, (idx, im) in enumerate(closeup_ims, 1):
            p = dl(im["url"], colour, f"closeup{ci}", pick_idx=idx, slug=slug)
            if not p or not os.path.exists(p):
                continue
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": rec["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
        for ri, (idx, im) in enumerate(room_ims, 1):
            p = dl(im["url"], colour, f"room{ri}", pick_idx=idx, slug=slug)
            if not p or not os.path.exists(p):
                continue
            fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
            gallery.append({"file": fn, "status": "representative", "kind": "room", "source": rec["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
            n_rooms += 1
        if len(gallery) > 1:
            entry["images"] = gallery

unmatched_lib = sorted(r["colour"] for r in entries if r["colour"] not in touched_colours)
engineered_pb_colours = {r["colour"] for r in entries}
unmatched_pb = sorted(engineered_pb_colours - touched_colours)

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))
print()
print(f"site colour pages: {len(by_slug)} | Symphony (new range, not in price book): {len(symphony)}")
print(f"library Picasso Surfaces engineered colours not touched this run: {unmatched_lib}")

if apply_mode:
    ids_touched = {e["id"]: e for e in entries if e["colour"] in touched_colours}

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, edited in ids_touched.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == SUPPLIER and not s.get("naturalStone"):
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly set: {n_new_main} | mains upgraded: {n_upgraded} | closeups: {n_closeups} | rooms: {n_rooms} | dl fails: {n_dl_fail}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "picasso2-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "picasso2-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing = sorted(r["colour"] for r in entries if r["image"]["status"] != "slab")
    not_on_new_site = sorted(r["colour"] for r in entries
                              if r["colour"] not in touched_colours and r["image"]["status"] == "slab")
    report_path = os.path.join(hl.REPORTS_DIR, "picasso2-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# Picasso Surfaces harvest report -- NEW site (picassosurfaces.co.uk)

Source: https://picassosurfaces.co.uk/wp-sitemap-posts-product-1.xml -- 40 product
pages: 36 real colours + 4 "Symphony ... HD Print" pages (a new HD-print range,
not in the price book -- listed below, NOT added as library entries). The
sitemap XML itself is served with a WordPress "soft 404" HTTP status despite a
valid body (harvest script fetches it with plain curl, no -f, to work around
that); every product page itself returns a normal 200.

Supersedes `harvest_picasso.py`/`reconcile_picasso.py`, which harvested the
OLD site (picassostones.com) last night -- that site is now gone from the
supplier's canonical links; all `productUrl`s here point at the new site.

Every product page has exactly one Elementor "gallery.default" widget (NOT a
standard WooCommerce gallery) holding 1-4 images, all served at a uniform
~1920x1200 (1.6:1) crop regardless of whether the shot is a full slab, a
texture close-up, or a room photo -- so aspect ratio carries no kind signal
on this site (unlike Fugen/Compac). All 102 gallery images across the 36
colour pages were downloaded and visually classified by hand from contact
sheets (`tools/_cache/picasso2/preview_part[123].png`) before writing
`reconcile_picasso2.py`'s PICKS table -- see that file's docstring for the
full reasoning, including two site data-quality issues found along the way
(Celestial Grey/White share identical photo URLs; Taj Honey Onyx and Verde
Onyx each carry a dramatic backlit "onyx-glow" shot that was skipped in
favour of the true-colour studio shot for `image`).

Each page's `<meta name="description">` cleanly contains the marketing blurb
plus a fixed "Slab size available / thickness available / finish(es)
available" block -- used directly for `details`/`slabSizes` (falling back to
the price book only if a page's fields don't parse).

## Counts
- Site colour pages: {len(by_slug)} (Symphony HD-print pages, not added: {len(symphony)} -- {symphony})
- Library Picasso Surfaces engineered colours touched this run: {len(touched_colours)} / {len(entries)}
- Mains newly set (was missing -> slab): {n_new_main}
- Mains upgraded (was closeup-only -> slab): {n_upgraded}
- Main downloads that failed: {n_dl_fail}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- Still not status=slab after this run: {still_missing}
- Library colours confirmed present with a slab image, but NOT on the new site
  (ask Carl -- old-site-only or discontinued?): {not_on_new_site}
- Library colours the site has no page for at all: {sorted(set(unmatched_pb) - set(not_on_new_site))}

## Assumptions
- Cristallo and Erebus have no plinth/rack "whole slab" studio photo on their
  page -- their best full-bleed texture crop was promoted to `image` instead
  (still a real, in-focus, whole-pattern shot at normal viewing scale, not a
  macro grain zoom -- just not standing on a plinth). Worth asking Carl for a
  proper slab photo of these two specifically.
- Taj Honey Onyx image #3 and Cristallo image #1 were excluded entirely (both
  look implausibly pale/mismatched next to every other image on the same
  page -- possible copy-paste error on the supplier's site).
- Verde Onyx and Taj Honey Onyx each have a dramatic backlit "onyx-glow" shot
  (Verde Onyx's glows amber/gold, not green) -- skipped in favour of the
  true-colour daylight studio shot for `image`; the backlit shot was not
  added to the gallery either, to keep the set unambiguous.
- Celestial Grey and Celestial White's pages embed byte-identical image URLs.
  Applied to Celestial White only (both the "cw" filename prefix and page
  name point that way); Celestial Grey's existing main/gallery are untouched
  this run. Ask Carl which product the 3 photos actually belong to.
- `slabSizes`/finish come from each page's own stated text first (all 36
  checked state "3200x1600mm, 20mm and 30mm" except Arabescato Creme, which
  states "Polished and Matte" finishes), price book only as fallback.
- Golden Thunder's page/photos apply to both the "Golden Thunder" and
  "Thunder Gold" price-book rows (pre-existing alias pairing, unchanged).

## Re-run
```
python tools/harvest_picasso2.py             # re-scrape (cached; delete tools/_cache/picasso2 to force)
python tools/reconcile_picasso2.py --report   # dry run, prints the match table
python tools/reconcile_picasso2.py --apply    # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
