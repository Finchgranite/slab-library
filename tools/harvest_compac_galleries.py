"""Compac galleries harvest (phase 2) -- closeup/room images for the 36
engineered Compac colours, sourced from the OneDrive folders that
compac_harvest.py already populated from en.compac.es (WordPress). Natural
entries (naturalStone: true) are out of scope and never touched.

Every colour's folder was inspected by hand (contact-sheet + visual spot
checks) to build the SELECTIONS table below -- this is NOT a generic
scraper, because the folders mix in "related product" carousel images from
OTHER Compac colours (e.g. Imperial/Vainille/Perlino/Smoke Gray/Glace
variants) that are not in our price book, and "*-referencia.jpg" /
"Formato_*" files that look like photos but are actually dimension
diagrams. Patterns are matched as case-insensitive substrings against the
folder's filenames (avoids literal-unicode filename issues -- several
original filenames contain a mis-encoded (c) glyph).

Fresh site checks done this run (see compac-galleries-harvest.json /
REPORT.md for detail):
  - https://en.compac.es/color/unique-calacatta-macchia-vecchia/ fetched
    fresh (its OneDrive folder has a garbled name from a page-title save) --
    confirms the folder already holds everything the live page has.
  - https://en.compac.es/color/{luxury-taj,luxury-travertino,unique-taj,
    unique-warm}/ all 404 on the live site AND have no OneDrive folder --
    genuinely delisted colours (still in the price book). Wayback Machine
    CDX checked too (partly degraded/offline during this run): no snapshots
    found for luxury-taj/luxury-travertino/unique-taj; unique-warm
    inconclusive (Archive.org was returning its "temporarily offline" page).
    No source images exist to harvest for these 4 -- galleries left empty,
    documented as blocked in the report.

Writes tools/compac-galleries-harvest.json.
"""
import json
import os

import harvest_lib as hl

DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "COMPAC")

# colour -> actual OneDrive folder name, only where it differs from the colour name
FOLDER_OVERRIDE = {
    "Unique Calacatta Macchia Vecchia":
        "NEW design - Unique Calacatta Macchia Vecchia. Unique Collection. "
        "Technological Quartz - COMPAC The Surfaces Company",
}

# colour -> {"closeup": substring pattern or None, "room": substring pattern or None}
# Patterns verified unique within each colour's folder listing by hand.
SELECTIONS = {
    "Absolute Blanc": {"closeup": None, "room": "amb-1"},
    "Alaska": {"closeup": None, "room": None},
    "Arena": {"closeup": None, "room": None},
    "Carrara": {"closeup": "REGLA-scaled", "room": None},
    "Ceniza": {"closeup": None, "room": None},
    "Elegance Michelangelo": {"closeup": "regla_LOW-scaled", "room": "2024_1"},
    "Glaciar": {"closeup": None, "room": None},
    "Ice Gold": {"closeup": "REGLA_4000X3000_GOLD", "room": "1800x600"},
    "Ice Green": {"closeup": "REGLA_4000X3000_GREEN", "room": "1800x600"},
    "Ice Ink": {"closeup": "REGLA_INK", "room": "1800x600"},
    "Ice Max Gold": {"closeup": "regla_LOW-scaled", "room": "1800x600"},
    "Ice Max Green": {"closeup": "regla_LOW-scaled", "room": "1800x600"},
    "Ice Max Pure": {"closeup": "CONREGLA", "room": "Slide_ICE_MAX_PURE"},
    "Ice Max Viola": {"closeup": "regla_LOW-scaled", "room": "1800x600"},
    "Ice Viola": {"closeup": "REGLA_VIOLA", "room": "1800x600"},
    "Ice White": {"closeup": "VETAS", "room": None},
    "Luna": {"closeup": None, "room": None},
    "Luxury Borghini": {"closeup": "regla_LOW-scaled", "room": "2024_1"},
    "Luxury Taj": {"closeup": None, "room": None},          # no source (see module docstring)
    "Luxury Travertino": {"closeup": None, "room": None},   # no source
    "Luxury Vagli Macchia Vecchia": {"closeup": "kitchen_det_horz", "room": "bath_nologo"},
    "Luxury Vagli Oro": {"closeup": "REGLA_U-CALACATTA-VAGLI-scaled", "room": None},
    "Moon": {"closeup": None, "room": None},
    "Nebulous Gold": {"closeup": "Regla-scaled", "room": "Slide_Nebulous_Genesis"},
    "Nocturno": {"closeup": None, "room": None},
    "Plomo": {"closeup": None, "room": None},
    "Snow": {"closeup": None, "room": "snow_render"},
    "Unique Arabescato": {"closeup": "REGLA-scaled", "room": "arabescato1"},
    "Unique Argento": {"closeup": "Regla-scaled", "room": "argento1"},
    "Unique Calacatta": {"closeup": "detalle-calacata-glace", "room": "calacatta_banyo"},
    "Unique Calacatta Black": {"closeup": "REGLA-scaled", "room": "render"},
    "Unique Calacatta Gold": {"closeup": "Regla_Calacatta_Gold-scaled", "room": "Slide_Calacatta_Gold"},
    "Unique Calacatta Macchia Vecchia": {"closeup": "Tablero_CR_MACCHIAVECCHIA", "room": None},
    "Unique Taj": {"closeup": None, "room": None},          # no source
    "Unique Venatino": {"closeup": "REGLA-scaled", "room": "aplicat_UNIQUEVENATIN"},
    "Unique Warm": {"closeup": None, "room": None},         # no source


}


def find(folder, pattern):
    if not pattern or not os.path.isdir(folder):
        return None
    hits = [f for f in os.listdir(folder) if pattern.lower() in f.lower()]
    if len(hits) != 1:
        if hits:
            print(f"  AMBIGUOUS pattern {pattern!r} in {folder}: {hits}")
        return None
    return hits[0]


def main():
    lib = hl.load_library()
    entries = [s for s in lib["slabs"] if s.get("supplier") == "Compac" and not s.get("naturalStone")]
    print(len(entries), "engineered Compac library entries")

    manifest = []
    for e in entries:
        colour = e["colour"]
        sel = SELECTIONS.get(colour)
        if sel is None:
            print(f"  NO SELECTION ENTRY for {colour!r} -- add it to SELECTIONS")
            sel = {"closeup": None, "room": None}
        folder_name = FOLDER_OVERRIDE.get(colour, colour)
        folder = os.path.join(DEST_ROOT, folder_name)
        closeup_fn = find(folder, sel["closeup"])
        room_fn = find(folder, sel["room"])
        row = {
            "id": e["id"], "colour": colour, "folder": folder,
            "closeup_file": closeup_fn, "room_file": room_fn,
            "source_url": e.get("productUrl") or "",
        }
        manifest.append(row)
        flag = "OK" if (closeup_fn or room_fn or not os.path.isdir(folder)) else "folder-exists-but-nothing-picked"
        print(f"{colour:<36} closeup={closeup_fn!r:<55} room={room_fn!r:<45} [{flag}]")

    out_path = os.path.join(hl.TOOLS_DIR, "compac-galleries-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n_cu = sum(1 for r in manifest if r["closeup_file"])
    n_rm = sum(1 for r in manifest if r["room_file"])
    n_none = sum(1 for r in manifest if not r["closeup_file"] and not r["room_file"])
    print(f"\nWROTE {out_path}: {len(manifest)} colours | closeup found: {n_cu} | "
          f"room found: {n_rm} | neither: {n_none}")


if __name__ == "__main__":
    main()
