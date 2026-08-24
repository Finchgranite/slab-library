"""Reconcile tools/brachot-harvest.json with slab-library, for all three
Brachot-group suppliers at once (Brachot/Uniceramica porcelain, Unistone
quartz, BQS quartz -- one site, three product lines, see HARVEST-SPEC.md +
nourl-DISCOVERY.md). --report prints the match table and changes nothing;
--apply downloads originals, writes webps, updates slabs.json (three separate
patch_library() calls, one per supplier string, per HARVEST-SPEC's
concurrency rule) and writes one contact sheet pair + REPORT.md per supplier.

Main image selection: materialStory.finishes[].image (a.storyblok.com,
~1920x954, one true flat slab crop per finish actually sold) is authoritative
-- prefer the finish that matches a price-book Finish for that colour, else
the first finish. Falls back to a pim.images 'fullslab'/'chevalet' shot only
when the page has no finishes[] at all. A crude aspect sanity check (from
the WxH embedded in the storyblok path/filename) guards against picking a
non-slab image; anything that fails it is logged, not silently used.

Rules (HARVEST-SPEC.md):
  - existing image.status == "slab": leave the main alone, still fill
    productUrl/slabSizes/details/gallery.
  - status "missing" or "closeup-only": if we found a slab image, download
    it and set/upgrade to status "slab".
  - price-book colours the site confirms but the library lacks: added.
  - site colours with no library/price-book match: reported, not invented.
  - never share an image file between same-named colours across the three
    brands -- each is harvested from its own product page/materialPim code.
"""
import csv
import json
import os
import re
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(SCRATCH, "brachot-harvest.json")

QUARTZ_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ")
PORCELAIN_ROOT = os.path.join(hl.BRANDS_ROOT, "3. PORCELAIN & SINTERED")

# Reuse each brand's EXISTING OneDrive folder convention (checked first, per spec):
#   BQS colour folders already exist as "BQS <Colour>" directly under 1. QUARTZ/BQS
#   Unistone colour folders already exist as plain "<Colour>" under
#     1. QUARTZ/UNISTONE/A1 Unistone 2026
#   Brachot/Uniceramica has no existing porcelain folder -- create one, plain
#     "<Colour>" names to match the majority convention (e.g. THOMAS GROUP (Atlas Plan)).
SUPPLIER_CFG = {
    "Brachot": {
        "dest_root": os.path.join(PORCELAIN_ROOT, "BRACHOT UNICERAMICA"),
        "folder": lambda colour: colour,
        "brand_label": "Uniceramica",
        "material": "Porcelain",
    },
    "Unistone": {
        "dest_root": os.path.join(QUARTZ_ROOT, "UNISTONE", "A1 Unistone 2026"),
        "folder": lambda colour: colour,
        "brand_label": "Unistone",
        "material": "Quartz",
    },
    "BQS": {
        "dest_root": os.path.join(QUARTZ_ROOT, "BQS"),
        "folder": lambda colour: f"BQS {colour}",
        "brand_label": "BQS",
        "material": "Quartz",
    },
}

# Known price-book spelling quirk (nourl-DISCOVERY.md): the price book's
# "Cararra Misterio" is a typo for the site's "Carrara Misterio" -- record the
# correct spelling as an alias so future colour-name matching doesn't need to
# rediscover this.
ALIASES = {
    "unistone--cararra-misterio": ["Carrara Misterio"],
}

apply_mode = "--apply" in sys.argv

manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
lib = hl.load_library()
by_id = {s["id"]: s for s in lib["slabs"]}


def load_pricebook_filtered(supplier, material):
    """Like harvest_lib.load_pricebook but restricted to one Material -- the
    'Brachot' supplier string covers granite/marble/terrazzo rows too, and a
    few colour names collide across materials (e.g. 'Sahara Noir' is both a
    Marble and a Porcelain row)."""
    rows = list(csv.DictReader(open(hl.PRICEBOOK_CSV, encoding="utf-8-sig")))
    use = [r for r in rows if r.get("Supplier", "") == supplier and r.get("Material", "") == material]
    out = {}
    for r in use:
        colour = r.get("Colour", "").strip()
        if not colour:
            continue
        e = out.setdefault(colour, {"colour": colour, "thicknesses": set(), "finishes": set(), "sizes": {}})
        t = None
        try:
            t = int(float(r["Thickness (mm)"]))
            e["thicknesses"].add(t)
        except Exception:
            pass
        if r.get("Finish"):
            e["finishes"].add(r["Finish"])
        try:
            L = int(float(r["Slab Length (mm)"]))
            W = int(float(r["Slab Width (mm)"]))
            if t is not None:
                e["sizes"][t] = f"{L}x{W}"
        except Exception:
            pass
    return out


