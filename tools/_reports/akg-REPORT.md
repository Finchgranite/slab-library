# AKG Surfaces gallery harvest report

Scope: 49 AKG Surfaces (Coante quartz) library entries. All 49 already had a
true-scale slab main -- this run only added `closeup`/`room` `images[]`.
Originals live under OneDrive `1. QUARTZ/AKG SURFACES (Sempre-Coante)/<Colour>/`,
already populated by the earlier akg_harvest.py (Cloudinary CDN) +
akg_wp_sweep.py (plain wp-content) crawls -- this run classified what was
already there (13 colours needed nothing more), then re-fetched the live
product page for every colour still missing a closeup and/or room to check
for anything the earlier crawl missed.

Classification: AKG's own filenames carry the kind reliably (Kitchen/K-
suffix/Composition/Render/Marketing = room; Close-Up/Bookmatch/PQ/Pattern/
Detail = closeup). Verified a sample of each keyword visually before writing
the classifier (Adira Bronze Render, Zenit Render, Alba Via Composition/
Bookmatch, Bianco Eclipsia PQ, Calacatta Clara Pattern, Carrara Enigma
Marketing). AKG also republishes the SAME full-slab photo as a square 1:1
social-media crop (e.g. Cortina/Sierra/Brittanica/Nuvo/Venato/Vicenza) --
confirmed visually these are NOT texture closeups, so aspect ratio was
deliberately NOT used as a fallback classifier here (unlike other suppliers)
to avoid mislabelling a slab crop as a closeup.

## Counts
- AKG library entries: 49 (all engineered Coante quartz)
- Colours with a closeup added/kept: 18 -- ['Alba Via P', 'Bianco Eclipsia', 'Calacatta Aspen', 'Calacatta Clara', 'Calacatta Edera Low Silica', 'Calacatta Encore', 'Calacatta Magnifico', 'Calacatta Mystic', 'Calacatta Vivaldi Gold', 'Concrete Terreno', 'Hielo', 'Lapland', 'Lux Grey', 'Majestic Brown Ultra', 'Petra Taj Low Silica', 'Sineda', 'Valiente Black Low Silica', 'Zenit']
- Colours with a room added/kept: 40 -- ['Adira Bronze', 'Alba Via P', 'Arabescato Gold', 'Bianco Carrara', 'Brittanica', 'Calacatta Arlena', 'Calacatta Claire', 'Calacatta Clara', 'Calacatta Edera Low Silica', 'Calacatta Encore', 'Calacatta Lucia', 'Calacatta Magnifico', 'Calacatta Marbella', 'Calacatta Nuvo', 'Calacatta Venato', 'Calacatta Verona', 'Calacatta Vicenza', 'Calacatta Vivaldi Gold', 'Carrara Enigma', 'Cathara Bronze', 'Cemento Matte', 'Concrete Terreno', 'Cortina', 'Cremo Jade', 'Elvare', 'Everest', 'Golden Veil', 'Hielo', 'Majestic Brown Ultra', 'Misterio Oro', 'Nebula', 'Petra Taj Low Silica', 'Sierra', 'Sineda', 'Solesta', 'Strataveris', 'Taj Mahal', 'Taj Mahal Supreme', 'Valiente Black Low Silica', 'Zenit']
- Colours with NO closeup and NO room available (from OneDrive or the live
  site): 4 -- ['Aurora Gold', 'Barents', 'Iceberg Mist', 'Velare Gold']
- Mains: all 49 unchanged (true-scale pass already done; this run never
  touches `image`)
- Live product pages re-fetched to check for missed images: 35 (every colour
  short a closeup and/or room after the local pass); zero produced a NEW
  image not already downloaded by the earlier crawls -- i.e. the gaps above
  are real (AKG's page for that colour genuinely has no separate closeup/
  room asset), not a crawl miss.

## Assumptions / notes
- **Velare Gold**: `productUrl` was a placeholder `?s=Velare+Gold` search
  link (never a real product page) and there is no OneDrive folder for it.
  Confirmed via a live site search (`?s=Velare+Gold` and `?s=Velare`) that
  AKG Surfaces no longer lists this colour at all ("Sorry, but nothing
  matched your search terms" / "No results") -- likely discontinued or
  renamed since the price-book row was added. `slabSizes`/`details` filled
  from the price book instead (20/30mm: 3200x1600, Polished). Main image
  kept (from an earlier crawl, source is a Cloudinary URL that may or may
  not still resolve). No gallery possible. Worth asking AKG directly what
  this colour is called now, or dropping it if genuinely discontinued.
- **"Coante Arteo 3D" range** (Adira Bronze, Calacatta Arlena, Calacatta
  Claire, Cathara Bronze, Elvare, Solesta, Strataveris): every page follows
  a fixed 3-shot template -- High-V Slab / Low-V Slab / Render -- so these
  have a room (Render) but genuinely no closeup on the site.
- A handful of colours (Aurora Gold, Barents, Iceberg Mist) have neither a
  closeup nor a room anywhere -- their AKG page is a single hero slab shot
  only (1-4 Cloudinary assets total, all slab angles).
- `images[]` only added where `len(gallery) > 1` i.e. at least one real
  closeup/room exists; colours with neither keep just their existing `image`
  main (no `images[]` array), same as before this run.
- `source` on gallery images is the product page URL (`productUrl`), not a
  per-asset CDN URL -- the originals were already on disk from the earlier
  crawl and per-file source URLs weren't retained in a manifest this agent
  could read (`akg-harvest.json` no longer present in `tools/`).

## Re-run
```
python tools/harvest_akg_galleries.py            # re-scan OneDrive + re-check site (cached under tools/_cache/akg/)
python tools/reconcile_akg_galleries.py --report  # dry run, prints the match table
python tools/reconcile_akg_galleries.py --apply   # writes images/ + slabs.json
```
