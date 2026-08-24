# Nile Stone harvest report

Two lines under one supplier: Quartz (41, own-brand "Nile Quartz Surfaces",
nilestone.co.uk Angular SPA -- catalogue scraped from the compiled main.js bundle's
JS object literal, images served plain from /assets/quartz-surfaces/); Porcelain (11,
Marazzi "The Top" rebrand -- Nile Trading UK Ltd is Marazzi's sole UK distributor,
primary source marazzitile.co.uk's Grande collection pages, nilestone.co.uk/top-marazzi
as fallback for 2 colours (Capraia, Limestone Sand) absent from marazzitile.co.uk).

## Counts
- Engineered Nile Stone colours in scope: 52 (41 Quartz + 11 Porcelain)
- Quartz matched to site catalogue: 41/41
- Porcelain matched to site catalogue: 11/11
- Mains newly set (was missing): 6
- Mains kept (already status=slab, untouched): 48
- Closeup gallery images added: 75 (74 auto + 1 manual, see Saint Laurent note below)
- Room gallery images added: 74
- Still missing a main after this pass: []
- Unmatched site quartz colours (site has, library/price book doesn't): ['CALACATTA CLASSIC', 'MARQUINA SHIMMER', 'CARRARA SHIMMER', 'REPEN', 'GRIGIO SHIMMERR', 'BIANCO SHIMMER', "CALACATTA VIOLA 'WOW' SATIN", 'CALACATTA SOFT SHIMMER', 'AZUL SHIMMER', 'CALACATTA GOLD SHIMMER', 'ARABESCATO GOLD', 'ALMOND BEIGE']
- Unmatched library colours (no site match this pass): []

## Assumptions / notes
- `productUrl`: quartz -> shared https://www.nilestone.co.uk/quartz-surfaces (SPA modal
  catalogue, no per-colour URL exists); porcelain -> the specific marazzitile.co.uk
  collection page the colour's product-detail block was found on (Capraia/Limestone Sand
  -> nilestone.co.uk/top-marazzi, the only source that carries them).
- `slabSizes` comes from the price book (naming/size authority per HARVEST-SPEC), not the
  site (Marazzi's Grande collection pages print 6mm/12mm TILE-range SKUs, e.g. 160x320cm,
  which are NOT the 3240x1620mm 12/20mm slab format Nile actually stocks -- price book
  wins on size for every colour).
- `details` = "Nile Quartz Surfaces" for quartz; "Marazzi The Top · <range>" for
  porcelain (Marble Look / Stone Look / Solid Color / Concrete Look) per HARVEST-SPEC
  Decisions (brand goes in details, supplier stays "Nile Stone").
- Porcelain "Black" resolves via price-book SKU code MNH9, which on marazzitile.co.uk sits
  under its "Concrete Look" range (not "Solid Color"/"Marble Look") -- confirmed by exact
  code match, a better/primary-source photo than the nilestone.co.uk fallback the
  discovery pass had flagged as the only option.
- Existing `image.status == "slab"` mains were left untouched even where the site had a
  same-or-different crop -- only "missing" mains were (re)set, per rule.
- Quartz images carry almost no filename hints (only "KITCHEN"/"RENDER" ever appear) --
  classification leans on aspect ratio (downloaded + PIL-measured) more than the usual
  filename-first rule; "RENDER" filenames are treated as room shots (kitchen-visualisation
  renders), consistent with what was actually downloaded.
- Originals: quartz -> `1. QUARTZ\Nile stone\<Colour>\` (existing folder, reused);
  porcelain -> new `3. PORCELAIN & SINTERED\NILE STONE (Marazzi)\<Colour>\`.
- Applied via harvest_lib.patch_library (concurrency-safe): all downloads/conversions ran
  against a read-only snapshot first; the live slabs.json was only touched once, at the
  end, re-loaded fresh inside the lock.
- **Manual post-fix, Saint Laurent (porcelain):** the auto-picked marazzitile.co.uk main
  (code M0FS) turned out to be a 120x120cm SQUARE tile-format product shot (1600x1600,
  aspect 1:1) -- a different SKU format from the 3240x1620mm slab Nile actually stocks, and
  not the elongated slab crop every other Nile Stone entry uses. Caught on contact-sheet
  review, not by the aspect-ratio classifier (its 1:1 rejection band is for closeups, not
  mains -- worth tightening in harvest_lib for the next supplier that hits this). Swapped
  in nilestone.co.uk's own /top-marazzi fallback image instead (`MARBLE LOOK - SAINT
  LAURENT - Lux-Satin.jpg`, 1600x799, proper 2:1 slab face, "THE TOP MARAZZI" watermark
  confirms source) via a second small patch_library() call; kept the original square crop
  as `--closeup1` rather than discarding it (still genuine Saint Laurent material, just the
  wrong shape for a main). productUrl updated to match (nilestone.co.uk/top-marazzi).

## Re-run
```
python tools/harvest_nilestone.py             # re-parse cached bundle/pages (delete tools/_cache/nile-stone or /marazzitile to force re-fetch)
python tools/reconcile_nilestone.py --report   # dry run, prints the match table
python tools/reconcile_nilestone.py --apply    # writes images/ + slabs.json
```
