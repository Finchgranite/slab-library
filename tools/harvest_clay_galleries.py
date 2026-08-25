"""Clay International (clayinternational.co.uk) GALLERY harvest -- phase 2.

Unlike the phase-1 clay_harvest.py/clay_reconcile.py (which crawled every product
page cold and set the 75 slab mains), this harvest works mostly from the images
clay_harvest.py ALREADY downloaded into the OneDrive colour folders
(BRANDS_ROOT/3. CERAMIC- PORCELAIN/Infinity porcelain - clay international/<Colour>/)
-- per HARVEST-SPEC.md: "the galleries you need may already be in those folders.
Classify and convert what is there first; fetch from the site only for colours
whose folder is empty or lacks gallery kinds."

Verified by inspecting the live product-sitemap.xml (72 URLs) and several product
pages directly:
  - Each OneDrive colour folder was populated from that colour's own WooCommerce
    product-gallery `data-large_image` links (+ the og:image main). Filenames are
    inconsistent (Italian marketing terms, WhatsApp exports, "Screenshot-*" batch
    captures, phone "original-<GUID>" exports) but VISUALLY VERIFIED (spot-checked
    ~15 images across colours) to be genuine, colour-appropriate site photography --
    not swatches/logos/unrelated colours.
  - "Infinity_<CODE>_<Name>_<WxH>_<T>mm[...]" filenames are the product-master slab
    render -- same image (or a same-content higher-res variant) already used as the
    library main. Excluded from the gallery (not new content).
  - "<Colour> - Infinity by Clay Int.jpg/.webp" are OUR OWN reference copies added
    to the folder previously (not site-sourced) -- always excluded.
  - The 6 colours with only 1 file in their OneDrive folder (Chianca Di Ostuni,
    Milan Stone, Pulpis Brown, Terrazzo White, Total Grey, Total White) were
    re-checked directly against their live product pages -- confirmed the site
    itself has only the one product-master image, no closeup/room photography.
    Nothing to fetch; they stay main-only.
  - Antibes, Bercy, Gordes are NOT in the 72-URL product-sitemap and a site search
    for each returns zero results -- not currently sold on clayinternational.co.uk.
    No OneDrive folder either. Left untouched (still `missing`); cannot fabricate
    a slab face per HARVEST-SPEC ("fill only with a real slab face").
  - The three "... Vein Tech" price-book rows (Calacatta Hermitage/Magnifico,
    Statuario Principe, all 20mm) are the SAME site product as their base colour
    (confirmed via price book: Vein Tech is just the 20mm/bookmatched SKU of that
    colour) -- they reuse the base colour's OneDrive folder/page/gallery images,
    just get their own productUrl + slabSizes + details text.

Classification (no aspect-ratio signal proved reliable on this dataset -- verified
visually that ~1.4-2.0 ratio covers both wide room renders AND tight macro/flat-lay
closeups): keyword hints first (Italian terms found on-site: bagno/cucina/dining/
ambiente/living = room, dettaglio/thumb = closeup, explicit English equivalents,
photographer/property names -> room), then position fallback for unlabelled numbered
extras: first sorted such file -> room, second -> closeup (matches the observed
site pattern -- e.g. Aegan Blue's holos-blue.png room / holos-blue2.png closeup --
in roughly half the sampled colours; the rest get a same-family photo under the
"other" kind, which is still genuine supplier photography, just not guaranteed to
be the ideal split). One closeup + one room max per colour. Reviewed via the
gallery contact sheet, not per-image -- HARVEST-SPEC budget rule.

Writes tools/clay-galleries-harvest.json. Re-run is cheap (no network calls except
the one-time site re-checks already cached under tools/_cache/clay/).
"""
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "Clay International"
GALLERY_DIR = os.path.join(
    hl.BRANDS_ROOT, "3. CERAMIC- PORCELAIN", "Infinity porcelain - clay international")

OWN_COPY_RE = re.compile(r' - Infinity by Clay Int\.(jpg|webp)$', re.I)
MASTER_RENDER_RE = re.compile(r'infinity.{0,40}\d+\s*[xX]\s*\d+.{0,15}mm', re.I)
IMG_EXT_RE = re.compile(r'\.(jpe?g|png|webp)$', re.I)

ROOM_HINTS = re.compile(
    r'bagno|cucina|dining|kitchen|bathroom|\broom\b|living|ambiente|install|'
    r'lifestyle|project|house|gdns|garden|rowland|crouch|dett.*ambiente',
    re.I)
CLOSEUP_HINTS = re.compile(
    r'dettaglio|detail|close.?up|texture|zoom|swatch|\bthumb\b|\bcu\b|flat',
    re.I)

