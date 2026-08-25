# Compac galleries harvest report

Scope: 36 engineered Compac library entries (12 naturalStone entries untouched).
Source: OneDrive `1. QUARTZ\COMPAC\<Colour>\` folders, already populated by the
earlier `compac_harvest.py`/`compac_reconcile.py` run from en.compac.es (WordPress).
No re-fetch was needed for 35 of 36 colours -- their folders already held every
image compac_harvest.py could find on the live page. One fresh fetch this run:
`https://en.compac.es/color/unique-calacatta-macchia-vecchia/` (its OneDrive
folder has a garbled page-title name), which confirmed the folder already has
everything the live page offers (3 files, no dedicated closeup/room asset).

## Counts
- Engineered entries: 36
- Closeup images added: 22
- Room images added: 20
- Colours with neither closeup nor room source available: 12 -- ['Alaska', 'Arena', 'Ceniza', 'Glaciar', 'Luna', 'Luxury Taj', 'Luxury Travertino', 'Moon', 'Nocturno', 'Plomo', 'Unique Taj', 'Unique Warm']
- Entries with productUrl/slabSizes/details filled this run: 6
- Mains replaced: 0 (34 kept as-is per spec; Luxury Taj/Luxury Travertino BLOCKED, see below)

## Classification approach
Every colour's folder was inspected by hand (not a generic auto-classifier) because
folders mix in "related product" carousel images belonging to OTHER Compac colours
not in our price book (Imperial, Vainille, Perlino, Smoke Gray, Warm/Cool Gray
Glace...) and "*-referencia.jpg"/"Formato_*" files that look like photos but are
actually dimension diagrams (verified visually, excluded). Selections in
`harvest_compac_galleries.py`'s SELECTIONS table:
- **closeup**: a dedicated texture/detail shot where the site has one (`*VETAS*`,
  `detalle-*`); otherwise the `Tablero_*_regla*`/`TABLERO_*_REGLA*` "board with a
  scale ruler" photo where present -- a genuine higher-res detail photo of the
  slab, just wider-framed than a macro crop (used for 21 of the 22 closeups; only
  Ice White, Unique Calacatta and Unique Calacatta Macchia Vecchia had a true
  macro/vase-styled texture shot). No regla/detail asset exists at all for the 9
  "Functional" Standard-size colours (Absolute Blanc, Alaska, Arena, Ceniza,
  Glaciar, Luna, Moon, Nocturno, Plomo) -- Compac simply doesn't publish one for
  that range; left absent rather than guessed.
- **room**: kitchen/bathroom/application photos (`*kitchen*`, `*bath*`, Spanish
  `banyo`/`cocina`/`aplicat`/`amb`(iente), `Slide_*`/`*-2024_1*`/`*_1800x600`
  secondary banner images -- verified by eye to be styled kitchen/bath vignettes,
  not more slab crops -- and numbered application photos e.g. `argento1.jpg`/
  `arabescato1.jpg`, verified to be full kitchen scenes). Absent for 11 colours
  (mostly the same Standard "Functional" range, plus Luxury Vagli Oro and Unique
  Calacatta Macchia Vecchia) where the site has no such photo.
- 8 colours (all "Functional" Standard-size: Alaska, Arena, Ceniza, Glaciar, Luna,
  Moon, Nocturno, Plomo) have neither -- Compac's site only ever gave these a hero
  crop + thumbnail, nothing else photographed.

## Assumptions / needs a human
- **Luxury Taj & Luxury Travertino (BLOCKED)**: spec asked these 2 closeup-only
  mains to be upgraded to a real slab face. Checked: en.compac.es/color/luxury-taj/
  and /luxury-travertino/ both 404, no OneDrive folder exists for either, and
  Wayback Machine CDX returned no snapshots for either URL (checked twice).
  Genuinely no source image exists to harvest from the supplier's own site. Both
  ARE still active price-book rows (Polished, 20/30mm, 3250x1630) so we still sell
  them -- recommend asking Compac directly for current photography, or scanning a
  physical swatch. Mains left unchanged (still closeup-only) this run.
- **Unique Taj & Unique Warm**: same story (404, no folder, no Wayback snapshot) --
  but their mains were already `status: slab` from an earlier run (source
  "onedrive-brands-folder", i.e. placed by hand previously), so nothing to
  upgrade; just filled `details` (collection-name convention) and `slabSizes`
  (from the price book, which still lists both). No gallery images added --
  no source. productUrl left empty for all 4 of these delisted colours; do not
  invent a URL that 404s.
- **Unique Argento**: on the live site (has productUrl) but NOT in the price book
  under any spelling -- `slabSizes` left blank rather than assumed from its Unique
  Collection siblings (all 3250x1630), since we may not actually stock/price it.
  Worth confirming with the price book owner.
