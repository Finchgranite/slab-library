"""Reconcile tools/crl-harvest.json with slab-library (supplier CRL, all 109
entries engineered -- no naturalStone rows for this supplier).
--report prints the match table and changes nothing; --apply downloads
originals (or reuses already-downloaded OneDrive originals -- see below),
writes webps, updates slabs.json via hl.patch_library (bumps `generated`),
writes the two contact sheets + REPORT.md.

Image sourcing priority (cheapest/most-authoritative first):
  1. An original already sitting in the OneDrive brand folder for that colour
     (both `1. QUARTZ\\CRL Quartz\\<Colour>\\` and
     `3. CERAMIC- PORCELAIN\\CRL Ceralsio (Porcelain)\\<Colour>\\` already had
     files from earlier manual/harvest passes -- classified by filename
     ("*Slab*"=slab, "*Zoom*"/"*Close-Up*"/"*close-detail*"=closeup,
     "*kitchen*"/"*Header*"=room; "*Featured*"/"*sample*"/"*by CRL*"/
     "*_rotated*" skipped as thumbnails/branding/ambiguous crops -- confirmed
     against Antonella/Arctic Shimmer/Calacatta Dorado/Monte Bianco folders
     before writing this). No network use.
  2. The live crlstone.co.uk page (tools/crl-harvest.json "live" records).
  3. For the 18 colours delisted from the site (12 recovered via a Wayback
     Machine snapshot, 6 with no snapshot -- see harvest_crl.py docstring):
     the media file URL discovered in the archived page's HTML, fetched from
     the LIVE crlstone.co.uk domain first (verified: image files commonly
     still resolve there even after the product page itself was pulled),
     the archive.org image proxy as fallback.

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": NEVER replace the main -- still fill
    productUrl/slabSizes/details/gallery.
  - status "missing" or "closeup-only": if a slab image is found (any of the
    3 sources above), download/convert and upgrade status to "slab".
  - `slabSizes` comes from the price book (has all 109 CRL colours) -- not
    parsed from the page.
"""
import os
import re
import sys

import harvest_lib as hl
import harvest_crl as hc

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "CRL"
QUARTZ_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "CRL Quartz")
PORCELAIN_ROOT = os.path.join(hl.BRANDS_ROOT, "3. CERAMIC- PORCELAIN", "CRL Ceralsio (Porcelain)")

apply_mode = "--apply" in sys.argv

import json
manifest = json.load(open(os.path.join(SCRATCH, "crl-harvest.json"), encoding="utf-8"))
live_by_slug = {r["slug"]: r for r in manifest if r.get("status") == "live"}
disc_by_slug = {r["slug"]: r for r in manifest if r.get("status") == "discontinued-wayback"}
name_to_disc_slug = {name.lower(): slug for slug, name in hc.DISCONTINUED_SLUGS.items()}

lib = hl.load_library()
entries = [s for s in lib["slabs"] if s.get("supplier") == "CRL"]
pb = hl.load_pricebook(SUPPLIER)


# --------------------------------------------------------------- matching --
def find_site_record(entry):
    m = re.search(r'/surfaces/([a-z0-9-]+)/?', entry.get("productUrl") or "")
    if m:
        slug = m.group(1)
        if slug in live_by_slug:
            return live_by_slug[slug], "live"
        if slug in disc_by_slug:
            return disc_by_slug[slug], "disc"
    disc_slug = name_to_disc_slug.get(entry["colour"].lower())
    if disc_slug:
        if disc_slug in disc_by_slug:
            return disc_by_slug[disc_slug], "disc"
        return None, "disc-no-wayback"
    ctoks = hl._toks(entry["colour"])
    best, best_toks = None, None
    for rec in live_by_slug.values():
        rtoks = hl._toks(rec["name"])
        if ctoks and rtoks and hl._fuzzy_subset(ctoks, rtoks):
            if best is None or len(rtoks) < len(best_toks):
                best, best_toks = rec, rtoks
    if best:
        return best, "live"
    return None, "none"


def dest_root_for(material):
    return QUARTZ_ROOT if material == "Quartz" else PORCELAIN_ROOT