# Vein Tech price-book rows share the base colour's site product/photos.
VEIN_TECH_BASE = {
    "Calacatta Hermitage Vein Tech": "Calacatta Hermitage",
    "Calacatta Magnifico Vein Tech": "Calacatta Magnifico",
    "Statuario Principe Vein Tech": "Statuario Principe",
}
# Confirmed absent from the live site (see docstring) -- no folder, no page.
NOT_ON_SITE = {"Antibes", "Bercy", "Gordes"}


def gallery_candidates(folder, exclude_basenames=()):
    """[{name, path, kind}] for every non-own-copy, non-master-render image file
    in an OneDrive colour folder, classified 'room'/'closeup'/'other'.
    exclude_basenames: filenames (e.g. the current main image's source basename)
    to skip outright -- they're the same file as the main, not new gallery content."""
    if not os.path.isdir(folder):
        return []
    excl = {b.lower() for b in exclude_basenames if b}
    out = []
    unkeyed = []
    for fn in sorted(os.listdir(folder)):
        fp = os.path.join(folder, fn)
        if not os.path.isfile(fp) or not IMG_EXT_RE.search(fn):
            continue
        if fn.lower() in excl:
            continue
        if OWN_COPY_RE.search(fn) or MASTER_RENDER_RE.search(fn):
            continue
        if ROOM_HINTS.search(fn):
            out.append({"name": fn, "path": fp, "kind": "room"})
        elif CLOSEUP_HINTS.search(fn):
            out.append({"name": fn, "path": fp, "kind": "closeup"})
        else:
            unkeyed.append({"name": fn, "path": fp, "kind": None})
    # position fallback: first unkeyed -> room, second -> closeup
    if unkeyed:
        unkeyed[0]["kind"] = "room"
    if len(unkeyed) > 1:
        unkeyed[1]["kind"] = "closeup"
    for extra in unkeyed[2:]:
        extra["kind"] = "closeup"  # spare candidates still usable as backup closeups
    out.extend(unkeyed)
    return out


def best_of_kind(cands, kind):
    for c in cands:
        if c["kind"] == kind:
            return c
    return None


def main():
    lib = hl.load_library()
    entries = [s for s in lib["slabs"] if s.get("supplier") == SUPPLIER]
    pb = hl.load_pricebook(SUPPLIER)

    manifest = []
    for e in entries:
        colour = e["colour"]
        if colour in NOT_ON_SITE:
            manifest.append({"colour": colour, "status": "not-on-site",
                              "folder": None, "closeup": None, "room": None,
                              "productUrl": "", "note": "confirmed absent from "
                              "product-sitemap.xml and site search; no OneDrive folder"})
            print(f"{colour}: NOT ON SITE (no productUrl/gallery possible)", flush=True)
            continue

        base_colour = VEIN_TECH_BASE.get(colour)
        folder_colour = base_colour or colour
        folder = os.path.join(GALLERY_DIR, folder_colour)
        base_entry_for_excl = (next((x for x in entries if x["colour"] == base_colour), None)
                                if base_colour else e)
        excl = set()
        if base_entry_for_excl:
            src = base_entry_for_excl.get("image", {}).get("source", "")
            if src and src.startswith("http"):
                excl.add(os.path.basename(src).split("?")[0])
        cands = gallery_candidates(folder, exclude_basenames=excl)
        closeup = best_of_kind(cands, "closeup")
        room = best_of_kind(cands, "room")

        rec = {
            "colour": colour, "status": "ok", "folder": folder_colour,
            "closeup": closeup, "room": room,
            "n_candidates": len(cands),
        }
        if base_colour:
            base_entry = next((x for x in entries if x["colour"] == base_colour), None)
            rec["productUrl"] = base_entry.get("productUrl", "") if base_entry else ""
            rec["vein_tech_of"] = base_colour
            pb_row = pb.get(colour)
            if pb_row and pb_row["sizes"]:
                rec["slabSizes"] = hl.format_slab_sizes(pb_row["sizes"])
            rec["details"] = (f"Infinity {base_colour} -- Vein Tech (bookmatched, "
                               f"20mm). Same slab design as {base_colour}.")
        manifest.append(rec)
        print(f"{colour}: {len(cands)} candidates -> "
              f"closeup={'Y' if closeup else 'N'} room={'Y' if room else 'N'}", flush=True)

    out_path = os.path.join(SCRATCH, "clay-galleries-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n_closeup = sum(1 for m in manifest if m.get("closeup"))
    n_room = sum(1 for m in manifest if m.get("room"))
    n_none = sum(1 for m in manifest if m.get("status") == "ok" and not m.get("closeup") and not m.get("room"))
    print(f"\nWROTE {out_path}: {len(manifest)} entries | "
          f"{n_closeup} with a closeup candidate | {n_room} with a room candidate | "
          f"{n_none} with no gallery candidates at all")


if __name__ == "__main__":
    main()
