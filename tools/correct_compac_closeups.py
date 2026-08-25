"""One-off correction pass, 2026-08-25 (orchestrator-requested), Compac only.

Fixes two defects left by the earlier galleries harvest
(harvest_compac_galleries.py / reconcile_compac_galleries.py):

1. Most of the 22 `images[]` items tagged `kind: "closeup"` are actually
   Compac's 3D slab-on-plinth product renders (a whole slab drawn in
   perspective with a dimension ruler beneath it), not texture/detail crops.
   Every one of the 22 was opened and viewed by hand this run (see decision
   table below) and reclassified:
     - perspective slab-on-plinth render -> kind "slab"
     - genuine flat texture/detail crop  -> stays "closeup"
     - Unique Calacatta's "closeup1" turned out to be neither -- it's a
       grayscale bathroom/kitchen lifestyle photo (a second, different room
       shot from the one already filed as room1) -- reclassified "room" so
       the kind accurately describes the content.

2. Three engineered mains render blank/near-blank white:
   Unique Calacatta, Unique Calacatta Black, Unique Calacatta Gold.
   Their OneDrive CABECERA_*/Cabecera_*.jpg source files (the ones the
   earlier compac_harvest.py always used for the main) are NOT blank --
   verified by eye and by pixel stats (real veined slab-face crops,
   ~2000x800, ~2.5:1). The blank webp was a bad conversion from an earlier
   run. Re-converted from the same CABECERA source Original with
   hl.to_library_webp(), overwriting the broken webp. image.status stays
   "slab" (genuine flat slab-face crop) and image.source stays the existing
   productUrl (unchanged -- it was already correct).

Run: python correct_compac_closeups.py --apply   (no --report/dry-run mode;
this is a single hand-verified correction, not a re-runnable harvester)
"""
import os
import sys

import harvest_lib as hl

SUPPLIER = "Compac"

# ---- decision table for the 22 existing `kind: "closeup"` images ---------
# colour -> new kind ("slab" | "closeup" | "room")
RECLASSIFY = {
    "Carrara": "slab",
    "Elegance Michelangelo": "slab",
    "Ice Gold": "slab",
    "Ice Green": "slab",
    "Ice Ink": "slab",
    "Ice Max Gold": "slab",
    "Ice Max Green": "slab",
    "Ice Max Pure": "slab",
    "Ice Max Viola": "slab",
    "Ice Viola": "slab",
    "Luxury Borghini": "slab",
    "Luxury Vagli Oro": "slab",
    "Nebulous Gold": "slab",
    "Unique Arabescato": "slab",
    "Unique Calacatta Black": "slab",
    "Unique Calacatta Gold": "slab",
    "Unique Calacatta Macchia Vecchia": "slab",
    "Unique Venatino": "slab",
    "Unique Argento": "slab",
    "Ice White": "closeup",                       # genuine macro texture shot -- unchanged
    "Luxury Vagli Macchia Vecchia": "closeup",     # genuine macro texture shot -- unchanged
    "Unique Calacatta": "room",                    # mislabeled -- it's a bathroom/kitchen lifestyle photo
}

# ---- the 3 blank/near-blank mains -----------------------------------------
BRANDS_QUARTZ_COMPAC = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "COMPAC")
BLANK_MAINS = {
    "Unique Calacatta": os.path.join(BRANDS_QUARTZ_COMPAC, "Unique Calacatta", "CABECERA_CALACATTA.jpg"),
    "Unique Calacatta Black": os.path.join(BRANDS_QUARTZ_COMPAC, "Unique Calacatta Black", "CABECERA_CALA_BLACK.jpg"),
    "Unique Calacatta Gold": os.path.join(BRANDS_QUARTZ_COMPAC, "Unique Calacatta Gold", "Cabecera_Calacatta_Gold.jpg"),
}

apply_mode = "--apply" in sys.argv

lib = hl.load_library()
entries = [s for s in lib["slabs"] if s.get("supplier") == SUPPLIER and not s.get("naturalStone")]
assert len(entries) == 36, f"expected 36 engineered Compac entries, got {len(entries)}"
by_colour = {e["colour"]: e for e in entries}

decisions = []       # (colour, file, old_kind, new_kind)
mains_fixed = []      # (colour, outcome)
edited_ids = set()

# --- pass 1: reclassify the 22 closeup images ---
for colour, new_kind in RECLASSIFY.items():
    e = by_colour[colour]
    changed = False
    for img in e.get("images", []):
        if img.get("kind") == "closeup" and img.get("file", "").endswith("--closeup1.webp"):
            old_kind = img["kind"]
            if old_kind != new_kind:
                img["kind"] = new_kind
                changed = True
            decisions.append((colour, img["file"], old_kind, new_kind))
    if changed:
        edited_ids.add(e["id"])

# sanity: exactly 22 closeup-kind items existed and were all visited
assert len(decisions) == 22, f"expected 22 closeup decisions, got {len(decisions)}: {decisions}"

# --- pass 2: fix the 3 blank mains (convert now, before the lock) ---
converted = {}
for colour, src in BLANK_MAINS.items():
    e = by_colour[colour]
    if not os.path.exists(src):
        mains_fixed.append((colour, "MISSING source -- image.status set to 'missing'"))
        if apply_mode:
            e["image"]["status"] = "missing"
            for img in e.get("images", []):
                if img.get("kind") == "slab" and img.get("file") == e["image"]["file"]:
                    img["status"] = "missing"
            edited_ids.add(e["id"])
        continue
    if apply_mode:
        fn = hl.to_library_webp(src, e["id"])  # overwrites the blank compac--<id>.webp in place (same canonical filename)
        assert fn == e["image"]["file"], f"unexpected filename change for {colour}: {fn} != {e['image']['file']}"
        e["image"]["status"] = "slab"
        for img in e.get("images", []):
            if img.get("file") == fn:
                img["status"] = "slab"
                img["kind"] = "slab"
        edited_ids.add(e["id"])
        mains_fixed.append((colour, f"re-converted from {os.path.basename(src)} (real slab-face crop, ~2.5:1) -> status 'slab', source unchanged"))
    else:
        mains_fixed.append((colour, f"WOULD re-convert from {os.path.basename(src)}"))

print(f"{len(decisions)} closeup-kind images visited:")
for colour, fn, old, new in decisions:
    mark = "-> " + new if old != new else "(kept)"
    print(f"  {colour:35s} {fn:55s} {old:8s} {mark}")

print("\n3 blank mains:")
for colour, outcome in mains_fixed:
    print(f"  {colour:30s} {outcome}")

if apply_mode:
    def mutate(fresh_lib):
        by_id = {}
        for s in fresh_lib["slabs"]:
            by_id.setdefault(s["id"], []).append(s)
        n = 0
        for eid in edited_ids:
            ed = by_colour_id[eid]
            for s in by_id.get(eid, []):
                if s.get("supplier") == SUPPLIER and not s.get("naturalStone"):
                    s.clear()
                    s.update(ed)
                    n += 1
        return {"updated": n}

    by_colour_id = {e["id"]: e for e in entries}
    result = hl.patch_library(mutate, supplier=SUPPLIER)
    print(f"\nAPPLIED via patch_library: {result}")

    n_slab = sum(1 for _, _, _, new in decisions if new == "slab")
    n_closeup_kept = sum(1 for _, _, old, new in decisions if new == "closeup")
    n_room = sum(1 for _, _, _, new in decisions if new == "room")
    print(f"reclassified to slab: {n_slab} | kept closeup: {n_closeup_kept} | reclassified to room: {n_room}")
else:
    print("\n--report only (no --apply): nothing written")