def find_local_folder(colour, material):
    root = dest_root_for(material)
    if not os.path.isdir(root):
        return None
    ctoks = hl._toks(colour)
    best, best_toks = None, None
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if not os.path.isdir(p):
            continue
        ftoks = hl._toks(name)
        if ctoks and ftoks and hl._fuzzy_subset(ctoks, ftoks):
            if best is None or len(ftoks) < len(best_toks):
                best, best_toks = name, ftoks
    return os.path.join(root, best) if best else None


_SKIP_LOCAL = re.compile(r'by crl|featured|sample|_rotated|logo|brochure', re.I)


def classify_local(folder):
    """-> (slab_paths, closeup_paths, room_paths), scaled variants collapsed
    to the largest/unsuffixed original per base name."""
    files = [f for f in os.listdir(folder)
             if os.path.isfile(os.path.join(folder, f)) and re.search(r'\.(jpe?g|png|webp)$', f, re.I)]
    groups = {}
    for f in files:
        base = hl._strip_size_suffix(f)
        has_suffix = bool(re.search(r'-\d+x\d+\.', f, re.I))
        rank = 1 if has_suffix else 0
        prev = groups.get(base)
        if prev is None or rank < prev[1]:
            groups[base] = (f, rank)
    slabs, closeups, rooms = [], [], []
    for f in sorted(v[0] for v in groups.values()):
        if _SKIP_LOCAL.search(f):
            continue
        low = f.lower()
        full = os.path.join(folder, f)
        if "slab" in low and not any(x in low for x in ("zoom", "close", "detail")):
            slabs.append(full)
        elif any(x in low for x in ("zoom", "close-up", "closeup", "close-detail")):
            closeups.append(full)
        elif any(x in low for x in ("kitchen", "header", "room", "install", "lifestyle")):
            rooms.append(full)
    return slabs, closeups, rooms


# ------------------------------------------------------------- downloading --
def _live_first_candidates(url):
    m = re.match(r'https?://web\.archive\.org/web/\d+[a-z_]*/(https?://.+)', url)
    return [m.group(1), url] if m else [url]


def download_remote(url, colour, dest_root):
    last_err = None
    for cand in _live_first_candidates(url):
        fn = cand.split("/")[-1].split("?")[0]
        try:
            data = hl.fetch(cand, supplier="crl", cache_key=f"img-{colour}-{fn}"[:150],
                             binary=True, tries=1, polite_delay=1.0)
        except Exception as e:
            last_err = e
            continue
        return hl.save_original(data, dest_root, colour, fn)
    print(f"  DOWNLOAD FAIL {colour} <- {url}: {last_err}")
    return None


# --------------------------------------------------------------------- run --
mains_sheet, gallery_sheet = [], []
rows_out = []
n_new_main = n_upgraded = n_closeups = n_rooms = n_url_fixed = n_still_missing = 0
site_names_matched = set()