_DIM_RE = re.compile(r'/(\d{3,4})x(\d{3,4})/|_(\d{3,4})x(\d{3,4})[_.]')


def url_aspect(url):
    m = _DIM_RE.search(url)
    if not m:
        return None
    g = [x for x in m.groups() if x]
    if len(g) < 2:
        return None
    w, h = int(g[0]), int(g[1])
    if not h:
        return None
    ar = w / h
    return max(ar, 1 / ar)


def fn_of(url):
    return url.split("/")[-1].split("?")[0]


def pick_main(row, pb_finishes):
    """Returns (src_url, chosen_finish_name_or_None, other_finish_srcs, note)."""
    finishes = row.get("finishes") or []
    pbf_lower = {f.lower() for f in pb_finishes}
    chosen = None
    if finishes:
        for f in finishes:
            if f["name"].lower() in pbf_lower:
                chosen = f
                break
        if chosen is None:
            chosen = finishes[0]
    if chosen:
        ar = url_aspect(chosen["src"])
        others = [f["src"] for f in finishes if f is not chosen]
        if ar is None or 1.4 <= ar <= 2.8:
            return chosen["src"], chosen["name"], others, ""
        # failed the sanity check -- fall through to pim slab_imgs, but keep
        # this candidate's other finishes available as closeups regardless
        note = f"finish image {fn_of(chosen['src'])} aspect {ar:.2f} out of range, fell back"
    else:
        others, note = [], ""
    slab_imgs = row.get("slab_imgs") or []
    # prefer a plain 'fullslab' filename over a 'chevalet' (on-easel) shot
    slab_imgs_sorted = sorted(slab_imgs, key=lambda u: 0 if "fullslab" in fn_of(u).lower() else 1)
    for u in slab_imgs_sorted:
        ar = url_aspect(u)
        if ar is None or 1.4 <= ar <= 2.8:
            return u, None, others, note
    if slab_imgs_sorted:
        return slab_imgs_sorted[0], None, others, note or "no slab image passed the aspect check; used best guess"
    return None, None, others, note or "no slab-candidate image found"


def dl(url, dest_root, folder_name, tag, apply_):
    if not apply_:
        return None
    fn = fn_of(url)
    try:
        data, used_url = hl.fetch_best(url, supplier="brachot", cache_key=f"img-{tag}-{fn}"[:150])
    except Exception as e:
        print(f"  DOWNLOAD FAIL {folder_name} <- {url}: {e}")
        return None
    used_fn = fn_of(used_url)
    return hl.save_original(data, dest_root, folder_name, used_fn)


