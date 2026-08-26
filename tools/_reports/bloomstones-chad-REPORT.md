# Bloomstones — Chad Gage photo zip import (2026-08-26)

Source: `Quartz .zip` (1.9 GB) from Chad Gage, Bloomstones London — `All Quartz + Close Ups/<Colour>/`.
Not a website harvest. Script: `tools/bloom_chad_import.py` (`--report` then `--apply`).

## Counts
- Zip colour folders (after merging Luxe Surfaces duplicates + Super Jumbos stems): **63**
- Matched to Bloomstones quartz entries: **56** (incl. **2** entries created for price-book colours with no entry: Arabescato Storm, Valencia Gold)
- Mains set/replaced: **12** — Arabescato Storm (chad-rerun (was missing)→slab), Arctic Wave (chad-rerun (was missing)→slab), Aurora Beige (chad-rerun (was missing)→slab), Bayside (chad-rerun (was missing)→slab), Blue Sparkle (chad-rerun (was missing)→closeup-only), Calacatta Aurelia (chad-rerun (was missing)→slab), Calacatta Nile (chad-rerun (was missing)→slab), Carrara Gold (chad-rerun (was missing)→slab), Glacial Rift (chad-rerun (was missing)→slab), Taj Velvet Cascade (chad-rerun (was missing)→slab), Valencia Gold (chad-rerun (was missing)→slab), Venus Gold (chad-rerun (was missing)→slab)
- Entries whose site main was kept (Chad slab shots added as `kind: slab` `--alt` images): **44**
- Extra slab images: **52** · closeups: **78** · rooms: **5**
- Unmatched folders (in Chad's photos but not in our book): **7** — Aurora Crystal, Calacatta Supreme, Como, Nova White, Sand Dune, Sorrento, Tuscany Mist
- Bloomstones quartz entries STILL without a `status: slab` main: **8** — Blue Sparkle, Calacatta Panda, Carrara Luni, Concreto Light, Cristallo Extra, Cristallo Grigio, Empire Grey, Gold Cream

## Kind classification
`Full Slab` / bare colour-name / `DSC*` / Super-Jumbo stems = slab; `Close up N` / `IMG_*` = closeup; `Fitted` = room.
Bare-name 4844x3229 (ar 1.5) files are slab-on-A-frame product shots — kept as `kind: slab` (viewed on a thumbnail sheet first).
Raw-camera subfolders (实物图 / inside / outside) copied to OneDrive only, not the library. Dedupe by SHA-256 (Luxe Surfaces/ duplicates, Viola Polished ≡ Viola Leathered close-ups).
Per-file overrides: `Viola Leathered/Viola Leathered Full Slab.jpg` → room; `Viola Leathered/Viola Leathrered Close up 1.JPG` → slab; `Aurora Beige Polished/TM Quartzite Collag..jpg` → skip; `Luxe Surfaces/Red Sparkle/Red Sparkle.jpg` → skip.
Main-status overrides: Blue Sparkle → closeup-only.

## Name mapping (folder → library colour)
blanco white → Bianco White, aurora beige polished → Aurora Beige, viola leathered → Viola, viola polished → Viola, vagli leathered → Vagli leathered, perla gold honed → Perla Gold, calacutta gold → Calacatta Gold, bianco calacutta → Bianco Calacatta, calacatta gold sj → Calacatta Gold, calacatta nile → Calacatta Nile, carrara gold → Carrara Gold, taj mahal → Taj Mahal (Printed Quartz), taj velvelet → Taj Velvet Cascade, venus gold → Venus Gold

## Notes / to ask Chad
- `Calacatta Nile` is only a 555x416 PNG (Super Jumbos) — main set but low-res; ask for the full file.
- `Blue Sparkle` is a 2576x2496 square crop — main set as `closeup-only`; ask for a full-slab shot.
- `Viola Leathered Full Slab.jpg` is a kitchen photo (imported as room); `Viola Polished Full Slab` is the slab. The Viola entry's site main was kept.
- Top-level `Calacatta Gold/` (DSC/IMG raw shots) and `Calacutta Gold/` and `Super Jumbos/CALACATTA GOLD SJ` all landed on the one quartz `Calacatta Gold` entry (price book has one quartz Calacatta Gold, 3500x2000 = SJ). If the T1 folder is a different standard-size product, it needs its own price-book row first.
- `Super Jumbos/TAJ MAHAL` → `Taj Mahal (Printed Quartz)` (quartz; existing OneDrive main kept, SJ shot added as alt). LuxeStone `Taj Mahal` (still missing) may be the same product — not touched (other supplier string).
- Unmatched folders were copied to OneDrive `Bloomstone quartz/_unmatched from Chad 2026-08-26/` only. Calacatta Supreme and Sorrento exist in the book for OTHER suppliers (Nile Stone/UK Stone Co; IQ/KSG) — not Bloomstones.
- The zip holds AppleDouble stubs (`._Concreto Light`, `._Grigio Glitter`, `._Nero Glitter`, `._Nero Marquina`) with NO matching folder — those colours existed on Chad's Mac but were not included; Concreto Light is still `missing`. Ask Chad for them (Grigio/Nero Glitter, Nero Marquina are not in the book).
- Two price-book Bloomstones colours had no library entry (Arabescato Storm, Valencia Gold — Luxe Jumbo rows) — entries created with Chad's photos as mains.
- Site-harvest `scale` is not set on Chad's images (A-frame / hand-held shots; not true-scale).
- Closeups capped at 4 new per entry; skipped: Everest: 2.

## Re-run
```
cd tools
python bloom_chad_import.py --report
python bloom_chad_import.py --apply   # idempotent; rebuilds Chad-sourced items
```
Originals: OneDrive `1. QUARTZ\Bloomstone quartz\<Colour>\`. Contact sheets: `bloomstones-chad-mains.png`, `bloomstones-chad-galleries.png`.
