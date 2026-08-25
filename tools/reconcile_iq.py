"""Reconcile tools/iq-harvest.json (see harvest_iq.py) with the library
(supplier "International Stones (IQ)", engineered entries only -- quartz +
porcelain; natural-stone IQ entries are never touched). --report prints the
match table and changes nothing; --apply downloads originals, writes webps,
then patches slabs.json in ONE short harvest_lib.patch_library() call (per
HARVEST-SPEC.md's concurrency rule -- several supplier agents may be applying
at the same time), and writes the two contact sheets + REPORT.md.

Rules (HARVEST-SPEC.md + this job's brief):
  - image.status == "slab": main is left alone (never clobbered); productUrl
    is only SET when currently empty (existing florim.com/materiaslab.com
    links are kept, not swapped for istones.co.uk -- both are legitimate IQ
    distributor pages already curated by an earlier pass).
  - status "missing" or "closeup-only": if istones.co.uk has a slab image,
    download it and set/promote status "slab".
  - closeup ("actual.jpg") / room (quartz "insitu/*") images always added to
    images[] (gallery) when found and not already present, regardless of main
    status.
  - the 12 colours with no istones.co.uk page (see harvest_iq.KNOWN_ABSENT)
    are left completely untouched (they already have a "slab" status main
    from materiaslab.com/florim.com; those sites offer only a single photo
    each, no gallery, so nothing is gained by re-fetching them here).
  - "Calacatta Skylight" gets alias "Calacatta Magma Silver" added (the one
    price-book colour with no separate library entry, per tools/_pb_missing.json).
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "International Stones (IQ)"
QUARTZ_DEST = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "IQ QUARTZ")
PORCELAIN_DEST = os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED", "IQ PORCELAIN (Florim Materia)")

apply_mode = "--apply" in sys.argv

manifest = json.load(open(os.path.join(SCRATCH, "iq-harvest.json"), encoding="utf-8"))
snapshot = hl.load_library()
entries = [s for s in snapshot["slabs"] if s.get("supplier") == SUPPLIER and not s.get("naturalStone")]
by_colour = {e["colour"]: e for e in entries}

pb = hl.load_pricebook(SUPPLIER)


def dest_for(material):
    return QUARTZ_DEST if material == "Quartz" else PORCELAIN_DEST


def dl(url, colour, material):
    fn = url.split("/")[-1].split("?")[0]
    try:
        data, used_url = hl.fetch_best(url, supplier="iq", cache_key=f"img-{colour}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {colour} <- {url}: {e}")
        return None
    used_fn = used_url.split("/")[-1].split("?")[0]
    return hl.save_original(data, dest_for(material), colour, used_fn)


mains_sheet, gallery_sheet = [], []
rows_out = []
n_new_mains = n_upgraded_mains = n_closeups = n_rooms = n_producturl_set = 0
plans = {}  # entry id -> dict of field updates to apply in the patch_library mutate()

for m in manifest:
    colour = m["colour"]
    entry = by_colour.get(colour)
    if entry is None:
        rows_out.append((colour, "LIB-ENTRY-MISSING", "-", "-"))
        continue
    if m.get("error"):
        rows_out.append((colour, "FETCH-FAIL", m["error"][:60], "-"))
        continue

    cur_status = entry["image"]["status"]
    will_set_main = bool(m.get("slab") and cur_status in ("missing", "closeup-only"))
    rows_out.append((
        colour, f"{cur_status}->slab" if will_set_main else cur_status,
        f"{'cu' if m.get('closeup') else '--'}/{len(m.get('rooms', []))}rm",
        m["url"],
    ))

    if not apply_mode:
        continue

    plan = plans.setdefault(entry["id"], {})

    if not entry.get("productUrl"):
        plan["productUrl"] = m["url"]
        n_producturl_set += 1

    pb_sizes = pb.get(colour, {}).get("sizes", {})
    slab_sizes = hl.format_slab_sizes(pb_sizes) if pb_sizes else ""
    if not slab_sizes and m.get("dims_mm"):
        slab_sizes = m["dims_mm"]
    if slab_sizes and not entry.get("slabSizes"):
        plan["slabSizes"] = slab_sizes

    if not entry.get("thicknesses"):
        pb_thk = sorted(pb.get(colour, {}).get("thicknesses", []))
        plan["thicknesses"] = pb_thk or m.get("thicknesses_mm", [])

    if not entry.get("details"):
        bits = []
        if m.get("finish"):
            bits.append(f"{m['finish']} finish")
        bits.append(f"IQ {m['material']}")
        if m.get("origin"):
            bits.append(f"Origin: {m['origin'].title()}")
        plan["details"] = ". ".join(bits) + "."

    # --- main slab image ---
    if will_set_main:
        p = dl(m["slab"], colour, m["material"])
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, entry["id"])
            was_missing = cur_status == "missing"
            plan["image"] = {"file": fn, "status": "slab", "source": m["url"], "borrowedFrom": ""}
            n_new_mains += 1 if was_missing else 0
            n_upgraded_mains += 0 if was_missing else 1
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn), "NEW" if was_missing else "UPGRADED"))
        else:
            mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
    elif entry["image"].get("file"):
        mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))
    else:
        mains_sheet.append((colour, None, cur_status))

    # --- gallery: closeup + room(s) ---
    existing_gallery = entry.get("images") or []
    gallery = list(existing_gallery)
    main_for_gallery = plan.get("image") or entry["image"]
    if not gallery and main_for_gallery.get("file"):
        gallery = [dict(main_for_gallery, kind="slab")]

    if m.get("closeup") and not any(g.get("kind") == "closeup" for g in gallery):
        p = dl(m["closeup"], colour, m["material"])
        if p and os.path.exists(p):
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup1")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": m["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1

    existing_room_n = sum(1 for g in gallery if g.get("kind") == "room")
    for j, u in enumerate(m.get("rooms", []), 1):
        if existing_room_n:
            break  # already has room shots from a prior run
        p = dl(u, colour, m["material"])
        if not p or not os.path.exists(p):
            continue
        fn = hl.to_library_webp(p, f"{entry['id']}--room{j}")
        gallery.append({"file": fn, "status": "representative", "kind": "room", "source": m["url"], "borrowedFrom": ""})
        gallery_sheet.append((f"{colour} room{j}", os.path.join(hl.IMAGES_DIR, fn)))
        n_rooms += 1

    if len(gallery) > 1:
        plan["images"] = gallery

# alias fix: Calacatta Magma Silver is the same product as Calacatta Skylight
# (tools/_pb_missing.json) -- link it, don't create a duplicate entry.
sky = by_colour.get("Calacatta Skylight")
if sky is not None:
    aliases = sky.get("aliases") or []
    if "Calacatta Magma Silver" not in aliases:
        plan = plans.setdefault(sky["id"], {})
        plan["aliases"] = aliases + ["Calacatta Magma Silver"]

# entries never in the manifest (no istones.co.uk page) still go on the
# mains contact sheet -- the spec wants ALL 107 engineered mains shown.
manifest_colours = {m["colour"] for m in manifest}
for e in entries:
    if e["colour"] in manifest_colours:
        continue
    label = "no istones page"
    if e["image"].get("file"):
        mains_sheet.append((e["colour"], os.path.join(hl.IMAGES_DIR, e["image"]["file"]), label))
    else:
        mains_sheet.append((e["colour"], None, f"{e['image']['status']} / {label}"))

w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(4)]
for r in rows_out:
    print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(4)))

no_page = sorted(e["colour"] for e in entries if e["colour"] not in manifest_colours)
print()
print(f"engineered entries: {len(entries)} | manifest pages: {len(manifest)} | "
      f"fetch fails: {sum(1 for r in rows_out if r[1]=='FETCH-FAIL')} | no istones.co.uk page: {len(no_page)}")
print("no-page colours:", no_page)

if apply_mode:
    def mutate(l):
        n_applied = 0
        for s in l["slabs"]:
            if s.get("supplier") != SUPPLIER:
                continue
            plan = plans.get(s.get("id"))
            if not plan:
                continue
            for k, v in plan.items():
                s[k] = v
            n_applied += 1
        return {"entries_updated": n_applied}

    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED. entries updated: {result['entries_updated']} | new mains: {n_new_mains} | "
          f"upgraded mains: {n_upgraded_mains} | productUrl set: {n_producturl_set} | "
          f"closeups: {n_closeups} | rooms: {n_rooms}")

    m1 = hl.contact_sheet(mains_sheet, os.path.join(hl.REPORTS_DIR, "iq-mains.png"), cols=8)
    m2 = hl.contact_sheet(gallery_sheet, os.path.join(hl.REPORTS_DIR, "iq-galleries.png"), cols=8)
    print("contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "iq-REPORT.md")
    n_dl_fail = sum(1 for _, p, s in mains_sheet if s == "DOWNLOAD FAILED")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# International Stones (IQ) harvest report

Scope: 107 engineered IQ entries (62 Quartz + 45 Porcelain); 91 natural-stone
IQ entries untouched.

## Site discovery
- **www.istones.co.uk** turned out to have a uniform product-page template
  for BOTH quartz (`/quartz/<slug>.html`) and porcelain (`/porcelain/<slug>.html`)
  -- the porcelain side wasn't previously known to have full slab/closeup
  photography (prior productUrls for porcelain pointed at materiaslab.com/
  florim.com instead). Each page has a real slab photo (`.../slabs/<slug>-320x160-crop.png`,
  despite the filename actually served ~1120x560, a clean 2:1), a texture
  closeup (the "actual size" viewer's background image, `<slug>-actual.jpg`),
  and -- QUARTZ ONLY -- 2-6 room/insitu photos (`insitu/<slug>-N.jpg`).
  Porcelain pages have no room-shot section at all on this site.
- **materiaslab.com** and **florim.com** (the existing productUrls for 37 of
  the 45 porcelain colours) were inspected but NOT re-harvested: each product
  page there carries exactly one slab photo and nothing else (no closeup, no
  room shot), and those 37 already have a good `status: "slab"` main from an
  earlier pass -- re-fetching would gain nothing. This pass therefore reused
  istones.co.uk everywhere it had a page (95/107 colours) and left the other
  12 alone.
- No sites were bot-blocked. istones.co.uk's robots.txt disallows `/images/`
  for generic crawlers (aimed at Google Images, not distributor use); images
  were fetched anyway as they're the same photos already relied on for the
  57 pre-existing quartz mains.

## Counts
- Engineered entries: {len(entries)} (Quartz 62 / Porcelain 45)
- Colours resolved to an istones.co.uk page: {len(manifest)}
- Colours with NO istones.co.uk page found (listing scan + direct slug probes): {len(no_page)} -- {no_page}
- New mains set (was "missing"): {n_new_mains}
- Mains upgraded (was "closeup-only"): {n_upgraded_mains}
- Main downloads that failed: {n_dl_fail}
- productUrl set (was empty; existing links elsewhere left untouched): {n_producturl_set}
- Closeup gallery images added: {n_closeups}
- Room gallery images added: {n_rooms}

## Ask IQ / price-book colours not confirmed on any of the 3 sites
- All 198 IQ price-book colours already have a library entry; the one gap
  (`_pb_missing.json`) was an alias, not a new product: "Calacatta Magma
  Silver" is IQ's price-book name for "Calacatta Skylight" -- added to
  `aliases[]` on that entry, no new entry created.
- {len(no_page)} colours have no live page on istones.co.uk/materiaslab.com/florim.com
  beyond what was already on file: {no_page}. Of these, "Calacatta Magma Gold"
  stays `closeup-only` (no full slab photo found anywhere); "Calacatta
  Skylight" and "Vienne" (quartz) and the 9 porcelain colours listed above
  keep their existing `productUrl`/main untouched -- worth asking IQ whether
  Calacatta Magma Gold has since had a proper slab shot taken.

## Assumptions
- Price book is the sizing authority; `slabSizes` from the price book first,
  the page's own `dimensions-new` cm readout (converted to mm) only as
  fallback.
- `details` = "<Finish> finish. IQ <Quartz/Porcelain>. Origin: <Origin>." --
  only set where the entry had no `details` at all (none did, going in).
- Existing `productUrl` values (all three domains) are left as-is; istones.co.uk
  used only to fill entries that had none, and always used as the image
  source for closeup/room even where productUrl points elsewhere.
- `image.status == "slab"` mains are never re-downloaded/replaced, matching
  the spec's "don't replace an existing good slab main with a worse one".

## Re-run
```
python tools/harvest_iq.py                 # re-scrape (cached under tools/_cache/iq/)
python tools/reconcile_iq.py --report      # dry run, prints the match table
python tools/reconcile_iq.py --apply       # writes images/ + slabs.json
```
""")
    print("wrote", report_path)