def process_supplier(supplier):
    cfg = SUPPLIER_CFG[supplier]
    rows = [m for m in manifest if not m.get("error") and m["discovery"]["supplier"] == supplier]
    pb = load_pricebook_filtered(supplier, cfg["material"])

    mains_sheet, gallery_sheet = [], []
    rows_out = []
    matched_lib_ids, matched_pb_colours = set(), set()
    n_added = n_new_mains = n_upgraded_mains = n_closeups = n_rooms = n_dl_fail = 0
    notes = []

    for row in rows:
        disc = row["discovery"]
        lib_id = disc["library_id"]
        colour = disc["library_colour"]
        entry = by_id.get(lib_id)
        existed = entry is not None
        pbinfo = pb.get(colour)
        pb_finishes = pbinfo["finishes"] if pbinfo else set()

        main_src, finish_name, other_finish_srcs, note = pick_main(row, pb_finishes)
        if note:
            notes.append(f"{colour}: {note}")

        if entry is None:
            if not pbinfo:
                rows_out.append((colour, "UNMATCHED (no library id, no pricebook)", "-", "-", "-"))
                continue
            entry = {
                "id": lib_id, "supplier": supplier, "colour": colour,
                "material": cfg["material"], "naturalStone": False, "illustrationOnly": False,
                "thicknesses": sorted(pbinfo["thicknesses"]),
                "productUrl": "", "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""},
            }
            lib["slabs"].append(entry)
            by_id[lib_id] = entry
            n_added += 1
        matched_lib_ids.add(lib_id)
        if pbinfo:
            matched_pb_colours.add(colour)

        cur_status = entry["image"]["status"]
        will_set_main = bool(main_src) and cur_status != "slab"
        rows_out.append((
            colour, "match" if existed else "NEW (pricebook confirms)",
            f"{cur_status}->slab" if will_set_main else cur_status,
            finish_name or "-",
            f"{len(row.get('closeup_imgs', []))}cu/{len(row.get('room_imgs', []))}rm",
        ))

        if not apply_mode:
            continue

        entry["productUrl"] = row["url"]
        if lib_id in ALIASES:
            entry["aliases"] = sorted(set(entry.get("aliases", [])) | set(ALIASES[lib_id]))
        pb_sizes = pbinfo["sizes"] if pbinfo else {}
        if pb_sizes:
            entry["slabSizes"] = hl.format_slab_sizes(pb_sizes)
        finish_list = sorted(pb_finishes) if pb_finishes else sorted({f["name"] for f in row.get("finishes", [])})
        if finish_list:
            entry["details"] = f"{cfg['brand_label']} · {', '.join(finish_list)}"
        elif row.get("description"):
            entry["details"] = f"{cfg['brand_label']} · {row['description'][:250]}"

        folder_name = cfg["folder"](colour)

        if will_set_main:
            p = dl(main_src, cfg["dest_root"], folder_name, lib_id, apply_mode)
            if p and os.path.exists(p):
                fn = hl.to_library_webp(p, entry["id"])
                was_missing = cur_status == "missing"
                entry["image"] = {"file": fn, "status": "slab", "source": row["url"], "borrowedFrom": ""}
                if was_missing:
                    n_new_mains += 1
                else:
                    n_upgraded_mains += 1
                mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, fn),
                                     "NEW" if was_missing else "UPGRADED"))
            else:
                n_dl_fail += 1
                mains_sheet.append((colour, None, "DOWNLOAD FAILED"))
        elif entry["image"].get("file"):
            mains_sheet.append((colour, os.path.join(hl.IMAGES_DIR, entry["image"]["file"]), "kept"))

        gallery = [dict(entry["image"], kind="slab")] if entry["image"].get("file") else []
        ci = ri = 0
        closeup_candidates = list(row.get("closeup_imgs", [])) + other_finish_srcs
        seen_fn = {fn_of(main_src)} if main_src else set()
        for u in closeup_candidates:
            if ci >= 4:
                break
            if fn_of(u) in seen_fn:
                continue
            seen_fn.add(fn_of(u))
            p = dl(u, cfg["dest_root"], folder_name, lib_id, apply_mode)
            if not p or not os.path.exists(p):
                continue
            ci += 1
            fn = hl.to_library_webp(p, f"{entry['id']}--closeup{ci}")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": row["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} CU{ci}", os.path.join(hl.IMAGES_DIR, fn)))
            n_closeups += 1
        for u in row.get("room_imgs", []):
            if ri >= 6:
                break
            if fn_of(u) in seen_fn:
                continue
            seen_fn.add(fn_of(u))
            p = dl(u, cfg["dest_root"], folder_name, lib_id, apply_mode)
            if not p or not os.path.exists(p):
                continue
            ri += 1
            fn = hl.to_library_webp(p, f"{entry['id']}--room{ri}")
            gallery.append({"file": fn, "status": "representative", "kind": "room", "source": row["url"], "borrowedFrom": ""})
            gallery_sheet.append((f"{colour} room{ri}", os.path.join(hl.IMAGES_DIR, fn)))
            n_rooms += 1
        if len(gallery) > 1:
            entry["images"] = gallery

    unmatched_pb = sorted(set(pb) - matched_pb_colours)

    print(f"\n===== {supplier} =====")
    w = [max((len(str(r[i])) for r in rows_out), default=8) for i in range(5)]
    for r in rows_out:
        print(" | ".join(f"{str(r[i]):<{w[i]}}" for i in range(5)))
    n_match = sum(1 for r in rows_out if r[1] == "match")
    n_unmatched = sum(1 for r in rows_out if "UNMATCHED" in r[1])
    print(f"site colours: {len(rows)} | matched/updated: {n_match} | added: {n_added} | unmatched: {n_unmatched}")
    print(f"unmatched price-book {supplier} colours (material={cfg['material']}, not seen on site): {unmatched_pb}")
    if notes:
        print("notes:")
        for n in notes:
            print(" -", n)

    result = dict(supplier=supplier, rows=len(rows), matched=n_match, added=n_added,
                  new_mains=n_new_mains, upgraded_mains=n_upgraded_mains, dl_fail=n_dl_fail,
                  closeups=n_closeups, rooms=n_rooms, unmatched_site=n_unmatched,
                  unmatched_pb=unmatched_pb, notes=notes,
                  mains_sheet=mains_sheet, gallery_sheet=gallery_sheet)
    return result


results = {sup: process_supplier(sup) for sup in ("Brachot", "Unistone", "BQS")}