for entry in entries:
    colour, material = entry["colour"], entry["material"]
    dest_root = dest_root_for(material)
    rec, kind = find_site_record(entry)
    local_folder = find_local_folder(colour, material)
    local_slab, local_closeups, local_rooms = classify_local(local_folder) if local_folder else ([], [], [])

    cur_status = entry["image"]["status"]
    has_slab_source = bool(rec and rec.get("slab")) or bool(local_slab)
    will_set_main = cur_status in ("missing", "closeup-only") and has_slab_source
    old_url = entry.get("productUrl", "")
    new_url = rec["url"] if rec else old_url
    url_changed = bool(rec) and new_url != old_url

    rows_out.append((
        colour, material, kind if rec else "NO SITE MATCH",
        f"{cur_status}->slab" if will_set_main else cur_status,
        "url-fixed" if url_changed else ("url-ok" if not old_url.count("?s=") else "url-STILL-PLACEHOLDER"),
        f"local:{len(local_closeups)}cu/{len(local_rooms)}rm" if local_folder else
        (f"site:{len(rec.get('closeups', []))}cu/{len(rec.get('rooms', []))}rm" if rec else "-"),
    ))
    if rec:
        site_names_matched.add(rec["name"])

    if not apply_mode:
        continue

    if url_changed:
        entry["productUrl"] = new_url
        n_url_fixed += 1
    pb_row = pb.get(colour)
    if pb_row and pb_row["sizes"]:
        entry["slabSizes"] = hl.format_slab_sizes(pb_row["sizes"])
    finishes = ", ".join(sorted(pb_row["finishes"])) if pb_row and pb_row["finishes"] else ""
    mat_label = "Quartz" if material == "Quartz" else "Ceralsio (Porcelain)"
    blurb = (rec.get("blurb") if rec else "") or ""
    disc_note = "Discontinued by CRL (archived page). " if kind == "disc" else ""
    bits = [b for b in (f"CRL {mat_label}", finishes, disc_note + blurb) if b]
    entry["details"] = " · ".join(bits)[:340]
    if rec and rec["name"].lower() != colour.lower():
        aliases = entry.setdefault("aliases", [])
        if rec["name"] not in aliases:
            aliases.append(rec["name"])

    # --- main slab image ---
    if will_set_main:
        if local_slab:
            p = local_slab[0]
        else:
            p = download_remote(rec["slab"], colour, dest_root)
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            entry["image"] = {"file": fn, "status": "slab",
                               "source": "OneDrive original" if local_slab else (rec["url"] if rec else "web"),
                               "borrowedFrom": ""}
            if was_missing:
                n_new_main += 1
            else:
                n_upgraded += 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn),
                                 "NEW" if was_missing else "UPGRADED"))
        else:
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
    else:
        mains_sheet.append((colour, None, "still missing"))
        n_still_missing += 1

    # --- gallery: closeups + rooms (local originals preferred, else site) ---
    gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
    ci = ri = 0
    closeup_srcs = local_closeups[:2] if local_closeups else \
        [("remote", u) for u in (rec.get("closeups", []) if rec else [])][:2]
    room_srcs = local_rooms[:2] if local_rooms else \
        [("remote", u) for u in (rec.get("rooms", []) if rec else [])][:2]

    for src in closeup_srcs:
        p = src if local_closeups else download_remote(src[1], colour, dest_root)
        if not p or not os.path.exists(p):
            continue
        ci += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
        gallery.append({"file": fn, "status": "closeup", "kind": "closeup",
                         "source": "OneDrive original" if local_closeups else (rec["url"] if rec else "web"),
                         "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
        n_closeups += 1
    for src in room_srcs:
        p = src if local_rooms else download_remote(src[1], colour, dest_root)
        if not p or not os.path.exists(p):
            continue
        ri += 1
        fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
        gallery.append({"file": fn, "status": "representative", "kind": "room",
                         "source": "OneDrive original" if local_rooms else (rec["url"] if rec else "web"),
                         "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1
    if len(gallery) > 1:
        entry["images"] = gallery

# ------------------------------------------------------------------ print --
w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(6)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(6)))

unmatched_lib = sorted(colour for colour, kind_ in
                        ((e["colour"], find_site_record(e)[1]) for e in entries) if kind_ in ("none", "disc-no-wayback"))
site_live_unmatched = sorted(set(r["name"] for r in live_by_slug.values()) - site_names_matched)

print()
print(f"CRL library entries: {len(entries)} | matched to a site/wayback record: "
      f"{sum(1 for r in rows_out if r[2] not in ('NO SITE MATCH',))}")
print(f"unmatched library colours (no live page, no wayback recovery): {unmatched_lib}")
print(f"live site colours with no library/price-book match (site sells, we don't stock or already renamed): "
      f"{len(site_live_unmatched)} -- {site_live_unmatched}")

if apply_mode:
    ids_touched = {e["id"]: e for e in entries}

    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid, edited in ids_touched.items():
            for s in by_id.get(eid, []):
                if s.get("supplier") == "CRL":
                    s.clear()
                    s.update(edited)
                    n += 1
        return {"updated": n}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")
    print(f"mains newly set: {n_new_main} | mains upgraded: {n_upgraded} | closeups: {n_closeups} | "
          f"rooms: {n_rooms} | productUrls fixed: {n_url_fixed} | still no slab: {n_still_missing}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "crl-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "crl-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    still_missing_colours = sorted(e["colour"] for e in entries if e["image"]["status"] != "slab")
    still_placeholder = sorted(e["colour"] for e in entries if "?s=" in (e.get("productUrl") or ""))
    report_path = os.path.join(hl.REPORTS_DIR, "crl-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# CRL harvest report

Source: `https://crlstone.co.uk/wp-json/wp/v2/collection` (WP REST API, `_fields=slug,link,
title,content,excerpt` -- the listing call itself returns each colour's full rendered page
HTML, so 2 paginated requests covered all 102 currently-live colour pages; no per-colour
fetch needed). 18 library colours (12 closeup-only + 6 missing) are NOT in that listing and
return "no results" on-site search -- delisted/discontinued by CRL. `archive.org`'s Wayback
Machine has a snapshot for 12 of those 18; their image files still resolve directly on the
LIVE crlstone.co.uk domain even though the product page itself is gone (verified: a
`Materia-Gris-Slab-image-*.jpg` URL returns HTTP 200 on crlstone.co.uk while
`/surfaces/matteria-gris/` 404s) -- fetched from there first, the archive.org image proxy as
fallback. 6 colours have no wayback snapshot either: Dual Blanco, Dual Negro, Larsen Super
Blanco Gris, Masai Blanco Plus, Masai Piedra, Matteria Taupe -- still `missing`/`closeup-only`.

Where a colour already had originals downloaded to OneDrive from an earlier pass
(`1. QUARTZ\\CRL Quartz\\<Colour>\\`, mostly quartz colours -- the porcelain "Ceralsio" folder
was essentially empty), those local files were reused for the gallery instead of
re-downloading (classified by filename: `*Slab*`=slab, `*Zoom*`/`*Close-Up*`/`*close-detail*`
=closeup, `*kitchen*`/`*Header*`=room).

## Counts
- CRL library entries: {len(entries)} (51 quartz + 58 porcelain per the brief's 109 total)
- Matched to a live or wayback-recovered site record: {sum(1 for r in rows_out if r[2] not in ('NO SITE MATCH',))}
- Mains newly set (was missing): {n_new_main}
- Mains upgraded (was closeup-only): {n_upgraded}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}
- productUrl placeholders (`?s=` search links) replaced with a real page/archive link: {n_url_fixed}
- Still `?s=` placeholder after this run (no site/wayback match found): {still_placeholder}
- Still not status=slab after this run: {still_missing_colours}
- Library colours with no site or wayback match at all: {unmatched_lib}
- Live site colours with no library/price-book match (site sells, we don't currently stock,
  or price-book name differs) -- {len(site_live_unmatched)}: {site_live_unmatched}

## Assumptions / notes
- `slabSizes` taken from the price book (`hl.load_pricebook("CRL")`, which already has sizes
  for all 109 CRL colours) rather than parsed off the page -- price book is the sizing
  authority per HARVEST-SPEC.md.
- `details` = "CRL {{Quartz|Ceralsio (Porcelain)}} · {{finishes from price book}} · {{blurb}}",
  blurb = the page's first 1-3 marketing paragraphs (skipping the generic "part of our silica
  free collection" note), truncated to ~340 chars total.
- For the 5 colours Ananda Blanco / Brazza Crema / Storm Gris / Storm Negro / Totem Gris:
  already `slab` status from an earlier "web"-sourced pass (not crlstone.co.uk), not present
  in the current 102-page listing, and archive.org rate-limited (HTTP 429) this run before a
  wayback check could complete for them -- productUrl left as the `?s=` placeholder; worth a
  follow-up wayback check once archive.org's rate limit clears (Storm Gris already has 10
  originals in the OneDrive porcelain folder from a prior pass, reused for its gallery here).
- Site colours with no library/price-book claim (Soft Concrete, Croma White/Grey/Black,
  Grassi White, Montblanc White, Varese Onice, Bianco Silver, Cosmopolitan Silver, Cardoso
  Grey, Stone, Platinum, Pacific Blanco, Moon Gris, Syros Super Blanco Gris, Oxford Grey,
  Arctic White Polished, Labradorite Royal Blue) are CRL ranges we don't currently stock --
  not added, per the "don't invent entries" rule.
- Never replaced an existing `status: "slab"` main, per the DON'T REPLACE rule, even where the
  live page's own "Full Slab" widget is now empty (Polar White, Grey Reflection, Cristallo
  Perla, Clear White, Windsor Grey all have this) -- their productUrl/gallery were still
  filled from the live page.

## Re-run
```
python tools/harvest_crl.py            # re-scrape (cached; delete tools/_cache/crl to force)
python tools/reconcile_crl.py --report  # dry run, prints the match table
python tools/reconcile_crl.py --apply   # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