- **Unique Calacatta Macchia Vecchia**: `details` filled from its live page title
  ("Unique Collection"); its OneDrive folder is named from a stale page-title save
  ("NEW design - Unique Calacatta Macchia Vecchia. Unique Collection...") --
  cosmetic only, left as-is (renaming it is outside this task's scope).
- Several `Tablero_*_regla*` files repurposed as "closeup" are full-board photos
  with a ruler graphic baked in, not a tight macro crop -- flagged here so the
  orchestrator can judge if that bar is acceptable for the public site; they do
  legitimately show the material's veining/pattern at higher fidelity than the
  hero crop.

## Pre-existing defect noticed (not caused by this run, not fixed here)
The contact sheet shows 3 engineered mains rendering blank/white: **Unique
Calacatta**, **Unique Calacatta Black**, **Unique Calacatta Gold**. Checked
`images/compac--unique-calacatta*.webp` directly: Calacatta and Calacatta
Black are pure `RGB(255,255,255)` (blank canvas), Calacatta Gold is nearly
uniform very-pale grey (mean ~255, min 0/max 255 -- almost no visible
content). File mtimes are 2026-08-03, i.e. from a prior run, well before
today -- not touched by this harvest (this task only ever wrote `--closeup1`/
`--room1` files, never the bare `{id}.webp` main). Their freshly-added
gallery closeup/room images (from a *different* source file each) render
fine, so this is isolated to the existing main image conversion for exactly
these 3 colours. Left as-is per the "don't replace the 34 slab mains" rule --
flagging for the orchestrator to re-run/fix those 3 mains specifically.

## Re-run
```
python tools/harvest_compac_galleries.py              # rebuild the manifest from OneDrive (no network)
python tools/reconcile_compac_galleries.py --report    # dry run, prints the match table
python tools/reconcile_compac_galleries.py --apply     # writes images/ + slabs.json + contact sheets + this report
```

## Correction 2026-08-25

Both defects flagged above are fixed. Every one of the 22 `images[]` items tagged
`kind: "closeup"` was opened and viewed by hand this run (contact sheets +
individual full-res views), not re-run through a classifier. Script:
`tools/correct_compac_closeups.py` (one-off, not part of the re-runnable harvest
chain above). Applied via one `hl.patch_library(mutate, supplier="Compac")` call
-- 20 entries updated, `generated` bumped.

### Closeup reclassification (22 viewed)
Most were Compac's 3D slab-on-plinth product render (a whole slab drawn in
perspective, dimension ruler baked in beneath it) -- not a texture/detail crop.
Reclassified `kind: "closeup"` -> `"slab"` (19):
Carrara, Elegance Michelangelo, Ice Gold, Ice Green, Ice Ink, Ice Max Gold,
Ice Max Green, Ice Max Pure, Ice Max Viola, Ice Viola, Luxury Borghini,
Luxury Vagli Oro, Nebulous Gold, Unique Arabescato, Unique Calacatta Black,
Unique Calacatta Gold, Unique Calacatta Macchia Vecchia, Unique Venatino,
Unique Argento. (These entries already had a real slab-face `image` main from
the earlier harvest, so the reclassified file is now an extra/duplicate-style
slab-kind gallery shot alongside the main -- left in `images[]` as a second
slab image rather than deleted, per the "don't delete images" rule.)

Kept `kind: "closeup"` (2) -- genuine flat macro texture crops, no perspective,
no ruler: **Ice White**, **Luxury Vagli Macchia Vecchia**.

Reclassified `kind: "closeup"` -> `"room"` (1): **Unique Calacatta** -- its
"closeup1" was neither a slab render nor a texture crop; it's a second,
different lifestyle photo (grayscale kitchen sink/hob scene) distinct from
the bathroom scene already filed as its room1. Kind now accurately describes
the content. (Judgment call beyond the literal slab/closeup instruction --
flagging it here since it wasn't one of the two outcomes specified.)

### Three blank mains -- fixed
All three were checkable against their own earlier-harvested OneDrive
original: `1. QUARTZ\COMPAC\<Colour>\CABECERA_*.jpg` / `Cabecera_*.jpg` (the
file `compac_harvest.py`/`compac_reconcile.py` always used for the main).
None of the three originals are blank -- verified by eye and by pixel stats
(2000x800, ~2.5:1, real veined slab-face crops, comparable mean/min/max to
every other colour's CABECERA). The blank/near-blank `.webp` was a bad
conversion from a prior run, isolated to the webp itself. Re-converted with
`hl.to_library_webp(src, entry_id)`, overwriting the broken webp at the same
canonical filename:
- **Unique Calacatta** -- re-converted from `CABECERA_CALACATTA.jpg` ->
  `image.status = "slab"`, `image.source` unchanged (already the correct
  productUrl).
- **Unique Calacatta Black** -- re-converted from `CABECERA_CALA_BLACK.jpg`
  -> `image.status = "slab"`, source unchanged.
- **Unique Calacatta Gold** -- re-converted from `Cabecera_Calacatta_Gold.jpg`
  -> `image.status = "slab"`, source unchanged.
No live-page fetch was needed for any of the three -- the OneDrive original
was sufficient in every case.

### Counts
- Closeup images viewed: 22 (all)
- Reclassified to slab: 19
- Kept closeup: 2
- Reclassified to room: 1
- Blank mains fixed: 3 of 3 (all from existing OneDrive originals, no live fetch)
- Entries touched: 20 (patch_library result)