if apply_mode:
    for supplier in ("Brachot", "Unistone", "BQS"):
        target_ids = {m["discovery"]["library_id"] for m in manifest if m["discovery"]["supplier"] == supplier}

        def mutate(l, target_ids=target_ids, supplier=supplier):
            fresh_by_id = {s["id"]: s for s in l["slabs"]}
            for lib_id in target_ids:
                if lib_id in by_id and lib_id not in fresh_by_id:
                    l["slabs"].append(by_id[lib_id])
                elif lib_id in fresh_by_id and lib_id in by_id:
                    idx = l["slabs"].index(fresh_by_id[lib_id])
                    l["slabs"][idx] = by_id[lib_id]
            return {"touched": len(target_ids)}

        r = hl.patch_library(mutate, supplier=supplier)
        print(f"patch_library({supplier}) -> {r}")

    for supplier, res in results.items():
        cfg = SUPPLIER_CFG[supplier]
        tag = supplier.lower()
        m1 = hl.contact_sheet(res["mains_sheet"], os.path.join(hl.REPORTS_DIR, f"brachot-{tag}-mains.png"), cols=8)
        m2 = hl.contact_sheet(res["gallery_sheet"], os.path.join(hl.REPORTS_DIR, f"brachot-{tag}-galleries.png"), cols=8)
        print(f"{supplier} contact sheets:", m1, m2)

    report_path = os.path.join(hl.REPORTS_DIR, "brachot-REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Brachot / Unistone / BQS harvest report\n\n")
        f.write("Source: www.brachot.com (Next.js/Storyblok), one company/site, three in-house "
                "brands (`-uniceramica` porcelain, `-unistone` quartz, `-bqs` quartz). Colour list "
                "and per-colour productUrl came from `tools/_reports/nourl-discovery.json` "
                "(111/111 already resolved by the no-URL discovery pass) -- no sitemap crawl needed "
                "this run. Main slab image = `materialStory.finishes[].image` (a.storyblok.com, one "
                "true flat slab crop per finish sold), matched to a price-book Finish where possible; "
                "falls back to a `materialPim.images[]` 'fullslab'/'chevalet' shot only when a page "
                "has no finishes[]. Room shots = kitchen/bathroom/wall-tagged `materialPim.images[]` "
                "plus 11 dedicated `/en/references/.../kitchen-...` pages found for BQS colours "
                "during discovery (2 of those 13 URLs 404'd this run). One dead productUrl "
                "(Brachot Taj Mahal, code KSXTAMA had no images/finishes) was swapped for its "
                "sibling code KSXTMA, per that colour's own discovery note.\n\n")
        for supplier, res in results.items():
            f.write(f"## {supplier}\n")
            f.write(f"- Site colour pages harvested: {res['rows']}\n")
            f.write(f"- Matched/updated existing library entries: {res['matched']}\n")
            f.write(f"- New library entries added (price-book confirmed): {res['added']}\n")
            f.write(f"- Mains newly set (was missing): {res['new_mains']}\n")
            f.write(f"- Mains upgraded (was closeup-only): {res['upgraded_mains']}\n")
            f.write(f"- Main downloads that failed: {res['dl_fail']}\n")
            f.write(f"- Closeup gallery images added: {res['closeups']}\n")
            f.write(f"- Room gallery images added: {res['rooms']}\n")
            f.write(f"- Unmatched site colours (neither library nor price book claims it): {res['unmatched_site']}\n")
            f.write(f"- Unmatched price-book {supplier} colours (not seen on site): "
                    f"{len(res['unmatched_pb'])} -- {res['unmatched_pb']}\n")
            if res["notes"]:
                f.write(f"- Notes: {'; '.join(res['notes'][:15])}"
                        f"{' ...' if len(res['notes']) > 15 else ''}\n")
            f.write("\n")
        f.write("""## Assumptions
- Price book is the naming/size/finish authority; `slabSizes` and the finish
  list in `details` come from the price book, filtered to the right Material
  for the (shared) 'Brachot' supplier string, which also carries granite/
  marble/terrazzo rows outside this phase's scope.
- Existing `image.status == "slab"` mains are left alone even if the site's
  crop differs -- only "missing"/"closeup-only" entries got a new main.
- Images are never shared between same-named colours across the three brands
  (each harvested from its own materialPim code/page).
- `unistone--cararra-misterio`'s price-book spelling ("Cararra") is a known
  typo for the site's "Carrara Misterio" -- matched via the discovery-supplied
  library_id directly, not by name matching, so the typo caused no mismatch.

## Re-run
```
python tools/harvest_brachot.py                 # re-scrape (cached under tools/_cache/brachot/)
python tools/reconcile_brachot.py --report       # dry run, prints the match tables
python tools/reconcile_brachot.py --apply        # writes images/ + slabs.json
```
""")
    print("\nwrote", report_path)
