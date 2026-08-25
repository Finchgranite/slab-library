# Kingstone Quartz harvest report

Source: https://kingstonequartz.co.uk (WordPress/Elementor). **All 35 colours sit on ONE
listing page**, `https://kingstonequartz.co.uk/quartz-collection/` (an Elementor image-gallery widget, no per-colour product
pages anywhere on the site -- confirmed via `/collection/` (empty stub), the WP sitemap
(only 7 static pages + unused Avada demo "portfolio" posts), and the gallery itself).
Each gallery item is one `<a href="...-scaled.<ext>"><img alt="<Colour> <SKU>"></a>` --
the href is the WP near-original ("-scaled", ~2560px) upload. **No separate closeup or
room images exist anywhere on the site** -- some filenames/alts say "with close up" but
downloading and inspecting one (Artic Frost, 1280x2560px) confirmed this just means the
single photo is a portrait full-slab shot with a small circled detail-zoom baked into the
same image, not a second file -- so `images[]` galleries stay empty for every entry.

22 of 35 price-book colours already had a `"slab"` main in `slabs.json` from an earlier,
undocumented pass; Artic Frost was spot-checked byte-for-byte against this run's fresh
download and is identical, confirming those 22 are already correctly sourced from this
same site -- left untouched this run except for productUrl/slabSizes/details (their old
productUrl values were dead `?s=` WordPress search-result links, not real product pages;
replaced with the real listing page for all 35 matched entries).

## Counts
- Price-book colours (Kingstone): 35
- Site gallery items: 35 total (34 matched a price-book colour, 1 did not)
- Mains newly set to "slab" (was missing): 12
- Main downloads that failed: 0
- Existing "slab" mains left untouched (productUrl/slabSizes/details refreshed): 22
- Closeup gallery images: 0 | Room gallery images: 0 (site has neither -- single hero photo per colour)
- Still `missing` (no matching site product), 1: ['Nero Calacatta']
- Unmatched site gallery items (no price-book colour), 1:
  - 'Platinum Grey 113' -> https://kingstonequartz.co.uk/wp-content/uploads/2023/07/CL1024-Grey-Shimmer-scaled-e1690278626632.jpg

## Assumptions / judgement calls
- **Portrait "with close-up" photos are the slab main, not a closeup crop.** Several
  filenames (`Artic-Frost-253-...`, `Calacatta-Eclipse-236-with-close-up-...`,
  `Carrara-Michelanglo-211-Slab-with-Close-Up-...`) suggested a texture closeup at first
  glance; downloading and viewing one showed a single portrait-orientation photo of the
  WHOLE slab face (this supplier photographs 3200x1600mm slabs standing tall) with a small
  circled detail-zoom inset drawn onto the same image -- there is no separate closeup file
  to harvest, so every matched item was applied as the `image` main, never as an
  `images[]` closeup/room entry. HARVEST-SPEC's generic slab-aspect check (1.8-2.3:1)
  still holds here once you invert the ratio (1280x2560 -> 0.5 -> 1/0.5 = 2.0), matching
  `harvest_lib.classify_kind`'s symmetric `ar_n` test -- this script does not call
  `classify_kind` at all though, because its filename-hint pass would wrongly tag
  "with-close-up" filenames as kind=closeup before the aspect check ever ran.
- **"Ivory Fantasy 751"** on-site -> price book's **"Ivory Fantasy (Irini)"** (hand-mapped;
  the site drops the "(Irini)" alias the price book carries).
- **"Nabula 611"**: site filename is `Nebula611-...` (their own typo) but the visible page
  alt text reads "Nabula 611", matching the price book's "Nabula" exactly -- used as-is.
- **"Platinum Grey 113"**: a 35th gallery item with no price-book match. Filename
  (`CL1024-Grey-Shimmer-scaled-...`) sits between the price book's "Grey Shimmer" (site
  item "Grey Shimmer 612", filename `grey-shimmer-2.jpg`) and "White Shimmer" (site item
  "White Shimmer 111", filename `CL1022-White-Shimmer-...`) in upload order/naming --
  looks like an older/renamed SKU rather than a genuinely different colour we stock. Not
  assumed to be either; no entry created or touched. **Worth asking Kingstone directly.**
- **Nero Calacatta**: the only price-book colour with no matching product anywhere on the
  site (checked by name and by "Nero"/"Calacatta" substring search across the whole
  listing page HTML -- only "Nero Marquina" and various "Calacatta X" appear, no
  "Nero Calacatta"). Stays `missing`. Worth a supplier check -- possible the price book
  entry is discontinued or renamed.
- `slabSizes` is uniform across all 35 Kingstone price-book rows (20mm and 30mm, both
  3200x1600) -- taken from the price book, not the site (the site states no dimensions).
- `details` = "Kingstone Quartz &lt;SKU&gt; · engineered quartz surface · Polished
  finish" -- SKU from the site's own alt text; "Polished" per the price book's Finish
  column for every Kingstone row (a few site captions say "(Matt Surface)" for 2-3 colours,
  e.g. Artic Frost -- not carried into `details` since the price book, the naming
  authority, lists Polished only; flagged here in case Graham wants a Matt SKU added).

## Re-run
```
python tools/harvest_kingstone.py                  # re-scrape (cached; delete tools/_cache/kingstone to force)
python tools/reconcile_kingstone.py --report        # dry run, prints the match table
python tools/reconcile_kingstone.py --apply         # writes images/ + slabs.json
```
